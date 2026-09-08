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
