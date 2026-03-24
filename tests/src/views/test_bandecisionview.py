from datetime import datetime
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord.ui import Button

from src.views.bandecisionview import BanDecisionView, DisputeModal, register_ban_views
from tests import helpers


def _make_interaction(
    guild: helpers.MockGuild | None = None,
    user: helpers.MockMember | None = None,
) -> MagicMock:
    """Build a lightweight mock Interaction with the attributes our callbacks use."""
    interaction = MagicMock()
    interaction.guild = guild or helpers.MockGuild()
    interaction.user = user or helpers.MockMember(name="Admin")
    interaction.user.display_name = interaction.user.name

    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()

    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    interaction.message = MagicMock()
    interaction.message.edit = AsyncMock()

    return interaction


def _make_ban(
    ban_id: int = 1,
    user_id: int = 42,
    approved: bool = False,
    unbanned: bool = False,
    timestamp: object = True,
    unban_time: int = 9999999999,
) -> MagicMock:
    """Build a mock Ban model instance."""
    ban = MagicMock()
    ban.id = ban_id
    ban.user_id = user_id
    ban.approved = approved
    ban.unbanned = unbanned
    ban.timestamp = timestamp
    ban.unban_time = unban_time
    return ban


def _session_ctx(session_mock: AsyncMock) -> MagicMock:
    """Wrap an AsyncMock session so it works as ``async with AsyncSessionLocal() as s``."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestBanDecisionViewInit:
    @pytest.mark.asyncio
    async def test_buttons_have_unique_custom_ids(self, bot):
        view = BanDecisionView(ban_id=7, bot=bot)
        buttons = [c for c in view.children if isinstance(c, Button)]

        assert len(buttons) == 3
        ids = {b.custom_id for b in buttons}
        assert ids == {"ban_approve:7", "ban_deny:7", "ban_dispute:7"}

    @pytest.mark.asyncio
    async def test_timeout_is_none(self, bot):
        view = BanDecisionView(ban_id=1, bot=bot)
        assert view.timeout is None

    @pytest.mark.asyncio
    async def test_buttons_are_not_disabled_by_default(self, bot):
        view = BanDecisionView(ban_id=1, bot=bot)
        for child in view.children:
            if isinstance(child, Button):
                assert not child.disabled


class TestDisableHelpers:
    @pytest.mark.asyncio
    async def test_disable_all(self, bot):
        view = BanDecisionView(ban_id=1, bot=bot)
        view._disable_all()
        for child in view.children:
            if isinstance(child, Button):
                assert child.disabled

    @pytest.mark.asyncio
    async def test_disable_one_only_targets_matching_button(self, bot):
        view = BanDecisionView(ban_id=5, bot=bot)
        view._disable_one("ban_approve:5")

        for child in view.children:
            if isinstance(child, Button):
                if child.custom_id == "ban_approve:5":
                    assert child.disabled
                else:
                    assert not child.disabled


class TestResolveMemberName:
    @pytest.mark.asyncio
    async def test_returns_display_name_when_member_exists(self, bot, guild):
        member = helpers.MockMember(name="BannedUser")
        member.display_name = "BannedUser"
        bot.get_member_or_user = AsyncMock(return_value=member)

        view = BanDecisionView(ban_id=1, bot=bot)
        result = await view._resolve_member_name(guild, 42)

        assert result == "BannedUser"
        bot.get_member_or_user.assert_awaited_once_with(guild, 42)

    @pytest.mark.asyncio
    async def test_falls_back_to_str_id_when_member_missing(self, bot, guild):
        bot.get_member_or_user = AsyncMock(return_value=None)

        view = BanDecisionView(ban_id=1, bot=bot)
        result = await view._resolve_member_name(guild, 42)

        assert result == "42"


class TestApproveCallback:
    @pytest.mark.asyncio
    async def test_approve_happy_path(self, bot, guild):
        ban = _make_ban(ban_id=1, user_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=ban)
        session.commit = AsyncMock()

        channel = helpers.MockTextChannel()
        guild.get_channel = MagicMock(return_value=channel)

        member = helpers.MockMember(name="BannedUser")
        member.display_name = "BannedUser"
        bot.get_member_or_user = AsyncMock(return_value=member)

        interaction = _make_interaction(
            guild=guild, user=helpers.MockMember(name="Admin")
        )

        view = BanDecisionView(ban_id=1, bot=bot)

        with patch(
            "src.views.bandecisionview.AsyncSessionLocal",
            return_value=_session_ctx(session),
        ):
            await view._approve(interaction)

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        assert ban.approved is True
        session.commit.assert_awaited_once()

        interaction.followup.send.assert_awaited_once()
        assert "approved" in interaction.followup.send.call_args[0][0].lower()

        channel.send.assert_awaited_once()
        interaction.message.edit.assert_awaited_once()
        assert "Approved Duration" in interaction.message.edit.call_args[1]["content"]

    @pytest.mark.asyncio
    async def test_approve_ban_not_found(self, bot, guild):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        interaction = _make_interaction(guild=guild)
        view = BanDecisionView(ban_id=999, bot=bot)

        with patch(
            "src.views.bandecisionview.AsyncSessionLocal",
            return_value=_session_ctx(session),
        ):
            await view._approve(interaction)

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        interaction.followup.send.assert_awaited_once()
        assert "not found" in interaction.followup.send.call_args[0][0].lower()
        interaction.message.edit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_approve_disables_approve_button(self, bot, guild):
        ban = _make_ban(ban_id=3, user_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=ban)
        session.commit = AsyncMock()

        channel = helpers.MockTextChannel()
        guild.get_channel = MagicMock(return_value=channel)
        bot.get_member_or_user = AsyncMock(return_value=helpers.MockMember(name="User"))

        interaction = _make_interaction(guild=guild)
        view = BanDecisionView(ban_id=3, bot=bot)

        with patch(
            "src.views.bandecisionview.AsyncSessionLocal",
            return_value=_session_ctx(session),
        ):
            await view._approve(interaction)

        for child in view.children:
            if isinstance(child, Button):
                if child.custom_id == "ban_approve:3":
                    assert child.disabled
                else:
                    assert not child.disabled

    @pytest.mark.asyncio
    async def test_approve_skips_channel_send_when_channel_is_none(self, bot, guild):
        ban = _make_ban(ban_id=1, user_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=ban)
        session.commit = AsyncMock()

        guild.get_channel = MagicMock(return_value=None)
        bot.get_member_or_user = AsyncMock(return_value=helpers.MockMember(name="User"))

        interaction = _make_interaction(guild=guild)
        view = BanDecisionView(ban_id=1, bot=bot)

        with patch(
            "src.views.bandecisionview.AsyncSessionLocal",
            return_value=_session_ctx(session),
        ):
            await view._approve(interaction)

        interaction.followup.send.assert_awaited_once()
        interaction.message.edit.assert_awaited_once()


class TestDenyCallback:
    @pytest.mark.asyncio
    async def test_deny_happy_path(self, bot, guild):
        ban = _make_ban(ban_id=2, user_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=ban)

        channel = helpers.MockTextChannel()
        guild.get_channel = MagicMock(return_value=channel)

        member = helpers.MockMember(name="BannedUser")
        member.display_name = "BannedUser"
        bot.get_member_or_user = AsyncMock(return_value=member)

        interaction = _make_interaction(
            guild=guild, user=helpers.MockMember(name="Admin")
        )
        view = BanDecisionView(ban_id=2, bot=bot)

        with (
            patch(
                "src.views.bandecisionview.AsyncSessionLocal",
                return_value=_session_ctx(session),
            ),
            patch("src.helpers.ban.unban_member", new_callable=AsyncMock) as mock_unban,
        ):
            await view._deny(interaction)

        interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        mock_unban.assert_awaited_once_with(guild, member)

        interaction.followup.send.assert_awaited_once()
        assert "denied" in interaction.followup.send.call_args[0][0].lower()

        channel.send.assert_awaited_once()
        interaction.message.edit.assert_awaited_once()
        assert "Denied and Unbanned" in interaction.message.edit.call_args[1]["content"]

    @pytest.mark.asyncio
    async def test_deny_ban_not_found(self, bot, guild):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        interaction = _make_interaction(guild=guild)
        view = BanDecisionView(ban_id=999, bot=bot)

        with patch(
            "src.views.bandecisionview.AsyncSessionLocal",
            return_value=_session_ctx(session),
        ):
            await view._deny(interaction)

        interaction.followup.send.assert_awaited_once()
        assert "not found" in interaction.followup.send.call_args[0][0].lower()
        interaction.message.edit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_deny_disables_all_buttons(self, bot, guild):
        ban = _make_ban(ban_id=4, user_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=ban)

        guild.get_channel = MagicMock(return_value=helpers.MockTextChannel())
        bot.get_member_or_user = AsyncMock(return_value=helpers.MockMember(name="User"))

        interaction = _make_interaction(guild=guild)
        view = BanDecisionView(ban_id=4, bot=bot)

        with (
            patch(
                "src.views.bandecisionview.AsyncSessionLocal",
                return_value=_session_ctx(session),
            ),
            patch("src.helpers.ban.unban_member", new_callable=AsyncMock),
        ):
            await view._deny(interaction)

        for child in view.children:
            if isinstance(child, Button):
                assert child.disabled

    @pytest.mark.asyncio
    async def test_deny_member_not_found_skips_unban(self, bot, guild):
        ban = _make_ban(ban_id=5, user_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=ban)

        guild.get_channel = MagicMock(return_value=helpers.MockTextChannel())
        bot.get_member_or_user = AsyncMock(return_value=None)

        interaction = _make_interaction(guild=guild)
        view = BanDecisionView(ban_id=5, bot=bot)

        with (
            patch(
                "src.views.bandecisionview.AsyncSessionLocal",
                return_value=_session_ctx(session),
            ),
            patch("src.helpers.ban.unban_member", new_callable=AsyncMock) as mock_unban,
        ):
            await view._deny(interaction)

        mock_unban.assert_not_awaited()
        assert "42" in interaction.followup.send.call_args[0][0]


class TestDisputeCallback:
    @pytest.mark.asyncio
    async def test_dispute_sends_modal(self, bot, guild):
        interaction = _make_interaction(guild=guild)
        view = BanDecisionView(ban_id=10, bot=bot)

        await view._dispute(interaction)

        interaction.response.send_modal.assert_awaited_once()
        modal = interaction.response.send_modal.call_args[0][0]
        assert isinstance(modal, DisputeModal)
        assert modal.ban_id == 10
        assert modal.parent_view is view


class TestDisputeModalCallback:
    @pytest.mark.asyncio
    async def test_dispute_modal_invalid_duration(self, bot, guild):
        view = BanDecisionView(ban_id=1, bot=bot)
        modal = DisputeModal(ban_id=1, bot=bot, parent_view=view)

        interaction = _make_interaction(guild=guild)
        modal.children[0].value = "garbage"

        with patch(
            "src.views.bandecisionview.validate_duration",
            return_value=(0, "Invalid duration"),
        ):
            await modal.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with(
            "Invalid duration", ephemeral=True
        )

    @pytest.mark.asyncio
    async def test_dispute_modal_ban_not_found(self, bot, guild):
        view = BanDecisionView(ban_id=999, bot=bot)
        modal = DisputeModal(ban_id=999, bot=bot, parent_view=view)

        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        interaction = _make_interaction(guild=guild)
        modal.children[0].value = "1d"

        future_ts = int(datetime.now().timestamp()) + 86400
        with (
            patch(
                "src.views.bandecisionview.validate_duration",
                return_value=(future_ts, ""),
            ),
            patch(
                "src.views.bandecisionview.AsyncSessionLocal",
                return_value=_session_ctx(session),
            ),
        ):
            await modal.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        assert "not found" in interaction.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_dispute_modal_happy_path(self, bot, guild):
        ban = _make_ban(ban_id=6, user_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=ban)
        session.commit = AsyncMock()

        channel = helpers.MockTextChannel()
        guild.get_channel = MagicMock(return_value=channel)

        member = helpers.MockMember(name="BannedUser")
        member.display_name = "BannedUser"
        bot.get_member_or_user = AsyncMock(return_value=member)

        view = BanDecisionView(ban_id=6, bot=bot)
        modal = DisputeModal(ban_id=6, bot=bot, parent_view=view)

        interaction = _make_interaction(guild=guild)
        modal.children[0].value = "2d"

        future_ts = int(datetime.now().timestamp()) + 172800
        with (
            patch(
                "src.views.bandecisionview.validate_duration",
                return_value=(future_ts, ""),
            ),
            patch(
                "src.views.bandecisionview.AsyncSessionLocal",
                return_value=_session_ctx(session),
            ),
            patch("src.views.bandecisionview.schedule", new_callable=AsyncMock),
        ):
            await modal.callback(interaction)

        assert ban.unban_time == future_ts
        assert ban.approved is True
        session.commit.assert_awaited_once()

        interaction.response.send_message.assert_awaited_once()
        assert "updated" in interaction.response.send_message.call_args[0][0].lower()
        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dispute_modal_disables_all_buttons(self, bot, guild):
        ban = _make_ban(ban_id=7, user_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=ban)
        session.commit = AsyncMock()

        guild.get_channel = MagicMock(return_value=helpers.MockTextChannel())
        bot.get_member_or_user = AsyncMock(return_value=helpers.MockMember(name="User"))

        view = BanDecisionView(ban_id=7, bot=bot)
        modal = DisputeModal(ban_id=7, bot=bot, parent_view=view)

        interaction = _make_interaction(guild=guild)
        modal.children[0].value = "1h"

        future_ts = int(datetime.now().timestamp()) + 3600
        with (
            patch(
                "src.views.bandecisionview.validate_duration",
                return_value=(future_ts, ""),
            ),
            patch(
                "src.views.bandecisionview.AsyncSessionLocal",
                return_value=_session_ctx(session),
            ),
            patch("src.views.bandecisionview.schedule", new_callable=AsyncMock),
        ):
            await modal.callback(interaction)

        for child in view.children:
            if isinstance(child, Button):
                assert child.disabled

    @pytest.mark.asyncio
    async def test_dispute_modal_skips_message_edit_when_message_is_none(
        self, bot, guild
    ):
        ban = _make_ban(ban_id=8, user_id=42)
        session = AsyncMock()
        session.get = AsyncMock(return_value=ban)
        session.commit = AsyncMock()

        guild.get_channel = MagicMock(return_value=helpers.MockTextChannel())
        bot.get_member_or_user = AsyncMock(return_value=helpers.MockMember(name="User"))

        view = BanDecisionView(ban_id=8, bot=bot)
        modal = DisputeModal(ban_id=8, bot=bot, parent_view=view)

        interaction = _make_interaction(guild=guild)
        interaction.message = None
        modal.children[0].value = "1d"

        future_ts = int(datetime.now().timestamp()) + 86400
        with (
            patch(
                "src.views.bandecisionview.validate_duration",
                return_value=(future_ts, ""),
            ),
            patch(
                "src.views.bandecisionview.AsyncSessionLocal",
                return_value=_session_ctx(session),
            ),
            patch("src.views.bandecisionview.schedule", new_callable=AsyncMock),
        ):
            await modal.callback(interaction)

        interaction.response.send_message.assert_awaited_once()


class TestRegisterBanViews:
    @pytest.mark.asyncio
    async def test_registers_views_for_unapproved_bans(self, bot):
        ban_a = _make_ban(ban_id=10)
        ban_b = _make_ban(ban_id=20)

        scalars_result = MagicMock()
        scalars_result.all.return_value = [ban_a, ban_b]

        session = AsyncMock()
        session.scalars = AsyncMock(return_value=scalars_result)

        bot.add_view = MagicMock()

        with patch(
            "src.views.bandecisionview.AsyncSessionLocal",
            return_value=_session_ctx(session),
        ):
            await register_ban_views(bot)

        assert bot.add_view.call_count == 2
        registered_ids = {call.args[0].ban_id for call in bot.add_view.call_args_list}
        assert registered_ids == {10, 20}

    @pytest.mark.asyncio
    async def test_no_views_registered_when_no_pending_bans(self, bot):
        scalars_result = MagicMock()
        scalars_result.all.return_value = []

        session = AsyncMock()
        session.scalars = AsyncMock(return_value=scalars_result)

        bot.add_view = MagicMock()

        with patch(
            "src.views.bandecisionview.AsyncSessionLocal",
            return_value=_session_ctx(session),
        ):
            await register_ban_views(bot)

        bot.add_view.assert_not_called()
