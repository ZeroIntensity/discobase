import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    """
    Commands to alter the database.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="hello", description="Says hello!")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Hello {interaction.user}!", ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(Utility(bot))
