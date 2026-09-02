import { Link } from 'react-router-dom'
import type { ScannerRow } from '@/types'
import { useApi } from '@/hooks/useApi'
import { api } from '@/services/api'
import { localDateTime, num, pct, score } from '@/utils/format'
import { EmptyState, ErrorState, LoadingState } from './States'
import { Section } from './PageHeader'

type Kind = 'high_scoring' | 'low_scoring' | 'high_corners'

interface Props {
  kind: Kind
  day?: string
  days?: number
}

const TITLES: Record<Kind, string> = {
  high_scoring: 'Scanner: expected goals vs league average (high scoring)',
  low_scoring: 'Scanner: expected goals vs league average (low scoring)',
  high_corners: 'Scanner: expected corners vs league average (high corners)',
}

/** Ratio bar: 1.0 = league average. Text label always accompanies the bar. */
function RatioBar({ ratio, invert = false }: { ratio: number | null; invert?: boolean }) {
  if (ratio === null || !Number.isFinite(ratio)) return <span className="chip chip-grey">DATA UNAVAILABLE</span>
  const width = Math.max(4, Math.min(100, (ratio / 1.6) * 100))
  const good = invert ? ratio < 0.9 : ratio > 1.1
  const marginal = invert ? ratio < 1 : ratio > 1
  const cls = good ? 'bg-emerald-500' : marginal ? 'bg-amber-400' : 'bg-slate-400'
  const label = good ? (invert ? 'WELL BELOW AVG' : 'WELL ABOVE AVG') : marginal ? (invert ? 'BELOW AVG' : 'ABOVE AVG') : 'NEAR/AGAINST AVG'
  return (
    <div className="flex min-w-[9rem] items-center gap-2">
      <div className="relative h-2 flex-1 rounded bg-slate-200 dark:bg-slate-700">
        <div className={`h-full rounded ${cls}`} style={{ width: `${width}%` }} />
        <div className="absolute top-[-3px] h-[14px] w-px bg-slate-600 dark:bg-slate-300" style={{ left: `${(1 / 1.6) * 100}%` }} title="League average" />
      </div>
      <span className="w-24 text-[10px] font-semibold uppercase">
        {num(ratio, 2)}x · {label}
      </span>
    </div>
  )
}

export function ScannerPanel({ kind, day, days }: Props) {
  const { data, loading, error, refetch } = useApi((signal) => api.scannersExpected({ day, days }, signal), [day, days])
  const rows: ScannerRow[] = data ? data[kind] ?? [] : []
  const cornersMode = kind === 'high_corners'
  const invert = kind === 'low_scoring'

  return (
    <Section title={TITLES[kind]}>
      {loading && <LoadingState label="Loading scanner" />}
      {error && !loading && <ErrorState message={error} onRetry={refetch} />}
      {!loading && !error && rows.length === 0 && <EmptyState title="No fixtures matched the scanner for this period." />}
      {!loading && !error && rows.length > 0 && (
        <div className="table-wrap">
          <table className="table text-xs">
            <thead>
              <tr>
                <th>Match</th>
                <th>Kickoff</th>
                <th className="text-right">{cornersMode ? 'Exp. corners' : 'Exp. goals'}</th>
                <th className="text-right">League avg</th>
                <th>Ratio vs league</th>
                <th className="text-right">{cornersMode ? 'P(corners > 9.5)' : 'P(over 2.5)'}</th>
                <th className="text-right">Data Q</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.fixture_id}>
                  <td>
                    <Link to={`/matches/${r.fixture_id}`}>
                      {r.home_team} vs {r.away_team}
                    </Link>
                    <div className="muted">{r.competition}</div>
                  </td>
                  <td className="whitespace-nowrap">{localDateTime(r.kickoff_utc)}</td>
                  <td className="text-right num">{num(cornersMode ? r.expected_corners : r.expected_goals)}</td>
                  <td className="text-right num">{num(cornersMode ? r.league_corners : r.league_goals)}</td>
                  <td>
                    <RatioBar ratio={cornersMode ? r.corners_ratio : r.goals_ratio} invert={invert} />
                  </td>
                  <td className="text-right num">{pct(cornersMode ? r.p_corners_over_9_5 : r.p_over_2_5)}</td>
                  <td className="text-right num">{score(r.data_quality)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  )
}
