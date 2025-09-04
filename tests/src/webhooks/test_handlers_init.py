from unittest import mock
from typing import Callable

import pytest

from src.webhooks.handlers import handlers, can_handle, handle
from src.webhooks.types import Platform, WebhookBody, WebhookEvent
from tests.conftest import bot

class TestHandlersInit:
    def test_handler_init(self):
        assert handlers is not None
        assert isinstance(handlers, dict)
        assert len(handlers) > 0
        assert all(isinstance(handler, Callable) for handler in handlers.values())

    def test_can_handle_unknown_platform(self):
        assert not can_handle("UNKNOWN")

    def test_can_handle_success(self):
        with mock.patch("src.webhooks.handlers.handlers", {Platform.MAIN: lambda x, y: True}):
            assert can_handle(Platform.MAIN)

    def test_handle_success(self):
        with mock.patch("src.webhooks.handlers.handlers", {Platform.MAIN: lambda x, y: 1337}):
            assert handle(WebhookBody(platform=Platform.MAIN, event=WebhookEvent.ACCOUNT_LINKED, properties={}, traits={}), bot) == 1337
        
    def test_handle_unknown_platform(self):
        with pytest.raises(ValueError):
            handle(WebhookBody(platform="UNKNOWN", event=WebhookEvent.ACCOUNT_LINKED, properties={}, traits={}), bot)

    def test_handle_unknown_event(self):
        with mock.patch("src.webhooks.handlers.handlers", {Platform.MAIN: lambda x, y: 1337}):
            with pytest.raises(ValueError):
                handle(WebhookBody(platform=Platform.MAIN, event="UNKNOWN", properties={}, traits={}), bot)