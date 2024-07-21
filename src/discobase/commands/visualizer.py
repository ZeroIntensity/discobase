import discord
from discord.ext import commands
from discord import app_commands


class DatabaseVisualizer(commands.Cog):
    """
    Slash commands that involve visualizing database information.
    """

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command()
    @app_commands.describe(channel='Choose the database you want to fetch statistics from.')
    async def status(
        self,
        inter: discord.Interaction,
        channel: discord.TextChannel
    ) -> None:
        """
        Displays general statistics.
        """
        pass

    @app_commands.command()
    @app_commands.describe(table='Choose the database you want to retrieve the schema from.')
    async def schema(
        self,
        inter: discord.Interaction,
        table: discord.TextChannel
    ) -> None:
        """
        Fetches the schema of the channel.
        """
        pass


async def setup(bot) -> None:
    await bot.add_cog(DatabaseVisualizer(bot))
