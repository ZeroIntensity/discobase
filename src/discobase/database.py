from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from threading import Thread
from typing import Type, TypeVar

import discord
import orjson

from .table import Table

__all__ = ("Database",)

T = TypeVar("T", bound=Type[Table])


class Database:
    """
    Top level class representing a Discord
    database bot controller.
    """

    def __init__(self, name: str) -> None:
        """
        Args:
            name: Name of the Discord server that will be used as the database.
        """
        self.name = name
        """Name of the Discord-database server."""
        intents = discord.Intents.all()
        self.bot = discord.Client(intents=intents)
        """discord.py `Client` instance."""
        self.guild: discord.Guild | None = None
        """discord.py `Guild` used as the database server."""
        self.tables: set[type[Table]] = set()
        """Set of `Table` objects attached to this database."""
        self.open: bool = False
        """Whether the database is connected."""
        self._metadata_channel: discord.TextChannel | None = None
        """discord.py `TextChannel` that acts as the metadata channel."""
        self._task: asyncio.Task[None] | None = None
        # We need to keep a strong reference to the free-flying
        # task

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
                self._metadata_channel = await self.guild.create_text_channel(
                    name=metadata_channel_name
                )
            else:
                self._metadata_channel = found_channel

            for table in self.tables:
                await self._create_table(table)

    async def _create_table(
        self,
        table: type[Table],
    ) -> None:
        """
        Creates a new table and all index tables that go with it.
        Writes the table metadata.
        """

        if self.guild is None:
            raise TypeError("(internal error) guild is None")

        name = table.__name__
        primary_table = await self.guild.create_text_channel(table.__name__)
        index_tables: set[discord.TextChannel] = set()
        for field_name in table.__disco_keys__:
            index_tables.add(
                await self.guild.create_text_channel(f"{name}-{field_name}")
            )

        table_metadata = {
            "name": name,
            "fields": table.__disco_keys__,
            "table_channel": primary_table.id,
            "index_channels": set(
                index_table.id for index_table in index_tables
            ),
            "current_records": 0,
            "max_records": 0,
        }

        message_text = orjson.dumps(table_metadata).decode("utf-8")

        if not self._metadata_channel:
            raise TypeError(
                "(internal error) expected _metadata_channel to be non-None"
            )

        await self._metadata_channel.send(message_text)

    async def _set_open(self) -> None:
        self.open = True

    async def login(self, bot_token: str) -> None:
        """
        Start running the bot.
        """
        # We use _set_open() with a gather to keep a finer link
        # between the `open` attribute and whether it's actually
        # running.
        await asyncio.gather(self.bot.start(token=bot_token), self._set_open())

    def login_task(self, bot_token: str) -> asyncio.Task[None]:
        """
        Call `login()` as a free-flying task, instead of
        blocking the event loop.

        Note that this method stores a reference to the created
        task object, allowing it to be truly "free-flying."

        Args:
            bot_token: Discord API bot token to log in to.

        Returns:
            Created `asyncio.Task` object. Note that the database
            will store this internally, so you don't have to worry
            about `await`ing it later. In most cases, you don't need
            the returned `asyncio.Task` object.

        Example:
            ```py
            import asyncio
            import os

            import discobase


            async def main():
                db = discobase.Database("test")
                dv.login_task("...")


            asyncio.run(main())
            ```
        """
        task = asyncio.create_task(self.login(bot_token))
        self._task = task
        return task

    @asynccontextmanager
    async def conn(self, bot_token: str):
        """
        Connect to the bot under a context manager.
        This is the recommended method to use for logging in.

        Args:
            bot_token: Discord API bot token to log in to.

        Returns:
            An asynchronous context manager.
            See `contextlib.asynccontextmanager` for details.

        Example:
            ```py
            import asyncio
            import os

            import discobase


            async def main():
                db = discobase.Database("test")
                async with db.conn(os.getenv("BOT_TOKEN")):
                    ...  # Your database code


            asyncio.run(main())
            ```
        """
        try:
            self.login_task(bot_token)
            yield
        finally:
            await self.bot.close()

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
            target=asyncio.run,
            args=(self.login(bot_token),),
            daemon=daemon,
        )

        if autostart:
            thread.start()

        return thread

    def table(self, clas: T) -> T:
        if not issubclass(clas, Table):
            raise TypeError(
                f"{clas} is not a subclass of Table, did you forget it?",
            )

        clas.__disco_database__ = self
        for field in clas.model_fields:
            clas.__disco_keys__.add(field)

        self.tables.add(clas)
        return clas
