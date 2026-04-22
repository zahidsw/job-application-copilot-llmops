from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    queued = "queued"
    intake = "intake"
    matching = "matching"
    tailoring = "tailoring"
    awaiting_approval = "awaiting_approval"
    blocked = "blocked"
    submitted = "submitted"
    manual_handoff = "manual_handoff"
    rejected = "rejected"
    failed = "failed"


class JobSourceType(str, Enum):
    email_alert = "email_alert"
    company_site = "company_site"
    saved_search = "saved_search"
    manual_entry = "manual_entry"
    imported_file = "imported_file"


class SubmissionChannel(str, Enum):
    email = "email"
    company_site = "company_site"
    manual_handoff = "manual_handoff"


class ProfileAssetKind(str, Enum):
    cv = "cv"
    motivation_letter = "motivation_letter"
    reference_letter = "reference_letter"
    previous_application = "previous_application"
    other = "other"


class CandidateSkill(BaseModel):
    name: str
    years: int = 0
    confidence: float = 1.0
    evidence: str = ""


class CandidateProfile(BaseModel):
    profile_id: str = "primary-candidate"
    display_name: str = "Primary Candidate"
    headline: str = "Senior .NET / AI workflow engineer"
    work_authorization: str = "Switzerland, EU remote where permitted"
    preferred_locations: list[str] = Field(default_factory=lambda: ["Zurich", "Switzerland", "Remote Europe"])
    salary_floor: int = 130
    languages: list[str] = Field(default_factory=lambda: ["English", "German"])
    education: list[str] = Field(default_factory=lambda: ["B.Sc. Computer Science"])
    experience_summary: str = (
        "Senior engineer focused on workflow automation, internal tools, .NET delivery, API integrations, and applied AI systems."
    )
    skills: list[CandidateSkill] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)


class ProfileAssetRecord(BaseModel):
    asset_id: str
    kind: ProfileAssetKind
    file_name: str
    stored_path: str
    extracted_text_excerpt: str = ""
    extracted_text: str = ""
    imported_at: datetime = Field(default_factory=datetime.utcnow)


class ProfileVault(BaseModel):
    profile_id: str = "primary-candidate"
    profile: CandidateProfile = Field(default_factory=CandidateProfile)
    assets: list[ProfileAssetRecord] = Field(default_factory=list)
    cv_style_samples: list[str] = Field(default_factory=list)
    motivation_letter_samples: list[str] = Field(default_factory=list)
    reference_highlights: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobApplicationRequest(BaseModel):
    profile: CandidateProfile | None = None
    profile_id: str = "primary-candidate"
    company: str = ""
    role: str = ""
    source_name: str = ""
    source_url: str = ""
    source_type: JobSourceType = JobSourceType.manual_entry
    destination: str = ""
    submission_channel: SubmissionChannel = SubmissionChannel.company_site
    job_text: str = ""
    discover_similar_jobs: bool = False
    similar_job_limit: int = 5


class JobUrlApplicationRequest(BaseModel):
    profile: CandidateProfile | None = None
    profile_id: str = "primary-candidate"
    company: str = ""
    role: str = ""
    source_name: str = ""
    source_url: str
    source_type: JobSourceType = JobSourceType.company_site
    destination: str = ""
    submission_channel: SubmissionChannel = SubmissionChannel.company_site
    discover_similar_jobs: bool = False
    similar_job_limit: int = 5


class JobFetchResult(BaseModel):
    source_url: str
    final_url: str
    source_name: str
    company: str = ""
    role: str = ""
    job_text: str = ""
    raw_html: str = ""
    fetch_note: str = ""
    requires_auth: bool = False


class JobOpportunity(BaseModel):
    company: str
    role: str
    source_name: str
    source_url: str = ""
    source_type: JobSourceType
    destination: str = ""
    submission_channel: SubmissionChannel
    normalized_description: str
    location_mode: str = "unknown"
    compensation_hint: str = ""
    work_authorization_requirement: str = ""
    source_identifier: str = ""
    source_approved: bool = True
    source_policy_note: str = ""


class JobRequirements(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    years_required: int = 0
    language_requirements: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    hard_blockers: list[str] = Field(default_factory=list)
    application_questions: list[str] = Field(default_factory=list)


class MatchAssessment(BaseModel):
    overall_score: int
    decision: str
    ready_for_tailoring: bool
    score_breakdown: dict[str, int] = Field(default_factory=dict)
    evidence_highlights: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    hard_blockers: list[str] = Field(default_factory=list)


class SimilarJobMatch(BaseModel):
    role: str
    company: str = ""
    source_name: str
    source_url: str
    similarity_score: int
    location_mode: str = "unknown"
    matched_skills: list[str] = Field(default_factory=list)
    snippet: str = ""
    source_approved: bool = True
    source_policy_note: str = ""
    requires_auth: bool = False


class GeneratedArtifact(BaseModel):
    artifact_type: str
    file_name: str
    content: str
    path: str = ""


class ApprovalPacket(BaseModel):
    summary: str
    exact_action_after_approval: str
    risks: list[str] = Field(default_factory=list)
    artifacts: list[GeneratedArtifact] = Field(default_factory=list)


class SubmissionRecord(BaseModel):
    channel: SubmissionChannel
    status: str
    destination: str
    dispatch_summary: str
    evidence: str = ""


class AgentStageSummary(BaseModel):
    stage: str
    summary: str
    duration_seconds: float


class ApplicationResult(BaseModel):
    run_id: str
    status: RunStatus
    request: JobApplicationRequest
    opportunity: JobOpportunity
    requirements: JobRequirements
    assessment: MatchAssessment
    similar_jobs: list[SimilarJobMatch] = Field(default_factory=list)
    artifacts: list[GeneratedArtifact] = Field(default_factory=list)
    approval_packet: ApprovalPacket | None = None
    submission_record: SubmissionRecord | None = None
    stage_summaries: list[AgentStageSummary] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RunSummary(BaseModel):
    run_id: str
    status: RunStatus
    company: str
    role: str
    score: int
    updated_at: datetime


class ApproveRunRequest(BaseModel):
    send_email_now: bool = False


class RejectRunRequest(BaseModel):
    reason: str = "Rejected by operator."


class HealthResponse(BaseModel):
    service: str
    environment: str
    details: dict[str, object]


class EvaluationSummary(BaseModel):
    case_count: int
    metrics: dict[str, float]
