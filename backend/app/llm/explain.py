"""Optional LLM explanation layer.

The LLM receives ONLY structured JSON produced by the statistical engine and is instructed to explain it.
It cannot change probabilities, odds or any stored number. If no provider is configured the function
returns None and the UI shows the deterministic explanation instead.
"""
from __future__ import annotations

import json

import httpx

from app.config import get_settings
from app.utils.logging import get_logger

log = get_logger(__name__)

SYSTEM_PROMPT = (
    "You are an analytical assistant for a football statistics platform. Do not guarantee betting outcomes. "
    "Do not invent information. Only discuss values contained in the supplied structured data. Never use words such as "
    "'guaranteed', 'sure', 'lock', 'certain' or 'can't lose'. Use language like 'model indicates', 'estimated probability', "
    "'potential value', 'statistical edge'. Write 3-5 sentences in plain English for a knowledgeable reader. "
    "Mention the main supporting factors and the main risks. If data is marked unavailable, say so."
)

FORBIDDEN = ("guarantee", "guaranteed", "sure bet", "sure win", "lock", "can't lose", "cannot lose", "free money", "certain win")


def _sanitise(text: str) -> str:
    lowered = text.lower()
    if any(f in lowered for f in FORBIDDEN):
        return text + "\n\n[Note: wording adjusted. Statistical analysis is not a guarantee of future results.]"
    return text


def explanation_payload(opp: dict, features: dict | None) -> dict:
    """Strict subset of stored data passed to the LLM."""
    hs = (features or {}).get("home_stats", {}) or {}
    as_ = (features or {}).get("away_stats", {}) or {}
    keep = ("goals_for_avg", "goals_against_avg", "xg_for_avg", "xg_against_avg", "over_2.5_last_5", "btts_last_10", "corners_for_avg", "corners_against_avg", "corners_for_last_5", "clean_sheet_pct", "points_per_game", "matches")
    return {
        "match": f"{opp['home_team']} vs {opp['away_team']}", "competition": opp["competition"], "market": opp["market"], "model_probability": opp["model_probability"], "market_probability": opp["market_probability"],
        "fair_odds": opp["fair_odds"], "best_odds": opp["best_odds"], "expected_value": opp["expected_value"], "confidence": opp["confidence"], "data_quality": opp["data_quality"], "status": opp["status"],
        "key_factors": opp["key_factors"], "risk_factors": opp["risk_factors"], "no_bet_reasons": opp["no_bet_reasons"],
        "home_stats": {k: hs.get(k) for k in keep}, "away_stats": {k: as_.get(k) for k in keep},
        "home_news": (features or {}).get("home_news", {}).get("names"), "away_news": (features or {}).get("away_news", {}).get("names"),
    }


async def generate_explanation(payload: dict) -> str | None:
    s = get_settings()
    user = "Explain this analysis using only the data below.\n\n" + json.dumps(payload, indent=2, default=str)
    try:
        if s.llm_provider == "anthropic" and s.anthropic_api_key:
            async with httpx.AsyncClient(timeout=40) as client:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": s.anthropic_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json={"model": s.llm_model, "max_tokens": 400, "system": SYSTEM_PROMPT, "messages": [{"role": "user", "content": user}]},
                )
                r.raise_for_status()
                return _sanitise("".join(b.get("text", "") for b in r.json().get("content", [])))
        if s.llm_provider == "openai" and s.openai_api_key:
            async with httpx.AsyncClient(timeout=40) as client:
                r = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {s.openai_api_key}"},
                    json={"model": s.llm_model, "max_tokens": 400, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]},
                )
                r.raise_for_status()
                return _sanitise(r.json()["choices"][0]["message"]["content"])
    except httpx.HTTPError as exc:
        log.warning("LLM explanation failed: %s", exc)
    return None
