"""Small-sample protection: weighted recent form and empirical-Bayes shrinkage towards league averages."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FormWeights:
    """Weights applied to windowed averages. They are normalised so they always sum to one."""

    last_5: float = 0.5
    last_10: float = 0.3
    season: float = 0.2
    # windows also reported but not weighted by default
    last_3: float = 0.0
    last_15: float = 0.0

    def normalised(self) -> dict[str, float]:
        raw = {"last_3": self.last_3, "last_5": self.last_5, "last_10": self.last_10, "last_15": self.last_15, "season": self.season}
        s = sum(raw.values())
        return {k: v / s for k, v in raw.items()} if s > 0 else {"season": 1.0}


def window_mean(values: list[float], n: int | None) -> float | None:
    """Mean of the most recent n values (values ordered oldest -> newest). None if empty."""
    if not values:
        return None
    subset = values if n is None else values[-n:]
    return sum(subset) / len(subset)


def weighted_form(values: list[float], weights: FormWeights | None = None) -> float | None:
    """Blend of windowed means. Windows are nested, so no match is double-counted within a window;
    the blend deliberately overweights recent matches. Windows longer than the data collapse to the season mean."""
    if not values:
        return None
    weights = weights or FormWeights()
    w = weights.normalised()
    windows = {"last_3": 3, "last_5": 5, "last_10": 10, "last_15": 15, "season": None}
    total, wsum = 0.0, 0.0
    for key, n in windows.items():
        if w.get(key, 0.0) <= 0:
            continue
        m = window_mean(values, n)
        if m is None:
            continue
        total += w[key] * m
        wsum += w[key]
    return total / wsum if wsum > 0 else None


def shrink(sample_mean: float | None, sample_size: int, prior_mean: float, prior_strength: float) -> float:
    """Empirical-Bayes style shrinkage: (n * x_bar + k * mu) / (n + k).

    prior_strength k is the number of matches the league prior is "worth". With n=3 and k=10 a team
    averaging 12 corners in a 9.5-corner league is shrunk to ~10.1.
    """
    if sample_mean is None or sample_size <= 0:
        return prior_mean
    return (sample_size * sample_mean + prior_strength * prior_mean) / (sample_size + prior_strength)


def blend_seasons(current_mean: float | None, current_n: int, previous_mean: float | None, league_mean: float, full_weight_matches: int = 12) -> tuple[float, dict]:
    """Season-start handling: previous season weight decays as current-season matches accumulate.

    Returns (blended_value, breakdown). If no previous-season data, falls back to league mean as prior.
    """
    w_current = min(current_n / full_weight_matches, 1.0) if current_n > 0 else 0.0
    prior = previous_mean if previous_mean is not None else league_mean
    # previous season itself is regressed 30% towards the league mean (squad turnover, promoted teams)
    prior = 0.7 * prior + 0.3 * league_mean
    cur = current_mean if current_mean is not None else prior
    value = w_current * cur + (1.0 - w_current) * prior
    return value, {"current_weight": w_current, "current_mean": current_mean, "prior_used": prior, "previous_mean": previous_mean}


def volatility(values: list[float], n: int = 10) -> float:
    """Coefficient of variation of the last n values, clipped to 0..1. Used by the confidence engine."""
    subset = values[-n:]
    if len(subset) < 3:
        return 0.5
    mean = sum(subset) / len(subset)
    if mean <= 0:
        return 0.5
    var = sum((v - mean) ** 2 for v in subset) / (len(subset) - 1)
    cv = var**0.5 / mean
    return min(cv / 1.5, 1.0)
