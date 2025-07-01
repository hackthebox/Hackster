from enum import Enum

from pydantic import BaseModel, ConfigDict, Extra, Field


class WebhookEvent(Enum):
    ACCOUNT_LINKED = "DiscordAccountLinked"
    ACCOUNT_UNLINKED = "DiscordAccountUnlinked"
    ACCOUNT_DELETED = "UserAccountDeleted"
    ACCOUNT_BANNED = "UserAccountBanned"
    CERTIFICATE_AWARDED = "CertificateAwarded"
    RANK_UP = "RankUp"
    HOF_CHANGE = "HofChange"
    SUBSCRIPTION_CHANGE = "SubscriptionChange"
    CONTENT_RELEASED = "ContentReleased"
    NAME_CHANGE = "NameChange"
    SEASON_RANK_CHANGE = "SeasonRankChange"
    PROLAB_COMPLETED = "ProlabCompleted"


class Platform(Enum):
    MAIN = "mp"
    ACADEMY = "academy"
    CTF = "ctf"
    ENTERPRISE = "enterprise"
    ACCOUNT = "account"


class WebhookBody(BaseModel):
    model_config = ConfigDict(extra=Extra.allow)

    platform: Platform
    event: WebhookEvent
    properties: dict = Field(default_factory=dict)
    traits: dict = Field(default_factory=dict)
