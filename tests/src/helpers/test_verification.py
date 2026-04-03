import unittest
from unittest.mock import AsyncMock, MagicMock

import aioresponses
import discord
import pytest

from src.core import settings
from src.helpers.verification import get_user_details, process_labs_identification
from tests.helpers import MockRoleManager


class TestGetUserDetails(unittest.IsolatedAsyncioTestCase):
    @pytest.mark.asyncio
    async def test_get_user_details_success(self):
        labs_id = "12345"

        with aioresponses.aioresponses() as m:
            # Mock the profile API call
            m.get(
                f"{settings.API_V4_URL}/user/profile/basic/{labs_id}",
                status=200,
                payload={"profile": {"username": "test_user", "rank": "Hacker"}},
            )
            # Mock the content API call
            m.get(
                f"{settings.API_V4_URL}/user/profile/content/{labs_id}",
                status=200,
                payload={"profile": {"content": {"sherlocks": True, "challenges": False}}},
            )

            result = await get_user_details(labs_id)
            expected = {"username": "test_user", "rank": "Hacker", "content": {"sherlocks": True, "challenges": False}}
            self.assertEqual(result, expected)

    @pytest.mark.asyncio
    async def test_get_user_details_404(self):
        labs_id = "12345"

        with aioresponses.aioresponses() as m:
            # Mock the profile API call with 404
            m.get(
                f"{settings.API_V4_URL}/user/profile/basic/{labs_id}",
                status=404,
            )
            # Mock the content API call - won't be reached due to 404 above
            m.get(
                f"{settings.API_V4_URL}/user/profile/content/{labs_id}",
                status=200,
                payload={"profile": {"content": {}}},
            )

            result = await get_user_details(labs_id)
            # Function returns empty dict with content when basic profile fails
            self.assertEqual(result, {"content": {}})

    @pytest.mark.asyncio
    async def test_get_user_details_other_status(self):
        labs_id = "12345"

        with aioresponses.aioresponses() as m:
            # Mock the profile API call with 500 error
            m.get(
                f"{settings.API_V4_URL}/user/profile/basic/{labs_id}",
                status=500,
            )
            # Mock the content API call - won't be reached due to 500 above
            m.get(
                f"{settings.API_V4_URL}/user/profile/content/{labs_id}",
                status=200,
                payload={"profile": {"content": {}}},
            )

            result = await get_user_details(labs_id)
            # Function returns empty dict with content when basic profile fails
            self.assertEqual(result, {"content": {}})


# Test role IDs used by the role manager mock
_SHERLOCK_ROLE_ID = 100
_CHALLENGE_ROLE_ID = 200
_BOX_ROLE_ID = 300
_HACKER_ROLE_ID = 400


def _make_test_role_manager():
    """Create a role manager that returns test role IDs for creator and rank lookups."""
    rm = MockRoleManager()
    rm.get_role_id = lambda cat, key: {
        ("creator", "Sherlock Creator"): _SHERLOCK_ROLE_ID,
        ("creator", "Challenge Creator"): _CHALLENGE_ROLE_ID,
        ("creator", "Box Creator"): _BOX_ROLE_ID,
    }.get((cat, key))
    rm.get_post_or_rank = lambda what: {
        "Hacker": _HACKER_ROLE_ID,
    }.get(what)
    rm.get_group_ids = lambda cat: {
        "rank": [_HACKER_ROLE_ID],
        "position": [],
    }.get(cat, [])
    rm.get_season_role_id = lambda tier: None
    return rm


class TestProcessLabsIdentification(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.bot = MagicMock()
        self.guild = MagicMock()
        self.member = MagicMock(spec=discord.Member)
        self.member.guild = self.guild
        self.user = MagicMock(spec=discord.User)

        # Mock roles
        self.sherlock_role = MagicMock(spec=discord.Role)
        self.challenge_role = MagicMock(spec=discord.Role)
        self.box_role = MagicMock(spec=discord.Role)
        self.rank_role = MagicMock(spec=discord.Role)

        # Set up guild.get_role to return appropriate roles by test IDs
        self.guild.get_role.side_effect = lambda role_id: {
            _SHERLOCK_ROLE_ID: self.sherlock_role,
            _CHALLENGE_ROLE_ID: self.challenge_role,
            _BOX_ROLE_ID: self.box_role,
            _HACKER_ROLE_ID: self.rank_role,
        }.get(role_id)

        # Set up role manager on bot
        self.bot.role_manager = _make_test_role_manager()

    @pytest.mark.asyncio
    async def test_process_identification_with_sherlocks(self):
        """Test that Sherlock creator role is assigned when user has sherlocks."""
        htb_user_details = {
            "id": "12345",
            "username": "test_user",
            "rank": "Hacker",
            "content": {
                "sherlocks": True,
                "challenges": False,
                "machines": False,
            },
            "isVip": False,
            "isDedicatedVip": False,
            "ranking": "unranked",
        }

        self.member.edit = AsyncMock()
        self.member.nick = "test_user"

        result = await process_labs_identification(htb_user_details, self.member, self.bot)

        self.assertIn(self.sherlock_role, result)
        self.guild.get_role.assert_any_call(_SHERLOCK_ROLE_ID)

    @pytest.mark.asyncio
    async def test_process_identification_with_challenges_and_sherlocks(self):
        """Test that both Challenge and Sherlock creator roles are assigned."""
        htb_user_details = {
            "id": "12345",
            "username": "test_user",
            "rank": "Hacker",
            "content": {
                "sherlocks": True,
                "challenges": True,
                "machines": False,
            },
            "isVip": False,
            "isDedicatedVip": False,
            "ranking": "unranked",
        }

        self.member.edit = AsyncMock()
        self.member.nick = "test_user"

        result = await process_labs_identification(htb_user_details, self.member, self.bot)

        self.assertIn(self.sherlock_role, result)
        self.assertIn(self.challenge_role, result)
        self.guild.get_role.assert_any_call(_SHERLOCK_ROLE_ID)
        self.guild.get_role.assert_any_call(_CHALLENGE_ROLE_ID)

    @pytest.mark.asyncio
    async def test_process_identification_without_sherlocks(self):
        """Test that Sherlock creator role is not assigned when user has no sherlocks."""
        htb_user_details = {
            "user_id": "12345",
            "user_name": "test_user",
            "rank": "Hacker",
            "content": {
                "sherlocks": False,
                "challenges": False,
                "machines": False,
            },
            "isVip": False,
            "isDedicatedVip": False,
            "ranking": "unranked",
        }

        self.member.edit = AsyncMock()
        self.member.nick = "test_user"

        result = await process_labs_identification(htb_user_details, self.member, self.bot)

        self.assertNotIn(self.sherlock_role, result)
        calls = [call[0][0] for call in self.guild.get_role.call_args_list]
        self.assertNotIn(_SHERLOCK_ROLE_ID, calls)

    @pytest.mark.asyncio
    async def test_process_identification_all_creator_roles(self):
        """Test that all creator roles are assigned when user qualifies for all."""
        htb_user_details = {
            "id": "12345",
            "username": "test_user",
            "rank": "Hacker",
            "content": {
                "sherlocks": True,
                "challenges": True,
                "machines": True,
            },
            "isVip": False,
            "isDedicatedVip": False,
            "ranking": "unranked",
        }

        self.member.edit = AsyncMock()
        self.member.nick = "test_user"

        result = await process_labs_identification(htb_user_details, self.member, self.bot)

        self.assertIn(self.sherlock_role, result)
        self.assertIn(self.challenge_role, result)
        self.assertIn(self.box_role, result)

        self.guild.get_role.assert_any_call(_SHERLOCK_ROLE_ID)
        self.guild.get_role.assert_any_call(_CHALLENGE_ROLE_ID)
        self.guild.get_role.assert_any_call(_BOX_ROLE_ID)
