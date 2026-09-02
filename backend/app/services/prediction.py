"""Prediction pipeline: features -> models -> probabilities for every registered market.

Primary probabilities come from the Dixon-Coles goal model and the corner model. A plain Poisson
model and an Elo-based 1X2 model are also evaluated so model agreement can feed confidence and the
model leaderboard. Nothing here consults an LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.models_ml import corner_model, goal_model
from app.models_ml.elo import win_probabilities
from app.odds.markets import MARKETS, MarketDef
from app.services.features import FixtureFeatures

PRIMARY_MODEL = "dixon_coles"
MODEL_VERSIONS = {"dixon_coles": goal_model.MODEL_VERSION, "poisson": "goal-poisson-1.0", "elo": "elo-1.0", "corners": corner_model.MODEL_VERSION}


@dataclass
class FixturePrediction:
    fixture_id: str
    prediction_timestamp: datetime
    data_timestamp: datetime
    home_lambda: float
    away_lambda: float
    home_corners: float | None
    away_corners: float | None
    probabilities: dict[str, float]  # primary probability per prob_key
    model_probabilities: dict[str, dict[str, float]]  # per model name
    agreement: dict[str, float]  # per prob_key: 1 - spread across models that produce it
    score_matrix: list[list[float]]
    total_goals_pmf: list[float]
    total_corners_pmf: list[float] | None
    top_scores: list[tuple[int, int, float]]
    corner_distribution: str | None
    model_versions: dict[str, str] = field(default_factory=dict)

    def market_probability(self, m: MarketDef) -> float | None:
        return self.probabilities.get(m.prob_key)

    def market_agreement(self, m: MarketDef) -> float | None:
        return self.agreement.get(m.prob_key)


def predict_fixture(ff: FixtureFeatures, gparams: goal_model.GoalModelParams, cparams: corner_model.CornerModelParams, now: datetime) -> FixturePrediction:
    f = ff.features
    lg = f["league"]
    ginp = goal_model.GoalModelInput(
        home_attack=f["home_attack"], home_defence=f["home_defence"], away_attack=f["away_attack"], away_defence=f["away_defence"],
        league_home_goals=lg["home_goals"], league_away_goals=lg["away_goals"], home_advantage=f.get("home_advantage"),
    )
    dc = goal_model.predict(ginp, gparams)
    pois = goal_model.predict(ginp, goal_model.GoalModelParams(**{**gparams.__dict__, "use_dixon_coles": False}))
    fh_share = lg.get("first_half_share") or 0.44
    fh = goal_model.first_half_probabilities(dc.home_lambda, dc.away_lambda, fh_share)
    elo = win_probabilities(f["home_elo"], f["away_elo"], draw_rate=max(min(1 - lg.get("btts_rate", 0.5) * 0.4 - 0.4, 0.32), 0.20))

    probs: dict[str, float] = {**dc.probabilities, **fh}
    model_probs: dict[str, dict[str, float]] = {"dixon_coles": dict(dc.probabilities), "poisson": dict(pois.probabilities), "elo": elo}

    corners_out = None
    if f.get("corner_data_available") and lg.get("home_corners") and lg.get("away_corners"):
        cinp = corner_model.CornerModelInput(
            home_corners_for=f["home_corners_for"], home_corners_against=f["home_corners_against"], away_corners_for=f["away_corners_for"], away_corners_against=f["away_corners_against"],
            league_home_corners=lg["home_corners"], league_away_corners=lg["away_corners"], observed_variance_ratio=lg.get("corner_var_ratio"),
        )
        corners_out = corner_model.predict(cinp, cparams)
        pois_c = corner_model.predict(cinp, corner_model.CornerModelParams(**{**cparams.__dict__, "distribution": "poisson"}))
        probs.update(corners_out.probabilities)
        model_probs["corners"] = dict(corners_out.probabilities)
        model_probs["corners_poisson"] = dict(pois_c.probabilities)

    agreement: dict[str, float] = {}
    for key in probs:
        vals = [mp[key] for mp in model_probs.values() if key in mp]
        if len(vals) >= 2:
            agreement[key] = max(0.0, 1.0 - (max(vals) - min(vals)) / 0.15)  # 15-pt spread -> zero agreement
    return FixturePrediction(
        fixture_id=ff.fixture_id, prediction_timestamp=now, data_timestamp=ff.data_timestamp,
        home_lambda=dc.home_lambda, away_lambda=dc.away_lambda,
        home_corners=corners_out.home_expected if corners_out else None, away_corners=corners_out.away_expected if corners_out else None,
        probabilities=probs, model_probabilities=model_probs, agreement=agreement,
        score_matrix=[[round(float(x), 5) for x in row[:7]] for row in dc.matrix[:7]], total_goals_pmf=[round(x, 5) for x in dc.total_pmf()[:10]],
        total_corners_pmf=[round(float(x), 5) for x in corners_out.total_pmf[:25]] if corners_out else None,
        top_scores=dc.top_scores(5), corner_distribution=corners_out.distribution if corners_out else None, model_versions=dict(MODEL_VERSIONS),
    )


def model_disagreement(pred: FixturePrediction, m: MarketDef) -> float | None:
    vals = [mp[m.prob_key] for mp in pred.model_probabilities.values() if m.prob_key in mp]
    return (max(vals) - min(vals)) if len(vals) >= 2 else None


def markets_with_probability(pred: FixturePrediction) -> list[MarketDef]:
    return [m for m in MARKETS if m.prob_key in pred.probabilities]
