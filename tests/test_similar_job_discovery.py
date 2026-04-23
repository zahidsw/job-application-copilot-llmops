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

    monkeypatch.setattr(tool_gateway, "_search_public_job_results", lambda query, runtime_settings=None, opportunity=None: search_results)
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


def test_search_public_job_results_prefers_serpapi(monkeypatch):
    settings = Settings(
        similar_job_search_provider="serpapi",
        serpapi_api_key="test-key",
    )
    expected = [
        {
            "role": "Platform Engineer",
            "company": "Example Corp",
            "source_name": "example.com",
            "source_url": "https://example.com/jobs/platform",
            "snippet": "Python platform engineering role",
        }
    ]

    monkeypatch.setattr(tool_gateway, "_search_serpapi_results", lambda query, runtime_settings, opportunity=None: expected)
    monkeypatch.setattr(tool_gateway, "_search_duckduckgo_results", lambda query: [])

    results = tool_gateway._search_public_job_results("platform engineer python", settings)

    assert results == expected


def test_evaluate_source_policy_allows_company_sites():
    settings = Settings(
        allowed_source_domains="greenhouse.io,lever.co,workday.com",
        manual_only_domains="linkedin.com,indeed.com",
    )

    result = tool_gateway.evaluate_source_policy(
        settings=settings,
        source_url="https://careers.contoso.com/jobs/platform-engineer",
        source_name="careers.contoso.com",
        source_type=JobSourceType.company_site,
        submission_channel=SubmissionChannel.company_site,
    )

    assert result["source_approved"] is True
    assert result["source_policy_note"] == "Source approved."


def test_similar_job_query_uses_source_job_location():
    opportunity = JobOpportunity(
        company="Swiss Example AG",
        role=".NET Software Engineer",
        source_name="careers.example.ch",
        source_url="https://careers.example.ch/jobs/dotnet",
        source_type=JobSourceType.company_site,
        destination="https://careers.example.ch/jobs/dotnet",
        submission_channel=SubmissionChannel.company_site,
        normalized_description=".NET Software Engineer role in Zurich, Switzerland with Azure and SQL.",
        location_mode="hybrid",
        source_identifier="careers.example.ch",
        source_approved=True,
        source_policy_note="Source approved.",
    )
    requirements = JobRequirements(required_skills=[".NET", "Azure", "SQL"])

    query = tool_gateway._build_similar_job_query(opportunity, requirements)

    assert "Zurich, Switzerland" in query
    assert "hybrid" in query


def test_find_similar_jobs_filters_wrong_country(monkeypatch):
    settings = Settings(
        allowed_source_domains="example.ch,builtin.com,swiss.example",
        manual_only_domains="linkedin.com,indeed.com",
        similar_job_min_score=70,
    )
    opportunity = JobOpportunity(
        company="Swiss Example AG",
        role=".NET Software Engineer",
        source_name="example.ch",
        source_url="https://example.ch/jobs/dotnet",
        source_type=JobSourceType.company_site,
        destination="https://example.ch/jobs/dotnet",
        submission_channel=SubmissionChannel.company_site,
        normalized_description=".NET Software Engineer Zurich Switzerland Azure C# SQL CI/CD",
        location_mode="hybrid",
        source_identifier="example.ch",
        source_approved=True,
        source_policy_note="Source approved.",
    )
    requirements = JobRequirements(
        required_skills=[".NET", "Azure", "C#", "SQL"],
        language_requirements=["English"],
    )
    search_results = [
        {
            "role": "Top Remote .NET Developer Jobs in Los Angeles, CA",
            "company": "BuiltIn",
            "source_name": "builtin.com",
            "source_url": "https://builtin.com/jobs/los-angeles/dotnet",
            "location_hint": "Los Angeles, CA",
            "snippet": ".NET Azure C# SQL jobs in Los Angeles, CA",
        },
        {
            "role": ".NET Software Engineer",
            "company": "Swiss Example",
            "source_name": "swiss.example",
            "source_url": "https://swiss.example/jobs/dotnet",
            "location_hint": "Zurich, Switzerland",
            "snippet": ".NET Azure C# SQL hybrid role in Zurich Switzerland",
        },
    ]
    fetched_payloads = {
        "https://builtin.com/jobs/los-angeles/dotnet": JobFetchResult(
            source_url="https://builtin.com/jobs/los-angeles/dotnet",
            final_url="https://builtin.com/jobs/los-angeles/dotnet",
            source_name="builtin.com",
            company="BuiltIn",
            role="Top Remote .NET Developer Jobs in Los Angeles, CA",
            job_text=".NET Azure C# SQL role in Los Angeles, CA",
            raw_html="",
            fetch_note="ok",
            requires_auth=False,
        ),
        "https://swiss.example/jobs/dotnet": JobFetchResult(
            source_url="https://swiss.example/jobs/dotnet",
            final_url="https://swiss.example/jobs/dotnet",
            source_name="swiss.example",
            company="Swiss Example",
            role=".NET Software Engineer",
            job_text=".NET Azure C# SQL hybrid English role in Zurich Switzerland",
            raw_html="",
            fetch_note="ok",
            requires_auth=False,
        ),
    }

    monkeypatch.setattr(tool_gateway, "_search_public_job_results", lambda query, runtime_settings=None, opportunity=None: search_results)
    monkeypatch.setattr(tool_gateway, "fetch_job_from_url", lambda source_url: fetched_payloads[source_url])

    matches = tool_gateway.find_similar_jobs(
        settings=settings,
        opportunity=opportunity,
        requirements=requirements,
        limit=5,
    )

    assert [match.company for match in matches] == ["Swiss Example"]
    assert matches[0].location_hint == "Zurich, Switzerland"


def test_find_similar_jobs_uses_structured_search_text_without_refetch(monkeypatch):
    settings = Settings(
        allowed_source_domains="swiss.example",
        manual_only_domains="linkedin.com,indeed.com",
        similar_job_min_score=70,
    )
    opportunity = JobOpportunity(
        company="Swiss Example AG",
        role=".NET Software Engineer",
        source_name="example.ch",
        source_url="https://example.ch/jobs/dotnet",
        source_type=JobSourceType.company_site,
        destination="https://example.ch/jobs/dotnet",
        submission_channel=SubmissionChannel.company_site,
        normalized_description=".NET Software Engineer Zurich Switzerland Azure C# SQL CI/CD",
        location_mode="hybrid",
        source_identifier="example.ch",
        source_approved=True,
        source_policy_note="Source approved.",
    )
    requirements = JobRequirements(required_skills=[".NET", "Azure", "C#", "SQL"])
    search_results = [
        {
            "role": ".NET Software Engineer",
            "company": "Swiss Example",
            "source_name": "swiss.example",
            "source_url": "https://swiss.example/jobs/dotnet",
            "location_hint": "Zurich, Switzerland",
            "skip_fetch": "true",
            "snippet": ".NET Software Engineer Azure C# SQL CI/CD hybrid role in Zurich Switzerland "
            "building cloud services, APIs, and production engineering workflows.",
        },
    ]

    monkeypatch.setattr(tool_gateway, "_search_public_job_results", lambda query, runtime_settings=None, opportunity=None: search_results)
    monkeypatch.setattr(
        tool_gateway,
        "fetch_job_from_url",
        lambda source_url: (_ for _ in ()).throw(AssertionError("search metadata should avoid page refetch")),
    )

    matches = tool_gateway.find_similar_jobs(
        settings=settings,
        opportunity=opportunity,
        requirements=requirements,
        limit=5,
    )

    assert len(matches) == 1
    assert matches[0].company == "Swiss Example"
    assert matches[0].location_hint == "Zurich, Switzerland"
