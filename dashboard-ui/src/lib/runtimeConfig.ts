type RuntimeDashboardConfig = {
  apiBaseUrl?: string
  toolBaseUrl?: string
  grafanaUrl?: string
  mlflowUrl?: string
  prometheusUrl?: string
  apiReadyUrl?: string
  toolReadyUrl?: string
  entraAuthEnabled?: string
  sessionAbsoluteTimeoutSeconds?: string
  sessionIdleTimeoutSeconds?: string
  sessionRefreshIntervalSeconds?: string
}

type BrowserWindow = Window & {
  __JOB_APP_CONFIG__?: RuntimeDashboardConfig
}

function normalizeValue(value?: string) {
  if (!value || value.startsWith('__')) {
    return undefined
  }
  return value
}

function normalizeBoolean(value?: string) {
  const normalized = normalizeValue(value)?.trim().toLowerCase()
  if (!normalized) {
    return undefined
  }
  if (normalized === 'true') {
    return true
  }
  if (normalized === 'false') {
    return false
  }
  return undefined
}

function normalizeNumber(value?: string) {
  const normalized = normalizeValue(value)?.trim()
  if (!normalized) {
    return undefined
  }

  const parsed = Number(normalized)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined
  }

  return parsed
}

const runtimeConfig = ((window as BrowserWindow).__JOB_APP_CONFIG__ ?? {}) as RuntimeDashboardConfig

export const appRuntimeConfig = {
  apiBaseUrl: normalizeValue(runtimeConfig.apiBaseUrl) ?? import.meta.env.VITE_API_BASE_URL ?? '',
  toolBaseUrl: normalizeValue(runtimeConfig.toolBaseUrl) ?? import.meta.env.VITE_TOOL_BASE_URL ?? '/tool-api',
  grafanaUrl: normalizeValue(runtimeConfig.grafanaUrl),
  mlflowUrl: normalizeValue(runtimeConfig.mlflowUrl),
  prometheusUrl: normalizeValue(runtimeConfig.prometheusUrl),
  apiReadyUrl: normalizeValue(runtimeConfig.apiReadyUrl) ?? '/ready',
  toolReadyUrl: normalizeValue(runtimeConfig.toolReadyUrl) ?? '/tool-api/ready',
  entraAuthEnabled: normalizeBoolean(runtimeConfig.entraAuthEnabled) ?? false,
  sessionAbsoluteTimeoutSeconds: normalizeNumber(runtimeConfig.sessionAbsoluteTimeoutSeconds),
  sessionIdleTimeoutSeconds: normalizeNumber(runtimeConfig.sessionIdleTimeoutSeconds),
  sessionRefreshIntervalSeconds: normalizeNumber(runtimeConfig.sessionRefreshIntervalSeconds),
}
