"""Odds arithmetic: conversions, implied probability, overround, normalisation, bookmaker comparison."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime
from fractions import Fraction


def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError("decimal odds must exceed 1.0")
    return 1.0 / decimal_odds


def fair_odds(probability: float) -> float:
    if not 0.0 < probability <= 1.0:
        raise ValueError("probability must be in (0, 1]")
    return 1.0 / probability


def overround(odds: list[float]) -> float:
    """Sum of implied probabilities over a complete outcome set. 1.05 == 5% margin."""
    return sum(implied_probability(o) for o in odds)


def normalise_probabilities(odds: list[float], method: str = "proportional") -> list[float]:
    """Remove bookmaker margin from a complete outcome set.

    proportional: p_i / sum(p)  (basic, most common)
    power: solve p_i^k with k such that sum == 1 (accounts for favourite-longshot bias)
    """
    raw = [implied_probability(o) for o in odds]
    total = sum(raw)
    if method == "proportional" or len(raw) < 2:
        return [p / total for p in raw]
    if method == "power":
        lo, hi = 0.5, 3.0
        for _ in range(60):
            k = (lo + hi) / 2
            s = sum(p**k for p in raw)
            if s > 1:
                lo = k
            else:
                hi = k
        k = (lo + hi) / 2
        powered = [p**k for p in raw]
        s = sum(powered)
        return [p / s for p in powered]
    raise ValueError(f"unknown normalisation method {method}")


def fractional_to_decimal(text: str) -> float:
    f = Fraction(text.replace(" ", ""))
    return float(f) + 1.0


def american_to_decimal(value: float) -> float:
    if value > 0:
        return 1.0 + value / 100.0
    return 1.0 + 100.0 / abs(value)


def decimal_to_american(odds: float) -> float:
    return (odds - 1) * 100 if odds >= 2 else -100 / (odds - 1)


@dataclass
class BookmakerPrice:
    bookmaker: str
    odds: float
    recorded_at: datetime | None = None


@dataclass
class MarketComparison:
    selection: str
    prices: list[BookmakerPrice] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return len(self.prices) > 0

    @property
    def best(self) -> BookmakerPrice | None:
        return max(self.prices, key=lambda p: p.odds) if self.prices else None

    @property
    def worst(self) -> float | None:
        return min(p.odds for p in self.prices) if self.prices else None

    @property
    def median(self) -> float | None:
        return statistics.median(p.odds for p in self.prices) if self.prices else None

    @property
    def mean(self) -> float | None:
        return statistics.fmean(p.odds for p in self.prices) if self.prices else None

    @property
    def count(self) -> int:
        return len(self.prices)

    @property
    def latest_timestamp(self) -> datetime | None:
        ts = [p.recorded_at for p in self.prices if p.recorded_at]
        return max(ts) if ts else None

    def as_dict(self) -> dict:
        b = self.best
        return {
            "selection": self.selection,
            "best_odds": b.odds if b else None,
            "best_bookmaker": b.bookmaker if b else None,
            "median_odds": self.median,
            "mean_odds": self.mean,
            "min_odds": self.worst,
            "max_odds": b.odds if b else None,
            "bookmaker_count": self.count,
            "prices": [{"bookmaker": p.bookmaker, "odds": p.odds} for p in sorted(self.prices, key=lambda p: -p.odds)],
        }


def market_probability_for_selection(
    selection: str, comparisons: dict[str, MarketComparison], method: str = "proportional", use: str = "median", required_outcomes: int | None = None
) -> tuple[float | None, float | None]:
    """Overround-removed market probability for `selection` given comparisons for the complete outcome set.

    Uses median odds per outcome (robust to a single outlier bookmaker). Returns (normalised, raw_implied).
    If any outcome in the set has no price (fewer than `required_outcomes`, default 2), the margin cannot
    be computed and (None, raw) is returned: the value engine then reports MARKET PROBABILITY UNAVAILABLE.
    """
    if selection not in comparisons or not comparisons[selection].available:
        return None, None
    getter = (lambda c: c.median) if use == "median" else (lambda c: c.best.odds)
    raw = implied_probability(getter(comparisons[selection]))
    if len(comparisons) < (required_outcomes or 2):
        return None, raw
    odds_list: list[float] = []
    order: list[str] = []
    for sel, comp in comparisons.items():
        if not comp.available:
            return None, raw
        odds_list.append(getter(comp))
        order.append(sel)
    normalised = normalise_probabilities(odds_list, method)
    return normalised[order.index(selection)], raw


def odds_movement(opening: float | None, current: float | None) -> dict:
    if opening is None or current is None:
        return {"opening": opening, "current": current, "movement": None, "movement_pct": None, "direction": "unknown"}
    move = current - opening
    return {
        "opening": opening,
        "current": current,
        "movement": round(move, 3),
        "movement_pct": round(move / opening * 100, 2),
        "direction": "shortening" if move < -1e-9 else "drifting" if move > 1e-9 else "stable",
    }


def closing_line_value(taken_odds: float, closing_odds: float) -> float:
    """CLV as the relative change in implied probability: (1/closing) / (1/taken) - 1 == taken/closing - 1."""
    return taken_odds / closing_odds - 1.0
