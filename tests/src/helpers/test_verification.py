import unittest

import aioresponses
import pytest

from src.core import settings
from src.helpers.verification import get_user_details


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
