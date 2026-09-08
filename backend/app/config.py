from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    sleeper_username: str | None = None

    espn_league_id: int | None = None
    espn_s2: str | None = None
    espn_swid: str | None = None
    espn_team_id: int | None = None

    yahoo_league_id: str | None = None
    yahoo_oauth_file: Path = Path("oauth2.json")

    season_override: int | None = None
    cache_dir: Path = BACKEND_DIR / ".cache"

    @field_validator("sleeper_username", "espn_league_id", "espn_s2", "espn_swid", "espn_team_id",
                     "yahoo_league_id", "season_override", mode="before")
    @classmethod
    def _blank_is_none(cls, v):
        return None if isinstance(v, str) and v.strip() == "" else v

    @property
    def yahoo_oauth_path(self) -> Path:
        p = self.yahoo_oauth_file
        return p if p.is_absolute() else BACKEND_DIR / p


settings = Settings()
