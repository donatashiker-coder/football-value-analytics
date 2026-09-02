export const UNAVAILABLE = 'DATA UNAVAILABLE'

export function isNum(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

/** Probability fraction (0..1) -> "54.3%" */
export function pct(v: number | null | undefined, digits = 1): string {
  if (!isNum(v)) return UNAVAILABLE
  return `${(v * 100).toFixed(digits)}%`
}

/** Fraction -> "+4.2%" / "-1.3%" */
export function signedPct(v: number | null | undefined, digits = 1): string {
  if (!isNum(v)) return UNAVAILABLE
  const value = v * 100
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(digits)}%`
}

/** Value already in percentage points (0..100) -> "54.3%" */
export function pctPoints(v: number | null | undefined, digits = 1): string {
  if (!isNum(v)) return UNAVAILABLE
  return `${v.toFixed(digits)}%`
}

/** Decimal odds -> "2.05" */
export function odds(v: number | null | undefined): string {
  if (!isNum(v)) return UNAVAILABLE
  return v.toFixed(2)
}

export function num(v: number | null | undefined, digits = 2): string {
  if (!isNum(v)) return UNAVAILABLE
  return v.toFixed(digits)
}

export function signedNum(v: number | null | undefined, digits = 2): string {
  if (!isNum(v)) return UNAVAILABLE
  return `${v > 0 ? '+' : ''}${v.toFixed(digits)}`
}

export function score(v: number | null | undefined): string {
  if (!isNum(v)) return UNAVAILABLE
  return Math.round(v).toString()
}

export function money(v: number | null | undefined, currency = ''): string {
  if (!isNum(v)) return UNAVAILABLE
  const s = v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return currency ? `${s} ${currency}` : s
}

export function signedMoney(v: number | null | undefined): string {
  if (!isNum(v)) return UNAVAILABLE
  return `${v > 0 ? '+' : ''}${money(v)}`
}

export function int(v: number | null | undefined): string {
  if (!isNum(v)) return UNAVAILABLE
  return Math.round(v).toLocaleString()
}

const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null
  // Backend timestamps are UTC; if there is no timezone designator, treat as UTC.
  const hasTz = /[zZ]|[+-]\d{2}:?\d{2}$/.test(value)
  const d = new Date(hasTz ? value : `${value}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

export function localDateTime(value: string | null | undefined): string {
  const d = parseDate(value)
  if (!d) return UNAVAILABLE
  return new Intl.DateTimeFormat(undefined, {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: userTz,
  }).format(d)
}

export function localDate(value: string | null | undefined): string {
  const d = parseDate(value)
  if (!d) return UNAVAILABLE
  return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', year: 'numeric', timeZone: userTz }).format(d)
}

export function localTime(value: string | null | undefined): string {
  const d = parseDate(value)
  if (!d) return UNAVAILABLE
  return new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', timeZone: userTz }).format(d)
}

export function shortDate(value: string | null | undefined): string {
  const d = parseDate(value)
  if (!d) return '—'
  return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', timeZone: userTz }).format(d)
}

export function ageHours(value: string | null | undefined): number | null {
  const d = parseDate(value)
  if (!d) return null
  return (Date.now() - d.getTime()) / 3_600_000
}

export function hours(v: number | null | undefined): string {
  if (!isNum(v)) return UNAVAILABLE
  if (v < 1) return `${Math.round(v * 60)}m`
  if (v < 48) return `${v.toFixed(1)}h`
  return `${(v / 24).toFixed(1)}d`
}

export function todayIso(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function titleCase(s: string | null | undefined): string {
  if (!s) return ''
  return s
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export function timezoneLabel(): string {
  return userTz
}
