import discord
from discord import app_commands
from discord.ext import commands


class Visualization(commands.Cog):
    """
    Slash commands to visualize the database's data.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(description="View the selected table.")
    @app_commands.describe(name="The name of the table.")
    async def table(
        self,
        interaction: discord.Interaction,
        name: discord.TextChannel,
    ) -> None:
        await interaction.response.send_message(
            f"I am showing you data from the table `{name}`."
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
            f"I am showing you data from the column `{name}`"
            f" in table `{table}`."
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