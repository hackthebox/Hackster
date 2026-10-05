import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.webhooks import server


@pytest.mark.asyncio
async def test_serve_passes_shutdown_trigger_so_hypercorn_keeps_off_signals():
    with patch.object(server, "hypercorn_serve", new=AsyncMock()) as mock_serve:
        await server.serve()

    trigger = mock_serve.await_args.kwargs.get("shutdown_trigger")
    assert trigger is not None
    waiter = asyncio.ensure_future(trigger())
    await asyncio.sleep(0)
    assert not waiter.done()
    waiter.cancel()
