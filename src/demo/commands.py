import discord
from models import BookmarkedMessage, db


async def bookmark_message_callback(interaction: discord.Interaction, message: discord.Message):
    bookmark = BookmarkedMessage(user_id=interaction.user.id, message_id=message.id)
    await bookmark.save()
    await interaction.response.send_message("Successfully saved the message", ephemeral=True)


@discord.app_commands.command(name="get_bookmarks", description="Retrieve all of your bookmarks")
async def get_bookmarks(interaction: discord.Interaction):
    records = await db._tables[BookmarkedMessage.__name__.lower()].find(user_id=interaction.user.id)
    await interaction.response.send_message(f"{records}")
