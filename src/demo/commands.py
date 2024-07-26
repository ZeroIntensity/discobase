import discord
from models import BookmarkedMessage


async def bookmark_message_callback(interaction: discord.Interaction, message: discord.Message):
    bookmark = BookmarkedMessage(user_id=interaction.user.id, message_id=message.id)
    await bookmark.save()
    await interaction.response.send_message("Successfully saved the message", ephemeral=True)
