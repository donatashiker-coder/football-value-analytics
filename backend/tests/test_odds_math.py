from datetime import UTC, datetime

import pytest

from app.odds.math import (
    BookmakerPrice,
    MarketComparison,
    american_to_decimal,
    closing_line_value,
    fair_odds,
    fractional_to_decimal,
    implied_probability,
    market_probability_for_selection,
    normalise_probabilities,
    odds_movement,
    overround,
)


def test_implied_and_fair_odds():
    assert implied_probability(2.0) == 0.5
    assert fair_odds(0.5) == 2.0
    assert fair_odds(0.25) == 4.0
    assert fair_odds(0.56) == pytest.approx(1.7857, rel=1e-4)
    with pytest.raises(ValueError):
        implied_probability(1.0)
    with pytest.raises(ValueError):
        fair_odds(0.0)


def test_overround_and_normalisation():
    odds = [2.0, 3.5, 4.0]  # 0.5 + 0.2857 + 0.25 = 1.0357
    assert overround(odds) == pytest.approx(1.0357, rel=1e-3)
    p = normalise_probabilities(odds)
    assert sum(p) == pytest.approx(1.0)
    assert p[0] == pytest.approx(0.5 / 1.0357, rel=1e-3)
    pw = normalise_probabilities(odds, "power")
    assert sum(pw) == pytest.approx(1.0, abs=1e-6)
    # power method gives the favourite a slightly larger share than proportional
    assert pw[0] > p[0]


def test_two_way_market_example():
    # Over 2.5 at 2.00, Under 2.5 at 1.90 -> overround 1.0263
    p = normalise_probabilities([2.0, 1.9])
    assert p[0] == pytest.approx(0.4872, rel=1e-3)
    assert p[1] == pytest.approx(0.5128, rel=1e-3)


def test_conversions():
    assert fractional_to_decimal("5/2") == 3.5
    assert fractional_to_decimal("1/1") == 2.0
    assert american_to_decimal(150) == 2.5
    assert american_to_decimal(-200) == 1.5


def test_bookmaker_comparison():
    ts = datetime.now(UTC)
    comp = MarketComparison("over", [BookmakerPrice("bet365", 2.00, ts), BookmakerPrice("hill", 1.95, ts), BookmakerPrice("betfair", 2.05, ts), BookmakerPrice("ladbrokes", 1.90, ts), BookmakerPrice("coral", 2.02, ts)])
    assert comp.best.odds == 2.05 and comp.best.bookmaker == "betfair"
    assert comp.median == 2.00
    assert comp.worst == 1.90
    assert comp.count == 5
    assert comp.mean == pytest.approx(1.984)


def test_market_probability_for_selection_requires_complete_set():
    over = MarketComparison("over", [BookmakerPrice("a", 2.0), BookmakerPrice("b", 2.1)])
    under = MarketComparison("under", [BookmakerPrice("a", 1.85), BookmakerPrice("b", 1.8)])
    p, raw = market_probability_for_selection("goals_over_2.5", {"goals_over_2.5": over, "goals_under_2.5": under})
    assert raw == pytest.approx(1 / 2.05)
    assert p == pytest.approx((1 / 2.05) / (1 / 2.05 + 1 / 1.825))
    p2, raw2 = market_probability_for_selection("goals_over_2.5", {"goals_over_2.5": over})
    assert p2 is None and raw2 == pytest.approx(1 / 2.05)


def test_movement_and_clv():
    m = odds_movement(2.10, 1.95)
    assert m["direction"] == "shortening" and m["movement_pct"] == pytest.approx(-7.14, abs=0.01)
    assert odds_movement(None, 2.0)["direction"] == "unknown"
    assert closing_line_value(2.10, 1.95) == pytest.approx(2.10 / 1.95 - 1)
    assert closing_line_value(2.0, 2.0) == 0.0
