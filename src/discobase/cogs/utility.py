import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    """
    All the slash commands for querying information from the database.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="Insert new data into a table.")
    @app_commands.describe(
        table="Choose the table you want to insert the data into.",
        data="The data that is to be inserted."
    )
    async def insert(
        self,
        interaction: discord.Interaction,
        table: discord.TextChannel,
        data: str
    ) -> None:
        await interaction.response.send_message(
            f"I have inserted `{data}` into `{table}` table."
        )

    @app_commands.command(description="Modifies a record with a new value.")
    @app_commands.describe(
        table='Choose the database you want to perform an update on.',
        field='Choose the key you want to update.',
        new_value="Your new information."
    )
    async def update(
        self,
        inter: discord.Interaction,
        table: discord.TextChannel,
        field: str,
        new_value: str
     ) -> None:
        pass

    @app_commands.command(description="Performs a left-join on two tables.")
    @app_commands.describe(key="The shared primary key to join the tables on.")
    async def join(
        self,
        inter: discord.Integration,
        first_table: discord.TextChannel,
        second_table: discord.TextChannel,
        key: str
    ) -> None:
        pass


async def setup(bot: commands.bot) -> None:
    await bot.add_cog(Utility(bot))
