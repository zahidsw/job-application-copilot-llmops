const STORAGE_KEY_PREFIX = 'job-application-copilot.session'

export const SESSION_STARTED_AT_KEY = `${STORAGE_KEY_PREFIX}.startedAt`
export const LAST_ACTIVITY_AT_KEY = `${STORAGE_KEY_PREFIX}.lastActivityAt`
export const FORCED_LOGOUT_AT_KEY = `${STORAGE_KEY_PREFIX}.forcedLogoutAt`

export function readTimestamp(key: string) {
  try {
    const storedValue = window.localStorage.getItem(key)
    if (!storedValue) {
      return undefined
    }

    const parsedValue = Number(storedValue)
    if (!Number.isFinite(parsedValue) || parsedValue <= 0) {
      return undefined
    }

    return parsedValue
  } catch {
    return undefined
  }
}

function writeTimestamp(key: string, value: number) {
  try {
    window.localStorage.setItem(key, String(value))
  } catch {
    // Ignore storage write failures and fall back to in-memory behavior.
  }
}

export function clearSessionTracking() {
  try {
    window.localStorage.removeItem(SESSION_STARTED_AT_KEY)
    window.localStorage.removeItem(LAST_ACTIVITY_AT_KEY)
  } catch {
    // Ignore storage cleanup failures during logout.
  }
}

export function markSessionActivity() {
  const now = Date.now()
  if (!readTimestamp(SESSION_STARTED_AT_KEY)) {
    writeTimestamp(SESSION_STARTED_AT_KEY, now)
  }
  writeTimestamp(LAST_ACTIVITY_AT_KEY, now)
}

function currentLocationUrl() {
  return `${window.location.origin}${window.location.pathname}${window.location.search}${window.location.hash}`
}

export function buildLogoutUrl(postLogoutRedirectUrl = currentLocationUrl()) {
  return `/.auth/logout?post_logout_redirect_uri=${encodeURIComponent(postLogoutRedirectUrl)}`
}

export function triggerLogout(postLogoutRedirectUrl = currentLocationUrl()) {
  const forcedLogoutAt = Date.now()
  clearSessionTracking()
  writeTimestamp(FORCED_LOGOUT_AT_KEY, forcedLogoutAt)
  window.location.assign(buildLogoutUrl(postLogoutRedirectUrl))
}
