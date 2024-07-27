from typing import Any

import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from ..ui.embed import ArrowButtons, EmbedFromContent, EmbedStyle


class Visualization(commands.Cog):
    """
    Slash commands to visualize the database's data.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = self.bot.db

    @app_commands.command(description="View the selected table.")
    @app_commands.describe(name="The name of the table.")
    async def table(
        self,
        interaction: discord.Interaction,
        name: discord.TextChannel,
    ) -> None:
        await interaction.response.send_message(
            f"Searching for table `{name}`..."
        )
        try:
            table = self.db._tables[name]
            await interaction.edit_original_response(
                content=f"Table `{name}` found! Gathering data..."
            )
        except IndexError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The table `{name}` does not exist."
            )
            return

        try:
            logger.debug("Getting table columns")
            table_columns = table.__disco_keys__
        except Exception as e:
            logger.error(e)
            return

        data: dict[str, Any] = {}

        try:
            logger.debug("Making data dict")
            for col in table_columns:
                data[col] = getattr(table, col)
        except Exception as e:
            logger.error(e)
            return

        try:
            logger.debug("Making embeds")
            embeds = EmbedFromContent(
                title=f"Table: {table.__disco_name__}",
                content=data,
                headers=table_columns,
                style=EmbedStyle.TABLE
            ).create()
        except Exception as e:
            logger.error(e)
            return

        try:
            logger.debug("Making view")
            view = ArrowButtons(content=embeds)
        except Exception as e:
            logger.error(e)
            return

        await interaction.edit_original_response(
            embeds=embeds,
            view=view
        )

    @app_commands.command(description="View the column data.")
    @app_commands.describe(
        table="The name of the table the column is in.",
        name="The name of the column.",
    )
    async def column(
        self,
        interaction: discord.Interaction,
        table: discord.TextChannel,
        name: str,
    ) -> None:
        message = await interaction.response.send_message(
            f"Searching for table `{table.name}`..."
        )
        try:
            col_table = self.db._tables[table.name]
            await message.edit_message(
                f"Table `{col_table.__disco_name__}` found! Gathering data..."
            )
        except IndexError:
            await message.edit_message(
                f"The table `{table.name}` does not exist."
            )
            return

        try:
            table_column = getattr(col_table.__disco_keys__, name)
        except AttributeError:
            await message.edit_message(
                f"The column `{name}` does not exist in the table `{col_table.__disco_name__}`."
            )
            return

        data = [table_column]

        embeds = EmbedFromContent(
            title=f"Column `{name.title()}` From Table `{col_table.__disco_name__.title()}`",
            content=data,
            headers=None,
            style=EmbedStyle.COLUMN
        ).create()

        view = ArrowButtons(content=embeds)

        await message.edit_message(
            embeds=embeds,
            view=view
        )

    @app_commands.command()
    @app_commands.describe(
        description="Displays general statistics for the selected table.",
        channel="Choose the table you want to fetch statistics from.",
    )
    async def status(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        pass

    @app_commands.command()
    @app_commands.describe(
        description="Retrieves and displays the schema for the table.",
        table="Choose the table you want to retrieve the schema from.",
    )
    async def schema(
        self, interaction: discord.Interaction, table: discord.TextChannel
    ) -> None:
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Visualization(bot))
