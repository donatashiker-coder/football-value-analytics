import pytest

from app.betting.settlement import ResultData, outcome_to_binary, settle_market
from app.betting.staking import StakeConfig, calculate_stake, kelly_fraction, settle

R = ResultData(home_goals=2, away_goals=1, home_goals_ht=1, away_goals_ht=1, home_corners=6, away_corners=4, home_corners_ht=3, away_corners_ht=2)


@pytest.mark.parametrize(
    "market,expected",
    [
        ("match_home", "won"), ("match_draw", "lost"), ("match_away", "lost"), ("dc_home_draw", "won"), ("dc_draw_away", "lost"), ("dnb_home", "won"), ("dnb_away", "lost"),
        ("goals_over_2.5", "won"), ("goals_under_2.5", "lost"), ("goals_over_3.5", "lost"), ("btts_yes", "won"), ("btts_no", "lost"), ("home_goals_over_1.5", "won"), ("away_goals_over_1.5", "lost"),
        ("corners_over_9.5", "won"), ("corners_under_9.5", "lost"), ("corners_over_10.5", "lost"), ("home_corners_over_5.5", "won"), ("away_corners_under_4.5", "won"),
        ("1h_goals_over_1.5", "won"), ("1h_btts_yes", "won"), ("1h_corners_over_4.5", "won"), ("ah_home_-1.0", "push"), ("ah_home_-0.5", "won"), ("ah_away_+1.5", "won"), ("ah_home_-1.5", "lost"),
    ],
)
def test_settlement(market, expected):
    assert settle_market(market, R) == expected


def test_settlement_missing_data_is_unsettled():
    r = ResultData(1, 1)
    assert settle_market("corners_over_9.5", r) == "unsettled"
    assert settle_market("1h_goals_over_0.5", r) == "unsettled"
    assert settle_market("dnb_home", r) == "push"
    assert settle_market("unknown_market", r) == "unsettled"
    assert outcome_to_binary("won") == 1 and outcome_to_binary("lost") == 0 and outcome_to_binary("push") is None


def test_settle_profit():
    assert settle(10, 2.5, "won") == 15.0
    assert settle(10, 2.5, "lost") == -10.0
    assert settle(10, 2.5, "push") == 0.0
    assert settle(10, 2.5, "half_won") == 7.5
    assert settle(10, 2.5, "half_lost") == -5.0


def test_kelly_and_caps():
    assert kelly_fraction(0.5, 2.0) == 0.0
    assert kelly_fraction(0.6, 2.0) == pytest.approx(0.2)
    assert kelly_fraction(0.4, 2.0) < 0
    bank = 1000.0
    assert calculate_stake(0.6, 2.0, bank, StakeConfig(method="flat", flat_stake=10)) == 10.0
    assert calculate_stake(0.6, 2.0, bank, StakeConfig(method="percentage", percentage=0.01)) == 10.0
    # full kelly = 20% but capped at 2% of bankroll
    assert calculate_stake(0.6, 2.0, bank, StakeConfig(method="full_kelly", max_stake_fraction=0.02)) == 20.0
    assert calculate_stake(0.6, 2.0, bank, StakeConfig(method="quarter_kelly", max_stake_fraction=0.10)) == 50.0
    assert calculate_stake(0.4, 2.0, bank, StakeConfig(method="half_kelly")) == 0.0
    assert calculate_stake(None, 2.0, bank, StakeConfig(method="half_kelly")) == 0.0
    assert calculate_stake(0.6, 2.0, 5.0, StakeConfig(method="flat", flat_stake=10)) == 5.0
