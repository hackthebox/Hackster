import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.webhooks.handlers.academy import AcademyHandler
from src.webhooks.types import WebhookBody, Platform, WebhookEvent
from tests import helpers


def _make_role_manager(**overrides):
    """Create a MockRoleManager with optional method overrides."""
    rm = helpers.MockRoleManager()
    for attr, val in overrides.items():
        setattr(rm, attr, val if callable(val) else lambda *a, v=val, **kw: v)
    return rm


class TestAcademyHandler:
    @pytest.mark.asyncio
    async def test_handle_certificate_awarded_success(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        certificate_id = 42
        mock_member = helpers.MockMember(id=discord_id, name="123456789")
        mock_member.add_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.CERTIFICATE_AWARDED,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "certificate_id": certificate_id,
                "certificate_name": "Test Certificate",
            },
            traits={},
        )
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=certificate_id)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(get_academy_cert_role=lambda cid: 555)

        with patch("src.webhooks.handlers.academy.settings") as mock_settings:
            mock_settings.channels.VERIFY_LOGS = 777
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = MagicMock()
            mock_channel = AsyncMock()
            mock_guild.get_channel.return_value = mock_channel
            bot.guilds = [mock_guild]

            result = await handler._handle_certificate_awarded(body, bot)
            mock_member.add_roles.assert_awaited()
            mock_channel.send.assert_awaited_once_with(
                "Certification linked: Test Certificate with Certificate ID: 42 -> @123456789 (123456789)"
            )
            assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_certificate_awarded_success_no_name(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        certificate_id = 42
        mock_member = helpers.MockMember(id=discord_id, name="123456789")
        mock_member.add_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.CERTIFICATE_AWARDED,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "certificate_id": certificate_id,
            },
            traits={},
        )
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=certificate_id)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(get_academy_cert_role=lambda cid: 555)

        with patch("src.webhooks.handlers.academy.settings") as mock_settings:
            mock_settings.channels.VERIFY_LOGS = 777
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = MagicMock()
            mock_channel = AsyncMock()
            mock_guild.get_channel.return_value = mock_channel
            bot.guilds = [mock_guild]

            result = await handler._handle_certificate_awarded(body, bot)
            mock_member.add_roles.assert_awaited()
            mock_channel.send.assert_awaited_once_with(
                "Certification linked: Certificate ID: 42 -> @123456789 (123456789)"
            )
            assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_certificate_awarded_no_role(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        certificate_id = 42
        mock_member = helpers.MockMember(id=discord_id, name="123456789")
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.CERTIFICATE_AWARDED,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "certificate_id": certificate_id,
                "certificate_name": "Test Certificate",
            },
            traits={},
        )
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=certificate_id)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(get_academy_cert_role=lambda cid: None)

        result = await handler._handle_certificate_awarded(body, bot)
        assert result == handler.fail()

    @pytest.mark.asyncio
    async def test_handle_certificate_awarded_add_roles_error(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        certificate_id = 42
        mock_member = helpers.MockMember(id=discord_id, name="123456789")
        mock_member.add_roles = AsyncMock(side_effect=Exception("add_roles error"))
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.CERTIFICATE_AWARDED,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "certificate_id": certificate_id,
                "certificate_name": "Test Certificate",
            },
            traits={},
        )
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=certificate_id)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(get_academy_cert_role=lambda cid: 555)

        with patch("src.webhooks.handlers.academy.settings") as mock_settings:
            mock_settings.channels.VERIFY_LOGS = 777
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = MagicMock()
            mock_channel = AsyncMock()
            mock_guild.get_channel.return_value = mock_channel
            bot.guilds = [mock_guild]

            with pytest.raises(Exception, match="add_roles error"):
                await handler._handle_certificate_awarded(body, bot)

    @pytest.mark.asyncio
    async def test_handle_certificate_awarded_no_verify_channel(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        certificate_id = 42
        mock_member = helpers.MockMember(id=discord_id, name="123456789")
        mock_member.add_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.CERTIFICATE_AWARDED,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "certificate_id": certificate_id,
                "certificate_name": "Test Certificate",
            },
            traits={},
        )
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=certificate_id)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(get_academy_cert_role=lambda cid: 555)

        with (
            patch("src.webhooks.handlers.academy.settings") as mock_settings,
            patch.object(handler.logger, "warning") as mock_log,
        ):
            mock_settings.channels.VERIFY_LOGS = 777
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = MagicMock()
            mock_guild.get_channel.return_value = None
            bot.guilds = [mock_guild]

            result = await handler._handle_certificate_awarded(body, bot)

            mock_member.add_roles.assert_awaited()
            mock_log.assert_called_with("Verify logs channel 777 not found")
            assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_subscription_change_success(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        plan = "Silver Annual"
        mock_member = helpers.MockMember(id=discord_id, name="123456789")
        mock_member.roles = []
        mock_member.add_roles = AsyncMock()
        mock_member.remove_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.SUBSCRIPTION_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "plan": plan,
            },
            traits={},
        )
        mock_role = MagicMock()
        mock_role.id = 555
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=plan)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(
            get_post_or_rank=lambda what: 555,
            get_group_ids=lambda cat: [555, 666, 777],
        )
        mock_guild = helpers.MockGuild(id=1)
        mock_guild.get_role.return_value = mock_role
        bot.guilds = [mock_guild]

        result = await handler._handle_subscription_change(body, bot)
        mock_member.add_roles.assert_awaited_once()
        assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_subscription_change_no_role(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        plan = "invalid_plan"
        mock_member = helpers.MockMember(id=discord_id, name="123456789")
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.SUBSCRIPTION_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "plan": plan,
            },
            traits={},
        )
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=plan)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(get_post_or_rank=lambda what: None)

        result = await handler._handle_subscription_change(body, bot)
        assert result == handler.fail()

    @pytest.mark.asyncio
    async def test_handle_subscription_change_role_swap(self, bot):
        """Test that subscription change properly swaps roles"""
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        plan = "professional"

        old_role = MagicMock()
        old_role.id = 666
        mock_member = helpers.MockMember(id=discord_id, name="123456789")
        mock_member.roles = [old_role]
        mock_member.add_roles = AsyncMock()
        mock_member.remove_roles = AsyncMock()

        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.SUBSCRIPTION_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "plan": plan,
            },
            traits={},
        )

        new_role = MagicMock()
        new_role.id = 555
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=plan)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(
            get_post_or_rank=lambda what: 555,
            get_group_ids=lambda cat: [555, 666, 777],
        )
        mock_guild = helpers.MockGuild(id=1)

        def get_role_mock(role_id):
            if role_id == 555:
                return new_role
            elif role_id == 666:
                return old_role
            return None

        mock_guild.get_role.side_effect = get_role_mock
        bot.guilds = [mock_guild]

        result = await handler._handle_subscription_change(body, bot)

        mock_member.remove_roles.assert_awaited_once_with(old_role, atomic=True)
        mock_member.add_roles.assert_awaited_once_with(new_role, atomic=True)
        assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_invalid_event(self, bot):
        handler = AcademyHandler()
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.RANK_UP,  # Not handled by AcademyHandler
            properties={},
            traits={},
        )
        with pytest.raises(ValueError, match="Invalid event"):
            await handler.handle(body, bot)
