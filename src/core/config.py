import os
import re
from pathlib import Path
from typing import Any, Optional

import toml
from pydantic import BaseSettings, validator


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

    @validator("DEVLOG", "SR_MOD", "VERIFY_LOGS", "BOT_COMMANDS", "SPOILER", "BOT_LOGS")
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


class AcademyCertificates(BaseSettings):
    CERTIFIED_BUG_BOUNTY_HUNTER = 2
    CERTIFIED_PENETRATION_TESTING_SPECIALIST = 3
    CERTIFIED_DEFENSIVE_SECURITY_ANALYST = 4
    CERTIFIED_WEB_EXPLOITATION_EXPERT = 5
    CERTIFIED_ACTIVEDIRECTORY_PENTESTING_EXPERT = 6


class Roles(BaseSettings):
    """The roles settings."""

    # Moderation
    COMMUNITY_MANAGER: int
    COMMUNITY_TEAM: int
    ADMINISTRATOR: int
    SR_MODERATOR: int
    MODERATOR: int
    JR_MODERATOR: int
    HTB_STAFF: int
    HTB_SUPPORT: int
    MUTED: int

    # Ranks
    OMNISCIENT: int
    GURU: int
    ELITE_HACKER: int
    PRO_HACKER: int
    HACKER: int
    SCRIPT_KIDDIE: int
    NOOB: int
    VIP: int
    VIP_PLUS: int

    # Content Creation
    CHALLENGE_CREATOR: int
    BOX_CREATOR: int

    # Positions
    RANK_ONE: int
    RANK_TEN: int

    # Season Tiers:
    SEASON_HOLO: int
    SEASON_PLATINUM: int
    SEASON_RUBY: int
    SEASON_SILVER: int
    SEASON_BRONZE: int
    # Academy
    ACADEMY_USER: int
    ACADEMY_CBBH: int
    ACADEMY_CPTS: int
    ACADEMY_CDSA: int
    ACADEMY_CWEE: int
    ACADEMY_CAPE: int
    # Joinable roles
    UNICTF2022: int
    BIZCTF2022: int
    NOAH_GANG: int
    BUDDY_GANG: int
    RED_TEAM: int
    BLUE_TEAM: int
    @validator("*", pre=True, each_item=True)
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

    # Collections are defined using lowercase
    academy_certificates: AcademyCertificates = AcademyCertificates()

    roles_to_join: dict[str, tuple[int | str, str]] = {}
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

    def get_academy_cert_role(self, certificate: int) -> int:
        return {
            self.academy_certificates.CERTIFIED_BUG_BOUNTY_HUNTER: self.roles.ACADEMY_CBBH,
            self.academy_certificates.CERTIFIED_PENETRATION_TESTING_SPECIALIST: self.roles.ACADEMY_CPTS,
            self.academy_certificates.CERTIFIED_DEFENSIVE_SECURITY_ANALYST: self.roles.ACADEMY_CDSA,
            self.academy_certificates.CERTIFIED_WEB_EXPLOITATION_EXPERT: self.roles.ACADEMY_CWEE,
            self.academy_certificates.CERTIFIED_ACTIVEDIRECTORY_PENTESTING_EXPERT: self.roles.ACADEMY_CAPE
        }.get(certificate)

    def get_post_or_rank(self, what: str) -> Optional[int]:
        return {
            "1": self.roles.RANK_ONE,
            "10": self.roles.RANK_TEN,
            "Omniscient": self.roles.OMNISCIENT,
            "Guru": self.roles.GURU,
            "Elite Hacker": self.roles.ELITE_HACKER,
            "Pro Hacker": self.roles.PRO_HACKER,
            "Hacker": self.roles.HACKER,
            "Script Kiddie": self.roles.SCRIPT_KIDDIE,
            "Noob": self.roles.NOOB,
            "vip": self.roles.VIP,
            "dedivip": self.roles.VIP_PLUS,
            "Challenge Creator": self.roles.CHALLENGE_CREATOR,
            "Box Creator": self.roles.BOX_CREATOR,
        }.get(what)

    def get_season(self, what: str):
        return {
            "Holo": self.roles.SEASON_HOLO,
            "Platinum": self.roles.SEASON_PLATINUM,
            "Ruby": self.roles.SEASON_RUBY,
            "Silver": self.roles.SEASON_SILVER,
            "Bronze": self.roles.SEASON_BRONZE,
        }.get(what)

    def get_cert(self, what: str):
        return {
            "CPTS": self.roles.ACADEMY_CPTS,
            "CBBH": self.roles.ACADEMY_CBBH,
            "CDSA": self.roles.ACADEMY_CDSA,
            "CWEE": self.roles.ACADEMY_CWEE,
            "CAPE": self.roles.ACADEMY_CAPE
        }.get(what)

    class Config:
        """The Pydantic settings configuration."""

        env_file = ".env"


def load_settings(env_file: str | None = None):
    global_settings = Global(_env_file=env_file)
    global_settings.bot = Bot(_env_file=env_file)
    global_settings.database = Database(_env_file=env_file)
    global_settings.channels = Channels(_env_file=env_file)
    global_settings.roles = Roles(_env_file=env_file)

    global_settings.roles_to_join = {
        "Cyber Apocalypse": (
            global_settings.roles.UNICTF2022,
            "Pinged for CTF Announcements",
        ),
        "Business CTF": (
            global_settings.roles.UNICTF2022,
            "Pinged for CTF Announcements",
        ),
        "University CTF": (
            global_settings.roles.UNICTF2022,
            "Pinged for CTF Announcements",
        ),
        "Noah Gang": (
            global_settings.roles.NOAH_GANG,
            "Get pinged when Fugl posts pictures of his cute bird",
        ),
        "Buddy Gang": (
            global_settings.roles.BUDDY_GANG,
            "Get pinged when Legacyy posts pictures of his cute dog",
        ),
        "Red Team": (
            global_settings.roles.RED_TEAM,
            "Red team fans. Also gives access to the Red and Blue team channels",
        ),
        "Blue Team": (
            global_settings.roles.BLUE_TEAM,
            "Blue team fans. Also gives access to the Red and Blue team channels",
        ),
    }

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
        "ALL_RANKS": [
            global_settings.roles.OMNISCIENT,
            global_settings.roles.GURU,
            global_settings.roles.ELITE_HACKER,
            global_settings.roles.PRO_HACKER,
            global_settings.roles.HACKER,
            global_settings.roles.SCRIPT_KIDDIE,
            global_settings.roles.NOOB,
            global_settings.roles.VIP,
            global_settings.roles.VIP_PLUS,
            global_settings.roles.SEASON_HOLO,
            global_settings.roles.SEASON_PLATINUM,
            global_settings.roles.SEASON_RUBY,
            global_settings.roles.SEASON_SILVER,
            global_settings.roles.SEASON_BRONZE,
        ],
        "ALL_CREATORS": [
            global_settings.roles.BOX_CREATOR,
            global_settings.roles.CHALLENGE_CREATOR,
        ],
        "ALL_POSITIONS": [
            global_settings.roles.RANK_ONE,
            global_settings.roles.RANK_TEN,
        ],
    }

    return global_settings


settings = load_settings(
    os.environ.get("ENV_PATH") if os.environ.get("BOT_ENVIRONMENT") else ".test.env"
)
