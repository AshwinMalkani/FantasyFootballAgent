"""Builds the configured providers and fans out across them."""
from concurrent.futures import ThreadPoolExecutor

from ..config import settings
from ..models import LeagueError, LeagueSummary, NflState
from ..services.players import player_db
from ..services.projections import nfl_state, weekly_projections
from .base import Provider, ProviderError


def current_state() -> NflState:
    st = nfl_state()
    if settings.season_override:
        st = NflState(season=settings.season_override, week=st.week, season_type=st.season_type)
    return st


def build_providers() -> dict[str, Provider]:
    state = current_state()
    db = player_db()
    proj = weekly_projections(state.season, state.week)
    out: dict[str, Provider] = {}
    if settings.sleeper_username:
        from .sleeper import SleeperProvider
        out["sleeper"] = SleeperProvider(settings.sleeper_username, state, db, proj)
    if settings.espn_league_id and settings.espn_s2 and settings.espn_swid:
        from .espn import EspnProvider
        out["espn"] = EspnProvider(settings.espn_league_id, settings.espn_s2, settings.espn_swid,
                                   settings.espn_team_id, state, db, proj)
    if settings.yahoo_oauth_path.exists() or settings.yahoo_league_id:
        from .yahoo import YahooProvider
        out["yahoo"] = YahooProvider(settings.yahoo_oauth_path, settings.yahoo_league_id, state, db, proj)
    return out


def get_provider(platform: str) -> Provider:
    providers = build_providers()
    if platform not in providers:
        raise ProviderError(f"{platform} is not configured", f"Add the {platform} settings to backend/.env")
    return providers[platform]


def all_leagues() -> list[LeagueSummary | LeagueError]:
    providers = build_providers()
    results: list[LeagueSummary | LeagueError] = []
    order = ["sleeper", "espn", "yahoo"]

    def run(name: str):
        try:
            return providers[name].list_leagues()
        except Exception as e:
            return [LeagueError(platform=name, error=str(e), hint=getattr(e, "hint", None))]

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {n: ex.submit(run, n) for n in order if n in providers}
        for n in order:
            if n in futures:
                results.extend(futures[n].result())
    for n in order:
        if n not in providers:
            results.append(LeagueError(platform=n, error=f"{n} not configured", hint=f"Add {n} credentials to backend/.env"))
    return results
