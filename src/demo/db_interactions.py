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
        content=message.clean_content,
        author_id=message.author.id,
        channel_id=message.channel.id,
        message_id=message.id
    )
    await record.save()

async def get(db: discobase.Database, interaction: discord.Interaction) -> tuple[BookmarkedMessage]:
    """Get bookmarks for a user, or across the whole server. If getting bookmarks for the whole sever, a search string is required.

    Args:
        interaction

    Returns:
        A tuple of bookmarked messages
    """
    return tuple(await db.tables[BookmarkedMessage.__name__.lower()].find(user_id = interaction.user.id))

async def remove(db: discobase.Database, user: discord.User, mid: discord.Message.id):
    """Remove a bookmark from the list.

    Args:
        user (discord.User): The user to remove the bookmark from.
        mid (discord.Message.id): The message ID of the bookmarked message. The owner of the message must be the user passed in.

    Returns:
        tuple[Result]: The Result (see Result Enum). Will return FAILURE if the user is not the owner of the message.
    """
    pass
