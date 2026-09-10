import logging

from ..cache import cached
from ..models import BENCH_SLOTS, LeagueDetail, LeagueError, LeagueSummary, NflState, Player, RosterSlot
from ..services.enrich import build_player
from ..services.players import PlayerDB
from ..services.projections import teams_playing
from ..services.recommendations import effective_points
from ..services.scoring import scoring_label
from .base import LEAGUE_TTL, ProviderError

log = logging.getLogger(__name__)

SLOT_MAP = {"W/R/T": "FLEX", "W/R": "WRRB_FLEX", "Q/W/R/T": "SUPER_FLEX", "BN": "BN", "IR": "IR", "IR+": "IR", "IL": "IR",
            "DEF": "DEF", "K": "K", "QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "D": "IDP_FLEX"}
PRIMARY = ["QB", "RB", "WR", "TE", "K", "DEF"]
HINT = "Run the Yahoo OAuth setup (see README): backend/oauth2.json needs consumer_key/consumer_secret, then authorize once."
AUTHORIZE_CMD = ("cd backend && ./.venv/bin/python -c \"from yahoo_oauth import OAuth2; OAuth2(None, None, from_file='oauth2.json')\"")
APPROVAL_HINT = ("Yahoo has not approved this app for the Fantasy Sports API yet (every app now needs manual approval via "
                 "sports.yahoo.com/developer/access). The card will start working on its own once Yahoo approves.")


class YahooProvider:
    platform = "yahoo"

    def __init__(self, oauth_path, league_id: str | None, state: NflState, db: PlayerDB, projections: dict[str, dict], live: dict | None = None):
        self.oauth_path, self.league_pref = oauth_path, league_id
        self.state, self.db, self.projections = state, db, projections
        self.playing = teams_playing(projections)
        self.live = (live or {}).get("stats", {})
        self.board = (live or {}).get("board", {})
        self._lg = None
        self._tm = None

    # ---- raw ---------------------------------------------------------
    def _session(self):
        import json
        if not self.oauth_path.exists():
            raise ProviderError(f"Yahoo oauth file not found: {self.oauth_path}", HINT)
        creds = json.loads(self.oauth_path.read_text() or "{}")
        if not creds.get("consumer_key") or not creds.get("consumer_secret"):
            raise ProviderError("oauth2.json is missing consumer_key / consumer_secret", HINT)
        if not creds.get("refresh_token"):
            # Never start the interactive browser login inside the server.
            raise ProviderError("Yahoo is not authorized yet", f"Run once in a terminal: {AUTHORIZE_CMD}")
        from yahoo_oauth import OAuth2
        sc = OAuth2(None, None, from_file=str(self.oauth_path))
        if not sc.token_is_valid():
            sc.refresh_access_token()
        return sc

    def league(self):
        if self._lg is None:
            import yahoo_fantasy_api as yfa
            try:
                gm = yfa.Game(self._session(), "nfl")
                ids = gm.league_ids(year=self.state.season)
            except ProviderError:
                raise
            except Exception as e:
                if "additional_authorization_required" in str(e) or "401" in str(e):
                    raise ProviderError("Yahoo returned 401: app not yet approved for Fantasy Sports", APPROVAL_HINT) from e
                raise ProviderError(f"Yahoo auth/league lookup failed: {e}", HINT) from e
            if not ids:
                raise ProviderError(f"No Yahoo NFL leagues found for {self.state.season}")
            chosen = ids[0]
            if self.league_pref:
                chosen = next((i for i in ids if i.endswith(f".l.{self.league_pref}") or i == self.league_pref), ids[0])
            self._lg = gm.to_league(chosen)
        return self._lg

    def team(self):
        if self._tm is None:
            lg = self.league()
            self._tm = lg.to_team(lg.team_key())
        return self._tm

    def _settings(self) -> dict:
        return cached(f"yahoo_settings_{self.league().league_id}", 6 * 3600, lambda: self.league().settings())

    def _rec_value(self) -> float | None:
        s = self._settings()
        try:
            cats = s.get("stat_categories", {}).get("stats", [])
            rec_id = next(c["stat"]["stat_id"] for c in cats if c["stat"].get("display_name") == "Rec")
            mods = s.get("stat_modifiers", {}).get("stats", [])
            return float(next(m["stat"]["value"] for m in mods if m["stat"]["stat_id"] == rec_id))
        except (StopIteration, KeyError, TypeError, ValueError, AttributeError):
            return None

    def _details(self, ids: list[int]) -> dict[int, dict]:
        """player_id -> details (team abbr, bye week)."""
        out: dict[int, dict] = {}
        lg = self.league()
        for i in range(0, len(ids), 25):
            chunk = ids[i:i + 25]
            try:
                for d in lg.player_details(chunk):
                    out[int(d["player_id"])] = d
            except Exception as e:  # details are best-effort
                log.warning("yahoo player_details failed: %s", e)
        return out

    # ---- helpers -----------------------------------------------------
    @staticmethod
    def _position(p: dict) -> str:
        elig = p.get("eligible_positions") or []
        for pos in PRIMARY:
            if pos in elig:
                return pos
        return p.get("primary_position") or (elig[0] if elig else "UNK")

    def _player(self, p: dict, details: dict[int, dict], rec_value: float | None) -> Player:
        pid = int(p["player_id"])
        pos = self._position(p)
        d = details.get(pid, {})
        team = d.get("editorial_team_abbr") or p.get("editorial_team_abbr")
        sid = self.db.from_yahoo(pid, p["name"], pos, team)
        status = p.get("status") or None
        if not team and sid and self.db.get(sid):
            team = self.db.get(sid).get("team")
        pl = build_player(
            self.db, sleeper_id=sid, platform_player_id=str(pid), name=p["name"], position=pos,
            nfl_team=team, injury_status=status, projections=self.projections, teams_playing=self.playing,
            rec_value=rec_value, live=self.live, board=self.board,
        )
        try:
            bye = int((d.get("bye_weeks") or {}).get("week", 0))
            if bye == self.state.week:
                pl.on_bye = True
        except (TypeError, ValueError):
            pass
        return pl

    def _roster_slots(self) -> list[RosterSlot]:
        raw = cached(f"yahoo_roster_{self.league().league_id}_{self.state.week}", LEAGUE_TTL,
                     lambda: self.team().roster(self.state.week))
        details = self._details([int(p["player_id"]) for p in raw])
        rec = self._rec_value()
        slots = [RosterSlot(slot=SLOT_MAP.get(p.get("selected_position"), p.get("selected_position") or "BN"),
                            player=self._player(p, details, rec)) for p in raw]
        order = {s: i for i, s in enumerate(self._lineup_slots())}
        slots.sort(key=lambda rs: order.get(rs.slot, 99))
        return slots

    def _lineup_slots(self) -> list[str]:
        out = []
        for rp in self._settings().get("roster_positions", []):
            slot = SLOT_MAP.get(rp.get("position"), rp.get("position"))
            out += [slot] * int(rp.get("count", 1))
        return out

    def _matchup(self) -> tuple[str | None, float | None, float | None, float | None, float | None]:
        """(opponent_name, my_projected, opp_projected, my_actual, opp_actual) from the scoreboard; best-effort."""
        try:
            lg = self.league()
            raw = cached(f"yahoo_matchups_{lg.league_id}_{self.state.week}", LEAGUE_TTL, lambda: lg.matchups(self.state.week))
            my_key = lg.team_key()
            matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]
            for k, m in matchups.items():
                if k == "count":
                    continue
                teams = m["matchup"]["0"]["teams"]
                parsed = []
                for tk, t in teams.items():
                    if tk == "count":
                        continue
                    meta = {}
                    for item in t["team"][0]:
                        if isinstance(item, dict):
                            meta.update(item)
                    proj = t["team"][1].get("team_projected_points", {}).get("total")
                    pts = t["team"][1].get("team_points", {}).get("total")
                    parsed.append((meta.get("team_key"), meta.get("name"), float(proj) if proj else None, float(pts) if pts else None))
                keys = [p[0] for p in parsed]
                if my_key in keys:
                    me = next(p for p in parsed if p[0] == my_key)
                    opp = next((p for p in parsed if p[0] != my_key), (None, None, None, None))
                    return opp[1], me[2], opp[2], me[3], opp[3]
        except Exception as e:
            log.warning("yahoo matchup parse failed: %s", e)
        return None, None, None, None, None

    def _summary(self) -> LeagueSummary:
        lg, s = self.league(), self._settings()
        my_key = lg.team_key()
        standings = cached(f"yahoo_standings_{lg.league_id}", LEAGUE_TTL, lambda: lg.standings())
        mine = next((t for t in standings if t.get("team_key") == my_key), {})
        ot = mine.get("outcome_totals") or {}
        opp_name, my_proj, opp_proj, my_actual, opp_actual = self._matchup()
        slots = self._roster_slots()
        started = [rs.player for rs in slots if rs.slot not in BENCH_SLOTS and rs.player and rs.player.game_state in ("in", "post")]
        if my_proj is None:
            my_proj = round(sum(effective_points(rs.player) for rs in slots if rs.slot not in BENCH_SLOTS), 2)
        if started and my_actual is None:
            my_actual = round(sum(rs.player.actual_points or 0.0 for rs in slots if rs.slot not in BENCH_SLOTS and rs.player), 2)
        if not started:
            my_actual = opp_actual = None
        teams = cached(f"yahoo_teams_{lg.league_id}", LEAGUE_TTL, lambda: lg.teams())
        me_team = teams.get(my_key, {}) if isinstance(teams, dict) else {}
        uses_faab = str(s.get("uses_faab", "0")) == "1"
        faab = me_team.get("faab_balance")
        num = lg.league_id.split(".l.")[-1]
        return LeagueSummary(
            platform="yahoo", league_id=lg.league_id, name=s.get("name", "Yahoo league"),
            season=self.state.season, week=self.state.week,
            team_name=mine.get("name") or me_team.get("name") or "My team",
            record=f"{ot.get('wins', 0)}-{ot.get('losses', 0)}" + (f"-{ot['ties']}" if str(ot.get("ties", "0")) not in ("0", "") else ""),
            rank=int(mine["rank"]) if mine.get("rank") else None, total_teams=int(s.get("num_teams", 0)) or None,
            points_for=float(mine["points_for"]) if mine.get("points_for") else None,
            opponent_name=opp_name, my_projected_total=my_proj, opp_projected_total=opp_proj,
            my_actual_total=my_actual, opp_actual_total=opp_actual, in_progress=any(p.game_state == "in" for p in started),
            waiver_type="FAAB" if uses_faab else "priority",
            faab_remaining=int(faab) if faab not in (None, "") else None,
            waiver_priority=int(me_team["waiver_priority"]) if me_team.get("waiver_priority") else None,
            scoring_label=scoring_label(self._rec_value()) if self._rec_value() is not None else "Half PPR (assumed)",
            url=f"https://football.fantasysports.yahoo.com/f1/{num}",
        )

    # ---- Provider interface -----------------------------------------
    def list_leagues(self) -> list[LeagueSummary | LeagueError]:
        try:
            return [self._summary()]
        except Exception as e:
            return [LeagueError(platform="yahoo", league_id=self.league_pref, error=str(e), hint=getattr(e, "hint", HINT))]

    def detail(self, league_id: str) -> LeagueDetail:
        return LeagueDetail(summary=self._summary(), roster=self._roster_slots(), lineup_slots=self._lineup_slots(), scoring={})

    def free_agents(self, league_id: str) -> list[Player]:
        lg = self.league()
        raw = cached(f"yahoo_fa_{lg.league_id}_{self.state.week}", LEAGUE_TTL,
                     lambda: [p for pos in PRIMARY for p in lg.free_agents(pos)])
        # Yahoo free_agents already returns ownership-sorted lists; we only need the top slice per position.
        rec = self._rec_value()
        out = [self._player(p, {}, rec) for p in raw]
        out = [p for p in out if p.projected_points > 0 or p.sleeper_id]
        out.sort(key=lambda p: p.projected_points, reverse=True)
        return out[:300]
