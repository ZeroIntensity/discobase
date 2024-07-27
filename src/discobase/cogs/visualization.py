import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from src.discobase.ui import embed


class Visualization(commands.Cog):
    """
    Slash commands to visualize the database's data.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.db = self.bot.db

    @app_commands.command()
    async def hello(self, interaction):
        await interaction.response.send_message("Hello!")

    @app_commands.command(description="View the selected table.")
    @app_commands.describe(name="The name of the table.")
    async def table(
        self,
        interaction: discord.Interaction,
        name: discord.TextChannel
    ) -> None:
        logger.debug("table cmd initialised")
        await interaction.response.send_message(
            content=f"Searching for table `{name}`..."
        )
        table_name = name.name.replace("-", " ").lower()

        try:
            logger.debug("Finding table")
            table = self.db.tables[table_name]
            await interaction.edit_original_response(
                content=f"Table `{table_name}` found! Gathering data..."
            )
        except IndexError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The table `{name.name}` does not exist."
            )
            return

        table_columns = [col.title() for col in table.__disco_keys__]  # convert set to list to enable subscripting

        data: dict[str:list] = {}
        for col in table_columns:
            data[col] = []

        table_values = await table.find()
        logger.info(table_values)

        for game in table_values:
            for col in table_columns:
                data[col].append(getattr(game, col))

        embed_from_content = embed.EmbedFromContent(
            title=f"Table: {table.__disco_name__.title()}",
            content=data,
            headers=table_columns,
            style=embed.EmbedStyle.TABLE
        )
        embeds = embed_from_content.create()

        view = embed.ArrowButtons(content=embeds)

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
        await interaction.response.send_message(
            f"Searching for table `{table.name}`..."
        )
        try:
            col_table = self.db.tables[table.name]
            await interaction.edit_original_response(
                content=f"Table `{col_table.__disco_name__}` found! Gathering data..."
            )
        except IndexError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The table `{table.name}` does not exist."
            )
            return

        try:
            column = [col for col in col_table.__disco_keys__ if col == name][0]
        except (IndexError, ValueError):
            await interaction.edit_original_response(
                content=f"The column `{name}` does not exist in the table `{col_table.__disco_name__}`."
            )
            return

        table_records = await col_table.find()
        column_values = [getattr(record, column) for record in table_records]

        embeds = embed.EmbedFromContent(
            title=f"Column `{name.title()}` from Table `{col_table.__disco_name__.title()}`",
            content=column_values,
            headers=None,
            style=embed.EmbedStyle.COLUMN
        ).create()

        view = embed.ArrowButtons(content=embeds)

        await interaction.edit_original_response(
            embeds=embeds,
            view=view
        )

    @app_commands.command(description="Displays general statistics for the selected table.")
    @app_commands.describe(
        channel="Choose the table you want to fetch statistics from."
    )
    async def status(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        pass

    @app_commands.command(description="Retrieves and displays the schema for the table.")
    @app_commands.describe(
        table="Choose the table you want to retrieve the schema from."
    )
    async def schema(
        self, interaction: discord.Interaction, table: discord.TextChannel
    ) -> None:
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Visualization(bot))
