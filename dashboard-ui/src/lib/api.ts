import type {
  ApplicationResult,
  CandidateProfile,
  EvaluationSummary,
  HealthResponse,
  JobApplicationRequest,
  JobFetchResult,
  JobUrlApplicationRequest,
  ProfileAssetKind,
  ProfileVault,
  RunSummary,
} from '../types'
import { appRuntimeConfig } from './runtimeConfig'

const API_BASE = appRuntimeConfig.apiBaseUrl
const TOOL_BASE = appRuntimeConfig.toolBaseUrl

async function readJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...init?.headers,
    },
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const message =
      (payload && typeof payload.detail === 'string' && payload.detail) ||
      `${response.status} ${response.statusText}`
    throw new Error(message)
  }

  return (await response.json()) as T
}

export const api = {
  live: () => readJson<HealthResponse>('/live'),
  ready: () => readJson<HealthResponse>('/ready'),
  listRuns: (limit = 24) => readJson<RunSummary[]>(`/api/v1/runs?limit=${limit}`),
  getRun: (runId: string) => readJson<ApplicationResult>(`/api/v1/applications/${runId}`),
  getLatestEval: () => readJson<EvaluationSummary>('/api/v1/evals/latest'),
  getProfileVault: (profileId = 'primary-candidate') =>
    readJson<ProfileVault>(`/api/v1/profile-vault?profile_id=${encodeURIComponent(profileId)}`),
  saveProfile: (profile: CandidateProfile) =>
    readJson<ProfileVault>('/api/v1/profile-vault/profile', {
      method: 'POST',
      body: JSON.stringify(profile),
    }),
  uploadProfileAsset: async (file: File, kind: ProfileAssetKind) => {
    const form = new FormData()
    form.append('file', file)
    return readJson<ProfileVault>(
      `/api/v1/profile-vault/upload?kind=${encodeURIComponent(kind)}`,
      { method: 'POST', body: form },
    )
  },
  submitRun: (payload: JobApplicationRequest) =>
    readJson<ApplicationResult>('/api/v1/applications/run', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  submitRunFromUrl: (payload: JobUrlApplicationRequest) =>
    readJson<ApplicationResult>('/api/v1/applications/run-from-url', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  approveRun: (runId: string, sendEmailNow = false) =>
    readJson<ApplicationResult>(`/api/v1/applications/${runId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ send_email_now: sendEmailNow }),
    }),
  discoverSimilarJobs: (runId: string, limit = 5) =>
    readJson<ApplicationResult>(`/api/v1/applications/${runId}/similar-jobs?limit=${limit}`, {
      method: 'POST',
    }),
  rejectRun: (runId: string, reason: string) =>
    readJson<ApplicationResult>(`/api/v1/applications/${runId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  previewJobUrl: async (sourceUrl: string) => {
    const response = await fetch(`${TOOL_BASE}/fetch-job`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ source_url: sourceUrl }),
    })

    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new Error(
        (payload && typeof payload.detail === 'string' && payload.detail) ||
          `${response.status} ${response.statusText}`,
      )
    }

    return (await response.json()) as JobFetchResult
  },
}

export function artifactDownloadUrl(runId: string, fileName: string) {
  return `${API_BASE}/api/v1/artifacts/${encodeURIComponent(runId)}/${encodeURIComponent(fileName)}`
}

export function reportDownloadUrl(runId: string, fileName: string) {
  return `${API_BASE}/api/v1/reports/${encodeURIComponent(runId)}/${encodeURIComponent(fileName)}`
}
