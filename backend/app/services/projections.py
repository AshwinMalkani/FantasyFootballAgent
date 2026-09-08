"""Weekly projections and NFL state from Sleeper."""
import httpx

from ..cache import cached
from ..models import NflState

POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"]


def nfl_state() -> NflState:
    def fetch() -> dict:
        r = httpx.get("https://api.sleeper.app/v1/state/nfl", timeout=15)
        r.raise_for_status()
        return r.json()

    raw = cached("nfl_state", 30 * 60, fetch)
    week = int(raw.get("week") or raw.get("display_week") or 1)
    return NflState(season=int(raw["season"]), week=max(week, 1), season_type=raw.get("season_type", "regular"))


def weekly_projections(season: int, week: int) -> dict[str, dict]:
    """sleeper_id -> {"stats": {...}, "opponent": str|None, "team": str|None}"""

    def fetch() -> dict:
        params = [("season_type", "regular"), ("order_by", "pts_ppr")] + [("position[]", p) for p in POSITIONS]
        r = httpx.get(f"https://api.sleeper.com/projections/nfl/{season}/{week}", params=params, timeout=60)
        r.raise_for_status()
        out: dict[str, dict] = {}
        for row in r.json():
            pid = str(row.get("player_id"))
            stats = row.get("stats") or {}
            if not stats:
                continue
            out[pid] = {"stats": stats, "opponent": row.get("opponent"), "team": row.get("team")}
        return out

    return cached(f"projections_{season}_{week}", 6 * 3600, fetch)


def teams_playing(projections: dict[str, dict]) -> set[str]:
    return {p["team"] for p in projections.values() if p.get("team")}


def trending_adds(limit: int = 100) -> dict[str, int]:
    def fetch() -> dict:
        r = httpx.get("https://api.sleeper.app/v1/players/nfl/trending/add",
                      params={"lookback_hours": 24, "limit": limit}, timeout=15)
        r.raise_for_status()
        return {str(x["player_id"]): int(x["count"]) for x in r.json()}

    return cached("trending_adds", 60 * 60, fetch)
