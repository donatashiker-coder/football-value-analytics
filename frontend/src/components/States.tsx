import type { ReactNode } from 'react'

export function LoadingState({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm muted" role="status" aria-live="polite">
      <Spinner />
      <span>{label}...</span>
    </div>
  )
}

export function Spinner({ className = '' }: { className?: string }) {
  return (
    <span
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-teal-700 ${className}`}
      aria-hidden="true"
    />
  )
}

export function ErrorState({
  message,
  onRetry,
  title = 'Could not load data',
}: {
  message: string
  onRetry?: () => void
  title?: string
}) {
  return (
    <div
      role="alert"
      className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-100"
    >
      <div className="font-semibold">{title}</div>
      <div className="mt-1">{message}</div>
      {onRetry && (
        <button type="button" className="btn-secondary btn-sm mt-3" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 p-6 text-center text-sm muted dark:border-slate-700">
      <div className="font-medium text-slate-700 dark:text-slate-300">{title}</div>
      {children && <div className="mt-1">{children}</div>}
    </div>
  )
}

export function DataUnavailable({ label = 'DATA UNAVAILABLE' }: { label?: string }) {
  return <span className="chip chip-grey">{label}</span>
}

export function WarningBox({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100">
      {title && <div className="font-semibold">{title}</div>}
      <div>{children}</div>
    </div>
  )
}

export function InfoBox({ children, title }: { children: ReactNode; title?: string }) {
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-100">
      {title && <div className="font-semibold">{title}</div>}
      <div>{children}</div>
    </div>
  )
}
