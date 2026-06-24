import os
import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _validate_discord_snowflake(value: int | str) -> int:
    if isinstance(value, int):
        discord_id = value
    elif isinstance(value, str) and value.isdigit():
        discord_id = int(value)
    else:
        raise ValueError("Discord IDs must be base-10 integer snowflakes.")

    if not 0 < discord_id < 2**64:
        raise ValueError("Discord IDs must be positive unsigned 64-bit snowflakes.")

    return discord_id


def _validate_non_zero_channel_id(value: int) -> int:
    if not value:
        return value
    if len(str(value)) <= 17:
        raise ValueError("Discord IDs must have a length of 19.")
    return value


class BotSettings(BaseModel):
    """Discord bot settings."""

    model_config = ConfigDict(extra="forbid")

    NAME: str = "Hackster"
    TOKEN: str
    ENVIRONMENT: str = "development"

    @field_validator("TOKEN")
    @classmethod
    def check_token_format(cls, value: str) -> str:
        """Validate Discord token format."""
        pattern = re.compile(r".{26}\..{6}\..{38}")
        if not pattern.fullmatch(value):
            raise ValueError(f"Discord token must follow >> {pattern.pattern} << pattern.")
        return value


class DatabaseSettings(BaseModel):
    """Database settings."""

    model_config = ConfigDict(extra="forbid")

    HOST: str = "localhost"
    PORT: int = 3306
    DATABASE: str = "bot"
    USER: str = "bot"
    PASSWORD: str = ""
    CHARSET: str = "utf8mb4"
    ASYNC: bool | None = None

    def assemble_db_connection(self) -> str:
        return (
            f"mariadb+asyncmy://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/"
            f"{self.DATABASE}?charset={self.CHARSET}"
        )


class ChannelsSettings(BaseModel):
    """Channel IDs."""

    model_config = ConfigDict(extra="forbid")

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
        """Validate Discord IDs format."""
        return _validate_non_zero_channel_id(value)


class RolesSettings(BaseModel):
    """Role settings.

    Core roles (required): used in decorators at import time for permission checks.
    Dynamic roles (optional): managed via DB, kept here as fallback during transition.
    """

    model_config = ConfigDict(extra="forbid")

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
    APRIL_ROLE_1: int | None = None
    APRIL_ROLE_2: int | None = None
    RANK_FIVE: int | None = None
    RANK_TWENTY_FIVE: int | None = None
    RANK_FIFTY: int | None = None
    RANK_HUNDRED: int | None = None
    RANK_ONE: int | None = None
    RANK_TEN: int | None = None
    ACADEMY_CBBH: int | None = None
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
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="forbid",
        populate_by_name=True,
    )

    bot: BotSettings = Field(validation_alias="BOT")
    database: DatabaseSettings = Field(validation_alias="DATABASE")
    channels: ChannelsSettings = Field(validation_alias="CHANNEL")
    roles: RolesSettings = Field(validation_alias="ROLE")

    HTB_API_KEY: str
    guild_ids: list[int]
    dev_guild_ids: list[int] = Field(default_factory=list)
    APRIL_FLAG_1: str = ""
    APRIL_FLAG_2: str = ""

    SENTRY_DSN: str | None = None
    LOG_LEVEL: str | int = "INFO"
    DEBUG: bool = False

    HTB_URL: str = "https://labs.hackthebox.com"
    HTB_API_SECRET: str | None = None

    START_WEBHOOK_SERVER: bool = False
    WEBHOOK_PORT: int = 1337
    WEBHOOK_TOKEN: str = ""

    SLACK_FEEDBACK_WEBHOOK: str = ""
    SLACK_WEBHOOK: str = ""
    JIRA_WEBHOOK: str = ""
    JIRA_SPOILER_WEBHOOK: str = ""

    # Feedback service ingest (POST /api/ingest/discord)
    FEEDBACK_SERVICE_URL: str = ""
    FEEDBACK_SERVICE_API_KEY: str = ""

    ROOT: Path | None = None
    VERSION: str = "unknown"
    SEASON_ID: int = 0

    @field_validator("guild_ids", "dev_guild_ids", mode="before")
    @classmethod
    def check_ids_format(cls, value: list[int | str] | int | str) -> list[int | str] | int:
        """Validate Discord snowflakes and accept string-form IDs from env sources."""
        if isinstance(value, list):
            return [_validate_discord_snowflake(item) for item in value]
        return _validate_discord_snowflake(value)

    @property
    def API_URL(self) -> str:
        return f"{self.HTB_URL}/api"

    @property
    def API_V4_URL(self) -> str:
        return f"{self.API_URL}/v4"

    @property
    def role_groups(self) -> dict[str, list[int]]:
        return {
            "ALL_ADMINS": [
                self.roles.ADMINISTRATOR,
                self.roles.COMMUNITY_MANAGER,
            ],
            "ALL_SR_MODS": [self.roles.SR_MODERATOR],
            "ALL_MODS": [
                self.roles.SR_MODERATOR,
                self.roles.MODERATOR,
                self.roles.JR_MODERATOR,
            ],
            "ALL_HTB_STAFF": [self.roles.HTB_STAFF],
            "ALL_HTB_SUPPORT": [self.roles.HTB_SUPPORT],
        }


settings = Global(
    _env_file=os.environ.get("ENV_PATH") if os.environ.get("BOT_ENVIRONMENT") else ".test.env"
)
