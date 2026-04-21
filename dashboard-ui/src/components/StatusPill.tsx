import { formatStatusLabel, statusTone } from '../lib/format'

interface StatusPillProps {
  status: string
}

export function StatusPill({ status }: StatusPillProps) {
  return <span className={`status-pill tone-${statusTone(status)}`}>{formatStatusLabel(status)}</span>
}
