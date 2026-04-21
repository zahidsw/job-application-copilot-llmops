import type { RunStatus } from '../types'
import { appRuntimeConfig } from './runtimeConfig'

export function formatDate(value?: string) {
  if (!value) {
    return 'Unknown'
  }

  const date = new Date(value)
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

export function formatStatusLabel(status: string) {
  return status.replaceAll('_', ' ')
}

export function formatScore(score?: number) {
  return typeof score === 'number' ? `${score}%` : 'n/a'
}

export function scoreTone(score: number) {
  if (score >= 85) {
    return 'strong'
  }
  if (score >= 70) {
    return 'good'
  }
  if (score >= 50) {
    return 'watch'
  }
  return 'risk'
}

export function artifactLabel(artifactType: string) {
  return artifactType.replaceAll('_', ' ')
}

export function statusTone(status: RunStatus | string) {
  switch (status) {
    case 'awaiting_approval':
      return 'watch'
    case 'submitted':
    case 'manual_handoff':
      return 'good'
    case 'blocked':
    case 'failed':
    case 'rejected':
      return 'risk'
    default:
      return 'neutral'
  }
}

export function serviceLinks() {
  return [
    { label: 'Grafana', href: appRuntimeConfig.grafanaUrl, note: 'metrics and dashboards' },
    { label: 'MLflow', href: appRuntimeConfig.mlflowUrl, note: 'run tracking' },
    { label: 'Prometheus', href: appRuntimeConfig.prometheusUrl, note: 'time-series metrics' },
    { label: 'API ready', href: appRuntimeConfig.apiReadyUrl, note: 'application health' },
    { label: 'Tool service', href: appRuntimeConfig.toolReadyUrl, note: 'URL fetch + extraction' },
  ].filter((link) => Boolean(link.href))
}

export function pathFileName(path: string) {
  if (!path) {
    return ''
  }
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? ''
}
