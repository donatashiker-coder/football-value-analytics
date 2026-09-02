"""Statistics engine.

Loads finished matches into an in-memory MatchHistory and computes team statistics strictly
as of a cutoff timestamp. The same code path serves the daily scan (cutoff = now) and the
backtester (cutoff = historical kickoff), which is what makes leakage prevention structural
rather than a matter of discipline: no record with kickoff >= cutoff is ever visible.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Competition, Fixture, FixtureStatistic, Result
from app.models_ml.elo import EloParams, regress_to_mean
from app.models_ml.elo import update as elo_update
from app.statistics.shrinkage import FormWeights, blend_seasons, shrink, volatility, weighted_form, window_mean

# Documented fallback league averages used only when a competition has no finished matches at all.
DEFAULT_LEAGUE_AVERAGES = {"home_goals": 1.50, "away_goals": 1.20, "home_corners": 5.5, "away_corners": 4.6, "corner_var_ratio": 1.6, "first_half_share": 0.44, "btts": 0.50, "over_2.5": 0.50}


@dataclass
class MatchRecord:
    fixture_id: str
    competition_id: str
    season_year: int
    kickoff: datetime
    team_id: str
    opponent_id: str
    is_home: bool
    goals_for: int
    goals_against: int
    ht_goals_for: int | None
    ht_goals_against: int | None
    xg_for: float | None
    xg_against: float | None
    shots_for: int | None
    shots_against: int | None
    sot_for: int | None
    sot_against: int | None
    corners_for: int | None
    corners_against: int | None
    ht_corners_for: int | None
    ht_corners_against: int | None
    early_red_card: bool = False

    @property
    def points(self) -> int:
        return 3 if self.goals_for > self.goals_against else 1 if self.goals_for == self.goals_against else 0


@dataclass
class LeagueAverages:
    competition_id: str
    season_year: int
    matches: int
    home_goals: float
    away_goals: float
    home_corners: float | None
    away_corners: float | None
    corner_var_ratio: float | None
    first_half_share: float | None
    btts_rate: float
    over_2_5_rate: float
    corner_coverage: float  # share of matches with corner data
    xg_coverage: float
    fallback: bool = False

    @property
    def total_goals(self) -> float:
        return self.home_goals + self.away_goals

    @property
    def total_corners(self) -> float | None:
        return None if self.home_corners is None or self.away_corners is None else self.home_corners + self.away_corners

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class TeamStats:
    team_id: str
    matches: int
    home_matches: int
    away_matches: int
    stats: dict = field(default_factory=dict)  # flat feature dictionary
    warnings: list[str] = field(default_factory=list)


class MatchHistory:
    """All finished matches for a set of competitions, indexed per team and ordered by kickoff."""

    def __init__(self) -> None:
        self.by_team: dict[str, list[MatchRecord]] = defaultdict(list)
        self.by_competition: dict[str, list[tuple[datetime, str, str, int, int, int]]] = defaultdict(list)  # (kickoff, home, away, hg, ag, season)
        self.competition_records: dict[str, list[MatchRecord]] = defaultdict(list)

    @classmethod
    def load(cls, db: Session, competition_ids: list[str] | None = None, before: datetime | None = None) -> MatchHistory:
        hist = cls()
        q = select(Fixture, Result).join(Result, Result.fixture_id == Fixture.id).where(Fixture.status == "FINISHED")
        if competition_ids:
            q = q.where(Fixture.competition_id.in_(competition_ids))
        if before is not None:
            q = q.where(Fixture.kickoff_utc < before)
        q = q.order_by(Fixture.kickoff_utc)
        rows = db.execute(q).all()
        fixture_ids = [f.id for f, _ in rows]
        stats: dict[tuple[str, str], FixtureStatistic] = {}
        if fixture_ids:
            for i in range(0, len(fixture_ids), 900):
                chunk = fixture_ids[i : i + 900]
                for s in db.scalars(select(FixtureStatistic).where(FixtureStatistic.fixture_id.in_(chunk))):
                    stats[(s.fixture_id, s.team_id)] = s
        from app.models import Season

        season_years = {s.id: s.year for s in db.scalars(select(Season))}
        for fx, res in rows:
            hs, as_ = stats.get((fx.id, fx.home_team_id)), stats.get((fx.id, fx.away_team_id))
            early_red = bool((res.abnormal_flags or {}).get("early_red_card"))
            season_year = season_years.get(fx.season_id, fx.kickoff_utc.year)
            kickoff = fx.kickoff_utc if fx.kickoff_utc.tzinfo else fx.kickoff_utc.replace(tzinfo=_UTC)
            common = dict(fixture_id=fx.id, competition_id=fx.competition_id, season_year=season_year, kickoff=kickoff, early_red_card=early_red)
            hc, ac = res.home_corners if res.home_corners is not None else (hs.corners if hs else None), res.away_corners if res.away_corners is not None else (as_.corners if as_ else None)
            home_rec = MatchRecord(
                team_id=fx.home_team_id, opponent_id=fx.away_team_id, is_home=True, goals_for=res.home_goals, goals_against=res.away_goals,
                ht_goals_for=res.home_goals_ht, ht_goals_against=res.away_goals_ht, xg_for=hs.xg if hs else None, xg_against=as_.xg if as_ else None,
                shots_for=hs.shots if hs else None, shots_against=as_.shots if as_ else None, sot_for=hs.shots_on_target if hs else None, sot_against=as_.shots_on_target if as_ else None,
                corners_for=hc, corners_against=ac, ht_corners_for=res.home_corners_ht, ht_corners_against=res.away_corners_ht, **common,
            )
            away_rec = MatchRecord(
                team_id=fx.away_team_id, opponent_id=fx.home_team_id, is_home=False, goals_for=res.away_goals, goals_against=res.home_goals,
                ht_goals_for=res.away_goals_ht, ht_goals_against=res.home_goals_ht, xg_for=as_.xg if as_ else None, xg_against=hs.xg if hs else None,
                shots_for=as_.shots if as_ else None, shots_against=hs.shots if hs else None, sot_for=as_.shots_on_target if as_ else None, sot_against=hs.shots_on_target if hs else None,
                corners_for=ac, corners_against=hc, ht_corners_for=res.away_corners_ht, ht_corners_against=res.home_corners_ht, **common,
            )
            hist.by_team[fx.home_team_id].append(home_rec)
            hist.by_team[fx.away_team_id].append(away_rec)
            hist.by_competition[fx.competition_id].append((kickoff, fx.home_team_id, fx.away_team_id, res.home_goals, res.away_goals, season_year))
            hist.competition_records[fx.competition_id].append(home_rec)
        return hist

    def team_matches(self, team_id: str, before: datetime, competition_id: str | None = None, season_year: int | None = None, exclude_early_red: bool = False) -> list[MatchRecord]:
        out = [m for m in self.by_team.get(team_id, []) if m.kickoff < before]
        if competition_id:
            out = [m for m in out if m.competition_id == competition_id]
        if season_year is not None:
            out = [m for m in out if m.season_year == season_year]
        if exclude_early_red:
            out = [m for m in out if not m.early_red_card]
        return out

    def league_averages(self, competition_id: str, season_year: int, before: datetime, min_matches: int = 30) -> LeagueAverages:
        recs = [m for m in self.competition_records.get(competition_id, []) if m.kickoff < before and m.season_year == season_year]
        if len(recs) < min_matches:
            prev = [m for m in self.competition_records.get(competition_id, []) if m.kickoff < before and m.season_year == season_year - 1]
            # blend: whatever current matches exist plus previous season
            recs = recs + prev
        if not recs:
            d = DEFAULT_LEAGUE_AVERAGES
            return LeagueAverages(competition_id, season_year, 0, d["home_goals"], d["away_goals"], d["home_corners"], d["away_corners"], d["corner_var_ratio"], d["first_half_share"], d["btts"], d["over_2.5"], 0.0, 0.0, fallback=True)
        n = len(recs)
        hg = sum(m.goals_for for m in recs) / n
        ag = sum(m.goals_against for m in recs) / n
        corners = [(m.corners_for, m.corners_against) for m in recs if m.corners_for is not None and m.corners_against is not None]
        hc = ac = var_ratio = None
        if corners:
            hc = sum(c[0] for c in corners) / len(corners)
            ac = sum(c[1] for c in corners) / len(corners)
            totals = [c[0] + c[1] for c in corners]
            mean = sum(totals) / len(totals)
            var = sum((t - mean) ** 2 for t in totals) / max(len(totals) - 1, 1)
            var_ratio = var / mean if mean > 0 else None
        ht = [(m.ht_goals_for or 0) + (m.ht_goals_against or 0) for m in recs if m.ht_goals_for is not None and m.ht_goals_against is not None]
        fh_share = None
        total_goals = sum(m.goals_for + m.goals_against for m in recs)
        if ht and total_goals > 0:
            fh_share = sum(ht) / total_goals
        xg_cov = sum(1 for m in recs if m.xg_for is not None) / n
        return LeagueAverages(
            competition_id, season_year, n, hg, ag, hc, ac, var_ratio, fh_share,
            btts_rate=sum(1 for m in recs if m.goals_for > 0 and m.goals_against > 0) / n,
            over_2_5_rate=sum(1 for m in recs if m.goals_for + m.goals_against > 2.5) / n,
            corner_coverage=len(corners) / n, xg_coverage=xg_cov,
        )

    def elo_ratings(self, competition_id: str, before: datetime, params: EloParams | None = None) -> dict[str, float]:
        """Sequential Elo over all matches before the cutoff, with between-season regression."""
        params = params or EloParams()
        ratings: dict[str, float] = {}
        last_season: dict[str, int] = {}
        for kickoff, home, away, hg, ag, season in self.by_competition.get(competition_id, []):
            if kickoff >= before:
                break
            for t in (home, away):
                ratings.setdefault(t, params.initial)
                if last_season.get(t, season) != season:
                    ratings[t] = regress_to_mean(ratings[t], params)
                last_season[t] = season
            ratings[home], ratings[away] = elo_update(ratings[home], ratings[away], hg, ag, params)
        return ratings


_UTC = __import__("datetime").UTC


def _mean(vals: list[float | None]) -> float | None:
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


def _rate(flags: list[bool]) -> float | None:
    return sum(flags) / len(flags) if flags else None


def compute_team_stats(
    hist: MatchHistory,
    team_id: str,
    competition_id: str,
    season_year: int,
    before: datetime,
    league: LeagueAverages,
    weights: FormWeights | None = None,
    prior_strength: float = 8.0,
    exclude_early_red: bool = False,
) -> TeamStats:
    """Compute the full statistics dictionary for a team as of `before`."""
    weights = weights or FormWeights()
    all_matches = hist.team_matches(team_id, before, exclude_early_red=exclude_early_red)  # any competition, for form
    season_matches = [m for m in all_matches if m.competition_id == competition_id and m.season_year == season_year]
    prev_matches = [m for m in all_matches if m.competition_id == competition_id and m.season_year == season_year - 1]
    home_m = [m for m in season_matches if m.is_home]
    away_m = [m for m in season_matches if not m.is_home]
    s: dict = {}
    w: list[str] = []
    n = len(season_matches)

    def series(ms: list[MatchRecord], attr: str) -> list[float]:
        return [getattr(m, attr) for m in ms if getattr(m, attr) is not None]

    # --- goals -------------------------------------------------------
    gf, ga = series(season_matches, "goals_for"), series(season_matches, "goals_against")
    s["matches"] = n
    s["home_matches"], s["away_matches"] = len(home_m), len(away_m)
    s["goals_for_avg"], s["goals_against_avg"] = _mean(gf), _mean(ga)
    s["goals_for_form"], s["goals_against_form"] = weighted_form(gf, weights), weighted_form(ga, weights)
    for k, nwin in (("last_3", 3), ("last_5", 5), ("last_10", 10), ("last_15", 15)):
        s[f"goals_for_{k}"], s[f"goals_against_{k}"] = window_mean(gf, nwin), window_mean(ga, nwin)
        s[f"points_{k}"] = window_mean([float(m.points) for m in season_matches], nwin)
    s["points_per_game"] = _mean([float(m.points) for m in season_matches])
    s["xg_for_avg"], s["xg_against_avg"] = _mean(series(season_matches, "xg_for")), _mean(series(season_matches, "xg_against"))
    s["xg_for_last_5"], s["xg_against_last_5"] = window_mean(series(season_matches, "xg_for"), 5), window_mean(series(season_matches, "xg_against"), 5)
    s["shots_for_avg"], s["shots_against_avg"] = _mean(series(season_matches, "shots_for")), _mean(series(season_matches, "shots_against"))
    s["sot_for_avg"], s["sot_against_avg"] = _mean(series(season_matches, "sot_for")), _mean(series(season_matches, "sot_against"))
    s["clean_sheet_pct"] = _rate([m.goals_against == 0 for m in season_matches])
    s["failed_to_score_pct"] = _rate([m.goals_for == 0 for m in season_matches])
    s["btts_pct"] = _rate([m.goals_for > 0 and m.goals_against > 0 for m in season_matches])
    s["btts_last_10"] = _rate([m.goals_for > 0 and m.goals_against > 0 for m in season_matches[-10:]])
    for line in (1.5, 2.5, 3.5):
        s[f"over_{line}_pct"] = _rate([m.goals_for + m.goals_against > line for m in season_matches])
        s[f"over_{line}_last_5"] = _rate([m.goals_for + m.goals_against > line for m in season_matches[-5:]])
        s[f"over_{line}_last_10"] = _rate([m.goals_for + m.goals_against > line for m in season_matches[-10:]])
    s["under_2.5_pct"] = None if s["over_2.5_pct"] is None else 1 - s["over_2.5_pct"]
    s["win_pct"] = _rate([m.points == 3 for m in season_matches])
    s["draw_pct"] = _rate([m.points == 1 for m in season_matches])
    s["loss_pct"] = _rate([m.points == 0 for m in season_matches])
    s["home_win_pct"], s["away_win_pct"] = _rate([m.points == 3 for m in home_m]), _rate([m.points == 3 for m in away_m])
    ht_for = [m.ht_goals_for for m in season_matches if m.ht_goals_for is not None]
    s["first_half_goals_for_avg"] = _mean(ht_for)
    s["second_half_goals_for_avg"] = _mean([m.goals_for - m.ht_goals_for for m in season_matches if m.ht_goals_for is not None])
    s["first_half_goals_against_avg"] = _mean([m.ht_goals_against for m in season_matches if m.ht_goals_against is not None])
    # venue splits
    for label, ms in (("home", home_m), ("away", away_m)):
        s[f"{label}_goals_for_avg"], s[f"{label}_goals_against_avg"] = _mean(series(ms, "goals_for")), _mean(series(ms, "goals_against"))
        s[f"{label}_goals_for_last_5"], s[f"{label}_goals_against_last_5"] = window_mean(series(ms, "goals_for"), 5), window_mean(series(ms, "goals_against"), 5)
        s[f"{label}_corners_for_avg"], s[f"{label}_corners_against_avg"] = _mean(series(ms, "corners_for")), _mean(series(ms, "corners_against"))
        s[f"{label}_xg_for_avg"], s[f"{label}_xg_against_avg"] = _mean(series(ms, "xg_for")), _mean(series(ms, "xg_against"))
        s[f"{label}_btts_pct"] = _rate([m.goals_for > 0 and m.goals_against > 0 for m in ms])
        s[f"{label}_over_2.5_pct"] = _rate([m.goals_for + m.goals_against > 2.5 for m in ms])
    # --- corners -----------------------------------------------------
    cf, ca = series(season_matches, "corners_for"), series(season_matches, "corners_against")
    s["corners_for_avg"], s["corners_against_avg"] = _mean(cf), _mean(ca)
    s["corners_for_form"], s["corners_against_form"] = weighted_form(cf, weights), weighted_form(ca, weights)
    s["corners_for_last_5"], s["corners_against_last_5"] = window_mean(cf, 5), window_mean(ca, 5)
    s["corners_for_last_10"], s["corners_against_last_10"] = window_mean(cf, 10), window_mean(ca, 10)
    s["corners_total_avg"] = _mean([m.corners_for + m.corners_against for m in season_matches if m.corners_for is not None and m.corners_against is not None])
    s["corners_matches"] = len(cf)
    s["corner_variance"] = (sum((c - s["corners_for_avg"]) ** 2 for c in cf) / (len(cf) - 1)) if len(cf) > 2 else None
    s["first_half_corners_for_avg"] = _mean(series(season_matches, "ht_corners_for"))
    s["corners_over_9.5_pct"] = _rate([m.corners_for + m.corners_against > 9.5 for m in season_matches if m.corners_for is not None and m.corners_against is not None])
    s["corners_over_10.5_pct"] = _rate([m.corners_for + m.corners_against > 10.5 for m in season_matches if m.corners_for is not None and m.corners_against is not None])
    # --- schedule ----------------------------------------------------
    if all_matches:
        last = all_matches[-1].kickoff
        s["days_since_last_match"] = (before - last).total_seconds() / 86400
        s["matches_last_14_days"] = sum(1 for m in all_matches if (before - m.kickoff).total_seconds() <= 14 * 86400)
    else:
        s["days_since_last_match"], s["matches_last_14_days"] = None, 0
    s["volatility"] = volatility([float(m.goals_for + m.goals_against) for m in season_matches])
    s["early_red_card_matches"] = sum(1 for m in season_matches if m.early_red_card)

    # --- strengths (opponent-adjusted, season-blended, shrunk) ---------
    # Opponent adjustment: scale each match by the opponent's raw defence/attack ratio (single pass).
    def opp_strength(opp_id: str, attr: str, league_avg: float) -> float:
        opp = [m for m in hist.team_matches(opp_id, before) if m.competition_id == competition_id and m.season_year == season_year]
        vals = series(opp, attr)
        if len(vals) < 3 or league_avg <= 0:
            return 1.0
        return max(min(shrink(_mean(vals), len(vals), league_avg, prior_strength) / league_avg, 1.8), 0.5)

    lg_goals = (league.home_goals + league.away_goals) / 2
    lg_corners = ((league.home_corners or 0) + (league.away_corners or 0)) / 2 or None

    def adjusted_rate(ms: list[MatchRecord], attr: str, opp_attr: str, league_avg: float | None) -> float | None:
        if not league_avg:
            return None
        vals = []
        for m in ms:
            v = getattr(m, attr)
            if v is None:
                continue
            vals.append(v / opp_strength(m.opponent_id, opp_attr, league_avg))
        return _mean(vals)

    def strength(ms_cur: list[MatchRecord], ms_prev: list[MatchRecord], attr: str, opp_attr: str, venue_avg: float | None, league_avg: float | None) -> tuple[float, dict]:
        """Multiplier vs league venue average, blended across seasons and shrunk to 1.0."""
        if not venue_avg or not league_avg:
            return 1.0, {"unavailable": True}
        cur = adjusted_rate(ms_cur, attr, opp_attr, league_avg)
        prev = adjusted_rate(ms_prev, attr, opp_attr, league_avg)
        n_cur = len([m for m in ms_cur if getattr(m, attr) is not None])
        blended, info = blend_seasons(cur, n_cur, prev, venue_avg)
        n_eff = n_cur + (len(ms_prev) * 0.5 if prev is not None else 0)
        shrunk = shrink(blended, int(n_eff), venue_avg, prior_strength)
        return max(min(shrunk / venue_avg, 2.5), 0.3), {**info, "raw": cur, "shrunk": shrunk, "n": n_cur}

    prev_home = [m for m in prev_matches if m.is_home]
    prev_away = [m for m in prev_matches if not m.is_home]
    # goals: home attack scaled by league home avg, defence by what opponents (away teams) score
    s["home_attack"], s["home_attack_info"] = strength(home_m, prev_home, "goals_for", "goals_against", league.home_goals, lg_goals)
    s["home_defence"], s["home_defence_info"] = strength(home_m, prev_home, "goals_against", "goals_for", league.away_goals, lg_goals)
    s["away_attack"], s["away_attack_info"] = strength(away_m, prev_away, "goals_for", "goals_against", league.away_goals, lg_goals)
    s["away_defence"], s["away_defence_info"] = strength(away_m, prev_away, "goals_against", "goals_for", league.home_goals, lg_goals)
    # overall (venue-agnostic) versions, used when venue samples are thin
    s["attack_overall"], _ = strength(season_matches, prev_matches, "goals_for", "goals_against", lg_goals, lg_goals)
    s["defence_overall"], _ = strength(season_matches, prev_matches, "goals_against", "goals_for", lg_goals, lg_goals)
    # corners
    s["home_corners_for_strength"], _ = strength(home_m, prev_home, "corners_for", "corners_against", league.home_corners, lg_corners)
    s["home_corners_against_strength"], _ = strength(home_m, prev_home, "corners_against", "corners_for", league.away_corners, lg_corners)
    s["away_corners_for_strength"], _ = strength(away_m, prev_away, "corners_for", "corners_against", league.away_corners, lg_corners)
    s["away_corners_against_strength"], _ = strength(away_m, prev_away, "corners_against", "corners_for", league.home_corners, lg_corners)
    s["corners_for_strength_overall"], _ = strength(season_matches, prev_matches, "corners_for", "corners_against", lg_corners, lg_corners)
    s["corners_against_strength_overall"], _ = strength(season_matches, prev_matches, "corners_against", "corners_for", lg_corners, lg_corners)
    # xG-based attack/defence multipliers where available (informational; blended in features)
    s["xg_attack"] = (shrink(s["xg_for_avg"], len(series(season_matches, "xg_for")), lg_goals, prior_strength) / lg_goals) if s["xg_for_avg"] is not None and lg_goals else None
    s["xg_defence"] = (shrink(s["xg_against_avg"], len(series(season_matches, "xg_against")), lg_goals, prior_strength) / lg_goals) if s["xg_against_avg"] is not None and lg_goals else None

    if n < 6:
        w.append(f"Only {n} matches this season; estimates shrunk towards league average")
    if len(prev_matches) == 0 and n < 12:
        w.append("No previous-season data in this competition (new/promoted team)")
    if not cf:
        w.append("No corner data available for this team")
    if s["xg_for_avg"] is None:
        w.append("xG unavailable")
    s["previous_season_matches"] = len(prev_matches)
    return TeamStats(team_id, n, len(home_m), len(away_m), s, w)


def competition_ids_for(db: Session, codes: list[str] | None = None) -> list[str]:
    q = select(Competition.id).where(Competition.enabled.is_(True))
    if codes:
        q = q.where(Competition.code.in_(codes))
    return [r[0] for r in db.execute(q).all()]
