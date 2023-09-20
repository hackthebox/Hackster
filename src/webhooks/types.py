from enum import Enum

from pydantic import BaseModel


class WebhookEvent(Enum):
    ACCOUNT_LINKED = "AccountLinked"
    ACCOUNT_UNLINKED = "AccountUnlinked"
    CERTIFICATE_AWARDED = "CertificateAwarded"
    RANK_UP = "RankUp"
    HOF_CHANGE = "HofChange"
    SUBSCRIPTION_CHANGE = "SubscriptionChange"
    CONTENT_RELEASED = "ContentReleased"
    NAME_CHANGE = "NameChange"
    PROLAB_RESET = "ProlabReset"


class Platform(Enum):
    MAIN = "mp"
    ACADEMY = "academy"
    CTF = "ctf"
    ENTERPRISE = "enterprise"
    MIDNA = "midna"


class WebhookBody(BaseModel):
    platform: Platform
    event: WebhookEvent
    data: dict
