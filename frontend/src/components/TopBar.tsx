import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/services/api'
import type { FixtureSearchItem } from '@/types'
import { localDateTime } from '@/utils/format'
import { useStatus } from '@/hooks/useStatus'

interface Props {
  onToggleSidebar: () => void
}

export function TopBar({ onToggleSidebar }: Props) {
  const navigate = useNavigate()
  const { status, error: statusError } = useStatus()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<FixtureSearchItem[]>([])
  const [open, setOpen] = useState(false)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)
  const [highlight, setHighlight] = useState(0)
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) {
      setResults([])
      setSearchError(null)
      return
    }
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setSearching(true)
      api
        .searchFixtures(q, controller.signal)
        .then((r) => {
          setResults(r.fixtures ?? [])
          setSearchError(null)
          setHighlight(0)
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return
          setSearchError(err instanceof Error ? err.message : 'Search failed')
          setResults([])
        })
        .finally(() => {
          if (!controller.signal.aborted) setSearching(false)
        })
    }, 250)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  function choose(item: FixtureSearchItem) {
    setOpen(false)
    setQuery('')
    navigate(`/matches/${item.fixture_id}`)
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlight((h) => Math.min(h + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlight((h) => Math.max(h - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const item = results[highlight]
      if (item) choose(item)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 dark:border-slate-800 dark:bg-slate-900 md:px-6">
      <button
        type="button"
        className="btn-secondary btn-sm md:hidden"
        aria-label="Toggle navigation"
        onClick={onToggleSidebar}
      >
        Menu
      </button>
      <div ref={boxRef} className="relative w-full max-w-lg">
        <label htmlFor="fixture-search" className="sr-only">
          Search fixtures
        </label>
        <input
          id="fixture-search"
          className="input"
          placeholder="Search fixtures (team name)..."
          value={query}
          autoComplete="off"
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls="fixture-search-results"
          aria-autocomplete="list"
        />
        {open && query.trim().length >= 2 && (
          <ul
            id="fixture-search-results"
            role="listbox"
            className="absolute left-0 right-0 top-full z-30 mt-1 max-h-80 overflow-auto rounded border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800"
          >
            {searching && <li className="px-3 py-2 text-xs muted">Searching...</li>}
            {!searching && searchError && <li className="px-3 py-2 text-xs text-red-700 dark:text-red-300">{searchError}</li>}
            {!searching && !searchError && results.length === 0 && (
              <li className="px-3 py-2 text-xs muted">No fixtures found.</li>
            )}
            {results.map((r, idx) => (
              <li
                key={r.fixture_id}
                role="option"
                aria-selected={idx === highlight}
                className={`cursor-pointer px-3 py-2 text-sm ${
                  idx === highlight ? 'bg-teal-50 dark:bg-teal-900/40' : ''
                }`}
                onMouseEnter={() => setHighlight(idx)}
                onMouseDown={(e) => {
                  e.preventDefault()
                  choose(r)
                }}
              >
                <div className="font-medium">
                  {r.home_team} vs {r.away_team}
                </div>
                <div className="text-xs muted">
                  {r.competition} · {localDateTime(r.kickoff_utc)} · {r.status}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="ml-auto hidden items-center gap-2 text-xs muted sm:flex">
        {statusError ? (
          <span className="chip chip-red">API UNAVAILABLE</span>
        ) : status ? (
          <>
            <span className={`chip ${status.demo ? 'chip-yellow' : 'chip-green'}`}>{status.demo ? 'DEMO' : status.app_mode}</span>
            <span>Last scan: {status.last_scan ? localDateTime(status.last_scan) : 'never'}</span>
          </>
        ) : (
          <span>Connecting...</span>
        )}
      </div>
    </header>
  )
}
