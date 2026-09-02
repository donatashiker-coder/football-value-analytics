"""Count distributions used by the goal and corner models.

All functions are pure and deterministic so they can be unit tested against known values.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

MAX_GOALS = 10  # score matrix truncation (P(goals > 10) is negligible for football)
MAX_COUNT = 40  # corner pmf truncation


def poisson_pmf(lam: float, max_k: int) -> np.ndarray:
    """Probability mass function of Poisson(lam) for k = 0..max_k, renormalised to sum to 1."""
    lam = max(lam, 1e-9)
    k = np.arange(max_k + 1)
    pmf = stats.poisson.pmf(k, lam)
    return pmf / pmf.sum()


def negative_binomial_pmf(mean: float, dispersion: float, max_k: int) -> np.ndarray:
    """Negative binomial parameterised by mean and dispersion (variance = mean + mean^2 / dispersion).

    As dispersion -> inf the distribution converges to Poisson. dispersion must be > 0.
    """
    mean = max(mean, 1e-9)
    if dispersion <= 0 or not math.isfinite(dispersion) or dispersion > 1e6:
        return poisson_pmf(mean, max_k)
    n = dispersion
    p = n / (n + mean)
    k = np.arange(max_k + 1)
    pmf = stats.nbinom.pmf(k, n, p)
    return pmf / pmf.sum()


def prob_over(pmf: np.ndarray, line: float) -> float:
    """P(X > line) for a half-integer line, e.g. 2.5 -> P(X >= 3)."""
    threshold = math.floor(line) + 1
    if threshold > len(pmf) - 1:
        return 0.0
    return float(pmf[threshold:].sum())


def prob_under(pmf: np.ndarray, line: float) -> float:
    return 1.0 - prob_over(pmf, line)


def prob_exact(pmf: np.ndarray, k: int) -> float:
    return float(pmf[k]) if 0 <= k < len(pmf) else 0.0


def dixon_coles_tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    """Dixon-Coles low-score correction factor for scoreline (x, y)."""
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(home_lambda: float, away_lambda: float, rho: float = 0.0, max_goals: int = MAX_GOALS) -> np.ndarray:
    """Joint scoreline probability matrix M[h, a] = P(home=h, away=a).

    rho == 0 gives the independent Poisson model; rho != 0 applies the Dixon-Coles adjustment.
    The matrix is renormalised so all probabilities sum to one.
    """
    ph = poisson_pmf(home_lambda, max_goals)
    pa = poisson_pmf(away_lambda, max_goals)
    m = np.outer(ph, pa)
    if rho != 0.0:
        for x in range(2):
            for y in range(2):
                m[x, y] *= dixon_coles_tau(x, y, home_lambda, away_lambda, rho)
        m = np.clip(m, 0.0, None)
    return m / m.sum()


def total_goals_pmf(matrix: np.ndarray) -> np.ndarray:
    n = matrix.shape[0]
    out = np.zeros(2 * n - 1)
    for h in range(n):
        for a in range(n):
            out[h + a] += matrix[h, a]
    return out


def matrix_probabilities(matrix: np.ndarray) -> dict[str, float]:
    """Derive the standard set of market probabilities from a scoreline matrix."""
    n = matrix.shape[0]
    home = float(np.tril(matrix, -1).sum())  # h > a
    away = float(np.triu(matrix, 1).sum())  # a > h
    draw = float(np.trace(matrix))
    total = total_goals_pmf(matrix)
    home_goals = matrix.sum(axis=1)
    away_goals = matrix.sum(axis=0)
    btts = float(matrix[1:, 1:].sum())
    out: dict[str, float] = {
        "home": home,
        "draw": draw,
        "away": away,
        "dc_home_draw": home + draw,
        "dc_home_away": home + away,
        "dc_draw_away": draw + away,
        "dnb_home": home / (home + away) if home + away > 0 else 0.5,
        "dnb_away": away / (home + away) if home + away > 0 else 0.5,
        "btts_yes": btts,
        "btts_no": 1.0 - btts,
        "home_clean_sheet": float(away_goals[0]),
        "away_clean_sheet": float(home_goals[0]),
    }
    for line in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5):
        out[f"over_{line}"] = prob_over(total, line)
        out[f"under_{line}"] = prob_under(total, line)
    for line in (0.5, 1.5, 2.5):
        out[f"home_over_{line}"] = prob_over(home_goals, line)
        out[f"home_under_{line}"] = prob_under(home_goals, line)
        out[f"away_over_{line}"] = prob_over(away_goals, line)
        out[f"away_under_{line}"] = prob_under(away_goals, line)
    # Asian handicap (whole and half lines), from the home perspective. Whole lines can push.
    for hcap in (-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0):
        win = lose = push = 0.0
        for h in range(n):
            for a in range(n):
                diff = h + hcap - a
                if diff > 0:
                    win += matrix[h, a]
                elif diff < 0:
                    lose += matrix[h, a]
                else:
                    push += matrix[h, a]
        out[f"ah_home_{hcap:+.1f}"] = float(win)
        out[f"ah_home_{hcap:+.1f}_push"] = float(push)
        out[f"ah_away_{-hcap:+.1f}"] = float(lose)
    return out


def most_likely_scores(matrix: np.ndarray, top: int = 5) -> list[tuple[int, int, float]]:
    n = matrix.shape[0]
    flat = [(h, a, float(matrix[h, a])) for h in range(n) for a in range(n)]
    flat.sort(key=lambda t: t[2], reverse=True)
    return flat[:top]
