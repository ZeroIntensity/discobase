import json

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger
from pydantic import ValidationError

from ..ui import embed as em


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

        await new_entry.save()

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
        interaction: discord.Interaction,
        table: discord.TextChannel,
        column: str,
        value: str,
    ) -> None:
        table_info: list | None = None
        results: list | None = None
        column: str = column.lower()
        results_found: int | None = None
        results_str: str = ""

        logger.debug("Find slash cmd initialised.")
        await interaction.response.send_message(
            content=f"Searching for `{value}`..."
        )

        if table.name in self.bot.db.tables:
            table_info = self.bot.db.tables[table.name]

            if column in table_info.__disco_keys__:
                results = await table_info.find(**{column: value})
                results_found = len(results)
                if results_found > 0:
                    for count, value in enumerate(results, start=1):
                        results_str += f"**{count}**. {str(value)}\n"

                    embed = em.EmbedFromContent(
                        title=f"Search Result - {results_found} Record(s) Found",
                        content=[],
                        headers=None,
                        style=em.EmbedStyle.DEFAULT,
                    ).create()

                    embed.description = results_str

                    await interaction.edit_original_response(
                        content="", embed=embed
                    )
                else:
                    await interaction.edit_original_response(
                        content="The record could not be found."
                    )
        else:
            await interaction.edit_original_response(
                content="Either the table doesn't exist or the column doesn't exist."
            )

    @app_commands.command(description="Modifies a record with a new value.")
    @app_commands.describe(
        table="Choose the table you want to perform an update on.",
        column="Choose the column you want to update.",
        current_value="The current value saved in the column.",
        new_value="Your new information.",
    )
    async def update(
        self,
        interaction: discord.Interaction,
        table: discord.TextChannel,
        column: str,
        current_value: str,
        new_value: str,
    ) -> None:
        logger.debug("Update slash cmd initialized.")
        table_info: list | None = None
        if table.name in self.db.tables:
            await interaction.response.send_message(
                content=f"Table `{table.name}` found! Searching for record..."
            )
            table_info = self.db.tables[table.name]

            try:
                if column in table_info.__disco_keys__:
                    column_name = [
                        col
                        for col in table_info.__disco_keys__
                        if col.lower() == column.lower()
                    ][0]
                    found_table = (
                        await table_info.find(**{column_name: current_value})
                    )[0]
                    setattr(found_table, column_name, new_value)
                    found_table.update()
                    await interaction.edit_original_response(
                        content=f"Successfully updated the value of **{column}** in **{table.name}**."
                    )
                else:
                    await interaction.edit_original_response(
                        content="The column does not exist."
                    )
            except ValidationError:
                await interaction.edit_original_response(
                    content=f"`{new_value}` could not be converted to the field's data type, use `/schema` to "
                    f"check the data type of the column before trying again."
                )
        else:
            await interaction.edit_original_response(
                content="There is no table with that name, try creating a table."
            )

    @app_commands.command(description="Deletes a record from a table.")
    @app_commands.describe(
        table="The table from which you want to delete",
        record="The record you want to delete - formatted as a json.",
    )
    async def delete(
        self,
        interaction: discord.Interaction,
        table: discord.TextChannel,
        record: str,
    ) -> None:
        logger.debug("Delete cmd initialized.")
        await interaction.response.send_message(
            content=f"Searching for table `{table.name}`..."
        )

        try:
            table_obj = self.db.tables[table.name]
            await interaction.edit_original_response(
                content=f"Table `{table_obj.__disco_name__}` found! Searching for record..."
            )
        except IndexError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The table `{table.name}` does not exist."
            )
            return

        try:
            record_dict = json.loads(record)
            table_record = await table_obj.find(**record_dict)
            table_record = table_record[0]
            if table_record is None:
                raise ValueError
            await interaction.edit_original_response(
                content=f"Record `{record}` found! Deleting..."
            )
        except ValueError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"No record found for `{record}`."
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
            content=f"Record `{record}` has been deleted from `{table.name}`!"
        )

    @app_commands.command(
        description="Resets the database, deleting all channels and unloading tables."
    )
    async def reset(self, interaction: discord.Interaction) -> None:
        logger.debug("Reset cmd initialized.")
        await interaction.response.send_message(
            content=f"Resetting the database, `{self.db.name}`..."
        )
        await self.db.clean()
        await interaction.edit_original_response(
            content=f"Database `{self.db.name}` has been reset!"
        )


async def setup(bot) -> None:
    await bot.add_cog(Utility(bot))
