from discord import Bot
from typing import Any

from src.webhooks.handlers.account import AccountHandler
from src.webhooks.handlers.academy import AcademyHandler
from src.webhooks.handlers.mp import MPHandler
from src.webhooks.types import Platform, WebhookBody

handlers = {
    Platform.ACCOUNT: AccountHandler().handle,
    Platform.MAIN: MPHandler().handle,
    Platform.ACADEMY: AcademyHandler().handle,
}


def can_handle(platform: Platform) -> bool:
    return platform in handlers.keys()


def handle(body: WebhookBody, bot: Bot) -> Any:
    platform = body.platform

    if not can_handle(platform):
        raise ValueError(f"Platform {platform} not implemented")

    return handlers[platform](body, bot)
