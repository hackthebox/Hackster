"""
One-time seed script to populate the dynamic_role table from environment variables.

Usage:
    ENV_PATH=.env python -m scripts.seed_dynamic_roles
    # or for test env:
    python -m scripts.seed_dynamic_roles  (defaults to .test.env)
"""

import asyncio
import logging
import os
import sys

from dotenv import dotenv_values
from sqlalchemy.dialects.mysql import insert

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.models.dynamic_role import DynamicRole, RoleCategory  # noqa: E402
from src.database.session import AsyncSessionLocal  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# (env_var_suffix, category, key, display_name, extra_kwargs)
SEED_DATA = [
    # Ranks
    ("OMNISCIENT", RoleCategory.RANK, "Omniscient", "Omniscient", {}),
    ("GURU", RoleCategory.RANK, "Guru", "Guru", {}),
    ("ELITE_HACKER", RoleCategory.RANK, "Elite Hacker", "Elite Hacker", {}),
    ("PRO_HACKER", RoleCategory.RANK, "Pro Hacker", "Pro Hacker", {}),
    ("HACKER", RoleCategory.RANK, "Hacker", "Hacker", {}),
    ("SCRIPT_KIDDIE", RoleCategory.RANK, "Script Kiddie", "Script Kiddie", {}),
    ("NOOB", RoleCategory.RANK, "Noob", "Noob", {}),
    # Subscriptions - Labs
    ("VIP", RoleCategory.SUBSCRIPTION_LABS, "vip", "VIP", {}),
    ("VIP_PLUS", RoleCategory.SUBSCRIPTION_LABS, "dedivip", "VIP+", {}),
    # Subscriptions - Academy
    ("SILVER_ANNUAL", RoleCategory.SUBSCRIPTION_ACADEMY, "Silver Annual", "Silver Annual", {}),
    ("GOLD_ANNUAL", RoleCategory.SUBSCRIPTION_ACADEMY, "Gold Annual", "Gold Annual", {}),
    # Creators
    ("BOX_CREATOR", RoleCategory.CREATOR, "Box Creator", "Box Creator", {}),
    ("CHALLENGE_CREATOR", RoleCategory.CREATOR, "Challenge Creator", "Challenge Creator", {}),
    ("SHERLOCK_CREATOR", RoleCategory.CREATOR, "Sherlock Creator", "Sherlock Creator", {}),
    # Positions
    ("RANK_ONE", RoleCategory.POSITION, "1", "Top 1", {}),
    ("RANK_TEN", RoleCategory.POSITION, "10", "Top 10", {}),
    # Seasons
    ("SEASON_HOLO", RoleCategory.SEASON, "Holo", "Holo", {}),
    ("SEASON_PLATINUM", RoleCategory.SEASON, "Platinum", "Platinum", {}),
    ("SEASON_RUBY", RoleCategory.SEASON, "Ruby", "Ruby", {}),
    ("SEASON_SILVER", RoleCategory.SEASON, "Silver", "Silver", {}),
    ("SEASON_BRONZE", RoleCategory.SEASON, "Bronze", "Bronze", {}),
    # Academy Certs (with cert_full_name and cert_integer_id)
    ("ACADEMY_CWES", RoleCategory.ACADEMY_CERT, "CWES", "Certified Web Exploitation Specialist", {
        "cert_full_name": "HTB Certified Web Exploitation Specialist",
        "cert_integer_id": 2,
    }),
    ("ACADEMY_CPTS", RoleCategory.ACADEMY_CERT, "CPTS", "Certified Penetration Testing Specialist", {
        "cert_full_name": "HTB Certified Penetration Testing Specialist",
        "cert_integer_id": 3,
    }),
    ("ACADEMY_CDSA", RoleCategory.ACADEMY_CERT, "CDSA", "Certified Defensive Security Analyst", {
        "cert_full_name": "HTB Certified Defensive Security Analyst",
        "cert_integer_id": 4,
    }),
    ("ACADEMY_CWEE", RoleCategory.ACADEMY_CERT, "CWEE", "Certified Web Exploitation Expert", {
        "cert_full_name": "HTB Certified Web Exploitation Expert",
        "cert_integer_id": 5,
    }),
    ("ACADEMY_CAPE", RoleCategory.ACADEMY_CERT, "CAPE", "Certified Active Directory Pentesting Expert", {
        "cert_full_name": "HTB Certified Active Directory Pentesting Expert",
        "cert_integer_id": 6,
    }),
    ("ACADEMY_CJCA", RoleCategory.ACADEMY_CERT, "CJCA", "Certified Junior Cybersecurity Associate", {
        "cert_full_name": "HTB Certified Junior Cybersecurity Associate",
        "cert_integer_id": 7,
    }),
    ("ACADEMY_CWPE", RoleCategory.ACADEMY_CERT, "CWPE", "Certified Wi-Fi Pentesting Expert", {
        "cert_full_name": "HTB Certified Wi-Fi Pentesting Expert",
        "cert_integer_id": 8,
    }),
]

# Joinable roles: multiple display names can share the same env var / discord_role_id.
# Format: (env_var_suffix, key, display_name, description)
JOINABLE_SEED_DATA = [
    ("UNICTF2022", "Cyber Apocalypse", "Cyber Apocalypse", "Pinged for CTF Announcements"),
    ("UNICTF2022", "Business CTF", "Business CTF", "Pinged for CTF Announcements"),
    ("UNICTF2022", "University CTF", "University CTF", "Pinged for CTF Announcements"),
    ("NOAH_GANG", "Noah Gang", "Noah Gang", "Get pinged when Fugl posts pictures of his cute bird"),
    ("BUDDY_GANG", "Buddy Gang", "Buddy Gang", "Get pinged when Legacyy posts pictures of his cute dog"),
    ("RED_TEAM", "Red Team", "Red Team", "Red team fans. Also gives access to the Red and Blue team channels"),
    ("BLUE_TEAM", "Blue Team", "Blue Team", "Blue team fans. Also gives access to the Red and Blue team channels"),
]


async def _upsert_role(session, values: dict) -> None:
    """Insert or update a dynamic role using MariaDB upsert."""
    stmt = insert(DynamicRole).values(values)
    # On duplicate key, update all fields except the unique key (key, category)
    stmt = stmt.on_duplicate_key_update(
        discord_role_id=stmt.inserted.discord_role_id,
        display_name=stmt.inserted.display_name,
        description=stmt.inserted.description,
        cert_full_name=stmt.inserted.cert_full_name,
        cert_integer_id=stmt.inserted.cert_integer_id,
    )
    await session.execute(stmt)


async def seed(env_file: str) -> None:
    env_values = dotenv_values(env_file)
    logger.info(f"Loaded env from {env_file} ({len(env_values)} values)")

    upserted = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        # Seed standard dynamic roles
        for env_suffix, category, key, display_name, extra in SEED_DATA:
            env_var = f"ROLE_{env_suffix}"
            role_id_str = env_values.get(env_var)
            if not role_id_str:
                logger.warning(f"Skipping {env_var}: not found in {env_file}")
                skipped += 1
                continue

            values = {
                "key": key,
                "discord_role_id": int(role_id_str),
                "category": category,
                "display_name": display_name,
                "description": None,
                "cert_full_name": extra.get("cert_full_name"),
                "cert_integer_id": extra.get("cert_integer_id"),
            }

            await _upsert_role(session, values)
            upserted += 1
            logger.info(f"  {category.value}/{key} = {role_id_str}")

        # Seed joinable roles
        for env_suffix, key, display_name, description in JOINABLE_SEED_DATA:
            env_var = f"ROLE_{env_suffix}"
            role_id_str = env_values.get(env_var)
            if not role_id_str:
                logger.warning(f"Skipping joinable {env_var}/{key}: not found in {env_file}")
                skipped += 1
                continue

            values = {
                "key": key,
                "discord_role_id": int(role_id_str),
                "category": RoleCategory.JOINABLE,
                "display_name": display_name,
                "description": description,
                "cert_full_name": None,
                "cert_integer_id": None,
            }

            await _upsert_role(session, values)
            upserted += 1
            logger.info(f"  joinable/{key} = {role_id_str}")

        await session.commit()

    logger.info(f"Seeding complete: {upserted} upserted, {skipped} skipped")


if __name__ == "__main__":
    env_file = os.environ.get("ENV_PATH", ".test.env")
    asyncio.run(seed(env_file))
