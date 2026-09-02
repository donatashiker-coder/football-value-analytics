"""DEMO provider: deterministic synthetic data so the whole pipeline can be exercised without API keys.

Everything produced here is labelled `source="demo"` and `is_demo=True`. Team names are obviously
synthetic ("Demo FC North"). Demo data is NEVER mixed with production data: production mode refuses
to load this provider.

The generator simulates seasons with latent team attack/defence/corner strengths so that model
calibration and backtests behave like real football data (over-dispersed corners, home advantage,
scoreline correlation). Bookmaker odds are simulated as noisy, margin-inflated prices around the
"true" latent probabilities so that some (not all) selections carry value.
"""
from __future__ import annotations

import math
import random
from datetime import UTC, date, datetime, timedelta

import numpy as np

from app.providers.base import (
    CompetitionDTO,
    FixtureDTO,
    FootballDataProvider,
    InjuryDataProvider,
    InjuryDTO,
    OddsDataProvider,
    OddsDTO,
    PlayerDTO,
    ProviderCapabilities,
    TeamDTO,
    TeamMatchStatsDTO,
)

DEMO_LEAGUES = [
    ("DEMO_A", "Demo League A", "Demoland", 20, 1.55, 1.20, 5.6, 4.6),  # code, name, country, teams, home goals avg, away goals avg, home corners, away corners
    ("DEMO_B", "Demo League B", "Demoland", 16, 1.45, 1.15, 5.3, 4.4),
]
DEMO_BOOKMAKERS = [("demo_book_1", "Demo Bookmaker 1", 1.06), ("demo_book_2", "Demo Bookmaker 2", 1.05), ("demo_book_3", "Demo Bookmaker 3", 1.07), ("demo_exchange", "Demo Exchange", 1.02)]
NAMES = ["North", "South", "East", "West", "City", "United", "Rovers", "Athletic", "Town", "Wanderers", "Harbour", "Valley", "Forest", "Lakes", "Hill", "Park", "Rangers", "County", "Albion", "Central"]


class DemoProvider(FootballDataProvider, OddsDataProvider, InjuryDataProvider):
    name = "demo"
    capabilities = ProviderCapabilities(fixtures=True, results=True, half_time_scores=True, corners=True, xg=True, shots=True, possession=False, cards=True, players=False, injuries=True, odds=True, odds_history=True, corner_odds=True, notes="SYNTHETIC DEMO DATA")

    def __init__(self, seed: int = 42, today: date | None = None, seasons: tuple[int, ...] | None = None):
        self.seed = seed
        self.today = today or datetime.now(UTC).date()
        # The latest demo season is anchored so that "today" falls ~12 rounds in: there is always
        # a live season with history behind it and fixtures ahead of it, whatever the real date.
        current = self.today.year if self.today.month >= 7 else self.today.year - 1
        self.seasons = seasons or (current - 2, current - 1, current)
        latest_start = self.today - timedelta(weeks=12)
        latest_start -= timedelta(days=latest_start.weekday())  # Monday
        self.season_starts = {yr: latest_start - timedelta(weeks=52 * (max(self.seasons) - yr)) for yr in self.seasons}
        self._teams: dict[str, list[dict]] = {}
        self._fixtures: dict[tuple[str, int], list[dict]] = {}
        self._build()

    # ---- world generation --------------------------------------------
    def _build(self) -> None:
        rng = random.Random(self.seed)
        for code, _name, _country, n, hg, ag, hc, ac in DEMO_LEAGUES:
            teams = []
            for i in range(n):
                teams.append(
                    {
                        "id": f"{code}_T{i + 1:02d}",
                        "name": f"Demo {NAMES[i % len(NAMES)]} {code[-1]}{i + 1}",
                        "attack": math.exp(rng.gauss(0, 0.22)),
                        "defence": math.exp(rng.gauss(0, 0.20)),
                        "corner_for": math.exp(rng.gauss(0, 0.16)),
                        "corner_against": math.exp(rng.gauss(0, 0.14)),
                    }
                )
            self._teams[code] = teams
            for season in self.seasons:
                self._fixtures[(code, season)] = self._simulate_season(rng, code, season, teams, hg, ag, hc, ac)

    def _simulate_season(self, rng: random.Random, code: str, season: int, teams: list[dict], hg: float, ag: float, hc: float, ac: float) -> list[dict]:
        n = len(teams)
        start = self.season_starts[season]
        # round-robin schedule (double)
        ids = list(range(n))
        rounds = []
        for r in range(n - 1):
            pairs = [(ids[i], ids[n - 1 - i]) for i in range(n // 2)]
            rounds.append(pairs if r % 2 == 0 else [(b, a) for a, b in pairs])
            ids = [ids[0]] + [ids[-1]] + ids[1:-1]
        rounds += [[(b, a) for a, b in rnd] for rnd in rounds]
        fixtures = []
        fid = 0
        for md, rnd in enumerate(rounds):
            day = start + timedelta(days=7 * md)
            for hi, ai in rnd:
                fid += 1
                home, away = teams[hi], teams[ai]
                kickoff = datetime(day.year, day.month, day.day, 15 if fid % 3 else 20, 0, tzinfo=UTC) + timedelta(days=fid % 2)
                lam_h = hg * home["attack"] * away["defence"] * (1 + 0.08 * (rng.random() - 0.5))
                lam_a = ag * away["attack"] * home["defence"] * (1 + 0.08 * (rng.random() - 0.5))
                ch = hc * home["corner_for"] * away["corner_against"]
                ca = ac * away["corner_for"] * home["corner_against"]
                fx = {
                    "id": f"demo_{code}_{season}_{fid:04d}", "competition": code, "season": season, "matchday": md + 1,
                    "home": home, "away": away, "kickoff": kickoff, "lam_h": lam_h, "lam_a": lam_a, "corn_h": ch, "corn_a": ca,
                }
                if kickoff.date() < self.today:
                    self._play(rng, fx)
                fixtures.append(fx)
        return fixtures

    @staticmethod
    def _nb(rng: random.Random, mean: float, dispersion: float) -> int:
        # gamma-poisson mixture
        shape = dispersion
        scale = mean / dispersion
        lam = rng.gammavariate(shape, scale)
        return int(np.random.default_rng(rng.getrandbits(32)).poisson(lam))

    def _play(self, rng: random.Random, fx: dict) -> None:
        r = np.random.default_rng(rng.getrandbits(32))
        hg = int(r.poisson(fx["lam_h"]))
        ag = int(r.poisson(fx["lam_a"]))
        # crude low-score correlation (Dixon-Coles style): occasionally nudge 1-1 towards 0-0 / 1-0
        if hg == 1 and ag == 1 and rng.random() < 0.06:
            hg, ag = (0, 0) if rng.random() < 0.5 else (1, 0)
        ht_h = int(r.binomial(hg, 0.44)) if hg else 0
        ht_a = int(r.binomial(ag, 0.44)) if ag else 0
        ch = self._nb(rng, fx["corn_h"], 9.0)
        ca = self._nb(rng, fx["corn_a"], 9.0)
        red_minute = rng.randint(5, 85) if rng.random() < 0.05 else None
        fx.update(
            {
                "hg": hg, "ag": ag, "ht_h": ht_h, "ht_a": ht_a, "ch": ch, "ca": ca, "ch_ht": int(r.binomial(ch, 0.46)), "ca_ht": int(r.binomial(ca, 0.46)),
                "xg_h": round(fx["lam_h"] * math.exp(rng.gauss(0, 0.25)), 2), "xg_a": round(fx["lam_a"] * math.exp(rng.gauss(0, 0.25)), 2),
                "shots_h": int(r.poisson(fx["lam_h"] * 9)), "shots_a": int(r.poisson(fx["lam_a"] * 9)),
                "sot_h": int(r.poisson(fx["lam_h"] * 3.2)), "sot_a": int(r.poisson(fx["lam_a"] * 3.2)),
                "yc_h": int(r.poisson(1.9)), "yc_a": int(r.poisson(2.1)), "red_minute": red_minute, "red_side": rng.choice(["h", "a"]) if red_minute else None,
                "played": True,
            }
        )

    # ---- helpers -----------------------------------------------------
    def _fx_dto(self, fx: dict) -> FixtureDTO:
        played = fx.get("played", False)
        return FixtureDTO(
            source=self.name, source_id=fx["id"], competition_code=fx["competition"], season_year=fx["season"],
            home_team_source_id=fx["home"]["id"], away_team_source_id=fx["away"]["id"], home_team_name=fx["home"]["name"], away_team_name=fx["away"]["name"],
            kickoff_utc=fx["kickoff"], status="FINISHED" if played else "SCHEDULED", matchday=fx["matchday"],
            home_goals=fx["hg"] if played else None, away_goals=fx["ag"] if played else None, home_goals_ht=fx["ht_h"] if played else None, away_goals_ht=fx["ht_a"] if played else None,
            last_updated_at=datetime.now(UTC),
        )

    def _all_fixtures(self) -> list[dict]:
        return [fx for fixtures in self._fixtures.values() for fx in fixtures]

    def true_probabilities(self, fx: dict) -> dict[str, float]:
        from app.models_ml.corner_model import CornerModelInput
        from app.models_ml.corner_model import predict as predict_corners
        from app.models_ml.goal_model import predict_from_lambdas

        goals = predict_from_lambdas(fx["lam_h"], fx["lam_a"], rho=-0.05).probabilities
        corners = predict_corners(CornerModelInput(fx["corn_h"], 1.0, fx["corn_a"], 1.0, 1.0, 1.0, observed_variance_ratio=1.9)).probabilities
        return {**goals, **corners}

    # ---- FootballDataProvider ----------------------------------------
    async def get_competitions(self) -> list[CompetitionDTO]:
        return [CompetitionDTO(self.name, code, code, name, country, 1, max(self.seasons)) for code, name, country, *_ in DEMO_LEAGUES]

    async def get_teams(self, competition_code: str, season_year: int) -> list[TeamDTO]:
        return [TeamDTO(self.name, t["id"], t["name"], t["name"].split()[1][:3].upper(), "Demoland", competition_code) for t in self._teams.get(competition_code, [])]

    async def get_fixtures(self, competition_code: str, season_year: int, date_from: date | None = None, date_to: date | None = None) -> list[FixtureDTO]:
        out = []
        for fx in self._fixtures.get((competition_code, season_year), []):
            d = fx["kickoff"].date()
            if date_from and d < date_from:
                continue
            if date_to and d > date_to:
                continue
            out.append(self._fx_dto(fx))
        return out

    async def get_results(self, competition_code: str, season_year: int) -> list[FixtureDTO]:
        return [self._fx_dto(fx) for fx in self._fixtures.get((competition_code, season_year), []) if fx.get("played")]

    async def get_fixture_statistics(self, fixture_source_id: str) -> list[TeamMatchStatsDTO]:
        for fx in self._all_fixtures():
            if fx["id"] == fixture_source_id and fx.get("played"):
                rm = fx["red_minute"]
                return [
                    TeamMatchStatsDTO(self.name, fx["id"], fx["home"]["id"], True, fx["hg"], fx["xg_h"], fx["shots_h"], fx["sot_h"], None, fx["ch"], fx["ch_ht"], fx["yc_h"], 1 if rm and fx["red_side"] == "h" else 0, None, rm if fx["red_side"] == "h" else None),
                    TeamMatchStatsDTO(self.name, fx["id"], fx["away"]["id"], False, fx["ag"], fx["xg_a"], fx["shots_a"], fx["sot_a"], None, fx["ca"], fx["ca_ht"], fx["yc_a"], 1 if rm and fx["red_side"] == "a" else 0, None, rm if fx["red_side"] == "a" else None),
                ]
        return []

    async def get_team_statistics(self, team_source_id: str, competition_code: str, season_year: int) -> dict:
        return {}

    async def get_player_information(self, team_source_id: str, season_year: int) -> list[PlayerDTO]:
        return []

    # ---- InjuryDataProvider ------------------------------------------
    async def get_team_injuries(self, team_source_id: str, competition_code: str, season_year: int) -> list[InjuryDTO]:
        rng = random.Random(f"{self.seed}-{team_source_id}-{self.today}")
        out = []
        for i in range(rng.choice([0, 0, 1, 1, 2, 3])):
            out.append(InjuryDTO(self.name, team_source_id, f"Demo Player {i + 1}", f"{team_source_id}_P{i + 1}", rng.choice(["Hamstring", "Knee", "Illness", "Ankle"]), rng.choice(["out", "out", "doubtful"]), datetime.now(UTC)))
        return out

    async def get_player_status(self, player_source_id: str) -> InjuryDTO | None:
        return None

    # ---- OddsDataProvider --------------------------------------------
    async def get_bookmakers(self) -> list[dict]:
        return [{"key": k, "name": n} for k, n, _ in DEMO_BOOKMAKERS]

    def _odds_for_fixture(self, fx: dict, recorded_at: datetime, drift_seed: int = 0) -> list[OddsDTO]:
        from app.odds.markets import MARKETS, outcome_set_members

        truth = self.true_probabilities(fx)
        rng = random.Random(f"{self.seed}-{fx['id']}-odds-{drift_seed}")
        out: list[OddsDTO] = []
        # the market's own (noisy) view of the fixture, shared by all bookmakers
        market_bias = {m.outcome_set: rng.gauss(0, 0.05) for m in MARKETS}
        priced_sets = set()
        for m in MARKETS:
            if m.outcome_set in priced_sets or m.prob_key not in truth:
                continue
            members = [mm for mm in outcome_set_members(m.outcome_set) if mm.prob_key in truth]
            if m.group == "handicap" or m.group == "team_corners" or m.group == "first_half" and rng.random() < 0.5:
                continue  # demo bookmakers do not price every market: exercise "market unavailable"
            priced_sets.add(m.outcome_set)
            for key, name, margin in DEMO_BOOKMAKERS:
                if rng.random() < 0.15:
                    continue  # this bookmaker does not offer the market
                probs = []
                for mm in members:
                    p = truth[mm.prob_key]
                    noisy = min(max(p * math.exp(market_bias[m.outcome_set] + rng.gauss(0, 0.03)), 0.02), 0.98)
                    probs.append(noisy)
                s = sum(probs)
                for mm, p in zip(members, probs, strict=True):
                    price = round(1.0 / (p / s * margin), 2)
                    if price > 1.01:
                        out.append(OddsDTO(self.name, fx["id"], key, name, mm.key, mm.selection, mm.line, price, recorded_at, fx["home"]["name"], fx["away"]["name"], fx["kickoff"]))
        return out

    async def get_match_odds(self, competition_code: str, date_from: date | None = None, date_to: date | None = None) -> list[OddsDTO]:
        return await self.get_market_odds(competition_code, [], date_from, date_to)

    async def get_market_odds(self, competition_code: str, market_keys: list[str], date_from: date | None = None, date_to: date | None = None) -> list[OddsDTO]:
        now = datetime.now(UTC)
        out: list[OddsDTO] = []
        for (code, _season), fixtures in self._fixtures.items():
            if code != competition_code:
                continue
            for fx in fixtures:
                d = fx["kickoff"].date()
                if date_from and d < date_from or date_to and d > date_to:
                    continue
                out.extend(self._odds_for_fixture(fx, now))
        return out

    async def get_market_history(self, fixture_source_id: str, market_key: str) -> list[OddsDTO]:
        for fx in self._all_fixtures():
            if fx["id"] == fixture_source_id:
                opening = self._odds_for_fixture(fx, fx["kickoff"] - timedelta(days=3), drift_seed=1)
                closing = self._odds_for_fixture(fx, fx["kickoff"] - timedelta(minutes=5), drift_seed=2)
                return [o for o in opening + closing if o.market_key == market_key]
        return []

    def historical_odds(self, fixture_source_id: str) -> tuple[list[OddsDTO], list[OddsDTO]]:
        """(opening, closing) odds for backtests of demo data."""
        for fx in self._all_fixtures():
            if fx["id"] == fixture_source_id:
                return self._odds_for_fixture(fx, fx["kickoff"] - timedelta(days=3), 1), self._odds_for_fixture(fx, fx["kickoff"] - timedelta(minutes=5), 2)
        return [], []
