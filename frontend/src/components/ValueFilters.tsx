import type { ValueQuery } from '@/services/api'
import { api } from '@/services/api'
import { useApi } from '@/hooks/useApi'
import { todayIso } from '@/utils/format'

export interface ValueFilterState {
  day: string
  days: number
  min_ev: string
  min_confidence: string
  min_quality: string
  competition: string
  market_group: string
  market: string
  min_odds: string
  max_odds: string
  status: string
}

export const MARKET_GROUPS = ['match_result', 'goals', 'btts', 'team_goals', 'corners', 'team_corners', 'first_half', 'handicap']

export function defaultFilters(overrides: Partial<ValueFilterState> = {}): ValueFilterState {
  return {
    day: todayIso(),
    days: 2,
    min_ev: '',
    min_confidence: '',
    min_quality: '',
    competition: '',
    market_group: '',
    market: '',
    min_odds: '',
    max_odds: '',
    status: 'VALUE_CANDIDATE',
    ...overrides,
  }
}

function numOrUndef(s: string): number | undefined {
  if (s.trim() === '') return undefined
  const n = Number(s)
  return Number.isFinite(n) ? n : undefined
}

export function filtersToQuery(f: ValueFilterState, extra: Partial<ValueQuery> = {}): ValueQuery {
  const minEv = numOrUndef(f.min_ev)
  return {
    day: f.day || undefined,
    days: f.days,
    min_ev: minEv !== undefined ? minEv / 100 : undefined,
    min_confidence: numOrUndef(f.min_confidence),
    min_quality: numOrUndef(f.min_quality),
    competition: f.competition || undefined,
    market_group: f.market_group || undefined,
    market: f.market || undefined,
    min_odds: numOrUndef(f.min_odds),
    max_odds: numOrUndef(f.max_odds),
    status: f.status || undefined,
    movement: true,
    ...extra,
  }
}

interface Props {
  value: ValueFilterState
  onChange: (next: ValueFilterState) => void
  /** Hide the market-group selector on pages that are already group-specific. */
  fixedGroup?: boolean
  /** Hide competition/market filters for the simpler scanner pages. */
  simple?: boolean
}

export function ValueFilters({ value, onChange, fixedGroup = false, simple = false }: Props) {
  const leagues = useApi((signal) => api.leagues(signal), [])
  const markets = useApi((signal) => api.markets(signal), [], { enabled: !simple })

  function set<K extends keyof ValueFilterState>(key: K, v: ValueFilterState[K]) {
    onChange({ ...value, [key]: v })
  }

  const marketOptions = (markets.data ?? []).filter((m) => !value.market_group || value.market_group.split(',').includes(m.group))

  return (
    <div className="card">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        <div>
          <label className="label" htmlFor="f-day">
            Date
          </label>
          <input id="f-day" type="date" className="input" value={value.day} onChange={(e) => set('day', e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="f-days">
            Days ahead
          </label>
          <select id="f-days" className="input" value={value.days} onChange={(e) => set('days', Number(e.target.value))}>
            {[1, 2, 3, 4, 5, 6, 7].map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="f-status">
            Status
          </label>
          <select id="f-status" className="input" value={value.status} onChange={(e) => set('status', e.target.value)}>
            <option value="VALUE_CANDIDATE">Value candidates only</option>
            <option value="">All (incl. NO BET / ODDS UNAVAILABLE)</option>
            <option value="NO_BET">NO BET only</option>
            <option value="ODDS_UNAVAILABLE">ODDS UNAVAILABLE only</option>
          </select>
        </div>
        <div>
          <label className="label" htmlFor="f-min-ev">
            Min EV (%)
          </label>
          <input id="f-min-ev" type="number" step="0.5" className="input" placeholder="e.g. 2" value={value.min_ev} onChange={(e) => set('min_ev', e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="f-min-conf">
            Min confidence
          </label>
          <input id="f-min-conf" type="number" min={0} max={100} className="input" placeholder="0-100" value={value.min_confidence} onChange={(e) => set('min_confidence', e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="f-min-q">
            Min data quality
          </label>
          <input id="f-min-q" type="number" min={0} max={100} className="input" placeholder="0-100" value={value.min_quality} onChange={(e) => set('min_quality', e.target.value)} />
        </div>
        {!simple && (
          <>
            <div>
              <label className="label" htmlFor="f-league">
                League
              </label>
              <select id="f-league" className="input" value={value.competition} onChange={(e) => set('competition', e.target.value)}>
                <option value="">All leagues</option>
                {(leagues.data ?? []).map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.name}
                  </option>
                ))}
              </select>
            </div>
            {!fixedGroup && (
              <div>
                <label className="label" htmlFor="f-group">
                  Market group
                </label>
                <select id="f-group" className="input" value={value.market_group} onChange={(e) => set('market_group', e.target.value)}>
                  <option value="">All groups</option>
                  {MARKET_GROUPS.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="label" htmlFor="f-market">
                Market
              </label>
              <select id="f-market" className="input" value={value.market} onChange={(e) => set('market', e.target.value)}>
                <option value="">All markets</option>
                {marketOptions.map((m) => (
                  <option key={m.key} value={m.key}>
                    {m.name} — {m.selection}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="f-min-odds">
                Min odds
              </label>
              <input id="f-min-odds" type="number" step="0.05" className="input" value={value.min_odds} onChange={(e) => set('min_odds', e.target.value)} />
            </div>
            <div>
              <label className="label" htmlFor="f-max-odds">
                Max odds
              </label>
              <input id="f-max-odds" type="number" step="0.05" className="input" value={value.max_odds} onChange={(e) => set('max_odds', e.target.value)} />
            </div>
          </>
        )}
        <div className="flex items-end">
          <button type="button" className="btn-secondary w-full" onClick={() => onChange(defaultFilters({ market_group: fixedGroup ? value.market_group : '' }))}>
            Reset filters
          </button>
        </div>
      </div>
    </div>
  )
}
