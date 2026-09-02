"""Ingestion: persist provider DTOs into the database (idempotent upserts, provenance recorded)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bookmaker, Competition, Fixture, FixtureStatistic, Injury, Market, Odds, Result, Season, Team
from app.odds.markets import MARKETS
from app.providers.base import FixtureDTO, InjuryDTO, OddsDTO, ProviderUnavailable, TeamMatchStatsDTO
from app.providers.factory import ProviderSet
from app.providers.leagues import LEAGUES
from app.utils.logging import get_logger

log = get_logger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


def season_year_for(d: date, summer_season: bool = False) -> int:
    if summer_season:
        return d.year
    return d.year if d.month >= 7 else d.year - 1


# ---------------------------------------------------------------- seeds
def seed_reference_data(db: Session, demo: bool) -> None:
    """Seed markets, bookmakers and competition catalogue. Safe to run repeatedly."""
    existing = {m.key for m in db.scalars(select(Market))}
    for m in MARKETS:
        if m.key not in existing:
            db.add(Market(key=m.key, group=m.group, name=m.name, line=m.line, period=m.period, outcomes=[x.key for x in MARKETS if x.outcome_set == m.outcome_set]))
    comps = {c.code: c for c in db.scalars(select(Competition))}
    if demo:
        from app.providers.football.demo import DEMO_BOOKMAKERS, DEMO_LEAGUES

        for code, name, country, *_ in DEMO_LEAGUES:
            if code not in comps:
                db.add(Competition(code=code, name=name, country=country, tier=1, enabled=True, source="demo", source_id=code, provider_ids={"demo": code}))
        bks = {b.key for b in db.scalars(select(Bookmaker))}
        for key, name, _ in DEMO_BOOKMAKERS:
            if key not in bks:
                db.add(Bookmaker(key=key, name=name, is_exchange=key.endswith("exchange")))
    else:
        for lg in LEAGUES:
            if lg.code not in comps:
                db.add(
                    Competition(
                        code=lg.code, name=lg.name, country=lg.country, tier=lg.tier, enabled=True, source="catalogue", source_id=lg.code,
                        provider_ids={"api_football": lg.api_football, "football_data": lg.football_data, "the_odds_api": lg.the_odds_api},
                    )
                )
    db.commit()


def get_or_create_season(db: Session, comp: Competition, year: int) -> Season:
    s = db.scalar(select(Season).where(Season.competition_id == comp.id, Season.year == year))
    if s is None:
        s = Season(competition_id=comp.id, year=year, label=f"{year}/{str(year + 1)[-2:]}")
        db.add(s)
        db.flush()
    return s


def get_or_create_team(db: Session, source: str, source_id: str, name: str, comp: Competition | None, demo: bool, cache: dict) -> Team:
    key = (source, source_id)
    if key in cache:
        return cache[key]
    t = db.scalar(select(Team).where(Team.source == source, Team.source_id == source_id))
    if t is None:
        t = Team(name=name, short_name=name[:40], competition_id=comp.id if comp else None, source=source, source_id=source_id, provider_ids={source: source_id}, is_demo=demo, retrieved_at=utcnow())
        db.add(t)
        db.flush()
    elif comp and t.competition_id != comp.id:
        t.competition_id = comp.id
    cache[key] = t
    return t


# ---------------------------------------------------------------- fixtures / results
def upsert_fixtures(db: Session, dtos: list[FixtureDTO], demo: bool) -> dict[str, int]:
    comps = {c.code: c for c in db.scalars(select(Competition))}
    counts = {"created": 0, "updated": 0, "results": 0}
    team_cache: dict = {}
    season_cache: dict[tuple[str, int], Season] = {}
    for d in dtos:
        comp = comps.get(d.competition_code)
        if comp is None:
            continue
        sk = (comp.id, d.season_year)
        if sk not in season_cache:
            season_cache[sk] = get_or_create_season(db, comp, d.season_year)
        season = season_cache[sk]
        home = get_or_create_team(db, d.source, d.home_team_source_id, d.home_team_name, comp, demo, team_cache)
        away = get_or_create_team(db, d.source, d.away_team_source_id, d.away_team_name, comp, demo, team_cache)
        fx = db.scalar(select(Fixture).where(Fixture.source == d.source, Fixture.source_id == d.source_id))
        if fx is None:
            fx = Fixture(competition_id=comp.id, season_id=season.id, home_team_id=home.id, away_team_id=away.id, kickoff_utc=d.kickoff_utc, status=d.status, matchday=d.matchday, venue=d.venue, source=d.source, source_id=d.source_id, is_demo=demo, retrieved_at=utcnow(), last_updated_at=d.last_updated_at)
            db.add(fx)
            db.flush()
            counts["created"] += 1
        else:
            fx.kickoff_utc, fx.status, fx.matchday, fx.retrieved_at, fx.last_updated_at = d.kickoff_utc, d.status, d.matchday, utcnow(), d.last_updated_at
            counts["updated"] += 1
        if d.status == "FINISHED" and d.home_goals is not None and d.away_goals is not None:
            res = db.scalar(select(Result).where(Result.fixture_id == fx.id))
            outcome = "H" if d.home_goals > d.away_goals else "A" if d.away_goals > d.home_goals else "D"
            if res is None:
                db.add(Result(fixture_id=fx.id, home_goals=d.home_goals, away_goals=d.away_goals, home_goals_ht=d.home_goals_ht, away_goals_ht=d.away_goals_ht, outcome=outcome, source=d.source, source_id=d.source_id, retrieved_at=utcnow()))
                counts["results"] += 1
            else:
                res.home_goals, res.away_goals, res.home_goals_ht, res.away_goals_ht, res.outcome = d.home_goals, d.away_goals, d.home_goals_ht, d.away_goals_ht, outcome
    db.commit()
    return counts


def upsert_fixture_statistics(db: Session, fixture: Fixture, stats: list[TeamMatchStatsDTO]) -> None:
    if not stats:
        return
    res = db.scalar(select(Result).where(Result.fixture_id == fixture.id))
    for s in stats:
        team = db.scalar(select(Team).where(Team.source == s.source, Team.source_id == s.team_source_id))
        if team is None:
            continue
        row = db.scalar(select(FixtureStatistic).where(FixtureStatistic.fixture_id == fixture.id, FixtureStatistic.team_id == team.id))
        if row is None:
            row = FixtureStatistic(fixture_id=fixture.id, team_id=team.id, is_home=s.is_home, source=s.source, source_id=s.fixture_source_id)
            db.add(row)
        row.goals, row.xg, row.shots, row.shots_on_target, row.possession = s.goals, s.xg, s.shots, s.shots_on_target, s.possession
        row.corners, row.corners_ht, row.yellow_cards, row.red_cards, row.fouls, row.retrieved_at = s.corners, s.corners_ht, s.yellow_cards, s.red_cards, s.fouls, utcnow()
        if res is not None:
            if s.is_home:
                res.home_corners, res.home_corners_ht, res.home_red_cards = s.corners, s.corners_ht, s.red_cards
            else:
                res.away_corners, res.away_corners_ht, res.away_red_cards = s.corners, s.corners_ht, s.red_cards
            if s.first_red_card_minute is not None:
                res.first_red_card_minute = min(s.first_red_card_minute, res.first_red_card_minute or 999)
                flags = dict(res.abnormal_flags or {})
                flags["early_red_card"] = res.first_red_card_minute <= 30
                res.abnormal_flags = flags


# ---------------------------------------------------------------- odds
def _resolve_fixture_for_odds(db: Session, o: OddsDTO, by_source: dict, by_names: dict) -> Fixture | None:
    fx = by_source.get((o.source, o.fixture_source_id))
    if fx is not None:
        return fx
    if o.home_team_name and o.away_team_name and o.kickoff_utc:
        key = (_norm(o.home_team_name), _norm(o.away_team_name), o.kickoff_utc.date())
        return by_names.get(key)
    return None


def _norm(name: str) -> str:
    import re

    n = name.lower()
    for token in (" fc", " afc", " cf", " sc", " ac", " bk", " if", " ff", " united", " city"):
        n = n.replace(token, "")
    return re.sub(r"[^a-z0-9]", "", n)


def upsert_odds(db: Session, dtos: list[OddsDTO], demo: bool, mark_closing_for: set[str] | None = None) -> dict[str, int]:
    """Store an odds snapshot. Previous snapshots for the same (fixture, bookmaker, market, selection) are
    marked is_current=False so history is preserved for movement / CLV analysis."""
    counts = {"stored": 0, "unmatched": 0}
    if not dtos:
        return counts
    horizon = utcnow() - timedelta(days=2)
    fixtures = list(db.scalars(select(Fixture).where(Fixture.kickoff_utc >= horizon)))
    by_source = {(f.source, f.source_id): f for f in fixtures}
    # name-based index for providers that use their own ids (The Odds API)
    by_names: dict = {}
    for f in fixtures:
        by_names[(_norm(f.home_team.name), _norm(f.away_team.name), f.kickoff_utc.date())] = f
    bks = {b.key for b in db.scalars(select(Bookmaker))}
    for o in dtos:
        fx = _resolve_fixture_for_odds(db, o, by_source, by_names)
        if fx is None:
            counts["unmatched"] += 1
            continue
        if o.bookmaker_key not in bks:
            db.add(Bookmaker(key=o.bookmaker_key, name=o.bookmaker_name, is_exchange="exchange" in o.bookmaker_key or "betfair" in o.bookmaker_key))
            bks.add(o.bookmaker_key)
        prev = list(db.scalars(select(Odds).where(Odds.fixture_id == fx.id, Odds.bookmaker_key == o.bookmaker_key, Odds.market_key == o.market_key, Odds.selection == o.selection, Odds.is_current.is_(True))))
        if prev and abs(prev[-1].decimal_odds - o.decimal_odds) < 1e-9:
            prev[-1].last_seen_at = o.recorded_at  # unchanged price: keep the opening timestamp, record last confirmation
            continue
        for p in prev:
            p.is_current = False
        db.add(Odds(fixture_id=fx.id, bookmaker_key=o.bookmaker_key, market_key=o.market_key, selection=o.selection, line=o.line, decimal_odds=o.decimal_odds, recorded_at=o.recorded_at, last_seen_at=o.recorded_at, is_current=True, is_closing=bool(mark_closing_for and fx.id in mark_closing_for), source=o.source, source_id=o.fixture_source_id, retrieved_at=utcnow(), is_demo=demo))
        counts["stored"] += 1
    db.commit()
    return counts


# ---------------------------------------------------------------- injuries
def upsert_injuries(db: Session, team: Team, dtos: list[InjuryDTO]) -> int:
    for inj in db.scalars(select(Injury).where(Injury.team_id == team.id, Injury.active.is_(True))):
        inj.active = False
    n = 0
    for d in dtos:
        db.add(Injury(team_id=team.id, player_name=d.player_name, reason=d.reason, status=d.status, reported_at=d.reported_at or utcnow(), expected_return=d.expected_return, source=d.source, source_id=d.player_source_id, retrieved_at=utcnow(), active=True))
        n += 1
    db.commit()
    return n


# ---------------------------------------------------------------- orchestration
async def update_fixtures_and_results(db: Session, providers: ProviderSet, seasons_back: int = 2, days_ahead: int = 7) -> dict:
    """Refresh fixtures for enabled competitions (results for current + previous seasons, upcoming fixtures)."""
    summary: dict = {"competitions": 0, "fixtures": 0, "results": 0, "errors": []}
    today = utcnow().date()
    comps = list(db.scalars(select(Competition).where(Competition.enabled.is_(True))))
    for comp in comps:
        summer = any(lg.code == comp.code and lg.summer_season for lg in LEAGUES)
        current = season_year_for(today, summer)
        years = [current - i for i in range(seasons_back + 1)]
        if providers.is_demo:
            years = list(providers.football.seasons)  # type: ignore[attr-defined]
        for year in years:
            try:
                dtos = await providers.football.get_results(comp.code, year)
                if year == max(years):
                    dtos += await providers.football.get_fixtures(comp.code, year, today, today + timedelta(days=days_ahead))
            except ProviderUnavailable as exc:
                summary["errors"].append(f"{comp.code} {year}: {exc}")
                continue
            c = upsert_fixtures(db, dtos, providers.is_demo)
            summary["fixtures"] += c["created"] + c["updated"]
            summary["results"] += c["results"]
        summary["competitions"] += 1
    return summary


async def update_fixture_statistics(db: Session, providers: ProviderSet, limit: int | None = None) -> dict:
    """Fetch per-match statistics for finished fixtures that do not have them yet (incremental)."""
    if not providers.football.capabilities.corners and not providers.football.capabilities.shots:
        return {"fetched": 0, "skipped": "provider has no per-fixture statistics"}
    have = {r[0] for r in db.execute(select(FixtureStatistic.fixture_id)).all()}
    q = select(Fixture).where(Fixture.status == "FINISHED").order_by(Fixture.kickoff_utc.desc())
    fetched, errors = 0, 0
    for fx in db.scalars(q):
        if fx.id in have:
            continue
        if limit is not None and fetched >= limit:
            break
        try:
            stats = await providers.football.get_fixture_statistics(fx.source_id)
        except ProviderUnavailable:
            errors += 1
            if errors > 5:
                break
            continue
        upsert_fixture_statistics(db, fx, stats)
        fetched += 1
        if fetched % 200 == 0:
            db.commit()
    db.commit()
    return {"fetched": fetched, "errors": errors}


async def update_odds(db: Session, providers: ProviderSet, days_ahead: int = 3, include_historical: bool = True, historical_limit: int | None = None) -> dict:
    if providers.odds is None:
        return {"stored": 0, "unmatched": 0, "warning": "odds provider not configured"}
    today = utcnow().date()
    total = {"stored": 0, "unmatched": 0}
    for comp in db.scalars(select(Competition).where(Competition.enabled.is_(True))):
        try:
            dtos = await providers.odds.get_market_odds(comp.code, ["match_result", "goals", "btts", "corners", "team_goals", "first_half"], today, today + timedelta(days=days_ahead))
        except ProviderUnavailable as exc:
            log.warning("odds unavailable for %s: %s", comp.code, exc)
            continue
        c = upsert_odds(db, dtos, providers.is_demo)
        total["stored"] += c["stored"]
        total["unmatched"] += c["unmatched"]
    if include_historical:
        hist = await update_historical_odds(db, providers, historical_limit)
        total["historical"] = hist.get("stored", 0)
    return total


def bulk_insert_historical_odds(db: Session, fixture: Fixture, opening: list[OddsDTO], closing: list[OddsDTO], demo: bool) -> int:
    """Store opening + closing snapshots for a finished fixture (used for backtests and CLV). Skips fixtures that already have odds."""
    if not opening and not closing:
        return 0
    n = 0
    for dtos, is_closing, is_current in ((opening, False, False), (closing, True, True)):
        for o in dtos:
            db.add(Odds(fixture_id=fixture.id, bookmaker_key=o.bookmaker_key, market_key=o.market_key, selection=o.selection, line=o.line, decimal_odds=o.decimal_odds, recorded_at=o.recorded_at, is_current=is_current, is_closing=is_closing, source=o.source, source_id=o.fixture_source_id, retrieved_at=utcnow(), is_demo=demo))
            n += 1
    return n


async def update_historical_odds(db: Session, providers: ProviderSet, limit: int | None = None) -> dict:
    """Backfill pre-match (opening) and closing odds for finished fixtures where the provider can supply them.

    Only the demo provider and paid odds-history plans offer this; free tiers cannot, in which case backtests
    run on the odds snapshots the platform itself has stored over time.
    """
    prov = providers.odds
    if prov is None or not hasattr(prov, "historical_odds"):
        return {"stored": 0, "warning": "historical odds not available from the configured provider"}
    have = {r[0] for r in db.execute(select(Odds.fixture_id).distinct()).all()}
    bks = {b.key for b in db.scalars(select(Bookmaker))}
    stored, fixtures = 0, 0
    for fx in db.scalars(select(Fixture).where(Fixture.status == "FINISHED").order_by(Fixture.kickoff_utc)):
        if fx.id in have:
            continue
        if limit is not None and fixtures >= limit:
            break
        opening, closing = prov.historical_odds(fx.source_id)
        for o in opening:
            if o.bookmaker_key not in bks:
                db.add(Bookmaker(key=o.bookmaker_key, name=o.bookmaker_name, is_exchange="exchange" in o.bookmaker_key))
                bks.add(o.bookmaker_key)
        stored += bulk_insert_historical_odds(db, fx, opening, closing, providers.is_demo)
        fixtures += 1
        if fixtures % 100 == 0:
            db.commit()
    db.commit()
    return {"stored": stored, "fixtures": fixtures}


async def update_injuries(db: Session, providers: ProviderSet, days_ahead: int = 3) -> dict:
    if providers.injuries is None:
        return {"teams": 0, "warning": "injury provider not configured"}
    today = utcnow().date()
    start, end = datetime(today.year, today.month, today.day, tzinfo=UTC), datetime(today.year, today.month, today.day, tzinfo=UTC) + timedelta(days=days_ahead)
    fixtures = list(db.scalars(select(Fixture).where(Fixture.kickoff_utc >= start, Fixture.kickoff_utc <= end, Fixture.status == "SCHEDULED")))
    done: set[str] = set()
    n = 0
    for fx in fixtures:
        for team in (fx.home_team, fx.away_team):
            if team.id in done:
                continue
            done.add(team.id)
            try:
                dtos = await providers.injuries.get_team_injuries(team.source_id or "", fx.competition.code, season_year_for(today))
            except ProviderUnavailable:
                continue
            upsert_injuries(db, team, dtos)
            n += 1
    return {"teams": n}
