import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  Area,
  AreaChart,
} from 'recharts'
import type { CalibrationBin, EquityPoint, OddsHistoryPoint } from '@/types'
import { shortDate } from '@/utils/format'

export const CHART_COLOURS = ['#0f766e', '#2563eb', '#d97706', '#dc2626', '#7c3aed', '#64748b', '#0891b2', '#be185d']

const axisStyle = { fontSize: 11, fill: '#64748b' }
const gridStroke = '#e2e8f0'

export interface Series {
  key: string
  name: string
  colour?: string
  dashed?: boolean
}

interface TrendProps {
  data: Record<string, number | string | null>[]
  series: Series[]
  xKey: string
  height?: number
  yDomain?: [number | 'auto', number | 'auto']
  yFormatter?: (v: number) => string
}

/** Generic multi-series line chart used for goals / xG / corners trends. Nulls create gaps. */
export function TrendChart({ data, series, xKey, height = 220, yDomain, yFormatter }: TrendProps) {
  if (data.length === 0) return <ChartEmpty />
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
        <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
        <XAxis dataKey={xKey} tick={axisStyle} />
        <YAxis tick={axisStyle} domain={yDomain} tickFormatter={yFormatter} />
        <Tooltip contentStyle={{ fontSize: 12 }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name}
            stroke={s.colour ?? CHART_COLOURS[i % CHART_COLOURS.length]}
            strokeDasharray={s.dashed ? '4 3' : undefined}
            dot={{ r: 2 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

interface BarProps {
  data: Record<string, number | string | null>[]
  series: Series[]
  xKey: string
  height?: number
  yFormatter?: (v: number) => string
  layout?: 'horizontal' | 'vertical'
}

export function BarsChart({ data, series, xKey, height = 240, yFormatter, layout = 'horizontal' }: BarProps) {
  if (data.length === 0) return <ChartEmpty />
  const vertical = layout === 'vertical'
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} layout={layout} margin={{ top: 8, right: 12, left: vertical ? 40 : -12, bottom: 0 }}>
        <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
        {vertical ? (
          <>
            <XAxis type="number" tick={axisStyle} tickFormatter={yFormatter} />
            <YAxis type="category" dataKey={xKey} tick={axisStyle} width={110} interval={0} />
          </>
        ) : (
          <>
            <XAxis dataKey={xKey} tick={axisStyle} interval={0} angle={data.length > 12 ? -45 : 0} textAnchor={data.length > 12 ? 'end' : 'middle'} height={data.length > 12 ? 70 : 30} />
            <YAxis tick={axisStyle} tickFormatter={yFormatter} />
          </>
        )}
        <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v: number) => (yFormatter ? yFormatter(v) : v)} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.colour ?? CHART_COLOURS[i % CHART_COLOURS.length]} isAnimationActive={false} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

export function EquityChart({ data, height = 240 }: { data: { t: string; equity: number }[]; height?: number }) {
  if (data.length === 0) return <ChartEmpty />
  const rows = data.map((p, i) => ({ i, t: shortDate(p.t), equity: p.equity }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 8, right: 12, left: -4, bottom: 0 }}>
        <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
        <XAxis dataKey="t" tick={axisStyle} minTickGap={30} />
        <YAxis tick={axisStyle} domain={['auto', 'auto']} />
        <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v: number) => v.toFixed(2)} />
        <Area type="monotone" dataKey="equity" name="Equity" stroke="#0f766e" fill="#0f766e" fillOpacity={0.12} isAnimationActive={false} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function DrawdownChart({ data, height = 160 }: { data: EquityPoint[]; height?: number }) {
  if (data.length === 0) return <ChartEmpty />
  const rows = data.map((p) => ({ t: shortDate(p.t), drawdown: -Math.abs(p.drawdown) }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 8, right: 12, left: -4, bottom: 0 }}>
        <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
        <XAxis dataKey="t" tick={axisStyle} minTickGap={30} />
        <YAxis tick={axisStyle} />
        <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v: number) => v.toFixed(2)} />
        <Area type="monotone" dataKey="drawdown" name="Drawdown" stroke="#dc2626" fill="#dc2626" fillOpacity={0.15} isAnimationActive={false} dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

/** Reliability diagram: mean predicted vs observed rate per bin, with the diagonal for perfect calibration. */
export function CalibrationChart({ bins, height = 260 }: { bins: CalibrationBin[]; height?: number }) {
  const points = bins
    .filter((b) => b.count > 0 && b.mean_predicted !== null && b.observed_rate !== null)
    .map((b) => ({ predicted: b.mean_predicted as number, observed: b.observed_rate as number, count: b.count, range: `${(b.lower * 100).toFixed(0)}–${(b.upper * 100).toFixed(0)}%` }))
  if (points.length === 0) return <ChartEmpty label="No calibration bins with data." />
  const diagonal = [
    { predicted: 0, observed: 0 },
    { predicted: 1, observed: 1 },
  ]
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 8, right: 12, left: -4, bottom: 8 }}>
        <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
        <XAxis type="number" dataKey="predicted" domain={[0, 1]} tick={axisStyle} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} name="Mean predicted" />
        <YAxis type="number" dataKey="observed" domain={[0, 1]} tick={axisStyle} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} name="Observed" />
        <Tooltip
          contentStyle={{ fontSize: 12 }}
          formatter={(v: number, name: string) => [`${(v * 100).toFixed(1)}%`, name]}
          labelFormatter={() => ''}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Scatter name="Perfect calibration" data={diagonal} line={{ stroke: '#94a3b8', strokeDasharray: '4 3' }} fill="transparent" shape={() => <g />} isAnimationActive={false} legendType="line" />
        <Scatter name="Observed rate (per bin)" data={points} fill="#0f766e" line={{ stroke: '#0f766e' }} isAnimationActive={false} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}

/** Odds history: one line per bookmaker over time. */
export function OddsHistoryChart({ history, height = 240 }: { history: OddsHistoryPoint[]; height?: number }) {
  if (history.length === 0) return <ChartEmpty label="No odds history recorded." />
  const bookmakers = Array.from(new Set(history.map((h) => h.bookmaker)))
  const byTime = new Map<string, Record<string, number | string | null>>()
  for (const h of history) {
    const key = h.t
    const row = byTime.get(key) ?? { t: key, label: new Date(h.t.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(h.t) ? h.t : `${h.t}Z`).toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) }
    row[h.bookmaker] = h.odds
    byTime.set(key, row)
  }
  const rows = Array.from(byTime.values()).sort((a, b) => String(a.t).localeCompare(String(b.t)))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={rows} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
        <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={axisStyle} minTickGap={40} />
        <YAxis tick={axisStyle} domain={['auto', 'auto']} tickFormatter={(v: number) => v.toFixed(2)} />
        <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v: number) => v.toFixed(2)} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {bookmakers.map((b, i) => (
          <Line key={b} type="stepAfter" dataKey={b} name={b} stroke={CHART_COLOURS[i % CHART_COLOURS.length]} dot={{ r: 2 }} connectNulls isAnimationActive={false} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}

/** Horizontal grouped bars: model vs market probability per market. */
export function ModelVsMarketChart({ rows, height }: { rows: { name: string; model: number | null; market: number | null }[]; height?: number }) {
  if (rows.length === 0) return <ChartEmpty />
  const data = rows.map((r) => ({ name: r.name, Model: r.model !== null ? +(r.model * 100).toFixed(1) : null, Market: r.market !== null ? +(r.market * 100).toFixed(1) : null }))
  const h = height ?? Math.max(160, rows.length * 28 + 40)
  return (
    <ResponsiveContainer width="100%" height={h}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 60, bottom: 0 }}>
        <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
        <XAxis type="number" domain={[0, 100]} tick={axisStyle} tickFormatter={(v: number) => `${v}%`} />
        <YAxis type="category" dataKey="name" tick={axisStyle} width={120} interval={0} />
        <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v: number) => `${v.toFixed(1)}%`} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <ReferenceLine x={50} stroke="#cbd5e1" />
        <Bar dataKey="Model" fill="#0f766e" isAnimationActive={false} />
        <Bar dataKey="Market" fill="#94a3b8" isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ChartEmpty({ label = 'No data to chart.' }: { label?: string }) {
  return <div className="flex h-32 items-center justify-center rounded border border-dashed border-slate-300 text-xs muted dark:border-slate-700">{label}</div>
}
