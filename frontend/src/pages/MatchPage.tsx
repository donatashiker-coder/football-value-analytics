import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { useStatus } from '@/hooks/useStatus'
import type { FixtureDetail, FormMatch, TeamNews, TeamStats } from '@/types'
import { localDate, localDateTime, num, odds, pct, shortDate, timezoneLabel, UNAVAILABLE } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { EmptyState, ErrorState, LoadingState, WarningBox } from '@/components/States'
import { FixtureStatusBadge, FormChip } from '@/components/Badges'
import { DemoBanner, DemoBadge } from '@/components/DemoBanner'
import { OpportunityTable } from '@/components/OpportunityTable'
import { ModelVsMarketChart, OddsHistoryChart, TrendChart } from '@/components/charts'
import { FreshnessChip } from '@/components/FreshnessChip'

export default function MatchPage() {
  const { id } = useParams()
  const { data, loading, error, refetch } = useApi((signal) => api.fixture(id ?? '', signal), [id])
  const { isDemo } = useStatus()

  if (loading) return <LoadingState label="Loading match" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!data) return <EmptyState title="Fixture not found." />

  return (
    <div>
      {data.is_demo && !isDemo && <div className="mb-3"><DemoBanner force /></div>}
      <PageHeader
        title={`${data.home_team} vs ${data.away_team}`}
        subtitle={
          <span className="flex flex-wrap items-center gap-2">
            <span>{data.competition}</span>
            <span>· {localDateTime(data.kickoff_utc)} ({timezoneLabel()})</span>
            {data.venue && <span>· {data.venue}</span>}
            {data.matchday !== null && <span>· matchday {data.matchday}</span>}
            <FixtureStatusBadge status={data.status} />
            <DemoBadge show={data.is_demo} />
            {data.result && data.result.home_goals !== null && (
              <span className="font-semibold text-slate-900 dark:text-slate-100">
                Result {data.result.home_goals}–{data.result.away_goals}
                {data.result.home_corners !== null ? ` (corners ${data.result.home_corners}–${data.result.away_corners})` : ''}
              </span>
            )}
          </span>
        }
        actions={<Link to={`/odds/${data.fixture_id}`} className="btn-secondary btn-sm">Odds page</Link>}
      />
      <div className="space-y-4">
        <ModelPanel data={data} />
        <Section title={`Opportunities (${data.opportunities.length})`}>
          {data.opportunities.length === 0 ? (
            <EmptyState title="No opportunities evaluated for this fixture.">Run a scan from the Dashboard once statistics and odds are loaded.</EmptyState>
          ) : (
            <OpportunityTable opportunities={data.opportunities} showMatch={false} defaultSort={{ key: 'value_score', dir: 'desc' }} />
          )}
        </Section>
        <div className="grid gap-4 lg:grid-cols-2">
          <StatsComparison data={data} />
          <ModelVsMarket data={data} />
        </div>
        <FormSection data={data} />
        <div className="grid gap-4 lg:grid-cols-2">
          <Section title="Head to head">
            {data.head_to_head.length === 0 ? (
              <div className="text-sm muted">No head-to-head matches recorded.</div>
            ) : (
              <table className="table text-xs">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Home side</th>
                    <th className="text-right">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {data.head_to_head.map((h, i) => (
                    <tr key={i}>
                      <td>{localDate(h.date)}</td>
                      <td>{h.home_was === 'this_home_team' ? data.home_team : h.home_was === 'this_away_team' ? data.away_team : h.home_was}</td>
                      <td className="text-right num">
                        {h.home_goals ?? '—'}–{h.away_goals ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>
          <Section title="Team news">
            <div className="grid gap-3 md:grid-cols-2">
              <TeamNewsBlock team={data.home_team} news={data.team_news?.home} />
              <TeamNewsBlock team={data.away_team} news={data.team_news?.away} />
            </div>
          </Section>
        </div>
        <OddsSection data={data} />
        <Section title="Feature snapshot (reproducibility)">
          {!data.feature_snapshot ? (
            <div className="text-sm muted">No feature snapshot — fixture not analysed yet (DATA UNAVAILABLE).</div>
          ) : (
            <div className="space-y-2 text-sm">
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 md:grid-cols-4">
                <dt className="muted">Snapshot id</dt>
                <dd>{data.feature_snapshot.id}</dd>
                <dt className="muted">Feature version</dt>
                <dd>{data.feature_snapshot.feature_version}</dd>
                <dt className="muted">Data timestamp</dt>
                <dd>{localDateTime(data.feature_snapshot.data_timestamp)}</dd>
                <dt className="muted">Data quality</dt>
                <dd>{data.feature_snapshot.data_quality === null ? UNAVAILABLE : Math.round(data.feature_snapshot.data_quality)}</dd>
                <dt className="muted">Model versions</dt>
                <dd>{data.model.versions.length > 0 ? data.model.versions.join(', ') : '—'}</dd>
                <dt className="muted">Prediction time</dt>
                <dd>{data.model.prediction_timestamp ? localDateTime(data.model.prediction_timestamp) : '—'}</dd>
                {data.features && (
                  <>
                    <dt className="muted">Sample size</dt>
                    <dd>{data.features.sample_size ?? UNAVAILABLE}</dd>
                    <dt className="muted">Volatility / news uncertainty</dt>
                    <dd>
                      {num(data.features.volatility)} / {num(data.features.news_uncertainty)}
                    </dd>
                  </>
                )}
              </dl>
              {data.feature_snapshot.warnings.length > 0 && (
                <WarningBox title="Data quality warnings">
                  <ul className="list-inside list-disc text-xs">
                    {data.feature_snapshot.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </WarningBox>
              )}
              {data.features?.league.fallback && <WarningBox>League averages use a fallback prior (insufficient league sample).</WarningBox>}
            </div>
          )}
        </Section>
      </div>
    </div>
  )
}

function ModelPanel({ data }: { data: FixtureDetail }) {
  const models = Object.keys(data.model.probabilities ?? {})
  const marketKeys = useMemo(() => {
    const keys = new Set<string>()
    for (const m of models) for (const k of Object.keys(data.model.probabilities[m])) keys.add(k)
    return Array.from(keys)
  }, [models, data.model.probabilities])

  return (
    <Section title="Model panel">
      <div className="grid gap-4 lg:grid-cols-4">
        <div className="space-y-2 lg:col-span-1">
          <ExpectedCard label="Expected goals" value={data.model.expected_goals} digits={2} />
          <ExpectedCard label="Expected corners" value={data.model.expected_corners} digits={1} />
          {data.features && (
            <div className="rounded border border-slate-200 p-2 text-xs dark:border-slate-700">
              <div className="font-semibold uppercase muted">Elo</div>
              <div className="num">
                {data.home_team}: {data.features.home_elo !== null ? Math.round(data.features.home_elo) : UNAVAILABLE}
              </div>
              <div className="num">
                {data.away_team}: {data.features.away_elo !== null ? Math.round(data.features.away_elo) : UNAVAILABLE}
              </div>
              <div className="num muted">Diff: {data.features.elo_diff !== null ? Math.round(data.features.elo_diff) : UNAVAILABLE}</div>
            </div>
          )}
        </div>
        <div className="lg:col-span-3">
          {models.length === 0 ? (
            <EmptyState title="No model predictions for this fixture (DATA UNAVAILABLE)." />
          ) : (
            <div className="table-wrap">
              <table className="table text-xs">
                <thead>
                  <tr>
                    <th>Market</th>
                    {models.map((m) => (
                      <th key={m} className="text-right">
                        {m}
                      </th>
                    ))}
                    <th className="text-right">Market</th>
                    <th>Agreement</th>
                  </tr>
                </thead>
                <tbody>
                  {marketKeys.map((k) => {
                    const vals = models.map((m) => data.model.probabilities[m][k]).filter((v): v is number => typeof v === 'number')
                    const spread = vals.length > 1 ? Math.max(...vals) - Math.min(...vals) : 0
                    const marketP = data.opportunities.find((o) => o.market_key === k)?.market_probability ?? null
                    return (
                      <tr key={k}>
                        <td>{data.markets?.[k]?.name ? `${data.markets[k].name}` : k}</td>
                        {models.map((m) => {
                          const v = data.model.probabilities[m][k]
                          return (
                            <td key={m} className="text-right num">
                              {typeof v === 'number' ? pct(v) : <span className="muted" title="Not predicted by this model">—</span>}
                            </td>
                          )
                        })}
                        <td className="text-right num">{marketP === null ? <span className="chip chip-grey">N/A</span> : pct(marketP)}</td>
                        <td>
                          {vals.length > 1 ? (
                            <span className={`chip ${spread <= 0.03 ? 'chip-green' : spread <= 0.08 ? 'chip-yellow' : 'chip-red'}`}>
                              {spread <= 0.03 ? 'AGREE' : spread <= 0.08 ? 'PARTIAL' : 'DISAGREE'} ({(spread * 100).toFixed(1)}pp)
                            </span>
                          ) : (
                            <span className="chip chip-grey">SINGLE MODEL</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </Section>
  )
}

function ExpectedCard({ label, value, digits }: { label: string; value: { home: number | null; away: number | null } | null; digits: number }) {
  return (
    <div className="rounded border border-slate-200 p-2 text-xs dark:border-slate-700">
      <div className="font-semibold uppercase muted">{label}</div>
      {!value ? (
        <span className="chip chip-grey">DATA UNAVAILABLE</span>
      ) : (
        <div className="flex items-baseline gap-2 text-lg font-semibold num">
          <span>{num(value.home, digits)}</span>
          <span className="text-sm muted">–</span>
          <span>{num(value.away, digits)}</span>
          <span className="text-xs font-normal muted">total {value.home !== null && value.away !== null ? (value.home + value.away).toFixed(digits) : UNAVAILABLE}</span>
        </div>
      )}
    </div>
  )
}

const COMPARE_ROWS: { key: string; label: string; fmt?: (v: number) => string }[] = [
  { key: 'matches', label: 'Matches (sample)', fmt: (v) => String(Math.round(v)) },
  { key: 'goals_for_avg', label: 'Goals for / match' },
  { key: 'goals_against_avg', label: 'Goals against / match' },
  { key: 'xg_for_avg', label: 'xG for / match' },
  { key: 'xg_against_avg', label: 'xG against / match' },
  { key: 'shots_for_avg', label: 'Shots / match' },
  { key: 'sot_for_avg', label: 'Shots on target / match' },
  { key: 'corners_for_avg', label: 'Corners for / match' },
  { key: 'corners_against_avg', label: 'Corners against / match' },
  { key: 'btts_pct', label: 'BTTS %', fmt: (v) => pct(v, 0) },
  { key: 'over_2.5_pct', label: 'Over 2.5 %', fmt: (v) => pct(v, 0) },
  { key: 'clean_sheet_pct', label: 'Clean sheets %', fmt: (v) => pct(v, 0) },
  { key: 'points_per_game', label: 'Points per game' },
  { key: 'goals_for_last_5', label: 'Goals for (last 5)' },
  { key: 'corners_for_last_5', label: 'Corners for (last 5)' },
  { key: 'days_since_last_match', label: 'Rest days', fmt: (v) => String(Math.round(v)) },
]

function statCell(stats: TeamStats | undefined, key: string, fmt?: (v: number) => string) {
  const v = stats?.[key]
  if (typeof v !== 'number' || !Number.isFinite(v)) return <span className="chip chip-grey">DATA UNAVAILABLE</span>
  return <span className="num">{fmt ? fmt(v) : num(v)}</span>
}

function StatsComparison({ data }: { data: FixtureDetail }) {
  const f = data.features
  return (
    <Section title="Team statistics comparison">
      {!f ? (
        <EmptyState title="Statistics DATA UNAVAILABLE for this fixture." />
      ) : (
        <div className="table-wrap">
          <table className="table text-xs">
            <thead>
              <tr>
                <th>Metric</th>
                <th className="text-right">{data.home_team}</th>
                <th className="text-right">{data.away_team}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Attack / defence rating</td>
                <td className="text-right num">
                  {num(f.home_attack)} / {num(f.home_defence)}
                </td>
                <td className="text-right num">
                  {num(f.away_attack)} / {num(f.away_defence)}
                </td>
              </tr>
              {COMPARE_ROWS.map((r) => (
                <tr key={r.key}>
                  <td>{r.label}</td>
                  <td className="text-right">{statCell(f.home_stats, r.key, r.fmt)}</td>
                  <td className="text-right">{statCell(f.away_stats, r.key, r.fmt)}</td>
                </tr>
              ))}
              <tr>
                <td>Home-venue goals for / away-venue goals for</td>
                <td className="text-right">{statCell(f.home_stats, 'home_goals_for_avg')}</td>
                <td className="text-right">{statCell(f.away_stats, 'away_goals_for_avg')}</td>
              </tr>
            </tbody>
          </table>
          <div className="mt-2 text-xs muted">
            League averages: home goals {num(f.league.home_goals)} · away goals {num(f.league.away_goals)} · corners {num(f.league.home_corners, 1)}/{num(f.league.away_corners, 1)} · BTTS {pct(f.league.btts_rate, 0)} · O2.5 {pct(f.league.over_2_5_rate, 0)} · corner coverage {pct(f.league.corner_coverage, 0)} · xG coverage {pct(f.league.xg_coverage, 0)}
          </div>
        </div>
      )}
    </Section>
  )
}

function ModelVsMarket({ data }: { data: FixtureDetail }) {
  const rows = data.opportunities.map((o) => ({ name: `${o.market} ${o.selection}`.slice(0, 28), model: o.model_probability, market: o.market_probability }))
  return (
    <Section title="Model vs market probability">
      {rows.length === 0 ? <EmptyState title="No evaluated markets." /> : <ModelVsMarketChart rows={rows} />}
    </Section>
  )
}

function FormSection({ data }: { data: FixtureDetail }) {
  const home = data.form?.home ?? []
  const away = data.form?.away ?? []
  return (
    <Section title="Recent form (last 10)">
      <div className="grid gap-4 lg:grid-cols-2">
        <FormBlock team={data.home_team} matches={home} />
        <FormBlock team={data.away_team} matches={away} />
      </div>
    </Section>
  )
}

function FormBlock({ team, matches }: { team: string; matches: FormMatch[] }) {
  const ordered = [...matches].sort((a, b) => a.date.localeCompare(b.date)).slice(-10)
  const trend = ordered.map((m) => ({ label: shortDate(m.date), goals_for: m.goals_for, goals_against: m.goals_against, xg_for: m.xg_for, xg_against: m.xg_against, corners_for: m.corners_for, corners_against: m.corners_against }))
  if (ordered.length === 0) {
    return (
      <div>
        <div className="mb-1 font-medium">{team}</div>
        <EmptyState title="Form DATA UNAVAILABLE." />
      </div>
    )
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{team}</span>
        <div className="flex gap-1">
          {ordered.map((m) => (
            <FormChip key={m.fixture_id} result={m.result} />
          ))}
        </div>
      </div>
      <div className="table-wrap">
        <table className="table text-xs">
          <thead>
            <tr>
              <th>Date</th>
              <th>H/A</th>
              <th className="text-right">Score</th>
              <th className="text-right">xG</th>
              <th className="text-right">Corners</th>
              <th>Res</th>
            </tr>
          </thead>
          <tbody>
            {[...ordered].reverse().map((m) => (
              <tr key={m.fixture_id}>
                <td>
                  <Link to={`/matches/${m.fixture_id}`}>{localDate(m.date)}</Link>
                </td>
                <td>{m.is_home ? 'H' : 'A'}</td>
                <td className="text-right num">
                  {m.goals_for ?? '—'}–{m.goals_against ?? '—'}
                </td>
                <td className="text-right num">
                  {num(m.xg_for, 1)}–{num(m.xg_against, 1)}
                </td>
                <td className="text-right num">
                  {m.corners_for ?? '—'}–{m.corners_against ?? '—'}
                </td>
                <td>
                  <FormChip result={m.result} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid gap-2 md:grid-cols-3">
        <div>
          <div className="text-[11px] font-semibold uppercase muted">Goals</div>
          <TrendChart data={trend} xKey="label" height={150} series={[{ key: 'goals_for', name: 'For' }, { key: 'goals_against', name: 'Against', colour: '#dc2626' }]} />
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase muted">xG</div>
          <TrendChart data={trend} xKey="label" height={150} series={[{ key: 'xg_for', name: 'For' }, { key: 'xg_against', name: 'Against', colour: '#dc2626' }]} />
        </div>
        <div>
          <div className="text-[11px] font-semibold uppercase muted">Corners</div>
          <TrendChart data={trend} xKey="label" height={150} series={[{ key: 'corners_for', name: 'For' }, { key: 'corners_against', name: 'Against', colour: '#dc2626' }]} />
        </div>
      </div>
    </div>
  )
}

function TeamNewsBlock({ team, news }: { team: string; news: TeamNews | undefined }) {
  return (
    <div>
      <div className="mb-1 font-medium">{team}</div>
      {!news || !news.available ? (
        <span className="chip chip-grey">TEAM NEWS DATA UNAVAILABLE</span>
      ) : (
        <div className="space-y-2 text-xs">
          <div>
            <div className="font-semibold uppercase muted">Injuries ({news.injuries.length})</div>
            {news.injuries.length === 0 ? (
              <div className="muted">None reported.</div>
            ) : (
              <ul className="space-y-0.5">
                {news.injuries.map((inj, i) => (
                  <li key={i}>
                    <span className="font-medium">{inj.player}</span> — {inj.reason ?? 'reason unknown'} · {inj.status ?? 'status unknown'}
                    {inj.importance ? ` · ${inj.importance}` : ''}
                    <div className="muted">
                      Source: {inj.source ?? 'unknown'} · retrieved {inj.retrieved_at ? localDateTime(inj.retrieved_at) : 'unknown'}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <div className="font-semibold uppercase muted">Suspensions ({news.suspensions.length})</div>
            {news.suspensions.length === 0 ? (
              <div className="muted">None reported.</div>
            ) : (
              <ul>
                {news.suspensions.map((s, i) => (
                  <li key={i}>
                    <span className="font-medium">{s.player}</span> — {s.reason ?? 'reason unknown'}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function OddsSection({ data }: { data: FixtureDetail }) {
  const oddsApi = useApi((signal) => api.odds(data.fixture_id, signal), [data.fixture_id])
  const [historyKey, setHistoryKey] = useState('')
  const marketEntries = Object.entries(data.odds ?? {})
  const historyKeys = Object.keys(oddsApi.data?.history ?? {})
  const activeKey = historyKey || historyKeys[0] || ''
  const overroundFor = (k: string) => oddsApi.data?.markets.find((m) => m.market_key === k)
  const staleAny = (oddsApi.data?.markets ?? []).some((m) => m.stale)

  return (
    <Section title="Odds" actions={<Link to={`/odds/${data.fixture_id}`} className="text-xs">Full odds page</Link>}>
      {marketEntries.length === 0 ? (
        <EmptyState title="ODDS UNAVAILABLE for this fixture." />
      ) : (
        <div className="space-y-3">
          {staleAny && <WarningBox>Some markets carry STALE ODDS (older than the configured freshness threshold).</WarningBox>}
          <div className="table-wrap">
            <table className="table text-xs">
              <thead>
                <tr>
                  <th>Market</th>
                  <th>Selection</th>
                  <th className="text-right">Best</th>
                  <th>Bookmaker</th>
                  <th className="text-right">Median</th>
                  <th className="text-right">Min</th>
                  <th className="text-right">Max</th>
                  <th className="text-right">Books</th>
                  <th className="text-right">Overround</th>
                  <th>Freshness</th>
                  <th>Movement</th>
                  <th>Prices</th>
                </tr>
              </thead>
              <tbody>
                {marketEntries.map(([k, m]) => {
                  const extra = overroundFor(k)
                  const mv = data.odds_movement?.[k]
                  return (
                    <tr key={k}>
                      <td>{data.markets?.[k]?.name ?? k}</td>
                      <td>{m.selection}</td>
                      <td className="text-right num font-medium">{odds(m.best_odds)}</td>
                      <td>{m.best_bookmaker ?? '—'}</td>
                      <td className="text-right num">{odds(m.median_odds)}</td>
                      <td className="text-right num">{odds(m.min_odds)}</td>
                      <td className="text-right num">{odds(m.max_odds)}</td>
                      <td className="text-right num">{m.bookmaker_count}</td>
                      <td className="text-right num">{extra ? pct(extra.overround, 2) : '—'}</td>
                      <td>{extra ? <FreshnessChip hoursOld={extra.age_hours} /> : <span className="chip chip-grey">AGE UNKNOWN</span>}</td>
                      <td>{mv ? <span className="whitespace-nowrap">{odds(mv.opening)} → {odds(mv.current)} <span className="muted">({mv.direction})</span></span> : <span className="muted">—</span>}</td>
                      <td>
                        <div className="flex flex-wrap gap-1">
                          {m.prices.map((p) => (
                            <span key={p.bookmaker} className={`rounded border px-1 ${p.bookmaker === m.best_bookmaker ? 'border-emerald-400' : 'border-slate-200 dark:border-slate-700'}`}>
                              {p.bookmaker} {odds(p.odds)}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between">
              <div className="text-xs font-semibold uppercase muted">Odds movement</div>
              {historyKeys.length > 0 && (
                <select className="input w-auto text-xs" value={activeKey} onChange={(e) => setHistoryKey(e.target.value)} aria-label="Market for movement chart">
                  {historyKeys.map((k) => (
                    <option key={k} value={k}>
                      {data.markets?.[k]?.name ?? k} — {data.odds?.[k]?.selection ?? ''}
                    </option>
                  ))}
                </select>
              )}
            </div>
            {oddsApi.loading && <LoadingState label="Loading odds history" />}
            {oddsApi.error && <ErrorState message={oddsApi.error} onRetry={oddsApi.refetch} />}
            {oddsApi.data && <OddsHistoryChart history={activeKey ? oddsApi.data.history[activeKey] ?? [] : []} />}
          </div>
        </div>
      )}
    </Section>
  )
}
