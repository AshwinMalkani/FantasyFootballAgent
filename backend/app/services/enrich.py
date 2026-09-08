"""Build normalized Player objects with this week's projection attached."""
from ..models import Player, ProjectionSource
from .players import PlayerDB, norm_team
from .scoring import approx_points, score_stat_line


def build_player(
    db: PlayerDB,
    *,
    sleeper_id: str | None,
    platform_player_id: str,
    name: str,
    position: str,
    nfl_team: str | None,
    injury_status: str | None,
    projections: dict[str, dict],
    teams_playing: set[str],
    scoring: dict[str, float] | None = None,
    rec_value: float | None = None,
    platform_points: float | None = None,
) -> Player:
    nfl_team = norm_team(nfl_team)
    proj = projections.get(sleeper_id) if sleeper_id else None
    on_bye = bool(nfl_team) and nfl_team not in teams_playing and bool(teams_playing)

    points = 0.0
    source: ProjectionSource = "none"
    if platform_points is not None:
        points, source = round(float(platform_points), 2), "espn"
    elif proj and scoring:
        points, source = score_stat_line(proj["stats"], scoring), "sleeper-exact"
    elif proj:
        points, source = approx_points(proj["stats"], rec_value if rec_value is not None else 0.5), "sleeper-approx"

    return Player(
        sleeper_id=sleeper_id,
        platform_player_id=str(platform_player_id),
        name=name,
        position=position,
        nfl_team=nfl_team,
        injury_status=injury_status or None,
        on_bye=on_bye,
        opponent=(proj or {}).get("opponent"),
        projected_points=points,
        projection_source=source,
    )
