"""Turn ESPN play-by-play text into what ONE player did, in fantasy stat terms."""
import re

from .scoring import score_stat_line

# ESPN play text uses old-style abbreviations for some teams.
ESPN_TEXT_ABBR = {"BAL": "BLT", "ARI": "ARZ", "HOU": "HST", "CLE": "CLV", "LAR": "LA", "WAS": "WSH"}

# Default scoring for leagues where we don't have exact settings (ESPN / Yahoo).
def default_scoring(rec_value: float) -> dict[str, float]:
    return {
        "pass_yd": 0.04, "pass_td": 4, "pass_int": -2, "pass_2pt": 2,
        "rush_yd": 0.1, "rush_td": 6, "rush_2pt": 2,
        "rec": rec_value, "rec_yd": 0.1, "rec_td": 6, "rec_2pt": 2,
        "fum_lost": -2, "xpm": 1, "fgm_0_19": 3, "fgm_20_29": 3, "fgm_30_39": 3, "fgm_40_49": 4, "fgm_50p": 5,
        "sack": 1, "int": 2, "fum_rec": 2, "def_td": 6, "safe": 2, "blk_kick": 2, "ff": 1,
    }


def team_text_abbrs(team: str | None) -> set[str]:
    """Abbreviations ESPN play text may use for a team (e.g. BAL appears as BLT)."""
    if not team:
        return set()
    return {team, ESPN_TEXT_ABBR.get(team, team)}


def parse_def_play(text: str, def_team: str | None) -> dict | None:
    """What a DEFENSE did on an opponent's offensive play. Caller must ensure the offense is the other team."""
    t = _clean(text)
    up = t.upper()
    mine = team_text_abbrs(def_team)
    delta: dict[str, float] = {}
    bits: list[str] = []
    turnover = False
    if "INTERCEPTED" in up:
        delta["int"] = 1
        bits.append("interception")
        turnover = True
    if "SACKED" in up:
        delta["sack"] = len(re.findall(r"\bsacked\b", t, re.I))
        bits.append("sack")
    if "FUMBLES" in up:
        rec = re.search(r"RECOVERED by ([A-Z]{2,3})-", t)
        if rec and rec.group(1) in mine:
            delta["fum_rec"] = 1
            delta["ff"] = 1
            bits.append("fumble recovery")
            turnover = True
    if "SAFETY" in up:
        delta["safe"] = 1
        bits.append("safety")
    if re.search(r"\bis BLOCKED\b", t, re.I):
        delta["blk_kick"] = 1
        bits.append("blocked kick")
    if turnover and "TOUCHDOWN" in up:
        delta["def_td"] = 1
        bits.append("defensive TD")
    if not delta:
        return None
    return {"summary": ", ".join(bits), "delta": delta}


def _yards(sentence: str) -> int | None:
    if re.search(r"for no gain", sentence):
        return 0
    m = re.search(r"for (-?\d+) yards?", sentence)
    return int(m.group(1)) if m else None


def _fg_bucket(dist: int) -> str:
    if dist < 20:
        return "fgm_0_19"
    if dist < 30:
        return "fgm_20_29"
    if dist < 40:
        return "fgm_30_39"
    if dist < 50:
        return "fgm_40_49"
    return "fgm_50p"


# Formation / clock tags ESPN puts in front of a play or of a sentence inside it:
# "(Shotgun)", "(No Huddle, Shotgun)", "(4:12)", "(Field Goal formation)", ...
_LEAD_TAGS = re.compile(r"(^|[.!]\s+)(?:\([^)]*\)\s*)+")


def _clean(text: str) -> str:
    t = _LEAD_TAGS.sub(r"\1", text)
    t = re.sub(r"\s*\([A-Z]\.[^)]*\)", "", t)  # tacklers: "(G.Rousseau)"
    t = re.sub(r",?\s*Center-[^.]*", "", t)     # snap/hold credits on kicks
    return t.strip()


def _mentions(sentence: str, key: str) -> bool:
    return re.search(re.escape(key) + r"(?![A-Za-z])", sentence) is not None


def _starts_with(sentence: str, key: str) -> bool:
    return re.match(re.escape(key) + r"(?![A-Za-z])", sentence.strip()) is not None


def parse_play(text: str, key: str, team: str | None) -> dict | None:
    """key is the player's play-text name ('D.Henry'). Returns {"summary", "delta"} or None if no fantasy impact."""
    t = _clean(text)
    sentences = [s.strip() for s in re.split(r"(?<=[.!])\s+", t) if s.strip()]
    delta: dict[str, float] = {}
    bits: list[str] = []
    in_2pt = False
    two_pt_role: str | None = None

    for s in sentences:
        up = s.upper()
        if "TWO-POINT CONVERSION ATTEMPT" in up:
            in_2pt = True
            continue
        if in_2pt:
            if "ATTEMPT SUCCEEDS" in up:
                if two_pt_role:
                    delta[f"{two_pt_role}_2pt"] = delta.get(f"{two_pt_role}_2pt", 0) + 1
                    bits.append("2-pt conversion")
                in_2pt = False
            elif "ATTEMPT FAILS" in up:
                in_2pt = False
            elif _mentions(s, key):
                if " pass " in s and not _starts_with(s, key):
                    two_pt_role = "rec"
                elif " pass " in s:
                    two_pt_role = "pass"
                else:
                    two_pt_role = "rush"
            continue
        if not _mentions(s, key):
            continue

        td = "TOUCHDOWN" in up
        # Kicks
        m = re.search(re.escape(key) + r" (\d+) yard field goal is (GOOD|No Good|BLOCKED)", s, re.I)
        if m:
            dist, res = int(m.group(1)), m.group(2).upper()
            if res == "GOOD":
                delta[_fg_bucket(dist)] = delta.get(_fg_bucket(dist), 0) + 1
                bits.append(f"{dist}-yd FG")
            else:
                delta["fgmiss"] = delta.get("fgmiss", 0) + 1
                bits.append(f"{dist}-yd FG missed")
            continue
        m = re.search(re.escape(key) + r" extra point is (GOOD|No Good|BLOCKED)", s, re.I)
        if m:
            if m.group(1).upper() == "GOOD":
                delta["xpm"] = delta.get("xpm", 0) + 1
                bits.append("XP")
            else:
                delta["xpmiss"] = delta.get("xpmiss", 0) + 1
                bits.append("XP missed")
            continue
        if "kicks" in s and _starts_with(s, key):
            continue  # kickoff

        # Passing plays
        if " pass " in s or s.startswith(key + " pass"):
            passer = _starts_with(s, key)
            intercepted = "INTERCEPTED" in up
            incomplete = "INCOMPLETE" in up
            if passer:
                if intercepted:
                    delta["pass_int"] = delta.get("pass_int", 0) + 1
                    bits.append("INT thrown")
                elif not incomplete:
                    y = _yards(s)
                    if y is not None:
                        delta["pass_yd"] = delta.get("pass_yd", 0) + y
                        tgt = re.search(r" to ([A-Z]\.[A-Za-z'\-]+(?:\.? [A-Z][a-z]+)?)", s)
                        who = f" to {tgt.group(1)}" if tgt else ""
                        if td:
                            delta["pass_td"] = delta.get("pass_td", 0) + 1
                            bits.append(f"{y}-yd TD pass{who}")
                        else:
                            bits.append(f"{y}-yd pass{who}")
            else:
                # receiver / target
                if incomplete or intercepted:
                    continue
                y = _yards(s)
                if y is not None and not re.search(r"intended for " + re.escape(key), s):
                    delta["rec"] = delta.get("rec", 0) + 1
                    delta["rec_yd"] = delta.get("rec_yd", 0) + y
                    if td:
                        delta["rec_td"] = delta.get("rec_td", 0) + 1
                        bits.append(f"{y}-yd catch, TD")
                    else:
                        bits.append(f"{y}-yd catch")
        elif _starts_with(s, key):
            # Rush (incl. scrambles, sneaks). Skip sacks/penalties.
            if "sacked" in s or "PENALTY" in up:
                continue
            y = _yards(s)
            if y is not None:
                delta["rush_att"] = delta.get("rush_att", 0) + 1
                delta["rush_yd"] = delta.get("rush_yd", 0) + y
                if td:
                    delta["rush_td"] = delta.get("rush_td", 0) + 1
                    bits.append(f"{y}-yd rush, TD")
                else:
                    bits.append(f"{y}-yd rush")

        # Fumbles (any sentence mentioning the player)
        if re.search(re.escape(key) + r"(?![A-Za-z]).*FUMBLES", s):
            rec = re.search(r"RECOVERED by ([A-Z]{2,3})-", s)
            lost = bool(rec) and rec.group(1) not in {team, ESPN_TEXT_ABBR.get(team or "", "")}
            if lost:
                delta["fum_lost"] = delta.get("fum_lost", 0) + 1
                bits.append("fumble lost")
            else:
                delta["fum"] = delta.get("fum", 0) + 1
                bits.append("fumble (recovered)")

    if not delta:
        return None
    return {"summary": ", ".join(dict.fromkeys(bits)) or "play", "delta": delta}


def play_points(delta: dict, scoring: dict | None, rec_value: float) -> float:
    sc = scoring if scoring else default_scoring(rec_value)
    return score_stat_line(delta, sc)
