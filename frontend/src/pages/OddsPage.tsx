import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import type { FixtureSearchItem, OddsMarketRow } from '@/types'
import { localDateTime, odds, pct, todayIso } from '@/utils/format'
import { PageHeader, Section } from '@/components/PageHeader'
import { DataTable, type Column } from '@/components/DataTable'
import { EmptyState, ErrorState, LoadingState } from '@/components/States'
import { FreshnessChip } from '@/components/FreshnessChip'
import { OddsHistoryChart } from '@/components/charts'

export default function OddsPage() {
  const { fixtureId } = useParams()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [results, setResults] = useState<FixtureSearchItem[]>([])
  const [searchError, setSearchError] = useState<string | null>(null)
  const today = useApi((signal) => api.fixturesToday({ day: todayIso(), days: 2 }, signal), [])
  const bookmakers = useApi((signal) => api.bookmakers(signal), [])

  useEffect(() => {
    const term = q.trim()
    if (term.length < 2) {
      setResults([])
      return
    }
    const controller = new AbortController()
    const t = window.setTimeout(() => {
      api
        .searchFixtures(term, controller.signal)
        .then((r) => {
          setResults(r.fixtures)
          setSearchError(null)
        })
        .catch((err: unknown) => {
          if (!controller.signal.aborted) setSearchError(err instanceof Error ? err.message : 'Search failed')
        })
    }, 250)
    return () => {
      window.clearTimeout(t)
      controller.abort()
    }
  }, [q])

  return (
    <div>
      <PageHeader title="Odds" subtitle="Compare bookmaker prices, overround and movement for a fixture." />
      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        <Section title="Find a fixture" className="lg:col-span-2">
          <label className="label" htmlFor="odds-q">
            Search
          </label>
          <input id="odds-q" className="input" placeholder="Team name..." value={q} onChange={(e) => setQ(e.target.value)} />
          {searchError && <div className="mt-1 text-xs text-red-700">{searchError}</div>}
          {results.length > 0 && (
            <ul className="mt-2 max-h-40 divide-y divide-slate-100 overflow-auto text-sm dark:divide-slate-800">
              {results.map((r) => (
                <li key={r.fixture_id}>
                  <button type="button" className="w-full py-1 text-left hover:bg-slate-50 dark:hover:bg-slate-800" onClick={() => navigate(`/odds/${r.fixture_id}`)}>
                    {r.home_team} vs {r.away_team} <span className="text-xs muted">· {r.competition} · {localDateTime(r.kickoff_utc)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 text-xs font-semibold uppercase muted">Upcoming (next 2 days)</div>
          {today.loading && <LoadingState label="Loading fixtures" />}
          {today.error && <ErrorState message={today.error} onRetry={today.refetch} />}
          {today.data && (
            today.data.fixtures.length === 0 ? (
              <div className="text-xs muted">No upcoming fixtures.</div>
            ) : (
              <ul className="mt-1 max-h-48 divide-y divide-slate-100 overflow-auto text-sm dark:divide-slate-800">
                {today.data.fixtures.map((f) => (
                  <li key={f.fixture_id}>
                    <button type="button" className={`w-full py-1 text-left hover:bg-slate-50 dark:hover:bg-slate-800 ${String(f.fixture_id) === fixtureId ? 'font-semibold text-teal-800 dark:text-teal-200' : ''}`} onClick={() => navigate(`/odds/${f.fixture_id}`)}>
                      {f.home_team} vs {f.away_team} <span className="text-xs muted">· {f.competition} · {localDateTime(f.kickoff_utc)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )
          )}
        </Section>
        <Section title="Bookmakers">
          {bookmakers.loading && <LoadingState label="Loading" />}
          {bookmakers.error && <ErrorState message={bookmakers.error} onRetry={bookmakers.refetch} />}
          {bookmakers.data && (
            <ul className="space-y-1 text-xs">
              {bookmakers.data.map((b) => (
                <li key={b.key} className="flex items-center justify-between">
                  <span>{b.name}</span>
                  <span className="flex gap-1">
                    {b.is_exchange && <span className="chip chip-blue">EXCHANGE</span>}
                    {b.enabled ? <span className="chip chip-green">ENABLED</span> : <span className="chip chip-grey">DISABLED</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
      {fixtureId ? <FixtureOddsPanel fixtureId={fixtureId} /> : <EmptyState title="Select a fixture to view its odds." />}
    </div>
  )
}

function FixtureOddsPanel({ fixtureId }: { fixtureId: string }) {
  const { data, loading, error, refetch } = useApi((signal) => api.odds(fixtureId, signal), [fixtureId])
  const [historyKey, setHistoryKey] = useState<string>('')

  useEffect(() => {
    if (data && !historyKey) {
      const first = Object.keys(data.history ?? {})[0]
      if (first) setHistoryKey(first)
    }
  }, [data, historyKey])

  if (loading) return <LoadingState label="Loading odds" />
  if (error) return <ErrorState message={error} onRetry={refetch} />
  if (!data) return null

  const columns: Column<OddsMarketRow>[] = [
    { key: 'market', header: 'Market', sortValue: (m) => m.market, render: (m) => <div>{m.market}<div className="text-xs muted">{m.group}</div></div> },
    { key: 'selection', header: 'Selection', sortValue: (m) => m.selection, render: (m) => m.selection },
    { key: 'best', header: 'Best', align: 'right', sortValue: (m) => m.best_odds, render: (m) => <span className="font-medium">{odds(m.best_odds)}</span> },
    { key: 'bk', header: 'Bookmaker', render: (m) => m.best_bookmaker ?? '—' },
    { key: 'median', header: 'Median', align: 'right', sortValue: (m) => m.median_odds, render: (m) => odds(m.median_odds) },
    { key: 'min', header: 'Min', align: 'right', sortValue: (m) => m.min_odds, render: (m) => odds(m.min_odds) },
    { key: 'max', header: 'Max', align: 'right', sortValue: (m) => m.max_odds, render: (m) => odds(m.max_odds) },
    { key: 'n', header: 'Books', align: 'right', sortValue: (m) => m.bookmaker_count, render: (m) => m.bookmaker_count },
    { key: 'implied', header: 'Raw implied', align: 'right', sortValue: (m) => m.raw_implied, render: (m) => pct(m.raw_implied) },
    { key: 'mp', header: 'Market prob.', align: 'right', sortValue: (m) => m.market_probability, render: (m) => pct(m.market_probability) },
    { key: 'over', header: 'Overround', align: 'right', sortValue: (m) => m.overround, render: (m) => pct(m.overround, 2) },
    { key: 'age', header: 'Freshness', sortValue: (m) => m.age_hours, render: (m) => <FreshnessChip hoursOld={m.age_hours} /> },
    {
      key: 'move',
      header: 'Movement',
      render: (m) => {
        const mv = data.movement?.[m.market_key]
        if (!mv) return <span className="chip chip-grey">N/A</span>
        return (
          <span className="text-xs">
            {odds(mv.opening)} → {odds(mv.current)} <span className="muted">({mv.direction})</span>
          </span>
        )
      },
    },
  ]

  const historyKeys = Object.keys(data.history ?? {})

  return (
    <div className="space-y-4">
      <Section title={`Odds for fixture #${data.fixture_id}`} actions={<Link to={`/matches/${data.fixture_id}`} className="text-xs">Match page</Link>}>
        {data.markets.length === 0 ? (
          <EmptyState title="ODDS UNAVAILABLE for this fixture." />
        ) : (
          <DataTable
            columns={columns}
            rows={data.markets}
            rowKey={(m) => m.market_key}
            dense
            expand={(m) => (
              <div className="flex flex-wrap gap-2 text-xs">
                {m.prices.length === 0 && <span className="muted">No bookmaker prices.</span>}
                {m.prices.map((p) => (
                  <span key={p.bookmaker} className={`rounded border px-2 py-0.5 ${p.bookmaker === m.best_bookmaker ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-900/40' : 'border-slate-200 dark:border-slate-700'}`}>
                    {p.bookmaker}: <span className="num font-medium">{odds(p.odds)}</span>
                  </span>
                ))}
              </div>
            )}
          />
        )}
      </Section>
      <Section
        title="Odds movement"
        actions={
          historyKeys.length > 0 ? (
            <select className="input w-auto text-xs" value={historyKey} onChange={(e) => setHistoryKey(e.target.value)} aria-label="Market for history chart">
              {historyKeys.map((k) => (
                <option key={k} value={k}>
                  {data.markets.find((m) => m.market_key === k)?.market ?? k} — {data.markets.find((m) => m.market_key === k)?.selection ?? ''}
                </option>
              ))}
            </select>
          ) : undefined
        }
      >
        <OddsHistoryChart history={historyKey ? data.history[historyKey] ?? [] : []} />
      </Section>
      {data.unavailable_markets.length > 0 && (
        <Section title="Unavailable markets">
          <div className="flex flex-wrap gap-1">
            {data.unavailable_markets.map((m) => (
              <span key={m} className="chip chip-grey">
                {m} · ODDS UNAVAILABLE
              </span>
            ))}
          </div>
        </Section>
      )}
    </div>
  )
}
