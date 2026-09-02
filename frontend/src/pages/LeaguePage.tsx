import { Link, useParams } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import type { LeagueTableRow } from '@/types'
import { num, pct, signedPct, titleCase } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { StatCard } from '@/components/StatCard'
import { DataTable, type Column } from '@/components/DataTable'
import { EmptyState, ErrorState, LoadingState } from '@/components/States'
import { BarsChart } from '@/components/charts'

const AVERAGE_LABELS: Record<string, string> = {
  home_goals: 'Home goals',
  away_goals: 'Away goals',
  home_corners: 'Home corners',
  away_corners: 'Away corners',
  btts_rate: 'BTTS rate',
  over_2_5_rate: 'Over 2.5 rate',
  matches: 'Matches',
}

function fmtAverage(key: string, v: number | null): string {
  if (v === null || !Number.isFinite(v)) return 'DATA UNAVAILABLE'
  if (key.endsWith('_rate') || key.endsWith('_pct')) return pct(v)
  if (key === 'matches') return String(Math.round(v))
  return num(v)
}

export default function LeaguePage() {
  const { code } = useParams()
  const { data, loading, error, refetch } = useApi((signal) => api.league(code ?? '', signal), [code])

  if (loading) return <LoadingState label="Loading league" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!data) return <EmptyState title="League not found." />

  const columns: Column<LeagueTableRow>[] = [
    { key: 'position', header: '#', align: 'right', sortValue: (r) => r.position, render: (r) => r.position },
    {
      key: 'team',
      header: 'Team',
      sortValue: (r) => r.team,
      render: (r) => (
        <Link to={`/teams/${r.team_id}`} className="font-medium">
          {r.team}
        </Link>
      ),
    },
    { key: 'matches', header: 'P', align: 'right', sortValue: (r) => r.matches, render: (r) => r.matches },
    { key: 'points', header: 'Pts', align: 'right', sortValue: (r) => r.points, render: (r) => r.points },
    { key: 'ppg', header: 'PPG', align: 'right', sortValue: (r) => r.ppg, render: (r) => num(r.ppg) },
    { key: 'gf', header: 'GF', align: 'right', sortValue: (r) => r.goals_for, render: (r) => r.goals_for ?? '—' },
    { key: 'ga', header: 'GA', align: 'right', sortValue: (r) => r.goals_against, render: (r) => r.goals_against ?? '—' },
    { key: 'xgf', header: 'xGF', align: 'right', sortValue: (r) => r.xg_for, render: (r) => num(r.xg_for, 1) },
    { key: 'xga', header: 'xGA', align: 'right', sortValue: (r) => r.xg_against, render: (r) => num(r.xg_against, 1) },
    { key: 'cf', header: 'Corners F', align: 'right', sortValue: (r) => r.corners_for, render: (r) => num(r.corners_for, 1) },
    { key: 'ca', header: 'Corners A', align: 'right', sortValue: (r) => r.corners_against, render: (r) => num(r.corners_against, 1) },
    { key: 'btts', header: 'BTTS%', align: 'right', sortValue: (r) => r.btts_pct, render: (r) => pct(r.btts_pct, 0) },
    { key: 'o25', header: 'O2.5%', align: 'right', sortValue: (r) => r.over_2_5_pct, render: (r) => pct(r.over_2_5_pct, 0) },
    { key: 'cs', header: 'CS%', align: 'right', sortValue: (r) => r.clean_sheet_pct, render: (r) => pct(r.clean_sheet_pct, 0) },
    { key: 'elo', header: 'Elo', align: 'right', sortValue: (r) => r.elo, render: (r) => (r.elo !== null ? Math.round(r.elo) : '—') },
  ]

  const goalsChart = data.table.map((r) => ({ team: r.team, 'Goals for': r.goals_for, 'Goals against': r.goals_against }))

  return (
    <div>
      <PageHeader
        title={data.name}
        subtitle={
          <span>
            {data.code} · season {data.season_year ?? '—'} · <Link to="/leagues">All leagues</Link>
          </span>
        }
      />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        {Object.entries(data.averages ?? {}).map(([k, v]) => (
          <StatCard key={k} label={AVERAGE_LABELS[k] ?? titleCase(k)} value={fmtAverage(k, v)} tone={v === null ? 'grey' : 'default'} />
        ))}
      </div>
      <Section title="League table" className="mb-4">
        {data.table.length === 0 ? <EmptyState title="No table data — results not loaded yet." /> : <DataTable columns={columns} rows={data.table} rowKey={(r) => r.team_id} defaultSort={{ key: 'position', dir: 'asc' }} dense />}
      </Section>
      <Section title="Goals per team" className="mb-4">
        <BarsChart data={goalsChart} xKey="team" series={[{ key: 'Goals for', name: 'Goals for' }, { key: 'Goals against', name: 'Goals against', colour: '#dc2626' }]} height={300} />
      </Section>
      {data.backtests.length > 0 && (
        <Section title="Backtest results for this league">
          <div className="grid gap-4 md:grid-cols-2">
            {data.backtests.map((b) => (
              <div key={b.strategy}>
                <div className="mb-1 text-xs font-semibold uppercase muted">{titleCase(b.strategy)}</div>
                <table className="table text-xs">
                  <thead>
                    <tr>
                      <th>Key</th>
                      <th className="text-right">Bets</th>
                      <th className="text-right">Strike</th>
                      <th className="text-right">ROI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {b.league_rows.map((r) => (
                      <tr key={r.key}>
                        <td>{r.key}</td>
                        <td className="text-right num">{r.bets}</td>
                        <td className="text-right num">{pct(r.strike_rate)}</td>
                        <td className="text-right num">{signedPct(r.roi)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}
