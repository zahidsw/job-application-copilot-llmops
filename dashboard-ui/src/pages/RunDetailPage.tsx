import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArtifactList } from '../components/ArtifactList'
import { StageTimeline } from '../components/StageTimeline'
import { StatusPill } from '../components/StatusPill'
import { api, reportDownloadUrl } from '../lib/api'
import {
  formatDate,
  formatScore,
  pathFileName,
  scoreTone,
} from '../lib/format'
import type { ApplicationResult } from '../types'

export function RunDetailPage() {
  const { runId = '' } = useParams()
  const [run, setRun] = useState<ApplicationResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [discoveringSimilarJobs, setDiscoveringSimilarJobs] = useState(false)
  const [rejectReason, setRejectReason] = useState('Rejected by operator.')

  useEffect(() => {
    let isMounted = true

    async function loadRun() {
      try {
        setError(null)
        const nextRun = await api.getRun(runId)
        if (isMounted) {
          setRun(nextRun)
        }
      } catch (loadError) {
        if (isMounted) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load run details.')
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    loadRun()
    return () => {
      isMounted = false
    }
  }, [runId])

  async function handleApprove() {
    try {
      setBusy(true)
      const nextRun = await api.approveRun(runId, false)
      setRun(nextRun)
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Unable to approve this run.')
    } finally {
      setBusy(false)
    }
  }

  async function handleReject() {
    try {
      setBusy(true)
      const nextRun = await api.rejectRun(runId, rejectReason)
      setRun(nextRun)
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Unable to reject this run.')
    } finally {
      setBusy(false)
    }
  }

  async function handleDiscoverSimilarJobs() {
    if (!run) {
      return
    }
    try {
      setDiscoveringSimilarJobs(true)
      setError(null)
      const nextRun = await api.discoverSimilarJobs(runId, run.request.similar_job_limit ?? 5)
      setRun(nextRun)
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Unable to discover similar jobs.')
    } finally {
      setDiscoveringSimilarJobs(false)
    }
  }

  if (loading) {
    return <p className="empty-state">Loading run details…</p>
  }

  if (error) {
    return <p className="error-banner">{error}</p>
  }

  if (!run) {
    return <p className="empty-state">This run could not be found.</p>
  }

  const evidenceFileName = pathFileName(run.submission_record?.evidence ?? '')

  return (
    <div className="detail-layout">
      <section className="detail-main">
        <section className="panel panel-hero">
          <div>
            <p className="eyebrow">Run detail</p>
            <h3>{run.opportunity.role}</h3>
            <p className="subtle-copy">{run.opportunity.company}</p>
          </div>
          <div className="hero-score">
            <span className={`score-chip tone-${scoreTone(run.assessment.overall_score)}`}>
              {formatScore(run.assessment.overall_score)}
            </span>
            <StatusPill status={run.status} />
          </div>
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Decision summary</p>
              <h3>Approval and dispatch state</h3>
            </div>
            <div className="hero-actions">
              {run.status === 'awaiting_approval' ? (
                <button className="primary-button" type="button" disabled={busy} onClick={handleApprove}>
                  {busy ? 'Working…' : 'Approve run'}
                </button>
              ) : null}
            </div>
          </div>

          <div className="decision-grid">
            <div>
              <p className="eyebrow">Action after approval</p>
              <p>{run.approval_packet?.exact_action_after_approval ?? 'No approval packet available.'}</p>
            </div>
            <div>
              <p className="eyebrow">Source policy</p>
              <p>{run.opportunity.source_policy_note}</p>
            </div>
            <div>
              <p className="eyebrow">Channel</p>
              <p>{run.request.submission_channel}</p>
            </div>
            <div>
              <p className="eyebrow">Updated</p>
              <p>{formatDate(run.updated_at)}</p>
            </div>
          </div>

          <label className="field">
            <span>Reject reason</span>
            <textarea rows={3} value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} />
          </label>
          <button className="danger-button" type="button" disabled={busy} onClick={handleReject}>
            Reject run
          </button>
        </section>

        <section className="panel">
          <p className="eyebrow">Requirements and fit</p>
          <h3>What the matcher extracted</h3>
          <div className="chips-wrap">
            {run.requirements.required_skills.map((skill) => (
              <span key={`required-${skill}`} className="chip chip-solid">
                {skill}
              </span>
            ))}
            {run.requirements.preferred_skills.map((skill) => (
              <span key={`preferred-${skill}`} className="chip">
                {skill}
              </span>
            ))}
            {run.requirements.language_requirements.map((language) => (
              <span key={`language-${language}`} className="chip chip-muted">
                {language}
              </span>
            ))}
          </div>

          <div className="score-breakdown">
            {Object.entries(run.assessment.score_breakdown).map(([label, value]) => (
              <div key={label} className="score-row">
                <span>{label}</span>
                <div className="score-bar">
                  <div className="score-bar-fill" style={{ width: `${Math.min(value, 100)}%` }} />
                </div>
                <strong>{value}</strong>
              </div>
            ))}
          </div>

          <div className="two-column-copy">
            <div>
              <p className="eyebrow">Evidence highlights</p>
              <ul className="plain-list">
                {run.assessment.evidence_highlights.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="eyebrow">Application questions</p>
              <ul className="plain-list">
                {run.requirements.application_questions.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="panel">
          <p className="eyebrow">Generated files</p>
          <h3>Artifacts for operator review</h3>
          <ArtifactList runId={run.run_id} artifacts={run.artifacts} />
          {evidenceFileName ? (
            <a
              className="ghost-button"
              href={reportDownloadUrl(run.run_id, evidenceFileName)}
              target="_blank"
              rel="noreferrer"
            >
              Open submission report
            </a>
          ) : null}
        </section>

        <section className="panel">
          <p className="eyebrow">Stage timeline</p>
          <h3>Pipeline execution trace</h3>
          <StageTimeline stages={run.stage_summaries} />
        </section>

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Similar jobs</p>
              <h3>Internet jobs that look at least 80% similar</h3>
            </div>
            <button className="primary-button" type="button" disabled={discoveringSimilarJobs} onClick={handleDiscoverSimilarJobs}>
              {discoveringSimilarJobs ? 'Finding…' : run.similar_jobs.length ? 'Refresh similar jobs' : 'Find similar jobs'}
            </button>
          </div>
          {run.similar_jobs.length ? (
            <div className="artifact-list">
              {run.similar_jobs.map((job) => (
                <article key={`${job.source_url}-${job.similarity_score}`} className="artifact-row">
                  <div>
                    <p className="artifact-label">{job.source_name}</p>
                    <h4>{job.role}</h4>
                    <p className="subtle-copy">
                      {job.company || 'Unknown company'} · {formatScore(job.similarity_score)}
                    </p>
                    {job.location_hint || job.location_mode !== 'unknown' ? (
                      <p className="subtle-copy">
                        Location: {job.location_hint || job.location_mode}
                      </p>
                    ) : null}
                    {job.matched_skills.length ? (
                      <p className="subtle-copy">Shared skills: {job.matched_skills.join(', ')}</p>
                    ) : null}
                    {job.snippet ? <p>{job.snippet}</p> : null}
                  </div>
                  <div className="hero-actions">
                    <a className="ghost-button" href={job.source_url} target="_blank" rel="noreferrer">
                      Open source
                    </a>
                    <Link className="primary-button" to={buildSimilarJobLaunchUrl(job)}>
                      Start tailored run
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="empty-state">No similar jobs have been loaded yet. Click the button above to search for them.</p>
          )}
        </section>
      </section>

      <aside className="detail-side">
        <section className="panel">
          <p className="eyebrow">Approval packet</p>
          <h3>{run.approval_packet?.summary ?? 'No approval packet yet.'}</h3>
          <ul className="plain-list">
            {(run.approval_packet?.risks ?? []).map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <p className="eyebrow">Submission record</p>
          {run.submission_record ? (
            <>
              <StatusPill status={run.submission_record.status} />
              <p>{run.submission_record.dispatch_summary}</p>
              <p className="subtle-copy">{run.submission_record.destination}</p>
            </>
          ) : (
            <p className="empty-state">This run has not been dispatched yet.</p>
          )}
        </section>

        <section className="panel">
          <p className="eyebrow">Request payload</p>
          <div className="meta-grid">
            <div>
              <span>Source</span>
              <strong>{run.request.source_name || 'manual'}</strong>
            </div>
            <div>
              <span>Source type</span>
              <strong>{run.request.source_type}</strong>
            </div>
            <div>
              <span>Destination</span>
              <strong>{run.request.destination || 'n/a'}</strong>
            </div>
            <div>
              <span>Run id</span>
              <strong>{run.run_id}</strong>
            </div>
          </div>
          <details className="details-block">
            <summary>Open normalized description</summary>
            <p>{run.opportunity.normalized_description}</p>
          </details>
          <Link className="ghost-button" to="/">
            Back to overview
          </Link>
        </section>
      </aside>
    </div>
  )
}

function buildSimilarJobLaunchUrl(job: ApplicationResult['similar_jobs'][number]) {
  const normalizedSource = job.source_name.toLowerCase()
  const sourceType =
    normalizedSource.includes('linkedin') || normalizedSource.includes('indeed') ? 'saved_search' : 'company_site'
  const params = new URLSearchParams({
    source_url: job.source_url,
    source_type: sourceType,
    submission_channel: job.requires_auth ? 'manual_handoff' : 'company_site',
    destination: job.source_url,
    company: job.company || '',
    role: job.role,
    source_name: job.source_name,
    discover_similar_jobs: 'false',
    similar_job_limit: '5',
  })
  return `/submit?${params.toString()}`
}
