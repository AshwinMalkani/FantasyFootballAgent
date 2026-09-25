from contextlib import contextmanager
from typing import Protocol

from ..models import LeagueDetail, LeagueError, LeagueSummary, Platform, Player


class Provider(Protocol):
    platform: Platform

    def list_leagues(self) -> list[LeagueSummary | LeagueError]: ...
    def detail(self, league_id: str) -> LeagueDetail: ...
    def free_agents(self, league_id: str) -> list[Player]: ...


class ProviderError(Exception):
    def __init__(self, message: str, hint: str | None = None):
        super().__init__(message)
        self.hint = hint


LEAGUE_TTL = 10 * 60


@contextmanager
def upstream_errors(platform: str):
    """Turn provider failures into useful HTTP errors instead of a bare 500."""
    from fastapi import HTTPException
    try:
        yield
    except ProviderError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "hint": e.hint}) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail={
            "error": f"{platform} request failed: {type(e).__name__}: {e}",
            "hint": "Usually a temporary upstream error. Try Refresh in a moment.",
        }) from e
