import random

import pytest
from sqlalchemy import delete, insert

from src.database.models import HtbDiscordLink


class TestHtbDiscordLinkModel:

    @pytest.mark.asyncio
    async def test_select(self, session):
        async with session() as session:
            # Define return value for select
            id_ = random.randint(1, 10)
            session.get.return_value = HtbDiscordLink(
                id=id_, account_identifier="AVy2aKzvtEeSsPuDAM23t6Tg2uC46T0rvqpupyPdbnzkYH1GbJBXpEkoyKfe",
                discord_user_id="815223854165240996", htb_user_id="1337"
            )

            link = await session.get(HtbDiscordLink, id_)
            assert link.id == id_
            assert link.discord_user_id_as_int == 815223854165240996
            assert link.htb_user_id_as_int == 1337

            # Check if the method was called with the correct argument
            session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert(self, session):
        async with session() as session:
            # Define return value for insert
            session.add.return_value = None
            session.commit.return_value = None

            query = insert(HtbDiscordLink).values(
                account_identifier="AVy2aKzvtEeSsPuDAM23t6Tg2uC46T0rvqpupyPdbnzkYH1GbJBXpEkoyKfe",
                discord_user_id=815223854165240996, htb_user_id=1337
            )
            session.add(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.add.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, session):
        async with session() as session:
            # Define a HtbDiscordLink record to delete
            link = HtbDiscordLink(
                id=13, account_identifier="AVy2aKzvtEeSsPuDAM23t6Tg2uC46T0rvqpupyPdbnzkYH1GbJBXpEkoyKfe",
                discord_user_id="815223854165240996", htb_user_id="1337"
            )
            session.add(link)
            await session.commit()

            # Define return value for delete
            session.execute.return_value = None
            session.commit.return_value = None

            # Delete the HtbDiscordLink record from the database
            query = delete(HtbDiscordLink).where(HtbDiscordLink.id == link.id)
            await session.execute(query)

            # Check if the methods were called with the correct arguments
            session.execute.assert_called_once_with(query)
            session.commit.assert_called_once()
