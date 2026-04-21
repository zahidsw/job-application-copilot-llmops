from __future__ import annotations

import re

from job_app_ops.config import Settings
from job_app_ops.schemas import (
    ApprovalPacket,
    CandidateProfile,
    GeneratedArtifact,
    JobOpportunity,
    JobRequirements,
    MatchAssessment,
)
from job_app_ops.services.profile_vault import ProfileVaultService


class JobApplicationAgents:
    def __init__(self, settings: Settings, profile_vault: ProfileVaultService) -> None:
        self.settings = settings
        self.profile_vault = profile_vault

    def match(self, profile: CandidateProfile, opportunity: JobOpportunity, requirements: JobRequirements) -> MatchAssessment:
        vault = self.profile_vault.get_vault(profile.profile_id)
        profile_skills = {skill.name.lower(): skill for skill in profile.skills}
        matched = [skill for skill in requirements.required_skills if skill.lower() in profile_skills]
        missing = [skill for skill in requirements.required_skills if skill.lower() not in profile_skills]

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

        evidence_highlights = [f"{skill.name}: {skill.evidence}" for skill in profile.skills if skill.name.lower() in {item.lower() for item in matched}][:4]
        evidence_highlights += vault.reference_highlights[: max(0, 4 - len(evidence_highlights))]
        evidence_highlights += profile.achievements[: max(0, 4 - len(evidence_highlights))]

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
            content=self._build_letter(profile, opportunity, assessment),
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
        vault = self.profile_vault.get_vault(profile.profile_id)
        relevant_skills = [skill for skill in profile.skills if skill.name in requirements.required_skills or skill.name in requirements.preferred_skills][:8]
        prior_context = ""
        if vault.cv_style_samples:
            prior_context = f"\n\n## Prior Experience Context\n- {vault.cv_style_samples[0][:220]}..."
        return (
            f"# {profile.display_name}\n\n"
            f"{profile.headline}\n\n"
            f"## Target Role\n{opportunity.role} at {opportunity.company}\n\n"
            f"## Tailored Summary\n{profile.experience_summary}\n\n"
            f"## Match Highlights\n" +
            "\n".join(f"- {item}" for item in assessment.evidence_highlights) +
            "\n\n## Relevant Skills\n" +
            "\n".join(f"- {skill.name} ({skill.years} years): {skill.evidence}" for skill in relevant_skills) +
            prior_context
        )

    def _build_letter(self, profile: CandidateProfile, opportunity: JobOpportunity, assessment: MatchAssessment) -> str:
        vault = self.profile_vault.get_vault(profile.profile_id)
        highlights = assessment.evidence_highlights or ["Strong overlap with the role requirements."]
        sample_line = ""
        if vault.motivation_letter_samples:
            sample_line = vault.motivation_letter_samples[0][:180]
        return (
            f"# Motivation Letter\n\n"
            f"Dear Hiring Team at {opportunity.company},\n\n"
            f"I am applying for the {opportunity.role} role because it strongly aligns with my experience in workflow automation, engineering delivery, and AI-enabled systems.\n\n"
            + (f"My previous letter style emphasizes this angle: {sample_line}\n\n" if sample_line else "")
            + "Relevant highlights:\n"
            +
            "\n".join(f"- {item}" for item in highlights[:3]) +
            f"\n\nSincerely,\n{profile.display_name}\n"
        )

    def _build_answers(self, profile: CandidateProfile, opportunity: JobOpportunity, requirements: JobRequirements, assessment: MatchAssessment) -> str:
        answers = []
        for question in requirements.application_questions:
            if "interested" in question.lower():
                response = f"I am interested in {opportunity.role} at {opportunity.company} because it combines {', '.join(requirements.required_skills[:3])} with the type of workflow and systems delivery I already do well."
            elif "background" in question.lower() or "strongest match" in question.lower():
                response = f"My strongest matches are {', '.join(requirements.required_skills[:4])} together with evidence-backed work in automation and operator tooling."
            else:
                response = f"I am open to {opportunity.location_mode} work and can align availability during the hiring process."
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


def _extract_comp_k(text: str) -> int:
    match = re.search(r"(\d{2,3})\s?[kK]", text)
    return int(match.group(1)) if match else 0


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
