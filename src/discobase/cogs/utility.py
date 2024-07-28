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

    @app_commands.command(
        description="Insert new data into a table."
    )
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
        await interaction.response.send_message(
            content=f"Looking for `{table.name}`..."
        )

        table_name = table.name.replace("-", " ").lower()

        try:
            table_obj = self.db.tables[table_name]  # Table object
        except IndexError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The table `{table_name}` does not exist."
            )
            return

        try:
            await interaction.edit_original_response(
                content=f"Table `{table_name}` found! Adding data to table..."
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
                content=f"You are missing one of the following columns in your data: `{table_obj.__disco_keys__}`."
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

    @app_commands.command(
        description="Finds a record with the specific column and value in the table."
    )
    @app_commands.describe(
        table="The name of the table the column is in.",
        column="The name of the column.",
        value="The value to search for.",
    )
    async def find(
        self,
        interaction: discord.Integration,
        table: discord.TextChannel,
        column: str,
        value: str,
    ) -> None:
        await interaction.response.send_message(
            content=f"Searching for `{value}`..."
        )

        table_info: list | None = None
        results: list | None = None
        column: str = column.lower()
        results_found: int | None = None
        results_str: str | None = None

        try:
            if table.name in self.bot.db.tables:
                table_info = self.bot.db.tables[table.name]

                if column in table_info.__disco_keys__:
                    results = table_info.find(**{column: value})
                    results_found = len(results)
                    if results_found > 0:
                        embed: discord.Embed = discord.Embed(
                            title=f"Search Result - {results_found} Record(s) Found",
                            color=discord.Color.blurple,
                        )

                        for count, value in enumerate(results, start=1):
                            results_str += f"**{count}**. {str(value)}\n"

                        embed.description(results_str)
                        interaction.response.send_message(embed=embed)
                    else:
                        interaction.response.send_message(
                            "The record could not be found."
                        )
            else:
                interaction.response.send_message(
                    "Either the table doesn't exist or the column doesn't exist."
                )
        except Exception as e:
            logger.exception(e)

    @app_commands.command(
        description="Performs a left-join on two tables."
    )
    @app_commands.describe(
        key="The shared primary key to join the tables on."
    )
    async def join(
        self,
        inter: discord.Integration,
        first_table: discord.TextChannel,
        second_table: discord.TextChannel,
        key: str,
    ) -> None:
        pass

    @app_commands.command(
        description="Deletes a record from a table."
    )
    @app_commands.describe(
        table="The table from which you want to delete",
        record="The record you want to delete - formatted as a json."
    )
    async def delete(
            self,
            interaction: discord.Interaction,
            table: discord.TextChannel,
            record: str
    ) -> None:
        logger.debug("Delete cmd initialized.")
        await interaction.response.send_message(
            content=f"Searching for table `{table.name}`..."
        )

        try:
            table_obj = self.db.tables[table.name]
            await interaction.edit_original_response(
                content=f"Table `{table_obj.__disco_name__} found! Searching for record..."
            )
        except IndexError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The table '{table.name}' does not exist."
            )
            return

        try:
            record_dict = json.loads(record)
            table_record = table_obj.find(**record_dict)
            if table_record is None:
                raise ValueError
        except ValueError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"No record found for {record}."
            )
            return
        except TypeError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The record you entered was not in json format.\nEntered record: {record}"
            )
            return

        await table_record.delete()

        await interaction.edit_original_response(
            content=f"Record `{record}` has been deleted from {table.name}!"
        )

    @app_commands.command(
        description="Resets the database, deleting all channels and unloading tables."
    )
    async def reset(
            self,
            interaction: discord.Interaction
    ) -> None:
        await interaction.response.send_message(
            content=f"Resetting the database, `{self.db.name}`..."
        )
        await self.db.clean()
        await interaction.edit_original_response(
            content=f"Database `{self.db.name}` has been reset!"
        )


async def setup(bot) -> None:
    await bot.add_cog(Utility(bot))
