import asyncio
import signal
from unittest.mock import AsyncMock, patch

import pytest

from src.webhooks import server


@pytest.mark.asyncio
@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
async def test_signal_drains_webhooks_then_closes_the_bot(monkeypatch, sig):
    signal_handlers = {}
    monkeypatch.setattr(
        asyncio.get_running_loop(), "add_signal_handler", lambda s, callback: signal_handlers.__setitem__(s, callback)
    )
    calls = []

    async def fake_hypercorn_serve(app, config, shutdown_trigger):
        await shutdown_trigger()
        calls.append("drained")

    close = AsyncMock(side_effect=lambda: calls.append("bot closed"))
    with (
        patch.object(server, "hypercorn_serve", new=fake_hypercorn_serve),
        patch.object(server.bot, "close", new=close),
    ):
        serving = asyncio.create_task(server.serve())
        await asyncio.sleep(0)
        assert not serving.done()

        signal_handlers[sig]()
        await asyncio.wait_for(serving, timeout=1)

    assert calls == ["drained", "bot closed"]


def test_webhooks_get_up_to_50_seconds_to_drain():
    assert server.config.graceful_timeout == 50
