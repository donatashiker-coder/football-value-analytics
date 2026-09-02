"""Backtesting engine with chronological walk-forward evaluation.

For each historical fixture (in kickoff order) the engine:
  1. builds features with cutoff = kickoff (MatchHistory only exposes earlier matches),
  2. runs the models,
  3. prices every market of the strategy against the odds that were available before kickoff
     (opening/pre-match snapshot; closing odds are only used for CLV, never for selection),
  4. applies the value filters and stake sizing,
  5. settles against the actual result.
Calibration is measured on all predictions, not only the bets taken.

Walk-forward: seasons are processed in order; model parameters that are fitted (Dixon-Coles rho,
league averages, strengths, Elo) only ever use matches before the fixture being evaluated.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.betting.settlement import ResultData, outcome_to_binary, settle_market
from app.betting.staking import StakeConfig, calculate_stake, settle
from app.betting.value import ValueConfig, expected_value
from app.models import Backtest, Competition, Fixture, Odds, Result, Season
from app.models_ml.calibration import evaluate
from app.models_ml.corner_model import CornerModelParams
from app.models_ml.goal_model import GoalModelParams
from app.odds.markets import markets_for_strategy, outcome_set_members
from app.odds.math import BookmakerPrice, MarketComparison, closing_line_value, market_probability_for_selection
from app.services.features import build_features
from app.services.prediction import predict_fixture
from app.statistics.engine import MatchHistory
from app.statistics.shrinkage import FormWeights
from app.utils.logging import get_logger

log = get_logger(__name__)

ODDS_BANDS = [(1.20, 1.49), (1.50, 1.79), (1.80, 2.09), (2.10, 2.49), (2.50, 2.99), (3.00, 3.99), (4.00, 99.0)]


@dataclass
class BacktestParams:
    strategy: str = "VALUE_ONLY"
    competition_codes: list[str] | None = None
    start: datetime | None = None
    end: datetime | None = None
    min_ev: float = 0.03
    min_confidence: float = 0.0
    min_data_quality: float = 0.0
    min_odds: float = 1.30
    max_odds: float = 6.0
    min_sample_size: int = 6
    stake: StakeConfig = field(default_factory=lambda: StakeConfig(method="flat", flat_stake=1.0))
    starting_bankroll: float = 100.0
    corner_distribution: str | None = None  # override: poisson | negative_binomial
    min_expected_corners: float | None = None  # corner-strategy threshold analysis
    min_expected_goals: float | None = None
    exclude_early_red_cards: bool = False
    warmup_matches_per_team: int = 6
    one_bet_per_fixture: bool = True

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        d["stake"] = dict(self.stake.__dict__)
        d["start"], d["end"] = self.start.isoformat() if self.start else None, self.end.isoformat() if self.end else None
        return d


@dataclass
class BetRecord:
    fixture_id: str
    kickoff: str
    competition: str
    market_key: str
    odds: float
    bookmaker: str
    model_probability: float
    market_probability: float | None
    ev: float
    stake: float
    outcome: str
    profit: float
    closing_odds: float | None
    clv: float | None
    season: int
    expected_total: float | None


def _pre_match_odds(db: Session, fixtures: list[Fixture]) -> tuple[dict[str, dict[str, MarketComparison]], dict[tuple[str, str], float]]:
    """Earliest snapshot per (fixture, bookmaker, market) recorded BEFORE kickoff = pre-match odds; the latest
    pre-kickoff (or flagged closing) snapshot = closing odds for CLV. Rows recorded after kickoff are never used
    for selection: this is the guard against in-play/closing prices leaking into the backtest."""
    pre: dict[str, dict[str, MarketComparison]] = defaultdict(dict)
    closing_prices: dict[tuple[str, str], list[float]] = defaultdict(list)
    kickoffs = {f.id: (f.kickoff_utc if f.kickoff_utc.tzinfo else f.kickoff_utc.replace(tzinfo=UTC)) for f in fixtures}
    fixture_ids = list(kickoffs)
    for i in range(0, len(fixture_ids), 500):
        chunk = fixture_ids[i : i + 500]
        rows = db.execute(select(Odds).where(Odds.fixture_id.in_(chunk)).order_by(Odds.recorded_at)).scalars().all()
        seen_first: set[tuple[str, str, str]] = set()
        latest: dict[tuple[str, str, str], Odds] = {}
        for o in rows:
            if o.recorded_at > kickoffs[o.fixture_id]:
                continue  # post-kickoff snapshot: ignored entirely
            k = (o.fixture_id, o.bookmaker_key, o.market_key)
            if k not in seen_first:
                seen_first.add(k)
                comp = pre[o.fixture_id].setdefault(o.market_key, MarketComparison(o.selection))
                comp.prices.append(BookmakerPrice(o.bookmaker_key, o.decimal_odds, o.recorded_at))
            if o.is_closing or k not in latest or o.recorded_at >= latest[k].recorded_at:
                latest[k] = o
        for (fid, _bk, mk), o in latest.items():
            closing_prices[(fid, mk)].append(o.decimal_odds)
    closing = {k: float(np.median(v)) for k, v in closing_prices.items()}
    return pre, closing


def run_backtest(db: Session, params: BacktestParams, gparams: GoalModelParams | None = None, cparams: CornerModelParams | None = None, weights: FormWeights | None = None, progress=None) -> Backtest:
    gparams = gparams or GoalModelParams()
    cparams = cparams or CornerModelParams()
    if params.corner_distribution:
        cparams = CornerModelParams(**{**cparams.__dict__, "distribution": params.corner_distribution})
    comp_q = select(Competition).where(Competition.enabled.is_(True))
    if params.competition_codes:
        comp_q = comp_q.where(Competition.code.in_(params.competition_codes))
    comps = {c.id: c for c in db.scalars(comp_q)}
    seasons = {s.id: s.year for s in db.scalars(select(Season))}
    q = select(Fixture, Result).join(Result, Result.fixture_id == Fixture.id).where(Fixture.status == "FINISHED", Fixture.competition_id.in_(list(comps)))
    if params.start:
        q = q.where(Fixture.kickoff_utc >= params.start)
    if params.end:
        q = q.where(Fixture.kickoff_utc <= params.end)
    rows = db.execute(q.order_by(Fixture.kickoff_utc)).all()
    hist = MatchHistory.load(db, list(comps))  # full history; per-fixture cutoff enforces chronology
    pre_odds, closing = _pre_match_odds(db, [f for f, _ in rows])
    markets = markets_for_strategy(params.strategy)
    cfg = ValueConfig(min_ev=params.min_ev, min_confidence=params.min_confidence, min_data_quality=params.min_data_quality, min_odds=params.min_odds, max_odds=params.max_odds, min_sample_size=params.min_sample_size)

    bets: list[BetRecord] = []
    all_probs: list[float] = []
    all_outcomes: list[int] = []
    corner_obs: list[tuple[int, float]] = []
    bankroll = params.starting_bankroll
    seen_teams: dict[str, int] = defaultdict(int)
    n_fixtures = 0
    for idx, (fx, res) in enumerate(rows):
        kickoff = fx.kickoff_utc if fx.kickoff_utc.tzinfo else fx.kickoff_utc.replace(tzinfo=UTC)
        # warm-up: skip fixtures where either team has too little history (documented; avoids pure-prior bets)
        if seen_teams[fx.home_team_id] < params.warmup_matches_per_team or seen_teams[fx.away_team_id] < params.warmup_matches_per_team:
            seen_teams[fx.home_team_id] += 1
            seen_teams[fx.away_team_id] += 1
            continue
        seen_teams[fx.home_team_id] += 1
        seen_teams[fx.away_team_id] += 1
        season_year = seasons.get(fx.season_id, kickoff.year)
        comps_odds = pre_odds.get(fx.id, {})
        try:
            ff = build_features(db, hist, fx, kickoff, season_year, weights, odds_bookmakers=len({p.bookmaker for c in comps_odds.values() for p in c.prices}), exclude_early_red=params.exclude_early_red_cards, include_team_news=False)
            pred = predict_fixture(ff, gparams, cparams, kickoff)
        except Exception:
            log.exception("backtest feature failure for %s", fx.id)
            continue
        n_fixtures += 1
        rd = ResultData(res.home_goals, res.away_goals, res.home_goals_ht, res.away_goals_ht, res.home_corners, res.away_corners, res.home_corners_ht, res.away_corners_ht)
        if pred.home_corners is not None and res.home_corners is not None and res.away_corners is not None:
            corner_obs.append((res.home_corners + res.away_corners, pred.home_corners + pred.away_corners))
        candidates: list[tuple[float, BetRecord]] = []
        for m in markets:
            if m.prob_key not in pred.probabilities:
                continue
            p = pred.probabilities[m.prob_key]
            outcome = settle_market(m.key, rd)
            b = outcome_to_binary(outcome)
            if b is not None and m.group in ("goals", "btts", "corners", "match_result"):
                all_probs.append(p)
                all_outcomes.append(b)
            comp = comps_odds.get(m.key)
            if not comp or not comp.available or outcome == "unsettled":
                continue
            best = comp.best
            if best.odds < params.min_odds or best.odds > params.max_odds:
                continue
            if m.group in ("corners", "team_corners") and params.min_expected_corners is not None and (pred.home_corners or 0) + (pred.away_corners or 0) < params.min_expected_corners:
                continue
            if m.group in ("goals", "btts") and params.min_expected_goals is not None and pred.home_lambda + pred.away_lambda < params.min_expected_goals:
                continue
            ev = expected_value(p, best.odds)
            if ev < cfg.min_ev or ev > cfg.max_ev_sanity:
                continue
            if ff.data_quality < cfg.min_data_quality or ff.features["sample_size_with_prior"] < cfg.min_sample_size:
                continue
            set_comps = {mm.key: comps_odds[mm.key] for mm in outcome_set_members(m.outcome_set) if mm.key in comps_odds}
            market_p, _ = market_probability_for_selection(m.key, set_comps, required_outcomes=len(outcome_set_members(m.outcome_set)))
            stake = calculate_stake(p, best.odds, bankroll, params.stake)
            if stake <= 0:
                continue
            profit = settle(stake, best.odds, outcome)
            cl = closing.get((fx.id, m.key))
            expected_total = (pred.home_corners or 0) + (pred.away_corners or 0) if m.group in ("corners", "team_corners") else pred.home_lambda + pred.away_lambda
            rec = BetRecord(fx.id, kickoff.isoformat(), comps[fx.competition_id].code, m.key, best.odds, best.bookmaker, p, market_p, ev, stake, outcome, profit, cl, closing_line_value(best.odds, cl) if cl else None, season_year, expected_total)
            candidates.append((ev, rec))
        if params.one_bet_per_fixture and candidates:
            candidates = [max(candidates, key=lambda c: c[0])]
        for _, rec in candidates:
            bets.append(rec)
            bankroll += rec.profit
        if progress and idx % 100 == 0:
            progress(idx, len(rows))

    summary, breakdowns, curve = summarise(bets, params.starting_bankroll)
    summary["fixtures_evaluated"] = n_fixtures
    calib = evaluate(np.array(all_probs), np.array(all_outcomes)) if all_probs else None
    summary["calibration"] = calib.as_dict() if calib else None
    if corner_obs:
        from app.models_ml.corner_model import compare_distributions

        obs = np.array([o for o, _ in corner_obs])
        exp = np.array([e for _, e in corner_obs])
        summary["corner_distribution_comparison"] = compare_distributions(obs, exp, cparams.dispersion)
        summary["corner_variance_ratio_observed"] = float(obs.var() / obs.mean()) if obs.mean() > 0 else None
    bt = Backtest(
        strategy=params.strategy, name=f"{params.strategy} {datetime.now(UTC):%Y-%m-%d %H:%M}", parameters=params.as_dict(), start_date=params.start, end_date=params.end, status="completed",
        summary=summary, breakdowns=breakdowns, equity_curve=curve, bets=[b.__dict__ for b in bets[-5000:]], model_version=f"{gparams.__class__.__name__}/{cparams.distribution}", is_demo=any(f.is_demo for f, _ in rows[:1]),
    )
    db.add(bt)
    db.commit()
    return bt


def summarise(bets: list[BetRecord], starting_bankroll: float) -> tuple[dict, dict, list]:
    if not bets:
        return {"bets": 0, "roi": None, "profit": 0.0, "note": "No bets met the strategy criteria"}, {}, []
    profits = np.array([b.profit for b in bets])
    stakes = np.array([b.stake for b in bets])
    wins = sum(1 for b in bets if b.outcome in ("won", "half_won"))
    losses = sum(1 for b in bets if b.outcome in ("lost", "half_lost"))
    pushes = len(bets) - wins - losses
    equity = starting_bankroll + np.cumsum(profits)
    peak = np.maximum.accumulate(np.concatenate([[starting_bankroll], equity]))[1:]
    drawdown = peak - equity
    streaks = _streaks([b.outcome for b in bets])
    gross_win = float(profits[profits > 0].sum())
    gross_loss = float(-profits[profits < 0].sum())
    clvs = [b.clv for b in bets if b.clv is not None]
    per_bet_returns = profits / np.where(stakes > 0, stakes, 1)
    summary = {
        "bets": len(bets), "wins": wins, "losses": losses, "pushes": pushes, "strike_rate": wins / max(wins + losses, 1), "average_odds": float(np.mean([b.odds for b in bets])),
        "profit": float(profits.sum()), "total_staked": float(stakes.sum()), "roi": float(profits.sum() / stakes.sum()) if stakes.sum() else None, "yield": float(profits.sum() / stakes.sum()) if stakes.sum() else None,
        "max_drawdown": float(drawdown.max()), "max_drawdown_pct": float((drawdown / peak).max()), "longest_losing_streak": streaks["lose"], "longest_winning_streak": streaks["win"],
        "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else None, "sharpe_like": float(per_bet_returns.mean() / per_bet_returns.std() * np.sqrt(len(bets))) if len(bets) > 1 and per_bet_returns.std() > 0 else None,
        "average_ev": float(np.mean([b.ev for b in bets])), "average_edge": float(np.mean([b.model_probability - b.market_probability for b in bets if b.market_probability is not None])) if any(b.market_probability is not None for b in bets) else None,
        "average_clv": float(np.mean(clvs)) if clvs else None, "clv_positive_rate": float(np.mean([c > 0 for c in clvs])) if clvs else None, "final_bankroll": float(equity[-1]),
    }
    breakdowns = {"by_league": _group(bets, lambda b: b.competition), "by_market": _group(bets, lambda b: b.market_key), "by_odds_range": _group(bets, _odds_band), "by_month": _group(bets, lambda b: b.kickoff[:7]), "by_season": _group(bets, lambda b: str(b.season)), "by_ev_range": _group(bets, _ev_band)}
    if any(b.expected_total is not None for b in bets):
        breakdowns["by_expected_total"] = _group(bets, lambda b: f"{np.floor(b.expected_total)}+" if b.expected_total is not None else "n/a")
    curve = [{"t": b.kickoff, "equity": round(float(e), 2), "drawdown": round(float(d), 2)} for b, e, d in zip(bets, equity, drawdown, strict=True)]
    if len(curve) > 2000:
        step = len(curve) // 2000 + 1
        curve = curve[::step]
    return summary, breakdowns, curve


def _streaks(outcomes: list[str]) -> dict[str, int]:
    best = {"win": 0, "lose": 0}
    cur = {"win": 0, "lose": 0}
    for o in outcomes:
        if o in ("won", "half_won"):
            cur["win"] += 1
            cur["lose"] = 0
        elif o in ("lost", "half_lost"):
            cur["lose"] += 1
            cur["win"] = 0
        else:
            continue
        best["win"], best["lose"] = max(best["win"], cur["win"]), max(best["lose"], cur["lose"])
    return best


def _odds_band(b: BetRecord) -> str:
    for lo, hi in ODDS_BANDS:
        if lo <= b.odds <= hi + 0.0099:
            return f"{lo:.2f}-{hi:.2f}" if hi < 99 else f"{lo:.2f}+"
    return "<1.20"


def _ev_band(b: BetRecord) -> str:
    for lo, hi in ((0.0, 0.02), (0.02, 0.05), (0.05, 0.08), (0.08, 0.12), (0.12, 0.20), (0.20, 9)):
        if lo <= b.ev < hi:
            return f"{lo * 100:.0f}-{hi * 100:.0f}%" if hi < 9 else f"{lo * 100:.0f}%+"
    return "negative"


def _group(bets: list[BetRecord], key) -> list[dict]:
    g: dict[str, list[BetRecord]] = defaultdict(list)
    for b in bets:
        g[key(b)].append(b)
    out = []
    for k, bs in sorted(g.items()):
        st = sum(b.stake for b in bs)
        pr = sum(b.profit for b in bs)
        w = sum(1 for b in bs if b.outcome in ("won", "half_won"))
        clvs = [b.clv for b in bs if b.clv is not None]
        out.append({"key": k, "bets": len(bs), "wins": w, "strike_rate": w / max(len(bs), 1), "profit": round(pr, 2), "roi": round(pr / st, 4) if st else None, "average_odds": round(sum(b.odds for b in bs) / len(bs), 3), "average_clv": round(sum(clvs) / len(clvs), 4) if clvs else None})
    return out


def corner_threshold_analysis(db: Session, thresholds=(10.0, 11.0, 12.0), lines=(8.5, 9.5, 10.5, 11.5), competition_codes: list[str] | None = None) -> list[dict]:
    """ROI by expected-corners threshold and line (section 70 of the specification)."""
    out = []
    for th in thresholds:
        bt = run_backtest(db, BacktestParams(strategy="CORNERS_OVER", competition_codes=competition_codes, min_expected_corners=th, min_ev=0.0, one_bet_per_fixture=False))
        by_market = {r["key"]: r for r in bt.breakdowns.get("by_market", [])}
        for line in lines:
            r = by_market.get(f"corners_over_{line}")
            out.append({"expected_corners_min": th, "line": line, "bets": r["bets"] if r else 0, "roi": r["roi"] if r else None, "strike_rate": r["strike_rate"] if r else None})
        db.delete(bt)
    db.commit()
    return out
