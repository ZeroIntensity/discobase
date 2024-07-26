from datetime import datetime as dt
from enum import StrEnum, auto

import discord

"""
How to Use:
1. Use EmbedfromContent for your database outputs and assign to variable.
2. Use Arrow buttons class with EmbedfromContent output as content argument and assign to variable.
3. Input the ArrowButton class as the view, and the embeds as the content in interaction.send_message.
"""

__all__ = ['ArrowButtons', 'EmbedFromContent', 'EmbedStyle']

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


class EmbedStyle(StrEnum):
    COLUMN = auto()
    TABLE = auto()


# TODO add support for character limits: https://anidiots.guide/.gitbook/assets/first-bot-embed-example.png
# TODO change icon url to our logo
class EmbedFromContent:
    """Creates a list of embeds suited for pagination from inserted content."""
    def __init__(self, title: str, content: list[str] | dict, style: "EmbedStyle", headers: list[str] | None = None) -> None:
        """
        Sets the base parameters for the embeds.

        :param title: Title of the embed.
        :param headers: Columns of the table. Required if seeking table display.
        :param content: Content of the table.

        :return: list[discord.Embed]
        """
        self.author = "Discobase"
        self.color = discord.Colour.blurple()
        self.title = title
        self.headers = headers
        self.content = content
        self.page_number = 0
        self.page_total = 0
        self.url = "https://github.com/ZeroIntensity/discobase"
        self.icon_url = ("https://static.vecteezy.com/system/resources/previews/018/930/500/original/discord-logo"
                         "-discord-icon-transparent-free-png.png")
        time = dt.now()
        self.footer = f"page {self.page_number}/{self.page_total}//{time.strftime('%I:%M %p')} // {time.strftime(
            '%d/%m/%Y')}"

        self.style = style

        match self.style:
            case "column":
                self._column_display()
            case "table":
                self._table_display()
            case _:
                raise ValueError("Invalid style input.")

    def _column_display(self) -> list[discord.Embed]:
        """
        Creates list of discord embeds for the column content, 15 rows per embed.
        """
        entries_per_page = 15
        embeds: list[discord.Embed] = []

        column_data: list[str] = ["str1", "str2"]
        self.page_total = round(len(column_data) / 15) + 1

        # Create each embed with the data
        for i in range(0, len(column_data), entries_per_page):
            self.page_number += 1
            embed_content = "\n".join(column_data[i:i+entries_per_page])
            discord_embed = discord.Embed(
                color=self.color,
                title=self.title,
                type='rich',
                description=embed_content,
            )
            discord_embed.set_author(
                name=self.author,
                url=self.url,
                icon_url=self.icon_url
            )
            discord_embed.set_footer(
                text=self.footer
            )

            embeds.append(discord_embed)

        return embeds

    def _table_display(self) -> list[discord.Embed]:
        """
        Creates a list of discord embeds that display the data in a table, 10 entries per page.
        """
        entries_per_page = 10
        embeds: list[discord.Embed] = []

        column_names: list = self.headers
        table_data: dict = self.content
        self.page_total = round(len(self.content) / entries_per_page) + 1

        # get the len of the first column's data
        for i in range(0, len(table_data[column_names[0]]), entries_per_page):
            self.page_number += 1
            discord_embed = discord.Embed(
                color=self.color,
                title=self.title,
                type='rich',
            )
            discord_embed.set_author(
                name=self.author,
                url=self.url,
                icon_url=self.icon_url
            )
            discord_embed.set_footer(
                text=self.footer
            )
            # create fields for each column with 10 data entries
            for k, v in table_data.items():
                field_title = k
                field_content = "\n".join([f"{i + 1}. {value}" for i, value in enumerate(v[i:i+entries_per_page])])
                discord_embed.add_field(
                    name=field_title,
                    value=field_content,
                    inline=True
                )
            embeds.append(discord_embed)

        return embeds
