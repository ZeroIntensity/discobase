import discord
from discord import app_commands
from discord.ext import commands


class Visualization(commands.Cog):
    """
    Commands to visualize the database.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="table", description="Sends a rich embed of the table data.")
    @app_commands.describe(name="Name of the table")
    async def table(self, interaction: discord.Interaction, name: str) -> None:
        """
        Discord slash command that sends the table data as a rich embed.

        :param interaction: Represents a Discord interaction.
        :param name: Name of the table.

        :return: None
        """
        await interaction.response.send_message(f"I am showing you data from the table `{name}`.")

    @app_commands.command(name="column", description="Sends a rich embed of the column data.")
    @app_commands.describe(table="Table the column is in", name="Name of the column")
    async def column(self, interaction: discord.Interaction, table: str, name: str) -> None:
        """
        Discord slash command that sends a rich embed of column data.

        :param interaction: Represents a Discord interaction.
        :param table: Name of the table the column is in.
        :param name: Name of the column.

        :return: None
        """
        await interaction.response.send_message(f"I am showing you data from the column `{name}` in table `{table}`.")


async def setup(bot) -> None:
    await bot.add_cog(Visualization(bot))
