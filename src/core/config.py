import os
import re
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# AcademyCertificates is removed; cert mappings are now in the dynamic_role DB table.


class Bot(BaseSettings):
    """The API settings."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="BOT_", extra="ignore")

    NAME: str = "Hackster"
    TOKEN: str
    ENVIRONMENT: str = "development"

    @field_validator("TOKEN")
    @classmethod
    def check_token_format(cls, value: str) -> str:
        """Validate discord tokens format."""
        pattern = re.compile(r".{26}\..{6}\..{38}")
        assert pattern.fullmatch(
            value
        ), f"Discord token must follow >> {pattern.pattern} << pattern."
        return value


class Database(BaseSettings):
    """The database settings."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="MYSQL_", extra="ignore")

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


class Channels(BaseSettings):
    """Channel ids."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="CHANNEL_", extra="ignore")

    DEVLOG: int = 0
    SR_MOD: int
    VERIFY_LOGS: int
    BOT_COMMANDS: int
    SPOILER: int
    BOT_LOGS: int
    UNVERIFIED_BOT_COMMANDS: int = 0
    HOW_TO_VERIFY: int = 0

    @field_validator(
        "DEVLOG",
        "SR_MOD",
        "VERIFY_LOGS",
        "BOT_COMMANDS",
        "SPOILER",
        "BOT_LOGS",
        "UNVERIFIED_BOT_COMMANDS",
        "HOW_TO_VERIFY",
    )
    @classmethod
    def check_ids_format(cls, value: int) -> int:
        """Validate discord ids format."""
        if not value:
            return value

        assert len(str(value)) > 17, "Discord ids must have a length of 19."
        return value


class Roles(BaseSettings):
    """The roles settings.

    Core roles (required): used in decorators at import time for permission checks.
    Dynamic roles (optional): managed via DB, kept here as fallback during transition.
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ROLE_", extra="ignore")

    # Core roles (required, used in decorators)
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

    # Dynamic roles (optional, DB-backed, env var fallback)
    OMNISCIENT: int | None = None
    GURU: int | None = None
    ELITE_HACKER: int | None = None
    PRO_HACKER: int | None = None
    HACKER: int | None = None
    SCRIPT_KIDDIE: int | None = None
    NOOB: int | None = None
    VIP: int | None = None
    VIP_PLUS: int | None = None
    SILVER_ANNUAL: int | None = None
    GOLD_ANNUAL: int | None = None
    CHALLENGE_CREATOR: int | None = None
    BOX_CREATOR: int | None = None
    SHERLOCK_CREATOR: int | None = None
    RANK_ONE: int | None = None
    RANK_TEN: int | None = None
    SEASON_HOLO: int | None = None
    SEASON_PLATINUM: int | None = None
    SEASON_RUBY: int | None = None
    SEASON_SILVER: int | None = None
    SEASON_BRONZE: int | None = None
    ACADEMY_CWES: int | None = None
    ACADEMY_CPTS: int | None = None
    ACADEMY_CDSA: int | None = None
    ACADEMY_CWEE: int | None = None
    ACADEMY_CAPE: int | None = None
    ACADEMY_CJCA: int | None = None
    ACADEMY_CWPE: int | None = None
    ACADEMY_COAE: int | None = None
    UNICTF2022: int | None = None
    BIZCTF2022: int | None = None
    NOAH_GANG: int | None = None
    BUDDY_GANG: int | None = None
    RED_TEAM: int | None = None
    BLUE_TEAM: int | None = None

    @field_validator(
        "VERIFIED",
        "COMMUNITY_MANAGER",
        "COMMUNITY_TEAM",
        "ADMINISTRATOR",
        "SR_MODERATOR",
        "MODERATOR",
        "JR_MODERATOR",
        "HTB_STAFF",
        "HTB_SUPPORT",
        "MUTED",
        "ACADEMY_USER",
        mode="before",
    )
    @classmethod
    def check_length(cls, value: str | int) -> str | int:
        value_str = str(value)
        if not 17 <= len(value_str) <= 20:
            raise ValueError("Each role ID must be between 18 & 19 characters long")
        return value


class Global(BaseSettings):
    """The app settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot: Bot | None = None
    database: Database | None = None
    channels: Channels | None = None
    roles: Roles | None = None
    HTB_API_KEY: str

    role_groups: dict[str, list[int | str]] = Field(default_factory=dict)

    guild_ids: list[int]
    dev_guild_ids: list[int] = Field(default_factory=list)

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

    ROOT: Path | None = None

    VERSION: str = "unknown"

    SEASON_ID: int = 0

    @field_validator("guild_ids", "dev_guild_ids", mode="before")
    @classmethod
    def check_ids_format(cls, value: list[int | str] | int | str) -> list[int | str] | int:
        """Validate Discord snowflakes and accept string-form IDs from env sources."""
        if isinstance(value, list):
            return [cls._validate_discord_id(item) for item in value]
        return cls._validate_discord_id(value)

    @staticmethod
    def _validate_discord_id(value: int | str) -> int:
        if isinstance(value, int):
            discord_id = value
        elif isinstance(value, str) and value.isdigit():
            discord_id = int(value)
        else:
            raise ValueError("Discord IDs must be base-10 integer snowflakes.")

        if not 0 < discord_id < 2**64:
            raise ValueError("Discord IDs must be positive unsigned 64-bit snowflakes.")

        return discord_id

    # Helper methods (get_post_or_rank, get_season, get_cert, get_academy_cert_role)
    # have been moved to RoleManager (src/services/role_manager.py).


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
