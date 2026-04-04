import logging
from typing import Optional

from sqlalchemy import delete, select

from src.database.models.dynamic_role import DynamicRole, RoleCategory
from src.database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Legacy alias: CBBH was renamed to CWES
_CERT_ALIASES = {"CBBH": "CWES"}

# Explicit search order for get_post_or_rank to avoid ambiguity on key collisions.
_POST_OR_RANK_SEARCH_ORDER = [
    RoleCategory.POSITION,
    RoleCategory.RANK,
    RoleCategory.SUBSCRIPTION_LABS,
    RoleCategory.SUBSCRIPTION_ACADEMY,
    RoleCategory.CREATOR,
]

# Mapping from env var field names to (category, key) for dual-read fallback.
# Only used during transition period; will be removed in follow-up PR.
_ENV_FALLBACK_MAP: dict[str, tuple[RoleCategory, str]] = {
    "OMNISCIENT": (RoleCategory.RANK, "Omniscient"),
    "GURU": (RoleCategory.RANK, "Guru"),
    "ELITE_HACKER": (RoleCategory.RANK, "Elite Hacker"),
    "PRO_HACKER": (RoleCategory.RANK, "Pro Hacker"),
    "HACKER": (RoleCategory.RANK, "Hacker"),
    "SCRIPT_KIDDIE": (RoleCategory.RANK, "Script Kiddie"),
    "NOOB": (RoleCategory.RANK, "Noob"),
    "VIP": (RoleCategory.SUBSCRIPTION_LABS, "vip"),
    "VIP_PLUS": (RoleCategory.SUBSCRIPTION_LABS, "dedivip"),
    "SILVER_ANNUAL": (RoleCategory.SUBSCRIPTION_ACADEMY, "Silver Annual"),
    "GOLD_ANNUAL": (RoleCategory.SUBSCRIPTION_ACADEMY, "Gold Annual"),
    "BOX_CREATOR": (RoleCategory.CREATOR, "Box Creator"),
    "CHALLENGE_CREATOR": (RoleCategory.CREATOR, "Challenge Creator"),
    "SHERLOCK_CREATOR": (RoleCategory.CREATOR, "Sherlock Creator"),
    "RANK_ONE": (RoleCategory.POSITION, "1"),
    "RANK_TEN": (RoleCategory.POSITION, "10"),
    "SEASON_HOLO": (RoleCategory.SEASON, "Holo"),
    "SEASON_PLATINUM": (RoleCategory.SEASON, "Platinum"),
    "SEASON_RUBY": (RoleCategory.SEASON, "Ruby"),
    "SEASON_SILVER": (RoleCategory.SEASON, "Silver"),
    "SEASON_BRONZE": (RoleCategory.SEASON, "Bronze"),
    "ACADEMY_CWES": (RoleCategory.ACADEMY_CERT, "CWES"),
    "ACADEMY_CPTS": (RoleCategory.ACADEMY_CERT, "CPTS"),
    "ACADEMY_CDSA": (RoleCategory.ACADEMY_CERT, "CDSA"),
    "ACADEMY_CWEE": (RoleCategory.ACADEMY_CERT, "CWEE"),
    "ACADEMY_CAPE": (RoleCategory.ACADEMY_CERT, "CAPE"),
    "ACADEMY_CJCA": (RoleCategory.ACADEMY_CERT, "CJCA"),
    "ACADEMY_CWPE": (RoleCategory.ACADEMY_CERT, "CWPE"),
}


class RoleManager:
    """Manages dynamic Discord roles backed by the database with an in-memory cache."""

    def __init__(self, fallback_roles=None):
        self._roles: dict[str, dict[str, DynamicRole]] = {}
        self._cert_by_integer_id: dict[int, DynamicRole] = {}
        self._cert_by_full_name: dict[str, DynamicRole] = {}
        self._fallback_roles = fallback_roles
        self._loaded = False

    async def load(self) -> None:
        """Load all dynamic roles from DB into memory.

        On failure: if a previous cache exists, keeps it and logs a warning.
        If no previous cache (first load), raises the exception.
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.scalars(select(DynamicRole))
                roles = result.all()

            new_roles: dict[str, dict[str, DynamicRole]] = {}
            new_cert_by_id: dict[int, DynamicRole] = {}
            new_cert_by_name: dict[str, DynamicRole] = {}

            for role in roles:
                cat = role.category.value
                if cat not in new_roles:
                    new_roles[cat] = {}
                new_roles[cat][role.key] = role

                if role.category == RoleCategory.ACADEMY_CERT:
                    if role.cert_integer_id is not None:
                        new_cert_by_id[role.cert_integer_id] = role
                    if role.cert_full_name:
                        new_cert_by_name[role.cert_full_name] = role

            # Apply env var fallbacks for any missing roles (transition period)
            if self._fallback_roles:
                self._apply_fallbacks(new_roles)

            self._roles = new_roles
            self._cert_by_integer_id = new_cert_by_id
            self._cert_by_full_name = new_cert_by_name
            self._loaded = True

            total = sum(len(v) for v in self._roles.values())
            logger.info(f"Loaded {total} dynamic roles from database")

        except Exception:
            if self._loaded:
                logger.warning("Failed to reload dynamic roles from DB, keeping previous cache", exc_info=True)
            else:
                logger.error("Failed to load dynamic roles from DB on first attempt", exc_info=True)
                raise

    def _apply_fallbacks(self, roles: dict[str, dict[str, DynamicRole]]) -> None:
        """Fill in missing roles from env var fallback values (transition period only)."""
        for field_name, (category, key) in _ENV_FALLBACK_MAP.items():
            cat = category.value
            if cat in roles and key in roles[cat]:
                continue

            value = getattr(self._fallback_roles, field_name, None)
            if value is None:
                continue

            if cat not in roles:
                roles[cat] = {}

            # Create a lightweight stand-in (not persisted to DB)
            fallback = DynamicRole()
            fallback.key = key
            fallback.discord_role_id = value
            fallback.category = category
            fallback.display_name = key
            roles[cat][key] = fallback
            logger.debug(f"Using env var fallback for dynamic role: {category.value}/{key}")

    async def reload(self) -> None:
        """Reload roles from DB. Alias for load(), used after CRUD operations."""
        await self.load()

    # ── Single role lookups ──────────────────────────────────────────

    def get_role_id(self, category: str, key: str) -> Optional[int]:
        """Get a single role's Discord ID by category and key. Returns None if not configured."""
        role = self._roles.get(category, {}).get(key)
        return role.discord_role_id if role else None

    def get_cert_role_id(self, cert_abbrev: str) -> Optional[int]:
        """Get academy cert role by abbreviation (CPTS, CWES, etc.). Handles CBBH legacy alias."""
        resolved = _CERT_ALIASES.get(cert_abbrev, cert_abbrev)
        return self.get_role_id(RoleCategory.ACADEMY_CERT.value, resolved)

    def get_academy_cert_role(self, certificate_id: int) -> Optional[int]:
        """Get academy cert role by platform integer ID (2, 3, 4, etc.)."""
        role = self._cert_by_integer_id.get(certificate_id)
        return role.discord_role_id if role else None

    def get_cert_abbrev_by_full_name(self, full_name: str) -> Optional[str]:
        """Get cert abbreviation by full platform name. Replaces the hardcoded process_certification() mapping."""
        role = self._cert_by_full_name.get(full_name)
        return role.key if role else None

    def get_rank_role_id(self, rank_name: str) -> Optional[int]:
        """Get rank role by name (Omniscient, Guru, etc.)."""
        return self.get_role_id(RoleCategory.RANK.value, rank_name)

    def get_season_role_id(self, tier: str) -> Optional[int]:
        """Get season tier role (Holo, Platinum, etc.)."""
        return self.get_role_id(RoleCategory.SEASON.value, tier)

    # ── Cross-category lookup ────────────────────────────────────────

    def get_post_or_rank(self, what: str) -> Optional[int]:
        """Replaces settings.get_post_or_rank(). Searches position, rank, subscriptions, creator."""
        for category in _POST_OR_RANK_SEARCH_ORDER:
            role_id = self.get_role_id(category.value, what)
            if role_id is not None:
                return role_id
        return None

    # ── Group lookups ────────────────────────────────────────────────

    def get_group_ids(self, category: str) -> list[int]:
        """Get all Discord role IDs for a category. Returns [] if none configured."""
        return [r.discord_role_id for r in self._roles.get(category, {}).values()]

    # ── Joinable roles ───────────────────────────────────────────────

    def get_joinable_roles(self) -> dict[str, tuple[int, str]]:
        """Get joinable roles as {display_name: (discord_role_id, description)}."""
        joinable = self._roles.get(RoleCategory.JOINABLE.value, {})
        return {
            r.display_name: (r.discord_role_id, r.description or "")
            for r in joinable.values()
        }

    # ── CRUD operations ──────────────────────────────────────────────

    async def add_role(
        self,
        key: str,
        category: RoleCategory,
        discord_role_id: int,
        display_name: str,
        description: str | None = None,
        cert_full_name: str | None = None,
        cert_integer_id: int | None = None,
    ) -> DynamicRole:
        """Add a new dynamic role to the database and reload cache."""
        role = DynamicRole()
        role.key = key
        role.category = category
        role.discord_role_id = discord_role_id
        role.display_name = display_name
        role.description = description
        role.cert_full_name = cert_full_name
        role.cert_integer_id = cert_integer_id

        async with AsyncSessionLocal() as session:
            session.add(role)
            await session.commit()
            await session.refresh(role)

        await self.reload()
        return role

    async def remove_role(self, category: RoleCategory, key: str) -> bool:
        """Remove a dynamic role from the database and reload cache. Returns True if found."""
        async with AsyncSessionLocal() as session:
            stmt = delete(DynamicRole).where(
                DynamicRole.key == key,
                DynamicRole.category == category,
            )
            result = await session.execute(stmt)
            await session.commit()
            deleted = result.rowcount > 0

        if deleted:
            await self.reload()
        return deleted

    async def update_role(self, category: RoleCategory, key: str, discord_role_id: int) -> Optional[DynamicRole]:
        """Update a role's Discord ID. Returns updated role or None if not found."""
        async with AsyncSessionLocal() as session:
            stmt = select(DynamicRole).where(
                DynamicRole.key == key,
                DynamicRole.category == category,
            )
            result = await session.scalars(stmt)
            role = result.first()
            if not role:
                return None
            role.discord_role_id = discord_role_id
            await session.commit()
            await session.refresh(role)

        await self.reload()
        return role

    async def list_roles(self, category: RoleCategory | None = None) -> list[DynamicRole]:
        """List all dynamic roles, optionally filtered by category."""
        async with AsyncSessionLocal() as session:
            stmt = select(DynamicRole)
            if category:
                stmt = stmt.where(DynamicRole.category == category)
            stmt = stmt.order_by(DynamicRole.category, DynamicRole.key)
            result = await session.scalars(stmt)
            return list(result.all())
