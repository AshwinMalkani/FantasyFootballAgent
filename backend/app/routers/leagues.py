from fastapi import APIRouter

from ..models import LeagueDetail, LeagueError, LeagueSummary, NflState
from ..providers.base import upstream_errors
from ..providers.registry import all_leagues, current_state, get_provider

router = APIRouter(prefix="/api")


@router.get("/state", response_model=NflState)
def state():
    return current_state()


@router.get("/leagues", response_model=list[LeagueSummary | LeagueError])
def leagues():
    return all_leagues()


@router.get("/leagues/{platform}/{league_id}", response_model=LeagueDetail)
def league_detail(platform: str, league_id: str):
    with upstream_errors(platform):
        return get_provider(platform).detail(league_id)
