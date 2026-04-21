from __future__ import annotations

import re

from job_app_ops.agents.llm_client import LLMClient
from job_app_ops.config import Settings
from job_app_ops.schemas import (
    ApprovalPacket,
    CandidateProfile,
    GeneratedArtifact,
    JobOpportunity,
    JobRequirements,
    MatchAssessment,
    ProfileAssetKind,
)
from job_app_ops.services.profile_vault import ProfileVaultService


class JobApplicationAgents:
    def __init__(self, settings: Settings, profile_vault: ProfileVaultService, llm: LLMClient | None = None) -> None:
        self.settings = settings
        self.profile_vault = profile_vault
        self.llm = llm

    def match(self, profile: CandidateProfile, opportunity: JobOpportunity, requirements: JobRequirements) -> MatchAssessment:
        vault = self.profile_vault.get_vault(profile.profile_id)
        reference_texts = self.profile_vault.get_reference_texts(
            profile.profile_id,
            kinds=(ProfileAssetKind.cv, ProfileAssetKind.previous_application, ProfileAssetKind.reference_letter),
        )
        profile_skills = {skill.name.lower(): skill for skill in profile.skills}
        matched = [skill for skill in requirements.required_skills if skill.lower() in profile_skills or _find_skill_evidence(reference_texts, skill)]
        missing = [skill for skill in requirements.required_skills if skill.lower() not in profile_skills]
        missing = [skill for skill in missing if not _find_skill_evidence(reference_texts, skill)]

        skills_score = 30 if not requirements.required_skills else round(30 * len(matched) / len(requirements.required_skills))
        experience_score = 20 if requirements.years_required == 0 else min(20, max((skill.years for skill in profile.skills), default=0) * 20 // max(requirements.years_required, 1))
        language_hits = sum(1 for lang in requirements.language_requirements if lang in profile.languages)
        language_score = 10 if not requirements.language_requirements else round(10 * language_hits / len(requirements.language_requirements))
        location_score = 15 if opportunity.location_mode != "onsite" else (15 if any("Zurich" in location for location in profile.preferred_locations) else 0)
        salary_score = 5 if not opportunity.compensation_hint else (5 if _extract_comp_k(opportunity.compensation_hint) >= profile.salary_floor else 0)
        mandatory_score = 20 if not missing else max(0, 20 - len(missing) * 4)

        hard_blockers = list(requirements.hard_blockers)
        if opportunity.work_authorization_requirement and "Switzerland" in opportunity.work_authorization_requirement and "Switzerland" not in profile.work_authorization:
            hard_blockers.append("Profile does not clearly show Swiss work authorization.")
        if opportunity.location_mode == "onsite" and not any("Munich" in location for location in profile.preferred_locations) and "munich" in opportunity.normalized_description.lower():
            hard_blockers.append("Strict onsite Munich role conflicts with current preferred locations.")
        if not opportunity.source_approved:
            hard_blockers.append(opportunity.source_policy_note)

        overall_score = max(0, min(100, skills_score + experience_score + language_score + location_score + salary_score + mandatory_score))
        ready = overall_score >= self.settings.match_threshold and not hard_blockers

        evidence_highlights: list[str] = []
        for skill_name in matched[:5]:
            skill = profile_skills.get(skill_name.lower())
            display_name = skill.name if skill else skill_name
            evidence = _clean_evidence(skill.evidence) if skill else ""
            evidence = evidence or _find_skill_evidence(reference_texts, skill_name)
            if evidence:
                evidence_highlights.append(f"{display_name}: {evidence}")
            else:
                evidence_highlights.append(f"{display_name}: Listed in the structured profile and relevant to the role.")

        evidence_highlights += [_clean_evidence(item) for item in vault.reference_highlights]
        evidence_highlights += [_clean_evidence(item) for item in profile.achievements]
        evidence_highlights = _unique_nonempty(evidence_highlights)[:4]

        return MatchAssessment(
            overall_score=overall_score,
            decision="ready_to_tailor" if ready else ("blocked_by_policy" if hard_blockers else "below_threshold"),
            ready_for_tailoring=ready,
            score_breakdown={
                "skills": skills_score,
                "experience": experience_score,
                "mandatory": mandatory_score,
                "location": location_score,
                "languages": language_score,
                "salary": salary_score,
            },
            evidence_highlights=evidence_highlights,
            missing_evidence=missing,
            hard_blockers=hard_blockers,
        )

    def generate_artifacts(
        self,
        profile: CandidateProfile,
        opportunity: JobOpportunity,
        requirements: JobRequirements,
        assessment: MatchAssessment,
    ) -> list[GeneratedArtifact]:
        slug = _slugify(f"{opportunity.company}-{opportunity.role}")
        cv = GeneratedArtifact(
            artifact_type="cv",
            file_name=f"{slug}-cv.md",
            content=self._build_cv(profile, opportunity, requirements, assessment),
        )
        letter = GeneratedArtifact(
            artifact_type="motivation_letter",
            file_name=f"{slug}-motivation-letter.md",
            content=self._build_letter(profile, opportunity, requirements, assessment),
        )
        answers = GeneratedArtifact(
            artifact_type="application_answers",
            file_name=f"{slug}-answers.md",
            content=self._build_answers(profile, opportunity, requirements, assessment),
        )
        packet = GeneratedArtifact(
            artifact_type="approval_packet",
            file_name=f"{slug}-approval-packet.md",
            content=self._build_packet(opportunity, assessment),
        )
        return [cv, letter, answers, packet]

    def review(
        self,
        opportunity: JobOpportunity,
        assessment: MatchAssessment,
        artifacts: list[GeneratedArtifact],
    ) -> ApprovalPacket:
        risks = assessment.hard_blockers or (
            ["Preferred skills are only partially covered."] if assessment.missing_evidence else ["No major blockers; final operator review still required."]
        )
        action = {
            "email": f"Send the application by email to {opportunity.destination or 'the configured recipient'}.",
            "company_site": f"Prepare the company-site submission for {opportunity.destination or 'the target company site'}.",
            "manual_handoff": f"Prepare a manual handoff packet for {opportunity.destination or 'LinkedIn / Indeed submission'}.",
        }[opportunity.submission_channel.value]

        return ApprovalPacket(
            summary=f"{opportunity.role} at {opportunity.company} scored {assessment.overall_score}% and is ready for operator approval.",
            exact_action_after_approval=action,
            risks=risks,
            artifacts=artifacts,
        )

    def _build_cv(self, profile: CandidateProfile, opportunity: JobOpportunity, requirements: JobRequirements, assessment: MatchAssessment) -> str:
        reference_texts = self.profile_vault.get_reference_texts(
            profile.profile_id,
            kinds=(ProfileAssetKind.cv, ProfileAssetKind.previous_application),
        )
        reference_texts = _rank_reference_texts(reference_texts, opportunity, requirements)
        fallback = _build_professional_cv(profile, opportunity, requirements, assessment, reference_texts)
        generated = self._generate_cv_with_llm(profile, opportunity, requirements, assessment, reference_texts)
        return generated if _looks_like_complete_document(generated, min_length=900) and _looks_role_tailored(generated, opportunity, requirements) else fallback

    def _build_letter(self, profile: CandidateProfile, opportunity: JobOpportunity, requirements: JobRequirements, assessment: MatchAssessment) -> str:
        reference_texts = self.profile_vault.get_reference_texts(
            profile.profile_id,
            kinds=(ProfileAssetKind.cv, ProfileAssetKind.previous_application, ProfileAssetKind.motivation_letter),
        )
        reference_texts = _rank_reference_texts(reference_texts, opportunity, requirements)
        fallback = _build_professional_letter(profile, opportunity, requirements, assessment, reference_texts)
        generated = self._generate_letter_with_llm(profile, opportunity, requirements, assessment, reference_texts)
        return generated if _looks_like_complete_document(generated, min_length=450) and _looks_role_tailored(generated, opportunity, requirements) else fallback

    def _build_answers(self, profile: CandidateProfile, opportunity: JobOpportunity, requirements: JobRequirements, assessment: MatchAssessment) -> str:
        skills_phrase = _skills_phrase(requirements.required_skills[:4] or [skill.name for skill in profile.skills[:4]])
        highlights = _clean_highlights(assessment.evidence_highlights)
        strongest = _skills_phrase([item.split(":", 1)[0] for item in highlights[:3]]) or skills_phrase
        answers = []
        for question in requirements.application_questions:
            if "interested" in question.lower():
                response = (
                    f"I am interested in {opportunity.role} at {opportunity.company} because the role combines {skills_phrase} "
                    "with production engineering, reliability, and cross-functional delivery."
                )
            elif "background" in question.lower() or "strongest match" in question.lower():
                response = (
                    f"My strongest match is {strongest}, supported by experience building and operating production systems, "
                    "API integrations, data workflows, and supportable automation for business users."
                )
            else:
                response = (
                    f"I am open to {opportunity.location_mode} work and can align availability during the hiring process. "
                    f"My preferred locations are {_skills_phrase(profile.preferred_locations[:3])}."
                )
            answers.append(f"## {question}\n{response}")
        return "# Application Answers\n\n" + "\n\n".join(answers)

    def _build_packet(self, opportunity: JobOpportunity, assessment: MatchAssessment) -> str:
        return (
            f"# Approval Packet\n\n"
            f"- Company: {opportunity.company}\n"
            f"- Role: {opportunity.role}\n"
            f"- Match score: {assessment.overall_score}%\n"
            f"- Decision: {assessment.decision}\n"
        )

    def _generate_cv_with_llm(
        self,
        profile: CandidateProfile,
        opportunity: JobOpportunity,
        requirements: JobRequirements,
        assessment: MatchAssessment,
        reference_texts: list[str],
    ) -> str:
        if not self.llm or not self.llm.is_configured:
            return ""
        prompt = _llm_context(profile, opportunity, requirements, assessment, reference_texts)
        return self.llm.generate_markdown(
            system_prompt=(
                "You are a senior Swiss/EU CV writer. Create a polished, truthful, ATS-readable CV in Markdown. "
                "Use only facts from the profile, job, and uploaded reference CV text. Do not write internal phrases "
                "such as 'inferred from uploaded file'. Do not invent employers, dates, credentials, or degrees."
            ),
            user_prompt=(
                f"{prompt}\n\n"
                "Return a complete tailored CV with these sections: name/contact, professional summary, target fit, "
                "technical skills grouped by category, professional experience with bullets, education, languages, and work authorization. "
                "The content must visibly change for each job ad: use the job description keywords, select the most relevant reference-CV evidence, "
                "and rewrite the summary and experience bullets around the target role without inventing missing skills."
            ),
            max_tokens=max(self.settings.llm_max_tokens, 1800),
        )

    def _generate_letter_with_llm(
        self,
        profile: CandidateProfile,
        opportunity: JobOpportunity,
        requirements: JobRequirements,
        assessment: MatchAssessment,
        reference_texts: list[str],
    ) -> str:
        if not self.llm or not self.llm.is_configured:
            return ""
        prompt = _llm_context(profile, opportunity, requirements, assessment, reference_texts)
        return self.llm.generate_markdown(
            system_prompt=(
                "You are a concise professional motivation-letter writer. Use only provided candidate facts and job facts. "
                "Do not include internal evidence labels, placeholders, or exaggerated claims."
            ),
            user_prompt=(
                f"{prompt}\n\n"
                "Return a tailored motivation letter in Markdown: greeting, 3 short paragraphs, 3 concrete fit bullets, and closing. "
                "Use the job ad's actual responsibilities and required skills; do not reuse a generic letter."
            ),
            max_tokens=max(self.settings.llm_max_tokens, 900),
        )


def _build_professional_cv(
    profile: CandidateProfile,
    opportunity: JobOpportunity,
    requirements: JobRequirements,
    assessment: MatchAssessment,
    reference_texts: list[str],
) -> str:
    name = _candidate_name(profile, reference_texts)
    contact = _contact_line(profile, reference_texts)
    summary = _summary(profile, opportunity, requirements, reference_texts)
    target_bullets = _target_fit_bullets(profile, opportunity, requirements, assessment, reference_texts)
    skill_sections = _technical_skill_sections(profile, requirements, reference_texts)
    experience = _experience_markdown(reference_texts, profile, opportunity, requirements)
    education = _education_markdown(profile, reference_texts)
    languages = _language_markdown(profile, reference_texts)
    authorization = _authorization_line(profile, reference_texts)

    sections = [
        f"# {name}",
        _role_aligned_headline(profile, opportunity, requirements, reference_texts),
        contact,
        "## Professional Summary",
        summary,
        f"## Target Fit for {opportunity.company} - {opportunity.role}",
        "\n".join(f"- {item}" for item in target_bullets),
        "## Technical Skills",
        skill_sections,
        "## Professional Experience",
        experience,
        "## Education",
        education,
        "## Languages and Work Authorization",
        "\n".join(_unique_nonempty([languages, authorization])),
    ]
    return "\n\n".join(section for section in sections if section.strip())


def _build_professional_letter(
    profile: CandidateProfile,
    opportunity: JobOpportunity,
    requirements: JobRequirements,
    assessment: MatchAssessment,
    reference_texts: list[str],
) -> str:
    name = _candidate_name(profile, reference_texts)
    highlights = _target_fit_bullets(profile, opportunity, requirements, assessment, reference_texts)[:3]
    skills = _skills_phrase(requirements.required_skills[:4] or [skill.name for skill in profile.skills[:4]])
    role = opportunity.role or "the advertised role"
    company = opportunity.company or "your team"
    focus = _role_focus_sentence(opportunity, requirements, reference_texts)

    return (
        "# Motivation Letter\n\n"
        f"Dear Hiring Team at {company},\n\n"
        f"I am applying for the {role} role because it connects closely with my experience building, operating, and improving production software and data systems in Switzerland.\n\n"
        f"For this position, I would focus on {focus}. My background gives me practical evidence across {skills}, supported by production delivery, "
        "API and data integration, monitoring, documentation, and direct collaboration with business and engineering stakeholders.\n\n"
        "The strongest fit points are:\n"
        + "\n".join(f"- {item}" for item in highlights)
        + "\n\n"
        "I would be happy to discuss how this experience can support your engineering, MLOps, and operational goals.\n\n"
        f"Sincerely,\n{name}\n"
    )


def _llm_context(
    profile: CandidateProfile,
    opportunity: JobOpportunity,
    requirements: JobRequirements,
    assessment: MatchAssessment,
    reference_texts: list[str],
) -> str:
    references = "\n\n--- Reference CV / prior application text ---\n\n".join(text[:6000] for text in reference_texts[:3])
    job_description = _limit_words(opportunity.normalized_description, 900)
    return (
        f"Candidate name: {_candidate_name(profile, reference_texts)}\n"
        f"Headline: {profile.headline}\n"
        f"Profile summary: {profile.experience_summary}\n"
        f"Languages: {_skills_phrase(profile.languages)}\n"
        f"Locations: {_skills_phrase(profile.preferred_locations)}\n"
        f"Education: {_skills_phrase(profile.education)}\n"
        f"Structured skills: {_skills_phrase([skill.name for skill in profile.skills])}\n\n"
        f"Target company: {opportunity.company}\n"
        f"Target role: {opportunity.role}\n"
        f"Full job description excerpt: {job_description}\n"
        f"Required skills: {_skills_phrase(requirements.required_skills)}\n"
        f"Preferred skills: {_skills_phrase(requirements.preferred_skills)}\n"
        f"Match score: {assessment.overall_score}\n"
        f"Evidence highlights: {_skills_phrase(_clean_highlights(assessment.evidence_highlights))}\n\n"
        f"{references}"
    )


def _candidate_name(profile: CandidateProfile, reference_texts: list[str]) -> str:
    if profile.display_name and profile.display_name != "Primary Candidate":
        return _title_name(profile.display_name)
    for line in _all_lines(reference_texts):
        if 2 <= len(line.split()) <= 4 and not _is_section_heading(line) and not re.search(r"\d|@|linkedin|engineer|developer", line, re.IGNORECASE):
            return _title_name(line)
    return _title_name(profile.display_name)


def _title_name(name: str) -> str:
    return " ".join(part.capitalize() if part.islower() else part for part in name.split())


def _contact_line(profile: CandidateProfile, reference_texts: list[str]) -> str:
    joined = "\n".join(reference_texts)
    email = _first_match(joined, r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
    phone = _first_match(joined, r"\+\d{1,3}[\d\s()/-]{6,}")
    linkedin = _first_match(joined, r"linkedin\.com/in/[A-Za-z0-9-]+")
    location = _first_location_line(reference_texts)
    pieces = _unique_nonempty([location, phone, email, linkedin])
    return " | ".join(pieces)


def _rank_reference_texts(reference_texts: list[str], opportunity: JobOpportunity, requirements: JobRequirements) -> list[str]:
    terms = _job_terms(opportunity, requirements)
    return sorted(reference_texts, key=lambda text: _score_text(text, terms), reverse=True)


def _role_aligned_headline(profile: CandidateProfile, opportunity: JobOpportunity, requirements: JobRequirements, reference_texts: list[str]) -> str:
    text = f"{opportunity.role} {opportunity.normalized_description}".lower()
    supported = _supported_skills(profile, requirements.required_skills + requirements.preferred_skills, reference_texts)
    skills = _skills_phrase([skill for skill in supported[:4] if skill.lower() not in opportunity.role.lower()])
    if "data engineer" in text or "datenpipeline" in text or "analytics" in text:
        return "Data Engineer | Data Pipelines, Analytics, Reporting"
    if "fullstack" in text or "frontend" in text or "backend" in text:
        return "Fullstack Software Engineer | .NET, APIs, AI-First Delivery"
    if "ml operations" in text or "mlops" in text or "machine learning operations" in text:
        return "ML Operations Engineer | MLOps, Python, Cloud Operations"
    return profile.headline or "Software Engineer"


def _role_focus_sentence(opportunity: JobOpportunity, requirements: JobRequirements, reference_texts: list[str]) -> str:
    areas = _job_focus_labels(opportunity)
    if areas:
        return _skills_phrase(areas[:4]).lower()
    skills = _skills_phrase(requirements.required_skills[:4])
    if skills:
        return skills.lower()
    return "production engineering, automation, and reliable delivery"


def _job_focus_labels(opportunity: JobOpportunity) -> list[str]:
    text = f"{opportunity.role} {opportunity.normalized_description}".lower()
    labels: list[str] = []
    if any(item in text for item in ("datenpipeline", "data pipeline", "data engineering", "data engineer")):
        labels.append("data pipeline development and operation")
    if any(item in text for item in ("datenmodell", "datenstrukturen", "data model")) or re.search(r"\b(crm|erp)\b", text):
        labels.append("data modeling and source harmonization")
    if any(item in text for item in ("analytics", "reporting", "reports", "dashboards", "auswertungen")):
        labels.append("analytics, dashboards, and reporting")
    if any(item in text for item in ("vue", "nuxt", "frontend", "fullstack")):
        labels.append("fullstack feature delivery")
    if any(item in text for item in ("asp.net", ".net", "backend", "graphql", "rest")):
        labels.append("backend services and API integration")
    if any(item in text for item in ("ki-agent", "ai agent", "ai-first", "ki-tools", "copilot", "cursor", "claude")):
        labels.append("AI-first engineering workflows")
    if any(item in text for item in ("ci/cd", "testing", "dokumentation", "documentation", "deployment")):
        labels.append("testing, documentation, and CI/CD delivery")
    return _unique_nonempty(labels)


def _job_focus_bullets(opportunity: JobOpportunity, reference_texts: list[str]) -> list[str]:
    labels = _job_focus_labels(opportunity)
    bullets: list[str] = []
    for label in labels:
        if label == "data pipeline development and operation":
            bullets.append("Data pipeline fit: experience with API-driven workflows, data-intensive services, validation checks, and reliable production operations.")
        elif label == "data modeling and source harmonization":
            bullets.append("Data modeling and harmonization fit: SQL/reporting background and experience integrating heterogeneous systems and structured data flows.")
        elif label == "analytics, dashboards, and reporting":
            bullets.append("Analytics and reporting fit: history of reporting workflows, operational analytics, data validation, and stakeholder-facing decision support.")
        elif label == "fullstack feature delivery":
            bullets.append("Fullstack fit: backend/API delivery plus modern frontend experience from React/Angular-style web applications and production releases.")
        elif label == "backend services and API integration":
            bullets.append("Backend/API fit: .NET, Python, REST-style services, integration testing, documentation, and supportable service operations.")
        elif label == "AI-first engineering workflows":
            bullets.append("AI-first fit: hands-on work with LLM/RAG-style assistants, prompt design, structured outputs, and AI-supported engineering workflows.")
        elif label == "testing, documentation, and CI/CD delivery":
            bullets.append("Delivery fit: practical ownership of tests, documentation, CI/CD-style releases, runbooks, debugging, and production support.")
    return bullets


def _supported_skills(profile: CandidateProfile, skills: list[str], reference_texts: list[str]) -> list[str]:
    profile_skills = {skill.name.lower(): skill.name for skill in profile.skills}
    supported: list[str] = []
    for skill in skills:
        if skill.lower() in profile_skills or _find_skill_evidence(reference_texts, skill):
            supported.append(profile_skills.get(skill.lower(), skill))
    return _unique_nonempty(supported)


def _summary(profile: CandidateProfile, opportunity: JobOpportunity, requirements: JobRequirements, reference_texts: list[str]) -> str:
    extracted = _section_paragraph(reference_texts, ("PROFESSIONAL SUMMARY", "PROFILE"), ("CORE FIT", "RELEVANT FIT", "TECHNICAL SKILLS", "PROFESSIONAL EXPERIENCE"))
    skills = _skills_phrase(_supported_skills(profile, requirements.required_skills[:6], reference_texts))
    if not skills:
        skills = _skills_phrase([skill.name for skill in profile.skills[:4]])
    role_focus = _role_focus_sentence(opportunity, requirements, reference_texts)
    base = _limit_words(extracted or profile.experience_summary, 60)
    return (
        f"{base} For {opportunity.role} at {opportunity.company}, the CV is tailored around {role_focus}. "
        f"Most relevant strengths: {skills or 'production software delivery, data integration, and stakeholder-facing engineering'}."
    )


def _target_fit_bullets(
    profile: CandidateProfile,
    opportunity: JobOpportunity,
    requirements: JobRequirements,
    assessment: MatchAssessment,
    reference_texts: list[str],
) -> list[str]:
    bullets = _clean_highlights(assessment.evidence_highlights)
    supported = _supported_skills(profile, requirements.required_skills, reference_texts)
    if supported:
        bullets.insert(0, f"Direct evidence for role requirements: {_skills_phrase(supported[:6])}.")

    for item in _job_focus_bullets(opportunity, reference_texts):
        bullets.append(item)

    if _contains_any(reference_texts, ("production", "monitoring", "root-cause", "incident", "reliability")) and _job_mentions(opportunity, ("production", "betreibst", "deployment", "operating", "betrieb")):
        bullets.append("Production engineering mindset with monitoring, troubleshooting, root-cause analysis, release readiness, and supportable operations.")
    if _contains_any(reference_texts, ("LLM", "RAG", "MLflow", "MLOps", "AI", "machine-learning")) and _job_mentions(opportunity, ("ai", "ki", "ml", "agent", "llm", "mlops")):
        bullets.append("Applied AI and MLOps exposure across LLM/RAG concepts, evaluation thinking, data workflows, and prototype-to-production delivery.")
    if _contains_any(reference_texts, ("stakeholder", "business", "operations", "external partners")):
        bullets.append("Comfortable working across engineering, business, operations, and external partners to move ideas into reliable production use.")
    return _unique_nonempty([_ensure_sentence(item) for item in bullets])[:6] or ["Strong fit with the role based on structured profile evidence and uploaded CV history."]


def _technical_skill_sections(profile: CandidateProfile, requirements: JobRequirements, reference_texts: list[str]) -> str:
    text = "\n".join(reference_texts)
    supported_requirements = _supported_skills(profile, requirements.required_skills + requirements.preferred_skills, reference_texts)
    known = _unique_nonempty(supported_requirements + [skill.name for skill in profile.skills] + _skills_from_reference(text))
    categories = {
        "AI / MLOps": ("AI", "ML", "LLM", "RAG", "LangGraph", "MLflow", "Prometheus", "Grafana", "TensorFlow", "scikit-learn", "OpenAI", "evaluation", "agents", "Copilot", "Cursor"),
        "Backend / APIs": ("Python", "FastAPI", "Flask", "Django", "Java", "C#", ".NET", "ASP.NET", "REST", "GraphQL", "microservices", "React", "Angular", "Vue", "Nuxt"),
        "Cloud / DevOps": ("Azure", "Azure DevOps", "Docker", "Kubernetes", "Linux", "CI/CD", "Git", "monitoring", "logging", "deployment"),
        "Data": ("SQL", "PostgreSQL", "SQL Server", "MySQL", "ETL", "ELT", "Elasticsearch", "data", "reporting", "analytics", "pipeline", "dashboard", "CRM", "ERP"),
    }
    lines: list[str] = []
    if supported_requirements:
        lines.append(f"- Role-matched evidence: {_skills_phrase(supported_requirements[:10])}")
    for label, terms in categories.items():
        matched = [skill for skill in known if any(term.lower() in skill.lower() for term in terms)]
        if matched:
            lines.append(f"- {label}: {_skills_phrase(matched[:12])}")
    if not lines and known:
        lines.append(f"- Core skills: {_skills_phrase(known[:16])}")
    return "\n".join(lines)


def _experience_markdown(reference_texts: list[str], profile: CandidateProfile, opportunity: JobOpportunity, requirements: JobRequirements) -> str:
    lines = _section_lines(
        reference_texts,
        ("PROFESSIONAL EXPERIENCE", "EXPERIENCE"),
        ("TECHNICAL SKILLS", "EDUCATION", "EDUCATION & LANGUAGES", "LANGUAGES"),
    )
    roles: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        cleaned = _clean_line(line)
        if not cleaned:
            continue
        if _looks_like_role_line(cleaned):
            if current:
                roles.append(current)
            current = [cleaned]
            continue
        if current and _looks_like_date_line(cleaned):
            current[0] = f"{current[0]} | {cleaned}"
            continue
        if current and len(cleaned) > 12:
            current.append(cleaned)
    if current:
        roles.append(current)

    if roles:
        parts: list[str] = []
        terms = _job_terms(opportunity, requirements)
        for role in roles[:5]:
            parts.append(f"### {role[0]}")
            for bullet in _select_relevant_bullets(role[1:], terms, limit=4):
                parts.append(f"- {bullet}")
        return "\n".join(parts)

    achievements = _clean_highlights(profile.achievements)
    if achievements:
        return "\n".join(f"- {item}" for item in achievements[:8])
    return "- Professional experience details are available in the uploaded CV and should be reviewed before submission."


def _select_relevant_bullets(bullets: list[str], terms: list[str], limit: int) -> list[str]:
    cleaned = _unique_nonempty([_clean_line(bullet) for bullet in bullets if len(_clean_line(bullet)) > 12])
    if not cleaned:
        return []
    scored = [(index, _score_text(bullet, terms), bullet) for index, bullet in enumerate(cleaned)]
    relevant = [item for item in sorted(scored, key=lambda item: (-item[1], item[0])) if item[1] > 0]
    selected = relevant[:limit]
    if len(selected) < min(limit, len(cleaned)):
        selected_indexes = {index for index, _, _ in selected}
        selected.extend(item for item in scored if item[0] not in selected_indexes)  # preserve enough context when job terms are sparse
    return [bullet for _, _, bullet in sorted(selected[:limit], key=lambda item: item[0])]


def _job_terms(opportunity: JobOpportunity, requirements: JobRequirements) -> list[str]:
    raw_terms = requirements.required_skills + requirements.preferred_skills
    raw_terms += _job_focus_labels(opportunity)
    raw_terms += re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{2,}", opportunity.role)

    description = opportunity.normalized_description.lower()
    keyword_map = {
        "data pipelines": ("datenpipelines", "data pipelines", "pipeline"),
        "data modeling": ("datenstrukturen", "datenmodelle", "data model", "modeling"),
        "analytics": ("analytics", "analysen", "insights", "erkenntnisse"),
        "reporting": ("reporting", "reports", "dashboards", "auswertungen"),
        "crm": ("crm",),
        "erp": ("erp",),
        "api": ("api", "apis", "rest", "graphql"),
        "vue": ("vue", "nuxt"),
        ".net": (".net", "asp.net"),
        "ai agents": ("ki-agent", "ai agent", "ai-first", "copilot", "cursor", "claude"),
        "ci/cd": ("ci/cd", "deployment", "testing", "dokumentation"),
        "german": ("deutsch", "german"),
        "security": ("informationssicherheit", "security"),
    }
    for label, aliases in keyword_map.items():
        if any(alias in description for alias in aliases):
            raw_terms.append(label)
            raw_terms.extend(aliases)
    return _unique_nonempty([term.lower() for term in raw_terms if len(term.strip()) > 1])


def _score_text(text: str, terms: list[str]) -> int:
    lowered = text.lower()
    score = 0
    for term in terms:
        term = term.lower().strip()
        if not term:
            continue
        if term in lowered:
            score += 3 if " " in term or "/" in term else 2
        elif term.replace("-", " ") in lowered:
            score += 1
    return score


def _education_markdown(profile: CandidateProfile, reference_texts: list[str]) -> str:
    lines = _section_lines(reference_texts, ("EDUCATION", "EDUCATION & LANGUAGES"), ("LANGUAGES", "ADDITIONAL", "TECHNICAL SKILLS"))
    cleaned = _unique_nonempty([_clean_line(line) for line in lines if len(_clean_line(line)) > 8])
    if cleaned:
        return "\n".join(f"- {line}" for line in cleaned[:4])
    return "\n".join(f"- {item}" for item in profile.education)


def _language_markdown(profile: CandidateProfile, reference_texts: list[str]) -> str:
    for line in _all_lines(reference_texts):
        if line.lower().startswith("languages:"):
            return _clean_line(line)
        if "english:" in line.lower() and "german:" in line.lower():
            return f"Languages: {_clean_line(line)}"
    return f"Languages: {_skills_phrase(profile.languages)}"


def _authorization_line(profile: CandidateProfile, reference_texts: list[str]) -> str:
    for line in _all_lines(reference_texts):
        if "permit" in line.lower() or "authorization" in line.lower() or "work authorisation" in line.lower():
            return _clean_line(line)
    return f"Work authorization: {profile.work_authorization}"


def _section_paragraph(reference_texts: list[str], starts: tuple[str, ...], stops: tuple[str, ...]) -> str:
    return _limit_words(" ".join(_section_lines(reference_texts, starts, stops)), 85)


def _section_lines(reference_texts: list[str], starts: tuple[str, ...], stops: tuple[str, ...]) -> list[str]:
    for text in reference_texts:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        capture = False
        captured: list[str] = []
        for line in lines:
            upper = line.upper().strip()
            if not capture and any(upper.startswith(start) for start in starts):
                capture = True
                continue
            if capture and any(upper.startswith(stop) for stop in stops):
                break
            if capture:
                captured.append(line)
        if captured:
            return captured
    return []


def _all_lines(reference_texts: list[str]) -> list[str]:
    return [_clean_line(line) for text in reference_texts for line in text.splitlines() if _clean_line(line)]


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip(" -\u2022\t")


def _clean_evidence(value: str) -> str:
    cleaned = _clean_line(value)
    if not cleaned or "inferred from uploaded file" in cleaned.lower():
        return ""
    if "mentioned in uploaded profile asset" in cleaned.lower():
        return ""
    return _limit_words(cleaned, 36)


def _clean_highlights(items: list[str]) -> list[str]:
    return _unique_nonempty([_clean_evidence(item) for item in items])


def _find_skill_evidence(reference_texts: list[str], skill_name: str) -> str:
    patterns = [skill_name] + _evidence_aliases(skill_name)
    for line in _all_lines(reference_texts):
        if len(line) <= 25:
            continue
        if any(re.search(re.escape(pattern), line, flags=re.IGNORECASE) for pattern in patterns):
            return _limit_words(line, 34)
    return ""


def _evidence_aliases(skill_name: str) -> list[str]:
    aliases = {
        "data engineering": ["data-intensive", "data workflows", "data-driven", "data pipelines"],
        "data pipelines": ["data-intensive pipelines", "data flows", "data workflows", "pipelines"],
        "data modeling": ["data validation", "structured data", "sql-based reporting", "reporting workflows"],
        "data analysis": ["analytics", "reporting", "analyses", "insights"],
        "analytics": ["analytics", "reporting", "decision support"],
        "reporting": ["reporting", "reports", "dashboards"],
        "requirements engineering": ["requirements", "backlog", "stakeholder"],
        "business analysis": ["business stakeholders", "decision support", "product owner"],
        "asp.net core": [".net", "c#/.net"],
        "ai agents": ["agentic ai", "llm/rag", "assistant features", "assistant-style"],
        "ai tools": ["ai-enabled", "ai-supported", "llm/rag", "prompt design"],
        "testing": ["testing", "tests", "validation checks"],
        "documentation": ["documentation", "runbooks", "documented"],
        "ci/cd": ["ci/cd", "release", "deployment"],
    }
    return aliases.get(skill_name.lower(), [])


def _skills_from_reference(text: str) -> list[str]:
    candidates = [
        "LLM",
        "RAG",
        "LangChain",
        "OpenAI API",
        "Python",
        "FastAPI",
        "Flask",
        "Django",
        "Java",
        "C#/.NET",
        "REST APIs",
        "GraphQL",
        "microservices",
        "React.js",
        "AngularJS",
        "Vue.js",
        "Nuxt",
        "Azure",
        "Azure DevOps",
        "Docker",
        "Kubernetes",
        "Linux",
        "CI/CD",
        "Git",
        "MLflow",
        "Prometheus",
        "Grafana",
        "PostgreSQL",
        "SQL Server",
        "MySQL",
        "ETL/ELT",
        "data pipelines",
        "data modeling",
        "data validation",
        "analytics",
        "reporting",
        "dashboards",
        "Elasticsearch",
        "TensorFlow",
        "scikit-learn",
        "AI agents",
        "GitHub Copilot",
        "Cursor",
        "Claude Code",
    ]
    lowered = text.lower()
    return [item for item in candidates if item.lower() in lowered]


def _looks_like_role_line(line: str) -> bool:
    lowered = line.lower()
    has_role_word = any(word in lowered for word in ("engineer", "developer", "owner", "roles", "consultant"))
    has_separator = "|" in line or " - " in line or " -- " in line or f" {chr(8212)} " in line
    has_date = bool(re.search(r"\b(20\d{2}|19\d{2}|present|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", lowered))
    return has_role_word and (has_separator or has_date)


def _looks_like_date_line(line: str) -> bool:
    lowered = line.lower()
    return bool(re.fullmatch(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\.?\s*\d{4}\s*(-|to)\s*((jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\.?\s*)?(present|\d{4})", lowered))


def _is_section_heading(line: str) -> bool:
    return line.isupper() and len(line.split()) <= 6


def _contains_any(reference_texts: list[str], needles: tuple[str, ...]) -> bool:
    text = "\n".join(reference_texts).lower()
    return any(needle.lower() in text for needle in needles)


def _job_mentions(opportunity: JobOpportunity, needles: tuple[str, ...]) -> bool:
    text = f"{opportunity.role} {opportunity.normalized_description}".lower()
    return any(needle.lower() in text for needle in needles)


def _first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(0).strip() if match else ""


def _first_line_containing(reference_texts: list[str], needles: tuple[str, ...]) -> str:
    for line in _all_lines(reference_texts):
        if any(needle.lower() in line.lower() for needle in needles) and "available" not in line.lower():
            return line
    return ""


def _first_location_line(reference_texts: list[str]) -> str:
    for line in _all_lines(reference_texts):
        lowered = line.lower()
        if not any(needle in line for needle in ("Switzerland", "Zurich", "Allschwil", "Basel")):
            continue
        if any(marker in lowered for marker in ("@", "+41", "linkedin", "permit", "available")):
            continue
        return line
    return _first_line_containing(reference_texts, ("Switzerland", "Zurich", "Allschwil", "Basel"))


def _limit_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text.strip()
    return " ".join(words[:limit]).rstrip(" ,;:") + "."


def _skills_phrase(items: list[str]) -> str:
    cleaned = _unique_nonempty([str(item).strip() for item in items if str(item).strip()])
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _ensure_sentence(text: str) -> str:
    cleaned = text.strip()
    if cleaned and cleaned[-1] not in ".!?":
        return cleaned + "."
    return cleaned


def _unique_nonempty(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = re.sub(r"\s+", " ", item).strip()
        key = normalized.lower()
        if normalized and key not in seen:
            result.append(normalized)
            seen.add(key)
    return result


def _looks_like_complete_document(content: str, min_length: int) -> bool:
    if not content or len(content) < min_length:
        return False
    lowered = content.lower()
    if "inferred from uploaded file" in lowered or "mentioned in uploaded profile asset" in lowered:
        return False
    return "# " in content and "## " in content


def _looks_role_tailored(content: str, opportunity: JobOpportunity, requirements: JobRequirements) -> bool:
    lowered = content.lower()
    anchors = [opportunity.company, opportunity.role] + requirements.required_skills[:6]
    anchors = [anchor.lower() for anchor in anchors if anchor]
    hits = sum(1 for anchor in anchors if anchor in lowered)
    return hits >= min(3, max(1, len(anchors)))


def _extract_comp_k(text: str) -> int:
    match = re.search(r"(\d{2,3})\s?[kK]", text)
    return int(match.group(1)) if match else 0


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
