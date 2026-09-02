import type { ReactNode } from 'react'

interface Props {
  label: string
  value: ReactNode
  hint?: ReactNode
  tone?: 'default' | 'green' | 'yellow' | 'red' | 'grey'
}

const TONES: Record<NonNullable<Props['tone']>, string> = {
  default: 'text-slate-900 dark:text-slate-100',
  green: 'text-emerald-700 dark:text-emerald-300',
  yellow: 'text-amber-700 dark:text-amber-300',
  red: 'text-red-700 dark:text-red-300',
  grey: 'text-slate-500 dark:text-slate-400',
}

export function StatCard({ label, value, hint, tone = 'default' }: Props) {
  return (
    <div className="card flex flex-col gap-1">
      <div className="text-xs font-medium uppercase tracking-wide muted">{label}</div>
      <div className={`text-2xl font-semibold num ${TONES[tone]}`}>{value}</div>
      {hint && <div className="text-xs muted">{hint}</div>}
    </div>
  )
}

/** Choose a tone from a signed fraction (ROI, EV, CLV...). */
export function toneForSigned(v: number | null | undefined): Props['tone'] {
  if (v === null || v === undefined || !Number.isFinite(v)) return 'grey'
  if (v > 0.005) return 'green'
  if (v < -0.005) return 'red'
  return 'yellow'
}
