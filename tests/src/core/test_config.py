import unittest

from src.core import settings


class TestConfig(unittest.TestCase):
    def test_sherlock_creator_role_in_all_creators(self):
        """Test that SHERLOCK_CREATOR role is included in ALL_CREATORS group."""
        all_creators = settings.role_groups.get("ALL_CREATORS", [])
        self.assertIn(settings.roles.SHERLOCK_CREATOR, all_creators)
        self.assertIn(settings.roles.CHALLENGE_CREATOR, all_creators)
        self.assertIn(settings.roles.BOX_CREATOR, all_creators)

    def test_get_post_or_rank_sherlock_creator(self):
        """Test that get_post_or_rank returns correct role for Sherlock Creator."""
        result = settings.get_post_or_rank("Sherlock Creator")
        self.assertEqual(result, settings.roles.SHERLOCK_CREATOR)

    def test_get_post_or_rank_other_creators(self):
        """Test that get_post_or_rank works for all creator types."""
        test_cases = [
            ("Challenge Creator", settings.roles.CHALLENGE_CREATOR),
            ("Box Creator", settings.roles.BOX_CREATOR),
            ("Sherlock Creator", settings.roles.SHERLOCK_CREATOR),
        ]

        for role_name, expected_role in test_cases:
            with self.subTest(role_name=role_name):
                result = settings.get_post_or_rank(role_name)
                self.assertEqual(result, expected_role)

    def test_get_post_or_rank_invalid_role(self):
        """Test that get_post_or_rank returns None for invalid role."""
        result = settings.get_post_or_rank("Invalid Role")
        self.assertIsNone(result)

    def test_sherlock_creator_role_configured(self):
        """Test that SHERLOCK_CREATOR role is properly configured."""
        self.assertIsNotNone(settings.roles.SHERLOCK_CREATOR)
        self.assertIsInstance(settings.roles.SHERLOCK_CREATOR, int)
