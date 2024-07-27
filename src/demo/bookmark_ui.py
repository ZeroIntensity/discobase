import db_interactions
import discord


async def dm_bookmark(user: discord.User | discord.Member, message: discord.Message, title: str):
    embed = build_bookmark_embed(tuple(title, message))
    await user.send(content="Successfully bookmarked the message", embed=embed)

class BookmarkForm(discord.ui.Modal):
    """The form where a user can fill in a custom title for their bookmark & submit it."""

    bookmark_title = discord.ui.TextInput(
        label="Choose a title for your bookmark (optional)",
        placeholder="Type your bookmark title here",
        default="Bookmark",
        max_length=50,
        min_length=0,
        required=False,
    )

    def __init__(self, message: discord.Message):
        super().__init__(timeout=1000, title="Name your bookmark")
        self.message = message

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Sends the bookmark embed to the user with the newly chosen title."""
        title = self.bookmark_title.value or self.bookmark_title.default
        try:
            await interaction.response.defer()
            await dm_bookmark(interaction.user, self.message, title)
            await db_interactions.add(interaction, self.message, title)
        except discord.Forbidden:
            await interaction.followup.send(
                embed=build_error_embed("Enable your DMs to receive the bookmark."),
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.followup.send(
                embed=(build_error_embed(f"{e.__class__.__name}: {e}"))
            )


def build_bookmark_embed(record: list[tuple[str, discord.Message]]):
        embed = discord.Embed(title=record[0], description=record[1].content, colour=0x68C290)
        embed.set_author(
            name=record[1].author.name,
            icon_url= record[1].author.display_avatar.url
        )
        return embed

def build_embeds_list(records: list[tuple[str, discord.Message]]) -> list[discord.Embed]:
        embeds: list[discord.Embed] = []
        for record in records:
            embed = build_bookmark_embed(record)
            embeds.append(embed)
        return embeds


def build_error_embed(embed_content: str):
    embed = discord.Embed(title="Error Saving embed", description=embed_content)
    embed.set_author("Bookmark Bot")
    return embed


class ArrowButtons(discord.ui.View):
    def __init__(self, content: list[discord.Embed]) -> None:
        super().__init__(timeout=None)
        self.value = None
        self.content = content
        self.position = 0
        self.pages = len(self.content)
        self.on_ready()

    @discord.ui.button(label='⬅️', style=discord.ButtonStyle.primary, custom_id='l_button')
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Controls the left button on the qotd list embed"""
        # move back a position in the embed list
        self.position -= 1

        # check if we're on the first page, then disable the button to go left if we are (cant go anymore left)
        if self.position == 0:
            button.disabled = True

        # set the right button to a variable
        right_button = [x for x in self.children if x.custom_id == 'r_button'][0]

        # check if we're not on the last page, if yes then enable right button
        if not self.position == self.pages - 1:
            right_button.disabled = False

        # update discord message
        await interaction.response.edit_message(embed=self.content[self.position], view=self)

    @discord.ui.button(label='➡️️️', style=discord.ButtonStyle.primary, custom_id='r_button')
    async def forward(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Controls the right button on the qotd list embed"""
        # move forward a position in the embed list
        self.position += 1

        # set a variable for left button
        left_button = [x for x in self.children if x.custom_id == 'l_button'][0]
        # check if we're not on the first page, if yes then enable left button
        if not self.position == 0:
            left_button.disabled = False

        # check if we're on the last page, if yes then disable right button
        if self.position == self.pages - 1:
            button.disabled = True

        # update discord message
        await interaction.response.edit_message(embed=self.content[self.position], view=self)

    def on_ready(self) -> None:
        """Checks the number of pages to decide which buttons to have enabled/disabled"""
        left_button = [x for x in self.children if x.custom_id == 'l_button'][0]
        right_button = [x for x in self.children if x.custom_id == 'r_button'][0]

        # if we only have one page, disable both buttons
        if self.pages == 1:
            left_button.disabled = True
            right_button.disabled = True
        # if we have more than one page, only disable the left button for the first page
        else:
            left_button.disabled = True
