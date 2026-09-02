import { useToast, type ToastKind } from '@/hooks/useToast'

const STYLES: Record<ToastKind, string> = {
  success: 'border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100',
  error: 'border-red-300 bg-red-50 text-red-900 dark:border-red-800 dark:bg-red-950 dark:text-red-100',
  info: 'border-sky-300 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950 dark:text-sky-100',
  warning: 'border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100',
}

export function ToastViewport() {
  const { toasts, dismiss } = useToast()
  if (toasts.length === 0) return null
  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} role="status" className={`rounded-md border p-3 text-sm shadow-lg ${STYLES[t.kind]}`}>
          <div className="flex items-start justify-between gap-2">
            <div className="font-semibold">{t.title}</div>
            <button type="button" className="text-xs underline" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              Dismiss
            </button>
          </div>
          {t.message && <div className="mt-1 whitespace-pre-wrap break-words text-xs">{t.message}</div>}
        </div>
      ))}
    </div>
  )
}
