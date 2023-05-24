from src.database.crud.base import CRUDBase
from src.database.models import Ban
from src.database.schemas.ban import BanCreate, BanUpdate


class CRUDItem(CRUDBase[Ban, BanCreate, BanUpdate]):
    pass


ban = CRUDItem(Ban)
