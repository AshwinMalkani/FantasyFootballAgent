from app.services import live
from app.services.live import play_mentions, play_name_keys, record_changes, recent_events, reset_tracking, stat_line


def test_play_name_matching():
    keys = play_name_keys("Bijan Robinson")
    assert keys[0] == "B.Robinson"
    assert play_mentions("(Shotgun) M.Penix pass short right to B.Robinson for 50 yards, TOUCHDOWN.", keys)
    assert not play_mentions("B.Robinsonville kicks off", keys)
    assert play_name_keys("Amon-Ra St. Brown")[0] == "A.St. Brown"
    assert play_name_keys("Marvin Harrison Jr.")[0] == "M.Harrison"


def test_stat_line_rb():
    s = {"rush_att": 12, "rush_yd": 78.0, "rush_td": 1, "rec": 3, "rec_tgt": 4, "rec_yd": 24}
    assert stat_line("RB", s) == "12 car, 78 yds, 1 TD; 3/4 rec, 24 yds"


def test_change_tracking_emits_after_baseline():
    reset_tracking()
    lp = [{"league_key": "sleeper:1", "league_name": "L1", "platform": "sleeper", "points": 4.0}]
    record_changes("9221", "Bijan Robinson", {"rush_yd": 20}, lp)
    assert recent_events() == []  # baseline only
    lp2 = [{"league_key": "sleeper:1", "league_name": "L1", "platform": "sleeper", "points": 12.4}]
    record_changes("9221", "Bijan Robinson", {"rush_yd": 44, "rush_td": 1}, lp2)
    ev = recent_events()
    assert len(ev) == 1
    assert {d["stat"]: d["delta"] for d in ev[0]["stat_diff"]} == {"rush_yd": 24.0, "rush_td": 1.0}
    assert ev[0]["league_deltas"][0]["delta"] == 8.4
