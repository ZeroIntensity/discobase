import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    """
    All the slash commands for querying information from the database.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        description="Insert new data into a table."
    )
    async def insert(self, interaction: discord.Interaction, table: str, data: str) -> None:
        """
        Discord slash command that inserts new data in the specified Table.

        :param interaction: Represents a Discord interaction.
        :param table: The table which the data is to be inserted into.
        :param data: The data that is to be inserted.
        """
        await interaction.response.send_message(f"I have inserted `{data}` into `{table}` table.")

    @app_commands.command(name="edit", description="Edit a piece of pre-existing data in a table.")
    @app_commands.describe(
        table="The table which the data is to be edited.",
        column="The column in which the data is to be edited.",
        row="The row in which the data is to be edited.",
        new_data="The new data that replaces the old data."
    )
    async def insert(
        self,
        interaction: discord.Interaction,
        table: discord.channel,
        data: str
    ) -> None:
        await interaction.response.send_message(
            f"I have edited data in table `{table}` / column `{column}` / row `{row}` to `{new_data}`."
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
