import db_interactions
import discord
from config import db


async def bookmark_message_callback(interaction: discord.Interaction, message: discord.Message):
    await db_interactions.add(interaction, message, "Bookmarked Message")
    await interaction.response.send_message("Successfully saved the message", ephemeral=True)


@discord.app_commands.command(name="get_bookmarks", description="Retrieve all of your bookmarks")
async def get_bookmarks(interaction: discord.Interaction):
    records = await db_interactions.get(db, interaction)
    await interaction.response.send_message(f"{records}")

@discord.app_commands.command(name="clean_database")
async def clean_database(interaction: discord.Interaction):
    await db.clean()
    await interaction.response.send_message("database has been cleaned")
