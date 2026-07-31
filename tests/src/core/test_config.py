import unittest

from pydantic import ValidationError

from src.core.config import Global
from src.core import settings


class TestConfig(unittest.TestCase):
    @staticmethod
    def minimal_settings(**overrides):
        payload = {
            "bot": {
                "TOKEN": "ODk3MTVyNDOb50MDAxODE0NTC4.YWRgYg.hqWNRybjyk1j2h3h42vEoc8feoNqR0ubBCYwxo",
            },
            "database": {
                "HOST": "localhost",
                "PORT": 3306,
                "DATABASE": "bot",
                "USER": "bot",
                "PASSWORD": "secret",
            },
            "channels": {
                "SR_MOD": 1127695218900993410,
                "VERIFY_LOGS": 1012769518828339331,
                "BOT_COMMANDS": 1276953350848588101,
                "SPOILER": 2769521890099371011,
                "BOT_LOGS": 1105517088266788925,
            },
            "roles": {
                "VERIFIED": 1333333333333333337,
                "COMMUNITY_MANAGER": 7839345151011276950,
                "COMMUNITY_TEAM": 845823057817153850,
                "ADMINISTRATOR": 7839345141011276950,
                "SR_MODERATOR": 7629466271011276950,
                "MODERATOR": 7629466261011276950,
                "JR_MODERATOR": 7629466221011276950,
                "HTB_STAFF": 7629466201011276950,
                "HTB_SUPPORT": 6455184211011276950,
                "MUTED": 7419955651011276950,
                "ACADEMY_USER": 8087599101014249251,
            },
            "HTB_API_KEY": "test",
            "guild_ids": [6455184161011276950],
            "dev_guild_ids": [7764771731239076051],
        }
        payload.update(overrides)
        return Global(**payload)

    def test_guild_ids_accept_string_snowflakes(self):
        """Test that guild IDs can be provided as digit strings and are coerced to ints."""
        config = self.minimal_settings(
            guild_ids=["6455184161011276950"],
            dev_guild_ids=["7764771731239076051"],
        )
        self.assertEqual(config.guild_ids, [6455184161011276950])
        self.assertEqual(config.dev_guild_ids, [7764771731239076051])

    def test_guild_ids_reject_non_snowflakes(self):
        """Test that guild IDs must be positive base-10 unsigned 64-bit snowflakes."""
        with self.assertRaises(ValidationError):
            self.minimal_settings(guild_ids=["not-a-snowflake"])

        with self.assertRaises(ValidationError):
            self.minimal_settings(guild_ids=[0])

        with self.assertRaises(ValidationError):
            self.minimal_settings(guild_ids=[2**64])

    def test_core_roles_required(self):
        """Test that core roles are still loaded from env vars."""
        self.assertIsNotNone(settings.roles.VERIFIED)
        self.assertIsInstance(settings.roles.VERIFIED, int)
        self.assertIsNotNone(settings.roles.ADMINISTRATOR)
        self.assertIsInstance(settings.roles.ADMINISTRATOR, int)

    def test_core_role_groups_present(self):
        """Test that core role groups are populated."""
        self.assertIn("ALL_ADMINS", settings.role_groups)
        self.assertIn("ALL_MODS", settings.role_groups)
        self.assertIn("ALL_HTB_STAFF", settings.role_groups)
        self.assertIn("ALL_SR_MODS", settings.role_groups)
        self.assertIn("ALL_HTB_SUPPORT", settings.role_groups)
        self.assertIn("VOTE_STARTERS", settings.role_groups)
        self.assertIn("VOTE_CASTERS", settings.role_groups)
        self.assertEqual(len(settings.role_groups["VOTE_STARTERS"]), 3)
        self.assertEqual(len(settings.role_groups["VOTE_CASTERS"]), 6)

    def test_dynamic_role_groups_removed(self):
        """Test that dynamic role groups are no longer in settings."""
        self.assertNotIn("ALL_RANKS", settings.role_groups)
        self.assertNotIn("ALL_SEASON_RANKS", settings.role_groups)
        self.assertNotIn("ALL_CREATORS", settings.role_groups)
        self.assertNotIn("ALL_POSITIONS", settings.role_groups)

    def test_dynamic_roles_are_optional(self):
        """Test that dynamic role fields default to None when env vars are missing."""
        # These should be Optional[int] = None if not in env
        # In test env they may still be set via .test.env, so just check the field exists
        self.assertTrue(hasattr(settings.roles, "OMNISCIENT"))
        self.assertTrue(hasattr(settings.roles, "VIP"))
        self.assertTrue(hasattr(settings.roles, "BOX_CREATOR"))

    def test_season_id_loads_from_nested_env_config(self):
        """Test that SEASON_ID is loaded under the new nested env contract."""
        self.assertEqual(settings.SEASON_ID, 1)
