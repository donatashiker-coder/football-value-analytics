"""Optional alerts (email / Telegram / Discord). Only fire when EV, confidence, data quality and odds freshness
all pass the configured thresholds. Never sends anything if no channel is configured."""
from __future__ import annotations

import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.services.settings_service import get_setting
from app.utils.logging import get_logger

log = get_logger(__name__)


def eligible_alerts(db: Session, opportunities: list[dict]) -> list[dict]:
    cfg = get_setting(db, "alerts")
    now = datetime.now(UTC)
    out = []
    for o in opportunities:
        if o["status"] != "VALUE_CANDIDATE" or o["expected_value"] is None:
            continue
        if o["expected_value"] < float(cfg["min_ev"]) or o["confidence"] < float(cfg["min_confidence"]) or o["data_quality"] < float(cfg["min_data_quality"]):
            continue
        if o.get("odds_recorded_at"):
            age = (now - datetime.fromisoformat(o["odds_recorded_at"])).total_seconds() / 3600
            if age > float(cfg["max_odds_age_hours"]):
                continue
        out.append(o)
    return out


def format_alert(o: dict) -> str:
    prefix = "[DEMO] " if o.get("is_demo") else ""
    return f"{prefix}VALUE CANDIDATE - {o['home_team']} v {o['away_team']} ({o['competition']}) - {o['market']} - Model {o['model_probability'] * 100:.0f}% - Odds {o['best_odds']:.2f} ({o['best_bookmaker']}) - EV {o['expected_value'] * 100:+.1f}% - Confidence {o['confidence']:.0f}/100. Statistical estimate, not a guarantee."


async def send_alerts(messages: list[str]) -> dict:
    s = get_settings()
    sent = {"email": 0, "telegram": 0, "discord": 0, "skipped": 0}
    if not messages:
        return sent
    body = "\n\n".join(messages)
    if s.smtp_host and s.smtp_user and s.alert_email_to:
        try:
            msg = EmailMessage()
            msg["Subject"] = "Football Value Analytics - value candidates"
            msg["From"], msg["To"] = s.smtp_user, s.alert_email_to
            msg.set_content(body + "\n\nStatistical analysis is not a guarantee of future results.")
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
                smtp.starttls()
                smtp.login(s.smtp_user, s.smtp_password or "")
                smtp.send_message(msg)
            sent["email"] = len(messages)
        except (OSError, smtplib.SMTPException) as exc:
            log.warning("email alert failed: %s", exc)
    async with httpx.AsyncClient(timeout=20) as client:
        if s.telegram_bot_token and s.telegram_chat_id:
            for m in messages:
                try:
                    await client.post(f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage", json={"chat_id": s.telegram_chat_id, "text": m})
                    sent["telegram"] += 1
                except httpx.HTTPError as exc:
                    log.warning("telegram alert failed: %s", exc)
        if s.discord_webhook_url:
            for m in messages:
                try:
                    await client.post(s.discord_webhook_url, json={"content": m[:1900]})
                    sent["discord"] += 1
                except httpx.HTTPError as exc:
                    log.warning("discord alert failed: %s", exc)
    if not any((s.smtp_host, s.telegram_bot_token, s.discord_webhook_url)):
        sent["skipped"] = len(messages)
    return sent
