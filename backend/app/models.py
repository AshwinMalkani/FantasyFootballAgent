from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Platform = Literal["sleeper", "espn", "yahoo"]
ProjectionSource = Literal["espn", "sleeper-exact", "sleeper-approx", "none"]

# Canonical slot names (Sleeper's vocabulary). Providers normalize to these.
BENCH_SLOTS = {"BN", "IR", "TAXI"}


class Player(BaseModel):
    sleeper_id: str | None = None
    platform_player_id: str
    name: str
    position: str
    nfl_team: str | None = None
    injury_status: str | None = None
    on_bye: bool = False
    opponent: str | None = None
    projected_points: float = 0.0
    projection_source: ProjectionSource = "none"
    actual_points: float | None = None      # None until the player's game has started
    game_state: Literal["pre", "in", "post"] | None = None


class RosterSlot(BaseModel):
    slot: str
    player: Player | None = None


class LeagueSummary(BaseModel):
    platform: Platform
    league_id: str
    name: str
    season: int
    week: int
    team_name: str
    record: str
    rank: int | None = None
    total_teams: int | None = None
    points_for: float | None = None
    opponent_name: str | None = None
    my_projected_total: float | None = None
    opp_projected_total: float | None = None
    my_actual_total: float | None = None
    opp_actual_total: float | None = None
    in_progress: bool = False
    waiver_type: str | None = None
    faab_remaining: int | None = None
    waiver_priority: int | None = None
    scoring_label: str | None = None
    url: str | None = None


class LeagueError(BaseModel):
    platform: Platform
    league_id: str | None = None
    name: str | None = None
    error: str
    hint: str | None = None


class LeagueDetail(BaseModel):
    summary: LeagueSummary
    roster: list[RosterSlot]
    lineup_slots: list[str]
    scoring: dict[str, float] = {}
    opponent_roster: list[RosterSlot] | None = None   # this week's opponent, starters + bench when available


class LineupMove(BaseModel):
    slot: str
    out: Player | None
    in_: Player = Field(alias="in")
    delta: float

    model_config = ConfigDict(populate_by_name=True)


class LineupSuggestion(BaseModel):
    current_starters: list[RosterSlot]
    suggested_starters: list[RosterSlot]
    moves: list[LineupMove]
    current_total: float
    suggested_total: float
    projected_gain: float
    flags: list[str] = []


class WaiverTarget(BaseModel):
    player: Player
    score: float
    trending_adds: int = 0
    lineup_gain: float = 0.0
    suggested_drop: Player | None = None
    net_gain: float | None = None


class NflState(BaseModel):
    season: int
    week: int
    season_type: str
