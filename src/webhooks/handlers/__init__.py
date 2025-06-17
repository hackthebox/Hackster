from discord import Bot

from src.webhooks.handlers.account import AccountHandler
from src.webhooks.types import Platform, WebhookBody

handlers = {Platform.ACCOUNT: AccountHandler.handle}


def can_handle(platform: Platform) -> bool:
    return platform in handlers.keys()


def handle(body: WebhookBody, bot: Bot) -> any:
    platform = body.platform

    if not can_handle(platform):
        raise ValueError(f"Platform {platform} not implemented")

    return handlers[platform](body, bot)
