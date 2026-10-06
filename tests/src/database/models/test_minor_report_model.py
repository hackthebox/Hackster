import pytest
from sqlalchemy import delete, insert, select, update
from unittest.mock import MagicMock

from src.database.models import MinorReport


class TestMinorReportModel:

    @pytest.mark.asyncio
    async def test_select(self, session):
        async with session() as session:
            # Define return value for select
            session.get.return_value = MinorReport(
                id=1,
                user_id=123456789,
                reporter_id=987654321,
                suspected_age=15,
                evidence="User stated they are 15 in chat",
                report_message_id=111222333,
                status="pending"
            )

            report = await session.get(MinorReport, 1)
            assert report.id == 1
            assert report.user_id == 123456789
            assert report.status == "pending"

            # Check if the method was called with the correct argument
            session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_insert(self, session):
        async with session() as session:
            # Define return value for insert
            session.add.return_value = None
            session.commit.return_value = None

            query = insert(MinorReport).values(
                user_id=123456789,
                reporter_id=987654321,
                suspected_age=15,
                evidence="User stated they are 15 in chat",
                report_message_id=111222333,
                status="pending"
            )
            session.add(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.add.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status(self, session):
        async with session() as session:
            # Define return value for update
            session.execute.return_value = None
            session.commit.return_value = None

            query = (
                update(MinorReport)
                .where(MinorReport.id == 1)
                .values(status="approved", reviewer_id=555666777)
            )
            await session.execute(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.execute.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_associated_ban(self, session):
        async with session() as session:
            # Define return value for update
            session.execute.return_value = None
            session.commit.return_value = None

            query = (
                update(MinorReport)
                .where(MinorReport.id == 1)
                .values(associated_ban_id=42)
            )
            await session.execute(query)
            await session.commit()

            # Check if the methods were called with the correct arguments
            session.execute.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, session):
        async with session() as session:
            # Define a MinorReport record to delete
            report = MinorReport(
                user_id=123456789,
                reporter_id=987654321,
                suspected_age=15,
                evidence="User stated they are 15 in chat",
                report_message_id=111222333,
                status="pending"
            )
            session.add(report)
            await session.commit()

            # Define return value for delete
            session.execute.return_value = None
            session.commit.return_value = None

            # Delete the MinorReport record from the database
            query = delete(MinorReport).where(MinorReport.id == report.id)
            await session.execute(query)

            # Check if the methods were called with the correct arguments
            session.execute.assert_called_once_with(query)
            session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_by_user_id(self, session):
        async with session() as session:
            # Mock the execute return value
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = MinorReport(
                id=1,
                user_id=123456789,
                reporter_id=987654321,
                suspected_age=15,
                evidence="Evidence",
                report_message_id=111222333,
                status="pending"
            )
            mock_result = MagicMock()
            mock_result.scalars.return_value = mock_scalars
            session.execute.return_value = mock_result

            query = select(MinorReport).where(MinorReport.user_id == 123456789)
            result = await session.execute(query)
            report = result.scalars().first()

            assert report.user_id == 123456789
            session.execute.assert_called_once()
