import discord
from discord.ext import commands
from discord import app_commands


class DatabaseQueries(app_commands.Group):
    """
    All the slash commands for querying information from the database.
    """

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command()
    @app_commands.describe(table='Choose the database you want to perform an update on.',
                           field='Choose the key you want to update.',
                           new_value="Your new information.")
    async def update(
        self,
        inter: discord.Interaction,
         table: discord.TextChannel,
         field: str,
         new_value: str
     ) -> None:
        """
        Modifies a record with a new value.
        """
        pass

    @app_commands.command()
    @app_commands.describe(key="The shared primary key to join the tables on.")
    async def join(
        self,
        inter: discord.Integration,
        first_table: discord.TextChannel,
        second_table: discord.TextChannel,
        key: str
    ) -> None:
        """
        Performs a left-join on two tables.
        """
        pass


class DatabaseCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.tree.add_command(DatabaseQueries(name="query"))


async def setup(bot) -> None:
    await bot.add_cog(DatabaseQueries(bot))
