import unittest
from unittest.mock import AsyncMock, MagicMock

import aioresponses
import discord
import pytest

from src.core import settings
from src.helpers.verification import get_user_details, process_identification


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


class TestProcessIdentification(unittest.IsolatedAsyncioTestCase):
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

        # Set up guild.get_role to return appropriate roles
        self.guild.get_role.side_effect = lambda role_id: {
            settings.roles.SHERLOCK_CREATOR: self.sherlock_role,
            settings.roles.CHALLENGE_CREATOR: self.challenge_role,
            settings.roles.BOX_CREATOR: self.box_role,
            settings.roles.HACKER: self.rank_role,
        }.get(role_id)

    @pytest.mark.asyncio
    async def test_process_identification_with_sherlocks(self):
        """Test that Sherlock creator role is assigned when user has sherlocks."""
        htb_user_details = {
            "user_id": "12345",
            "user_name": "test_user",
            "rank": "Hacker",
            "sherlocks": True,
            "challenges": False,
            "boxes": False,
            "is_academy_user": False,
            "vip": False,
            "dedivip": False,
            "hof_position": "unranked",
            "machines": False,
            "team": None,
            "season_rank": None,
            "university": None,
            "certificate": None,
        }

        # Mock the member edit method
        self.member.edit = AsyncMock()
        self.member.nick = "test_user"  # Same as user_name, so no edit needed

        result = await process_identification(htb_user_details, self.member, self.bot)

        # Verify that the Sherlock creator role is in the result
        self.assertIn(self.sherlock_role, result)
        self.guild.get_role.assert_any_call(settings.roles.SHERLOCK_CREATOR)

    @pytest.mark.asyncio
    async def test_process_identification_with_challenges_and_sherlocks(self):
        """Test that both Challenge and Sherlock creator roles are assigned."""
        htb_user_details = {
            "user_id": "12345",
            "user_name": "test_user",
            "rank": "Hacker",
            "sherlocks": True,
            "challenges": True,
            "boxes": False,
            "is_academy_user": False,
            "vip": False,
            "dedivip": False,
            "hof_position": "unranked",
            "machines": False,
            "team": None,
            "season_rank": None,
            "university": None,
            "certificate": None,
        }

        # Mock the member edit method
        self.member.edit = AsyncMock()
        self.member.nick = "test_user"

        result = await process_identification(htb_user_details, self.member, self.bot)

        # Verify that both roles are in the result
        self.assertIn(self.sherlock_role, result)
        self.assertIn(self.challenge_role, result)
        self.guild.get_role.assert_any_call(settings.roles.SHERLOCK_CREATOR)
        self.guild.get_role.assert_any_call(settings.roles.CHALLENGE_CREATOR)

    @pytest.mark.asyncio
    async def test_process_identification_without_sherlocks(self):
        """Test that Sherlock creator role is not assigned when user has no sherlocks."""
        htb_user_details = {
            "user_id": "12345",
            "user_name": "test_user",
            "rank": "Hacker",
            "sherlocks": False,
            "challenges": False,
            "boxes": False,
            "is_academy_user": False,
            "vip": False,
            "dedivip": False,
            "hof_position": "unranked",
            "machines": False,
            "team": None,
            "season_rank": None,
            "university": None,
            "certificate": None,
        }

        # Mock the member edit method
        self.member.edit = AsyncMock()
        self.member.nick = "test_user"

        result = await process_identification(htb_user_details, self.member, self.bot)

        # Verify that the Sherlock creator role is not in the result
        self.assertNotIn(self.sherlock_role, result)
        # Verify get_role was not called for Sherlock creator
        calls = [call[0][0] for call in self.guild.get_role.call_args_list]
        self.assertNotIn(settings.roles.SHERLOCK_CREATOR, calls)

    @pytest.mark.asyncio
    async def test_process_identification_all_creator_roles(self):
        """Test that all creator roles are assigned when user qualifies for all."""
        htb_user_details = {
            "user_id": "12345",
            "user_name": "test_user",
            "rank": "Hacker",
            "sherlocks": True,
            "challenges": True,
            "boxes": True,
            "is_academy_user": False,
            "vip": False,
            "dedivip": False,
            "hof_position": "unranked",
            "machines": True,
            "team": None,
            "season_rank": None,
            "university": None,
            "certificate": None,
        }

        # Mock the member edit method
        self.member.edit = AsyncMock()
        self.member.nick = "test_user"

        result = await process_identification(htb_user_details, self.member, self.bot)

        # Verify that all three creator roles are in the result
        self.assertIn(self.sherlock_role, result)
        self.assertIn(self.challenge_role, result)
        self.assertIn(self.box_role, result)

        # Verify all get_role calls were made
        self.guild.get_role.assert_any_call(settings.roles.SHERLOCK_CREATOR)
        self.guild.get_role.assert_any_call(settings.roles.CHALLENGE_CREATOR)
        self.guild.get_role.assert_any_call(settings.roles.BOX_CREATOR)
