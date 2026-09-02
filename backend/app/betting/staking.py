"""Stake sizing. Default is FLAT. Kelly variants are capped to avoid excessive staking."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StakeConfig:
    method: str = "flat"  # flat | percentage | quarter_kelly | half_kelly | full_kelly
    flat_stake: float = 10.0
    percentage: float = 0.01  # of bankroll
    max_stake_fraction: float = 0.02  # cap on any stake as fraction of bankroll
    min_stake: float = 0.0


def kelly_fraction(probability: float, odds: float) -> float:
    """Full Kelly fraction f* = (p*(O-1) - (1-p)) / (O-1). Negative means no bet."""
    b = odds - 1.0
    if b <= 0:
        return 0.0
    return (probability * b - (1.0 - probability)) / b


def calculate_stake(probability: float | None, odds: float, bankroll: float, cfg: StakeConfig) -> float:
    method = cfg.method
    if method == "flat":
        stake = cfg.flat_stake
    elif method == "percentage":
        stake = bankroll * cfg.percentage
    elif method in ("quarter_kelly", "half_kelly", "full_kelly"):
        if probability is None:
            return 0.0
        f = kelly_fraction(probability, odds)
        mult = {"quarter_kelly": 0.25, "half_kelly": 0.5, "full_kelly": 1.0}[method]
        stake = max(f, 0.0) * mult * bankroll
    else:
        raise ValueError(f"unknown stake method {method}")
    cap = bankroll * cfg.max_stake_fraction if bankroll > 0 else stake
    stake = min(stake, cap) if method != "flat" else stake
    if bankroll > 0 and method == "flat":
        stake = min(stake, bankroll)  # never stake more than the bankroll
    return round(max(stake, cfg.min_stake if stake > 0 else 0.0), 2)


def settle(stake: float, odds: float, outcome: str) -> float:
    """Profit for a settled bet. outcome: won | lost | push | void | half_won | half_lost."""
    if outcome == "won":
        return round(stake * (odds - 1.0), 2)
    if outcome == "lost":
        return round(-stake, 2)
    if outcome in ("push", "void"):
        return 0.0
    if outcome == "half_won":
        return round(stake * (odds - 1.0) / 2.0, 2)
    if outcome == "half_lost":
        return round(-stake / 2.0, 2)
    raise ValueError(f"unknown outcome {outcome}")
