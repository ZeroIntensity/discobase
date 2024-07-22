import discord
from discord import app_commands
from discord.ext import commands


class Visualization(commands.Cog):
    """
    Commands to visualize the database.
    """
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="goodbye", description="Says goodbye!")
    async def goodbye(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Goodbye {interaction.user}!", ephemeral=True)


async def setup(bot) -> None:
    await bot.add_cog(Visualization(bot))
