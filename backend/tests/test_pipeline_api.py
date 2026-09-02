"""End-to-end tests over the demo pipeline: ingestion -> statistics -> scan -> value -> API -> paper bets -> backtest."""
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models import Fixture, ModelPrediction, Odds, Result, ValueOpportunity
from app.services.scan import run_scan
from app.statistics.engine import MatchHistory


def test_demo_data_ingested(db):
    assert db.scalar(select(func.count(Fixture.id))) > 1000
    assert db.scalar(select(func.count(Result.id))) > 500
    assert db.scalar(select(func.count(Odds.id))) > 100
    assert db.scalar(select(Fixture.is_demo).limit(1)) is True
    assert db.scalar(select(func.count(Fixture.id)).where(Fixture.status == "SCHEDULED", Fixture.kickoff_utc >= datetime.now(UTC))) > 0


def test_history_cutoff_prevents_leakage(db):
    hist = MatchHistory.load(db)
    team_id, recs = next((t, r) for t, r in hist.by_team.items() if len(r) > 30)
    mid = recs[len(recs) // 2].kickoff
    visible = hist.team_matches(team_id, mid)
    assert all(m.kickoff < mid for m in visible)
    assert len(visible) < len(recs)
    # league averages / elo as of a cutoff only use earlier matches
    comp = recs[0].competition_id
    early = hist.elo_ratings(comp, recs[5].kickoff)
    late = hist.elo_ratings(comp, recs[-1].kickoff)
    assert early != late
    lg = hist.league_averages(comp, recs[0].season_year, recs[0].kickoff)
    assert lg.matches == 0 or lg.fallback or lg.matches < len(hist.competition_records[comp])


def test_scan_produces_reproducible_predictions(db):
    today = datetime.now(UTC).astimezone().date()
    summary = run_scan(db, today, days_ahead=7, is_demo=True)
    assert summary["analysed"] > 0
    opps = list(db.scalars(select(ValueOpportunity)))
    assert opps
    statuses = {o.status for o in opps}
    assert "NO_BET" in statuses  # the system must be comfortable saying NO BET
    for o in opps:
        assert 0 < o.model_probability < 1
        assert o.fair_odds == pytest.approx(1 / o.model_probability, rel=1e-6)
        if o.best_odds is not None:
            assert o.expected_value == pytest.approx(o.model_probability * o.best_odds - 1, rel=1e-6)
        else:
            assert o.status == "ODDS_UNAVAILABLE"
        if o.status == "VALUE_CANDIDATE":
            assert o.expected_value >= 0.03 and o.confidence >= 45 and not o.no_bet_reasons
        assert o.explanation and "Model probability" in o.explanation
        assert not any(bad in o.explanation.lower() for bad in ("guarantee", "sure bet", "can't lose"))
    # every prediction has a feature snapshot and model version
    pred = db.scalar(select(ModelPrediction).where(ModelPrediction.model_name == "dixon_coles"))
    assert pred.feature_snapshot_id and pred.model_version and pred.data_timestamp <= pred.prediction_timestamp
    # the data timestamp never exceeds kickoff
    for p in db.scalars(select(ModelPrediction).limit(200)):
        fx = db.get(Fixture, p.fixture_id)
        assert p.data_timestamp <= fx.kickoff_utc.replace(tzinfo=UTC) if fx.kickoff_utc.tzinfo is None else p.data_timestamp <= fx.kickoff_utc


def test_api_endpoints(client):
    assert client.get("/api/health").json()["status"] == "ok"
    st = client.get("/api/status").json()
    assert st["demo"] is True and "disclaimer" in st
    assert client.get("/api/data-health").status_code == 200
    assert client.get("/api/model-health").status_code == 200
    today = client.get("/api/fixtures/today?days=7").json()
    assert today["count"] > 0
    fid = today["fixtures"][0]["fixture_id"]
    detail = client.get(f"/api/fixtures/{fid}").json()
    assert detail["home_team"] and detail["model"]["probabilities"]["dixon_coles"]
    assert client.get("/api/fixtures/does-not-exist").status_code == 404
    val = client.get("/api/value?days=7&status=&limit=50").json()
    assert val["count"] > 0
    assert client.get("/api/value/today").status_code == 200
    assert client.get("/api/goals?days=7").status_code == 200
    assert client.get("/api/corners?days=7").status_code == 200
    assert client.get("/api/low-scoring?days=7").status_code == 200
    assert client.get("/api/scanners/expected?days=7").status_code == 200
    assert client.get("/api/value/export?days=7&fmt=csv").headers["content-type"].startswith("text/csv")
    leagues = client.get("/api/leagues").json()
    assert leagues and leagues[0]["is_demo"]
    lg = client.get(f"/api/leagues/{leagues[0]['code']}").json()
    assert lg["table"] and lg["table"][0]["position"] == 1
    team = client.get(f"/api/teams/{lg['table'][0]['team_id']}").json()
    assert team["stats"]["matches"] > 0
    assert client.get(f"/api/odds/{fid}").json()["markets"]
    assert client.get("/api/markets").json()
    assert client.get("/api/models").status_code == 200
    assert client.get("/api/settings").json()["settings"]["value"]["min_ev"] == 0.03
    r = client.put("/api/settings/value", json={"value": {"min_ev": 0.05}})
    assert r.status_code == 200 and r.json()["min_ev"] == 0.05
    client.put("/api/settings/value", json={"value": {"min_ev": 0.03}})
    assert client.put("/api/settings/staking", json={"value": {"method": "martingale"}}).status_code == 400
    assert client.get("/api/data-sources").json()["mode"] == "demo"
    assert client.get("/api/reports/daily").json()["disclaimer"]
    assert "FOOTBALL VALUE ANALYTICS" in client.get("/api/reports/daily/text").text
    assert client.get("/api/dashboard").status_code == 200


def test_paper_betting_and_bankroll(client):
    val = client.get("/api/value?days=7&status=VALUE_CANDIDATE&limit=5").json()["opportunities"]
    if not val:
        pytest.skip("no value candidates in demo window")
    o = val[0]
    r = client.post("/api/paper-bets", json={"fixture_id": o["fixture_id"], "market_key": o["market_key"], "selection": o["selection"], "odds": o["best_odds"], "opportunity_id": o["id"], "bookmaker_key": o["best_bookmaker"]})
    assert r.status_code == 201, r.text
    bet = r.json()
    assert bet["status"] == "open" and bet["stake"] > 0 and bet["is_paper"] is True
    assert client.post("/api/paper-bets", json={"fixture_id": o["fixture_id"], "market_key": o["market_key"], "selection": o["selection"], "odds": 0.5}).status_code == 422
    bank = client.get("/api/bankroll").json()
    assert bank["open_bets"] >= 1 and bank["starting_bankroll"] == 1000.0
    preview = client.get("/api/paper-bets/stake-preview?probability=0.6&odds=2.0").json()
    assert preview["stakes"]["full_kelly"] <= 1000 * 0.02 + 1e-9
    assert client.post("/api/paper-bets/settle").status_code == 200


def test_backtest_api_and_walk_forward(client, db):
    r = client.post("/api/backtests/run", json={"strategy": "GOALS_OVER", "min_ev": 0.02, "one_bet_per_fixture": True})
    assert r.status_code == 200, r.text
    bt = r.json()
    s = bt["summary"]
    assert s["fixtures_evaluated"] > 100
    assert s["calibration"]["n"] > 100
    assert 0.0 < s["calibration"]["brier"] < 0.3
    if s["bets"]:
        assert s["roi"] is not None and abs(s["profit"] - sum(b["profit"] for b in bt["bets"])) < 1e-6 or len(bt["bets"]) == 500
        assert bt["breakdowns"]["by_odds_range"]
    assert client.get("/api/backtests").json()["backtests"]
    assert client.get(f"/api/backtests/{bt['id']}").status_code == 200
    comp = client.get("/api/backtests/comparison").json()
    assert any(c["strategy"] == "GOALS_OVER" for c in comp)
    r2 = client.post("/api/backtests/run", json={"strategy": "CORNERS_OVER", "min_ev": 0.02, "corner_distribution": "poisson"})
    assert r2.status_code == 200
    assert r2.json()["summary"].get("corner_distribution_comparison")
    assert client.post("/api/backtests/run", json={"strategy": "NOPE"}).status_code == 400


def test_model_evaluation_after_settlement(client, db):
    """Simulate: predictions made before kickoff, results arrive, predictions are settled and evaluated."""
    from app.services.evaluation import model_leaderboard, model_performance, settle_predictions

    # pick a finished fixture, temporarily pretend it was scheduled, scan it, restore the result, settle
    fx = db.scalar(select(Fixture).where(Fixture.status == "FINISHED").order_by(Fixture.kickoff_utc.desc()))
    res = db.scalar(select(Result).where(Result.fixture_id == fx.id))
    saved = dict(home_goals=res.home_goals, away_goals=res.away_goals, home_goals_ht=res.home_goals_ht, away_goals_ht=res.away_goals_ht, home_corners=res.home_corners, away_corners=res.away_corners, home_corners_ht=res.home_corners_ht, away_corners_ht=res.away_corners_ht, outcome=res.outcome, source=res.source, source_id=res.source_id)
    db.delete(res)
    fx.status = "SCHEDULED"
    db.commit()
    # ensure the fixture is in the scan window by scanning its own day
    kick = fx.kickoff_utc.replace(tzinfo=UTC) if fx.kickoff_utc.tzinfo is None else fx.kickoff_utc
    run_scan(db, kick.astimezone().date(), days_ahead=1, is_demo=True)
    n_pred = db.scalar(select(func.count(ModelPrediction.id)).where(ModelPrediction.fixture_id == fx.id))
    assert n_pred > 0
    for p in db.scalars(select(ModelPrediction).where(ModelPrediction.fixture_id == fx.id)):
        assert p.data_timestamp <= kick
    fx.status = "FINISHED"
    db.add(Result(fixture_id=fx.id, **saved))
    db.commit()
    out = settle_predictions(db)
    assert out["settled"] > 0
    perf = model_performance(db, None, "dixon_coles")
    assert perf["n"] > 0 and perf["brier"] is not None
    assert model_leaderboard(db)
    assert client.get("/api/performance").json()["performance"]["n"] > 0
    assert client.get("/api/models/leaderboard").json()


def test_provider_quota_is_recorded_from_response_headers(client, db_session_factory):
    """The Odds API reports credits in x-requests-remaining/used; the client stores them and
    /api/data-sources shows the numbers exactly as reported."""
    import asyncio

    import httpx

    from app.providers.http import CachedHttpClient
    from app.services.settings_service import all_settings, provider_quotas

    http = CachedHttpClient("the_odds_api", "https://example.test/v4", default_ttl=0, session_factory=db_session_factory, quota_headers=("x-requests-remaining", "x-requests-used"))
    http.transport = httpx.MockTransport(lambda req: httpx.Response(200, json=[], headers={"x-requests-remaining": "437", "x-requests-used": "63"}))
    assert asyncio.run(http.get_json("sports", use_cache=False)) == []

    with db_session_factory() as db:
        q = provider_quotas(db)["the_odds_api"]
        assert (q["remaining"], q["used"]) == (437, 63) and q["updated_at"]
        assert "_provider_quota" not in all_settings(db)  # internal state is not an editable setting
    odds = next(p for p in client.get("/api/data-sources").json()["providers"] if p["key"] == "the_odds_api")
    assert odds["quota"]["remaining"] == 437 and odds["quota"]["used"] == 63


def test_provider_errors_never_contain_api_keys():
    from app.providers.http import redact_secrets

    msg = "Client error '401 Unauthorized' for url 'https://api.the-odds-api.com/v4/sports/x/odds?apiKey=d55dcbb7571243fc84bd6e577cfa2226&regions=uk%2Ceu&markets=h2h'"
    out = redact_secrets(msg)
    assert "d55dcbb7" not in out and "apiKey=***&regions=uk" in out
    assert redact_secrets(None) is None
