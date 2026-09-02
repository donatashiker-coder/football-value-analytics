"""Feature engineering: turn team statistics, league averages, ratings and team news into the exact
feature dictionary a prediction is made from (stored as a FeatureSnapshot), plus a data-quality score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fixture, Injury, LeagueSetting, Suspension
from app.models_ml.elo import EloParams
from app.statistics.engine import LeagueAverages, MatchHistory, TeamStats, compute_team_stats
from app.statistics.shrinkage import FormWeights

FEATURE_VERSION = "1.2"


@dataclass
class FixtureFeatures:
    fixture_id: str
    data_timestamp: datetime
    features: dict
    data_quality: float  # 0..100
    quality_components: dict
    warnings: list[str] = field(default_factory=list)
    home_stats: TeamStats | None = None
    away_stats: TeamStats | None = None
    league: LeagueAverages | None = None


def team_news_features(db: Session, team_id: str, kickoff: datetime) -> dict:
    """Injury/suspension summary available before kickoff. Impact is importance-weighted only when
    importance is known; otherwise counts are reported and uncertainty is raised."""
    injuries = list(db.scalars(select(Injury).where(Injury.team_id == team_id, Injury.active.is_(True))))
    injuries = [i for i in injuries if i.reported_at is None or i.reported_at <= kickoff]
    suspensions = list(db.scalars(select(Suspension).where(Suspension.team_id == team_id, Suspension.active.is_(True))))
    out_count = sum(1 for i in injuries if i.status == "out") + len(suspensions)
    doubtful = sum(1 for i in injuries if i.status != "out")
    known = [i.player_importance for i in injuries if i.player_importance is not None] + [s.player_importance for s in suspensions if s.player_importance is not None]
    importance_lost = sum(known) if known else None
    uncertainty = min(0.15 * doubtful + (0.1 * out_count if importance_lost is None else 0.0), 1.0)
    return {
        "injuries_out": out_count,
        "injuries_doubtful": doubtful,
        "importance_lost": importance_lost,
        "news_uncertainty": uncertainty,
        "names": [f"{i.player_name} ({i.status}{': ' + i.reason if i.reason else ''})" for i in injuries][:8] + [f"{s.player_name} (suspended)" for s in suspensions][:4],
        "available": True,
    }


def data_quality_score(home: TeamStats, away: TeamStats, league: LeagueAverages, odds_bookmakers: int, news_available: bool, min_sample: int) -> tuple[float, dict]:
    comp: dict[str, float] = {}
    n = min(home.matches + home.stats.get("previous_season_matches", 0) * 0.5, away.matches + away.stats.get("previous_season_matches", 0) * 0.5)
    comp["sample_size"] = min(n / max(min_sample * 2.5, 1), 1.0)
    comp["results_data"] = 1.0 if home.matches >= 1 and away.matches >= 1 else 0.3
    comp["corner_data"] = min((home.stats.get("corners_matches", 0) + away.stats.get("corners_matches", 0)) / max(2 * min_sample, 1), 1.0)
    comp["xg_data"] = 1.0 if home.stats.get("xg_for_avg") is not None and away.stats.get("xg_for_avg") is not None else 0.0
    comp["league_data"] = 0.0 if league.fallback else min(league.matches / 60, 1.0)
    comp["odds_coverage"] = min(odds_bookmakers / 4, 1.0)
    comp["team_news"] = 1.0 if news_available else 0.0
    weights = {"sample_size": 0.25, "results_data": 0.15, "corner_data": 0.15, "xg_data": 0.10, "league_data": 0.15, "odds_coverage": 0.10, "team_news": 0.10}
    score = sum(comp[k] * w for k, w in weights.items()) * 100
    return round(score, 1), comp


def build_features(
    db: Session,
    hist: MatchHistory,
    fixture: Fixture,
    cutoff: datetime,
    season_year: int,
    form_weights: FormWeights | None = None,
    prior_strength: float = 8.0,
    odds_bookmakers: int = 0,
    exclude_early_red: bool = False,
    include_team_news: bool = True,
) -> FixtureFeatures:
    """Features strictly from information dated before `cutoff` (<= kickoff)."""
    assert cutoff <= fixture.kickoff_utc.replace(tzinfo=cutoff.tzinfo) or cutoff.date() <= fixture.kickoff_utc.date(), "cutoff must not be after kickoff"
    league = hist.league_averages(fixture.competition_id, season_year, cutoff)
    ls = db.scalar(select(LeagueSetting).where(LeagueSetting.competition_id == fixture.competition_id))
    min_sample = ls.min_sample_size if ls else 6
    reliability = ls.reliability if ls else 0.8
    home = compute_team_stats(hist, fixture.home_team_id, fixture.competition_id, season_year, cutoff, league, form_weights, prior_strength, exclude_early_red)
    away = compute_team_stats(hist, fixture.away_team_id, fixture.competition_id, season_year, cutoff, league, form_weights, prior_strength, exclude_early_red)
    ratings = hist.elo_ratings(fixture.competition_id, cutoff)
    elo = EloParams()
    home_elo, away_elo = ratings.get(fixture.home_team_id, elo.initial), ratings.get(fixture.away_team_id, elo.initial)
    news_h = team_news_features(db, fixture.home_team_id, cutoff) if include_team_news else {"available": False, "news_uncertainty": 0.3, "injuries_out": None, "injuries_doubtful": None, "importance_lost": None, "names": []}
    news_a = team_news_features(db, fixture.away_team_id, cutoff) if include_team_news else {"available": False, "news_uncertainty": 0.3, "injuries_out": None, "injuries_doubtful": None, "importance_lost": None, "names": []}

    warnings = [f"Home: {w}" for w in home.warnings] + [f"Away: {w}" for w in away.warnings]
    if league.fallback:
        warnings.append("League averages unavailable: using documented defaults")
    if league.corner_coverage < 0.5:
        warnings.append(f"Corner data covers only {league.corner_coverage:.0%} of league matches")

    # blend venue-specific strength with overall strength when venue sample is thin (<5 matches)
    def venue_blend(venue_val: float, overall_val: float, n_venue: int) -> float:
        w = min(n_venue / 5.0, 1.0)
        return w * venue_val + (1 - w) * overall_val

    hs, as_ = home.stats, away.stats
    ha = ls.home_advantage if ls and ls.home_advantage else 1.0
    features = {
        "feature_version": FEATURE_VERSION,
        "cutoff": cutoff.isoformat(),
        "season_year": season_year,
        "league": league.as_dict(),
        "league_reliability": reliability,
        "min_sample_size": min_sample,
        "home_advantage": ha,
        "home_attack": venue_blend(hs["home_attack"], hs["attack_overall"], home.home_matches),
        "home_defence": venue_blend(hs["home_defence"], hs["defence_overall"], home.home_matches),
        "away_attack": venue_blend(as_["away_attack"], as_["attack_overall"], away.away_matches),
        "away_defence": venue_blend(as_["away_defence"], as_["defence_overall"], away.away_matches),
        "home_corners_for": venue_blend(hs["home_corners_for_strength"], hs["corners_for_strength_overall"], home.home_matches),
        "home_corners_against": venue_blend(hs["home_corners_against_strength"], hs["corners_against_strength_overall"], home.home_matches),
        "away_corners_for": venue_blend(as_["away_corners_for_strength"], as_["corners_for_strength_overall"], away.away_matches),
        "away_corners_against": venue_blend(as_["away_corners_against_strength"], as_["corners_against_strength_overall"], away.away_matches),
        "home_elo": home_elo,
        "away_elo": away_elo,
        "elo_diff": home_elo - away_elo,
        "home_stats": hs,
        "away_stats": as_,
        "home_news": news_h,
        "away_news": news_a,
        "home_rest_days": hs.get("days_since_last_match"),
        "away_rest_days": as_.get("days_since_last_match"),
        "sample_size": min(home.matches, away.matches),
        "sample_size_with_prior": min(home.matches + hs.get("previous_season_matches", 0), away.matches + as_.get("previous_season_matches", 0)),
        "volatility": (hs.get("volatility", 0.5) + as_.get("volatility", 0.5)) / 2,
        "news_uncertainty": max(news_h["news_uncertainty"], news_a["news_uncertainty"]),
        "corner_data_available": bool(hs.get("corners_matches")) and bool(as_.get("corners_matches")) and league.home_corners is not None,
    }
    dq, comps = data_quality_score(home, away, league, odds_bookmakers, news_h["available"] and news_a["available"], min_sample)
    return FixtureFeatures(fixture.id, cutoff, features, dq, comps, warnings, home, away, league)
