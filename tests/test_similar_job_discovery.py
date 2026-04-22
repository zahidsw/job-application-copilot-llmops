from __future__ import annotations

from job_app_ops.config import Settings
from job_app_ops.schemas import JobFetchResult, JobOpportunity, JobRequirements, JobSourceType, SubmissionChannel
from job_app_ops.services import tool_gateway


def test_find_similar_jobs_returns_high_similarity_matches(monkeypatch):
    settings = Settings(
        allowed_source_domains="example.com,contoso.example,fabrikam.example",
        manual_only_domains="linkedin.com,indeed.com",
    )
    opportunity = JobOpportunity(
        company="Example AG",
        role="Senior Backend Engineer",
        source_name="example.com",
        source_url="https://example.com/jobs/backend-engineer",
        source_type=JobSourceType.company_site,
        destination="https://example.com/jobs/backend-engineer",
        submission_channel=SubmissionChannel.company_site,
        normalized_description="Python FastAPI SQL Docker CI/CD remote engineering platform services",
        location_mode="remote",
        source_identifier="example.com",
        source_approved=True,
        source_policy_note="Source approved.",
    )
    requirements = JobRequirements(
        required_skills=["Python", "FastAPI", "SQL", "Docker", "CI/CD"],
        preferred_skills=["Grafana"],
        language_requirements=["English"],
    )

    search_results = [
        {
            "role": "Senior Backend Engineer",
            "company": "Contoso",
            "source_name": "contoso.example",
            "source_url": "https://contoso.example/jobs/backend-platform",
            "snippet": "Python FastAPI SQL Docker CI/CD remote backend role",
        },
        {
            "role": "Marketing Manager",
            "company": "Fabrikam",
            "source_name": "fabrikam.example",
            "source_url": "https://fabrikam.example/jobs/marketing-manager",
            "snippet": "Brand campaigns and communications",
        },
    ]

    fetched_payloads = {
        "https://contoso.example/jobs/backend-platform": JobFetchResult(
            source_url="https://contoso.example/jobs/backend-platform",
            final_url="https://contoso.example/jobs/backend-platform",
            source_name="contoso.example",
            company="Contoso",
            role="Senior Backend Engineer",
            job_text="Senior Backend Engineer Python FastAPI SQL Docker CI/CD remote English observability",
            raw_html="",
            fetch_note="ok",
            requires_auth=False,
        ),
        "https://fabrikam.example/jobs/marketing-manager": JobFetchResult(
            source_url="https://fabrikam.example/jobs/marketing-manager",
            final_url="https://fabrikam.example/jobs/marketing-manager",
            source_name="fabrikam.example",
            company="Fabrikam",
            role="Marketing Manager",
            job_text="Marketing campaigns content communications onsite German",
            raw_html="",
            fetch_note="ok",
            requires_auth=False,
        ),
    }

    monkeypatch.setattr(tool_gateway, "_search_public_job_results", lambda query: search_results)
    monkeypatch.setattr(tool_gateway, "fetch_job_from_url", lambda source_url: fetched_payloads[source_url])

    matches = tool_gateway.find_similar_jobs(
        settings=settings,
        opportunity=opportunity,
        requirements=requirements,
        limit=5,
    )

    assert len(matches) == 1
    assert matches[0].company == "Contoso"
    assert matches[0].role == "Senior Backend Engineer"
    assert matches[0].similarity_score >= 80
    assert "Python" in matches[0].matched_skills
    assert "SQL" in matches[0].matched_skills
