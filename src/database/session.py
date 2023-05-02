import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.core import settings

logger = logging.getLogger(__name__)

connection_string = settings.database.assemble_db_connection()
logger.debug(f"Database connection string: {connection_string}")
async_engine = create_async_engine(connection_string, poolclass=NullPool)
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    async_engine, autoflush=True, expire_on_commit=False, class_=AsyncSession
)
