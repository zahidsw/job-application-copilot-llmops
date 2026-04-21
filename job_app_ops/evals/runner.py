from __future__ import annotations

import json
from pathlib import Path

from job_app_ops.config import get_settings
from job_app_ops.runtime import get_runtime
from job_app_ops.schemas import CandidateProfile, CandidateSkill, JobApplicationRequest, JobSourceType, SubmissionChannel


def main() -> None:
    settings = get_settings()
    runtime = get_runtime()
    dataset_path = Path(settings.eval_dataset_path)
    if not dataset_path.exists():
        print("No eval dataset configured.")
        return

    cases = json.loads(dataset_path.read_text(encoding="utf-8"))
    print(f"Loaded {len(cases)} evaluation cases for {settings.app_name}.")
    print("This runner is the scheduled evaluation placeholder for MLflow-linked quality tracking.")


def sample_profile() -> CandidateProfile:
    return CandidateProfile(
        skills=[
            CandidateSkill(name="C#", years=10, evidence="Production .NET delivery"),
            CandidateSkill(name=".NET", years=10, evidence="Desktop and backend systems"),
            CandidateSkill(name="ASP.NET Core", years=7, evidence="API and service delivery"),
            CandidateSkill(name="Azure", years=6, evidence="Cloud-hosted workloads"),
            CandidateSkill(name="SQL", years=8, evidence="Relational persistence"),
            CandidateSkill(name="Python", years=5, evidence="Automation and AI integrations"),
            CandidateSkill(name="WPF", years=6, evidence="Operator-facing desktop tools"),
            CandidateSkill(name="DevExpress", years=4, evidence="Enterprise desktop UI"),
        ],
        achievements=["Reduced operator handoff time by 40%", "Built AI-enabled workflow tooling with review gates"],
    )


def sample_request() -> JobApplicationRequest:
    return JobApplicationRequest(
        profile=sample_profile(),
        company="Contoso Labs",
        role="Senior .NET Platform Engineer",
        source_name="Manual intake",
        source_type=JobSourceType.manual_entry,
        destination="https://careers.contoso.example/platform-engineer",
        submission_channel=SubmissionChannel.company_site,
        job_text="Required: C#, .NET, ASP.NET Core, Azure, SQL, Docker, English, authorization to work in Switzerland.",
    )
