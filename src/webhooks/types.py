from enum import Enum

from pydantic import BaseModel


class WebhookEvent(Enum):
    """Enumeration representing different webhook events."""

    ACCOUNT_LINKED = "AccountLinked"
    ACCOUNT_UNLINKED = "AccountUnlinked"
    CERTIFICATE_AWARDED = "CertificateAwarded"
    RANK_UP = "RankUp"
    HOF_CHANGE = "HofChange"
    SUBSCRIPTION_CHANGE = "SubscriptionChange"
    CONTENT_RELEASED = "ContentReleased"
    NAME_CHANGE = "NameChange"


class Platform(Enum):
    """Enumeration representing different platforms."""

    MAIN = "mp"
    ACADEMY = "academy"
    CTF = "ctf"
    ENTERPRISE = "enterprise"


class WebhookBody(BaseModel):
    """Model representing the webhook body."""

    platform: Platform
    event: WebhookEvent
    data: dict
