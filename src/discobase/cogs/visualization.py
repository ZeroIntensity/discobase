import discord
from discord import app_commands
from discord.ext import commands
from loguru import logger

from ..ui import embed as em


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
        self, interaction: discord.Interaction, name: discord.TextChannel
    ) -> None:
        logger.debug("Table slash cmd initialized.")
        await interaction.response.send_message(
            content=f"Searching for table `{name}`..."
        )
        table_name = name.name.replace("-", " ").lower()

        try:
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

        table_columns = [
            col for col in table.__disco_keys__
        ]  # convert set to list to enable subscripting

        data: dict[str:list] = {}
        for col in table_columns:
            data[col] = []

        table_values = await table.find()
        logger.info(table_values)

        await interaction.edit_original_response(
            content="Still gathering data..."
        )

        for game in table_values:
            for col in table_columns:
                data[col].append(getattr(game, col))

        embed_from_content = em.EmbedFromContent(
            title=f"Table: {table.__disco_name__.title()}",
            content=data,
            headers=table_columns,
            style=em.EmbedStyle.TABLE,
        )
        embeds = embed_from_content.create()

        view = em.ArrowButtons(content=embeds)

        await interaction.edit_original_response(
            content="", embed=embeds[0], view=view
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
        logger.debug("Column slash cmd initialized.")
        await interaction.response.send_message(
            f"Searching for table `{table.name}`..."
        )
        try:
            col_table = self.db.tables[table.name]
            await interaction.edit_original_response(
                content=f"Table `{col_table.__disco_name__}` found! Gathering column data..."
            )
        except IndexError as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The table `{table.name}` does not exist."
            )
            return

        try:
            column = [
                col
                for col in col_table.__disco_keys__
                if col.lower() == name.lower()
            ][0]
        except (IndexError, ValueError) as e:
            logger.error(e)
            await interaction.edit_original_response(
                content=f"The column `{name}` does not exist in the table `{col_table.__disco_name__}`."
            )
            return

        table_records = await col_table.find()
        column_values = [getattr(record, column) for record in table_records]

        embeds = em.EmbedFromContent(
            title=f"Column `{name.title()}` from Table `{col_table.__disco_name__.title()}`",
            content=column_values,
            headers=None,
            style=em.EmbedStyle.COLUMN,
        ).create()

        view = em.ArrowButtons(content=embeds)

        await interaction.edit_original_response(
            content="", embed=embeds[0], view=view
        )

    @app_commands.command(
        description="Displays the number of tables and the names of the tables."
    )
    async def tablestats(self, interaction: discord.Interaction) -> None:
        logger.debug("Tablestats slash cmd initialized.")
        await interaction.response.send_message(
            content="Getting table statistics..."
        )
        try:
            tables_names: list | None = None
            tables_names = [table for table in self.db.tables]
            logger.debug(tables_names)
            combined_tables_names = "\n".join(tables_names)

            embed_gen = em.EmbedFromContent(
                title="Tables",
                content=[],
                headers=None,
                style=em.EmbedStyle.DEFAULT,
            ).create()

            embed_gen.add_field(
                name="Number of Tables",
                value=len(self.db.tables),
            )

            embed_gen.add_field(
                name="Names of Tables",
                value=combined_tables_names,
            )

            await interaction.edit_original_response(
                content="", embed=embed_gen
            )
        except Exception as e:
            logger.exception(e)
            return

    @app_commands.command(
        description="Retrieves and displays the schema for the table.",
    )
    @app_commands.describe(
        table="Choose the table you want to retrieve the schema from.",
    )
    async def schema(
        self, interaction: discord.Interaction, table: discord.TextChannel
    ) -> None:
        logger.debug("Schema slash cmd initialized.")
        await interaction.response.send_message(
            content=f"Getting schema for {table.name}..."
        )
        table_info: list | None = None
        table_schema: dict | None = None
        schemas: list[dict] | None = None
        embed_gen: discord.Embed | None = None

        if table.name in self.db.tables:
            table_info = self.db.tables[table.name]
            table_schema = table_info.model_json_schema()
            schemas = [
                table_schema["properties"][disco_key]
                for disco_key in table_info.__disco_keys__
            ]

            embed_gen = em.EmbedFromContent(
                title=f"Table: {table.name.title()}",
                content=schemas,
                headers=None,
                style=em.EmbedStyle.SCHEMA,
            ).create()

            await interaction.edit_original_response(
                content="", embed=embed_gen
            )
        else:
            await interaction.edit_original_response(
                content="There is no table with that name, try creating a table."
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Visualization(bot))
