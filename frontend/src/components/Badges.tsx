import type { BetStatus, OpportunityStatus, ValueLabel } from '@/types'

/** Colour is never the only signal: every badge carries an explicit text label. */

const VALUE_STYLES: Record<ValueLabel, { cls: string; text: string }> = {
  VERY_STRONG: { cls: 'chip-green', text: 'VERY STRONG' },
  STRONG: { cls: 'chip-green', text: 'STRONG' },
  INTERESTING: { cls: 'chip-yellow', text: 'INTERESTING' },
  WEAK: { cls: 'chip-yellow', text: 'WEAK' },
  IGNORE: { cls: 'chip-red', text: 'IGNORE' },
  UNAVAILABLE: { cls: 'chip-grey', text: 'UNAVAILABLE' },
}

export function ValueBadge({ label }: { label: ValueLabel | string | null | undefined }) {
  const style = (label && VALUE_STYLES[label as ValueLabel]) || { cls: 'chip-grey', text: label || 'UNAVAILABLE' }
  return <span className={`chip ${style.cls}`}>{style.text}</span>
}

const STATUS_STYLES: Record<OpportunityStatus, { cls: string; text: string }> = {
  VALUE_CANDIDATE: { cls: 'chip-green', text: 'VALUE CANDIDATE' },
  NO_BET: { cls: 'chip-red', text: 'NO BET' },
  ODDS_UNAVAILABLE: { cls: 'chip-grey', text: 'ODDS UNAVAILABLE' },
}

export function StatusBadge({ status }: { status: OpportunityStatus | string | null | undefined }) {
  const style = (status && STATUS_STYLES[status as OpportunityStatus]) || {
    cls: 'chip-grey',
    text: (status || 'UNKNOWN').replace(/_/g, ' '),
  }
  return <span className={`chip ${style.cls}`}>{style.text}</span>
}

const BET_STYLES: Record<BetStatus, { cls: string; text: string }> = {
  open: { cls: 'chip-blue', text: 'OPEN' },
  won: { cls: 'chip-green', text: 'WON' },
  lost: { cls: 'chip-red', text: 'LOST' },
  push: { cls: 'chip-grey', text: 'PUSH' },
}

export function BetStatusBadge({ status }: { status: BetStatus | string }) {
  const style = BET_STYLES[status as BetStatus] || { cls: 'chip-grey', text: status.toUpperCase() }
  return <span className={`chip ${style.cls}`}>{style.text}</span>
}

/** EV sign badge: green positive, yellow marginal (0..2%), red negative, grey unavailable. */
export function EvBadge({ ev }: { ev: number | null | undefined }) {
  if (ev === null || ev === undefined || !Number.isFinite(ev)) return <span className="chip chip-grey">EV UNAVAILABLE</span>
  const value = (ev * 100).toFixed(1)
  if (ev >= 0.02) return <span className="chip chip-green">EV +{value}%</span>
  if (ev >= 0) return <span className="chip chip-yellow">EV +{value}% MARGINAL</span>
  return <span className="chip chip-red">EV {value}% NEGATIVE</span>
}

/** 0..100 score chip with explicit label. */
export function ScoreChip({ value, label }: { value: number | null | undefined; label: string }) {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return <span className="chip chip-grey">{label} UNAVAILABLE</span>
  }
  const cls = value >= 70 ? 'chip-green' : value >= 45 ? 'chip-yellow' : 'chip-red'
  return (
    <span className={`chip ${cls}`}>
      {label} {Math.round(value)}
    </span>
  )
}

export function FixtureStatusBadge({ status }: { status: string }) {
  const s = status.toUpperCase()
  const cls = s === 'FINISHED' ? 'chip-grey' : s === 'LIVE' || s === 'IN_PLAY' ? 'chip-green' : 'chip-blue'
  return <span className={`chip ${cls}`}>{s.replace(/_/g, ' ')}</span>
}

export function FormChip({ result }: { result: 'W' | 'D' | 'L' | string }) {
  const cls = result === 'W' ? 'chip-green' : result === 'L' ? 'chip-red' : 'chip-grey'
  return (
    <span className={`chip ${cls} h-5 w-5 justify-center px-0`} title={result === 'W' ? 'Win' : result === 'L' ? 'Loss' : 'Draw'}>
      {result}
    </span>
  )
}
