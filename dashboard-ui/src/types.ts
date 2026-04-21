export type RunStatus =
  | 'queued'
  | 'intake'
  | 'matching'
  | 'tailoring'
  | 'awaiting_approval'
  | 'blocked'
  | 'submitted'
  | 'manual_handoff'
  | 'rejected'
  | 'failed'

export type JobSourceType =
  | 'email_alert'
  | 'company_site'
  | 'saved_search'
  | 'manual_entry'
  | 'imported_file'

export type SubmissionChannel = 'email' | 'company_site' | 'manual_handoff'

export type ProfileAssetKind =
  | 'cv'
  | 'motivation_letter'
  | 'reference_letter'
  | 'previous_application'
  | 'other'

export interface CandidateSkill {
  name: string
  years: number
  confidence: number
  evidence: string
}

export interface CandidateProfile {
  profile_id: string
  display_name: string
  headline: string
  work_authorization: string
  preferred_locations: string[]
  salary_floor: number
  languages: string[]
  education: string[]
  experience_summary: string
  skills: CandidateSkill[]
  achievements: string[]
}

export interface ProfileAssetRecord {
  asset_id: string
  kind: ProfileAssetKind
  file_name: string
  stored_path: string
  extracted_text_excerpt: string
  imported_at: string
}

export interface ProfileVault {
  profile_id: string
  profile: CandidateProfile
  assets: ProfileAssetRecord[]
  cv_style_samples: string[]
  motivation_letter_samples: string[]
  reference_highlights: string[]
  updated_at: string
}

export interface JobUrlApplicationRequest {
  profile_id: string
  company?: string
  role?: string
  source_name?: string
  source_url: string
  source_type: JobSourceType
  destination?: string
  submission_channel: SubmissionChannel
}

export interface JobApplicationRequest {
  profile_id: string
  company: string
  role: string
  source_name: string
  source_url: string
  source_type: JobSourceType
  destination: string
  submission_channel: SubmissionChannel
  job_text: string
}

export interface JobFetchResult {
  source_url: string
  final_url: string
  source_name: string
  company: string
  role: string
  job_text: string
  raw_html: string
  fetch_note: string
  requires_auth: boolean
}

export interface JobOpportunity {
  company: string
  role: string
  source_name: string
  source_url: string
  source_type: JobSourceType
  destination: string
  submission_channel: SubmissionChannel
  normalized_description: string
  location_mode: string
  compensation_hint: string
  work_authorization_requirement: string
  source_identifier: string
  source_approved: boolean
  source_policy_note: string
}

export interface JobRequirements {
  required_skills: string[]
  preferred_skills: string[]
  years_required: number
  language_requirements: string[]
  education_requirements: string[]
  hard_blockers: string[]
  application_questions: string[]
}

export interface MatchAssessment {
  overall_score: number
  decision: string
  ready_for_tailoring: boolean
  score_breakdown: Record<string, number>
  evidence_highlights: string[]
  missing_evidence: string[]
  hard_blockers: string[]
}

export interface GeneratedArtifact {
  artifact_type: string
  file_name: string
  content: string
  path: string
}

export interface ApprovalPacket {
  summary: string
  exact_action_after_approval: string
  risks: string[]
  artifacts: GeneratedArtifact[]
}

export interface SubmissionRecord {
  channel: SubmissionChannel
  status: string
  destination: string
  dispatch_summary: string
  evidence: string
}

export interface AgentStageSummary {
  stage: string
  summary: string
  duration_seconds: number
}

export interface ApplicationResult {
  run_id: string
  status: RunStatus
  request: JobApplicationRequest & { profile: CandidateProfile }
  opportunity: JobOpportunity
  requirements: JobRequirements
  assessment: MatchAssessment
  artifacts: GeneratedArtifact[]
  approval_packet: ApprovalPacket | null
  submission_record: SubmissionRecord | null
  stage_summaries: AgentStageSummary[]
  metrics: Record<string, number>
  created_at: string
  updated_at: string
}

export interface RunSummary {
  run_id: string
  status: RunStatus
  company: string
  role: string
  score: number
  updated_at: string
}

export interface HealthResponse {
  service: string
  environment: string
  details: Record<string, unknown>
}

export interface EvaluationSummary {
  case_count: number
  metrics: Record<string, number>
}
