import json

import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    """
    All the slash commands for querying information from the database.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = self.bot.db

    @app_commands.command(description="Insert new data into a table.")
    @app_commands.describe(
        table="Choose the table you want to insert the data into.",
        data="The data that is to be inserted.",
    )
    async def insert(
        self,
        interaction: discord.Interaction,
        table: discord.TextChannel,
        data: str,
    ) -> None:
        table_name = table.name.replace("-", " ")
        try:
            table = [table for table in self.bot.db._tables if table.__disco_name__ == table_name][0]  # Table object
        except IndexError:
            await interaction.response.send_message(f"The table '{table_name} does not exist.")
            return

        # Get columns and values in data variable; json format or | separators?
        data_dict: dict = json.loads(data)

        # Check if column name exists
        # If it does then insert the data into it
        # for k, v in data_dict.items():
        #     if table.hasattr(k):
        #         table.k = v
        try:
            new_entry = table(**data_dict)
        except TypeError:
            await interaction.response.send_message(
                f"The keys in your data did not match the column names for {table_name}"
            )
            return

        # save db
        new_entry.save()

        await interaction.response.send_message(
            f"I have inserted `{data}` into `{table}` table."
        )

    @app_commands.command(description="Modifies a record with a new value.")
    @app_commands.describe(
        table="Choose the database you want to perform an update on.",
        field="Choose the key you want to update.",
        new_value="Your new information.",
    )
    async def update(
        self,
        inter: discord.Interaction,
        table: discord.TextChannel,
        field: str,
        new_value: str,
    ) -> None:
        pass

    @app_commands.command(description="Performs a left-join on two tables.")
    @app_commands.describe(key="The shared primary key to join the tables on.")
    async def join(
        self,
        inter: discord.Integration,
        first_table: discord.TextChannel,
        second_table: discord.TextChannel,
        key: str,
    ) -> None:
        pass


async def setup(bot) -> None:
    await bot.add_cog(Utility(bot))
