import pytest
from sqlalchemy import delete, insert, update

from src.database.models import Ban


class TestBanModel:

    @pytest.mark.asyncio
    async def test_select(self, session):
        async with session() as session:
            # Define return value for select
            session.get.return_value = Ban(id=1, user_id=1, reason="No reason", moderator_id=2)

            ban = await session.get(Ban, 1)
            assert ban.id == 1

            # Check if the method was called with the correct argument
            session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert(self, session):
        async with session() as session:
            # Define return value for insert
            session.add.return_value = None
            session.commit.return_value = None

            query = insert(Ban).values(name="John Doe", age=30)
            session.add(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.add.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert_unban_time_bigint(self, session):
        async with session() as session:
            # Define return value for insert
            session.add.return_value = None
            session.commit.return_value = None

            query = insert(Ban).values(name="John Doe", age=30, unban_time=2153337603)
            session.add(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.add.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update(self, session):
        async with session() as session:
            # Define return value for update
            session.execute.return_value = None
            session.commit.return_value = None

            query = (
                update(Ban)
                .where(Ban.id == 1)
                .values(name="Jane Doe")
            )
            await session.execute(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.execute.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, session):
        async with session() as session:
            # Define a Ban record to delete
            ban = Ban(user_id=1, reason="No reason", moderator_id=2)
            session.add(ban)
            await session.commit()

            # Define return value for delete
            session.execute.return_value = None
            session.commit.return_value = None

            # Delete the Ban record from the database
            query = delete(Ban).where(Ban.id == ban.id)
            await session.execute(query)

            # Check if the methods were called with the correct arguments
            session.execute.assert_called_once_with(query)
            session.commit.assert_called_once()
