from app.models import Player, RosterSlot
from app.services.recommendations import optimize_lineup, rank_waivers


def P(pid, name, pos, pts, team="KC", injury=None, bye=False):
    return Player(platform_player_id=pid, sleeper_id=pid, name=name, position=pos, nfl_team=team,
                  projected_points=pts, injury_status=injury, on_bye=bye, projection_source="sleeper-exact")


SLOTS = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K", "DEF", "BN", "BN", "BN"]


def test_benches_bye_player_and_promotes_best_flex():
    roster = [
        RosterSlot(slot="QB", player=P("1", "QB1", "QB", 20)),
        RosterSlot(slot="RB", player=P("2", "RB1", "RB", 15)),
        RosterSlot(slot="RB", player=P("3", "RB2", "RB", 12, bye=True)),
        RosterSlot(slot="WR", player=P("4", "WR1", "WR", 14)),
        RosterSlot(slot="WR", player=P("5", "WR2", "WR", 11)),
        RosterSlot(slot="TE", player=P("6", "TE1", "TE", 8)),
        RosterSlot(slot="FLEX", player=P("7", "WR3", "WR", 9)),
        RosterSlot(slot="K", player=P("8", "K1", "K", 7)),
        RosterSlot(slot="DEF", player=P("KC", "KC", "DEF", 6)),
        RosterSlot(slot="BN", player=P("9", "RB3", "RB", 10)),
        RosterSlot(slot="BN", player=P("10", "WR4", "WR", 9.2)),
        RosterSlot(slot="BN", player=P("11", "TE2", "TE", 3)),
    ]
    s = optimize_lineup(roster, SLOTS)
    ids = {rs.slot: rs.player.platform_player_id for rs in s.suggested_starters}
    starters = {rs.player.platform_player_id for rs in s.suggested_starters}
    assert "3" not in starters  # bye player benched
    assert "9" in starters      # RB3 promoted
    assert ids["RB"] in ("2", "9")
    # RB1 stays in his own RB slot (no phantom swap)
    assert s.suggested_starters[1].player.platform_player_id == "2"
    assert s.projected_gain == 10.0
    assert len(s.moves) == 1 and s.moves[0].in_.name == "RB3" and s.moves[0].out.name == "RB2"
    assert any("bye" in f for f in s.flags)


def test_out_player_zeroed_and_marginal_swap_ignored():
    roster = [
        RosterSlot(slot="QB", player=P("1", "QB1", "QB", 18, injury="Out")),
        RosterSlot(slot="WR", player=P("4", "WR1", "WR", 10.0)),
        RosterSlot(slot="BN", player=P("2", "QB2", "QB", 12)),
        RosterSlot(slot="BN", player=P("5", "WR2", "WR", 10.3)),
    ]
    s = optimize_lineup(roster, ["QB", "WR", "BN", "BN"])
    assert s.suggested_starters[0].player.name == "QB2"
    assert s.suggested_starters[1].player.name == "WR1"  # +0.3 is below the noise threshold
    assert [m.in_.name for m in s.moves] == ["QB2"]


def test_superflex_takes_second_qb():
    roster = [
        RosterSlot(slot="QB", player=P("1", "QB1", "QB", 20)),
        RosterSlot(slot="SUPER_FLEX", player=P("3", "RB1", "RB", 12)),
        RosterSlot(slot="BN", player=P("2", "QB2", "QB", 17)),
    ]
    s = optimize_lineup(roster, ["QB", "SUPER_FLEX", "BN"])
    assert s.suggested_starters[1].player.name == "QB2"


def test_waivers_rank_and_suggest_drop():
    roster = [
        RosterSlot(slot="RB", player=P("2", "RB1", "RB", 15)),
        RosterSlot(slot="BN", player=P("9", "RB3", "RB", 4)),
        RosterSlot(slot="BN", player=P("10", "WR4", "WR", 6, bye=True)),
        RosterSlot(slot="BN", player=P("11", "TE2", "TE", 3)),
    ]
    fas = [P("100", "FA RB", "RB", 9), P("101", "FA WR", "WR", 7), P("102", "Nobody", "WR", 0)]
    t = rank_waivers(fas, roster, trending={"101": 50000}, lineup_slots=["RB", "FLEX", "BN", "BN", "BN"])
    assert [x.player.name for x in t] == ["FA WR", "FA RB"]  # trending bonus lifts the WR above the RB
    assert t[0].score == 9.7 and t[1].score == 7.5
    # FA RB (9) would take FLEX over RB3 (4): lineup gain of 5
    assert next(x for x in t if x.player.name == "FA RB").lineup_gain == 5.0
    rb = next(x for x in t if x.player.name == "FA RB")
    assert rb.suggested_drop.name == "RB3" and rb.net_gain == 5.0
    wr = next(x for x in t if x.player.name == "FA WR")
    assert wr.suggested_drop.name == "TE2"  # bye-week WR4 is not offered as a drop


def test_moves_reported_as_swaps_not_slot_shuffles():
    roster = [
        RosterSlot(slot="RB", player=P("1", "RB1", "RB", 20)),
        RosterSlot(slot="RB", player=P("2", "RB2", "RB", 9.7)),
        RosterSlot(slot="FLEX", player=P("3", "WR3", "WR", 6.9)),
        RosterSlot(slot="BN", player=P("4", "RB3", "RB", 10.2)),
    ]
    s = optimize_lineup(roster, ["RB", "RB", "FLEX", "BN"])
    assert len(s.moves) == 1
    assert s.moves[0].in_.name == "RB3" and s.moves[0].out.name == "WR3"
    assert s.moves[0].delta == 3.3


def test_started_players_are_locked():
    a = P("1", "RB1", "RB", 5); a.game_state = "post"; a.actual_points = 3.2
    b = P("2", "RB2", "RB", 14)
    c = P("3", "RB3", "RB", 12); c.game_state = "in"
    roster = [RosterSlot(slot="RB", player=a), RosterSlot(slot="BN", player=b), RosterSlot(slot="BN", player=c)]
    s = optimize_lineup(roster, ["RB", "BN", "BN"])
    assert s.suggested_starters[0].player.name == "RB1"  # game over: can't swap out
    assert s.moves == []


def test_no_slot_shuffle_between_wr_and_flex():
    roster = [
        RosterSlot(slot="WR", player=P("1", "WR1", "WR", 13.3)),
        RosterSlot(slot="FLEX", player=P("2", "WR2", "WR", 13.7)),
        RosterSlot(slot="BN", player=P("3", "RB9", "RB", 2)),
    ]
    s = optimize_lineup(roster, ["WR", "FLEX", "BN"])
    assert [rs.player.name for rs in s.suggested_starters] == ["WR1", "WR2"]
    assert s.moves == []


def test_effective_points_uses_actual_once_the_game_starts():
    from app.services.recommendations import effective_points
    pre = P("1", "RB1", "RB", 12.0)
    assert effective_points(pre) == 12.0
    done = P("2", "RB2", "RB", 12.0); done.game_state = "post"; done.actual_points = 3.4
    assert effective_points(done) == 3.4
    dnp = P("3", "RB3", "RB", 12.0); dnp.game_state = "post"
    assert effective_points(dnp) == 0.0          # game over, never played
    playing = P("4", "RB4", "RB", 12.0); playing.game_state = "in"; playing.actual_points = 2.0
    assert effective_points(playing) == 2.0
    kickoff = P("5", "RB5", "RB", 12.0); kickoff.game_state = "in"
    assert effective_points(kickoff) == 12.0     # no stats yet: keep the projection
    # An "Out" (or bye) tag must not wipe points a player actually scored.
    surprise = P("6", "RB6", "RB", 0.0, injury="Out"); surprise.game_state = "post"; surprise.actual_points = 14.2
    assert effective_points(surprise) == 14.2
    benched = P("7", "RB7", "RB", 11.0, injury="Out")
    assert effective_points(benched) == 0.0


def test_lineup_total_counts_finished_games_not_projections():
    roster = [
        RosterSlot(slot="RB", player=P("1", "RB1", "RB", 15.0)),
        RosterSlot(slot="BN", player=P("2", "RB2", "RB", 9.0)),
    ]
    roster[0].player.game_state = "post"
    roster[0].player.actual_points = 21.5
    s = optimize_lineup(roster, ["RB", "BN"])
    assert s.current_total == 21.5 and s.suggested_total == 21.5
    assert s.moves == []  # RB1's game is over; he is locked in


def test_waivers_never_suggest_dropping_a_player_mid_game():
    playing = P("9", "RB3", "RB", 4); playing.game_state = "in"
    finished = P("11", "TE2", "TE", 3); finished.game_state = "post"; finished.actual_points = 1.0
    roster = [
        RosterSlot(slot="RB", player=P("2", "RB1", "RB", 15)),
        RosterSlot(slot="BN", player=playing),
        RosterSlot(slot="BN", player=finished),
    ]
    t = rank_waivers([P("100", "FA RB", "RB", 9)], roster, trending={}, lineup_slots=["RB", "FLEX", "BN", "BN"])
    drop = t[0].suggested_drop
    assert drop is not None and drop.name == "TE2"  # RB3 is playing right now; TE2 is done
