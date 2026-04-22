import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import type { JobApplicationRequest, JobFetchResult, JobSourceType, JobUrlApplicationRequest, SubmissionChannel } from '../types'

const sourceTypeOptions: JobSourceType[] = [
  'saved_search',
  'company_site',
  'manual_entry',
  'email_alert',
  'imported_file',
]

const channelOptions: SubmissionChannel[] = ['manual_handoff', 'company_site', 'email']

const defaultUrlForm: JobUrlApplicationRequest = {
  profile_id: 'primary-candidate',
  source_url: '',
  source_type: 'saved_search',
  destination: '',
  submission_channel: 'manual_handoff',
  company: '',
  role: '',
  source_name: '',
  discover_similar_jobs: false,
  similar_job_limit: 5,
}

const defaultManualForm: JobApplicationRequest = {
  profile_id: 'primary-candidate',
  company: '',
  role: '',
  source_name: '',
  source_url: '',
  source_type: 'manual_entry',
  destination: '',
  submission_channel: 'company_site',
  job_text: '',
  discover_similar_jobs: false,
  similar_job_limit: 5,
}

export function SubmitPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [mode, setMode] = useState<'url' | 'manual'>('url')
  const [urlForm, setUrlForm] = useState<JobUrlApplicationRequest>(defaultUrlForm)
  const [manualForm, setManualForm] = useState<JobApplicationRequest>(defaultManualForm)
  const [preview, setPreview] = useState<JobFetchResult | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [previewing, setPreviewing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const sourceUrl = searchParams.get('source_url')?.trim() ?? ''
    if (!sourceUrl) {
      return
    }

    const sourceType = (searchParams.get('source_type') as JobSourceType | null) ?? defaultUrlForm.source_type
    const submissionChannel =
      (searchParams.get('submission_channel') as SubmissionChannel | null) ?? defaultUrlForm.submission_channel
    const similarJobLimit = Number(searchParams.get('similar_job_limit') ?? defaultUrlForm.similar_job_limit)

    setMode('url')
    setUrlForm((current) => ({
      ...current,
      source_url: sourceUrl,
      company: searchParams.get('company') ?? current.company,
      role: searchParams.get('role') ?? current.role,
      source_name: searchParams.get('source_name') ?? current.source_name,
      destination: searchParams.get('destination') ?? current.destination,
      source_type: sourceType,
      submission_channel: submissionChannel,
      discover_similar_jobs: parseBooleanParam(searchParams.get('discover_similar_jobs')),
      similar_job_limit: Number.isFinite(similarJobLimit) && similarJobLimit > 0 ? similarJobLimit : defaultUrlForm.similar_job_limit,
    }))
  }, [searchParams])

  async function handlePreview() {
    if (!urlForm.source_url.trim()) {
      setError('Paste a source URL before previewing.')
      return
    }

    try {
      setPreviewing(true)
      setError(null)
      const result = await api.previewJobUrl(urlForm.source_url.trim())
      setPreview(result)
      setUrlForm((current) => ({
        ...current,
        company: current.company || result.company,
        role: current.role || result.role,
        source_name: current.source_name || result.source_name,
        destination: current.destination || result.final_url || current.source_url,
      }))
    } catch (previewError) {
      setError(previewError instanceof Error ? previewError.message : 'Unable to preview the job URL.')
    } finally {
      setPreviewing(false)
    }
  }

  async function handleSubmit() {
    try {
      setSubmitting(true)
      setError(null)
      const result =
        mode === 'url'
          ? await api.submitRunFromUrl({
              ...urlForm,
              source_url: urlForm.source_url.trim(),
              destination: urlForm.destination?.trim() ?? '',
              company: urlForm.company?.trim(),
              role: urlForm.role?.trim(),
              source_name: urlForm.source_name?.trim(),
            })
          : await api.submitRun({
              ...manualForm,
              company: manualForm.company.trim(),
              role: manualForm.role.trim(),
              source_name: manualForm.source_name.trim(),
              source_url: manualForm.source_url.trim(),
              destination: manualForm.destination.trim(),
              job_text: manualForm.job_text.trim(),
            })
      navigate(`/runs/${result.run_id}`)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to submit this run.')
    } finally {
      setSubmitting(false)
    }
  }

  const payloadPreview = mode === 'url' ? urlForm : manualForm

  return (
    <div className="page-grid">
      <section className="page-main">
        <section className="panel panel-hero">
          <div>
            <p className="eyebrow">New application run</p>
            <h3>Use URL-first intake for public job pages, or drop to manual mode when you need full pasted text.</h3>
          </div>
          <div className="mode-switch">
            <button
              className={`tab-button${mode === 'url' ? ' is-active' : ''}`}
              type="button"
              onClick={() => setMode('url')}
            >
              URL first
            </button>
            <button
              className={`tab-button${mode === 'manual' ? ' is-active' : ''}`}
              type="button"
              onClick={() => setMode('manual')}
            >
              Manual
            </button>
          </div>
        </section>

        {error ? <p className="error-banner">{error}</p> : null}

        {mode === 'url' ? (
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">URL-only intake</p>
                <h3>Preview the fetch, then run the full pipeline</h3>
              </div>
              <div className="hero-actions">
                <button className="ghost-button" type="button" onClick={handlePreview} disabled={previewing}>
                  {previewing ? 'Previewing…' : 'Fetch preview'}
                </button>
                <button className="primary-button" type="button" onClick={handleSubmit} disabled={submitting}>
                  {submitting ? 'Submitting…' : 'Start URL run'}
                </button>
              </div>
            </div>

            <div className="form-grid">
              <label className="field field-wide">
                <span>Source URL</span>
                <input
                  value={urlForm.source_url}
                  onChange={(event) => setUrlForm((current) => ({ ...current, source_url: event.target.value }))}
                  placeholder="https://www.linkedin.com/jobs/view/4328133201/"
                />
              </label>
              <label className="field">
                <span>Profile id</span>
                <input
                  value={urlForm.profile_id}
                  onChange={(event) => setUrlForm((current) => ({ ...current, profile_id: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Source type</span>
                <select
                  value={urlForm.source_type}
                  onChange={(event) =>
                    setUrlForm((current) => ({ ...current, source_type: event.target.value as JobSourceType }))
                  }
                >
                  {sourceTypeOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Submission channel</span>
                <select
                  value={urlForm.submission_channel}
                  onChange={(event) =>
                    setUrlForm((current) => ({
                      ...current,
                      submission_channel: event.target.value as SubmissionChannel,
                    }))
                  }
                >
                  {channelOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Destination</span>
                <input
                  value={urlForm.destination}
                  onChange={(event) => setUrlForm((current) => ({ ...current, destination: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Company override</span>
                <input
                  value={urlForm.company ?? ''}
                  onChange={(event) => setUrlForm((current) => ({ ...current, company: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Role override</span>
                <input
                  value={urlForm.role ?? ''}
                  onChange={(event) => setUrlForm((current) => ({ ...current, role: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Source name override</span>
                <input
                  value={urlForm.source_name ?? ''}
                  onChange={(event) => setUrlForm((current) => ({ ...current, source_name: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Discover similar jobs</span>
                <select
                  value={urlForm.discover_similar_jobs ? 'yes' : 'no'}
                  onChange={(event) =>
                    setUrlForm((current) => ({
                      ...current,
                      discover_similar_jobs: event.target.value === 'yes',
                    }))
                  }
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </select>
              </label>
              <label className="field">
                <span>Similar job limit</span>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={urlForm.similar_job_limit ?? 5}
                  onChange={(event) =>
                    setUrlForm((current) => ({
                      ...current,
                      similar_job_limit: Number(event.target.value) || 5,
                    }))
                  }
                />
              </label>
            </div>
          </section>
        ) : (
          <section className="panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Manual intake</p>
                <h3>Submit a fully specified request directly to the main run endpoint</h3>
              </div>
              <button className="primary-button" type="button" onClick={handleSubmit} disabled={submitting}>
                {submitting ? 'Submitting…' : 'Start manual run'}
              </button>
            </div>

            <div className="form-grid">
              <label className="field">
                <span>Profile id</span>
                <input
                  value={manualForm.profile_id}
                  onChange={(event) => setManualForm((current) => ({ ...current, profile_id: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Company</span>
                <input
                  value={manualForm.company}
                  onChange={(event) => setManualForm((current) => ({ ...current, company: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Role</span>
                <input
                  value={manualForm.role}
                  onChange={(event) => setManualForm((current) => ({ ...current, role: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Source name</span>
                <input
                  value={manualForm.source_name}
                  onChange={(event) => setManualForm((current) => ({ ...current, source_name: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Source URL</span>
                <input
                  value={manualForm.source_url}
                  onChange={(event) => setManualForm((current) => ({ ...current, source_url: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Source type</span>
                <select
                  value={manualForm.source_type}
                  onChange={(event) =>
                    setManualForm((current) => ({ ...current, source_type: event.target.value as JobSourceType }))
                  }
                >
                  {sourceTypeOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Submission channel</span>
                <select
                  value={manualForm.submission_channel}
                  onChange={(event) =>
                    setManualForm((current) => ({
                      ...current,
                      submission_channel: event.target.value as SubmissionChannel,
                    }))
                  }
                >
                  {channelOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Destination</span>
                <input
                  value={manualForm.destination}
                  onChange={(event) => setManualForm((current) => ({ ...current, destination: event.target.value }))}
                />
              </label>
              <label className="field field-wide">
                <span>Job description text</span>
                <textarea
                  rows={14}
                  value={manualForm.job_text}
                  onChange={(event) => setManualForm((current) => ({ ...current, job_text: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Discover similar jobs</span>
                <select
                  value={manualForm.discover_similar_jobs ? 'yes' : 'no'}
                  onChange={(event) =>
                    setManualForm((current) => ({
                      ...current,
                      discover_similar_jobs: event.target.value === 'yes',
                    }))
                  }
                >
                  <option value="no">No</option>
                  <option value="yes">Yes</option>
                </select>
              </label>
              <label className="field">
                <span>Similar job limit</span>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={manualForm.similar_job_limit ?? 5}
                  onChange={(event) =>
                    setManualForm((current) => ({
                      ...current,
                      similar_job_limit: Number(event.target.value) || 5,
                    }))
                  }
                />
              </label>
            </div>
          </section>
        )}
      </section>

      <aside className="page-side">
        <section className="panel">
          <p className="eyebrow">Endpoint preview</p>
          <h3>{mode === 'url' ? 'POST /api/v1/applications/run-from-url' : 'POST /api/v1/applications/run'}</h3>
          <pre className="json-preview">{JSON.stringify(payloadPreview, null, 2)}</pre>
        </section>

        <section className="panel">
          <p className="eyebrow">URL fetch preview</p>
          {preview ? (
            <>
              <h3>{preview.role || 'Fetched posting'}</h3>
              <p className="subtle-copy">{preview.company || preview.source_name}</p>
              <p>{preview.fetch_note}</p>
              <details className="details-block">
                <summary>Open extracted text</summary>
                <p>{preview.job_text}</p>
              </details>
            </>
          ) : (
            <p className="empty-state">Preview a URL to see what the tool service extracts before running the workflow.</p>
          )}
        </section>
      </aside>
    </div>
  )
}

function parseBooleanParam(value: string | null) {
  if (!value) {
    return false
  }
  return value.toLowerCase() === 'true' || value.toLowerCase() === 'yes' || value === '1'
}
