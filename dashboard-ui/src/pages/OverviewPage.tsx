import { useDeferredValue, useEffect, useState, startTransition } from 'react'
import { Link } from 'react-router-dom'
import { MetricBand } from '../components/MetricBand'
import { StatusPill } from '../components/StatusPill'
import { api } from '../lib/api'
import { formatDate, formatScore, serviceLinks } from '../lib/format'
import type { EvaluationSummary, HealthResponse, RunSummary } from '../types'

export function OverviewPage() {
  const [live, setLive] = useState<HealthResponse | null>(null)
  const [ready, setReady] = useState<HealthResponse | null>(null)
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [evalSummary, setEvalSummary] = useState<EvaluationSummary | null>(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const deferredSearch = useDeferredValue(search)

  useEffect(() => {
    let isMounted = true

    async function loadOverview() {
      try {
        setError(null)
        const [liveResponse, readyResponse, runList, evalResponse] = await Promise.all([
          api.live(),
          api.ready(),
          api.listRuns(),
          api.getLatestEval(),
        ])

        if (!isMounted) {
          return
        }

        setLive(liveResponse)
        setReady(readyResponse)
        setRuns(runList)
        setEvalSummary(evalResponse)
      } catch (loadError) {
        if (!isMounted) {
          return
        }
        setError(loadError instanceof Error ? loadError.message : 'Unable to load dashboard overview.')
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    loadOverview()
    const intervalId = window.setInterval(loadOverview, 30000)

    return () => {
      isMounted = false
      window.clearInterval(intervalId)
    }
  }, [])

  const query = deferredSearch.trim().toLowerCase()
  const filteredRuns = !query
    ? runs
    : runs.filter((run) =>
        [run.company, run.role, run.status, run.run_id].some((value) => value.toLowerCase().includes(query)),
      )

  const awaitingApproval = runs.filter((run) => run.status === 'awaiting_approval')
  const blockedRuns = runs.filter((run) => run.status === 'blocked')
  const completedRuns = runs.filter(
    (run) => run.status === 'submitted' || run.status === 'manual_handoff',
  )
  const spotlightRun = awaitingApproval[0] ?? filteredRuns[0] ?? null

  const metrics = [
    {
      label: 'Environment',
      value: live?.environment ?? 'loading',
      note: ready ? 'API and dependencies reachable' : 'Waiting for readiness',
      tone: ready ? ('good' as const) : ('watch' as const),
    },
    {
      label: 'Awaiting approval',
      value: String(awaitingApproval.length),
      note: 'Runs paused at operator gate',
      tone: awaitingApproval.length ? ('watch' as const) : ('neutral' as const),
    },
    {
      label: 'Blocked',
      value: String(blockedRuns.length),
      note: 'Runs stopped by threshold or policy',
      tone: blockedRuns.length ? ('risk' as const) : ('neutral' as const),
    },
    {
      label: 'Submitted or handed off',
      value: String(completedRuns.length),
      note: 'Approved runs that reached dispatch state',
      tone: completedRuns.length ? ('good' as const) : ('neutral' as const),
    },
    {
      label: 'Eval dataset',
      value: String(evalSummary?.case_count ?? 0),
      note: 'Latest evaluation case count',
      tone: 'neutral' as const,
    },
  ]

  return (
    <div className="page-grid">
      <section className="page-main">
        <section className="panel panel-hero">
          <div>
            <p className="eyebrow">Control surface</p>
            <h3>Track application throughput, inspect approval-ready runs, and jump into the exact packet that needs a decision.</h3>
          </div>
          <div className="hero-actions">
            <Link className="primary-button" to="/submit">
              Launch a new run
            </Link>
            <Link className="ghost-button" to="/profile">
              Open profile vault
            </Link>
          </div>
        </section>

        <MetricBand items={metrics} />

        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Recent pipeline</p>
              <h3>Live runs</h3>
            </div>
            <input
              className="search-input"
              type="search"
              value={search}
              placeholder="Search company, role, status, run id"
              onChange={(event) => {
                const nextValue = event.target.value
                startTransition(() => {
                  setSearch(nextValue)
                })
              }}
            />
          </div>

          {loading ? <p className="empty-state">Loading runs…</p> : null}
          {error ? <p className="error-banner">{error}</p> : null}

          {!loading && !filteredRuns.length ? <p className="empty-state">No runs match the current filter.</p> : null}

          {filteredRuns.length ? (
            <div className="run-table">
              {filteredRuns.map((run) => (
                <Link key={run.run_id} className="run-row" to={`/runs/${run.run_id}`}>
                  <div>
                    <p className="eyebrow">{run.company}</p>
                    <h4>{run.role}</h4>
                  </div>
                  <div className="run-row-meta">
                    <strong>{formatScore(run.score)}</strong>
                    <StatusPill status={run.status} />
                    <small>{formatDate(run.updated_at)}</small>
                  </div>
                </Link>
              ))}
            </div>
          ) : null}
        </section>
      </section>

      <aside className="page-side">
        <section className="panel">
          <p className="eyebrow">Approval queue</p>
          <h3>{awaitingApproval.length ? `${awaitingApproval.length} run(s) waiting for a decision` : 'Approval queue is clear'}</h3>
          <div className="compact-list">
            {awaitingApproval.slice(0, 4).map((run) => (
              <Link key={run.run_id} className="compact-link" to={`/runs/${run.run_id}`}>
                <span>{run.company}</span>
                <small>{run.role}</small>
              </Link>
            ))}
          </div>
        </section>

        <section className="panel">
          <p className="eyebrow">Spotlight run</p>
          {spotlightRun ? (
            <>
              <h3>{spotlightRun.role}</h3>
              <p className="subtle-copy">{spotlightRun.company}</p>
              <div className="spotlight-strip">
                <StatusPill status={spotlightRun.status} />
                <strong>{formatScore(spotlightRun.score)}</strong>
              </div>
              <p className="subtle-copy">Last updated {formatDate(spotlightRun.updated_at)}</p>
              <Link className="primary-button" to={`/runs/${spotlightRun.run_id}`}>
                Inspect run
              </Link>
            </>
          ) : (
            <p className="empty-state">Submit a run and it will surface here automatically.</p>
          )}
        </section>

        <section className="panel">
          <p className="eyebrow">Linked stack</p>
          <div className="link-stack">
            {serviceLinks().map((link) => (
              <a key={link.label} className="service-link" href={link.href} target="_blank" rel="noreferrer">
                <span>{link.label}</span>
                <small>{link.note}</small>
              </a>
            ))}
          </div>
        </section>
      </aside>
    </div>
  )
}
