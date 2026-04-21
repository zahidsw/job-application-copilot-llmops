type RuntimeDashboardConfig = {
  apiBaseUrl?: string
  toolBaseUrl?: string
  grafanaUrl?: string
  mlflowUrl?: string
  prometheusUrl?: string
  apiReadyUrl?: string
  toolReadyUrl?: string
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

const runtimeConfig = ((window as BrowserWindow).__JOB_APP_CONFIG__ ?? {}) as RuntimeDashboardConfig

export const appRuntimeConfig = {
  apiBaseUrl: normalizeValue(runtimeConfig.apiBaseUrl) ?? import.meta.env.VITE_API_BASE_URL ?? '',
  toolBaseUrl: normalizeValue(runtimeConfig.toolBaseUrl) ?? import.meta.env.VITE_TOOL_BASE_URL ?? '/tool-api',
  grafanaUrl: normalizeValue(runtimeConfig.grafanaUrl),
  mlflowUrl: normalizeValue(runtimeConfig.mlflowUrl),
  prometheusUrl: normalizeValue(runtimeConfig.prometheusUrl),
  apiReadyUrl: normalizeValue(runtimeConfig.apiReadyUrl) ?? '/ready',
  toolReadyUrl: normalizeValue(runtimeConfig.toolReadyUrl) ?? '/tool-api/ready',
}
