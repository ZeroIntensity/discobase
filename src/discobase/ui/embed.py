from __future__ import annotations

from datetime import datetime as dt
from enum import Enum, auto
from math import ceil

import discord
from loguru import logger

"""
How to Use:
1. Use EmbedfromContent for your database outputs with .create() and assign to a variable.
    e.g. EmbedfromContent(title="something", content={"foo":"bar"}, headers=["foo"], style="TABLE").create()
2. Use Arrow buttons class with EmbedfromContent output as content argument and assign to variable.
3. Input the ArrowButton class as the view, and the embeds as the content in interaction.send_message.
"""

__all__ = ["ArrowButtons", "EmbedFromContent", "EmbedStyle"]


class ArrowButtons(discord.ui.View):
    def __init__(self, content: list[discord.Embed]) -> None:
        super().__init__(timeout=None)
        self.value = None
        self.content = content
        self.position = 0
        self.pages = len(self.content)
        logger.debug(f"pages in button {self.pages}")
        self.on_ready()

    @discord.ui.button(
        label="◀", style=discord.ButtonStyle.primary, custom_id="l_button"
    )
    async def back(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Controls the left button on the qotd list embed"""
        # move back a position in the embed list
        self.position -= 1

        # check if we're on the first page, then disable the button to go left if we are (cant go anymore left)
        if self.position == 0:
            button.disabled = True

        # set the right button to a variable
        right_button = [x for x in self.children if x.custom_id == "r_button"][
            0
        ]

        # check if we're not on the last page, if yes then enable right button
        if not self.position == self.pages - 1:
            right_button.disabled = False

        # update discord message
        await interaction.response.edit_message(
            embed=self.content[self.position], view=self
        )

    @discord.ui.button(
        label="▶", style=discord.ButtonStyle.primary, custom_id="r_button"
    )
    async def forward(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        """Controls the right button on the qotd list embed"""
        # move forward a position in the embed list
        self.position += 1

        # set a variable for left button
        left_button = [x for x in self.children if x.custom_id == "l_button"][0]
        # check if we're not on the first page, if yes then enable left button
        if not self.position == 0:
            left_button.disabled = False

        # check if we're on the last page, if yes then disable right button
        if self.position == self.pages - 1:
            button.disabled = True

        # update discord message
        await interaction.response.edit_message(
            embed=self.content[self.position], view=self
        )

    def on_ready(self) -> None:
        """Checks the number of pages to decide which buttons to have enabled/disabled"""
        left_button = [x for x in self.children if x.custom_id == "l_button"][0]
        right_button = [x for x in self.children if x.custom_id == "r_button"][
            0
        ]

        # if we only have one page, disable both buttons
        if self.pages == 1:
            left_button.disabled = True
            right_button.disabled = True
        # if we have more than one page, only disable the left button for the first page
        else:
            left_button.disabled = True


class EmbedStyle(str, Enum):
    COLUMN = auto()
    TABLE = auto()
    SCHEMA = auto()
    DEFAULT = auto()


# TODO add support for character limits: https://anidiots.guide/.gitbook/assets/first-bot-embed-example.png
class EmbedFromContent:
    """Creates a list of embeds suited for pagination from inserted content."""

    def __init__(
        self,
        title: str,
        content: list[str] | dict | list[dict],
        style: "EmbedStyle",
        headers: list[str] | None = None,
    ) -> None:
        """
        Sets the base parameters for the embeds.

        :param title: Title of the embed.
        :param headers: Columns of the table, will be used for field names. Required if seeking table display.
        :param content: Content of the table.
        """
        self.author = "Discobase"
        self.color = discord.Colour.blurple()
        self.title = title if len(title) < 256 else f"{title[0:253]}..."
        self.headers = headers
        self.content = content
        self.page_number = 0
        self.page_total = 0
        self.url = "https://github.com/ZeroIntensity/discobase"
        self.icon_url = "https://i.imgur.com/2QH3tEQ.png"

        self.style = style

    def create(self) -> list[discord.Embed] | discord.Embed:
        if self.style == "column":
            return self._column_display()
        elif self.style == "table":
            return self._table_display()
        elif self.style == "schema":
            return self._schema_display()
        elif self.style == "default":
            return self._default_display()
        else:
            raise ValueError("Invalid style input.")

    def _column_display(self) -> list[discord.Embed]:
        """
        Creates list of discord embeds for the column content, 15 rows per embed.
        """
        entries_per_page = 15
        embeds: list[discord.Embed] = []

        column_data: list[str] = self.content
        self.page_total = ceil(len(column_data) / 15)
        logger.debug(f"{self.page_total}, round: {len(column_data) / 15}")

        # Create each embed with the data
        for i in range(0, len(column_data), entries_per_page):
            self.page_number += 1
            embed_content = "\n".join(column_data[i : i + entries_per_page])
            discord_embed = discord.Embed(
                color=self.color,
                title=self.title,
                type="rich",
                description=embed_content,
                timestamp=dt.now(),
            )
            discord_embed.set_author(
                name=self.author, url=self.url, icon_url=self.icon_url
            )
            discord_embed.set_footer(
                text=f"Page: {self.page_number}/{self.page_total}"
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
        self.page_total = ceil(
            len(self.content[self.headers[0]]) / entries_per_page
        )

        # get the len of the first column's data
        for i in range(0, len(table_data[column_names[0]]), entries_per_page):
            self.page_number += 1
            discord_embed = discord.Embed(
                color=self.color,
                title=self.title,
                type="rich",
                timestamp=dt.now(),
            )
            discord_embed.set_author(
                name=self.author, url=self.url, icon_url=self.icon_url
            )
            discord_embed.set_footer(
                text=f"Page: {self.page_number}/{self.page_total}"
            )
            # create fields for each column with 10 data entries
            for k, v in table_data.items():
                field_title = k.title()
                field_content = "\n".join(
                    [
                        f"**{i + 1}.** {value}"
                        for i, value in enumerate(v[i : i + entries_per_page])
                    ]
                )
                discord_embed.add_field(
                    name=field_title, value=field_content, inline=True
                )
            embeds.append(discord_embed)

        return embeds

    def _schema_display(self) -> discord.Embed:
        """
        Creates an embed that has the schema information. Column names as field titles, and type as field values.
        """
        embed = discord.Embed(
            title=self.title, color=self.color, type="rich", timestamp=dt.now()
        )
        embed.set_author(name=self.author, url=self.url, icon_url=self.icon_url)

        for content in self.content:
            embed.add_field(
                name=content["title"], value=content["type"], inline=True
            )

        return embed

    def _default_display(self) -> discord.Embed:
        """
        Creates an embed with a default visual style.
        """
        embed = discord.Embed(
            title=self.title, color=self.color, type="rich", timestamp=dt.now()
        )
        embed.set_author(name=self.author, url=self.url, icon_url=self.icon_url)

        return embed
