from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.crud.base import CRUDBase
from src.database.models import Ban
from src.database.schemas.ban import BanCreate, BanUpdate


class CRUDBan(CRUDBase[Ban, BanCreate, BanUpdate]):
    """Ban CRUD operations."""

    async def read_for_user(
        self, db: AsyncSession, *, user_id: int, filter_by: Optional[dict] = None, order_by: Optional[str] = None
    ) -> List[Ban]:
        """Read all bans for a user."""
        query = db.query(Ban).filter(Ban.user_id == user_id)
        if filter_by:
            query = query.filter_by(**filter_by)
        if order_by:
            query = query.order_by(getattr(Ban, order_by))
        return await query.all()


ban = CRUDBan(Ban)
