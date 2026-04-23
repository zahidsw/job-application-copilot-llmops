import { useEffect, useEffectEvent, useRef } from 'react'
import {
  buildLogoutUrl,
  FORCED_LOGOUT_AT_KEY,
  LAST_ACTIVITY_AT_KEY,
  SESSION_STARTED_AT_KEY,
  readTimestamp,
  triggerLogout,
} from '../lib/auth'
import { appRuntimeConfig } from '../lib/runtimeConfig'

const SESSION_CHECK_INTERVAL_MS = 15_000

function writeTimestamp(key: string, value: number) {
  try {
    window.localStorage.setItem(key, String(value))
  } catch {
    // Ignore storage write failures and fall back to in-memory behavior.
  }
}

export function SessionGuard() {
  const refreshInFlightRef = useRef(false)
  const absoluteTimeoutMs = (appRuntimeConfig.sessionAbsoluteTimeoutSeconds ?? 0) * 1000
  const idleTimeoutMs = (appRuntimeConfig.sessionIdleTimeoutSeconds ?? 0) * 1000
  const refreshIntervalMs = (appRuntimeConfig.sessionRefreshIntervalSeconds ?? 0) * 1000
  const sessionGuardEnabled =
    appRuntimeConfig.entraAuthEnabled &&
    absoluteTimeoutMs > 0 &&
    idleTimeoutMs > 0 &&
    refreshIntervalMs > 0

  const forceReauthentication = useEffectEvent(() => {
    triggerLogout()
  })

  const ensureSessionWindow = useEffectEvent(() => {
    const now = Date.now()
    const startedAt = readTimestamp(SESSION_STARTED_AT_KEY) ?? now
    const lastActivityAt = readTimestamp(LAST_ACTIVITY_AT_KEY) ?? now

    writeTimestamp(SESSION_STARTED_AT_KEY, startedAt)
    writeTimestamp(LAST_ACTIVITY_AT_KEY, lastActivityAt)

    return { startedAt, lastActivityAt, now }
  })

  const registerActivity = useEffectEvent(() => {
    if (!sessionGuardEnabled) {
      return
    }

    const now = Date.now()
    if (!readTimestamp(SESSION_STARTED_AT_KEY)) {
      writeTimestamp(SESSION_STARTED_AT_KEY, now)
    }
    writeTimestamp(LAST_ACTIVITY_AT_KEY, now)
  })

  const evaluateSession = useEffectEvent(() => {
    if (!sessionGuardEnabled) {
      return
    }

    const { startedAt, lastActivityAt, now } = ensureSessionWindow()
    if (now - startedAt >= absoluteTimeoutMs) {
      forceReauthentication()
      return
    }

    if (now - lastActivityAt >= idleTimeoutMs) {
      forceReauthentication()
    }
  })

  const refreshSession = useEffectEvent(async () => {
    if (!sessionGuardEnabled || refreshInFlightRef.current) {
      return
    }

    if (document.visibilityState !== 'visible' || !document.hasFocus()) {
      return
    }

    const { startedAt, lastActivityAt, now } = ensureSessionWindow()
    if (now - startedAt >= absoluteTimeoutMs || now - lastActivityAt >= idleTimeoutMs) {
      evaluateSession()
      return
    }

    refreshInFlightRef.current = true

    try {
      const response = await fetch('/.auth/refresh', {
        method: 'GET',
        credentials: 'same-origin',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
        },
      })

      if (response.status === 401 || response.status === 403) {
        evaluateSession()
      }
    } catch {
      // Ignore transient refresh failures and retry on the next interval.
    } finally {
      refreshInFlightRef.current = false
    }
  })

  useEffect(() => {
    if (!sessionGuardEnabled) {
      return undefined
    }

    registerActivity()
    evaluateSession()

    const activityEvents: Array<keyof WindowEventMap> = ['pointerdown', 'keydown', 'mousemove', 'scroll', 'focus']
    const onStorage = (event: StorageEvent) => {
      if (event.key === FORCED_LOGOUT_AT_KEY && event.newValue) {
        window.location.assign(buildLogoutUrl(triggeredLogoutLocation()))
      }
    }

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        registerActivity()
        void refreshSession()
      }
    }

    const onActivity = () => {
      registerActivity()
    }

    for (const eventName of activityEvents) {
      window.addEventListener(eventName, onActivity, { passive: true })
    }
    window.addEventListener('storage', onStorage)
    document.addEventListener('visibilitychange', onVisibilityChange)

    const evaluationTimer = window.setInterval(() => {
      evaluateSession()
    }, SESSION_CHECK_INTERVAL_MS)

    const refreshTimer = window.setInterval(() => {
      void refreshSession()
    }, refreshIntervalMs)

    return () => {
      for (const eventName of activityEvents) {
        window.removeEventListener(eventName, onActivity)
      }
      window.removeEventListener('storage', onStorage)
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.clearInterval(evaluationTimer)
      window.clearInterval(refreshTimer)
    }
  }, [
    absoluteTimeoutMs,
    idleTimeoutMs,
    refreshIntervalMs,
    sessionGuardEnabled,
  ])

  return null
}

function triggeredLogoutLocation() {
  return window.location.href
}
