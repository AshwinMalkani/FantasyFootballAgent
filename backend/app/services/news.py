"""Player news from ESPN's fantasy news feed (Rotowire blurbs + ESPN stories), per player."""
import re
from concurrent.futures import ThreadPoolExecutor

import httpx

from ..cache import cached
from ..models import BENCH_SLOTS, LeagueError
from ..providers.registry import all_leagues, build_providers
from .players import player_db

FEED = "https://site.api.espn.com/apis/fantasy/v2/games/ffl/news/players"
_TAGS = re.compile(r"<[^>]+>")


def _clean(s: str | None) -> str:
    return _TAGS.sub("", s or "").replace("&nbsp;", " ").strip()


def player_feed(espn_id: int, days: int = 10, limit: int = 8) -> list[dict]:
    def fetch() -> list:
        r = httpx.get(FEED, params={"playerId": espn_id, "days": days, "limit": limit}, timeout=20)
        r.raise_for_status()
        out = []
        for x in r.json().get("feed", []):
            link = ((x.get("links") or {}).get("web") or {}).get("href")
            out.append({
                "id": str(x.get("id")),
                "type": x.get("type") or "Story",
                "headline": _clean(x.get("headline")),
                "description": _clean(x.get("description")),
                "story": _clean(x.get("story"))[:1200] if x.get("type") == "Rotowire" else "",
                "published": x.get("published"),
                "link": link,
                "premium": bool(x.get("premium")),
            })
        return out

    return cached(f"news_{espn_id}_{days}", 15 * 60, fetch)


def build_news(days: int = 10, include_bench: bool = True) -> dict:
    db = player_db()
    providers = build_providers()
    summaries = [s for s in all_leagues() if not isinstance(s, LeagueError)]

    def load(s):
        try:
            return s, providers[s.platform].detail(s.league_id)
        except Exception:
            return s, None

    with ThreadPoolExecutor(max_workers=5) as ex:
        details = list(ex.map(load, summaries))

    players: dict[str, dict] = {}   # keyed by espn_id
    unmapped: list[str] = []
    for s, d in details:
        if d is None:
            continue
        for rs in d.roster:
            p = rs.player
            if not p:
                continue
            is_starter = rs.slot not in BENCH_SLOTS
            if not include_bench and not is_starter:
                continue
            espn_id = None
            if s.platform == "espn":
                espn_id = int(p.platform_player_id) if p.platform_player_id.lstrip("-").isdigit() else None
            elif p.sleeper_id:
                espn_id = db.espn_id_for(p.sleeper_id)
            if not espn_id or espn_id < 0 or p.position == "DEF":
                if p.position != "DEF" and p.name not in unmapped:
                    unmapped.append(p.name)
                continue
            e = players.setdefault(str(espn_id), {
                "espn_id": espn_id, "sleeper_id": p.sleeper_id, "name": p.name, "position": p.position,
                "nfl_team": p.nfl_team, "injury_status": p.injury_status, "leagues": [],
            })
            e["leagues"].append({"platform": s.platform, "league_id": s.league_id, "league_name": s.name,
                                 "slot": rs.slot, "is_starter": is_starter})

    with ThreadPoolExecutor(max_workers=8) as ex:
        feeds = dict(zip(players.keys(), ex.map(lambda k: _safe(players[k]["espn_id"], days), players.keys())))

    # One ESPN story often tags several of my players; show it once, listing them all.
    by_id: dict[str, dict] = {}
    for k, e in players.items():
        who = {kk: e[kk] for kk in ("espn_id", "sleeper_id", "name", "position", "nfl_team", "injury_status")}
        for n in feeds.get(k, []):
            item = by_id.get(n["id"])
            if item is None:
                # `player` / `leagues` stay as the first player, for older clients.
                by_id[n["id"]] = {**n, "player": who, "leagues": list(e["leagues"]),
                                  "players": [{**who, "leagues": e["leagues"]}]}
            elif not any(x["espn_id"] == who["espn_id"] for x in item["players"]):
                item["players"].append({**who, "leagues": e["leagues"]})
    items = sorted(by_id.values(), key=lambda n: n.get("published") or "", reverse=True)
    return {"days": days, "players": len(players), "unmapped": unmapped, "items": items}


def _safe(espn_id: int, days: int) -> list[dict]:
    try:
        return player_feed(espn_id, days)
    except Exception:
        return []
