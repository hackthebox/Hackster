import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord import Forbidden, HTTPException, NotFound

from src.bot import Bot

USER_ID = 123456789


@pytest.fixture(autouse=True)
def enabled_bot_logger(monkeypatch):
    # The alembic migration tests call logging.config.fileConfig, which disables existing loggers.
    monkeypatch.setattr(logging.getLogger("src.bot"), "disabled", False)


def _response(status: int) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.reason = "reason"
    return response


def _bot(fetch_member_error: Exception | None = None, user_result=None) -> MagicMock:
    bot = MagicMock()
    bot.guild = MagicMock()
    bot.guild.fetch_member = AsyncMock(side_effect=fetch_member_error, return_value="member")
    if isinstance(user_result, Exception):
        bot.get_or_fetch_user = AsyncMock(side_effect=user_result)
    else:
        bot.get_or_fetch_user = AsyncMock(return_value=user_result)
    return bot


def _records(caplog):
    return [r for r in caplog.records if r.name == "src.bot"]


class TestGetMemberOrUser:
    @pytest.mark.asyncio
    async def test_returns_member(self, caplog):
        bot = _bot()
        with caplog.at_level(logging.DEBUG, logger="src.bot"):
            result = await Bot.get_member_or_user(bot, bot.guild, USER_ID)

        assert result == "member"
        assert _records(caplog) == []

    @pytest.mark.asyncio
    async def test_member_not_in_guild_falls_back_to_user_without_traceback(self, caplog):
        bot = _bot(NotFound(_response(404), "Unknown Member"), user_result="user")
        with caplog.at_level(logging.DEBUG, logger="src.bot"):
            result = await Bot.get_member_or_user(bot, bot.guild, USER_ID)

        assert result == "user"
        bot.get_or_fetch_user.assert_awaited_once_with(USER_ID)
        records = _records(caplog)
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        assert records[0].getMessage() == f"Could not find guild member with id: {USER_ID}"
        assert records[0].exc_info is None

    @pytest.mark.asyncio
    async def test_member_and_user_not_found_logs_warnings_without_traceback(self, caplog):
        user_error = NotFound(_response(404), "Unknown User")
        bot = _bot(NotFound(_response(404), "Unknown Member"), user_result=user_error)
        with caplog.at_level(logging.DEBUG, logger="src.bot"):
            result = await Bot.get_member_or_user(bot, bot.guild, USER_ID)

        assert result is None
        warnings = [r for r in _records(caplog) if r.levelno == logging.WARNING]
        assert len(warnings) == 2
        assert warnings[0].getMessage() == f"Could not find guild member with id: {USER_ID}"
        assert warnings[0].exc_info is None
        assert warnings[1].getMessage() == f"Could not find user with id: {USER_ID}"
        assert warnings[1].exc_info is None

    @pytest.mark.asyncio
    async def test_forbidden_fetching_member_logs_warning_without_traceback(self, caplog):
        error = Forbidden(_response(403), "Missing Access")
        bot = _bot(error)
        with caplog.at_level(logging.DEBUG, logger="src.bot"):
            result = await Bot.get_member_or_user(bot, bot.guild, USER_ID)

        assert result is None
        bot.get_or_fetch_user.assert_not_awaited()
        records = _records(caplog)
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        assert records[0].getMessage() == f"Unauthorized attempt to fetch member with id: {USER_ID}"
        assert records[0].exc_info is None

    @pytest.mark.asyncio
    async def test_forbidden_fetching_user_after_member_not_found_logs_warnings_without_traceback(self, caplog):
        error = Forbidden(_response(403), "Missing Access")
        bot = _bot(NotFound(_response(404), "Unknown Member"), user_result=error)
        with caplog.at_level(logging.DEBUG, logger="src.bot"):
            result = await Bot.get_member_or_user(bot, bot.guild, USER_ID)

        assert result is None
        warnings = [r for r in _records(caplog) if r.levelno == logging.WARNING]
        assert len(warnings) == 2
        assert warnings[0].getMessage() == f"Could not find guild member with id: {USER_ID}"
        assert warnings[0].exc_info is None
        assert warnings[1].getMessage() == f"Unauthorized attempt to fetch user with id: {USER_ID}"
        assert warnings[1].exc_info is None

    @pytest.mark.asyncio
    async def test_http_error_after_member_not_found_logs_error_with_traceback(self, caplog):
        error = HTTPException(_response(500), "boom")
        bot = _bot(NotFound(_response(404), "Unknown Member"), user_result=error)
        with caplog.at_level(logging.DEBUG, logger="src.bot"):
            result = await Bot.get_member_or_user(bot, bot.guild, USER_ID)

        assert result is None
        errors = [r for r in _records(caplog) if r.levelno == logging.ERROR]
        assert len(errors) == 1
        assert errors[0].getMessage() == f"Discord error while fetching user with id: {USER_ID}"
        assert errors[0].exc_info[1] is error

    @pytest.mark.asyncio
    async def test_http_error_fetching_member_falls_back_to_user(self, caplog):
        error = HTTPException(_response(500), "boom")
        bot = _bot(error, user_result="user")
        with caplog.at_level(logging.DEBUG, logger="src.bot"):
            result = await Bot.get_member_or_user(bot, bot.guild, USER_ID)

        assert result == "user"
        records = _records(caplog)
        assert len(records) == 1
        assert records[0].levelno == logging.ERROR
        assert records[0].getMessage() == f"Discord error while fetching guild member with id: {USER_ID}"
        assert records[0].exc_info[1] is error
