import discord
from models import BookmarkedMessage

import discobase


async def add(interaction: discord.Interaction, message: discord.Message, title: str):
    """Add a message to the bookmarks.

    Args:
        interaction: The `discord.Interaction` that initiated the command.
        message: The `discord.Message` that is being bookmarked
    Returns:
        tuple[Result]: _description_
    """
    record = BookmarkedMessage(
        user_id=interaction.user.id,
        title=title,
        channel_id=message.channel.id,
        message_id=message.id
    )
    await record.save()

async def get(channel_bot: discord.Client, db: discobase.Database, interaction: discord.Interaction) -> list[tuple[str, discord.Message]]:
    """Get bookmarks for a user, or across the whole server. If getting bookmarks for the whole sever, a search string is required.

    Args:
        interaction

    Returns:
        A tuple of bookmarked messages
    """
    records = await db.tables[BookmarkedMessage.__name__.lower()].find(user_id = interaction.user.id)

    return_data = []
    for record in records:
        channel = await channel_bot.fetch_channel(record.channel_id)
        message = await channel.fetch_message(record.message_id)
        return_data.append((record.title, message))
    return return_data

async def remove(db: discobase.Database, user: discord.User, mid: discord.Message.id):
    """Remove a bookmark from the list.

    Args:
        user (discord.User): The user to remove the bookmark from.
        mid (discord.Message.id): The message ID of the bookmarked message. The owner of the message must be the user passed in.

    Returns:
        tuple[Result]: The Result (see Result Enum). Will return FAILURE if the user is not the owner of the message.
    """
    pass
