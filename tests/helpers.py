from __future__ import annotations

import itertools
from asyncio import AbstractEventLoop
from collections import ChainMap, defaultdict
from typing import Iterable, Optional, Union
from unittest import mock

import discord
import discord.mixins
from aiohttp import ClientSession
from discord import Interaction
from discord.commands import ApplicationContext
from discord.types.member import MemberWithUser

from src.bot import Bot


class HashableMixin(discord.mixins.EqualityComparable):
    """
    Mixin that provides similar hashing and equality functionality as discord.py's `Hashable` mixin.

    Note: discord.py`s `Hashable` mixin bit-shifts `self.id` (`>> 22`); to prevent hash-collisions
    for the relative small `id` integers we generally use in tests, this bit-shift is omitted.
    """

    def __hash__(self):
        return self.id


class ColourMixin:
    """A mixin for Mocks that provides the aliasing of (accent_)color->(accent_)colour like discord.py does."""

    def __init__(self):
        self.colour = None
        self.accent_colour = None

    @property
    def color(self) -> discord.Colour:
        """Alias of the `colour` attribute."""
        return self.colour

    @color.setter
    def color(self, color: discord.Colour) -> None:
        """Alias of the `colour` attribute."""
        self.colour = color

    @property
    def accent_color(self) -> discord.Colour:
        """Alias of the `accent_colour` attribute."""
        return self.accent_colour

    @accent_color.setter
    def accent_color(self, color: discord.Colour) -> None:
        """Alias of the `accent_colour` attribute."""
        self.accent_colour = color


class CustomMockMixin:
    """
    Provides common functionality for our custom Mock types.

    The `_get_child_mock` method automatically returns an AsyncMock for coroutine methods of the mock
    object. As discord.py also uses synchronous methods that nonetheless return coroutine objects, the
    class attribute `additional_spec_asyncs` can be overwritten with an iterable containing additional
    attribute names that should also mocked with an AsyncMock instead of a regular MagicMock/Mock. The
    class method `spec_set` can be overwritten with the object that should be uses as the specification
    for the mock.

    Mock/MagicMock subclasses that use this mixin only need to define `__init__` method if they need to
    implement custom behavior.
    """

    child_mock_type = mock.MagicMock
    discord_id = itertools.count(0)
    spec_set = None
    additional_spec_asyncs = None

    def __init__(self, **kwargs):
        name = kwargs.pop('name', None)  # `name` has special meaning for Mock classes, so we need to set it manually.
        super().__init__(spec_set=self.spec_set, **kwargs)

        if self.additional_spec_asyncs:
            self._spec_asyncs.extend(self.additional_spec_asyncs)

        if name:
            self.name = name

    def _get_child_mock(self, **kwargs) -> Union[mock.MagicMock, mock.AsyncMock]:
        """
        Overwrite of the `_get_child_mock` method to stop the propagation of our custom mock classes.

        Mock objects automatically create children when you access an attribute or call a method on them. By default,
        the class of these children is the type of the parent itself. However, this would mean that the children created
        for our custom mock types would also be instances of that custom mock type. This is not desirable, as attributes
        of, e.g., a `Bot` object are not `Bot` objects themselves. The Python docs for `unittest.mock` hint that
        overwriting this method is the best way to deal with that.

        This override will look for an attribute called `child_mock_type` and use that as the type of the child mock.
        """
        _new_name = kwargs.get("_new_name")
        if _new_name in self.__dict__['_spec_asyncs']:
            return mock.AsyncMock(**kwargs)

        _type = type(self)
        if issubclass(_type, mock.MagicMock) and _new_name in mock._async_method_magics:
            # Any asynchronous magic becomes an AsyncMock
            klass = mock.AsyncMock
        else:
            klass = self.child_mock_type

        if self._mock_sealed:
            attribute = "." + kwargs["name"] if "name" in kwargs else "()"
            mock_name = self._extract_mock_name() + attribute
            raise AttributeError(mock_name)

        return klass(**kwargs)


# Create a guild instance to get a realistic Mock of `discord.Guild`
guild_data = {
    'id': 1,
    'name': 'guild',
    'verification_level': 2,
    'default_notications': 1,
    'afk_timeout': 100,
    'icon': "icon.png",
    'banner': 'banner.png',
    'mfa_level': 1,
    'splash': 'splash.png',
    'system_channel_id': 464033278631084042,
    'description': 'mocking is fun',
    'max_presences': 10_000,
    'max_members': 100_000,
    'preferred_locale': 'UTC',
    'owner_id': 1,
    'afk_channel_id': 464033278631084042,
}
guild_instance = discord.Guild(data=guild_data, state=mock.MagicMock())


class MockGuild(CustomMockMixin, mock.Mock, HashableMixin):
    """
    A `Mock` subclass to mock `discord.Guild` objects.

    A MockGuild instance will follow the specifications of a `discord.Guild` instance. This means
    that if the code you're testing tries to access an attribute or method that normally does not
    exist for a `discord.Guild` object this will raise an `AttributeError`. This is to make sure our
    tests fail if the code we're testing uses a `discord.Guild` object in the wrong way.

    One restriction of that is that if the code tries to access an attribute that normally does not
    exist for `discord.Guild` instance but was added dynamically, this will raise an exception with
    the mocked object. To get around that, you can set the non-standard attribute explicitly for the
    instance of `MockGuild`:
    """
    spec_set = guild_instance
    additional_spec_asyncs = None

    def __init__(self, roles: Optional[Iterable[MockRole]] = None, **kwargs) -> None:
        default_kwargs = {'id': next(self.discord_id), 'members': []}
        super().__init__(**ChainMap(kwargs, default_kwargs))

        self.roles = [MockRole(name="@everyone", position=1, id=0)]
        if roles:
            self.roles.extend(roles)


# Create a Role instance to get a realistic Mock of `discord.Role`
role_data = {'name': 'role', 'id': 1}
# noinspection PyTypeChecker
role_instance = discord.Role(guild=guild_instance, state=mock.MagicMock(), data=role_data)


class MockRole(CustomMockMixin, mock.Mock, ColourMixin, HashableMixin):
    """
    A Mock subclass to mock `discord.Role` objects.

    Instances of this class will follow the specifications of `discord.Role` instances. For more
    information, see the `MockGuild` docstring.
    """
    spec_set = role_instance

    def __init__(self, **kwargs) -> None:
        default_kwargs = {
            'id': next(self.discord_id),
            'name': 'role',
            'position': 1,
            'colour': discord.Colour(0xdeadbf),
            'permissions': discord.Permissions(),
        }
        super().__init__(**ChainMap(kwargs, default_kwargs))

        if isinstance(self.colour, int):
            self.colour = discord.Colour(self.colour)

        if isinstance(self.permissions, int):
            self.permissions = discord.Permissions(self.permissions)

        if 'mention' not in kwargs:
            self.mention = f'&{self.name}'

    def __lt__(self, other):
        """Simplified position-based comparisons similar to those of `discord.Role`."""
        return self.position < other.position

    def __ge__(self, other):
        """Simplified position-based comparisons similar to those of `discord.Role`."""
        return self.position >= other.position


# Create a Member instance to get a realistic Mock of `discord.Member`
member_data = {'user': 'lemon', 'roles': [1]}
state_mock = mock.MagicMock()
member_instance = discord.Member(data=MemberWithUser(**member_data), guild=guild_instance, state=state_mock)


class MockMember(CustomMockMixin, mock.Mock, ColourMixin, HashableMixin):
    """
    A Mock subclass to mock Member objects.

    Instances of this class will follow the specifications of `discord.Member` instances. For more
    information, see the `MockGuild` docstring.
    """
    spec_set = member_instance

    def __init__(self, roles: Optional[Iterable[MockRole]] = None, **kwargs) -> None:
        default_kwargs = {'name': 'member', 'id': next(self.discord_id), 'bot': False, "pending": False}
        super().__init__(**ChainMap(kwargs, default_kwargs))

        self.roles = [MockRole(name="@everyone", position=1, id=0)]
        if roles:
            self.roles.extend(roles)
        self.top_role = max(self.roles)

        if 'mention' not in kwargs:
            self.mention = f"@{self.name}"


# Create a User instance to get a realistic Mock of `discord.User`
_user_data_mock = defaultdict(mock.MagicMock)
user_instance = discord.User(
    data=mock.MagicMock(get=mock.Mock(side_effect=_user_data_mock.get)),
    state=mock.MagicMock()
)


class MockUser(CustomMockMixin, mock.Mock, ColourMixin, HashableMixin):
    """
    A Mock subclass to mock User objects.

    Instances of this class will follow the specifications of `discord.User` instances. For more
    information, see the `MockGuild` docstring.
    """
    spec_set = user_instance

    def __init__(self, **kwargs) -> None:
        default_kwargs = {'name': 'user', 'id': next(self.discord_id), 'bot': False}
        super().__init__(**ChainMap(kwargs, default_kwargs))

        if 'mention' not in kwargs:
            self.mention = f"@{self.name}"


def _get_mock_loop() -> mock.Mock:
    """Return a mocked asyncio.AbstractEventLoop."""
    loop = mock.create_autospec(spec=AbstractEventLoop, spec_set=True)

    # Since calling `create_task` on our MockBot does not actually schedule the coroutine object
    # as a task in the asyncio loop, this `side_effect` calls `close()` on the coroutine object
    # to prevent "has not been awaited"-warnings.
    def mock_create_task(coroutine):
        coroutine.close()
        return mock.Mock()

    loop.create_task.side_effect = mock_create_task

    return loop


class MockBot(CustomMockMixin, mock.MagicMock):
    """
    A MagicMock subclass to mock Bot objects.

    Instances of this class will follow the specifications of `discord.ext.commands.Bot` instances.
    For more information, see the `MockGuild` docstring.
    """
    spec_set = Bot(mock=True)
    additional_spec_asyncs = ("wait_for",)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.loop = _get_mock_loop()
        self.http_session = mock.create_autospec(spec=ClientSession, spec_set=True)


# Create a TextChannel instance to get a realistic MagicMock of `discord.TextChannel`
channel_data = {
    'id': 1,
    'type': 'TextChannel',
    'name': 'channel',
    'parent_id': 1234567890,
    'topic': 'topic',
    'position': 1,
    'nsfw': False,
    'last_message_id': 1,
}
state = mock.MagicMock()
guild = mock.MagicMock()
# noinspection PyTypeChecker
text_channel_instance = discord.TextChannel(state=state, guild=guild, data=channel_data)

channel_data["type"] = "VoiceChannel"
# noinspection PyTypeChecker
voice_channel_instance = discord.VoiceChannel(state=state, guild=guild, data=channel_data)


class MockTextChannel(CustomMockMixin, mock.Mock, HashableMixin):
    """
    A MagicMock subclass to mock TextChannel objects.

    Instances of this class will follow the specifications of `discord.TextChannel` instances. For
    more information, see the `MockGuild` docstring.
    """
    spec_set = text_channel_instance
    additional_spec_asyncs = ("send", "edit")

    def __init__(self, **kwargs) -> None:
        default_kwargs = {'id': next(self.discord_id), 'name': 'channel', 'guild': MockGuild()}
        super().__init__(**ChainMap(kwargs, default_kwargs))

        if 'mention' not in kwargs:
            self.mention = f"#{self.name}"


class MockVoiceChannel(CustomMockMixin, mock.Mock, HashableMixin):
    """
    A MagicMock subclass to mock VoiceChannel objects.

    Instances of this class will follow the specifications of `discord.VoiceChannel` instances. For
    more information, see the `MockGuild` docstring.
    """
    spec_set = voice_channel_instance

    def __init__(self, **kwargs) -> None:
        default_kwargs = {'id': next(self.discord_id), 'name': 'channel', 'guild': MockGuild()}
        super().__init__(**ChainMap(kwargs, default_kwargs))

        if 'mention' not in kwargs:
            self.mention = f"#{self.name}"


# Create data for the DMChannel instance
state = mock.MagicMock()
me = mock.MagicMock()
dm_channel_data = {"id": 1, "recipients": [mock.MagicMock()]}
# noinspection PyTypeChecker
dm_channel_instance = discord.DMChannel(me=me, state=state, data=dm_channel_data)


class MockDMChannel(CustomMockMixin, mock.Mock, HashableMixin):
    """
    A MagicMock subclass to mock TextChannel objects.

    Instances of this class will follow the specifications of `discord.TextChannel` instances. For
    more information, see the `MockGuild` docstring.
    """
    spec_set = dm_channel_instance

    def __init__(self, **kwargs) -> None:
        default_kwargs = {'id': next(self.discord_id), 'recipient': MockUser(), "me": MockUser()}
        super().__init__(**ChainMap(kwargs, default_kwargs))


# Create CategoryChannel instance to get a realistic MagicMock of `discord.CategoryChannel`
category_channel_data = {
    'id': 1,
    'type': discord.ChannelType.category,
    'name': 'category',
    'position': 1,
}

state = mock.MagicMock()
guild = mock.MagicMock()
# noinspection PyTypeChecker
category_channel_instance = discord.CategoryChannel(
    state=state, guild=guild, data=category_channel_data
)


class MockCategoryChannel(CustomMockMixin, mock.Mock, HashableMixin):
    def __init__(self, **kwargs) -> None:
        default_kwargs = {'id': next(self.discord_id)}
        super().__init__(**ChainMap(default_kwargs, kwargs))


# Create a Message instance to get a realistic MagicMock of `discord.Message`
message_data = {
    'id': 1,
    'webhook_id': 431341013479718912,
    'attachments': [],
    'embeds': [],
    'application': 'Python Discord',
    'activity': 'mocking',
    'channel': mock.MagicMock(),
    'edited_timestamp': '2019-10-14T15:33:48+00:00',
    'type': 'message',
    'pinned': False,
    'mention_everyone': False,
    'tts': None,
    'content': 'content',
    'nonce': None,
}
state = mock.MagicMock()
channel = mock.MagicMock()
message_instance = discord.Message(state=state, channel=channel, data=message_data)


# Create a Context instance to get a realistic MagicMock of `discord.ext.commands.Context`
# noinspection PyTypeChecker

class Context(ApplicationContext):
    """Patch certain code breaking functions."""

    def __init__(self, bot: Bot, interaction: Interaction):
        super().__init__(bot, interaction)

    def send_response(self):
        """Avoid calling `self.response.is_done` to avoid breaking error."""
        return self.interaction.response.send_message


context_instance = Context(bot=MockBot(), interaction=mock.MagicMock())
context_instance.invoked_from_error_handler = None


class MockContext(CustomMockMixin, mock.MagicMock):
    """
    A MagicMock subclass to mock Context objects.

    Instances of this class will follow the specifications of `discord.ext.commands.Context`
    instances. For more information, see the `MockGuild` docstring.
    """
    spec_set = context_instance

    additional_spec_asyncs = ("respond",)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.me = kwargs.get('me', MockMember())
        self.bot = kwargs.get('src', MockBot())
        self.guild = kwargs.get('guild', MockGuild())
        self.author = kwargs.get('author', MockMember())
        self.channel = kwargs.get('channel', MockTextChannel())
        self.message = kwargs.get('message', MockMessage())
        self.respond = mock.AsyncMock()


dummy_attachment = {
    "id": 123456789012345678,  # Snowflake, typically a large integer
    "filename": "example_image.png",
    "size": 1024,  # Size in bytes
    "url": "http://example.com/example_image.png",
    "proxy_url": "http://example.com/proxy_example_image.png",
    "height": 600,  # Optional, int or None
    "width": 800,  # Optional, int or None
    "content_type": "image/png",  # Optional, string
    "spoiler": False,  # Optional, boolean
    "duration_secs": None,  # Optional, float or None
    "waveform": None,  # Optional, string or None
    "flags": 0  # Optional, int
}
attachment_instance = discord.Attachment(data=dummy_attachment, state=mock.MagicMock())


class MockAttachment(CustomMockMixin, mock.MagicMock):
    """
    A MagicMock subclass to mock Attachment objects.

    Instances of this class will follow the specifications of `discord.Attachment` instances. For
    more information, see the `MockGuild` docstring.
    """
    spec_set = attachment_instance


class MockMessage(CustomMockMixin, mock.MagicMock):
    """
    A MagicMock subclass to mock Message objects.

    Instances of this class will follow the specifications of `discord.Message` instances. For more
    information, see the `MockGuild` docstring.
    """
    spec_set = message_instance

    def __init__(self, **kwargs) -> None:
        default_kwargs = {'attachments': []}
        super().__init__(**ChainMap(kwargs, default_kwargs))
        self.author = kwargs.get('author', MockMember())
        self.channel = kwargs.get('channel', MockTextChannel())


emoji_data = {'require_colons': True, 'managed': True, 'id': 1, 'name': 'hyperlemon'}
# noinspection PyTypeChecker
emoji_instance = discord.Emoji(guild=MockGuild(), state=mock.MagicMock(), data=emoji_data)


class MockEmoji(CustomMockMixin, mock.MagicMock):
    """
    A MagicMock subclass to mock Emoji objects.

    Instances of this class will follow the specifications of `discord.Emoji` instances. For more
    information, see the `MockGuild` docstring.
    """
    spec_set = emoji_instance

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.guild = kwargs.get('guild', MockGuild())


partial_emoji_instance = discord.PartialEmoji(animated=False, name='guido')


class MockPartialEmoji(CustomMockMixin, mock.MagicMock):
    """
    A MagicMock subclass to mock PartialEmoji objects.

    Instances of this class will follow the specifications of `discord.PartialEmoji` instances. For
    more information, see the `MockGuild` docstring.
    """
    spec_set = partial_emoji_instance


# noinspection PyTypeChecker
reaction_instance = discord.Reaction(message=MockMessage(), data={'me': True}, emoji=MockEmoji())


class MockReaction(CustomMockMixin, mock.MagicMock):
    """
    A MagicMock subclass to mock Reaction objects.

    Instances of this class will follow the specifications of `discord.Reaction` instances. For
    more information, see the `MockGuild` docstring.
    """
    spec_set = reaction_instance

    def __init__(self, **kwargs) -> None:
        _users = kwargs.pop("users", [])
        super().__init__(**kwargs)
        self.emoji = kwargs.get('emoji', MockEmoji())
        self.message = kwargs.get('message', MockMessage())

        user_iterator = mock.AsyncMock()
        user_iterator.__aiter__.return_value = _users
        self.users.return_value = user_iterator

        self.__str__.return_value = str(self.emoji)


webhook_instance = discord.Webhook(data=mock.MagicMock(), session=mock.MagicMock())


class MockAsyncWebhook(CustomMockMixin, mock.MagicMock):
    """
    A MagicMock subclass to mock Webhook objects using an AsyncWebhookAdapter.

    Instances of this class will follow the specifications of `discord.Webhook` instances. For
    more information, see the `MockGuild` docstring.
    """
    spec_set = webhook_instance
    additional_spec_asyncs = ("send", "edit", "delete", "execute")
