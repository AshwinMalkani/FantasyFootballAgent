"""Live game data: Sleeper live stats, ESPN scoreboard and play-by-play. No auth needed."""
import re
import time
from collections import deque
from datetime import datetime, timezone

import httpx

from ..cache import cached
from .players import norm_team

POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"]
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"


def live_stats(season: int, week: int) -> dict[str, dict]:
    """sleeper_id -> {"stats": {...}, "updated_at": ms, "opponent": str|None}"""

    def fetch() -> dict:
        params = [("season_type", "regular"), ("order_by", "pts_ppr")] + [("position[]", p) for p in POSITIONS]
        r = httpx.get(f"https://api.sleeper.com/stats/nfl/{season}/{week}", params=params, timeout=30)
        r.raise_for_status()
        out = {}
        for row in r.json():
            stats = row.get("stats") or {}
            if stats:
                out[str(row["player_id"])] = {"stats": stats, "updated_at": row.get("updated_at"), "opponent": row.get("opponent")}
        return out

    return cached(f"live_stats_{season}_{week}", 30, fetch)


def scoreboard(date: str | None = None) -> dict[str, dict]:
    """NFL team abbr -> game info for the current (or given YYYYMMDD) scoreboard."""

    def fetch() -> dict:
        params = {"dates": date} if date else None
        r = httpx.get(f"{ESPN}/scoreboard", params=params, timeout=20)
        r.raise_for_status()
        out: dict[str, dict] = {}
        for ev in r.json().get("events", []):
            comp = ev["competitions"][0]
            st = comp.get("status", {}).get("type", {})
            teams = {c["homeAway"]: c for c in comp["competitors"]}
            home, away = teams.get("home", {}), teams.get("away", {})
            info = {
                "event_id": ev["id"],
                "name": ev.get("shortName") or ev.get("name"),
                "start": ev.get("date"),
                "state": st.get("state", "pre"),  # pre | in | post
                "detail": st.get("shortDetail") or st.get("detail"),
                "clock": comp.get("status", {}).get("displayClock"),
                "period": comp.get("status", {}).get("period"),
                "home": norm_team(home.get("team", {}).get("abbreviation")),
                "away": norm_team(away.get("team", {}).get("abbreviation")),
                "home_score": home.get("score"),
                "away_score": away.get("score"),
                "home_team_id": home.get("team", {}).get("id"),
                "away_team_id": away.get("team", {}).get("id"),
            }
            for abbr in (info["home"], info["away"]):
                if abbr:
                    out[abbr] = info
        return out

    return cached(f"scoreboard_{date or 'now'}", 30, fetch)


def plays(event_id: str, limit: int = 150) -> list[dict]:
    """Most recent plays of a game, newest first."""

    def fetch() -> list:
        r = httpx.get(f"{ESPN}/summary", params={"event": event_id}, timeout=20)
        r.raise_for_status()
        d = r.json()
        drives = d.get("drives", {})
        all_drives = list(drives.get("previous", []))
        if drives.get("current"):
            all_drives.append(drives["current"])
        out = []
        for drv in all_drives:
            for p in drv.get("plays", []):
                out.append({
                    "id": p.get("id"),
                    "text": p.get("text", ""),
                    "scoring": bool(p.get("scoringPlay")),
                    "wallclock": p.get("wallclock"),
                    "clock": (p.get("clock") or {}).get("displayValue"),
                    "period": (p.get("period") or {}).get("number"),
                    "team_id": ((p.get("start") or {}).get("team") or {}).get("id"),
                })
        out = [p for p in out if p["text"]]
        return out[-limit:][::-1]

    return cached(f"plays_{event_id}", 20, fetch)


# ---- name matching -----------------------------------------------------

def play_name_keys(full_name: str) -> list[str]:
    """ESPN play text abbreviates names as 'F.Lastname' (e.g. 'B.Robinson', 'A.St. Brown')."""
    parts = full_name.replace("’", "'").split()
    parts = [p for p in parts if p.lower().strip(".") not in ("jr", "sr", "ii", "iii", "iv", "v")]
    if len(parts) < 2:
        return [full_name]
    first, last = parts[0], " ".join(parts[1:])
    return [f"{first[0]}.{last}", full_name]


def play_mentions(play_text: str, keys: list[str]) -> bool:
    for k in keys:
        # Word boundary after the name avoids 'J.Allen' matching 'J.Allenby'.
        if re.search(re.escape(k) + r"(?![A-Za-z])", play_text):
            return True
    return False


# ---- stat lines ----------------------------------------------------------

def _n(v) -> int:
    try:
        return int(round(float(v or 0)))
    except (TypeError, ValueError):
        return 0


def stat_line(position: str, s: dict) -> str:
    parts = []
    if position == "QB":
        if s.get("pass_att"):
            parts.append(f"{_n(s.get('pass_cmp'))}/{_n(s.get('pass_att'))}, {_n(s.get('pass_yd'))} yds, {_n(s.get('pass_td'))} TD, {_n(s.get('pass_int'))} INT")
        if s.get("rush_att"):
            parts.append(f"{_n(s.get('rush_att'))} car, {_n(s.get('rush_yd'))} yds" + (f", {_n(s.get('rush_td'))} TD" if s.get("rush_td") else ""))
    elif position in ("RB", "WR", "TE"):
        if s.get("rush_att"):
            parts.append(f"{_n(s.get('rush_att'))} car, {_n(s.get('rush_yd'))} yds" + (f", {_n(s.get('rush_td'))} TD" if s.get("rush_td") else ""))
        if s.get("rec_tgt") or s.get("rec"):
            parts.append(f"{_n(s.get('rec'))}/{_n(s.get('rec_tgt'))} rec, {_n(s.get('rec_yd'))} yds" + (f", {_n(s.get('rec_td'))} TD" if s.get("rec_td") else ""))
    elif position == "K":
        parts.append(f"{_n(s.get('fgm'))}/{_n(s.get('fga'))} FG, {_n(s.get('xpm'))}/{_n(s.get('xpa'))} XP")
    elif position == "DEF":
        parts.append(f"{_n(s.get('sack'))} sk, {_n(s.get('int'))} INT, {_n(s.get('fum_rec'))} FR, {_n(s.get('def_td'))} TD, {_n(s.get('pts_allow'))} PA")
    if s.get("fum_lost"):
        parts.append(f"{_n(s.get('fum_lost'))} FL")
    return "; ".join(parts) or "no stats yet"


# ---- change tracking -------------------------------------------------------
# Server memory only: what each player's line looked like at the last poll, and a feed of changes.
_last_stats: dict[str, dict] = {}
_last_points: dict[str, float] = {}
_events: deque = deque(maxlen=400)
TRACKED = ["pass_yd", "pass_td", "pass_int", "rush_att", "rush_yd", "rush_td", "rec", "rec_yd", "rec_td",
           "fum_lost", "fgm", "xpm", "sack", "int", "fum_rec", "def_td", "pts_allow"]


def record_changes(sleeper_id: str, name: str, stats: dict, league_points: list[dict]) -> None:
    """Compare against the previous snapshot and append a feed event when something moved."""
    prev = _last_stats.get(sleeper_id)
    _last_stats[sleeper_id] = stats
    key_pts = {lp["league_key"]: lp["points"] for lp in league_points}
    prev_pts = _last_points.get(sleeper_id)
    _last_points[sleeper_id] = key_pts
    if prev is None or prev_pts is None:
        return  # first sighting: establish a baseline, don't announce the whole game so far
    diff = []
    for k in TRACKED:
        a, b = float(prev.get(k) or 0), float(stats.get(k) or 0)
        if abs(b - a) >= 0.5:
            diff.append({"stat": k, "delta": round(b - a, 1)})
    deltas = [{"league_key": lp["league_key"], "league_name": lp["league_name"], "platform": lp["platform"],
               "delta": round(lp["points"] - prev_pts.get(lp["league_key"], lp["points"]), 2)} for lp in league_points]
    deltas = [d for d in deltas if abs(d["delta"]) >= 0.05]
    if not diff and not deltas:
        return
    _events.appendleft({
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "stats",
        "sleeper_id": sleeper_id,
        "name": name,
        "stat_diff": diff,
        "league_deltas": deltas,
        "text": None,
    })


def recent_events(limit: int = 60) -> list[dict]:
    return list(_events)[:limit]


def reset_tracking() -> None:
    _last_stats.clear()
    _last_points.clear()
    _events.clear()
