from fastapi import APIRouter

from ..services.activity import build_activity

router = APIRouter(prefix="/api")


@router.get("/activity")
def activity(bench: bool = False, season: int | None = None, week: int | None = None, date: str | None = None):
    """Game-day view. `season`/`week`/`date` (YYYYMMDD) are for testing against past weeks."""
    return build_activity(include_bench=bench, season=season, week=week, date=date)
