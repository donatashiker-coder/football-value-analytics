import { Link, useParams } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import type { TeamStats } from '@/types'
import { localDate, localDateTime, num, pct, shortDate, UNAVAILABLE } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { StatCard } from '@/components/StatCard'
import { EmptyState, ErrorState, LoadingState, WarningBox } from '@/components/States'
import { TrendChart } from '@/components/charts'
import { DemoBadge } from '@/components/DemoBanner'

interface StatDef {
  key: string
  label: string
  fmt?: (v: number) => string
}

const STAT_ROWS: StatDef[] = [
  { key: 'matches', label: 'Matches', fmt: (v) => String(Math.round(v)) },
  { key: 'points_per_game', label: 'Points per game' },
  { key: 'goals_for_avg', label: 'Goals for (avg)' },
  { key: 'goals_against_avg', label: 'Goals against (avg)' },
  { key: 'xg_for_avg', label: 'xG for (avg)' },
  { key: 'xg_against_avg', label: 'xG against (avg)' },
  { key: 'shots_for_avg', label: 'Shots for (avg)' },
  { key: 'sot_for_avg', label: 'Shots on target (avg)' },
  { key: 'corners_for_avg', label: 'Corners for (avg)' },
  { key: 'corners_against_avg', label: 'Corners against (avg)' },
  { key: 'btts_pct', label: 'BTTS %', fmt: (v) => pct(v) },
  { key: 'over_2.5_pct', label: 'Over 2.5 %', fmt: (v) => pct(v) },
  { key: 'clean_sheet_pct', label: 'Clean sheet %', fmt: (v) => pct(v) },
  { key: 'goals_for_last_5', label: 'Goals for (last 5)' },
  { key: 'corners_for_last_5', label: 'Corners for (last 5)' },
  { key: 'days_since_last_match', label: 'Days since last match', fmt: (v) => String(Math.round(v)) },
]

function statValue(stats: TeamStats, key: string, fmt?: (v: number) => string): string {
  const v = stats[key]
  if (typeof v !== 'number' || !Number.isFinite(v)) return UNAVAILABLE
  return fmt ? fmt(v) : num(v)
}

export default function TeamPage() {
  const { id } = useParams()
  const { data, loading, error, refetch } = useApi((signal) => api.team(id ?? '', signal), [id])

  if (loading) return <LoadingState label="Loading team" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!data) return <EmptyState title="Team not found." />

  const stats = data.stats ?? {}
  const recent = [...data.recent_matches].sort((a, b) => a.date.localeCompare(b.date))
  const trend = recent.map((m) => ({
    label: shortDate(m.date),
    goals_for: m.goals_for,
    goals_against: m.goals_against,
    xg_for: m.xg_for,
    xg_against: m.xg_against,
    corners_for: m.corners_for,
    corners_against: m.corners_against,
  }))

  return (
    <div>
      <PageHeader
        title={data.name}
        subtitle={
          <span>
            Season {data.season_year ?? '—'} · <DemoBadge show={data.is_demo} /> <Link to="/teams">Back to search</Link>
          </span>
        }
      />
      {data.warnings.length > 0 && (
        <div className="mb-4">
          <WarningBox title="Data warnings">
            <ul className="list-inside list-disc text-xs">
              {data.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </WarningBox>
        </div>
      )}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="Elo" value={data.elo !== null ? Math.round(data.elo) : UNAVAILABLE} tone={data.elo === null ? 'grey' : 'default'} />
        <StatCard label="PPG" value={statValue(stats, 'points_per_game')} />
        <StatCard label="Goals for / against" value={`${statValue(stats, 'goals_for_avg')} / ${statValue(stats, 'goals_against_avg')}`} />
        <StatCard label="xG for / against" value={`${statValue(stats, 'xg_for_avg')} / ${statValue(stats, 'xg_against_avg')}`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Season statistics (overall / home / away)">
          <div className="table-wrap">
            <table className="table text-xs">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th className="text-right">Season</th>
                  <th className="text-right">Home</th>
                  <th className="text-right">Away</th>
                  <th className="text-right">League avg</th>
                </tr>
              </thead>
              <tbody>
                {STAT_ROWS.map((r) => (
                  <tr key={r.key}>
                    <td>{r.label}</td>
                    <td className="text-right num">{statValue(stats, r.key, r.fmt)}</td>
                    <td className="text-right num">{statValue(stats, `home_${r.key}`, r.fmt)}</td>
                    <td className="text-right num">{statValue(stats, `away_${r.key}`, r.fmt)}</td>
                    <td className="text-right num muted">{statValue(data.league_averages ?? {}, r.key, r.fmt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <div className="space-y-4">
          <Section title="Goals trend (recent matches)">
            <TrendChart data={trend} xKey="label" series={[{ key: 'goals_for', name: 'Goals for' }, { key: 'goals_against', name: 'Goals against', colour: '#dc2626' }]} />
          </Section>
          <Section title="xG trend">
            <TrendChart data={trend} xKey="label" series={[{ key: 'xg_for', name: 'xG for' }, { key: 'xg_against', name: 'xG against', colour: '#dc2626' }]} />
          </Section>
          <Section title="Corners trend">
            <TrendChart data={trend} xKey="label" series={[{ key: 'corners_for', name: 'Corners for' }, { key: 'corners_against', name: 'Corners against', colour: '#dc2626' }]} />
          </Section>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Section title="Recent matches">
          {data.recent_matches.length === 0 ? (
            <EmptyState title="No recent matches." />
          ) : (
            <div className="table-wrap">
              <table className="table text-xs">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>H/A</th>
                    <th className="text-right">GF</th>
                    <th className="text-right">GA</th>
                    <th className="text-right">xGF</th>
                    <th className="text-right">xGA</th>
                    <th className="text-right">CF</th>
                    <th className="text-right">CA</th>
                    <th>Flags</th>
                  </tr>
                </thead>
                <tbody>
                  {[...data.recent_matches].sort((a, b) => b.date.localeCompare(a.date)).map((m) => (
                    <tr key={m.fixture_id}>
                      <td>
                        <Link to={`/matches/${m.fixture_id}`}>{localDate(m.date)}</Link>
                      </td>
                      <td>{m.is_home ? 'H' : 'A'}</td>
                      <td className="text-right num">{m.goals_for ?? '—'}</td>
                      <td className="text-right num">{m.goals_against ?? '—'}</td>
                      <td className="text-right num">{num(m.xg_for)}</td>
                      <td className="text-right num">{num(m.xg_against)}</td>
                      <td className="text-right num">{m.corners_for ?? '—'}</td>
                      <td className="text-right num">{m.corners_against ?? '—'}</td>
                      <td>{m.early_red_card && <span className="chip chip-yellow">EARLY RED</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
        <div className="space-y-4">
          <Section title="Upcoming fixtures">
            {data.upcoming.length === 0 ? (
              <div className="text-xs muted">No upcoming fixtures.</div>
            ) : (
              <ul className="divide-y divide-slate-100 text-sm dark:divide-slate-800">
                {data.upcoming.map((u) => (
                  <li key={u.fixture_id} className="flex items-center justify-between py-1.5">
                    <Link to={`/matches/${u.fixture_id}`}>
                      {u.home_team} vs {u.away_team}
                    </Link>
                    <span className="text-xs muted">{localDateTime(u.kickoff_utc)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title="Injuries">
            {data.injuries.length === 0 ? (
              <div className="text-xs muted">No injuries listed (or DATA UNAVAILABLE from provider).</div>
            ) : (
              <ul className="space-y-1 text-xs">
                {data.injuries.map((inj, i) => (
                  <li key={i}>
                    <span className="font-medium">{inj.player}</span> — {inj.reason ?? 'unknown'} · {inj.status ?? 'status unknown'}
                    {inj.importance ? ` · ${inj.importance}` : ''}
                    <span className="muted"> ({inj.source ?? 'source unknown'}, {inj.retrieved_at ? localDateTime(inj.retrieved_at) : 'time unknown'})</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <Section title="Transfers">
            <GenericList rows={data.transfers} empty="No transfers recorded." />
          </Section>
          <Section title="Manager changes">
            <GenericList rows={data.manager_changes} empty="No manager changes recorded." />
          </Section>
        </div>
      </div>
    </div>
  )
}

function GenericList({ rows, empty }: { rows: Record<string, unknown>[]; empty: string }) {
  if (!rows || rows.length === 0) return <div className="text-xs muted">{empty}</div>
  return (
    <ul className="space-y-1 text-xs">
      {rows.map((r, i) => (
        <li key={i} className="flex flex-wrap gap-x-2">
          {Object.entries(r).map(([k, v]) => (
            <span key={k}>
              <span className="muted">{k}:</span> {v === null || v === undefined ? '—' : String(v)}
            </span>
          ))}
        </li>
      ))}
    </ul>
  )
}
