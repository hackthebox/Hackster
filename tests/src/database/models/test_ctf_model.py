import random

import pytest
from sqlalchemy import delete, insert

from src.database.models import Ctf


class TestCtfModel:

    @pytest.mark.asyncio
    async def test_select(self, session):
        async with session() as session:
            # Define return value for select
            id_ = random.randint(1, 10)
            session.get.return_value = Ctf(
                id=id_, name="Test CTF", guild_id="12345678901234567",
                admin_role_id="123456789012345678", participant_role_id="987654321098765432", password="secure_pass123",
            )

            ctf = await session.get(Ctf, id_)
            assert ctf.id == id_
            assert ctf.password == "secure_pass123"

            # Check if the method was called with the correct argument
            session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert(self, session):
        async with session() as session:
            # Define return value for insert
            session.add.return_value = None
            session.commit.return_value = None

            query = insert(Ctf).values(
                name="Test CTF", guild_id="12345678901234567",
                admin_role_id="123456789012345678", participant_role_id="987654321098765432", password="secure_pass123",
            )
            session.add(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.add.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, session):
        async with session() as session:
            # Define a Ctf record to delete
            ctf = Ctf(
                id=13, name="Test CTF", guild_id="12345678901234567",
                admin_role_id="123456789012345678", participant_role_id="987654321098765432", password="secure_pass123",
            )
            session.add(ctf)
            await session.commit()

            # Define return value for delete
            session.execute.return_value = None
            session.commit.return_value = None

            # Delete the Ctf record from the database
            query = delete(Ctf).where(Ctf.id == ctf.id)
            await session.execute(query)

            # Check if the methods were called with the correct arguments
            session.execute.assert_called_once_with(query)
            session.commit.assert_called_once()
