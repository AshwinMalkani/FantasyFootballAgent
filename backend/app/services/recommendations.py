"""Deterministic lineup optimizer and waiver ranker. Pure functions, no I/O."""
import math

from ..models import BENCH_SLOTS, LineupMove, LineupSuggestion, Player, RosterSlot, WaiverTarget

SLOT_ELIGIBILITY: dict[str, set[str]] = {
    "QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "K": {"K"}, "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"}, "WRRB_FLEX": {"RB", "WR"}, "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "DL": {"DL", "DE", "DT"}, "LB": {"LB"}, "DB": {"DB", "CB", "S"},
    "IDP_FLEX": {"DL", "DE", "DT", "LB", "DB", "CB", "S"},
}
# Injury statuses that make a player worthless this week.
ZERO_STATUSES = {"OUT", "O", "IR", "INJURY_RESERVE", "SUS", "SUSP", "SUSPENSION", "PUP", "NA", "DOUBTFUL", "D", "COV", "NFI"}
QUESTIONABLE = {"QUESTIONABLE", "Q"}
MIN_MOVE_DELTA = 0.5


def effective_points(p: Player | None) -> float:
    if p is None or p.on_bye:
        return 0.0
    if (p.injury_status or "").upper() in ZERO_STATUSES:
        return 0.0
    return p.projected_points


def _eligible(slot: str, p: Player) -> bool:
    return p.position in SLOT_ELIGIBILITY.get(slot, {slot})


def starting_slots(lineup_slots: list[str]) -> list[str]:
    return [s for s in lineup_slots if s not in BENCH_SLOTS]


def optimize_lineup(roster: list[RosterSlot], lineup_slots: list[str]) -> LineupSuggestion:
    slots = starting_slots(lineup_slots)
    current_slots = [rs for rs in roster if rs.slot not in BENCH_SLOTS]
    # Align current starters to the slot template order.
    current: list[RosterSlot] = []
    pool_current = list(current_slots)
    for s in slots:
        match = next((rs for rs in pool_current if rs.slot == s), None)
        if match:
            pool_current.remove(match)
            current.append(match)
        else:
            current.append(RosterSlot(slot=s, player=None))

    # IR/TAXI players can't be started without a roster move; everyone else can.
    pool = [rs.player for rs in roster if rs.player and rs.slot not in ("IR", "TAXI")]
    used: set[str] = set()
    chosen: dict[int, Player | None] = {}
    # Fill the most restrictive slots first, then flex slots.
    order = sorted(range(len(slots)), key=lambda i: (len(SLOT_ELIGIBILITY.get(slots[i], {slots[i]})), i))
    for i in order:
        cands = [p for p in pool if p.platform_player_id not in used and _eligible(slots[i], p)]
        best = max(cands, key=effective_points, default=None)
        chosen[i] = best
        if best:
            used.add(best.platform_player_id)

    # Keep retained players in the slot they already occupy (avoids RB1/RB2 phantom swaps).
    suggested: list[Player | None] = [None] * len(slots)
    remaining = {i: p for i, p in chosen.items()}
    for label in set(slots):
        idxs = [i for i, s in enumerate(slots) if s == label]
        new_players = {p.platform_player_id: p for i in idxs for p in [remaining[i]] if p}
        free_idxs = []
        for i in idxs:
            cur = current[i].player
            if cur and cur.platform_player_id in new_players:
                suggested[i] = new_players.pop(cur.platform_player_id)
            else:
                free_idxs.append(i)
        for i, p in zip(free_idxs, list(new_players.values())):
            suggested[i] = p

    # Drop marginal swaps below the noise threshold.
    for i in range(len(slots)):
        cur, new = current[i].player, suggested[i]
        if cur is None or new is None or cur.platform_player_id == new.platform_player_id:
            continue
        delta = effective_points(new) - effective_points(cur)
        still_used = any(s and s.platform_player_id == cur.platform_player_id for j, s in enumerate(suggested) if j != i)
        if delta < MIN_MOVE_DELTA and not still_used and _eligible(slots[i], cur):
            suggested[i] = cur

    # Report moves as bench-for-starter swaps (slot reshuffles among retained players are implicit).
    cur_ids = {p.platform_player_id for p in (rs.player for rs in current) if p}
    new_ids = {p.platform_player_id for p in suggested if p}
    entering = sorted([(i, p) for i, p in enumerate(suggested) if p and p.platform_player_id not in cur_ids],
                      key=lambda ip: effective_points(ip[1]), reverse=True)
    leaving = sorted([rs.player for rs in current if rs.player and rs.player.platform_player_id not in new_ids],
                     key=effective_points, reverse=True)
    moves: list[LineupMove] = []
    for k, (i, p) in enumerate(entering):
        out = leaving[k] if k < len(leaving) else None
        moves.append(LineupMove(slot=slots[i], out=out, in_=p, delta=round(effective_points(p) - effective_points(out), 2)))

    flags: list[str] = []
    for i, s in enumerate(slots):
        new = suggested[i]
        if new and (new.injury_status or "").upper() in QUESTIONABLE:
            flags.append(f"{new.name} ({s}) is Questionable")
        if new is None:
            flags.append(f"No eligible player for {s}")
    for rs in current:
        p = rs.player
        if p and (p.on_bye or (p.injury_status or "").upper() in ZERO_STATUSES):
            why = "on bye" if p.on_bye else (p.injury_status or "out")
            flags.append(f"{p.name} is currently starting at {rs.slot} but is {why}")

    cur_total = round(sum(effective_points(rs.player) for rs in current), 2)
    new_total = round(sum(effective_points(p) for p in suggested), 2)
    return LineupSuggestion(
        current_starters=current,
        suggested_starters=[RosterSlot(slot=s, player=suggested[i]) for i, s in enumerate(slots)],
        moves=moves,
        current_total=cur_total,
        suggested_total=new_total,
        projected_gain=round(new_total - cur_total, 2),
        flags=flags,
    )


def trending_bonus(adds: int) -> float:
    return round(min(5.0, math.log10(1 + max(adds, 0))), 2) if adds else 0.0


def rank_waivers(
    free_agents: list[Player],
    roster: list[RosterSlot],
    trending: dict[str, int],
    limit: int = 15,
    lineup_slots: list[str] | None = None,
) -> list[WaiverTarget]:
    bench = [rs.player for rs in roster if rs.slot == "BN" and rs.player]
    droppable = [p for p in bench if not p.on_bye]
    base_total = optimize_lineup(roster, lineup_slots).suggested_total if lineup_slots else None
    # Depth (bench) value matters less at positions you rarely start more than one of.
    slots = starting_slots(lineup_slots or [])
    qb_depth = 0.5 if (slots.count("QB") > 1 or "SUPER_FLEX" in slots) else 0.25
    depth_weight = {"QB": qb_depth, "K": 0.1, "DEF": 0.2}

    def lineup_gain(cand: Player) -> float:
        if base_total is None:
            return 0.0
        with_cand = roster + [RosterSlot(slot="BN", player=cand)]
        return round(max(0.0, optimize_lineup(with_cand, lineup_slots).suggested_total - base_total), 2)

    def drop_for(cand: Player) -> Player | None:
        same = [p for p in droppable if p.position == cand.position]
        if same:
            return min(same, key=lambda p: p.projected_points)
        if cand.position in ("K", "DEF"):
            return None
        skill = [p for p in droppable if p.position in ("RB", "WR", "TE")]
        return min(skill, key=lambda p: p.projected_points, default=None)

    targets: list[WaiverTarget] = []
    for fa in free_agents:
        adds = trending.get(fa.sleeper_id or "", 0)
        eff = effective_points(fa)
        if eff <= 0 and adds == 0:
            continue
        gain = lineup_gain(fa)
        drop = drop_for(fa)
        net = round(fa.projected_points - drop.projected_points, 2) if drop else None
        depth = depth_weight.get(fa.position, 0.5) * max(net or 0.0, 0.0)
        # Hype without a projection (often injury news) still shows, but at half weight.
        score = round(gain + depth + trending_bonus(adds) * (1.0 if eff > 0 else 0.5), 2)
        targets.append(WaiverTarget(player=fa, score=score, trending_adds=adds, lineup_gain=gain,
                                    suggested_drop=drop, net_gain=net))
    targets.sort(key=lambda t: t.score, reverse=True)
    return targets[:limit]
