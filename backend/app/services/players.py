"""Master player table from Sleeper, with reverse maps to ESPN / Yahoo ids."""
import re

import httpx

from ..cache import cached

FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}

# Normalize team abbreviations from every platform to Sleeper's vocabulary.
TEAM_ALIASES = {"WSH": "WAS", "JAC": "JAX", "OAK": "LV", "SD": "LAC", "STL": "LAR", "LA": "LAR"}


def norm_team(abbr: str | None) -> str | None:
    if not abbr:
        return None
    a = abbr.upper().strip()
    return TEAM_ALIASES.get(a, a)


def norm_name(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", n)
    n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()


def _fetch_players() -> dict:
    r = httpx.get("https://api.sleeper.app/v1/players/nfl", timeout=60)
    r.raise_for_status()
    raw = r.json()
    # Keep only fields we use; the full payload is ~14 MB.
    keep = ("full_name", "first_name", "last_name", "position", "fantasy_positions", "team",
            "injury_status", "status", "espn_id", "yahoo_id", "active")
    return {pid: {k: p.get(k) for k in keep} for pid, p in raw.items()}


class PlayerDB:
    def __init__(self) -> None:
        self.by_id: dict[str, dict] = {}
        self.espn_to_sleeper: dict[int, str] = {}
        self.yahoo_to_sleeper: dict[int, str] = {}
        self.name_to_sleeper: dict[tuple[str, str], str] = {}
        self.load()

    def load(self) -> None:
        self.by_id = cached("sleeper_players", 24 * 3600, _fetch_players)
        self.espn_to_sleeper.clear()
        self.yahoo_to_sleeper.clear()
        self.name_to_sleeper.clear()
        for pid, p in self.by_id.items():
            if p.get("espn_id"):
                self.espn_to_sleeper[int(p["espn_id"])] = pid
            if p.get("yahoo_id"):
                self.yahoo_to_sleeper[int(p["yahoo_id"])] = pid
            name = p.get("full_name") or " ".join(filter(None, [p.get("first_name"), p.get("last_name")]))
            if name and p.get("position"):
                self.name_to_sleeper[(norm_name(name), p["position"])] = pid

    def get(self, sleeper_id: str | None) -> dict | None:
        return self.by_id.get(str(sleeper_id)) if sleeper_id else None

    def name(self, sleeper_id: str) -> str:
        p = self.get(sleeper_id)
        if not p:
            return f"Player {sleeper_id}"
        return p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or sleeper_id

    def from_espn(self, espn_id: int | None, name: str, position: str, pro_team: str | None = None) -> str | None:
        if position in ("DEF", "D/ST"):
            return norm_team(pro_team)
        if espn_id is not None and int(espn_id) in self.espn_to_sleeper:
            return self.espn_to_sleeper[int(espn_id)]
        return self.name_to_sleeper.get((norm_name(name), position))

    def from_yahoo(self, yahoo_id: int | None, name: str, position: str, pro_team: str | None = None) -> str | None:
        if position == "DEF":
            return norm_team(pro_team)
        if yahoo_id is not None and int(yahoo_id) in self.yahoo_to_sleeper:
            return self.yahoo_to_sleeper[int(yahoo_id)]
        return self.name_to_sleeper.get((norm_name(name), position))

    def fantasy_relevant_ids(self) -> list[str]:
        out = []
        for pid, p in self.by_id.items():
            if p.get("position") in FANTASY_POSITIONS and (p.get("team") or p.get("position") == "DEF"):
                if p.get("status") in (None, "Active") or p.get("position") == "DEF":
                    out.append(pid)
        return out


_db: PlayerDB | None = None


def player_db() -> PlayerDB:
    global _db
    if _db is None:
        _db = PlayerDB()
    return _db


def reset_player_db() -> None:
    global _db
    _db = None
