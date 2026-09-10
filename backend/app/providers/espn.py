from ..cache import cached
from ..models import BENCH_SLOTS, LeagueDetail, LeagueError, LeagueSummary, NflState, Player, RosterSlot
from ..services.enrich import build_player
from ..services.players import PlayerDB, norm_team
from ..services.projections import teams_playing
from ..services.recommendations import effective_points
from ..services.scoring import scoring_label
from .base import LEAGUE_TTL, ProviderError

SLOT_MAP = {
    "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "K": "K", "D/ST": "DEF",
    "RB/WR/TE": "FLEX", "RB/WR": "WRRB_FLEX", "WR/TE": "REC_FLEX", "OP": "SUPER_FLEX",
    "BE": "BN", "IR": "IR", "DP": "IDP_FLEX", "DL": "DL", "LB": "LB", "DB": "DB",
}
POS_MAP = {"D/ST": "DEF"}
HINT = "Refresh ESPN_S2 / ESPN_SWID in backend/.env (fantasy.espn.com -> DevTools -> Application -> Cookies)."


class EspnProvider:
    platform = "espn"

    def __init__(self, league_id: int, s2: str, swid: str, team_id: int | None, state: NflState,
                 db: PlayerDB, projections: dict[str, dict], live: dict | None = None):
        self.league_id, self.s2, self.swid, self.team_id = league_id, s2, swid, team_id
        self.state, self.db, self.projections = state, db, projections
        self.playing = teams_playing(projections)
        self.live = (live or {}).get("stats", {})
        self.board = (live or {}).get("board", {})
        self._league = None

    # ---- raw ---------------------------------------------------------
    def league(self):
        if self._league is None:
            from espn_api.football import League
            try:
                self._league = League(league_id=self.league_id, year=self.state.season, espn_s2=self.s2, swid=self.swid)
            except Exception as e:
                raise ProviderError(f"ESPN login failed: {e}", HINT) from e
        return self._league

    def _week(self) -> int:
        lg = self.league()
        return int(getattr(lg, "current_week", None) or self.state.week)

    def my_team(self):
        lg = self.league()
        if self.team_id:
            t = next((t for t in lg.teams if t.team_id == self.team_id), None)
            if t:
                return t
        swid = (self.swid or "").strip("{}").lower()
        for t in lg.teams:
            for o in getattr(t, "owners", []) or []:
                oid = o.get("id") if isinstance(o, dict) else str(o)
                if oid and oid.strip("{}").lower() == swid:
                    return t
        raise ProviderError("Could not find your ESPN team", "Set ESPN_TEAM_ID in backend/.env (teamId= in the ESPN URL)")

    def _box(self):
        """(my_box_lineup, my_projected, opp_team, opp_projected, my_score, opp_score, opp_box_lineup)"""
        lg, me, week = self.league(), self.my_team(), self._week()
        for bs in lg.box_scores(week):
            if getattr(bs.home_team, "team_id", None) == me.team_id:
                return bs.home_lineup, bs.home_projected, bs.away_team, bs.away_projected, bs.home_score, bs.away_score, bs.away_lineup
            if getattr(bs.away_team, "team_id", None) == me.team_id:
                return bs.away_lineup, bs.away_projected, bs.home_team, bs.home_projected, bs.away_score, bs.home_score, bs.home_lineup
        return me.roster, None, None, None, None, None, []

    def _lineup_states(self, lineup) -> list[str | None]:
        """game_state of each *starter* in a box lineup, straight off the scoreboard."""
        out = []
        for bp in lineup or []:
            raw = getattr(bp, "slot_position", None) or getattr(bp, "lineupSlot", "BE")
            if SLOT_MAP.get(raw, raw) in BENCH_SLOTS:
                continue
            team = norm_team(getattr(bp, "proTeam", None))
            out.append((self.board.get(team) or {}).get("state") if team else None)
        return out

    def _rec_value(self) -> float | None:
        for s in getattr(self.league().settings, "scoring_format", []) or []:
            if s.get("abbr") == "REC":
                return float(s.get("points", 0))
        return None

    # ---- helpers -----------------------------------------------------
    def _player(self, bp) -> Player:
        pos = POS_MAP.get(bp.position, bp.position)
        team = getattr(bp, "proTeam", None)
        sid = self.db.from_espn(getattr(bp, "playerId", None), bp.name, pos, team)
        status = getattr(bp, "injuryStatus", None)
        if isinstance(status, str) and status.upper() in ("ACTIVE", "NORMAL"):
            status = None
        p = build_player(
            self.db, sleeper_id=sid, platform_player_id=str(bp.playerId), name=bp.name, position=pos,
            nfl_team=team, injury_status=status, projections=self.projections, teams_playing=self.playing,
            platform_points=getattr(bp, "projected_points", 0.0) or 0.0,
            live=self.live, board=self.board, platform_actual=getattr(bp, "points", None),
        )
        if getattr(bp, "on_bye_week", False):
            p.on_bye = True
        return p

    def _roster_slots(self, lineup=None) -> list[RosterSlot]:
        if lineup is None:
            lineup, *_ = self._box()
        slots = []
        for bp in lineup:
            raw = getattr(bp, "slot_position", None) or getattr(bp, "lineupSlot", "BE")
            slots.append(RosterSlot(slot=SLOT_MAP.get(raw, raw), player=self._player(bp)))
        order = {s: i for i, s in enumerate(self._lineup_slots())}
        slots.sort(key=lambda rs: order.get(rs.slot, 99))
        return slots

    def _lineup_slots(self) -> list[str]:
        counts = getattr(self.league().settings, "position_slot_counts", {}) or {}
        out = []
        for raw, n in counts.items():
            out += [SLOT_MAP.get(raw, raw)] * int(n)
        pref = ["QB", "RB", "WR", "TE", "FLEX", "WRRB_FLEX", "REC_FLEX", "SUPER_FLEX", "K", "DEF", "DL", "LB", "DB", "IDP_FLEX", "BN", "IR"]
        return sorted(out, key=lambda s: pref.index(s) if s in pref else 50)

    def _summary(self) -> LeagueSummary:
        lg, me = self.league(), self.my_team()
        lineup, my_proj, opp, opp_proj, my_score, opp_score, opp_lineup = self._box()
        st = lg.settings
        slots = self._roster_slots()
        started = [rs.player for rs in slots if rs.slot not in BENCH_SLOTS and rs.player and rs.player.game_state in ("in", "post")]
        opp_states = self._lineup_states(opp_lineup)
        # Either side kicking off makes the matchup live; the other side then shows 0.0, not "–".
        any_started = bool(started) or any(s in ("in", "post") for s in opp_states)
        in_progress = any(p.game_state == "in" for p in started) or "in" in opp_states
        faab = None
        if getattr(st, "faab", False):
            faab = int(getattr(st, "acquisition_budget", 0) or 0) - int(getattr(me, "acquisition_budget_spent", 0) or 0)
        if my_proj is None:
            my_proj = round(sum(effective_points(rs.player) for rs in slots if rs.slot not in BENCH_SLOTS), 2)
        return LeagueSummary(
            platform="espn", league_id=str(self.league_id), name=getattr(st, "name", f"ESPN {self.league_id}"),
            season=self.state.season, week=self._week(),
            team_name=me.team_name,
            record=f"{me.wins}-{me.losses}" + (f"-{me.ties}" if getattr(me, 'ties', 0) else ""),
            rank=getattr(me, "standing", None), total_teams=len(lg.teams), points_for=round(float(me.points_for), 2),
            opponent_name=getattr(opp, "team_name", None) if opp else None,
            my_projected_total=round(float(my_proj), 2) if my_proj is not None else None,
            opp_projected_total=round(float(opp_proj), 2) if opp_proj is not None else None,
            my_actual_total=round(float(my_score or 0.0), 2) if any_started else None,
            opp_actual_total=round(float(opp_score or 0.0), 2) if any_started and opp is not None else None,
            in_progress=in_progress,
            waiver_type="FAAB" if faab is not None else "priority", faab_remaining=faab,
            waiver_priority=getattr(me, "waiver_rank", None),
            scoring_label=scoring_label(self._rec_value()),
            url=f"https://fantasy.espn.com/football/team?leagueId={self.league_id}&teamId={me.team_id}",
        )

    # ---- Provider interface -----------------------------------------
    def list_leagues(self) -> list[LeagueSummary | LeagueError]:
        try:
            return [cached_model("espn_summary", self._summary, LeagueSummary, ttl=60)]
        except Exception as e:
            return [LeagueError(platform="espn", league_id=str(self.league_id), error=str(e), hint=getattr(e, "hint", HINT))]

    def detail(self, league_id: str) -> LeagueDetail:
        lineup, _p, opp, _op, _ms, _os, opp_lineup = self._box()
        return LeagueDetail(
            summary=self._summary(), roster=self._roster_slots(lineup), lineup_slots=self._lineup_slots(), scoring={},
            opponent_roster=self._roster_slots(opp_lineup) if opp is not None and opp_lineup else None,
        )

    def free_agents(self, league_id: str) -> list[Player]:
        lg, week = self.league(), self._week()
        out = [self._player(bp) for bp in lg.free_agents(week=week, size=200)]
        out.sort(key=lambda p: p.projected_points, reverse=True)
        return out


def cached_model(key, fn, model, ttl=LEAGUE_TTL):
    data = cached(key, ttl, lambda: fn().model_dump())
    return model.model_validate(data)
