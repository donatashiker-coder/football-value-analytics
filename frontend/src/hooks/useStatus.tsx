import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '@/services/api'
import type { Status } from '@/types'

interface StatusContextValue {
  status: Status | null
  loading: boolean
  error: string | null
  isDemo: boolean
  refresh: () => void
}

const StatusContext = createContext<StatusContextValue>({
  status: null,
  loading: true,
  error: null,
  isDemo: false,
  refresh: () => undefined,
})

export function StatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    setLoading(true)
    api
      .status(controller.signal)
      .then((s) => {
        if (!active) return
        setStatus(s)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!active) return
        setError(err instanceof Error ? err.message : 'Status unavailable')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
      controller.abort()
    }
  }, [tick])

  const refresh = useCallback(() => setTick((t) => t + 1), [])

  const value = useMemo<StatusContextValue>(
    () => ({ status, loading, error, isDemo: Boolean(status?.demo), refresh }),
    [status, loading, error, refresh],
  )

  return <StatusContext.Provider value={value}>{children}</StatusContext.Provider>
}

export function useStatus(): StatusContextValue {
  return useContext(StatusContext)
}
