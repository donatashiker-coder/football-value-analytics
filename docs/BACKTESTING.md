# Backtesting

Implementation: `backend/app/backtesting/engine.py`. CLI: `python -m app backtest --strategy <name>`.
API: `POST /api/backtests/run`.

## Walk-forward, leakage-safe by construction

Finished fixtures are processed in kickoff order. For each fixture:

1. `build_features(cutoff = kickoff)` — the shared `MatchHistory` only exposes matches with kickoff < cutoff,
   so team statistics, league averages, season blending, opponent adjustment and Elo are all "as of" that
   moment. The same function serves the daily scan, so there is one code path to audit.
2. Models run on those features (goal model, corner model, Elo, Poisson).
3. Markets of the chosen strategy are priced against the **earliest stored odds snapshot** per bookmaker
   (pre-match/opening odds). Closing odds are only used afterwards to compute CLV.
4. Value filters (`min_ev`, odds range, data quality, sample size, EV sanity cap, optional expected-corner or
   expected-goal thresholds) select bets; stake sizing is applied (`flat` by default, Kelly variants capped).
5. The bet is settled against the actual result (`settlement.settle_market`), including pushes/half-wins.
6. Every market probability (goals, BTTS, corners, 1X2) is also collected for calibration, regardless of
   whether a bet was taken.

A warm-up of 6 matches per team is skipped (documented) so that pure-prior fixtures do not generate bets.
`one_bet_per_fixture=true` keeps only the highest-EV bet per fixture (avoids correlated over/under stacking).

Team news is excluded from backtests (no historical injury feed), which is stated in the feature snapshot.

## Strategies

`GOALS_OVER, GOALS_UNDER, BTTS, CORNERS_OVER, CORNERS_UNDER, MATCH_RESULT, TEAM_GOALS, FIRST_HALF, VALUE_ONLY`
(all markets). Each is independently parameterised.

## Output

Summary: bets, wins, losses, pushes, strike rate, average odds, profit, total staked, ROI, yield, max drawdown
(absolute and %), longest winning/losing streak, profit factor, Sharpe-like ratio (mean/std of per-bet return
× √n), average EV, average edge, average CLV, CLV-positive rate, final bankroll, fixtures evaluated,
calibration (Brier, log-loss, ECE, reliability bins), corner distribution comparison (Poisson vs NB
log-likelihood, preferred), observed corner variance ratio.

Breakdowns: by league, market, odds range (1.20–1.49, 1.50–1.79, 1.80–2.09, 2.10–2.49, 2.50–2.99, 3.00–3.99,
4.00+), month, season, EV range, expected total. Equity curve with drawdown; bet list (last 5,000).

`POST /api/backtests/corner-thresholds` runs the corner strategy at expected-corner thresholds 10/11/12 and
reports ROI by line (8.5–11.5).

## Historical odds

Backtests need pre-match odds. Sources, in order:

1. Odds snapshots stored by this platform (the scheduler stores current odds on every refresh; the final refresh
   before kickoff is marked closing).
2. Provider historical odds where the provider exposes `historical_odds()` (the demo provider does; The Odds
   API historical endpoint is paid-only and not wired).

With no odds for a fixture, no bet is possible for it, but it still contributes to calibration.

## Model promotion rule

A model version is only promoted to primary if, on out-of-sample walk-forward data with ≥ 500 settled
predictions: Brier and ECE are not worse than the incumbent, ROI/CLV are not materially worse, and no drift
is flagged. Record the comparison in `model_versions.metrics`.

## Interpreting results

* Demo data is synthetic: odds are noisy around the latent truth, so the model shows positive CLV by
  construction. This validates the plumbing, not any real-market edge.
* On real data, treat CLV as the primary long-run signal, ROI as noisy, and require sample sizes per league
  (`league_settings.min_sample_size`) before drawing conclusions. Do not assume higher odds are better; check
  the odds-range breakdown.
