import { useStatus } from '@/hooks/useStatus'

export const DEMO_TEXT = 'DEMO DATA — synthetic fixtures and odds, clearly labelled, never mixed with production data'

/** Persistent yellow banner shown whenever the backend reports demo mode, or when a page passes `force`. */
export function DemoBanner({ force = false }: { force?: boolean }) {
  const { isDemo } = useStatus()
  if (!isDemo && !force) return null
  return (
    <div
      role="status"
      className="border-b border-amber-300 bg-amber-100 px-4 py-1.5 text-center text-xs font-semibold uppercase tracking-wide text-amber-900 dark:border-amber-700 dark:bg-amber-900/60 dark:text-amber-100 md:px-6"
    >
      {DEMO_TEXT}
    </div>
  )
}

/** Inline demo badge for individual records (e.g. an opportunity flagged is_demo when status is not demo). */
export function DemoBadge({ show }: { show: boolean | undefined }) {
  if (!show) return null
  return <span className="chip chip-yellow">DEMO</span>
}
