from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# Shared properties
class BanBase(BaseModel):
    user_id: Optional[int] = None
    reason: Optional[str] = None
    moderator_id: Optional[int] = None
    unban_time: Optional[int] = None
    approved: Optional[bool] = None
    unbanned: Optional[bool] = None
    timestamp: Optional[datetime] = None


# Properties to receive on Ban creation
class BanCreate(BanBase):
    user_id: int
    reason: str
    moderator_id: int
    unban_time: int
    approved: bool
    unbanned: Optional[bool] = False
    timestamp: Optional[bool] = datetime.now()


# Properties to receive on Ban update
class BanUpdate(BanBase):
    unban_time: Optional[int] = False
    approved: Optional[bool] = False
    unbanned: Optional[bool] = False


# Properties shared by models stored in DB
class BanInDBBase(BanBase):
    id: int = Field(..., const=True)
    user_id: int
    reason: str
    moderator_id: int
    unban_time: int
    approved: bool
    unbanned: bool
    timestamp: datetime

    class Config:
        orm_mode = True


# Properties to return to client
class Ban(BanInDBBase):
    pass


# Properties properties stored in DB
class BanInDB(BanInDBBase):
    pass
