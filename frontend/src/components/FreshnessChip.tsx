import { ageHours, hours } from '@/utils/format'

interface Props {
  /** ISO timestamp of the odds/data record. */
  recordedAt?: string | null
  /** Pre-computed age in hours (takes precedence over recordedAt). */
  hoursOld?: number | null
  /** Age above which the chip becomes a warning. */
  staleAfterHours?: number
  label?: string
}

/** "Odds 4.2h old" chip; yellow STALE warning when older than the threshold, grey when unknown. */
export function FreshnessChip({ recordedAt, hoursOld, staleAfterHours = 4, label = 'Odds' }: Props) {
  const age = typeof hoursOld === 'number' ? hoursOld : ageHours(recordedAt)
  if (age === null || !Number.isFinite(age)) {
    return <span className="chip chip-grey">{label.toUpperCase()} AGE UNKNOWN</span>
  }
  const stale = age > staleAfterHours
  return (
    <span className={`chip ${stale ? 'chip-yellow' : 'chip-grey'}`} title={`${label} recorded ${hours(age)} ago`}>
      {stale ? 'STALE ' : ''}
      {label} {hours(age)} old
    </span>
  )
}
