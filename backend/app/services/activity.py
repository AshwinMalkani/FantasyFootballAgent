"""Game-day activity: my players across every league with live stats, plays, and point changes."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from ..models import BENCH_SLOTS, LeagueError
from ..providers.registry import all_leagues, build_providers, current_state
from .live import live_stats, play_mentions, play_name_keys, plays, recent_events, record_changes, scoreboard, stat_line
from .playparse import parse_play, play_points
from .scoring import approx_points, score_stat_line

REC_BY_LABEL = {"PPR": 1.0, "Half PPR": 0.5, "Standard": 0.0}


TABLE_PLAYS = 8  # the table only renders plays[0]; the feed uses the full list


def _league_points(platform: str, scoring: dict, label: str | None, stats: dict, actual: float | None = None) -> float:
    """The league's own number when we have it (ESPN's real total, Sleeper's exact score)."""
    if actual is not None:
        return actual
    if platform == "sleeper" and scoring:
        return score_stat_line(stats, scoring)
    return approx_points(stats, REC_BY_LABEL.get(label or "", 0.5))


def build_activity(include_bench: bool = False, season: int | None = None, week: int | None = None,
                   date: str | None = None) -> dict:
    state = current_state()
    season = season or state.season
    week = week or state.week
    # Replay mode (a past season/week): the rosters' own actuals and the change tracker
    # both belong to the live week, so neither may be used here.
    is_current = season == state.season and week == state.week
    providers = build_providers()
    summaries = [s for s in all_leagues() if not isinstance(s, LeagueError)]

    # Roster of every league, in parallel (all cached for 10 min by the providers).
    def load(s):
        try:
            return s, providers[s.platform].detail(s.league_id)
        except Exception:
            return s, None

    with ThreadPoolExecutor(max_workers=5) as ex:
        details = list(ex.map(load, summaries))

    stats = live_stats(season, week)
    board = scoreboard(date)

    players: dict[str, dict] = {}
    league_scoring: dict[str, tuple] = {}
    for s, d in details:
        if d is None:
            continue
        league_key = f"{s.platform}:{s.league_id}"
        league_scoring[league_key] = (d.scoring if s.platform == "sleeper" else None, REC_BY_LABEL.get(s.scoring_label or "", 0.5))
        for rs in d.roster:
            p = rs.player
            if not p or not p.sleeper_id:
                continue
            is_starter = rs.slot not in BENCH_SLOTS
            if not include_bench and not is_starter:
                continue
            entry = players.setdefault(p.sleeper_id, {
                "sleeper_id": p.sleeper_id, "name": p.name, "position": p.position, "nfl_team": p.nfl_team,
                "injury_status": p.injury_status, "leagues": [], "stats": {}, "stat_line": "no stats yet",
                "updated_at": None, "game": None, "plays": [], "pts_ppr": 0.0,
            })
            live = stats.get(p.sleeper_id)
            st = live["stats"] if live else {}
            entry["leagues"].append({
                "league_key": league_key, "platform": s.platform, "league_id": s.league_id, "league_name": s.name,
                "slot": rs.slot, "is_starter": is_starter,
                "points": _league_points(s.platform, d.scoring, s.scoring_label, st,
                                        p.actual_points if is_current else None),
                "projected": p.projected_points,
            })
            if live:
                entry["stats"] = st
                entry["stat_line"] = stat_line(p.position, st)
                entry["updated_at"] = live.get("updated_at")
                entry["pts_ppr"] = float(st.get("pts_ppr") or 0.0)

    # Game status + plays, one fetch per distinct game.
    games: dict[str, dict] = {}
    for e in players.values():
        g = board.get(e["nfl_team"] or "")
        if g:
            e["game"] = g
            games[g["event_id"]] = g
    live_games = {eid: g for eid, g in games.items() if g["state"] != "pre"}
    with ThreadPoolExecutor(max_workers=6) as ex:
        game_plays = dict(zip(live_games.keys(), ex.map(lambda eid: plays(eid), live_games.keys())))

    for e in players.values():
        g = e.get("game")
        if not g or g["event_id"] not in game_plays or e["position"] == "DEF":
            continue
        keys = play_name_keys(e["name"])
        # Parse every match: the feed filters by point value afterwards, so capping here
        # would drop an early TD once the player has newer touches.
        matched = [p for p in game_plays[g["event_id"]] if play_mentions(p["text"], keys)]
        out = []
        for p in matched:
            parsed = parse_play(p["text"], keys[0], e["nfl_team"])
            p = dict(p)
            p["summary"] = parsed["summary"] if parsed else None
            p["league_points"] = []
            if parsed:
                for l in e["leagues"]:
                    scoring, rec = league_scoring[l["league_key"]]
                    p["league_points"].append({"league_key": l["league_key"], "league_name": l["league_name"],
                                               "platform": l["platform"], "delta": play_points(parsed["delta"], scoring, rec)})
            out.append(p)
        e["plays"] = out

    # Feed: stat changes since the last poll + scoring plays involving my players.
    # A replay of a past week must not touch (or read) the live baseline.
    events: list[dict] = []
    if is_current:
        for e in players.values():
            if e["stats"]:
                record_changes(e["sleeper_id"], e["name"], e["stats"], e["leagues"])
        events = recent_events()
    seen_play_ids = {ev.get("play_id") for ev in events}
    for e in players.values():
        for p in e["plays"]:
            if p["id"] in seen_play_ids or not p.get("summary"):
                continue
            if not any(abs(lp["delta"]) >= 1.0 for lp in p["league_points"]):  # skip 2-yd runs and the like
                continue
            seen_play_ids.add(p["id"])
            events.append({
                "ts": p.get("wallclock") or datetime.now(timezone.utc).isoformat(), "kind": "play", "play_id": p["id"],
                "sleeper_id": e["sleeper_id"], "name": e["name"], "summary": p["summary"], "text": p["text"],
                "stat_diff": [], "league_deltas": p["league_points"],
            })
    events.sort(key=lambda ev: ev["ts"], reverse=True)

    # The client only shows the newest play per player; keep the payload small.
    for e in players.values():
        e["plays"] = e["plays"][:TABLE_PLAYS]

    def sort_key(e):
        g = e.get("game") or {}
        order = {"in": 0, "post": 1, "pre": 2}.get(g.get("state", "pre"), 2)
        return (order, -e["pts_ppr"], e["name"])

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "season": season, "week": week,
        "games": sorted(games.values(), key=lambda g: ({"in": 0, "pre": 1, "post": 2}[g["state"]], g["start"] or "")),
        "players": sorted(players.values(), key=sort_key),
        "events": events[:60],
    }
