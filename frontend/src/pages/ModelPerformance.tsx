import { useState } from 'react'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import type { LeaderboardRow } from '@/types'
import { int, localDate, num, signedPct, titleCase } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { StatCard, toneForSigned } from '@/components/StatCard'
import { DataTable, type Column } from '@/components/DataTable'
import { EmptyState, ErrorState, LoadingState, WarningBox } from '@/components/States'
import { CalibrationChart } from '@/components/charts'

export default function ModelPerformance() {
  const [window_, setWindow] = useState<'30' | 'all'>('30')
  const [marketGroup, setMarketGroup] = useState('')
  const [model, setModel] = useState('')
  const days = window_ === '30' ? 30 : undefined
  const perf = useApi((signal) => api.performance({ days, market_group: marketGroup || undefined, model: model || undefined }, signal), [days, marketGroup, model])
  const leaderboard = useApi((signal) => api.leaderboard(signal), [])
  const models = useApi((signal) => api.models(signal), [])

  const p = perf.data?.performance
  const drift = perf.data?.drift

  const lbCols: Column<LeaderboardRow>[] = [
    { key: 'model', header: 'Model', sortValue: (r) => r.model, render: (r) => <span className="font-medium">{r.model}</span> },
    { key: 'version', header: 'Version', sortValue: (r) => r.version, render: (r) => r.version },
    { key: 'group', header: 'Market group', sortValue: (r) => r.market_group, render: (r) => r.market_group },
    { key: 'n', header: 'Predictions', align: 'right', sortValue: (r) => r.predictions, render: (r) => int(r.predictions) },
    { key: 'brier', header: 'Brier', align: 'right', sortValue: (r) => r.brier, render: (r) => num(r.brier, 4) },
    { key: 'll', header: 'Log loss', align: 'right', sortValue: (r) => r.log_loss, render: (r) => num(r.log_loss, 4) },
    { key: 'ece', header: 'ECE', align: 'right', sortValue: (r) => r.ece, render: (r) => num(r.ece, 4) },
    { key: 'auc', header: 'ROC AUC', align: 'right', sortValue: (r) => r.roc_auc, render: (r) => num(r.roc_auc, 3) },
    { key: 'roi', header: 'ROI', align: 'right', sortValue: (r) => r.roi, render: (r) => signedPct(r.roi) },
    { key: 'clv', header: 'CLV', align: 'right', sortValue: (r) => r.clv, render: (r) => signedPct(r.clv) },
    { key: 'period', header: 'Period', render: (r) => <span className="text-xs">{localDate(r.from)} – {localDate(r.to)}</span> },
  ]

  return (
    <div>
      <PageHeader
        title="Model Performance"
        subtitle="Calibration and profitability of the probability models. Statistical analysis is not a guarantee of future results."
        actions={
          <>
            <div role="group" aria-label="Window" className="inline-flex rounded border border-slate-300 dark:border-slate-700">
              <button type="button" className={`px-3 py-1 text-sm ${window_ === '30' ? 'bg-teal-700 text-white' : ''}`} onClick={() => setWindow('30')}>
                Last 30 days
              </button>
              <button type="button" className={`px-3 py-1 text-sm ${window_ === 'all' ? 'bg-teal-700 text-white' : ''}`} onClick={() => setWindow('all')}>
                All time
              </button>
            </div>
            <select className="input w-auto" value={marketGroup} onChange={(e) => setMarketGroup(e.target.value)} aria-label="Market group">
              <option value="">All market groups</option>
              {['match_result', 'goals', 'btts', 'team_goals', 'corners', 'team_corners', 'first_half', 'handicap'].map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
            <select className="input w-auto" value={model} onChange={(e) => setModel(e.target.value)} aria-label="Model">
              <option value="">All models</option>
              {Object.keys(models.data?.active ?? {}).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </>
        }
      />
      <div className="space-y-4">
        {drift && (
          drift.drift_detected ? (
            <WarningBox title="MODEL DRIFT DETECTED">
              Recent Brier {num(drift.recent_brier, 4)} vs historical {num(drift.historical_brier, 4)} (difference {num(drift.difference, 4)}).{drift.reason ? ` ${drift.reason}` : ''}
            </WarningBox>
          ) : (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100">
              <span className="font-semibold">NO DRIFT DETECTED</span> — recent Brier {num(drift.recent_brier, 4)} vs historical {num(drift.historical_brier, 4)}.
            </div>
          )
        )}
        {perf.loading && <LoadingState label="Loading performance" />}
        {perf.error && <ErrorState message={perf.error} onRetry={perf.refetch} />}
        {p && (
          <>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
              <StatCard label="Predictions" value={int(p.n)} tone={p.n === 0 ? 'grey' : 'default'} />
              <StatCard label="Brier" value={num(p.brier, 4)} hint="lower is better" />
              <StatCard label="Log loss" value={num(p.log_loss, 4)} hint="lower is better" />
              <StatCard label="ROC AUC" value={num(p.roc_auc, 3)} />
              <StatCard label="ECE" value={num(p.expected_calibration_error, 4)} hint="calibration error" />
              <StatCard label="Avg CLV" value={signedPct(p.average_clv)} tone={toneForSigned(p.average_clv)} hint={`${p.signals_backed} signals backed`} />
              <StatCard label="Flat ROI (all signals)" value={signedPct(p.flat_roi_all_signals)} tone={toneForSigned(p.flat_roi_all_signals)} />
            </div>
            {p.n === 0 && <EmptyState title="No settled predictions in this window — metrics show DATA UNAVAILABLE." />}
            {perf.data?.note && <p className="text-xs muted">{perf.data.note}</p>}
            <div className="grid gap-4 lg:grid-cols-2">
              <Section title="Calibration curve (reliability diagram)">
                <CalibrationChart bins={p.bins ?? []} />
                {p.bins && p.bins.length > 0 && (
                  <div className="table-wrap mt-2">
                    <table className="table text-xs">
                      <thead>
                        <tr>
                          <th>Bin</th>
                          <th className="text-right">Count</th>
                          <th className="text-right">Mean predicted</th>
                          <th className="text-right">Observed</th>
                        </tr>
                      </thead>
                      <tbody>
                        {p.bins.map((b, i) => (
                          <tr key={i}>
                            <td>
                              {(b.lower * 100).toFixed(0)}–{(b.upper * 100).toFixed(0)}%
                            </td>
                            <td className="text-right num">{b.count}</td>
                            <td className="text-right num">{b.mean_predicted === null ? '—' : `${(b.mean_predicted * 100).toFixed(1)}%`}</td>
                            <td className="text-right num">{b.observed_rate === null ? '—' : `${(b.observed_rate * 100).toFixed(1)}%`}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Section>
              <Section title="Strategy scores">
                {perf.data && Object.keys(perf.data.strategy_scores ?? {}).length === 0 ? (
                  <EmptyState title="No strategy scores available." />
                ) : (
                  <ul className="space-y-1 text-sm">
                    {Object.entries(perf.data?.strategy_scores ?? {}).map(([k, raw]) => {
                      // Scores may arrive as fractions (0..1) or points (0..100); normalise to 0..100.
                      const v = raw <= 1 ? raw * 100 : raw
                      const label = v >= 70 ? 'STRONG' : v >= 45 ? 'MODERATE' : 'WEAK'
                      return (
                        <li key={k} className="flex items-center gap-2">
                          <span className="w-40 shrink-0">{titleCase(k)}</span>
                          <div className="h-2 flex-1 rounded bg-slate-200 dark:bg-slate-700">
                            <div className={`h-full rounded ${v >= 70 ? 'bg-emerald-500' : v >= 45 ? 'bg-amber-400' : 'bg-red-500'}`} style={{ width: `${Math.max(2, Math.min(100, v))}%` }} />
                          </div>
                          <span className="w-10 text-right num">{Math.round(v)}</span>
                          <span className="w-20 text-[10px] font-semibold uppercase muted">{label}</span>
                        </li>
                      )
                    })}
                  </ul>
                )}
                <div className="mt-4 text-xs font-semibold uppercase muted">Active models</div>
                {models.error && <div className="text-xs text-red-700">{models.error}</div>}
                <ul className="mt-1 text-xs">
                  {Object.entries(models.data?.active ?? {}).map(([k, v]) => (
                    <li key={k}>
                      <span className="font-medium">{k}</span>: {v}
                    </li>
                  ))}
                  {models.data && Object.keys(models.data.active).length === 0 && <li className="muted">No active models registered.</li>}
                </ul>
              </Section>
            </div>
          </>
        )}
        <Section title="Model leaderboard">
          {leaderboard.loading && <LoadingState label="Loading leaderboard" />}
          {leaderboard.error && <ErrorState message={leaderboard.error} onRetry={leaderboard.refetch} />}
          {leaderboard.data && <DataTable columns={lbCols} rows={leaderboard.data} rowKey={(r, ) => `${r.model}-${r.version}-${r.market_group}`} defaultSort={{ key: 'brier', dir: 'asc' }} dense emptyMessage="No leaderboard entries yet." />}
        </Section>
      </div>
    </div>
  )
}
