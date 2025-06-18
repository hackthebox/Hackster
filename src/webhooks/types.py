from enum import Enum

from pydantic import BaseModel, ConfigDict


class WebhookEvent(Enum):
    ACCOUNT_LINKED = "DiscordAccountLinked"
    ACCOUNT_UNLINKED = "DiscordAccountUnlinked"
    ACCOUNT_DELETED = "UserAccountDeleted"
    CERTIFICATE_AWARDED = "CertificateAwarded"
    RANK_UP = "RankUp"
    HOF_CHANGE = "HofChange"
    SUBSCRIPTION_CHANGE = "SubscriptionChange"
    CONTENT_RELEASED = "ContentReleased"
    NAME_CHANGE = "NameChange"


class Platform(Enum):
    MAIN = "mp"
    ACADEMY = "academy"
    CTF = "ctf"
    ENTERPRISE = "enterprise"
    ACCOUNT = "account"


class WebhookBody(BaseModel):
    model_config = ConfigDict(extra="allow")

    platform: Platform
    event: WebhookEvent
    properties: dict | None
    traits: dict | None
