import bookmark_ui
import db_interactions
import discord
from demobot_config import db
from discord.ext import commands


class Bookmark(discord.app_commands.Group):
    def __init__(self, bot: commands.Bot):
        super().__init__(name="bookmark")
        self.bot = bot
        self.bookmark_context_menu = discord.app_commands.ContextMenu(name="Bookmark", callback=self.bookmark_message_callback)
        self.bot.tree.add_command(self.bookmark_context_menu)

    async def bookmark_message_callback(self, interaction: discord.Interaction, message: discord.Message) -> None:
        """
        The callback in charge of creating a bookmark when the context menu is selected

        Args:
            interaction: discord.Interaction that triggered the save
            message: discord.Message that is being saved
        """
        bookmark_form = bookmark_ui.BookmarkForm(message=message)
        await interaction.response.send_modal(bookmark_form)

    @discord.app_commands.command(name="get_bookmarks", description="Retrieve all of your bookmarks")
    async def get_bookmarks(self, interaction: discord.Interaction) -> None:
        """
        Creates a message with all of the user's bookmarks that can be flipped through and deleted

        Args:
            interaction: discord.Interaction that triggered the save
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
        records = await db_interactions.get(db, interaction)
        if len(records) == 0:
            await interaction.followup.send("You have not bookmarked any messages")
        else:
            buttons = bookmark_ui.ArrowButtons(records=records)
            await interaction.followup.send(view=buttons, embed=buttons.content[0], ephemeral=True)
