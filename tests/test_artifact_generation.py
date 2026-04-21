from __future__ import annotations

from types import SimpleNamespace

from job_app_ops.agents.job_application_agents import JobApplicationAgents
from job_app_ops.config import Settings
from job_app_ops.schemas import (
    CandidateProfile,
    CandidateSkill,
    JobOpportunity,
    JobRequirements,
    JobSourceType,
    MatchAssessment,
    ProfileAssetKind,
    SubmissionChannel,
)


REFERENCE_CV = """
Zahid Muhammad
AI Software Engineer | LLM, RAG, Python, Production Systems
Allschwil (BL), Switzerland
+41 76 612 28 07
zahidkhan27@gmail.com
linkedin.com/in/zahid-muhammad-8641a626
PROFESSIONAL SUMMARY
AI and software engineer with 8+ years of experience building and operating production systems in Switzerland across trading, data, and digital platforms.
TECHNICAL SKILLS
AI / ML
LLM integration, prompt engineering, RAG architectures, TensorFlow, scikit-learn
Cloud / MLOps / Ops
Docker, Kubernetes, Git, CI/CD, Azure, Azure DevOps, Linux, monitoring/logging
Data
PostgreSQL, SQL Server, MySQL, data validation, reporting/analytics
PROFESSIONAL EXPERIENCE
Trading Desk Engineer (Data & AI) | Alpiq, Switzerland
Jun 2023 - Present
Develop and operate production services, automations, and integrations in Python, Java, and .NET for trading and operational workflows.
Design data-intensive pipelines and API-driven services with validation checks, audit-friendly logging, and monitoring for high reliability.
EDUCATION
M.Sc. Computer Science - Applied Artificial Intelligence | Dalarna University, Sweden
LANGUAGES
English: Fluent | German: Professional working proficiency | Urdu/Hindi: Fluent
Swiss residence permit: C | Available for hybrid work in Zurich
"""


class FakeProfileVault:
    def get_vault(self, profile_id: str):
        return SimpleNamespace(reference_highlights=[])

    def get_reference_texts(self, profile_id: str, kinds: tuple[ProfileAssetKind, ...] | None = None, limit: int = 5):
        return [REFERENCE_CV]


def test_generated_cv_and_letter_use_reference_cv_without_internal_evidence_labels(tmp_path):
    settings = Settings(artifacts_dir=tmp_path / "artifacts", profiles_dir=tmp_path / "profiles", reports_dir=tmp_path / "reports")
    agents = JobApplicationAgents(settings, FakeProfileVault())
    profile = CandidateProfile(
        display_name="Zahid muhammad",
        headline="AI Software Engineer | LLM, RAG, Python, Production Systems",
        skills=[
            CandidateSkill(name="Azure", evidence="Inferred from uploaded file old.pdf"),
            CandidateSkill(name="Python", evidence="Strong Python API delivery with FastAPI and data workflows."),
            CandidateSkill(name="SQL", evidence="Data validation and SQL reporting workflows."),
        ],
    )
    opportunity = JobOpportunity(
        company="Galenica",
        role="ML Operations Engineer (w/m/d)",
        source_name="LinkedIn",
        source_type=JobSourceType.saved_search,
        submission_channel=SubmissionChannel.manual_handoff,
        normalized_description="Azure SQL Python MLflow Prometheus Grafana Docker CI/CD",
    )
    requirements = JobRequirements(required_skills=["Azure", "SQL", "Python", "MLflow"], preferred_skills=["Docker", "CI/CD"])
    assessment = MatchAssessment(
        overall_score=88,
        decision="ready_to_tailor",
        ready_for_tailoring=True,
        evidence_highlights=[
            "Azure: Inferred from uploaded file old.pdf",
            "Python: Strong Python API delivery with FastAPI and data workflows.",
            "SQL: Data validation and SQL reporting workflows.",
        ],
    )

    artifacts = agents.generate_artifacts(profile, opportunity, requirements, assessment)
    cv = next(artifact.content for artifact in artifacts if artifact.artifact_type == "cv")
    letter = next(artifact.content for artifact in artifacts if artifact.artifact_type == "motivation_letter")

    assert "Inferred from uploaded file" not in cv
    assert "Inferred from uploaded file" not in letter
    assert "## Professional Experience" in cv
    assert "Trading Desk Engineer" in cv
    assert "## Technical Skills" in cv
    assert "Dear Hiring Team at Galenica" in letter
