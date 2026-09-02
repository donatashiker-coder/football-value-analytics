// ---- Shared enums ----------------------------------------------------------

export type OpportunityStatus = 'VALUE_CANDIDATE' | 'NO_BET' | 'ODDS_UNAVAILABLE'
export type ValueLabel = 'IGNORE' | 'WEAK' | 'INTERESTING' | 'STRONG' | 'VERY_STRONG' | 'UNAVAILABLE'
export type BetStatus = 'open' | 'won' | 'lost' | 'push'
export type FormResult = 'W' | 'D' | 'L'

// ---- System ----------------------------------------------------------------

export interface Health {
  status: string
  app_mode: string
  version: string
  database: string
  time_utc: string
}

export interface Status {
  app_mode: string
  demo: boolean
  providers_configured: Record<string, boolean>
  fixtures: number
  results: number
  upcoming_fixtures: number
  opportunities: number
  predictions: number
  last_scan: string | null
  scheduler_enabled: boolean
  timezone: string
  disclaimer: string
}

export interface ApiRequestStat {
  provider: string
  requests: number
  cached: number
  errors: number
}

export interface DataHealth {
  status: string
  last_odds_update: string | null
  odds_age_hours: number | null
  last_fixture_update: string | null
  api_requests_24h: ApiRequestStat[]
  warnings: string[]
}

export interface CalibrationBin {
  lower: number
  upper: number
  count: number
  mean_predicted: number | null
  observed_rate: number | null
}

/** Metric keys are omitted by the backend when the sample is empty (n = 0), so they are optional. */
export interface PerformanceMetrics {
  n: number
  brier?: number | null
  log_loss?: number | null
  roc_auc?: number | null
  expected_calibration_error?: number | null
  bins?: CalibrationBin[]
  average_clv: number | null
  signals_backed: number
  flat_roi_all_signals: number | null
  period_days?: number
  model_name?: string | null
  market_group?: string | null
}

export interface DriftInfo {
  drift_detected: boolean
  recent_brier?: number | null
  historical_brier?: number | null
  difference?: number | null
  reason?: string
  [key: string]: unknown
}

export interface ModelHealth {
  status: string
  last_30_days: PerformanceMetrics
  drift: DriftInfo
}

// ---- Opportunities ---------------------------------------------------------

export interface OddsMovement {
  opening: number | null
  current: number | null
  movement: number | null
  movement_pct: number | null
  direction: string
}

export interface Opportunity {
  id: string
  fixture_id: string
  home_team: string
  away_team: string
  competition: string
  competition_code: string
  kickoff_utc: string
  status: OpportunityStatus
  is_demo: boolean
  market_key: string
  market: string
  market_group: string
  selection: string
  line: number | null
  best_odds: number | null
  best_bookmaker: string | null
  median_odds: number | null
  bookmaker_count: number
  model_probability: number
  market_probability: number | null
  fair_odds: number | null
  edge: number | null
  expected_value: number | null
  value_label: ValueLabel
  confidence: number
  data_quality: number
  value_score: number
  no_bet_reasons: string[]
  key_factors: string[]
  risk_factors: string[]
  explanation: string
  llm_explanation: string | null
  model_version: string
  odds_recorded_at: string | null
  scan_date: string
  movement?: OddsMovement | null
}

export interface OpportunityList {
  date?: string
  days?: number
  count: number
  opportunities: Opportunity[]
  disclaimer?: string
}

// ---- Dashboard -------------------------------------------------------------

export interface DashboardModelPerformance {
  n: number
  brier?: number | null
  log_loss?: number | null
  expected_calibration_error?: number | null
  average_clv: number | null
  flat_roi_all_signals: number | null
}

export interface PaperBettingSummary {
  starting_bankroll: number
  current_bankroll: number
  profit: number
  total_staked: number
  roi: number | null
  max_drawdown: number | null
  open_bets: number
  settled_bets: number
  wins: number
  losses: number
  strike_rate: number | null
  average_clv: number | null
}

export interface Dashboard {
  date: string
  is_demo: boolean
  fixtures_today: number
  fixtures_analysed: number
  value_candidates: number
  markets_evaluated: number
  top_opportunities: Opportunity[]
  highest_ev: Opportunity | null
  highest_confidence: Opportunity | null
  best_corners: Opportunity[]
  best_goals: Opportunity[]
  best_low_scoring: Opportunity[]
  best_btts: Opportunity[]
  model_performance: DashboardModelPerformance
  paper_betting: PaperBettingSummary
  data_quality_warnings: number
  stale_odds: number
  disclaimer: string
}

// ---- Fixtures --------------------------------------------------------------

export interface HomeAway {
  home: number | null
  away: number | null
}

export interface FixtureResult {
  home_goals: number | null
  away_goals: number | null
  home_corners: number | null
  away_corners: number | null
}

export interface FixtureSummary {
  fixture_id: string
  home_team: string
  away_team: string
  competition: string
  competition_code: string
  kickoff_utc: string
  status: string
  is_demo: boolean
  analysed: boolean
  data_quality: number | null
  value_candidates: number
  markets_evaluated: number
  best_opportunity: Opportunity | null
  expected_goals: HomeAway | null
  expected_corners: HomeAway | null
  result: FixtureResult | null
}

export interface FixturesToday {
  date: string
  count: number
  fixtures: FixtureSummary[]
}

export interface FixtureSearchItem {
  fixture_id: string
  home_team: string
  away_team: string
  competition: string
  kickoff_utc: string
  status: string
}

export interface FixtureSearch {
  fixtures: FixtureSearchItem[]
}

export type TeamStats = Record<string, number | null | undefined>

export interface LeagueFeatures {
  home_goals: number | null
  away_goals: number | null
  home_corners: number | null
  away_corners: number | null
  btts_rate: number | null
  over_2_5_rate: number | null
  matches: number | null
  fallback: boolean
  corner_coverage: number | null
  xg_coverage: number | null
}

export interface TeamNewsFeature {
  injuries_out: number | null
  injuries_doubtful: number | null
  names: string[]
  available: boolean
}

export interface FixtureFeatures {
  league: LeagueFeatures
  home_attack: number | null
  home_defence: number | null
  away_attack: number | null
  away_defence: number | null
  home_elo: number | null
  away_elo: number | null
  elo_diff: number | null
  home_stats: TeamStats
  away_stats: TeamStats
  home_news: TeamNewsFeature | null
  away_news: TeamNewsFeature | null
  sample_size: number | null
  volatility: number | null
  news_uncertainty: number | null
}

export interface FeatureSnapshot {
  id: string
  feature_version: string
  data_timestamp: string
  data_quality: number | null
  warnings: string[]
}

export interface FixtureModel {
  expected_goals: HomeAway | null
  expected_corners: HomeAway | null
  probabilities: Record<string, Record<string, number>>
  versions: string[]
  prediction_timestamp: string | null
}

export interface BookmakerPrice {
  bookmaker: string
  odds: number
}

export interface FixtureOddsMarket {
  selection: string
  best_odds: number | null
  best_bookmaker: string | null
  median_odds: number | null
  mean_odds: number | null
  min_odds: number | null
  max_odds: number | null
  bookmaker_count: number
  prices: BookmakerPrice[]
}

export interface FormMatch {
  fixture_id: string
  date: string
  is_home: boolean
  goals_for: number | null
  goals_against: number | null
  xg_for: number | null
  xg_against: number | null
  corners_for: number | null
  corners_against: number | null
  result: FormResult
}

export interface HeadToHead {
  date: string
  home_goals: number | null
  away_goals: number | null
  home_was: string
}

export interface Injury {
  player: string
  reason: string | null
  status: string | null
  importance: string | null
  source: string | null
  retrieved_at: string | null
}

export interface Suspension {
  player: string
  reason: string | null
}

export interface TeamNews {
  injuries: Injury[]
  suspensions: Suspension[]
  available: boolean
}

export interface MarketInfo {
  name: string
  group: string
}

export interface FixtureDetail {
  fixture_id: string
  home_team: string
  away_team: string
  competition: string
  competition_code: string
  kickoff_utc: string
  status: string
  is_demo: boolean
  venue: string | null
  matchday: number | null
  result: FixtureResult | null
  features: FixtureFeatures | null
  feature_snapshot: FeatureSnapshot | null
  model: FixtureModel
  opportunities: Opportunity[]
  odds: Record<string, FixtureOddsMarket>
  odds_movement: Record<string, OddsMovement>
  form: { home: FormMatch[]; away: FormMatch[] }
  head_to_head: HeadToHead[]
  team_news: { home: TeamNews; away: TeamNews }
  markets: Record<string, MarketInfo>
}

// ---- Scanners --------------------------------------------------------------

export interface ScannerRow {
  fixture_id: string
  home_team: string
  away_team: string
  competition: string
  kickoff_utc: string
  expected_goals: number | null
  league_goals: number | null
  goals_ratio: number | null
  expected_corners: number | null
  league_corners: number | null
  corners_ratio: number | null
  p_over_2_5: number | null
  p_corners_over_9_5: number | null
  data_quality: number | null
}

export interface ScannerExpected {
  high_scoring: ScannerRow[]
  low_scoring: ScannerRow[]
  high_corners: ScannerRow[]
}

// ---- Teams -----------------------------------------------------------------

export interface TeamListItem {
  id: string
  name: string
  short_name: string | null
  country: string | null
  competition_id: string | null
  is_demo: boolean
}

export interface TeamRecentMatch {
  fixture_id: string
  date: string
  is_home: boolean
  opponent_id: string | null
  goals_for: number | null
  goals_against: number | null
  xg_for: number | null
  xg_against: number | null
  corners_for: number | null
  corners_against: number | null
  early_red_card: boolean
}

export interface TeamUpcoming {
  fixture_id: string
  kickoff_utc: string
  home_team: string
  away_team: string
}

export interface TeamDetail {
  id: string
  name: string
  competition_id: string | null
  is_demo: boolean
  season_year: number | null
  elo: number | null
  stats: TeamStats
  warnings: string[]
  league_averages: Record<string, number | null>
  recent_matches: TeamRecentMatch[]
  upcoming: TeamUpcoming[]
  injuries: Injury[]
  transfers: Record<string, unknown>[]
  manager_changes: Record<string, unknown>[]
}

// ---- Leagues ---------------------------------------------------------------

export interface LeagueSettings {
  min_sample_size: number
  reliability: number
  home_advantage: number
}

export interface League {
  id: string
  code: string
  name: string
  country: string | null
  tier: number | null
  enabled: boolean
  fixtures: number
  results: number
  settings: LeagueSettings
  is_demo: boolean
}

export interface LeagueTableRow {
  position: number
  team_id: string
  team: string
  matches: number
  points: number
  ppg: number | null
  goals_for: number | null
  goals_against: number | null
  xg_for: number | null
  xg_against: number | null
  corners_for: number | null
  corners_against: number | null
  btts_pct: number | null
  over_2_5_pct: number | null
  clean_sheet_pct: number | null
  elo: number | null
}

export interface LeagueBacktestRow {
  key: string
  bets: number
  roi: number | null
  strike_rate: number | null
}

export interface LeagueDetail {
  code: string
  name: string
  season_year: number | null
  averages: Record<string, number | null>
  table: LeagueTableRow[]
  backtests: { strategy: string; league_rows: LeagueBacktestRow[] }[]
}

// ---- Odds ------------------------------------------------------------------

export interface OddsMarketRow {
  market_key: string
  market: string
  group: string
  selection: string
  best_odds: number | null
  best_bookmaker: string | null
  median_odds: number | null
  min_odds: number | null
  max_odds: number | null
  bookmaker_count: number
  prices: BookmakerPrice[]
  raw_implied: number | null
  market_probability: number | null
  overround: number | null
  age_hours: number | null
  stale: boolean
}

export interface OddsHistoryPoint {
  t: string
  bookmaker: string
  odds: number
  closing: boolean
}

export interface FixtureOdds {
  fixture_id: string
  markets: OddsMarketRow[]
  history: Record<string, OddsHistoryPoint[]>
  movement: Record<string, OddsMovement>
  unavailable_markets: string[]
}

export interface Bookmaker {
  key: string
  name: string
  enabled: boolean
  is_exchange: boolean
}

export interface MarketDef {
  key: string
  group: string
  name: string
  selection: string
  line: number | null
  period: string | null
  strategy: string | null
}

// ---- Models / performance ---------------------------------------------------

export interface ModelsInfo {
  active: Record<string, string>
  registry: Record<string, unknown>[]
}

export interface LeaderboardRow {
  model: string
  version: string
  market_group: string
  predictions: number
  brier: number | null
  log_loss: number | null
  ece: number | null
  roc_auc: number | null
  roi: number | null
  clv: number | null
  from: string | null
  to: string | null
}

export interface PerformanceResponse {
  performance: PerformanceMetrics
  drift: DriftInfo
  strategy_scores: Record<string, number>
  note: string | null
}

// ---- Backtests -------------------------------------------------------------

export interface BacktestCalibration {
  n: number
  brier: number | null
  log_loss: number | null
  expected_calibration_error: number | null
  bins: CalibrationBin[]
}

export interface CornerDistributionComparison {
  poisson_loglik: number | null
  negative_binomial_loglik: number | null
  preferred: string
}

export interface BacktestSummary {
  bets: number
  wins: number
  losses: number
  pushes: number
  strike_rate: number | null
  average_odds: number | null
  profit: number
  total_staked: number
  roi: number | null
  yield: number | null
  max_drawdown: number | null
  max_drawdown_pct: number | null
  longest_losing_streak: number
  longest_winning_streak: number
  profit_factor: number | null
  sharpe_like: number | null
  average_ev: number | null
  average_edge: number | null
  average_clv: number | null
  clv_positive_rate: number | null
  final_bankroll: number | null
  fixtures_evaluated: number
  calibration?: BacktestCalibration | null
  corner_distribution_comparison?: CornerDistributionComparison | null
}

export interface BacktestListItem {
  id: string
  strategy: string
  name: string
  status: string
  parameters: Record<string, unknown>
  summary: BacktestSummary | null
  created_at: string
  model_version: string | null
  is_demo: boolean
}

export interface BacktestList {
  strategies: string[]
  backtests: BacktestListItem[]
}

export interface BacktestComparisonRow {
  strategy: string
  backtest_id: string
  bets: number
  strike_rate: number | null
  roi: number | null
  clv: number | null
  max_drawdown: number | null
  average_odds: number | null
  created_at: string
  is_demo: boolean
}

export interface BreakdownRow {
  key: string
  bets: number
  wins: number
  strike_rate: number | null
  profit: number
  roi: number | null
  average_odds: number | null
  average_clv: number | null
}

export interface EquityPoint {
  t: string
  equity: number
  drawdown: number
}

export interface BacktestBet {
  fixture_id: string
  kickoff: string
  competition: string
  market_key: string
  odds: number
  bookmaker: string | null
  model_probability: number
  market_probability: number | null
  ev: number | null
  stake: number
  outcome: string
  profit: number
  closing_odds: number | null
  clv: number | null
  season: string | number | null
  expected_total?: number | null
}

export interface BacktestDetail extends BacktestListItem {
  breakdowns: Record<string, BreakdownRow[] | undefined>
  equity_curve: EquityPoint[]
  bets: BacktestBet[]
}

export interface BacktestRunRequest {
  strategy: string
  competition_codes?: string[]
  start?: string
  end?: string
  min_ev: number
  min_confidence: number
  min_data_quality: number
  min_odds: number
  max_odds: number
  min_sample_size: number
  stake_method: string
  flat_stake: number
  starting_bankroll: number
  corner_distribution?: string
  min_expected_corners?: number
  min_expected_goals?: number
  exclude_early_red_cards: boolean
  one_bet_per_fixture: boolean
}

// ---- Paper bets / bankroll --------------------------------------------------

export interface PaperBet {
  id: string
  fixture_id: string
  home_team: string
  away_team: string
  competition: string
  kickoff_utc: string
  market_key: string
  selection: string
  bookmaker_key: string | null
  odds: number
  stake: number
  stake_method: string | null
  model_probability: number | null
  expected_value: number | null
  placed_at: string
  status: BetStatus
  profit: number | null
  settled_at: string | null
  closing_odds: number | null
  clv: number | null
  notes: string | null
}

export interface PaperBetCreate {
  fixture_id: string
  market_key: string
  selection: string
  odds: number
  stake?: number
  bookmaker_key?: string
  opportunity_id?: string
  notes?: string
  stake_method?: string
}

export interface StakePreview {
  kelly_fraction: number
  stakes: {
    flat: number
    percentage: number
    quarter_kelly: number
    half_kelly: number
    full_kelly: number
  }
  default_method: string
  bankroll: number
  max_stake_fraction: number
}

export interface Bankroll {
  starting_bankroll: number
  current_bankroll: number
  profit: number
  total_staked: number
  roi: number | null
  max_drawdown: number | null
  open_bets: number
  open_stake: number
  settled_bets: number
  wins: number
  losses: number
  pushes: number
  strike_rate: number | null
  average_odds: number | null
  average_clv: number | null
  equity_curve: { t: string; equity: number }[]
  snapshots: { as_of: string; bankroll: number; profit: number; roi: number | null; max_drawdown: number | null }[]
  note: string | null
}

// ---- Settings --------------------------------------------------------------

export type SettingsValue = Record<string, unknown>

export interface SettingsResponse {
  settings: Record<string, SettingsValue>
  descriptions: Record<string, string>
  defaults: Record<string, SettingsValue>
}

// ---- Data sources ----------------------------------------------------------

export interface ProviderInfo {
  key: string
  name: string
  role: string
  configured: boolean
  active: boolean
  fields: string[]
  notes: string | null
}

export interface DataSourceLeague {
  code: string
  name: string
  country: string | null
  api_football: string | number | null
  football_data: string | number | null
  the_odds_api: string | null
}

export interface DataSources {
  mode: string
  message: string | null
  providers: ProviderInfo[]
  leagues: DataSourceLeague[]
}

// ---- Reports / jobs --------------------------------------------------------

export interface ScanSummary {
  date: string
  fixtures: number
  analysed: number
  value_candidates: number
  no_bet: number
  odds_unavailable: number
  leagues: number
  warnings: string[]
}

export interface ExplainResponse {
  llm_available: boolean
  explanation: string | null
  generated?: boolean
}
