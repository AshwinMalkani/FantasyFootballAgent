from fastapi import APIRouter, HTTPException

from ..cache import clear_all
from ..models import LineupSuggestion, WaiverTarget
from ..providers.base import ProviderError
from ..providers.registry import get_provider
from ..services.players import reset_player_db
from ..services.projections import trending_adds
from ..services.recommendations import optimize_lineup, rank_waivers

router = APIRouter(prefix="/api")


@router.get("/leagues/{platform}/{league_id}/lineup", response_model=LineupSuggestion, response_model_by_alias=True)
def lineup(platform: str, league_id: str):
    try:
        d = get_provider(platform).detail(league_id)
    except ProviderError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "hint": e.hint})
    return optimize_lineup(d.roster, d.lineup_slots)


@router.get("/leagues/{platform}/{league_id}/waivers", response_model=list[WaiverTarget])
def waivers(platform: str, league_id: str, limit: int = 15):
    try:
        p = get_provider(platform)
        d = p.detail(league_id)
        fas = p.free_agents(league_id)
    except ProviderError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "hint": e.hint})
    return rank_waivers(fas, d.roster, trending_adds(), limit=limit, lineup_slots=d.lineup_slots)


@router.post("/refresh")
def refresh():
    n = clear_all()
    reset_player_db()
    return {"cleared": n}
