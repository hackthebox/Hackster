"""End-to-end tests for the SubscriptionChange webhook (issue #205).

Each test sends a signed SubscriptionChange webhook through the real FastAPI app, the real
MPHandler and a real RoleManager filled from the env-var fallback roles (the
`vip` / `dedivip` keys). Only Discord itself is mocked.
"""
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core import settings
from src.database.models.dynamic_role import DynamicRole, RoleCategory
from src.services.role_manager import RoleManager
from src.webhooks import handlers, server
from src.webhooks.types import Platform


def _role(role_id: int) -> MagicMock:
    role = MagicMock()
    role.id = role_id
    return role


@pytest.fixture
def fake_bot(monkeypatch):
    """A bot whose guild has the VIP and VIP+ roles and one member holding no subscription role."""
    role_manager = RoleManager(fallback_roles=settings.roles)
    roles: dict = {}
    role_manager._apply_fallbacks(roles)  # same code path load() uses when the DB has no row
    role_manager._roles = roles

    guild_roles = {rid: _role(rid) for rid in role_manager.get_group_ids("subscription_labs")}

    member = MagicMock()
    member.roles = []
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()

    guild = MagicMock()
    guild.get_role.side_effect = guild_roles.get
    guild.fetch_member = AsyncMock(return_value=member)

    bot = MagicMock()
    bot.role_manager = role_manager
    bot.guilds = [guild]
    bot.fetch_guild = AsyncMock(return_value=guild)
    bot.member = member
    bot.bot_fetch_guild = bot.fetch_guild

    monkeypatch.setattr(server, "bot", bot)
    return bot


async def _post(subscription_name: str) -> httpx.Response:
    raw = json.dumps(
        {
            "platform": "mp",
            "event": "SubscriptionChange",
            "properties": {
                "discord_id": 123456789,
                "account_id": 987654321,
                "subscription_name": subscription_name,
            },
        }
    ).encode()
    signature = hmac.new(settings.WEBHOOK_TOKEN.encode(), raw, hashlib.sha1).hexdigest()
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            "/webhook", content=raw, headers={"X-Signature": signature, "Content-Type": "application/json"}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["vip", "dedivip"])
async def test_known_subscription_names_grant_the_role(fake_bot, name):
    response = await _post(name)
    assert response.status_code == 200
    fake_bot.member.add_roles.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["Free", "free"])
async def test_free_removes_the_subscription_role(fake_bot, name):
    vip_id = fake_bot.role_manager.get_role_id("subscription_labs", "vip")
    vip_role = fake_bot.guilds[0].get_role(vip_id)
    fake_bot.member.roles = [vip_role]

    response = await _post(name)

    assert response.status_code == 200
    fake_bot.member.remove_roles.assert_awaited_once_with(vip_role, atomic=True)
    fake_bot.member.add_roles.assert_not_awaited()


@pytest.mark.asyncio
async def test_free_without_a_subscription_role_changes_nothing(fake_bot):
    response = await _post("Free")
    assert response.status_code == 200
    fake_bot.member.remove_roles.assert_not_awaited()
    fake_bot.member.add_roles.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["Pro", "Hacker", "nonsense"])
async def test_name_without_a_role_returns_422_and_warns(fake_bot, name):
    """`Hacker` is a rank key: it must not resolve to a role outside the subscription group."""
    mp_logger = handlers.handlers[Platform.MAIN].__self__.logger
    with patch.object(mp_logger, "warning") as warning, patch.object(server.logger, "error") as error:
        response = await _post(name)

    assert response.status_code == 422
    assert response.json() == {"detail": f"Unknown subscription name: {name}"}
    warning.assert_called_once()
    assert name in warning.call_args.args
    error.assert_not_called()
    fake_bot.bot_fetch_guild.assert_not_awaited()
    fake_bot.member.add_roles.assert_not_awaited()
    fake_bot.member.remove_roles.assert_not_awaited()


@pytest.mark.asyncio
async def test_pro_grants_its_role_once_one_is_configured(fake_bot):
    pro = DynamicRole()
    pro.key, pro.discord_role_id, pro.category, pro.display_name = "Pro", 4242, RoleCategory.SUBSCRIPTION_LABS, "Pro"
    fake_bot.role_manager._roles["subscription_labs"]["Pro"] = pro
    pro_role = _role(4242)
    known = fake_bot.guilds[0].get_role.side_effect
    fake_bot.guilds[0].get_role.side_effect = lambda rid: pro_role if rid == 4242 else known(rid)

    response = await _post("Pro")

    assert response.status_code == 200
    fake_bot.member.add_roles.assert_awaited_once_with(pro_role, atomic=True)
