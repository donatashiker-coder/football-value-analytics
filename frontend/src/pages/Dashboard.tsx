import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { useToast } from '@/hooks/useToast'
import { useStatus } from '@/hooks/useStatus'
import type { Opportunity } from '@/types'
import { int, localDateTime, money, num, odds, pct, signedPct } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { StatCard, toneForSigned } from '@/components/StatCard'
import { OpportunityTable } from '@/components/OpportunityTable'
import { EmptyState, ErrorState, LoadingState, Spinner } from '@/components/States'
import { EvBadge, ScoreChip, StatusBadge, ValueBadge } from '@/components/Badges'
import { DemoBanner } from '@/components/DemoBanner'

export default function Dashboard() {
  const { data, loading, error, refetch } = useApi((signal) => api.dashboard(signal), [])
  const { isDemo, refresh: refreshStatus } = useStatus()
  const toast = useToast()
  const [scanning, setScanning] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  async function runScan() {
    setScanning(true)
    try {
      const r = await api.runScan({})
      toast.push(
        'success',
        'Scan complete',
        `${r.fixtures} fixtures, ${r.analysed} analysed, ${r.value_candidates} value candidates, ${r.no_bet} no-bet, ${r.odds_unavailable} odds unavailable${r.warnings?.length ? `\nWarnings: ${r.warnings.slice(0, 3).join('; ')}` : ''}`,
      )
      refetch()
      refreshStatus()
    } catch (err) {
      toast.push('error', 'Scan failed', err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setScanning(false)
    }
  }

  async function refreshData() {
    setRefreshing(true)
    try {
      const r = await api.runJob('pipeline')
      toast.push('success', 'Data pipeline finished', summariseJob(r))
      refetch()
      refreshStatus()
    } catch (err) {
      toast.push('error', 'Pipeline failed', err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setRefreshing(false)
    }
  }

  return (
    <div>
      <PageHeader
        title="Dashboard"
        subtitle={data ? `Scan date ${data.date}` : undefined}
        actions={
          <>
            <button type="button" className="btn-secondary" onClick={refreshData} disabled={refreshing || scanning}>
              {refreshing && <Spinner />}
              Refresh data
            </button>
            <button type="button" className="btn-primary" onClick={runScan} disabled={scanning || refreshing}>
              {scanning && <Spinner />}
              Run scan
            </button>
          </>
        }
      />
      {data?.is_demo && !isDemo && <div className="mb-3"><DemoBanner force /></div>}

      {loading && <LoadingState label="Loading dashboard" />}
      {error && !loading && <ErrorState message={error} onRetry={refetch} />}

      {data && !loading && !error && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <StatCard label="Fixtures today" value={int(data.fixtures_today)} />
            <StatCard label="Analysed" value={int(data.fixtures_analysed)} hint={data.fixtures_today > 0 ? `${Math.round((data.fixtures_analysed / data.fixtures_today) * 100)}% coverage` : undefined} />
            <StatCard label="Value candidates" value={int(data.value_candidates)} tone={data.value_candidates > 0 ? 'green' : 'grey'} />
            <StatCard label="Markets evaluated" value={int(data.markets_evaluated)} />
            <StatCard label="Paper ROI" value={signedPct(data.paper_betting.roi)} tone={toneForSigned(data.paper_betting.roi)} hint={`${data.paper_betting.settled_bets} settled`} />
            <StatCard label="Model Brier (30d)" value={num(data.model_performance.brier, 4)} hint={`n = ${data.model_performance.n}`} tone={data.model_performance.brier === null ? 'grey' : 'default'} />
          </div>

          <div className="flex flex-wrap gap-2">
            {data.data_quality_warnings > 0 ? (
              <span className="chip chip-yellow">{data.data_quality_warnings} data quality warnings</span>
            ) : (
              <span className="chip chip-green">No data quality warnings</span>
            )}
            {data.stale_odds > 0 ? <span className="chip chip-yellow">{data.stale_odds} fixtures with STALE ODDS</span> : <span className="chip chip-green">Odds fresh</span>}
            {data.fixtures_today === 0 && <span className="chip chip-grey">No fixtures today</span>}
          </div>

          <Section title="Top 10 opportunities" actions={<Link to="/value" className="text-xs">All value bets</Link>}>
            {data.top_opportunities.length === 0 ? (
              <EmptyState title="No value candidates for this scan date.">Run a scan or widen the filters on the Value Bets page.</EmptyState>
            ) : (
              <OpportunityTable opportunities={data.top_opportunities.slice(0, 10)} compact />
            )}
          </Section>

          <div className="grid gap-4 lg:grid-cols-2">
            <HighlightCard title="Highest EV" opp={data.highest_ev} />
            <HighlightCard title="Highest confidence" opp={data.highest_confidence} />
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MiniList title="Best corners" items={data.best_corners} link="/corners" />
            <MiniList title="Best goals" items={data.best_goals} link="/goals" />
            <MiniList title="Best low scoring" items={data.best_low_scoring} link="/low-scoring" />
            <MiniList title="Best BTTS" items={data.best_btts} link="/value?market_group=btts" />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Section title="Model performance (last 30 days)" actions={<Link to="/performance" className="text-xs">Details</Link>}>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                <Metric label="Predictions" value={int(data.model_performance.n)} />
                <Metric label="Brier" value={num(data.model_performance.brier, 4)} />
                <Metric label="Log loss" value={num(data.model_performance.log_loss, 4)} />
                <Metric label="ECE" value={num(data.model_performance.expected_calibration_error, 4)} />
                <Metric label="Avg CLV" value={signedPct(data.model_performance.average_clv)} />
                <Metric label="Flat ROI (all signals)" value={signedPct(data.model_performance.flat_roi_all_signals)} />
              </dl>
              {data.model_performance.n === 0 && <p className="mt-2 text-xs muted">No settled predictions in the last 30 days — metrics show DATA UNAVAILABLE.</p>}
            </Section>
            <Section title="Paper betting" actions={<Link to="/bankroll" className="text-xs">Bankroll</Link>}>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
                <Metric label="Starting bankroll" value={money(data.paper_betting.starting_bankroll)} />
                <Metric label="Current bankroll" value={money(data.paper_betting.current_bankroll)} />
                <Metric label="Profit" value={money(data.paper_betting.profit)} />
                <Metric label="Total staked" value={money(data.paper_betting.total_staked)} />
                <Metric label="ROI" value={signedPct(data.paper_betting.roi)} />
                <Metric label="Max drawdown" value={money(data.paper_betting.max_drawdown)} />
                <Metric label="Open / settled" value={`${data.paper_betting.open_bets} / ${data.paper_betting.settled_bets}`} />
                <Metric label="Wins / losses" value={`${data.paper_betting.wins} / ${data.paper_betting.losses}`} />
                <Metric label="Strike rate" value={pct(data.paper_betting.strike_rate)} />
                <Metric label="Avg CLV" value={signedPct(data.paper_betting.average_clv)} />
              </dl>
              <p className="mt-2 text-xs muted">Paper bets only — no real bets are placed.</p>
            </Section>
          </div>
        </div>
      )}
    </div>
  )
}

function summariseJob(r: Record<string, unknown>): string {
  const parts: string[] = []
  for (const [k, v] of Object.entries(r)) {
    if (typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean') parts.push(`${k}: ${String(v)}`)
  }
  return parts.slice(0, 8).join(', ') || 'Done'
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt className="muted">{label}</dt>
      <dd className="num font-medium">{value}</dd>
    </>
  )
}

function HighlightCard({ title, opp }: { title: string; opp: Opportunity | null }) {
  return (
    <Section title={title}>
      {!opp ? (
        <EmptyState title="No value candidate available." />
      ) : (
        <div className="space-y-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Link to={`/matches/${opp.fixture_id}`} className="font-semibold">
              {opp.home_team} vs {opp.away_team}
            </Link>
            <span className="text-xs muted">
              {opp.competition} · {localDateTime(opp.kickoff_utc)}
            </span>
          </div>
          <div>
            {opp.market} — <span className="font-medium">{opp.selection}</span> @ {odds(opp.best_odds)}
            {opp.best_bookmaker ? ` (${opp.best_bookmaker})` : ''}
          </div>
          <div className="flex flex-wrap gap-1">
            <StatusBadge status={opp.status} />
            <ValueBadge label={opp.value_label} />
            <EvBadge ev={opp.expected_value} />
            <ScoreChip label="Conf" value={opp.confidence} />
            <ScoreChip label="Data Q" value={opp.data_quality} />
            <ScoreChip label="Value" value={opp.value_score} />
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <span>Model {pct(opp.model_probability)}</span>
            <span>Market {pct(opp.market_probability)}</span>
            <span>Fair {odds(opp.fair_odds)}</span>
          </div>
          <p className="text-xs muted">{opp.explanation}</p>
          {opp.key_factors.length > 0 && (
            <ul className="list-inside list-disc text-xs">
              {opp.key_factors.slice(0, 3).map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Section>
  )
}

function MiniList({ title, items, link }: { title: string; items: Opportunity[]; link: string }) {
  return (
    <Section title={title} actions={<Link to={link} className="text-xs">More</Link>}>
      {items.length === 0 ? (
        <div className="text-xs muted">No candidates.</div>
      ) : (
        <ul className="divide-y divide-slate-100 text-xs dark:divide-slate-800">
          {items.slice(0, 5).map((o) => (
            <li key={o.id} className="flex items-center justify-between gap-2 py-1.5">
              <div className="min-w-0">
                <Link to={`/matches/${o.fixture_id}`} className="block truncate font-medium">
                  {o.home_team} vs {o.away_team}
                </Link>
                <div className="truncate muted">
                  {o.market} {o.selection} @ {odds(o.best_odds)}
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-0.5">
                <EvBadge ev={o.expected_value} />
                <StatusBadge status={o.status} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}
