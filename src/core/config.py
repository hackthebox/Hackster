import os
import re
from pathlib import Path
from typing import Any, Optional

import toml
from pydantic import BaseSettings, validator

# AcademyCertificates is removed; cert mappings are now in the dynamic_role DB table.


class Bot(BaseSettings):
    """The API settings."""

    NAME: str = "Hackster"
    TOKEN: str
    ENVIRONMENT: str = "development"

    @validator("TOKEN")
    def check_token_format(cls, v: str) -> str:
        """Validate discord tokens format."""
        pattern = re.compile(r".{26}\..{6}\..{38}")
        assert pattern.fullmatch(
            v
        ), f"Discord token must follow >> {pattern.pattern} << pattern."
        return v

    class Config:
        """The Pydantic settings configuration."""

        env_file = ".env"
        env_prefix = "BOT_"


class Database(BaseSettings):
    """The database settings."""

    HOST: str = "localhost"
    PORT: int = 3306
    DATABASE: str = "bot"
    USER: str = "bot"
    PASSWORD: str = ""
    CHARSET: str = "utf8mb4"

    def assemble_db_connection(self) -> str:
        connection_string = (
            f"mariadb+asyncmy://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/"
            f"{self.DATABASE}?charset="
            f"{self.CHARSET}"
        )
        return connection_string

    class Config:
        """The Pydantic settings configuration."""

        env_file = ".env"
        env_prefix = "MYSQL_"


class Channels(BaseSettings):
    """Channel ids."""

    DEVLOG: int = 0
    SR_MOD: int
    VERIFY_LOGS: int
    BOT_COMMANDS: int
    SPOILER: int
    BOT_LOGS: int
    UNVERIFIED_BOT_COMMANDS: int = 0
    HOW_TO_VERIFY: int = 0

    @validator(
        "DEVLOG", "SR_MOD", "VERIFY_LOGS", "BOT_COMMANDS", "SPOILER", "BOT_LOGS",
        "UNVERIFIED_BOT_COMMANDS", "HOW_TO_VERIFY",
    )
    def check_ids_format(cls, v: list[int]) -> list[int]:
        """Validate discord ids format."""
        if not v:
            return v

        assert len(str(v)) > 17, "Discord ids must have a length of 19."
        return v

    class Config:
        """The Pydantic settings configuration."""

        env_file = ".env"
        env_prefix = "CHANNEL_"


class Roles(BaseSettings):
    """The roles settings.

    Core roles (required): used in decorators at import time for permission checks.
    Dynamic roles (optional): managed via DB, kept here as fallback during transition.
    """
    # ── Core roles (required, used in decorators) ────────────────────
    VERIFIED: int
    COMMUNITY_MANAGER: int
    COMMUNITY_TEAM: int
    ADMINISTRATOR: int
    SR_MODERATOR: int
    MODERATOR: int
    JR_MODERATOR: int
    HTB_STAFF: int
    HTB_SUPPORT: int
    MUTED: int
    ACADEMY_USER: int

    # ── Dynamic roles (optional, DB-backed, env var fallback) ────────
    # Ranks
    OMNISCIENT: Optional[int] = None
    GURU: Optional[int] = None
    ELITE_HACKER: Optional[int] = None
    PRO_HACKER: Optional[int] = None
    HACKER: Optional[int] = None
    SCRIPT_KIDDIE: Optional[int] = None
    NOOB: Optional[int] = None
    # Subscriptions
    VIP: Optional[int] = None
    VIP_PLUS: Optional[int] = None
    SILVER_ANNUAL: Optional[int] = None
    GOLD_ANNUAL: Optional[int] = None
    # Content Creation
    CHALLENGE_CREATOR: Optional[int] = None
    BOX_CREATOR: Optional[int] = None
    SHERLOCK_CREATOR: Optional[int] = None
    # Positions
    RANK_ONE: Optional[int] = None
    RANK_TEN: Optional[int] = None
    # Season Tiers
    SEASON_HOLO: Optional[int] = None
    SEASON_PLATINUM: Optional[int] = None
    SEASON_RUBY: Optional[int] = None
    SEASON_SILVER: Optional[int] = None
    SEASON_BRONZE: Optional[int] = None
    # Academy Certs
    ACADEMY_CWES: Optional[int] = None
    ACADEMY_CPTS: Optional[int] = None
    ACADEMY_CDSA: Optional[int] = None
    ACADEMY_CWEE: Optional[int] = None
    ACADEMY_CAPE: Optional[int] = None
    ACADEMY_CJCA: Optional[int] = None
    ACADEMY_CWPE: Optional[int] = None
    # Joinable roles
    UNICTF2022: Optional[int] = None
    BIZCTF2022: Optional[int] = None
    NOAH_GANG: Optional[int] = None
    BUDDY_GANG: Optional[int] = None
    RED_TEAM: Optional[int] = None
    BLUE_TEAM: Optional[int] = None

    @validator("VERIFIED", "COMMUNITY_MANAGER", "COMMUNITY_TEAM", "ADMINISTRATOR",
               "SR_MODERATOR", "MODERATOR", "JR_MODERATOR", "HTB_STAFF", "HTB_SUPPORT",
               "MUTED", "ACADEMY_USER", pre=True, each_item=True)
    def check_length(cls, value: str | int) -> str | int:
        value_str = str(value)
        if not 17 <= len(value_str) <= 20:
            raise ValueError("Each role ID must be between 18 & 19 characters long")
        return value

    class Config:
        """The Pydantic settings configuration."""

        env_file = ".env"
        env_prefix = "ROLE_"


class Global(BaseSettings):
    """The app settings."""

    bot: Bot = None
    database: Database = None
    channels: Channels = None
    roles: Roles = None
    HTB_API_KEY: str

    role_groups: dict[str, list[int | str]] = {}

    guild_ids: list[int]
    dev_guild_ids: list[int] = []

    SENTRY_DSN: str | None = None
    LOG_LEVEL: str | int = "INFO"
    DEBUG: bool = False

    HTB_URL: str = "https://labs.hackthebox.com"
    API_URL: str = f"{HTB_URL}/api"
    API_V4_URL: str = f"{API_URL}/v4"
    HTB_API_SECRET: str | None = None

    START_WEBHOOK_SERVER: bool = False
    WEBHOOK_PORT: int = 1337
    WEBHOOK_TOKEN: str = ""

    SLACK_FEEDBACK_WEBHOOK: str = ""
    JIRA_WEBHOOK: str = ""

    ROOT: Path = None

    VERSION: str | None = None

    SEASON_ID: int = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @validator("VERSION")
    @classmethod
    def get_project_versions(cls, v: Optional[str], values: dict[str, Any]) -> str:
        def _get_from_pyproject():
            with open("pyproject.toml", "r") as f:
                config = toml.load(f)
                version = config.get("tool", {}).get("poetry", {}).get("version")
                return version

        if not v:
            return values.get("VERSION", _get_from_pyproject())
        return v

    @validator("guild_ids", "dev_guild_ids")
    def check_ids_format(cls, v: list[int]) -> list[int]:
        """Validate discord ids format."""
        for discord_id in v:
            assert len(str(discord_id)) > 17, "Discord ids must have a length of 19."
        return v

    # Helper methods (get_post_or_rank, get_season, get_cert, get_academy_cert_role)
    # have been moved to RoleManager (src/services/role_manager.py).

    class Config:
        """The Pydantic settings configuration."""

        env_file = ".env"


def load_settings(env_file: str | None = None):
    global_settings = Global(_env_file=env_file)
    global_settings.bot = Bot(_env_file=env_file)
    global_settings.database = Database(_env_file=env_file)
    global_settings.channels = Channels(_env_file=env_file)
    global_settings.roles = Roles(_env_file=env_file)

    # Core role groups (used in decorators at import time for permission checks).
    # Dynamic role groups (ALL_RANKS, ALL_SEASON_RANKS, etc.) are now served by
    # RoleManager.get_group_ids() from the database.
    global_settings.role_groups = {
        "ALL_ADMINS": [
            global_settings.roles.ADMINISTRATOR,
            global_settings.roles.COMMUNITY_MANAGER,
        ],
        "ALL_SR_MODS": [global_settings.roles.SR_MODERATOR],
        "ALL_MODS": [
            global_settings.roles.SR_MODERATOR,
            global_settings.roles.MODERATOR,
            global_settings.roles.JR_MODERATOR,
        ],
        "ALL_HTB_STAFF": [global_settings.roles.HTB_STAFF],
        "ALL_HTB_SUPPORT": [global_settings.roles.HTB_SUPPORT],
    }

    return global_settings


settings = load_settings(
    os.environ.get("ENV_PATH") if os.environ.get("BOT_ENVIRONMENT") else ".test.env"
)
