from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import arrow
import pytest
from discord import ApplicationContext, Embed, Interaction, WebhookMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.bot import Bot
from src.cmds.core.macro import MacroCog
from src.core import settings
from src.database.models import Macro


class MockScalarsResult:
    def __init__(self, return_value):
        self.return_value = return_value

    def first(self):
        return self.return_value

    def all(self):
        return self.return_value

@pytest.fixture
def bot():
    return MagicMock(spec=Bot)

@pytest.fixture
def cog(bot):
    return MacroCog(bot)

@pytest.fixture
def ctx():
    mock_ctx = AsyncMock(spec=ApplicationContext)
    mock_ctx.user = MagicMock()
    mock_ctx.user.id = 12345
    mock_ctx.respond = AsyncMock()
    return mock_ctx

@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)

    # Configure the session methods
    session.add = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    session.close = AsyncMock()

    async def mock_scalars(stmt):
        return MockScalarsResult([])

    session.scalars = AsyncMock(side_effect=mock_scalars)

    return session

@pytest.fixture(autouse=True)
def mock_session_maker(mock_session):
    with patch('src.cmds.core.macro.AsyncSessionLocal') as mock:
        cm = AsyncMock()
        cm.__aenter__.return_value = mock_session
        cm.__aexit__.return_value = None
        mock.return_value = cm
        yield mock

@pytest.mark.asyncio
async def test_add_macro_success(cog, ctx, mock_session):
    # Setup
    name = "test_macro"
    text = "This is a test macro"
    # Configure mock to return None for the duplicate check
    mock_session.scalars.return_value.first.return_value = None

    # Execute
    await cog.add.callback(cog, ctx, name=name, text=text)

    # Assert
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    ctx.respond.assert_called_once()
    assert "added" in ctx.respond.call_args[0][0]

@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_add_macro_duplicate_name(cog, ctx, mock_session):
    # Setup
    name = "existing_macro"
    text = "This is a test macro"
    mock_macro = Macro(name=name)  # Create a mock macro

    # Mock the scalars call to simulate finding an existing macro
    async def mock_scalars_call(stmt):
        # Return a result that indicates the macro already exists
        result = AsyncMock()
        result.first.return_value = mock_macro
        return result

    mock_session.scalars.side_effect = mock_scalars_call

    # Execute
    await cog.add.callback(cog, ctx, name=name, text=text)

    # Assert
    assert not mock_session.add.called
    assert not mock_session.commit.called
    ctx.respond.assert_called_once_with(f"Macro with the name '{name}' already exists.", ephemeral=True)

@pytest.mark.asyncio
async def test_remove_macro_success(cog, ctx, mock_session):
    # Setup
    macro_id = 1
    mock_macro = Macro(id=macro_id, name="test")
    mock_session.get = AsyncMock(return_value=mock_macro)

    # Execute
    await cog.remove.callback(cog, ctx, macro_id=macro_id)

    # Assert
    mock_session.delete.assert_called_once_with(mock_macro)
    mock_session.commit.assert_called_once()
    ctx.respond.assert_called_once()
    assert f"#{macro_id}" in ctx.respond.call_args[0][0]

@pytest.mark.asyncio
async def test_remove_macro_not_found(cog, ctx, mock_session):
    # Setup
    macro_id = 999
    mock_session.get = AsyncMock(return_value=None)

    # Execute
    await cog.remove.callback(cog, ctx, macro_id=macro_id)

    # Assert
    assert not mock_session.delete.called
    assert not mock_session.commit.called
    ctx.respond.assert_called_once_with(f"Macro #{macro_id} has not been found.", ephemeral=True)

@pytest.mark.asyncio
async def test_edit_macro_success(cog, ctx, mock_session):
    # Setup
    macro_id = 1
    new_text = "Updated macro text"
    mock_macro = Macro(id=macro_id, name="test", text="old text")
    mock_session.scalars = AsyncMock(return_value=MockScalarsResult(mock_macro))

    # Execute
    await cog.edit.callback(cog, ctx, macro_id=macro_id, text=new_text)

    # Assert
    assert mock_macro.text == new_text
    mock_session.commit.assert_called_once()
    ctx.respond.assert_called_once()
    assert f"#{macro_id}" in ctx.respond.call_args[0][0]

@pytest.mark.asyncio
async def test_edit_macro_not_found(cog, ctx, mock_session):
    # Setup
    macro_id = 999
    mock_session.scalars = AsyncMock(return_value=MockScalarsResult(None))

    # Execute
    await cog.edit.callback(cog, ctx, macro_id=macro_id, text="new text")

    # Assert
    assert not mock_session.commit.called
    ctx.respond.assert_called_once_with(f"Macro #{macro_id} has not been found.", ephemeral=True)

@pytest.mark.asyncio
async def test_list_macros_success(cog, ctx, mock_session):
    # Setup
    macros = [
        Macro(id=1, name="macro1", text="text1"),
        Macro(id=2, name="macro2", text="text2")
    ]

    # Mock the scalars call to directly return the macros
    mock_session.scalars = AsyncMock()
    mock_session.scalars.return_value = AsyncMock(all=lambda: macros)

    # Execute
    await cog.list.callback(cog, ctx)

    # Assert
    ctx.respond.assert_called_once()
    embed = ctx.respond.call_args.kwargs['embed']
    assert isinstance(embed, Embed)
    assert len(embed.fields) == len(macros)

    for macro, field in zip(macros, embed.fields):
        assert str(macro.id) in field.name
        assert macro.name in field.name
        assert macro.text == field.value

@pytest.mark.asyncio
async def test_list_macros_empty(cog, ctx, mock_session):
    # Setup
    mock_session.scalars = AsyncMock(return_value=MockScalarsResult([]))

    # Execute
    await cog.list.callback(cog, ctx)

    # Assert
    ctx.respond.assert_called_once_with("No macros have been added yet.")

@pytest.mark.asyncio
async def test_send_macro_success(cog, ctx, mock_session):
    # Setup
    name = "test_macro"
    text = "Macro text"
    mock_macro = Macro(name=name, text=text)
    mock_session.scalars = AsyncMock(return_value=MockScalarsResult(mock_macro))

    # Execute
    await cog.send.callback(cog, ctx, name=name)

    # Assert
    ctx.respond.assert_called_once_with(text)

@pytest.mark.asyncio
async def test_send_macro_not_found(cog, ctx, mock_session):
    # Setup
    name = "nonexistent"
    mock_session.scalars = AsyncMock(return_value=MockScalarsResult(None))

    # Execute
    await cog.send.callback(cog, ctx, name=name)

    # Assert
    ctx.respond.assert_called_once()
    assert "has not been found" in ctx.respond.call_args[0][0]

@pytest.mark.asyncio
async def test_send_macro_to_channel_success(cog, ctx, mock_session):
    # Setup
    name = "test_macro"
    text = "Macro text"
    mock_macro = Macro(name=name, text=text)
    mock_channel = AsyncMock()
    mock_channel.mention = "#test-channel"
    mock_session.scalars = AsyncMock(return_value=MockScalarsResult(mock_macro))

    # Mock admin role
    ctx.user.roles = [MagicMock(id=settings.role_groups["ALL_ADMINS"][0])]

    # Execute
    await cog.send.callback(cog, ctx, name=name, channel=mock_channel)

    # Assert
    mock_channel.send.assert_called_once_with(text)
    ctx.respond.assert_called_once_with(f"Macro {name} has been sent to #test-channel.", ephemeral=True)

@pytest.mark.asyncio
async def test_send_macro_to_channel_no_permission(cog, ctx, mock_session):
    # Setup
    name = "test_macro"
    text = "Macro text"
    mock_macro = Macro(name=name, text=text)
    mock_channel = AsyncMock()
    mock_session.scalars = AsyncMock(return_value=MockScalarsResult(mock_macro))

    # Mock regular user role
    ctx.user.roles = [MagicMock(id=0)]

    # Execute
    await cog.send.callback(cog, ctx, name=name, channel=mock_channel)

    # Assert
    mock_channel.send.assert_not_called()
    ctx.respond.assert_called_once_with("You don't have permission to send macros in other channels.", ephemeral=True)

@pytest.mark.asyncio
async def test_send_macro_channel_error(cog, ctx, mock_session):
    # Setup
    name = "test_macro"
    text = "Macro text"
    mock_macro = Macro(name=name, text=text)
    mock_channel = AsyncMock()
    mock_channel.send.side_effect = Exception("Channel error")
    mock_channel.mention = "#test-channel"
    mock_session.scalars = AsyncMock(return_value=MockScalarsResult(mock_macro))

    # Mock admin role
    ctx.user.roles = [MagicMock(id=settings.role_groups["ALL_ADMINS"][0])]

    # Execute
    with pytest.raises(Exception, match="Channel error"):
        await cog.send.callback(cog, ctx, name=name, channel=mock_channel)

    # Assert
    mock_channel.send.assert_called_once_with(text)
