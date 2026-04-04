from unittest.mock import AsyncMock, patch

import pytest

from src.cmds.core import verify
from src.cmds.core.verify import VerifyCog
from tests import helpers


class TestVerifyCog:
    """Test the `Verify` cog."""

    @pytest.mark.asyncio
    async def test_verifycertification_success(self, ctx, bot):
        """Test successful certification verification adds the role."""
        bot.role_manager.get_cert_role_id = lambda abbrev: 5555
        guild_role = helpers.MockRole(id=5555, name="CPTS")
        ctx.guild.get_role = lambda rid: guild_role if rid == 5555 else None
        ctx.author = helpers.MockMember()
        ctx.author.add_roles = AsyncMock()

        with patch(
            "src.cmds.core.verify.process_certification",
            new_callable=AsyncMock,
            return_value="CPTS",
        ):
            cog = VerifyCog(bot)
            await cog.verifycertification.callback(cog, ctx, certid="HTBCERT-123", fullname="John Doe")

        ctx.author.add_roles.assert_awaited_once_with(guild_role)
        ctx.respond.assert_awaited_once()
        assert "Added CPTS" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_verifycertification_cert_role_not_configured(self, ctx, bot):
        """Test that when get_cert_role_id returns None, user is told the role is not configured."""
        # Default MockRoleManager.get_cert_role_id returns None
        with patch(
            "src.cmds.core.verify.process_certification",
            new_callable=AsyncMock,
            return_value="NEWCERT",
        ):
            cog = VerifyCog(bot)
            await cog.verifycertification.callback(cog, ctx, certid="HTBCERT-456", fullname="Jane Doe")

        ctx.respond.assert_awaited_once()
        assert "not yet configured" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_verifycertification_cert_not_found(self, ctx, bot):
        """Test that when process_certification returns False, user is told cert was not found."""
        with patch(
            "src.cmds.core.verify.process_certification",
            new_callable=AsyncMock,
            return_value=False,
        ):
            cog = VerifyCog(bot)
            await cog.verifycertification.callback(cog, ctx, certid="HTBCERT-789", fullname="Unknown")

        ctx.respond.assert_awaited_once()
        assert "Unable to find certification" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_verifycertification_empty_certid(self, ctx, bot):
        """Test that empty certid returns an error."""
        cog = VerifyCog(bot)
        await cog.verifycertification.callback(cog, ctx, certid="", fullname="John")

        ctx.respond.assert_awaited_once()
        assert "must supply a cert id" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_verifycertification_bad_prefix(self, ctx, bot):
        """Test that certid without HTBCERT- prefix returns an error."""
        cog = VerifyCog(bot)
        await cog.verifycertification.callback(cog, ctx, certid="BADPREFIX-123", fullname="John")

        ctx.respond.assert_awaited_once()
        assert "must start with HTBCERT-" in ctx.respond.call_args[0][0]

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        verify.setup(bot)

        bot.add_cog.assert_called_once()
