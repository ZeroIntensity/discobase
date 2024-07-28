import discord
import models
from demobot_config import default_icon

import discobase


async def add(interaction: discord.Interaction, message: discord.Message, title: str) -> models.BookmarkedMessage:
    """Add a message to the bookmarks.

    Args:
        interaction: The `discord.Interaction` that initiated the command
        message: The `discord.Message` that is being bookmarked
        title: The title provided by the modal
    Returns:
        models.BookmarkedMessage: the record that was saved to the database
    """

    avatar_url = message.author.display_avatar.url if message.author.display_avatar is not None else default_icon
    record = models.BookmarkedMessage(
        user_id=interaction.user.id,
        title=title,
        author_name=message.author.name,
        author_avatar_url=avatar_url,
        message_content=message.content
    )
    await record.save()
    return record

async def get(db: discobase.Database, interaction: discord.Interaction) -> list[models.BookmarkedMessage]:
    """Get bookmarks for a user, or across the whole server. If getting bookmarks for the whole sever, a search string is required.

    Args:
        db: Discobase database instance
        interaction: discord interaction that triggered the function

    Returns:
        list[models.BookmarkedMessage]: the list of bookmarks saved by the user
    """
    return await db.tables[models.BookmarkedMessage.__name__.lower()].find(user_id = interaction.user.id)

async def remove(record: models.BookmarkedMessage) -> None:
    """Remove a bookmark from the list.

    Args:
        db: discobase database instance.
        record: the record to delete
    """
    await record.delete()
