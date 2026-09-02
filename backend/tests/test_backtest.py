"""Backtest arithmetic on a tiny artificial dataset with known odds, probabilities and outcomes."""
from app.backtesting.engine import BetRecord, summarise


def _bet(i, odds, outcome, ev=0.05, clv=None):
    profit = (odds - 1) if outcome == "won" else -1.0 if outcome == "lost" else 0.0
    return BetRecord(f"f{i}", f"2025-0{1 + i % 9}-0{1 + i % 9}T15:00:00+00:00", "DEMO_A" if i % 2 else "DEMO_B", "goals_over_2.5" if i % 3 else "corners_over_9.5", odds, "demo_book_1", 0.55, 0.5, ev, 1.0, outcome, profit, odds * 0.98 if clv is None else clv, (odds / (odds * 0.98) - 1) if clv is None else None, 2025, 2.9)


def test_manual_profit_calculation():
    # 10 flat 1-unit bets: 6 won at 2.0 (+6), 3 lost (-3), 1 push (0) -> profit +3, staked 10, ROI +30%
    bets = [_bet(i, 2.0, "won") for i in range(6)] + [_bet(6 + i, 2.0, "lost") for i in range(3)] + [_bet(9, 2.0, "push")]
    summary, breakdowns, curve = summarise(bets, 100.0)
    assert summary["bets"] == 10 and summary["wins"] == 6 and summary["losses"] == 3 and summary["pushes"] == 1
    assert summary["profit"] == 3.0 and summary["total_staked"] == 10.0
    assert abs(summary["roi"] - 0.30) < 1e-9
    assert summary["strike_rate"] == 6 / 9
    assert summary["final_bankroll"] == 103.0
    assert summary["longest_winning_streak"] == 6 and summary["longest_losing_streak"] == 3
    assert summary["profit_factor"] == 2.0
    assert summary["max_drawdown"] == 3.0  # after 6 wins, 3 straight losses
    assert len(curve) == 10 and curve[-1]["equity"] == 103.0
    assert {r["key"] for r in breakdowns["by_league"]} == {"DEMO_A", "DEMO_B"}
    assert breakdowns["by_odds_range"][0]["key"] == "1.80-2.09"
    assert all(r["average_clv"] is not None for r in breakdowns["by_market"])
    assert summary["average_clv"] > 0


def test_empty_backtest():
    s, b, c = summarise([], 100.0)
    assert s["bets"] == 0 and s["roi"] is None and b == {} and c == []


def test_drawdown_with_losses_first():
    bets = [_bet(0, 3.0, "lost"), _bet(1, 3.0, "lost"), _bet(2, 3.0, "won"), _bet(3, 3.0, "won")]
    s, _, _ = summarise(bets, 10.0)
    assert s["profit"] == 2.0 and s["max_drawdown"] == 2.0 and s["max_drawdown_pct"] == 0.2
