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

    async def bookmark_message_callback(self, interaction: discord.Interaction, message: discord.Message):
        bookmark_form = bookmark_ui.BookmarkForm(message=message)
        await interaction.response.send_modal(bookmark_form)

    @discord.app_commands.command(name="get_bookmarks", description="Retrieve all of your bookmarks")
    async def get_bookmarks(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        records = await db_interactions.get(db, interaction)
        if len(records) == 0:
            await interaction.followup.send("You have not bookmarked any messages")
        else:
            buttons = bookmark_ui.ArrowButtons(records=records)
            await interaction.followup.send(view=buttons, embed=buttons.content[0], ephemeral=True)


    @discord.app_commands.command(name="clean_database")
    async def clean_database(self, interaction: discord.Interaction):
        await db.clean()
        await interaction.response.send_message("database has been cleaned", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Bookmark(bot))