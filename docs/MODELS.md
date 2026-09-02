# Model documentation

Everything below is implemented in `backend/app/statistics`, `backend/app/models_ml`, `backend/app/services`
and covered by `backend/tests`. Probabilities are always computed by these functions — never by an LLM.

## 1. Data used (feature version 1.2)

For a fixture at cutoff time `T` (= now for the daily scan, = kickoff for backtests), **only matches with kickoff
< T** are visible (`MatchHistory.team_matches`, `league_averages`, `elo_ratings` all filter on `T`). Post-match
statistics are only ever read for those completed matches. Team news is filtered to items reported before `T`
and excluded entirely in backtests (no historical injury feed is available).

Per team and season: goals for/against (season, home, away, last 3/5/10/15), weighted form, xG for/against,
shots, shots on target, clean-sheet %, failed-to-score %, BTTS %, over 1.5/2.5/3.5 %, win/draw/loss %,
first/second-half goals, corners for/against (season, venue, last 5/10, variance, first half), rest days,
matches in the last 14 days, scoring volatility, early-red-card matches.

League per season: home/away goal averages, home/away corner averages, corner variance/mean ratio,
first-half goal share, BTTS and over-2.5 rates, corner and xG coverage. When fewer than 30 matches exist the
previous season is blended in; with none at all, documented defaults are used and the fixture is flagged
("League averages unavailable").

## 2. Recent form weighting

`weighted_form(values, FormWeights(last_5=0.5, last_10=0.3, season=0.2))` — nested windows, normalised weights,
configurable from Settings → `form_weights`.

## 3. Shrinkage and season blending (small-sample protection)

* `shrink(x̄, n, μ, k) = (n·x̄ + k·μ)/(n + k)`, k = `scanner.prior_strength` (default 8 matches).
* `blend_seasons`: current-season weight = min(n/12, 1); the previous-season value is itself regressed 30 %
  towards the league mean (squad turnover / promoted teams). With no previous data the league mean is the prior.
* Venue-specific strengths are blended with overall strengths until 5 venue matches exist.
* Strength multipliers are clipped to [0.3, 2.5].

## 4. Opponent adjustment

Each match's goals/corners are divided by the opponent's shrunk defence/attack ratio (single pass, ratio
clipped to [0.5, 1.8]) before averaging, so a 3–0 against the league's worst defence counts less than 3–0
against the best.

## 5. Elo

`expected = 1/(1+10^((R_b − R_a)/400))`, home advantage +60 points, K = 20 × margin multiplier
(1, 1.5, 1.75 + (gd−3)/8), 20 % regression to 1500 between seasons. Used for the strength feature and a
secondary 1X2 probability (draw share depends on rating closeness) that feeds model-agreement.

## 6. Goal model (primary: `dixon_coles`, version `goal-poisson-dc-1.0`)

```
λ_home = league_home_goals × home_attack × away_defence × home_advantage
λ_away = league_away_goals × away_attack × home_defence
P(h, a) = Pois(h; λ_home) · Pois(a; λ_away) · τ(h, a)          (matrix up to 10 goals, renormalised)
τ(0,0) = 1 − λμρ, τ(0,1) = 1 + λρ, τ(1,0) = 1 + μρ, τ(1,1) = 1 − ρ, else 1
```

ρ default −0.05 (Settings → `goal_model.rho`); `fit_rho` estimates it by grid-search maximum likelihood on
historical matches with ≥ 50 observations. From the matrix: 1X2, double chance, DNB, BTTS, totals O/U
0.5–5.5, team totals, Asian handicaps (push mass reported for whole lines), clean sheets, most likely scores.
First-half markets use λ × league first-half share (default 0.44) with independent Poissons.

A plain Poisson (ρ = 0) is evaluated alongside; the spread between models feeds agreement/confidence.

## 7. Corner model (`corners-nb-1.0`)

```
E[home corners] = league_home_corners × home_corners_for × away_corners_against
E[away corners] = league_away_corners × away_corners_for × home_corners_against
Total ~ NegBin(mean = E_h + E_a, r) with r = mean / (var_ratio − 1) from the league's observed variance/mean
```

If the league's corner counts are not over-dispersed (ratio ≤ 1.02) the distribution collapses to Poisson.
Team corner markets use a team-level dispersion; first-half corners scale the mean by the first-half share.
`compare_distributions` reports Poisson vs NB log-likelihood in every backtest, and the preferred family.
Demo data (r ≈ 9) and real football corner counts are over-dispersed, so NB is normally selected.

## 8. Team news

* Player importance (0–1) = 0.55 × availability share + 0.45 × goal-involvement share, × position weight —
  only when minutes are known.
* Absence impact: attack multiplier = 1 − min(importance_lost × 0.12, 0.12) × evidence confidence, evidence
  confidence = min(matches/10, 1). With unknown importance the multiplier is 1.0 and uncertainty is raised.
  The bound is a documented prior awaiting backtests with injury history.
* Manager change: before/after (10 matches) PPG, goals, corners; flagged insufficient below 5 matches; never
  assumed positive.

## 9. Data quality (0–100)

Weighted: sample size 25 %, results data 15 %, corner data 15 %, xG data 10 %, league data 15 %, odds coverage
10 %, team news 10 %.

## 10. Confidence (0–100, independent of EV)

Weighted: sample 15 %, data completeness 15 %, calibration 15 %, league reliability 10 %, liquidity 8 %, model
agreement 12 %, stability 7 %, team news 8 %, odds freshness 5 %, strategy history 5 %.

## 11. Calibration and monitoring

`evaluate()` returns Brier, log-loss, ROC-AUC, expected calibration error and 10 reliability bins.
`detect_drift()` flags MODEL DRIFT when recent Brier exceeds the historical Brier by > 0.02 with ≥ 100 recent
predictions. `platt_scale()` is available for recalibration (identity below 200 observations). Every prediction
stores `model_name`, `model_version`, `feature_version`, `feature_snapshot_id`, `data_timestamp`,
`prediction_timestamp`, `best_odds_at_prediction`; after results arrive it stores outcome, closing odds and CLV.

## 12. Ensemble policy

The primary probability is the Dixon-Coles model for goals/result markets and the NB model for corners. Elo
and plain Poisson are secondary and only influence confidence via agreement. No ML ensemble is enabled: the
registry (`model_versions`) and leaderboard support adding models, but a new model is only promoted after it
passes calibration, out-of-sample and minimum-sample checks (`docs/BACKTESTING.md`).
