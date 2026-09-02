"""Model evaluation: Brier score, log loss, calibration curves, ROC-AUC, drift detection."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_predicted: float
    observed_rate: float


@dataclass
class EvaluationReport:
    n: int
    brier: float | None
    log_loss: float | None
    roc_auc: float | None
    expected_calibration_error: float | None
    bins: list[CalibrationBin] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "brier": self.brier,
            "log_loss": self.log_loss,
            "roc_auc": self.roc_auc,
            "expected_calibration_error": self.expected_calibration_error,
            "bins": [b.__dict__ for b in self.bins],
        }


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    return float(np.mean((probs - outcomes) ** 2))


def log_loss(probs: np.ndarray, outcomes: np.ndarray, eps: float = 1e-12) -> float:
    p = np.clip(probs, eps, 1 - eps)
    return float(-np.mean(outcomes * np.log(p) + (1 - outcomes) * np.log(1 - p)))


def roc_auc(probs: np.ndarray, outcomes: np.ndarray) -> float | None:
    pos = probs[outcomes == 1]
    neg = probs[outcomes == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    # rank-based AUC (Mann-Whitney U), tie-aware
    from scipy.stats import rankdata

    ranks = rankdata(np.concatenate([pos, neg]))
    r_pos = ranks[: len(pos)].sum()
    return float((r_pos - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def calibration_bins(probs: np.ndarray, outcomes: np.ndarray, n_bins: int = 10) -> list[CalibrationBin]:
    edges = np.linspace(0, 1, n_bins + 1)
    bins: list[CalibrationBin] = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (probs >= lo) & (probs < hi) if i < n_bins - 1 else (probs >= lo) & (probs <= hi)
        c = int(mask.sum())
        if c == 0:
            continue
        bins.append(CalibrationBin(float(lo), float(hi), c, float(probs[mask].mean()), float(outcomes[mask].mean())))
    return bins


def expected_calibration_error(bins: list[CalibrationBin], n: int) -> float | None:
    if n == 0:
        return None
    return float(sum(b.count / n * abs(b.mean_predicted - b.observed_rate) for b in bins))


def evaluate(probs: list[float] | np.ndarray, outcomes: list[int] | np.ndarray, n_bins: int = 10) -> EvaluationReport:
    p = np.asarray(probs, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    if len(p) == 0:
        return EvaluationReport(0, None, None, None, None, [])
    bins = calibration_bins(p, y, n_bins)
    return EvaluationReport(
        n=len(p),
        brier=brier_score(p, y),
        log_loss=log_loss(p, y),
        roc_auc=roc_auc(p, y),
        expected_calibration_error=expected_calibration_error(bins, len(p)),
        bins=bins,
    )


def detect_drift(recent_brier: float | None, historical_brier: float | None, recent_n: int, threshold: float = 0.02, min_n: int = 100) -> dict:
    """Flag drift when recent Brier is materially worse than the historical baseline."""
    if recent_brier is None or historical_brier is None or recent_n < min_n:
        return {"drift_detected": False, "reason": "insufficient sample", "recent_n": recent_n}
    diff = recent_brier - historical_brier
    return {
        "drift_detected": diff > threshold,
        "recent_brier": recent_brier,
        "historical_brier": historical_brier,
        "difference": diff,
        "threshold": threshold,
        "recent_n": recent_n,
    }


def platt_scale(probs: np.ndarray, outcomes: np.ndarray) -> tuple[float, float]:
    """Fit a logistic recalibration p' = sigmoid(a*logit(p)+b). Returns (a, b). Identity if data is thin."""
    if len(probs) < 200:
        return 1.0, 0.0
    from sklearn.linear_model import LogisticRegression

    p = np.clip(probs, 1e-6, 1 - 1e-6)
    x = np.log(p / (1 - p)).reshape(-1, 1)
    lr = LogisticRegression(C=1e6)
    lr.fit(x, outcomes)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


def apply_platt(p: float, a: float, b: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    z = a * math.log(p / (1 - p)) + b
    return 1.0 / (1.0 + math.exp(-z))
