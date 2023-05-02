import logging

from discord import Member

from src.core import settings

logger = logging.getLogger(__name__)


def member_is_staff(member: Member) -> bool:
    """Checks if a member has any of the Administrator or Moderator or Staff roles defined in the RoleIDs class."""
    role_ids = set([role.id for role in member.roles])
    staff_role_ids = (
        set(settings.role_groups.get("ALL_ADMINS"))
        | set(settings.role_groups.get("ALL_MODS"))
        | set(settings.role_groups.get("ALL_HTB_STAFF"))
    )
    return bool(role_ids.intersection(staff_role_ids))
