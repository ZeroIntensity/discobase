import json

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger
from pydantic import ValidationError


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
        logger.info("Called 'insert' command.")
        await interaction.response.send_message(f"Looking for {table.name}...")

        table_name = table.name.replace("-", " ").lower()

        try:
            table_obj = self.db.tables[table_name]  # Table object
        except IndexError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The table '{table_name}' does not exist."
            )
            return

        # Get columns and values in data variable; json format or | separators?
        try:
            await interaction.edit_original_response(
                content=f"Table `{table_name} found! Adding data to table..."
            )
            data_dict: dict = json.loads(data)
        except TypeError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The data you entered was not in json format.\nEntered data: {data}"
            )
            return

        try:
            logger.info("Adding new data to table")
            new_entry = table_obj(**data_dict)
        except ValidationError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"You are missing one of the following columns in your data: {table_obj.__disco_keys__}."
            )
            return

        try:
            await new_entry.save()
        except Exception as e:
            logger.error(e)
            return

        await interaction.edit_original_response(
            content=f"I have inserted `{data}` into `{table_name}` table."
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

    @app_commands.command(description="Deletes a record from a table.")
    @app_commands.describe(
        table="The table from which you want to delete",
        record="The record you want to delete formatted as a json."
    )
    async def delete(
            self,
            interaction: discord.Interaction,
            table: discord.TextChannel,
            record: str
    ):
        pass

    @app_commands.command(description="Deletes all database tables and records.")
    async def reset(
            self,
            interaction: discord.Interaction
    ):
        pass


async def setup(bot) -> None:
    await bot.add_cog(Utility(bot))
