import httpx

from ..cache import cached
from ..models import BENCH_SLOTS, LeagueDetail, LeagueError, LeagueSummary, NflState, Player, RosterSlot
from ..services.enrich import build_player
from ..services.players import PlayerDB
from ..services.projections import teams_playing
from ..services.scoring import scoring_label
from .base import LEAGUE_TTL, ProviderError

API = "https://api.sleeper.app/v1"


def _get(path: str, ttl: int = LEAGUE_TTL):
    def fetch():
        r = httpx.get(f"{API}{path}", timeout=30)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    return cached(f"sleeper_{path}", ttl, fetch)


class SleeperProvider:
    platform = "sleeper"

    def __init__(self, username: str, state: NflState, db: PlayerDB, projections: dict[str, dict]):
        self.username = username
        self.state = state
        self.db = db
        self.projections = projections
        self.playing = teams_playing(projections)

    # ---- raw fetches -------------------------------------------------
    def _user_id(self) -> str:
        user = _get(f"/user/{self.username}", ttl=24 * 3600)
        if not user:
            raise ProviderError(f"Sleeper user '{self.username}' not found", "Check SLEEPER_USERNAME in backend/.env")
        return user["user_id"]

    def _leagues(self) -> list[dict]:
        leagues = _get(f"/user/{self._user_id()}/leagues/nfl/{self.state.season}") or []
        # Pre-draft leagues have empty rosters and nothing to recommend.
        return [lg for lg in leagues if lg.get("status") not in ("pre_draft", "drafting")]

    def _bundle(self, league_id: str) -> dict:
        league = _get(f"/league/{league_id}")
        if not league:
            raise ProviderError(f"Sleeper league {league_id} not found")
        return {
            "league": league,
            "rosters": _get(f"/league/{league_id}/rosters") or [],
            "users": {u["user_id"]: u for u in (_get(f"/league/{league_id}/users") or [])},
            "matchups": _get(f"/league/{league_id}/matchups/{self.state.week}") or [],
        }

    # ---- helpers -----------------------------------------------------
    def _player(self, pid: str, scoring: dict) -> Player:
        p = self.db.get(pid) or {}
        return build_player(
            self.db, sleeper_id=pid, platform_player_id=pid, name=self.db.name(pid),
            position=p.get("position") or "UNK", nfl_team=p.get("team") or (pid if p.get("position") == "DEF" else None),
            injury_status=p.get("injury_status"), projections=self.projections, teams_playing=self.playing,
            scoring=scoring,
        )

    @staticmethod
    def _team_name(users: dict, roster: dict) -> str:
        u = users.get(roster.get("owner_id") or "", {})
        return (u.get("metadata") or {}).get("team_name") or u.get("display_name") or f"Roster {roster.get('roster_id')}"

    def _my_roster(self, b: dict) -> dict:
        uid = self._user_id()
        for r in b["rosters"]:
            if r.get("owner_id") == uid or uid in (r.get("co_owners") or []):
                return r
        raise ProviderError(f"You don't have a roster in Sleeper league {b['league']['name']}")

    def _roster_slots(self, league: dict, roster: dict, scoring: dict) -> list[RosterSlot]:
        positions = league.get("roster_positions") or []
        start_slots = [s for s in positions if s not in BENCH_SLOTS]
        starters = roster.get("starters") or []
        slots: list[RosterSlot] = []
        for i, slot in enumerate(start_slots):
            pid = starters[i] if i < len(starters) else None
            slots.append(RosterSlot(slot=slot, player=self._player(pid, scoring) if pid and pid != "0" else None))
        used = {s for s in starters if s and s != "0"}
        for pid in roster.get("reserve") or []:
            slots.append(RosterSlot(slot="IR", player=self._player(pid, scoring)))
            used.add(pid)
        for pid in roster.get("taxi") or []:
            slots.append(RosterSlot(slot="TAXI", player=self._player(pid, scoring)))
            used.add(pid)
        for pid in roster.get("players") or []:
            if pid not in used:
                slots.append(RosterSlot(slot="BN", player=self._player(pid, scoring)))
        return slots

    def _starter_total(self, league: dict, roster: dict, scoring: dict) -> float:
        from ..services.recommendations import effective_points
        return round(sum(effective_points(rs.player) for rs in self._roster_slots(league, roster, scoring)
                         if rs.slot not in BENCH_SLOTS), 2)

    def _summary(self, b: dict) -> LeagueSummary:
        league, rosters, users = b["league"], b["rosters"], b["users"]
        scoring = league.get("scoring_settings") or {}
        me = self._my_roster(b)
        st = me.get("settings") or {}
        fpts = float(st.get("fpts", 0)) + float(st.get("fpts_decimal", 0)) / 100

        def key(r):
            s = r.get("settings") or {}
            return (s.get("wins", 0), float(s.get("fpts", 0)) + float(s.get("fpts_decimal", 0)) / 100)

        ranked = sorted(rosters, key=key, reverse=True)
        rank = next((i + 1 for i, r in enumerate(ranked) if r["roster_id"] == me["roster_id"]), None)

        opp_name = opp_total = None
        mine = next((m for m in b["matchups"] if m.get("roster_id") == me["roster_id"]), None)
        if mine and mine.get("matchup_id") is not None:
            opp = next((m for m in b["matchups"] if m.get("matchup_id") == mine["matchup_id"] and m["roster_id"] != me["roster_id"]), None)
            if opp:
                opp_roster = next((r for r in rosters if r["roster_id"] == opp["roster_id"]), None)
                if opp_roster:
                    opp_name = self._team_name(users, opp_roster)
                    opp_total = self._starter_total(league, opp_roster, scoring)

        ls = league.get("settings") or {}
        wtype = {0: "priority", 1: "priority", 2: "FAAB"}.get(ls.get("waiver_type"), None)
        faab = None
        if wtype == "FAAB":
            faab = int(ls.get("waiver_budget", 0)) - int(st.get("waiver_budget_used", 0))
        return LeagueSummary(
            platform="sleeper", league_id=league["league_id"], name=league["name"],
            season=self.state.season, week=self.state.week,
            team_name=self._team_name(users, me),
            record=f"{st.get('wins', 0)}-{st.get('losses', 0)}" + (f"-{st['ties']}" if st.get("ties") else ""),
            rank=rank, total_teams=len(rosters), points_for=round(fpts, 2),
            opponent_name=opp_name,
            my_projected_total=self._starter_total(league, me, scoring), opp_projected_total=opp_total,
            waiver_type=wtype, faab_remaining=faab, waiver_priority=st.get("waiver_position"),
            scoring_label=scoring_label(scoring.get("rec")),
            url=f"https://sleeper.com/leagues/{league['league_id']}",
        )

    # ---- Provider interface -----------------------------------------
    def list_leagues(self) -> list[LeagueSummary | LeagueError]:
        out: list[LeagueSummary | LeagueError] = []
        for lg in self._leagues():
            try:
                out.append(self._summary(self._bundle(lg["league_id"])))
            except Exception as e:  # one bad league must not hide the others
                out.append(LeagueError(platform="sleeper", league_id=lg.get("league_id"), name=lg.get("name"),
                                       error=str(e), hint=getattr(e, "hint", None)))
        return out

    def detail(self, league_id: str) -> LeagueDetail:
        b = self._bundle(league_id)
        scoring = b["league"].get("scoring_settings") or {}
        me = self._my_roster(b)
        return LeagueDetail(
            summary=self._summary(b),
            roster=self._roster_slots(b["league"], me, scoring),
            lineup_slots=b["league"].get("roster_positions") or [],
            scoring=scoring,
        )

    def free_agents(self, league_id: str) -> list[Player]:
        b = self._bundle(league_id)
        scoring = b["league"].get("scoring_settings") or {}
        rostered = {pid for r in b["rosters"] for pid in (r.get("players") or [])}
        out = []
        for pid in self.db.fantasy_relevant_ids():
            if pid in rostered or pid not in self.projections:
                continue
            out.append(self._player(pid, scoring))
        out.sort(key=lambda p: p.projected_points, reverse=True)
        return out[:300]
