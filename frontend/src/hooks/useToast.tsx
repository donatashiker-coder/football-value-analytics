import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

export type ToastKind = 'success' | 'error' | 'info' | 'warning'

export interface ToastItem {
  id: number
  kind: ToastKind
  title: string
  message?: string
}

interface ToastContextValue {
  toasts: ToastItem[]
  push: (kind: ToastKind, title: string, message?: string) => void
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastContextValue>({
  toasts: [],
  push: () => undefined,
  dismiss: () => undefined,
})

let counter = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback(
    (kind: ToastKind, title: string, message?: string) => {
      const id = ++counter
      setToasts((prev) => [...prev, { id, kind, title, message }])
      window.setTimeout(() => dismiss(id), kind === 'error' ? 10000 : 6000)
    },
    [dismiss],
  )

  const value = useMemo(() => ({ toasts, push, dismiss }), [toasts, push, dismiss])
  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
}

export function useToast() {
  return useContext(ToastContext)
}
