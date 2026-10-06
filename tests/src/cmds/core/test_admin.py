"""Tests for Admin cog."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.cmds.core import admin
from src.core import settings
from src.database.models.dynamic_role import DynamicRole, RoleCategory
from tests import helpers


def _session_ctx(session_mock: AsyncMock) -> MagicMock:
    """Wrap an AsyncMock session so it works as ``async with AsyncSessionLocal() as s``."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


class TestAdminCog:
    """Test the Admin cog."""

    @pytest.mark.asyncio
    async def test_add_role_success(self, ctx, bot):
        """Test adding a dynamic role."""
        mock_role = MagicMock()
        mock_role.id = 123456789
        mock_role.mention = "<@&123456789>"

        bot.role_manager = MagicMock()
        bot.role_manager.add_role = AsyncMock()

        cog = admin.AdminCog(bot)
        await cog.add.callback(
            cog, ctx, "rank", "TestRole", mock_role, "Test Display Name",
            None, None, None  # description, cert_full_name, cert_integer_id
        )

        bot.role_manager.add_role.assert_called_once_with(
            key="TestRole",
            category=RoleCategory.RANK,
            discord_role_id=123456789,
            display_name="Test Display Name",
            description=None,
            cert_full_name=None,
            cert_integer_id=None,
        )
        ctx.respond.assert_called_once_with(
            "Added dynamic role: `rank/TestRole` -> <@&123456789>",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_add_role_with_cert(self, ctx, bot):
        """Test adding a cert role with extra fields."""
        mock_role = MagicMock()
        mock_role.id = 123456789
        mock_role.mention = "<@&123456789>"

        bot.role_manager = MagicMock()
        bot.role_manager.add_role = AsyncMock()

        cog = admin.AdminCog(bot)
        await cog.add.callback(
            cog,
            ctx,
            "academy_cert",
            "CPTS",
            mock_role,
            "CPTS Cert",
            None,  # description
            "HTB Certified Penetration Testing Specialist",
            3,
        )

        bot.role_manager.add_role.assert_called_once_with(
            key="CPTS",
            category=RoleCategory.ACADEMY_CERT,
            discord_role_id=123456789,
            display_name="CPTS Cert",
            description=None,
            cert_full_name="HTB Certified Penetration Testing Specialist",
            cert_integer_id=3,
        )

    @pytest.mark.asyncio
    async def test_add_role_invalid_category(self, ctx, bot):
        """Test adding a role with invalid category."""
        mock_role = MagicMock()

        cog = admin.AdminCog(bot)
        await cog.add.callback(
            cog, ctx, "invalid_category", "TestRole", mock_role, "Test",
            None, None, None  # description, cert_full_name, cert_integer_id
        )

        ctx.respond.assert_called_once_with(
            "Invalid category: invalid_category",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_remove_role_success(self, ctx, bot):
        """Test removing a dynamic role successfully."""
        bot.role_manager = MagicMock()
        bot.role_manager.remove_role = AsyncMock(return_value=True)

        cog = admin.AdminCog(bot)
        await cog.remove.callback(cog, ctx, "rank", "Omniscient")

        bot.role_manager.remove_role.assert_called_once_with(
            RoleCategory.RANK,
            "Omniscient",
        )
        ctx.respond.assert_called_once_with(
            "Removed dynamic role: `rank/Omniscient`",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_remove_role_not_found(self, ctx, bot):
        """Test removing a role that doesn't exist."""
        bot.role_manager = MagicMock()
        bot.role_manager.remove_role = AsyncMock(return_value=False)

        cog = admin.AdminCog(bot)
        await cog.remove.callback(cog, ctx, "rank", "NonExistent")

        ctx.respond.assert_called_once_with(
            "No role found for `rank/NonExistent`",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_update_role_success(self, ctx, bot):
        """Test updating a dynamic role successfully."""
        mock_role = MagicMock()
        mock_role.id = 987654321
        mock_role.mention = "<@&987654321>"

        bot.role_manager = MagicMock()
        bot.role_manager.update_role = AsyncMock(return_value=True)

        cog = admin.AdminCog(bot)
        await cog.update.callback(cog, ctx, "rank", "Omniscient", mock_role)

        bot.role_manager.update_role.assert_called_once_with(
            RoleCategory.RANK,
            "Omniscient",
            987654321,
        )
        ctx.respond.assert_called_once_with(
            "Updated `rank/Omniscient` -> <@&987654321>",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, ctx, bot):
        """Test updating a role that doesn't exist."""
        mock_role = MagicMock()
        mock_role.id = 987654321

        bot.role_manager = MagicMock()
        bot.role_manager.update_role = AsyncMock(return_value=False)

        cog = admin.AdminCog(bot)
        await cog.update.callback(cog, ctx, "rank", "NonExistent", mock_role)

        ctx.respond.assert_called_once_with(
            "No role found for `rank/NonExistent`",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_list_roles_empty(self, ctx, bot):
        """Test listing roles when none are configured."""
        bot.role_manager = MagicMock()
        bot.role_manager.list_roles = AsyncMock(return_value=[])

        cog = admin.AdminCog(bot)
        await cog.list.callback(cog, ctx, None)

        ctx.respond.assert_called_once_with(
            "No dynamic roles configured.",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_list_roles_with_data(self, ctx, bot, guild):
        """Test listing roles with data."""
        ctx.guild = guild

        mock_roles = [
            DynamicRole(
                id=1,
                key="Omniscient",
                discord_role_id=586528519459438592,
                category=RoleCategory.RANK,
                display_name="Omniscient",
            ),
            DynamicRole(
                id=2,
                key="Hacker",
                discord_role_id=586528079363702801,
                category=RoleCategory.RANK,
                display_name="Hacker",
            ),
        ]

        bot.role_manager = MagicMock()
        bot.role_manager.list_roles = AsyncMock(return_value=mock_roles)

        cog = admin.AdminCog(bot)
        await cog.list.callback(cog, ctx, None)

        # Should respond with an embed
        assert ctx.respond.called
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral") is True
        assert "embed" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_reload_success(self, ctx, bot):
        """Test reloading dynamic roles."""
        bot.role_manager = MagicMock()
        bot.role_manager.reload = AsyncMock()

        cog = admin.AdminCog(bot)
        await cog.reload.callback(cog, ctx)

        bot.role_manager.reload.assert_called_once()
        ctx.respond.assert_called_once_with(
            "Dynamic roles reloaded from database.",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_remove_role_invalid_category(self, ctx, bot):
        """Test removing with an invalid category returns an error."""
        cog = admin.AdminCog(bot)
        await cog.remove.callback(cog, ctx, "bad_cat", "Key")

        ctx.respond.assert_called_once_with(
            "Invalid category: bad_cat",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_update_role_invalid_category(self, ctx, bot):
        """Test updating with an invalid category returns an error."""
        mock_role = helpers.MockRole(id=7777, name="NewRole")

        cog = admin.AdminCog(bot)
        await cog.update.callback(cog, ctx, "bad_cat", "Key", mock_role)

        ctx.respond.assert_called_once_with(
            "Invalid category: bad_cat",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_list_roles_with_category_filter(self, ctx, bot):
        """Test listing dynamic roles filtered by a specific category."""
        bot.role_manager = MagicMock()
        bot.role_manager.list_roles = AsyncMock(return_value=[])

        cog = admin.AdminCog(bot)
        await cog.list.callback(cog, ctx, "rank")

        bot.role_manager.list_roles.assert_called_once_with(RoleCategory.RANK)

    @pytest.mark.asyncio
    async def test_list_role_not_in_guild(self, ctx, bot):
        """Test listing when a role ID does not exist in the guild (shows raw ID)."""
        mock_role_entry = MagicMock()
        mock_role_entry.category = RoleCategory.RANK
        mock_role_entry.key = "Ghost"
        mock_role_entry.discord_role_id = 99999
        mock_role_entry.display_name = "Ghost Rank"

        ctx.guild.get_role = MagicMock(return_value=None)
        bot.role_manager = MagicMock()
        bot.role_manager.list_roles = AsyncMock(return_value=[mock_role_entry])

        cog = admin.AdminCog(bot)
        await cog.list.callback(cog, ctx, None)

        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral") is True
        embed = call_args.kwargs["embed"]
        # When guild role is not found, the raw ID should be shown
        assert "99999" in embed.fields[0].value

    def test_setup(self, bot):
        """Test the setup function registers the cog."""
        admin.setup(bot)
        bot.add_cog.assert_called_once()


class TestParseMemberIds:
    """Test the nominee token parser."""

    def test_parses_mentions_and_bare_snowflakes(self):
        """Both mention forms and bare snowflakes resolve to ints, order preserved."""
        assert admin._parse_member_ids("<@123456789012345678> <@!234567890123456789> 345678901234567890") == [
            123456789012345678,
            234567890123456789,
            345678901234567890,
        ]

    def test_drops_duplicates(self):
        """A repeated nominee is only counted once."""
        assert admin._parse_member_ids("123456789012345678, <@123456789012345678>") == [123456789012345678]

    def test_rejects_overlong_digit_run(self):
        """A digit run longer than a snowflake is rejected at parse time."""
        with pytest.raises(ValueError, match="Could not parse"):
            admin._parse_member_ids("9" * 600)

    def test_rejects_too_short_digit_run(self):
        """A digit run shorter than a snowflake is rejected at parse time."""
        with pytest.raises(ValueError, match="Could not parse"):
            admin._parse_member_ids("12345")


def _member(user_id: int, name: str = "Nominee") -> MagicMock:
    member = MagicMock()
    member.id = user_id
    member.display_name = name
    return member


def _guild_ctx(get_member: MagicMock, query_members: AsyncMock | None = None) -> MagicMock:
    """Build a context whose guild resolves members from the cache, then over the gateway."""
    ctx = MagicMock()
    ctx.guild = MagicMock()
    ctx.guild.get_member = get_member
    ctx.guild.query_members = query_members or AsyncMock(return_value=[])
    return ctx


class TestLookupMembers:
    """Test the nominee member lookup."""

    @pytest.mark.asyncio
    async def test_cached_members_need_no_gateway_request(self):
        ctx = _guild_ctx(MagicMock(side_effect=lambda uid: _member(uid)))

        resolved, missing = await admin._lookup_members(ctx, [1, 2])

        assert resolved == [(1, "Nominee"), (2, "Nominee")]
        assert missing == []
        ctx.guild.query_members.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uncached_members_are_fetched_in_one_request(self):
        cached = {1: _member(1, "Cached")}
        query = AsyncMock(return_value=[_member(3, "Three"), _member(2, "Two")])
        ctx = _guild_ctx(MagicMock(side_effect=cached.get), query)

        resolved, missing = await admin._lookup_members(ctx, [1, 2, 3])

        query.assert_awaited_once_with(user_ids=[2, 3], limit=2)
        assert resolved == [(1, "Cached"), (2, "Two"), (3, "Three")]
        assert missing == []

    @pytest.mark.asyncio
    async def test_reports_ids_discord_did_not_return(self):
        ctx = _guild_ctx(MagicMock(return_value=None), AsyncMock(return_value=[_member(1)]))

        resolved, missing = await admin._lookup_members(ctx, [1, 2])

        assert resolved == [(1, "Nominee")]
        assert missing == ["2"]

    @pytest.mark.asyncio
    async def test_a_gateway_timeout_becomes_a_user_facing_error(self):
        ctx = _guild_ctx(MagicMock(return_value=None), AsyncMock(side_effect=asyncio.TimeoutError))

        with pytest.raises(ValueError, match="Try again"):
            await admin._lookup_members(ctx, [1])


class TestResolveNominees:
    """Test the nominee argument validation."""

    @pytest.mark.asyncio
    async def test_rejects_an_empty_nominee_list(self):
        with pytest.raises(ValueError, match="at least one nominee"):
            await admin._resolve_nominees(MagicMock(), "   ")

    @pytest.mark.asyncio
    async def test_rejects_more_nominees_than_a_select_menu_holds(self):
        too_many = " ".join(str(123456789012345678 + i) for i in range(admin.MAX_VOTE_NOMINEES + 1))

        with pytest.raises(ValueError, match="at most 25 nominees"):
            await admin._resolve_nominees(MagicMock(), too_many)

    @pytest.mark.asyncio
    async def test_names_the_members_it_could_not_find(self):
        ctx = _guild_ctx(MagicMock(return_value=None))

        with pytest.raises(ValueError, match="123456789012345678"):
            await admin._resolve_nominees(ctx, "123456789012345678")

    @pytest.mark.asyncio
    async def test_returns_id_and_display_name_pairs(self):
        ctx = _guild_ctx(MagicMock(return_value=_member(123456789012345678)))

        assert await admin._resolve_nominees(ctx, "123456789012345678") == [(123456789012345678, "Nominee")]


class TestVoteCommand:
    """Test the /admin vote command."""

    @pytest.fixture(autouse=True)
    def in_vote_channel(self, ctx):
        ctx.channel.id = settings.channels.VOTE

    def test_topic_is_bounded_below_the_embed_title_limit(self, bot):
        """Discord caps embed titles at 256; build_results_embed also prefixes 'Results: '."""
        cog = admin.AdminCog(bot)
        topic = next(o for o in cog.vote.options if o.name == "topic")

        assert topic.max_length is not None
        assert topic.max_length + len("Results: ") <= 256

    @pytest.mark.asyncio
    async def test_defers_before_resolving_members(self, ctx, bot):
        """Resolving nominees can outlast the 3s initial-response budget; defer must come first."""
        order: list[str] = []
        ctx.defer = AsyncMock(side_effect=lambda **kw: order.append("defer"))
        ctx.guild.get_member = MagicMock(side_effect=lambda uid: order.append("resolve") or None)
        ctx.guild.query_members = AsyncMock(return_value=[])

        cog = admin.AdminCog(bot)
        with patch("src.cmds.core.admin.validate_duration", return_value=(1800000000, "")), patch(
            "src.cmds.core.admin.time.time", return_value=1799999000
        ):
            await cog.vote.callback(cog, ctx, "<@123456789012345678>", "10m", None)

        assert order[0] == "defer"
        assert "resolve" in order

    @pytest.mark.asyncio
    async def test_rejects_duration_beyond_cap(self, ctx, bot):
        """A duration validate_duration happily accepts is still capped at 30 days."""
        cog = admin.AdminCog(bot)
        with patch("src.cmds.core.admin.AsyncSessionLocal") as session_local:
            await cog.vote.callback(cog, ctx, "<@123456789012345678>", "50y", None)

        session_local.assert_not_called()
        ctx.respond.assert_called_once()
        assert "30 days" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_stores_closes_at_as_epoch_seconds(self, ctx, bot):
        """The validated epoch int is persisted and scheduled on unconverted."""
        member = MagicMock()
        member.id = 123456789012345678
        member.display_name = "Nominee"
        ctx.guild.get_member = MagicMock(return_value=member)

        loaded = MagicMock()
        loaded.id = 42
        loaded.candidates = []

        session = AsyncMock()
        session.add = MagicMock()
        session.scalar = AsyncMock(return_value=loaded)

        cog = admin.AdminCog(bot)
        with (
            patch("src.cmds.core.admin.AsyncSessionLocal", return_value=_session_ctx(session)),
            patch("src.cmds.core.admin.build_poll_embed", return_value=MagicMock()),
            patch("src.cmds.core.admin.schedule_vote_close") as mock_schedule_close,
            patch("src.cmds.core.admin.validate_duration", return_value=(1800000000, "")),
            patch("src.cmds.core.admin.time.time", return_value=1799999000),
        ):
            await cog.vote.callback(cog, ctx, "<@123456789012345678>", "10m", "Topic")

        created = session.add.call_args_list[0].args[0]
        assert created.closes_at == 1800000000
        mock_schedule_close.assert_called_once_with(bot, 42, 1800000000)

    @pytest.mark.asyncio
    async def test_rolls_back_the_session_when_the_poll_cannot_be_posted(self, ctx, bot):
        """A failed send must not leave an orphan open session that resurfaces on restart."""
        member = MagicMock()
        member.id = 123456789012345678
        member.display_name = "Nominee"
        ctx.guild.get_member = MagicMock(return_value=member)
        ctx.channel.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "no embed links"))

        loaded = MagicMock()
        loaded.id = 42
        loaded.candidates = []

        session = AsyncMock()
        session.add = MagicMock()
        session.scalar = AsyncMock(return_value=loaded)

        cog = admin.AdminCog(bot)
        with (
            patch("src.cmds.core.admin.AsyncSessionLocal", return_value=_session_ctx(session)),
            patch("src.cmds.core.admin.build_poll_embed", return_value=MagicMock()),
            patch("src.cmds.core.admin.schedule_vote_close") as mock_schedule_close,
            patch("src.cmds.core.admin.validate_duration", return_value=(1800000000, "")),
            patch("src.cmds.core.admin.time.time", return_value=1799999000),
        ):
            await cog.vote.callback(cog, ctx, "<@123456789012345678>", "10m", "Topic")

        deletes = [
            call.args[0] for call in session.execute.await_args_list if getattr(call.args[0], "is_delete", False)
        ]
        assert len(deletes) == 1
        assert deletes[0].compile().params == {"id_1": 42}

        mock_schedule_close.assert_not_called()
        ctx.followup.send.assert_awaited_once()
        assert "Could not post the poll" in ctx.followup.send.await_args[0][0]

    @pytest.mark.asyncio
    async def test_rejects_an_unparseable_duration(self, ctx, bot):
        """An invalid duration is refused before any nominee lookup or DB work."""
        cog = admin.AdminCog(bot)
        with patch("src.cmds.core.admin.AsyncSessionLocal") as session_local:
            await cog.vote.callback(cog, ctx, "<@123456789012345678>", "banana", None)

        session_local.assert_not_called()
        ctx.guild.get_member.assert_not_called()
        ctx.respond.assert_called_once()
        assert "could not parse" in ctx.respond.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_rejects_a_malformed_nominee_argument(self, ctx, bot):
        """A nominee token that is neither a mention nor a snowflake is reported back."""
        cog = admin.AdminCog(bot)
        with patch("src.cmds.core.admin.AsyncSessionLocal") as session_local:
            await cog.vote.callback(cog, ctx, "not-a-mention", "10m", None)

        session_local.assert_not_called()
        ctx.respond.assert_called_once()
        assert "not-a-mention" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_refuses_to_post_outside_the_vote_channel(self, ctx, bot):
        """One wrong channel would show nominees and their tallies to everyone in it."""
        ctx.channel.id = settings.channels.VOTE + 1
        cog = admin.AdminCog(bot)
        with patch("src.cmds.core.admin.AsyncSessionLocal") as session_local:
            await cog.vote.callback(cog, ctx, "<@123456789012345678>", "10m", None)

        session_local.assert_not_called()
        ctx.channel.send.assert_not_called()
        assert f"<#{settings.channels.VOTE}>" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("target", "name"),
        [(settings.channels, "VOTE"), (settings, "VOTE_HMAC_SECRET")],
    )
    async def test_refuses_to_start_until_votes_are_configured(self, ctx, bot, target, name):
        cog = admin.AdminCog(bot)
        with (
            patch.object(target, name, type(getattr(target, name))()),
            patch("src.cmds.core.admin.AsyncSessionLocal") as session_local,
        ):
            await cog.vote.callback(cog, ctx, "<@123456789012345678>", "10m", None)

        session_local.assert_not_called()
        assert "not set up" in ctx.respond.call_args[0][0]
