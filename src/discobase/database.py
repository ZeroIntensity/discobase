from __future__ import annotations

import json
from threading import Thread
from typing import Dict, Set, Tuple

import discord

__all__ = ("Database",)


class Database:
    """
    Top level class representing a Discord
    database bot controller.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        intents = discord.Intents.all()
        self.bot = discord.Client(intents=intents)
        self.guild: discord.Guild | None = None
        self.metadata_channel: discord.TextChannel | None = None

        @self.bot.event
        async def on_ready() -> None:
            """
            When bot is online, creates the DB server.
            """
            await self.bot.wait_until_ready()
            found_guild: discord.Guild | None = None
            for guild in self.bot.guilds:
                if guild.name == self.name:
                    found_guild = guild
                    break

            if not found_guild:
                self.guild = await self.bot.create_guild(name=self.name)
            else:
                self.guild = found_guild

            metadata_channel_name = f"{self.name}_metadata"
            found_channel: discord.TextChannel | None = None
            for channel in self.guild.text_channels:
                if channel.name == metadata_channel_name:
                    found_channel = channel
                    break

            if not found_channel:
                self.metadata_channel = await self.guild.create_text_channel(
                    name=metadata_channel_name
                )
            else:
                self.metadata_channel = found_channel

    async def create_table(
        self, name: str, fields: Dict[str, Tuple[type, bool]]
    ) -> None:
        """
        Creates a new table and all index tables that go with it. Writes the table metadata.

        name: str - The name of the new table
        fields: Dict[str, Tuple[type, bool]] - Information about the types of data that will be stored in the database
            key - Field name
            value - Tuple containing the type of data to be stored and whether the field is required
        return None
        """

        if self.guild is None:
            raise TypeError(
                "The bot is not logged in. Please call login before creating a table."
            )

        primary_table = await self.guild.create_text_channel(name)
        index_tables: Set[discord.TextChannel] = []
        for field_name in fields.keys():
            index_tables.add(
                await self.guild.create_text_channel(f"{name}-{field_name}")
            )

        table_metadata = {
            "name": name,
            "fields": fields,
            "table_channel": primary_table.id,
            "index_channels": set(index_table.id for index_table in index_tables),
            "current_records": 0,
            "max_records": 0,
        }

        message_text = json.dumps(table_metadata)
        self.metadata_channel.send(message_text)

    def login(self, bot_token: str) -> None:
        """
        Start running the bot.
        This starts the `asyncio` event loop.
        """
        self.bot.run(token=bot_token)

    def login_thread(
        self,
        bot_token: str,
        *,
        daemon: bool = False,
        autostart: bool = True,
    ) -> Thread:
        """
        Run the bot in a seperate thread.

        Args:
            bot_token: Discord API bot token.
            daemon: Equivalent to `daemon` parameter in `threading.Thread`
            autostart: Whether to automatically call `start`

        Returns:
            The `Thread` instance used to start the bot.
        """
        thread = Thread(
            target=self.login,
            args=(bot_token,),
            daemon=daemon,
        )

        if autostart:
            thread.start()

        return thread
