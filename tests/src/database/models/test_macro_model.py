import pytest
from sqlalchemy import delete, insert, update

from src.database.models import Macro


class TestMacroModel:
    @pytest.mark.asyncio
    async def test_select(self, session):
        async with session() as session:
            # Define return value for select
            session.get.return_value = Macro(id=1, user_id=1, name="Test", text="Test", created_at="2022-01-01 00:00:00")

            macro = await session.get(Macro, 1)
            assert macro.id == 1

            # Check if the method was called with the correct argument
            session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert(self, session):
        async with session() as session:
            # Define return value for insert
            session.add.return_value = None
            session.commit.return_value = None

            query = insert(Macro).values(name="Test", text="Test")
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
                update(Macro)
                .where(Macro.id == 1)
                .values(name="Test", text="Test")
            )
            session.execute(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.execute.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, session):
        async with session() as session:
            # Define return value for delete
            session.delete.return_value = None
            session.commit.return_value = None

            query = delete(Macro).where(Macro.id == 1)
            session.delete(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.delete.assert_called_once_with(query)
            session.commit.assert_called_once()
