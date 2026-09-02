import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '@/services/api'

export interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
  errorStatus: number | null
  refetch: () => void
}

/**
 * Generic data-fetching hook. `fetcher` receives an AbortSignal and must return a promise.
 * Re-runs whenever `deps` change. Aborts in-flight requests on unmount / dep change.
 */
export function useApi<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: ReadonlyArray<unknown>,
  options: { enabled?: boolean } = {},
): ApiState<T> {
  const enabled = options.enabled ?? true
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState<boolean>(enabled)
  const [error, setError] = useState<string | null>(null)
  const [errorStatus, setErrorStatus] = useState<number | null>(null)
  const [tick, setTick] = useState(0)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    const controller = new AbortController()
    let active = true
    setLoading(true)
    setError(null)
    setErrorStatus(null)
    fetcherRef
      .current(controller.signal)
      .then((result) => {
        if (!active) return
        setData(result)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (!active) return
        if (err instanceof ApiError && err.message === 'Request cancelled') return
        setError(err instanceof Error ? err.message : 'Unknown error')
        setErrorStatus(err instanceof ApiError ? err.status : null)
        setLoading(false)
      })
    return () => {
      active = false
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, tick, ...deps])

  const refetch = useCallback(() => setTick((t) => t + 1), [])

  return { data, loading, error, errorStatus, refetch }
}

/** Small helper for imperative async actions (POST etc.) with loading/error state. */
export function useAction<Args extends unknown[], R>(action: (...args: Args) => Promise<R>) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<R | null>(null)

  const run = useCallback(
    async (...args: Args): Promise<R | null> => {
      setLoading(true)
      setError(null)
      try {
        const r = await action(...args)
        setResult(r)
        return r
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
        return null
      } finally {
        setLoading(false)
      }
    },
    [action],
  )

  const reset = useCallback(() => {
    setError(null)
    setResult(null)
  }, [])

  return { run, loading, error, result, reset }
}
