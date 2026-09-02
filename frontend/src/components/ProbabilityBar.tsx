import { pct } from '@/utils/format'

interface Props {
  model: number | null | undefined
  market: number | null | undefined
  compact?: boolean
}

/** Side-by-side horizontal bars: model probability vs market (implied) probability. */
export function ProbabilityBar({ model, market, compact = false }: Props) {
  const m = typeof model === 'number' ? Math.max(0, Math.min(1, model)) : null
  const k = typeof market === 'number' ? Math.max(0, Math.min(1, market)) : null
  return (
    <div className={`flex flex-col gap-0.5 ${compact ? 'w-32' : 'w-full'}`} aria-label="Model vs market probability">
      <Row label="Model" value={m} colour="bg-teal-600" />
      <Row label="Market" value={k} colour="bg-slate-400" />
    </div>
  )
}

function Row({ label, value, colour }: { label: string; value: number | null; colour: string }) {
  return (
    <div className="flex items-center gap-1 text-[11px]">
      <span className="w-11 shrink-0 muted">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded bg-slate-200 dark:bg-slate-700">
        {value !== null && <div className={`h-full ${colour}`} style={{ width: `${value * 100}%` }} />}
      </div>
      <span className="w-12 shrink-0 text-right num">{value === null ? 'N/A' : pct(value, 1)}</span>
    </div>
  )
}
