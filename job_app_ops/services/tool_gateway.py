from __future__ import annotations

import re
from html import unescape
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import httpx

from job_app_ops.config import Settings
from job_app_ops.schemas import JobFetchResult, JobOpportunity, JobRequirements, JobSourceType, SubmissionChannel


KNOWN_SKILLS = [
    "c#",
    ".net",
    "asp.net core",
    "azure",
    "sql",
    "docker",
    "wpf",
    "devexpress",
    "akka.net",
    "python",
    "langgraph",
    "fastapi",
    "llmops",
    "playwright",
    "microsoft graph",
    "gmail api",
    "mlflow",
    "prometheus",
    "grafana",
    "sap basis",
]

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def evaluate_source_policy(
    *,
    settings: Settings,
    source_url: str,
    source_name: str,
    source_type: JobSourceType,
    submission_channel: SubmissionChannel,
) -> dict[str, object]:
    host = ""
    if source_url:
        try:
            host = urlparse(source_url).netloc.replace("www.", "")
        except Exception:
            host = ""

    identifier = host or source_name.lower().replace(" ", "-") or source_type.value
    allowed = source_type == JobSourceType.manual_entry or any(
        identifier.endswith(domain) for domain in settings.allowed_source_domain_set
    )
    manual_only = any(identifier.endswith(domain) for domain in settings.manual_only_domain_set)
    note = "Source approved."

    if not allowed:
        note = f"Source {identifier} is not on the allowlist."
    elif manual_only and submission_channel != SubmissionChannel.manual_handoff:
        allowed = False
        note = f"Source {identifier} must use manual handoff."

    return {
        "source_identifier": identifier,
        "source_approved": allowed,
        "source_policy_note": note,
    }


def fetch_job_from_url(source_url: str) -> JobFetchResult:
    parsed = urlparse(source_url)
    source_name = parsed.netloc.replace("www.", "")
    job_id = _extract_linkedin_job_id(source_url)
    candidates = [source_url]
    if source_name.endswith("linkedin.com") and job_id:
        candidates = [
            f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}",
            f"https://www.linkedin.com/jobs/view/{job_id}/",
            source_url,
        ]

    last_note = f"Unable to fetch job details from {source_url}."
    final_url = source_url
    with httpx.Client(follow_redirects=True, timeout=20, headers=FETCH_HEADERS) as client:
        for candidate in candidates:
            try:
                response = client.get(candidate)
                final_url = str(response.url)
                body = response.text
                if _looks_like_login_wall(final_url, body):
                    last_note = f"{candidate} redirected to a login wall."
                    continue

                html = body
                text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
                role, company = _infer_role_company(html, final_url)
                if not text:
                    last_note = f"{candidate} returned an empty page."
                    continue

                note = "Fetched job details from the public job page."
                if candidate != source_url:
                    note = f"Fetched job details using fallback URL {candidate}."
                return JobFetchResult(
                    source_url=source_url,
                    final_url=final_url,
                    source_name=source_name or "job-source",
                    company=company,
                    role=role,
                    job_text=text,
                    raw_html=html,
                    fetch_note=note,
                    requires_auth=False,
                )
            except Exception as exc:
                last_note = f"Fetching {candidate} failed: {exc}"

    return JobFetchResult(
        source_url=source_url,
        final_url=final_url,
        source_name=source_name or "job-source",
        fetch_note=last_note,
        requires_auth=source_name.endswith("linkedin.com"),
    )


def normalize_job_post(
    *,
    company: str,
    role: str,
    source_name: str,
    source_url: str,
    source_type: JobSourceType,
    destination: str,
    submission_channel: SubmissionChannel,
    job_text: str,
    source_identifier: str,
    source_approved: bool,
    source_policy_note: str,
) -> JobOpportunity:
    description = BeautifulSoup(job_text, "html.parser").get_text(" ", strip=True)
    location_mode = _infer_location_mode(description)
    compensation_hint = _extract_compensation(description)
    work_auth = _infer_work_authorization(description)

    return JobOpportunity(
        company=company,
        role=role,
        source_name=source_name,
        source_url=source_url,
        source_type=source_type,
        destination=destination,
        submission_channel=submission_channel,
        normalized_description=description,
        location_mode=location_mode,
        compensation_hint=compensation_hint,
        work_authorization_requirement=work_auth,
        source_identifier=source_identifier,
        source_approved=source_approved,
        source_policy_note=source_policy_note,
    )


def extract_job_requirements(description: str) -> JobRequirements:
    text = description.lower()
    required = _extract_skills_from_line(text, "required")
    preferred = _extract_skills_from_line(text, "preferred")

    if not required:
        required = [skill for skill in KNOWN_SKILLS if skill in text][:6]

    languages = []
    if "english" in text:
        languages.append("English")
    if "german" in text:
        languages.append("German")

    education = []
    if "bachelor" in text:
        education.append("Bachelor's degree")
    if "master" in text:
        education.append("Master's degree")

    hard_blockers = []
    if "no sponsorship" in text or "sponsorship unavailable" in text:
        hard_blockers.append("Role states that sponsorship is unavailable.")
    if "german c1" in text:
        hard_blockers.append("Role requires German C1 proficiency.")

    questions = [
        "Why are you interested in this role?",
        "Which parts of your background are the strongest match?",
        "What is your current availability and preferred work setup?",
    ]

    return JobRequirements(
        required_skills=[_display_skill(skill) for skill in required],
        preferred_skills=[_display_skill(skill) for skill in preferred],
        years_required=_extract_years_required(text),
        language_requirements=languages,
        education_requirements=education,
        hard_blockers=hard_blockers,
        application_questions=questions,
    )


def _extract_skills_from_line(text: str, marker: str) -> list[str]:
    lines = re.split(r"[\n\.]", text)
    matches: list[str] = []
    for line in lines:
        if marker not in line:
            continue
        for skill in KNOWN_SKILLS:
            if skill in line:
                matches.append(skill)
    seen: set[str] = set()
    unique: list[str] = []
    for item in matches:
        if item not in seen:
            unique.append(item)
            seen.add(item)
    return unique


def _extract_years_required(text: str) -> int:
    match = re.search(r"(\d{1,2})\+?\s+years", text)
    return int(match.group(1)) if match else 0


def _infer_location_mode(text: str) -> str:
    if "remote" in text:
        return "remote"
    if "hybrid" in text:
        return "hybrid"
    if "onsite" in text or "on-site" in text:
        return "onsite"
    return "unknown"


def _extract_compensation(text: str) -> str:
    match = re.search(r"(CHF|EUR|USD)\s?\d{2,3}[kK]", text)
    return match.group(0) if match else ""


def _infer_work_authorization(text: str) -> str:
    if "switzerland" in text and "authorization" in text:
        return "Authorization to work in Switzerland"
    if "europe" in text and "remote" in text:
        return "Eligibility to work remotely in Europe"
    if "no sponsorship" in text:
        return "Existing work authorization required"
    return ""


def _display_skill(skill: str) -> str:
    mapping = {
        "c#": "C#",
        ".net": ".NET",
        "asp.net core": "ASP.NET Core",
        "sql": "SQL",
        "wpf": "WPF",
        "akka.net": "Akka.NET",
        "microsoft graph": "Microsoft Graph",
        "gmail api": "Gmail API",
    }
    return mapping.get(skill, skill.title())


def _looks_like_login_wall(final_url: str, body: str) -> bool:
    lowered = body.lower()
    return "linkedin.com/uas/login" in final_url.lower() or "sign in | linkedin" in lowered or "join linkedin" in lowered


def _extract_linkedin_job_id(url: str) -> str:
    path_match = re.search(r"/jobs/view/(\d+)", url)
    if path_match:
        return path_match.group(1)
    query_match = re.search(r"currentJobId=(\d+)", url)
    if query_match:
        return query_match.group(1)
    return ""


def _infer_role_company(html: str, final_url: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for selector in (
        ".top-card-layout__title",
        ".topcard__title",
        "h1",
    ):
        node = soup.select_one(selector)
        if node and node.get_text(strip=True):
            role = node.get_text(" ", strip=True)
            company = ""
            for company_selector in (".topcard__org-name-link", ".topcard__flavor", ".top-card-layout__card .topcard__flavor"):
                company_node = soup.select_one(company_selector)
                if company_node and company_node.get_text(strip=True):
                    company = company_node.get_text(" ", strip=True)
                    break
            return role, company

    title_node = soup.find("title")
    title = unescape(title_node.get_text(" ", strip=True)) if title_node else ""
    if " at " in title:
        role, company = title.split(" at ", 1)
        company = company.split(" | ", 1)[0]
        return role.strip(), company.strip()

    meta_title = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "title"})
    if meta_title and meta_title.get("content"):
        meta_value = unescape(meta_title["content"]).strip()
        if " at " in meta_value:
            role, company = meta_value.split(" at ", 1)
            return role.strip(), company.split(" | ", 1)[0].strip()
        return meta_value, ""

    host = urlparse(final_url).netloc.replace("www.", "")
    return "", host
