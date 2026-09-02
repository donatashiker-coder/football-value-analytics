import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import type { BacktestBet, BreakdownRow } from '@/types'
import { localDateTime, money, num, odds, pct, signedPct, titleCase } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { StatCard, toneForSigned } from '@/components/StatCard'
import { DataTable, type Column } from '@/components/DataTable'
import { Tabs } from '@/components/Tabs'
import { EmptyState, ErrorState, LoadingState } from '@/components/States'
import { CalibrationChart, DrawdownChart, EquityChart } from '@/components/charts'
import { DemoBadge } from '@/components/DemoBanner'

const BREAKDOWN_TABS: { key: string; label: string }[] = [
  { key: 'by_league', label: 'League' },
  { key: 'by_market', label: 'Market' },
  { key: 'by_odds_range', label: 'Odds range' },
  { key: 'by_month', label: 'Month' },
  { key: 'by_season', label: 'Season' },
  { key: 'by_ev_range', label: 'EV range' },
  { key: 'by_expected_total', label: 'Expected total' },
]

export default function BacktestDetailPage() {
  const { id } = useParams()
  const { data, loading, error, refetch } = useApi((signal) => api.backtest(id ?? '', signal), [id])
  const [tab, setTab] = useState('by_league')

  const availableTabs = useMemo(
    () => BREAKDOWN_TABS.filter((t) => data?.breakdowns && Array.isArray(data.breakdowns[t.key])).map((t) => ({ ...t, count: data?.breakdowns[t.key]?.length })),
    [data],
  )

  if (loading) return <LoadingState label="Loading backtest" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!data) return <EmptyState title="Backtest not found." />

  const s = data.summary
  const activeTab = availableTabs.some((t) => t.key === tab) ? tab : availableTabs[0]?.key ?? ''
  const breakdownRows: BreakdownRow[] = (activeTab && data.breakdowns[activeTab]) || []

  const breakdownCols: Column<BreakdownRow>[] = [
    { key: 'key', header: 'Key', sortValue: (r) => r.key, render: (r) => r.key },
    { key: 'bets', header: 'Bets', align: 'right', sortValue: (r) => r.bets, render: (r) => r.bets },
    { key: 'wins', header: 'Wins', align: 'right', sortValue: (r) => r.wins, render: (r) => r.wins },
    { key: 'sr', header: 'Strike', align: 'right', sortValue: (r) => r.strike_rate, render: (r) => pct(r.strike_rate) },
    { key: 'profit', header: 'Profit', align: 'right', sortValue: (r) => r.profit, render: (r) => money(r.profit) },
    { key: 'roi', header: 'ROI', align: 'right', sortValue: (r) => r.roi, render: (r) => <span className={roiClass(r.roi)}>{signedPct(r.roi)}</span> },
    { key: 'ao', header: 'Avg odds', align: 'right', sortValue: (r) => r.average_odds, render: (r) => num(r.average_odds) },
    { key: 'clv', header: 'Avg CLV', align: 'right', sortValue: (r) => r.average_clv, render: (r) => signedPct(r.average_clv) },
  ]

  const betCols: Column<BacktestBet>[] = [
    { key: 'kickoff', header: 'Kickoff', sortValue: (b) => b.kickoff, render: (b) => <span className="whitespace-nowrap">{localDateTime(b.kickoff)}</span> },
    { key: 'fixture', header: 'Fixture', render: (b) => <Link to={`/matches/${b.fixture_id}`} title={b.fixture_id}>{b.fixture_id.slice(0, 8)}</Link> },
    { key: 'comp', header: 'League', sortValue: (b) => b.competition, render: (b) => b.competition },
    { key: 'market', header: 'Market', sortValue: (b) => b.market_key, render: (b) => b.market_key },
    { key: 'odds', header: 'Odds', align: 'right', sortValue: (b) => b.odds, render: (b) => odds(b.odds) },
    { key: 'bk', header: 'Bookmaker', render: (b) => b.bookmaker ?? '—' },
    { key: 'mp', header: 'Model %', align: 'right', sortValue: (b) => b.model_probability, render: (b) => pct(b.model_probability) },
    { key: 'kp', header: 'Market %', align: 'right', sortValue: (b) => b.market_probability, render: (b) => pct(b.market_probability) },
    { key: 'ev', header: 'EV', align: 'right', sortValue: (b) => b.ev, render: (b) => signedPct(b.ev) },
    { key: 'stake', header: 'Stake', align: 'right', sortValue: (b) => b.stake, render: (b) => money(b.stake) },
    { key: 'outcome', header: 'Outcome', sortValue: (b) => b.outcome, render: (b) => <span className={`chip ${b.outcome === 'won' ? 'chip-green' : b.outcome === 'lost' ? 'chip-red' : 'chip-grey'}`}>{b.outcome}</span> },
    { key: 'profit', header: 'Profit', align: 'right', sortValue: (b) => b.profit, render: (b) => <span className={roiClass(b.profit)}>{money(b.profit)}</span> },
    { key: 'close', header: 'Closing', align: 'right', sortValue: (b) => b.closing_odds, render: (b) => odds(b.closing_odds) },
    { key: 'clv', header: 'CLV', align: 'right', sortValue: (b) => b.clv, render: (b) => signedPct(b.clv) },
    { key: 'season', header: 'Season', render: (b) => b.season ?? '—' },
  ]

  return (
    <div>
      <PageHeader
        title={`Backtest ${data.id.slice(0, 8)}: ${data.name}`}
        subtitle={
          <span>
            {titleCase(data.strategy)} · {data.status} · model {data.model_version ?? '—'} · {localDateTime(data.created_at)} <DemoBadge show={data.is_demo} /> · <Link to="/backtests">All backtests</Link>
          </span>
        }
      />
      {!s ? (
        <EmptyState title="No summary available for this backtest." />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <StatCard label="Bets" value={s.bets} hint={`${s.wins}W / ${s.losses}L / ${s.pushes}P · ${s.fixtures_evaluated} fixtures`} />
            <StatCard label="ROI" value={signedPct(s.roi)} tone={toneForSigned(s.roi)} hint={`Yield ${signedPct(s.yield)}`} />
            <StatCard label="Profit" value={money(s.profit)} tone={toneForSigned(s.profit)} hint={`Staked ${money(s.total_staked)}`} />
            <StatCard label="Strike rate" value={pct(s.strike_rate)} hint={`Avg odds ${num(s.average_odds)}`} />
            <StatCard label="Max drawdown" value={money(s.max_drawdown)} hint={pct(s.max_drawdown_pct)} tone="red" />
            <StatCard label="Avg CLV" value={signedPct(s.average_clv)} tone={toneForSigned(s.average_clv)} hint={`CLV+ rate ${pct(s.clv_positive_rate)}`} />
            <StatCard label="Avg EV / edge" value={`${signedPct(s.average_ev)} / ${signedPct(s.average_edge)}`} />
            <StatCard label="Profit factor" value={num(s.profit_factor)} />
            <StatCard label="Sharpe-like" value={num(s.sharpe_like)} />
            <StatCard label="Streaks" value={`${s.longest_winning_streak}W / ${s.longest_losing_streak}L`} />
            <StatCard label="Final bankroll" value={money(s.final_bankroll)} />
            {s.calibration && <StatCard label="Brier (backtest)" value={num(s.calibration.brier, 4)} hint={`ECE ${num(s.calibration.expected_calibration_error, 4)} · n=${s.calibration.n}`} />}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Equity curve">
              <EquityChart data={data.equity_curve} />
            </Section>
            <Section title="Drawdown">
              <DrawdownChart data={data.equity_curve} height={240} />
            </Section>
          </div>

          <Section title="Breakdowns">
            {availableTabs.length === 0 ? (
              <EmptyState title="No breakdowns available." />
            ) : (
              <>
                <Tabs tabs={availableTabs} active={activeTab} onChange={setTab} />
                <div className="mt-3">
                  <DataTable columns={breakdownCols} rows={breakdownRows} rowKey={(r) => r.key} dense emptyMessage="No rows in this breakdown." />
                </div>
              </>
            )}
          </Section>

          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Calibration (reliability diagram)">
              {s.calibration ? <CalibrationChart bins={s.calibration.bins} /> : <EmptyState title="Calibration DATA UNAVAILABLE." />}
            </Section>
            <Section title="Corner distribution comparison">
              {s.corner_distribution_comparison ? (
                <dl className="grid grid-cols-2 gap-1 text-sm">
                  <dt className="muted">Poisson log-likelihood</dt>
                  <dd className="num">{num(s.corner_distribution_comparison.poisson_loglik, 2)}</dd>
                  <dt className="muted">Negative binomial log-likelihood</dt>
                  <dd className="num">{num(s.corner_distribution_comparison.negative_binomial_loglik, 2)}</dd>
                  <dt className="muted">Preferred</dt>
                  <dd>
                    <span className="chip chip-blue">{s.corner_distribution_comparison.preferred}</span>
                  </dd>
                </dl>
              ) : (
                <div className="text-sm muted">Not applicable for this strategy (corner distribution comparison is produced for corner strategies only).</div>
              )}
              <div className="mt-3 text-xs font-semibold uppercase muted">Parameters</div>
              <pre className="mt-1 max-h-48 overflow-auto rounded bg-slate-50 p-2 text-xs dark:bg-slate-800">{JSON.stringify(data.parameters, null, 2)}</pre>
            </Section>
          </div>

          <Section title={`Bets (${data.bets.length})`}>
            <DataTable columns={betCols} rows={data.bets} rowKey={(b, ) => `${b.fixture_id}-${b.market_key}-${b.kickoff}`} dense maxRows={50} defaultSort={{ key: 'kickoff', dir: 'asc' }} emptyMessage="No bets were placed in this backtest." />
          </Section>
        </div>
      )}
    </div>
  )
}

function roiClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return 'muted'
  if (v > 0.005) return 'text-emerald-700 dark:text-emerald-300'
  if (v < -0.005) return 'text-red-700 dark:text-red-300'
  return 'text-amber-700 dark:text-amber-300'
}
