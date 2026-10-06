import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core import settings

logger = logging.getLogger(__name__)

connection_string = settings.database.assemble_db_connection(async_=True)
async_engine = create_async_engine(connection_string, poolclass=NullPool)
# repr() of a SQLAlchemy URL masks the password.
logger.debug(f"Database URL: {async_engine.url!r}")
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine, autoflush=True, expire_on_commit=False, class_=AsyncSession
)
