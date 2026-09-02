import type {
  Bankroll,
  BacktestComparisonRow,
  BacktestDetail,
  BacktestList,
  BacktestRunRequest,
  Bookmaker,
  Dashboard,
  DataHealth,
  DataSources,
  ExplainResponse,
  FixtureDetail,
  FixtureOdds,
  FixtureSearch,
  FixturesToday,
  Health,
  LeaderboardRow,
  League,
  LeagueDetail,
  LeagueSettings,
  MarketDef,
  ModelHealth,
  ModelsInfo,
  OpportunityList,
  PaperBet,
  PaperBetCreate,
  PerformanceMetrics,
  PerformanceResponse,
  ScanSummary,
  ScannerExpected,
  SettingsResponse,
  SettingsValue,
  StakePreview,
  Status,
  TeamDetail,
  TeamListItem,
} from '@/types'

export const API_BASE = '/api'

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

export type QueryValue = string | number | boolean | null | undefined

export function buildQuery(params?: Record<string, QueryValue>): string {
  if (!params) return ''
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export function apiUrl(path: string, params?: Record<string, QueryValue>): string {
  return `${API_BASE}${path}${buildQuery(params)}`
}

function extractDetail(body: unknown): string | null {
  if (!body || typeof body !== 'object') return null
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (d && typeof d === 'object' && 'msg' in d) {
          const loc = Array.isArray((d as { loc?: unknown[] }).loc)
            ? (d as { loc: unknown[] }).loc.join('.')
            : ''
          return `${loc ? loc + ': ' : ''}${String((d as { msg: unknown }).msg)}`
        }
        return JSON.stringify(d)
      })
      .join('; ')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return null
}

async function request<T>(
  method: string,
  path: string,
  options: { params?: Record<string, QueryValue>; body?: unknown; signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<T> {
  const url = apiUrl(path, options.params)
  const controller = new AbortController()
  const timeout = options.timeoutMs ?? 30000
  const timer = window.setTimeout(() => controller.abort(), timeout)
  if (options.signal) {
    options.signal.addEventListener('abort', () => controller.abort(), { once: true })
  }
  let response: Response
  try {
    response = await fetch(url, {
      method,
      headers: options.body !== undefined ? { 'Content-Type': 'application/json', Accept: 'application/json' } : { Accept: 'application/json' },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    })
  } catch (err) {
    window.clearTimeout(timer)
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(0, options.signal?.aborted ? 'Request cancelled' : 'Request timed out')
    }
    throw new ApiError(0, 'API unavailable - could not reach the server')
  }
  window.clearTimeout(timer)

  const contentType = response.headers.get('content-type') ?? ''
  let payload: unknown = null
  if (contentType.includes('application/json')) {
    try {
      payload = await response.json()
    } catch {
      payload = null
    }
  } else {
    try {
      payload = await response.text()
    } catch {
      payload = null
    }
  }

  if (!response.ok) {
    const detail = extractDetail(payload)
    const message =
      detail ??
      (response.status === 503
        ? 'Service unavailable (database or provider may be down)'
        : `Request failed with status ${response.status}`)
    throw new ApiError(response.status, message, payload)
  }
  return payload as T
}

const get = <T,>(path: string, params?: Record<string, QueryValue>, signal?: AbortSignal) =>
  request<T>('GET', path, { params, signal })
const post = <T,>(path: string, body?: unknown, timeoutMs?: number) => request<T>('POST', path, { body, timeoutMs })
const put = <T,>(path: string, body?: unknown) => request<T>('PUT', path, { body })
const patch = <T,>(path: string, body?: unknown) => request<T>('PATCH', path, { body })

export interface ValueQuery extends Record<string, QueryValue> {
  day?: string
  days?: number
  min_ev?: number
  min_confidence?: number
  min_quality?: number
  competition?: string
  market_group?: string
  market?: string
  min_odds?: number
  max_odds?: number
  status?: string
  selection?: string
  limit?: number
  movement?: boolean
}

export const api = {
  // system
  health: (signal?: AbortSignal) => get<Health>('/health', undefined, signal),
  status: (signal?: AbortSignal) => get<Status>('/status', undefined, signal),
  dataHealth: (signal?: AbortSignal) => get<DataHealth>('/data-health', undefined, signal),
  modelHealth: (signal?: AbortSignal) => get<ModelHealth>('/model-health', undefined, signal),

  // dashboard
  dashboard: (signal?: AbortSignal) => get<Dashboard>('/dashboard', undefined, signal),

  // fixtures
  fixturesToday: (params: { day?: string; days?: number; competition?: string }, signal?: AbortSignal) =>
    get<FixturesToday>('/fixtures/today', params, signal),
  searchFixtures: (q: string, signal?: AbortSignal) => get<FixtureSearch>('/fixtures/search', { q }, signal),
  fixture: (id: number | string, signal?: AbortSignal) => get<FixtureDetail>(`/fixtures/${id}`, undefined, signal),

  // value & scanners
  value: (params: ValueQuery, signal?: AbortSignal) => get<OpportunityList>('/value', params, signal),
  valueToday: (signal?: AbortSignal) => get<OpportunityList>('/value/today', undefined, signal),
  goals: (params: ValueQuery, signal?: AbortSignal) => get<OpportunityList>('/goals', params, signal),
  corners: (params: ValueQuery, signal?: AbortSignal) => get<OpportunityList>('/corners', params, signal),
  lowScoring: (params: ValueQuery, signal?: AbortSignal) => get<OpportunityList>('/low-scoring', params, signal),
  scannersExpected: (params: { day?: string; days?: number }, signal?: AbortSignal) =>
    get<ScannerExpected>('/scanners/expected', params, signal),
  valueExportUrl: (params: { day?: string; days?: number; fmt: 'csv' | 'json' }) => apiUrl('/value/export', params),

  // teams
  teams: (params: { q?: string; competition?: string; limit?: number }, signal?: AbortSignal) =>
    get<TeamListItem[]>('/teams', params, signal),
  team: (id: number | string, signal?: AbortSignal) => get<TeamDetail>(`/teams/${id}`, undefined, signal),

  // leagues
  leagues: (signal?: AbortSignal) => get<League[]>('/leagues', undefined, signal),
  league: (code: string, signal?: AbortSignal) => get<LeagueDetail>(`/leagues/${code}`, undefined, signal),
  updateLeagueSettings: (code: string, body: Partial<LeagueSettings & { enabled: boolean }>) =>
    patch<League>(`/leagues/${code}/settings`, body),

  // odds
  odds: (fixtureId: number | string, signal?: AbortSignal) => get<FixtureOdds>(`/odds/${fixtureId}`, undefined, signal),
  bookmakers: (signal?: AbortSignal) => get<Bookmaker[]>('/bookmakers', undefined, signal),
  markets: (signal?: AbortSignal) => get<MarketDef[]>('/markets', undefined, signal),

  // models
  models: (signal?: AbortSignal) => get<ModelsInfo>('/models', undefined, signal),
  leaderboard: (signal?: AbortSignal) => get<LeaderboardRow[]>('/models/leaderboard', undefined, signal),
  performance: (params: { days?: number; model?: string; market_group?: string }, signal?: AbortSignal) =>
    get<PerformanceResponse>('/performance', params, signal),
  calibration: (params: { days?: number; model?: string; market_group?: string }, signal?: AbortSignal) =>
    get<PerformanceMetrics>('/performance/calibration', params, signal),

  // backtests
  backtests: (strategy?: string, signal?: AbortSignal) => get<BacktestList>('/backtests', { strategy }, signal),
  backtestComparison: (signal?: AbortSignal) => get<BacktestComparisonRow[]>('/backtests/comparison', undefined, signal),
  backtest: (id: number | string, signal?: AbortSignal) => get<BacktestDetail>(`/backtests/${id}`, undefined, signal),
  runBacktest: (body: BacktestRunRequest) => post<BacktestDetail>('/backtests/run', body, 180000),

  // paper bets
  paperBets: (status?: string, signal?: AbortSignal) => get<PaperBet[]>('/paper-bets', { status }, signal),
  createPaperBet: (body: PaperBetCreate) => post<PaperBet>('/paper-bets', body),
  settlePaperBets: () => post<unknown>('/paper-bets/settle', undefined, 120000),
  stakePreview: (probability: number, odds: number, signal?: AbortSignal) =>
    get<StakePreview>('/paper-bets/stake-preview', { probability, odds }, signal),
  bankroll: (signal?: AbortSignal) => get<Bankroll>('/bankroll', undefined, signal),

  // settings
  settings: (signal?: AbortSignal) => get<SettingsResponse>('/settings', undefined, signal),
  updateSettings: (key: string, value: SettingsValue) => put<SettingsValue>(`/settings/${key}`, { value }),

  // data sources / jobs
  dataSources: (signal?: AbortSignal) => get<DataSources>('/data-sources', undefined, signal),
  runScan: (body: { scan_date?: string; days_ahead?: number; competition_codes?: string[] }) =>
    post<ScanSummary>('/scan', body, 300000),
  runJob: (name: string) => post<Record<string, unknown>>(`/jobs/${name}`, undefined, 600000),
  explain: (opportunityId: string) => post<ExplainResponse>(`/opportunities/${opportunityId}/explain`, undefined, 120000),
}

export type Api = typeof api
