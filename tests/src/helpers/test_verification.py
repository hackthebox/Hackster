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
            # Mock the profile API call
            m.get(
                f"{settings.API_V4_URL}/user/profile/basic/{account_identifier}",
                status=200,
                payload={"profile": {"some_key": "some_value"}},
            )
            # Mock the content API call
            m.get(
                f"{settings.API_V4_URL}/user/profile/content/{account_identifier}",
                status=200,
                payload={"profile": {"content": {"content_key": "content_value"}}},
            )

            result = await get_user_details(account_identifier)
            expected = {
                "some_key": "some_value",
                "content": {"content_key": "content_value"}
            }
            self.assertEqual(result, expected)

    @pytest.mark.asyncio
    async def test_get_user_details_404(self):
        account_identifier = "some_identifier"

        with aioresponses.aioresponses() as m:
            # Mock the profile API call with404
            m.get(
                f"{settings.API_V4_URL}/user/profile/basic/{account_identifier}",
                status=404,
            )
            # Mock the content API call with404
            m.get(
                f"{settings.API_V4_URL}/user/profile/content/{account_identifier}",
                status=404,
            )

            result = await get_user_details(account_identifier)
            self.assertEqual(result, {"content": {}})

    @pytest.mark.asyncio
    async def test_get_user_details_other_status(self):
        account_identifier = "some_identifier"

        with aioresponses.aioresponses() as m:
            # Mock the profile API call with500
            m.get(
                f"{settings.API_V4_URL}/user/profile/basic/{account_identifier}",
                status=500,
            )
            # Mock the content API call with500
            m.get(
                f"{settings.API_V4_URL}/user/profile/content/{account_identifier}",
                status=500,
            )

            result = await get_user_details(account_identifier)
            self.assertEqual(result, {"content": {}})
