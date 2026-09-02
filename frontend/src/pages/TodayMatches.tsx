import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import type { FixtureSummary } from '@/types'
import { localDateTime, num, odds, signedPct, todayIso } from '@/utils/format'
import { PageHeader } from '@/components/PageHeader'
import { DataTable, type Column } from '@/components/DataTable'
import { EmptyState, ErrorState, LoadingState } from '@/components/States'
import { FixtureStatusBadge, ScoreChip, StatusBadge } from '@/components/Badges'
import { DemoBadge } from '@/components/DemoBanner'

export default function TodayMatches() {
  const [day, setDay] = useState(todayIso())
  const [days, setDays] = useState(2)
  const [competition, setCompetition] = useState('')
  const leagues = useApi((signal) => api.leagues(signal), [])
  const { data, loading, error, refetch } = useApi((signal) => api.fixturesToday({ day, days, competition: competition || undefined }, signal), [day, days, competition])

  const columns: Column<FixtureSummary>[] = [
    {
      key: 'kickoff',
      header: 'Kickoff',
      sortValue: (f) => f.kickoff_utc,
      render: (f) => <span className="whitespace-nowrap text-xs">{localDateTime(f.kickoff_utc)}</span>,
    },
    {
      key: 'match',
      header: 'Match',
      sortValue: (f) => f.home_team,
      render: (f) => (
        <div>
          <Link to={`/matches/${f.fixture_id}`} className="font-medium">
            {f.home_team} vs {f.away_team}
          </Link>
          <div className="text-xs muted">
            {f.competition} <DemoBadge show={f.is_demo} />
          </div>
        </div>
      ),
    },
    { key: 'status', header: 'Status', sortValue: (f) => f.status, render: (f) => <FixtureStatusBadge status={f.status} /> },
    {
      key: 'result',
      header: 'Result',
      render: (f) =>
        f.result && f.result.home_goals !== null ? (
          <span className="num">
            {f.result.home_goals}–{f.result.away_goals}
            {f.result.home_corners !== null && <span className="muted"> (c {f.result.home_corners}–{f.result.away_corners})</span>}
          </span>
        ) : (
          <span className="muted">—</span>
        ),
    },
    {
      key: 'xg',
      header: 'Exp. goals',
      align: 'right',
      sortValue: (f) => (f.expected_goals ? (f.expected_goals.home ?? 0) + (f.expected_goals.away ?? 0) : null),
      render: (f) =>
        f.expected_goals ? (
          <span>
            {num(f.expected_goals.home)} – {num(f.expected_goals.away)}
          </span>
        ) : (
          <span className="chip chip-grey">N/A</span>
        ),
    },
    {
      key: 'xc',
      header: 'Exp. corners',
      align: 'right',
      sortValue: (f) => (f.expected_corners ? (f.expected_corners.home ?? 0) + (f.expected_corners.away ?? 0) : null),
      render: (f) =>
        f.expected_corners ? (
          <span>
            {num(f.expected_corners.home, 1)} – {num(f.expected_corners.away, 1)}
          </span>
        ) : (
          <span className="chip chip-grey">N/A</span>
        ),
    },
    { key: 'dq', header: 'Data Q', align: 'right', sortValue: (f) => f.data_quality, render: (f) => <ScoreChip label="DQ" value={f.data_quality} /> },
    { key: 'analysed', header: 'Analysed', sortValue: (f) => (f.analysed ? 1 : 0), render: (f) => (f.analysed ? <span className="chip chip-green">YES</span> : <span className="chip chip-grey">NOT ANALYSED</span>) },
    { key: 'vc', header: 'Value cand.', align: 'right', sortValue: (f) => f.value_candidates, render: (f) => `${f.value_candidates} / ${f.markets_evaluated}` },
    {
      key: 'best',
      header: 'Best opportunity',
      sortValue: (f) => f.best_opportunity?.expected_value ?? null,
      render: (f) =>
        f.best_opportunity ? (
          <div className="text-xs">
            <div>
              {f.best_opportunity.market} {f.best_opportunity.selection} @ {odds(f.best_opportunity.best_odds)}
            </div>
            <div className="flex items-center gap-1">
              <StatusBadge status={f.best_opportunity.status} />
              <span className="num">EV {signedPct(f.best_opportunity.expected_value)}</span>
            </div>
          </div>
        ) : (
          <span className="chip chip-grey">NONE</span>
        ),
    },
    { key: 'link', header: '', render: (f) => <Link to={`/matches/${f.fixture_id}`} className="btn-secondary btn-sm">Open</Link> },
  ]

  return (
    <div>
      <PageHeader title="Today's Matches" subtitle={data ? `${data.count} fixtures from ${data.date}` : undefined} />
      <div className="card mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <div>
          <label className="label" htmlFor="m-day">
            Date
          </label>
          <input id="m-day" type="date" className="input" value={day} onChange={(e) => setDay(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="m-days">
            Days
          </label>
          <select id="m-days" className="input" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {[1, 2, 3, 4, 5, 6, 7].map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="m-league">
            League
          </label>
          <select id="m-league" className="input" value={competition} onChange={(e) => setCompetition(e.target.value)}>
            <option value="">All leagues</option>
            {(leagues.data ?? []).map((l) => (
              <option key={l.code} value={l.code}>
                {l.name}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <button type="button" className="btn-secondary" onClick={() => { setDay(todayIso()); setDays(2); setCompetition('') }}>
            Today
          </button>
        </div>
      </div>

      {loading && <LoadingState label="Loading fixtures" />}
      {error && !loading && <ErrorState message={error} onRetry={refetch} />}
      {data && !loading && !error && (
        data.fixtures.length === 0 ? (
          <EmptyState title="No fixtures for the selected period.">Try widening the date range or choose another league. If data was never loaded, use “Refresh data” on the Dashboard.</EmptyState>
        ) : (
          <div className="card">
            <DataTable columns={columns} rows={data.fixtures} rowKey={(f) => f.fixture_id} defaultSort={{ key: 'kickoff', dir: 'asc' }} />
          </div>
        )
      )}
    </div>
  )
}
