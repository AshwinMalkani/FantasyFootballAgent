from app.services.playparse import default_scoring, parse_play, play_points


def test_rushing_td_with_missed_xp_by_someone_else():
    t = "D.Henry left tackle for 46 yards, TOUCHDOWN. T.Loop extra point is No Good, Hit Right Upright, Center-N.Moore, Holder-J.Stout."
    r = parse_play(t, "D.Henry", "BAL")
    assert r["summary"] == "46-yd rush, TD"
    assert r["delta"] == {"rush_att": 1, "rush_yd": 46, "rush_td": 1}
    assert play_points(r["delta"], None, 1.0) == 10.6
    assert parse_play(t, "T.Loop", "BAL")["delta"] == {"xpmiss": 1}


def test_receiving_td_both_sides():
    t = "(Shotgun) M.Penix pass short right to B.Robinson for 50 yards, TOUCHDOWN. Y.Koo extra point is GOOD, Center-L.McCullough, Holder-B.Pinion."
    r = parse_play(t, "B.Robinson", "ATL")
    assert r["summary"] == "50-yd catch, TD" and r["delta"] == {"rec": 1, "rec_yd": 50, "rec_td": 1}
    q = parse_play(t, "M.Penix", "ATL")
    assert q["summary"] == "50-yd TD pass to B.Robinson" and q["delta"] == {"pass_yd": 50, "pass_td": 1}
    assert parse_play(t, "Y.Koo", "ATL")["delta"] == {"xpm": 1}


def test_two_point_and_field_goal():
    t = "(Shotgun) T.Tagovailoa pass short right to D.Achane for 11 yards, TOUCHDOWN. TWO-POINT CONVERSION ATTEMPT. T.Tagovailoa pass to J.Hill is complete. ATTEMPT SUCCEEDS."
    assert parse_play(t, "J.Hill", "MIA")["delta"] == {"rec_2pt": 1}
    assert parse_play(t, "D.Achane", "MIA")["summary"] == "11-yd catch, TD"
    fg = parse_play("J.Myers 37 yard field goal is GOOD, Center-C.Stoll, Holder-M.Dickson.", "J.Myers", "SEA")
    assert fg["summary"] == "37-yd FG" and play_points(fg["delta"], None, 1.0) == 3


def test_no_impact_plays_return_none():
    assert parse_play("J.Allen pass incomplete short right to D.Kincaid.", "D.Kincaid", "BUF") is None
    assert parse_play("C.McLaughlin kicks 59 yards from TB 35 to ATL 6. J.Agnew to ATL 35 for 29 yards.", "C.McLaughlin", "TB") is None


def test_fumble_lost_and_interception():
    f = parse_play("D.Henry right guard to BLT 40 for 3 yards. D.Henry FUMBLES, RECOVERED by BUF-T.Bernard at BLT 41.", "D.Henry", "BAL")
    assert f["delta"] == {"rush_att": 1, "rush_yd": 3, "fum_lost": 1}
    assert play_points(f["delta"], default_scoring(1.0), 1.0) == -1.7
    i = parse_play("J.Allen pass deep left intended for K.Coleman INTERCEPTED by M.Humphrey at BLT 20.", "J.Allen", "BUF")
    assert i["delta"] == {"pass_int": 1}
    assert parse_play("J.Allen pass deep left intended for K.Coleman INTERCEPTED by M.Humphrey at BLT 20.", "K.Coleman", "BUF") is None


def test_leading_parentheticals_are_stripped():
    r = parse_play("(Shotgun, No Huddle) D.Henry left end for 5 yards.", "D.Henry", "BAL")
    assert r["summary"] == "5-yd rush" and r["delta"] == {"rush_att": 1, "rush_yd": 5}
    # Clock/formation tags stack, and reappear at the start of later sentences.
    t = ("(12:04) (Shotgun) J.Allen pass short right to J.Cook for 8 yards, TOUCHDOWN. "
         "(Pass formation) TWO-POINT CONVERSION ATTEMPT. J.Allen rushes right end. ATTEMPT SUCCEEDS.")
    assert parse_play(t, "J.Cook", "BUF")["delta"] == {"rec": 1, "rec_yd": 8, "rec_td": 1}
    assert parse_play(t, "J.Allen", "BUF")["delta"] == {"pass_yd": 8, "pass_td": 1, "rush_2pt": 1}
    # A tackler parenthetical still gets removed mid-sentence, not treated as a leading tag.
    f = parse_play("(No Huddle) S.Barkley right guard to PHI 40 for 3 yards (M.Humphrey).", "S.Barkley", "PHI")
    assert f["delta"] == {"rush_att": 1, "rush_yd": 3}
