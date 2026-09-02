import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { useToast } from '@/hooks/useToast'
import type { FixtureSearchItem, PaperBet, StakePreview } from '@/types'
import { localDateTime, money, odds, pct, signedPct } from '@/utils/format'
import { PageHeader } from '@/components/PageHeader'
import { DataTable, type Column } from '@/components/DataTable'
import { EmptyState, ErrorState, LoadingState, Spinner } from '@/components/States'
import { BetStatusBadge } from '@/components/Badges'
import { Modal } from '@/components/Modal'

export default function PaperBets() {
  const toast = useToast()
  const [status, setStatus] = useState('')
  const { data, loading, error, refetch } = useApi((signal) => api.paperBets(status || undefined, signal), [status])
  const [settling, setSettling] = useState(false)
  const [showForm, setShowForm] = useState(false)

  async function settle() {
    setSettling(true)
    try {
      const r = await api.settlePaperBets()
      toast.push('success', 'Settlement run', typeof r === 'object' && r ? JSON.stringify(r).slice(0, 200) : 'Done')
      refetch()
    } catch (err) {
      toast.push('error', 'Settlement failed', err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSettling(false)
    }
  }

  const columns: Column<PaperBet>[] = [
    { key: 'placed', header: 'Placed', sortValue: (b) => b.placed_at, render: (b) => <span className="whitespace-nowrap text-xs">{localDateTime(b.placed_at)}</span> },
    {
      key: 'match',
      header: 'Match',
      sortValue: (b) => b.home_team,
      render: (b) => (
        <div>
          <Link to={`/matches/${b.fixture_id}`} className="font-medium">
            {b.home_team} vs {b.away_team}
          </Link>
          <div className="text-xs muted">
            {b.competition} · {localDateTime(b.kickoff_utc)}
          </div>
        </div>
      ),
    },
    { key: 'market', header: 'Market', sortValue: (b) => b.market_key, render: (b) => <div>{b.market_key}<div className="text-xs muted">{b.selection}</div></div> },
    { key: 'odds', header: 'Odds', align: 'right', sortValue: (b) => b.odds, render: (b) => odds(b.odds) },
    { key: 'bk', header: 'Bookmaker', render: (b) => b.bookmaker_key ?? '—' },
    { key: 'stake', header: 'Stake', align: 'right', sortValue: (b) => b.stake, render: (b) => <span>{money(b.stake)}<div className="text-xs muted">{b.stake_method ?? ''}</div></span> },
    { key: 'mp', header: 'Model %', align: 'right', sortValue: (b) => b.model_probability, render: (b) => pct(b.model_probability) },
    { key: 'ev', header: 'EV', align: 'right', sortValue: (b) => b.expected_value, render: (b) => signedPct(b.expected_value) },
    { key: 'status', header: 'Status', sortValue: (b) => b.status, render: (b) => <BetStatusBadge status={b.status} /> },
    { key: 'profit', header: 'Profit', align: 'right', sortValue: (b) => b.profit, render: (b) => (b.profit === null ? <span className="muted">—</span> : <span className={b.profit > 0 ? 'text-emerald-700 dark:text-emerald-300' : b.profit < 0 ? 'text-red-700 dark:text-red-300' : ''}>{money(b.profit)}</span>) },
    { key: 'closing', header: 'Closing', align: 'right', sortValue: (b) => b.closing_odds, render: (b) => odds(b.closing_odds) },
    { key: 'clv', header: 'CLV', align: 'right', sortValue: (b) => b.clv, render: (b) => signedPct(b.clv) },
    { key: 'settled', header: 'Settled', render: (b) => <span className="whitespace-nowrap text-xs">{b.settled_at ? localDateTime(b.settled_at) : '—'}</span> },
    { key: 'notes', header: 'Notes', render: (b) => <span className="text-xs">{b.notes ?? ''}</span> },
  ]

  return (
    <div>
      <PageHeader
        title="Paper Bets"
        subtitle="Tracked for evaluation only — no real bets are placed."
        actions={
          <>
            <button type="button" className="btn-secondary" onClick={settle} disabled={settling}>
              {settling && <Spinner />}
              Settle open bets
            </button>
            <button type="button" className="btn-primary" onClick={() => setShowForm(true)}>
              Record bet
            </button>
          </>
        }
      />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <label className="text-xs muted" htmlFor="pb-status">
          Status
        </label>
        <select id="pb-status" className="input w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="won">Won</option>
          <option value="lost">Lost</option>
          <option value="push">Push</option>
        </select>
      </div>
      {loading && <LoadingState label="Loading paper bets" />}
      {error && !loading && <ErrorState message={error} onRetry={refetch} />}
      {data && !loading && !error && (
        data.length === 0 ? (
          <EmptyState title="No paper bets recorded.">Record one from a value candidate or with the “Record bet” button.</EmptyState>
        ) : (
          <div className="card">
            <DataTable columns={columns} rows={data} rowKey={(b) => b.id} defaultSort={{ key: 'placed', dir: 'desc' }} dense />
          </div>
        )
      )}
      {showForm && <RecordBetModal onClose={() => setShowForm(false)} onCreated={refetch} />}
    </div>
  )
}

function RecordBetModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const toast = useToast()
  const markets = useApi((signal) => api.markets(signal), [])
  const bookmakers = useApi((signal) => api.bookmakers(signal), [])
  const [q, setQ] = useState('')
  const [results, setResults] = useState<FixtureSearchItem[]>([])
  const [fixture, setFixture] = useState<FixtureSearchItem | null>(null)
  const [marketKey, setMarketKey] = useState('')
  const [selection, setSelection] = useState('')
  const [oddsStr, setOddsStr] = useState('')
  const [probStr, setProbStr] = useState('')
  const [stake, setStake] = useState('')
  const [method, setMethod] = useState('')
  const [bookmaker, setBookmaker] = useState('')
  const [notes, setNotes] = useState('')
  const [preview, setPreview] = useState<StakePreview | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const term = q.trim()
    if (term.length < 2) {
      setResults([])
      return
    }
    const controller = new AbortController()
    const t = window.setTimeout(() => {
      api.searchFixtures(term, controller.signal).then((r) => setResults(r.fixtures)).catch(() => undefined)
    }, 250)
    return () => {
      window.clearTimeout(t)
      controller.abort()
    }
  }, [q])

  useEffect(() => {
    const m = markets.data?.find((x) => x.key === marketKey)
    if (m) setSelection(m.selection)
  }, [marketKey, markets.data])

  const oddsNum = Number(oddsStr)
  const probNum = Number(probStr) / 100
  const canPreview = Number.isFinite(oddsNum) && oddsNum > 1 && Number.isFinite(probNum) && probNum > 0 && probNum < 1

  useEffect(() => {
    if (!canPreview) {
      setPreview(null)
      return
    }
    const controller = new AbortController()
    const t = window.setTimeout(() => {
      api
        .stakePreview(probNum, oddsNum, controller.signal)
        .then((p) => {
          setPreview(p)
          setMethod((m) => m || p.default_method)
        })
        .catch(() => setPreview(null))
    }, 250)
    return () => {
      window.clearTimeout(t)
      controller.abort()
    }
  }, [canPreview, probNum, oddsNum])

  useEffect(() => {
    if (!preview || !method) return
    const v = preview.stakes[method as keyof StakePreview['stakes']]
    if (typeof v === 'number') setStake(v.toFixed(2))
  }, [preview, method])

  async function submit() {
    setError(null)
    if (!fixture) return setError('Choose a fixture.')
    if (!marketKey) return setError('Choose a market.')
    if (!selection) return setError('Enter a selection.')
    if (!Number.isFinite(oddsNum) || oddsNum <= 1) return setError('Odds must be greater than 1.')
    setSubmitting(true)
    try {
      await api.createPaperBet({
        fixture_id: fixture.fixture_id,
        market_key: marketKey,
        selection,
        odds: oddsNum,
        stake: Number(stake) > 0 ? Number(stake) : undefined,
        bookmaker_key: bookmaker || undefined,
        notes: notes || undefined,
        stake_method: method || undefined,
      })
      toast.push('success', 'Paper bet recorded')
      onCreated()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not record bet')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Record paper bet"
      wide
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
            Cancel
          </button>
          <button type="button" className="btn-primary" onClick={submit} disabled={submitting}>
            {submitting && <Spinner />}
            Record bet
          </button>
        </>
      }
    >
      <div className="grid gap-3 text-sm md:grid-cols-2">
        <div className="md:col-span-2">
          <label className="label" htmlFor="rb-fixture">
            Fixture
          </label>
          {fixture ? (
            <div className="flex items-center justify-between rounded border border-slate-200 px-2 py-1.5 dark:border-slate-700">
              <span>
                {fixture.home_team} vs {fixture.away_team} <span className="text-xs muted">· {fixture.competition} · {localDateTime(fixture.kickoff_utc)}</span>
              </span>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setFixture(null)}>
                Change
              </button>
            </div>
          ) : (
            <>
              <input id="rb-fixture" className="input" placeholder="Search team..." value={q} onChange={(e) => setQ(e.target.value)} />
              {results.length > 0 && (
                <ul className="mt-1 max-h-32 overflow-auto rounded border border-slate-200 text-xs dark:border-slate-700">
                  {results.map((r) => (
                    <li key={r.fixture_id}>
                      <button type="button" className="w-full px-2 py-1 text-left hover:bg-slate-50 dark:hover:bg-slate-800" onClick={() => setFixture(r)}>
                        {r.home_team} vs {r.away_team} · {r.competition} · {localDateTime(r.kickoff_utc)}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
        <div>
          <label className="label" htmlFor="rb-market">
            Market
          </label>
          <select id="rb-market" className="input" value={marketKey} onChange={(e) => setMarketKey(e.target.value)}>
            <option value="">Select market</option>
            {(markets.data ?? []).map((m) => (
              <option key={m.key} value={m.key}>
                {m.group} · {m.name} — {m.selection}
              </option>
            ))}
          </select>
          {markets.error && <div className="text-xs text-red-700">{markets.error}</div>}
        </div>
        <div>
          <label className="label" htmlFor="rb-selection">
            Selection
          </label>
          <input id="rb-selection" className="input" value={selection} onChange={(e) => setSelection(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="rb-odds">
            Odds (decimal)
          </label>
          <input id="rb-odds" type="number" step="0.01" min="1.01" className="input" value={oddsStr} onChange={(e) => setOddsStr(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="rb-prob">
            Your probability estimate (%) — for stake preview
          </label>
          <input id="rb-prob" type="number" step="0.5" min="1" max="99" className="input" value={probStr} onChange={(e) => setProbStr(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="rb-method">
            Stake method
          </label>
          <select id="rb-method" className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="">Default</option>
            {['flat', 'percentage', 'quarter_kelly', 'half_kelly', 'full_kelly'].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="rb-stake">
            Stake
          </label>
          <input id="rb-stake" type="number" step="0.01" min="0" className="input" value={stake} onChange={(e) => setStake(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="rb-bk">
            Bookmaker
          </label>
          <select id="rb-bk" className="input" value={bookmaker} onChange={(e) => setBookmaker(e.target.value)}>
            <option value="">Not specified</option>
            {(bookmakers.data ?? []).map((b) => (
              <option key={b.key} value={b.key}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="rb-notes">
            Notes
          </label>
          <input id="rb-notes" className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <div className="rounded border border-slate-200 p-2 text-xs md:col-span-2 dark:border-slate-700">
          <div className="font-semibold uppercase muted">Stake preview</div>
          {!preview ? (
            <div className="muted">{canPreview ? 'Loading...' : 'Enter odds and a probability estimate to preview stakes.'}</div>
          ) : (
            <div className="grid grid-cols-2 gap-1 sm:grid-cols-3">
              {(Object.keys(preview.stakes) as (keyof StakePreview['stakes'])[]).map((k) => (
                <button key={k} type="button" className={`rounded px-1 py-0.5 text-left hover:bg-slate-100 dark:hover:bg-slate-800 ${method === k ? 'font-semibold text-teal-800 dark:text-teal-200' : ''}`} onClick={() => setMethod(k)}>
                  {k}: {money(preview.stakes[k])}
                </button>
              ))}
              <span className="muted">Kelly {pct(preview.kelly_fraction, 2)} · bankroll {money(preview.bankroll)}</span>
            </div>
          )}
        </div>
        {error && (
          <div role="alert" className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800 md:col-span-2 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}
      </div>
    </Modal>
  )
}
