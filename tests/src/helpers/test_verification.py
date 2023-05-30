import unittest
from unittest.mock import AsyncMock, MagicMock

import aioresponses
import pytest

from src.core import settings
from src.helpers.verification import _assign_hof_role, _check_for_ban, get_user_details


class TestGetUserDetails(unittest.IsolatedAsyncioTestCase):

    @pytest.mark.asyncio
    async def test_get_user_details_success(self):
        account_identifier = "some_identifier"

        with aioresponses.aioresponses() as m:
            m.get(
                f"{settings.API_URL}/discord/identifier/{account_identifier}?secret={settings.HTB_API_SECRET}",
                status=200,
                payload={"some_key": "some_value"},
            )

            result = await get_user_details(account_identifier)
            self.assertEqual(result, {"some_key": "some_value"})

    @pytest.mark.asyncio
    async def test_get_user_details_404(self):
        account_identifier = "some_identifier"

        with aioresponses.aioresponses() as m:
            m.get(
                f"{settings.API_URL}/discord/identifier/{account_identifier}?secret={settings.HTB_API_SECRET}",
                status=404,
            )

            result = await get_user_details(account_identifier)
            self.assertIsNone(result)

    @pytest.mark.asyncio
    async def test_get_user_details_other_status(self):
        account_identifier = "some_identifier"

        with aioresponses.aioresponses() as m:
            m.get(
                f"{settings.API_URL}/discord/identifier/{account_identifier}?secret={settings.HTB_API_SECRET}",
                status=500,
            )

            result = await get_user_details(account_identifier)
            self.assertIsNone(result)


@pytest.mark.parametrize(
    "htb_hof_position, expected_role",
    [
        ("1", "1"),
        ("5", "5"),
        ("10", "10"),
        ("25", "25"),
        ("50", "50"),
        ("100", "100"),
        ("101", None),
        ("0", None),
    ],
)
@pytest.mark.asyncio
async def test_assign_hof_role(htb_hof_position, expected_role):
    # Call the function under test
    result = await _assign_hof_role(htb_hof_position)

    # Assert the expected behavior
    assert result == expected_role


@pytest.mark.asyncio
async def test_check_for_ban(mock_aiohttp_client_session):
    # Mock the response from the API
    mock_response = {
        "banned": True,
        "ends_at": "2023-06-01 12:00:00"
    }

    # Mock the session.get method
    mock_get = mock_aiohttp_client_session.get
    mock_get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)
    mock_get.return_value.__aenter__.return_value.status = 200
    mock_get.return_value.__aenter__.return_value.content = AsyncMock(return_value=b"Mocked Content")

    # Call the function under test
    result = await _check_for_ban("user123")

    # Assert the expected behavior
    assert result == mock_response

    # Assert the session.get method was called with the correct URL
    expected_url = f"{settings.API_URL}/discord/user123/banned?secret={settings.HTB_API_SECRET}"
    mock_get.assert_called_once_with(expected_url)


@pytest.mark.asyncio
async def test_check_for_ban_non_ok_status(mock_aiohttp_client_session):
    # Mock a non-OK response from the API
    mock_response = AsyncMock()
    mock_response.status = 404
    mock_response.content = AsyncMock(return_value=b"Not Found")

    # Mock the session.get method
    mock_get = mock_aiohttp_client_session.get
    mock_get.return_value.__aenter__.return_value = mock_response

    # Call the function under test
    result = await _check_for_ban("user123")

    # Assert the expected behavior
    assert result is None

    # Assert the session.get method was called with the correct URL
    expected_url = f"{settings.API_URL}/discord/user123/banned?secret={settings.HTB_API_SECRET}"
    mock_get.assert_called_once_with(expected_url)


@pytest.fixture
def mock_aiohttp_client_session(monkeypatch):
    # Mock the aiohttp.ClientSession context manager
    mock_session = MagicMock()
    mock_session.return_value.__aenter__.return_value = mock_session
    monkeypatch.setattr("aiohttp.ClientSession", mock_session)
    return mock_session
