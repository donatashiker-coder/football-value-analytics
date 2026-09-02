import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { useToast } from '@/hooks/useToast'
import type { BacktestRunRequest } from '@/types'
import { localDateTime, money, num, pct, signedPct, titleCase } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { EmptyState, ErrorState, LoadingState, Spinner } from '@/components/States'
import { DemoBadge } from '@/components/DemoBanner'

interface FormState {
  strategy: string
  competition_codes: string[]
  start: string
  end: string
  min_ev: string
  min_confidence: string
  min_data_quality: string
  min_odds: string
  max_odds: string
  min_sample_size: string
  stake_method: string
  flat_stake: string
  starting_bankroll: string
  corner_distribution: string
  min_expected_corners: string
  min_expected_goals: string
  exclude_early_red_cards: boolean
  one_bet_per_fixture: boolean
}

const DEFAULT_FORM: FormState = {
  strategy: '',
  competition_codes: [],
  start: '',
  end: '',
  min_ev: '2',
  min_confidence: '50',
  min_data_quality: '50',
  min_odds: '1.3',
  max_odds: '6',
  min_sample_size: '5',
  stake_method: 'flat',
  flat_stake: '10',
  starting_bankroll: '1000',
  corner_distribution: '',
  min_expected_corners: '',
  min_expected_goals: '',
  exclude_early_red_cards: true,
  one_bet_per_fixture: true,
}

function optNum(s: string): number | undefined {
  if (s.trim() === '') return undefined
  const n = Number(s)
  return Number.isFinite(n) ? n : undefined
}

export default function Backtesting() {
  const navigate = useNavigate()
  const toast = useToast()
  const list = useApi((signal) => api.backtests(undefined, signal), [])
  const comparison = useApi((signal) => api.backtestComparison(signal), [])
  const leagues = useApi((signal) => api.leagues(signal), [])
  const [form, setForm] = useState<FormState>(DEFAULT_FORM)
  const [running, setRunning] = useState(false)
  const [runError, setRunError] = useState<string | null>(null)

  const strategies = list.data?.strategies ?? []
  const strategy = form.strategy || strategies[0] || ''

  function set<K extends keyof FormState>(k: K, v: FormState[K]) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function run() {
    setRunError(null)
    if (!strategy) {
      setRunError('Choose a strategy.')
      return
    }
    const body: BacktestRunRequest = {
      strategy,
      competition_codes: form.competition_codes.length > 0 ? form.competition_codes : undefined,
      start: form.start || undefined,
      end: form.end || undefined,
      min_ev: (optNum(form.min_ev) ?? 0) / 100,
      min_confidence: optNum(form.min_confidence) ?? 0,
      min_data_quality: optNum(form.min_data_quality) ?? 0,
      min_odds: optNum(form.min_odds) ?? 1.01,
      max_odds: optNum(form.max_odds) ?? 100,
      min_sample_size: optNum(form.min_sample_size) ?? 0,
      stake_method: form.stake_method,
      flat_stake: optNum(form.flat_stake) ?? 10,
      starting_bankroll: optNum(form.starting_bankroll) ?? 1000,
      corner_distribution: form.corner_distribution || undefined,
      min_expected_corners: optNum(form.min_expected_corners),
      min_expected_goals: optNum(form.min_expected_goals),
      exclude_early_red_cards: form.exclude_early_red_cards,
      one_bet_per_fixture: form.one_bet_per_fixture,
    }
    setRunning(true)
    try {
      const result = await api.runBacktest(body)
      toast.push('success', 'Backtest complete', `${result.summary?.bets ?? 0} bets · ROI ${signedPct(result.summary?.roi)}`)
      list.refetch()
      comparison.refetch()
      navigate(`/backtests/${result.id}`)
    } catch (err) {
      setRunError(err instanceof Error ? err.message : 'Backtest failed')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <PageHeader title="Backtesting" subtitle="Evaluate strategies on historical fixtures and closing odds. Past performance is not a guarantee of future results." />
      <div className="space-y-4">
        <Section title="Run a backtest">
          {list.error && <ErrorState message={list.error} onRetry={list.refetch} />}
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <Field label="Strategy" id="bt-strategy">
              <select id="bt-strategy" className="input" value={strategy} onChange={(e) => set('strategy', e.target.value)}>
                {strategies.length === 0 && <option value="">No strategies available</option>}
                {strategies.map((s) => (
                  <option key={s} value={s}>
                    {titleCase(s)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Leagues (all if none)" id="bt-leagues">
              <select
                id="bt-leagues"
                className="input"
                multiple
                size={3}
                value={form.competition_codes}
                onChange={(e) => set('competition_codes', Array.from(e.target.selectedOptions).map((o) => o.value))}
              >
                {(leagues.data ?? []).map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Start date" id="bt-start">
              <input id="bt-start" type="date" className="input" value={form.start} onChange={(e) => set('start', e.target.value)} />
            </Field>
            <Field label="End date" id="bt-end">
              <input id="bt-end" type="date" className="input" value={form.end} onChange={(e) => set('end', e.target.value)} />
            </Field>
            <NumField label="Min EV (%)" id="bt-min-ev" value={form.min_ev} onChange={(v) => set('min_ev', v)} step="0.5" />
            <NumField label="Min confidence" id="bt-min-conf" value={form.min_confidence} onChange={(v) => set('min_confidence', v)} />
            <NumField label="Min data quality" id="bt-min-dq" value={form.min_data_quality} onChange={(v) => set('min_data_quality', v)} />
            <NumField label="Min odds" id="bt-min-odds" value={form.min_odds} onChange={(v) => set('min_odds', v)} step="0.05" />
            <NumField label="Max odds" id="bt-max-odds" value={form.max_odds} onChange={(v) => set('max_odds', v)} step="0.05" />
            <NumField label="Min sample size" id="bt-min-sample" value={form.min_sample_size} onChange={(v) => set('min_sample_size', v)} />
            <Field label="Stake method" id="bt-stake-method">
              <select id="bt-stake-method" className="input" value={form.stake_method} onChange={(e) => set('stake_method', e.target.value)}>
                {['flat', 'percentage', 'quarter_kelly', 'half_kelly', 'full_kelly'].map((m) => (
                  <option key={m} value={m}>
                    {titleCase(m)}
                  </option>
                ))}
              </select>
            </Field>
            <NumField label="Flat stake" id="bt-flat" value={form.flat_stake} onChange={(v) => set('flat_stake', v)} step="1" />
            <NumField label="Starting bankroll" id="bt-bankroll" value={form.starting_bankroll} onChange={(v) => set('starting_bankroll', v)} step="10" />
            <Field label="Corner distribution" id="bt-corner-dist">
              <select id="bt-corner-dist" className="input" value={form.corner_distribution} onChange={(e) => set('corner_distribution', e.target.value)}>
                <option value="">Default</option>
                <option value="poisson">Poisson</option>
                <option value="negative_binomial">Negative binomial</option>
              </select>
            </Field>
            <NumField label="Min expected corners" id="bt-min-corners" value={form.min_expected_corners} onChange={(v) => set('min_expected_corners', v)} step="0.5" />
            <NumField label="Min expected goals" id="bt-min-goals" value={form.min_expected_goals} onChange={(v) => set('min_expected_goals', v)} step="0.1" />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.exclude_early_red_cards} onChange={(e) => set('exclude_early_red_cards', e.target.checked)} />
              Exclude early red cards
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.one_bet_per_fixture} onChange={(e) => set('one_bet_per_fixture', e.target.checked)} />
              One bet per fixture
            </label>
          </div>
          {runError && (
            <div role="alert" className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {runError}
            </div>
          )}
          <div className="mt-3 flex items-center gap-3">
            <button type="button" className="btn-primary" onClick={run} disabled={running || !strategy}>
              {running && <Spinner />}
              {running ? 'Running backtest (this can take up to a minute)...' : 'Run backtest'}
            </button>
            <button type="button" className="btn-secondary" onClick={() => setForm(DEFAULT_FORM)} disabled={running}>
              Reset form
            </button>
          </div>
        </Section>

        <Section title="Strategy comparison (latest backtest per strategy)">
          {comparison.loading && <LoadingState label="Loading comparison" />}
          {comparison.error && <ErrorState message={comparison.error} onRetry={comparison.refetch} />}
          {comparison.data && (
            comparison.data.length === 0 ? (
              <EmptyState title="No backtests yet. Run one above." />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Strategy</th>
                      <th className="text-right">Bets</th>
                      <th className="text-right">Win %</th>
                      <th className="text-right">ROI</th>
                      <th className="text-right">CLV</th>
                      <th className="text-right">Max drawdown</th>
                      <th className="text-right">Avg odds</th>
                      <th>Created</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.data.map((r) => (
                      <tr key={r.backtest_id}>
                        <td>
                          {titleCase(r.strategy)} <DemoBadge show={r.is_demo} />
                        </td>
                        <td className="text-right num">{r.bets}</td>
                        <td className="text-right num">{pct(r.strike_rate)}</td>
                        <td className={`text-right num font-medium ${roiClass(r.roi)}`}>{signedPct(r.roi)}</td>
                        <td className="text-right num">{signedPct(r.clv)}</td>
                        <td className="text-right num">{money(r.max_drawdown)}</td>
                        <td className="text-right num">{num(r.average_odds)}</td>
                        <td className="text-xs">{localDateTime(r.created_at)}</td>
                        <td>
                          <Link to={`/backtests/${r.backtest_id}`} className="btn-secondary btn-sm">
                            Open
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}
        </Section>

        <Section title="Past backtests">
          {list.loading && <LoadingState label="Loading backtests" />}
          {list.data && (
            list.data.backtests.length === 0 ? (
              <EmptyState title="No backtests stored." />
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Name</th>
                      <th>Strategy</th>
                      <th>Status</th>
                      <th className="text-right">Bets</th>
                      <th className="text-right">ROI</th>
                      <th className="text-right">Profit</th>
                      <th>Model</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.data.backtests.map((b) => (
                      <tr key={b.id}>
                        <td>
                          <Link to={`/backtests/${b.id}`}>#{b.id}</Link>
                        </td>
                        <td>
                          {b.name} <DemoBadge show={b.is_demo} />
                        </td>
                        <td>{titleCase(b.strategy)}</td>
                        <td>
                          <span className={`chip ${b.status === 'completed' ? 'chip-green' : b.status === 'failed' ? 'chip-red' : 'chip-grey'}`}>{b.status}</span>
                        </td>
                        <td className="text-right num">{b.summary?.bets ?? '—'}</td>
                        <td className={`text-right num ${roiClass(b.summary?.roi ?? null)}`}>{signedPct(b.summary?.roi)}</td>
                        <td className="text-right num">{money(b.summary?.profit)}</td>
                        <td className="text-xs">{b.model_version ?? '—'}</td>
                        <td className="text-xs">{localDateTime(b.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          )}
        </Section>
      </div>
    </div>
  )
}

export function roiClass(v: number | null | undefined): string {
  if (v === null || v === undefined) return 'muted'
  if (v > 0.005) return 'text-emerald-700 dark:text-emerald-300'
  if (v < -0.005) return 'text-red-700 dark:text-red-300'
  return 'text-amber-700 dark:text-amber-300'
}

function Field({ label, id, children }: { label: string; id: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="label" htmlFor={id}>
        {label}
      </label>
      {children}
    </div>
  )
}

function NumField({ label, id, value, onChange, step = '1' }: { label: string; id: string; value: string; onChange: (v: string) => void; step?: string }) {
  return (
    <Field label={label} id={id}>
      <input id={id} type="number" step={step} className="input" value={value} onChange={(e) => onChange(e.target.value)} />
    </Field>
  )
}
