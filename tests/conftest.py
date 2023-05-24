from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests import helpers


@pytest.fixture
def hashable_mocks():
    return helpers.MockRole, helpers.MockMember, helpers.MockGuild


@pytest.fixture
def bot():
    return helpers.MockBot()


@pytest.fixture
def ctx():
    return helpers.MockContext()


@pytest.fixture
def text_channel():
    return helpers.MockTextChannel()


@pytest.fixture
def user():
    return helpers.MockUser()


@pytest.fixture
def member():
    return helpers.MockMember()


@pytest.fixture
def author():
    return helpers.MockMember()


@pytest.fixture
def guild():
    # Create and return a mocked instance of the Guild class
    return helpers.MockGuild()


@pytest.fixture
def id_():
    return 297552404041814548  # Randomly generated id.


@pytest.fixture
def content():
    return 297552404041814548  # Randomly generated id.


@pytest.fixture
def session(mocker):
    class AsyncContextManager:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            pass

    # Mock the AsyncSession class
    session = AsyncMock(spec=AsyncSession)

    # Mock the async_sessionmaker
    async_sessionmaker_mock = mocker.MagicMock(spec=async_sessionmaker)
    async_sessionmaker_mock.return_value = AsyncContextManager()
    return async_sessionmaker_mock
