import asyncio
import unittest.mock

import discord
import pytest
from discord.commands import ApplicationContext
from discord.ext import commands

from tests import helpers


class TestDiscordMocks:
    """Tests for our specialized discord.py mocks."""

    def test_mock_role_default_initialization(self):
        """Test if the default initialization of MockRole results in the correct object."""
        role = helpers.MockRole()

        # The `spec` argument makes sure `isistance` checks with `discord.Role` pass
        assert isinstance(role, discord.Role)

        assert role.name == "role"
        assert role.position == 1
        assert role.mention == "&role"

    def test_mock_role_alternative_arguments(self):
        """Test if MockRole initializes with the arguments provided."""
        role = helpers.MockRole(
            name="Admins",
            id=90210,
            position=10,
        )

        assert role.name == "Admins"
        assert role.id == 90210
        assert role.position == 10
        assert role.mention == "&Admins"

    def test_mock_role_accepts_dynamic_arguments(self):
        """Test if MockRole accepts and sets abitrary keyword arguments."""
        role = helpers.MockRole(
            guild="Dino Man",
            hoist=True,
        )

        assert role.guild == "Dino Man"
        assert role.hoist

    def test_mock_role_uses_position_for_less_than_greater_than(self):
        """Test if `<` and `>` comparisons for MockRole are based on its position attribute."""
        role_one = helpers.MockRole(position=1)
        role_two = helpers.MockRole(position=2)
        role_three = helpers.MockRole(position=3)

        assert role_one < role_two
        assert role_one < role_three
        assert role_two < role_three
        assert role_three > role_two
        assert role_three > role_one
        assert role_two > role_one

    def test_mock_member_default_initialization(self):
        """Test if the default initialization of Mockmember results in the correct object."""
        member = helpers.MockMember()

        # The `spec` argument makes sure `isistance` checks with `discord.Member` pass
        assert isinstance(member, discord.Member)

        assert member.name == "member"
        assert member.roles == [helpers.MockRole(name="@everyone", position=1, id=0)]
        assert member.mention == "@member"

    def test_mock_member_alternative_arguments(self):
        """Test if MockMember initializes with the arguments provided."""
        core_developer = helpers.MockRole(name="Core Developer", position=2)
        member = helpers.MockMember(
            name="Mark",
            id=12345,
            roles=[core_developer]
        )

        assert member.name == "Mark"
        assert member.id == 12345
        assert member.roles == [helpers.MockRole(name="@everyone", position=1, id=0), core_developer]
        assert member.mention == "@Mark"

    def test_mock_member_accepts_dynamic_arguments(self):
        """Test if MockMember accepts and sets abitrary keyword arguments."""
        member = helpers.MockMember(
            nick="Dino Man",
            colour=discord.Colour.default(),
        )

        assert member.nick == "Dino Man"
        assert member.colour == discord.Colour.default()

    def test_mock_guild_default_initialization(self):
        """Test if the default initialization of Mockguild results in the correct object."""
        guild = helpers.MockGuild()

        # The `spec` argument makes sure `isistance` checks with `discord.Guild` pass
        assert isinstance(guild, discord.Guild)

        assert guild.roles == [helpers.MockRole(name="@everyone", position=1, id=0)]
        assert guild.members == []

    def test_mock_guild_alternative_arguments(self):
        """Test if MockGuild initializes with the arguments provided."""
        core_developer = helpers.MockRole(name="Core Developer", position=2)
        guild = helpers.MockGuild(
            roles=[core_developer],
            members=[helpers.MockMember(id=54321)],
        )

        assert guild.roles == [helpers.MockRole(name="@everyone", position=1, id=0), core_developer]
        assert guild.members == [helpers.MockMember(id=54321)]

    def test_mock_guild_accepts_dynamic_arguments(self):
        """Test if MockGuild accepts and sets abitrary keyword arguments."""
        guild = helpers.MockGuild(
            emojis=(":hyperjoseph:", ":pensive_ela:"),
            premium_subscription_count=15,
        )

        assert guild.emojis == (":hyperjoseph:", ":pensive_ela:")
        assert guild.premium_subscription_count == 15

    def test_mock_bot_default_initialization(self):
        """Tests if MockBot initializes with the correct values."""
        bot = helpers.MockBot()

        # The `spec` argument makes sure `isistance` checks with `discord.ext.commands.Bot` pass
        assert isinstance(bot, commands.Bot)

    def test_mock_context_default_initialization(self):
        """Tests if MockContext initializes with the correct values."""
        context = helpers.MockContext()

        # The `spec` argument makes sure `isistance` checks with `discord.ext.commands.Context` pass
        assert isinstance(context, ApplicationContext)

        assert isinstance(context.bot, helpers.MockBot)
        assert isinstance(context.guild, helpers.MockGuild)
        assert isinstance(context.author, helpers.MockMember)

    def test_mocks_allows_access_to_attributes_part_of_spec(self):
        """Accessing attributes that are valid for the objects they mock should succeed."""
        mocks = (
            (helpers.MockGuild(), 'name'),
            (helpers.MockRole(), 'hoist'),
            (helpers.MockMember(), 'display_name'),
            (helpers.MockBot(), 'user'),
            (helpers.MockTextChannel(), 'last_message'),
            (helpers.MockMessage(), 'mention_everyone'),
        )

        for mock, valid_attribute in mocks:
            try:
                getattr(mock, valid_attribute)
            except AttributeError:
                msg = f"Accessing valid attribute `{valid_attribute}` raised an AttributeError."
                raise AssertionError(msg)

    def test_mocks_rejects_access_to_attributes_not_part_of_spec(self):
        """Accessing attributes that are invalid for the objects they mock should fail."""
        mocks = (
            helpers.MockGuild(),
            helpers.MockRole(),
            helpers.MockMember(),
            helpers.MockBot(),
            helpers.MockContext(),
            helpers.MockTextChannel(),
            helpers.MockMessage(),
        )

        for mock in mocks:
            with pytest.raises(AttributeError):
                bool(mock.this_does_not_exist)

    def test_mocks_use_mention_when_provided_as_kwarg(self):
        """The mock should use the passed `mention` instead of the default one if present."""
        test_cases = (
            (helpers.MockRole, "role mention"),
            (helpers.MockMember, "member mention"),
            (helpers.MockTextChannel, "channel mention"),
        )

        for mock_type, mention in test_cases:
            mock = mock_type(mention=mention)
            assert mock.mention == mention

    def test_create_test_on_mock_bot_closes_passed_coroutine(self):
        """`bot.loop.create_task` should close the passed coroutine object to prevent warnings."""

        async def dummy():
            """Dummy coroutine for testing purposes."""
            pass

        coroutine_object = dummy()

        bot = helpers.MockBot()
        bot.loop.create_task(coroutine_object)
        with pytest.raises(RuntimeError):
            asyncio.run(coroutine_object)

    def test_user_mock_uses_explicitly_passed_mention_attribute(self):
        """MockUser should use an explicitly passed value for user.mention."""
        user = helpers.MockUser(mention="hello")
        assert user.mention == "hello"


class TestMockObject:
    """Tests the mock objects and mixins we've defined."""

    def test_colour_mixin(self):
        """Test if the ColourMixin adds aliasing of color -> colour for child classes."""

        class MockHemlock(unittest.mock.MagicMock, helpers.ColourMixin):
            pass

        hemlock = MockHemlock()
        hemlock.color = 1
        assert hemlock.colour == 1
        assert hemlock.colour == hemlock.color

    def test_hashable_mixin_hash_returns_id(self):
        """Test if the HashableMixing uses the id attribute for hashing."""

        class MockScragly(unittest.mock.Mock, helpers.HashableMixin):
            pass

        scragly = MockScragly()
        scragly.id = 10
        assert hash(scragly) == scragly.id

    def test_hashable_mixin_uses_id_for_equality_comparison(self):
        """Test if the HashableMixing uses the id attribute for hashing."""

        class MockScragly(helpers.HashableMixin):
            pass

        scragly = MockScragly()
        scragly.id = 10
        eevee = MockScragly()
        eevee.id = 10
        python = MockScragly()
        python.id = 20

        assert scragly == eevee
        assert scragly != python

    def test_hashable_mixin_uses_id_for_nonequality_comparison(self):
        """Test if the HashableMixing uses the id attribute for hashing."""

        class MockScragly(helpers.HashableMixin):
            pass

        scragly = MockScragly()
        scragly.id = 10
        eevee = MockScragly()
        eevee.id = 10
        python = MockScragly()
        python.id = 20

        assert scragly != python
        assert scragly == eevee

    def test_mock_class_with_hashable_mixin_uses_id_for_hashing(self, hashable_mocks):
        """Test if the MagicMock subclasses that implement the HashableMixin use id for hash."""
        for mock_class in hashable_mocks:
            instance = mock_class(id=100)
            assert hash(instance) == instance.id

    def test_mock_class_with_hashable_mixin_uses_id_for_equality(self, hashable_mocks):
        """Test if MagicMocks that implement the HashableMixin use id for equality comparisons."""
        for mock_class in hashable_mocks:
            instance_one = mock_class()
            instance_two = mock_class()
            instance_three = mock_class()

            instance_one.id = 10
            instance_two.id = 10
            instance_three.id = 20

            assert instance_one == instance_two
            assert instance_one != instance_three

    def test_mock_class_with_hashable_mixin_uses_id_for_nonequality(self, hashable_mocks):
        """Test if MagicMocks that implement HashableMixin use id for nonequality comparisons."""
        for mock_class in hashable_mocks:
            instance_one = mock_class()
            instance_two = mock_class()
            instance_three = mock_class()

            instance_one.id = 10
            instance_two.id = 10
            instance_three.id = 20

            assert instance_one == instance_two
            assert instance_one != instance_three

    def test_custom_mock_mixin_accepts_mock_seal(self):
        """The `CustomMockMixin` should support `unittest.mock.seal`."""

        class MyMock(helpers.CustomMockMixin, unittest.mock.MagicMock):
            child_mock_type = unittest.mock.MagicMock
            pass

        mock = MyMock()
        unittest.mock.seal(mock)
        with pytest.raises(AttributeError):
            mock.shirayuki = "hello!"

    def test_spec_propagation_of_mock_subclasses(self):
        """Test if the `spec` does not propagate to attributes of the mock object."""
        test_values = (
            (helpers.MockGuild, "name"),
            (helpers.MockRole, "mentionable"),
            (helpers.MockMember, "display_name"),
            (helpers.MockBot, "owner_id"),
            (helpers.MockMessage, "mention_everyone"),
            (helpers.MockEmoji, 'managed'),
            (helpers.MockPartialEmoji, 'url'),
            (helpers.MockReaction, 'me'),
        )

        for mock_type, valid_attribute in test_values:
            mock = mock_type()
            assert isinstance(mock, mock_type)

            attribute = getattr(mock, valid_attribute)
            assert isinstance(attribute, mock_type.child_mock_type)

    def test_custom_mock_mixin_mocks_async_magic_methods_with_async_mock(self):
        """The CustomMockMixin should mock async magic methods with an AsyncMock."""

        class MyMock(helpers.CustomMockMixin, unittest.mock.MagicMock):
            pass

        mock = MyMock()
        assert isinstance(mock.__aenter__, unittest.mock.AsyncMock)
