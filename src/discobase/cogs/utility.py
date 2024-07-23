import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    """
    All the slash commands for querying information from the database.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="insert", description="Insert new data into a table.")
    @app_commands.describe(
        table="The table which the data is to be inserted into.",
        data="The data that is to be inserted."
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
    async def edit(self, interaction: discord.Interaction, table: str, column: str, row: int,
                   new_data: str) -> None:
        """
        Discord slash command that edits a piece of pre-existing data in a table.

        :param interaction: Represents a Discord interaction.
        :param table: The table which the data is to be edited.
        :param column: The column in which the data is to be edited.
        :param row: The row in which the data is to be edited.
        :param new_data: The new data that replaces the old data.
        """
        await interaction.response.send_message(
            f"I have edited data in table `{table}` / column `{column}` / row `{row}` to `{new_data}`."
        )


async def setup(bot) -> None:
    await bot.add_cog(Utility(bot))
