import { formatStatusLabel } from '../lib/format'
import type { AgentStageSummary } from '../types'

interface StageTimelineProps {
  stages: AgentStageSummary[]
}

export function StageTimeline({ stages }: StageTimelineProps) {
  if (!stages.length) {
    return <p className="empty-state">No stage activity recorded yet.</p>
  }

  return (
    <ol className="stage-timeline">
      {stages.map((stage) => (
        <li key={`${stage.stage}-${stage.duration_seconds}`} className="stage-step">
          <div>
            <p className="eyebrow">{formatStatusLabel(stage.stage)}</p>
            <p>{stage.summary}</p>
          </div>
          <strong>{stage.duration_seconds.toFixed(3)}s</strong>
        </li>
      ))}
    </ol>
  )
}
