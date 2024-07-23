from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pkgutil import iter_modules
from typing import Type, TypeVar

import discord
import orjson
from discord.ext import commands

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
        self.bot = commands.Bot(
            intents=discord.Intents.all(), command_prefix="!"
        )
        """discord.py `Bot` instance."""
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
        self._setup_event = asyncio.Event()

        @self.bot.event
        async def on_ready() -> None:
            await self.init()

    async def init(self) -> None:
        """
        Initializes the database server.
        Generally, you don't want to call this manually.
        """
        # Load external commands
        for module in iter_modules(path=["cogs"], prefix="cogs."):
            await self.bot.load_extension(module.name)

        await self.bot.tree.sync()

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

        self._setup_event.set()

    async def wait_ready(self) -> None:
        """Wait until the database is ready."""
        await self._setup_event.wait()

    async def _create_table(
        self,
        table: type[Table],
    ) -> None:
        """
        Creates a new table and all index tables that go with it.
        This writes the table metadata.

        If the table already exists, this method does (almost) nothing.

        Args:
            table: Table schema to create channels for.
        """

        if self.guild is None:
            raise TypeError("(internal error) guild is None")

        name = table.__name__

        for channel in self.guild.channels:
            if channel == table.__name__:
                # The table is already set up, no need to do anything more.
                return
        primary_table = await self.guild.create_text_channel(table.__name__)
        index_tables: set[discord.TextChannel] = set()
        for field_name in table.__disco_keys__:
            index_tables.add(
                await self.guild.create_text_channel(f"{name}_{field_name}")
            )

        table_metadata = {
            "name": name,
            "fields": tuple(table.__disco_keys__),
            "table_channel": primary_table.id,
            "index_channels": [index_table.id for index_table in index_tables],
            "current_records": 0,
            "max_records": 0,
        }

        message_text = orjson.dumps(table_metadata).decode("utf-8")

        if not self._metadata_channel:
            raise TypeError(
                "(internal error) expected _metadata_channel to be non-None"
            )

        await self._metadata_channel.send(message_text)

    # This needs to be async for use in gather()
    async def _set_open(self) -> None:
        self.open = True

    async def login(self, bot_token: str) -> None:
        """
        Start running the bot.

        Args:
            bot_token: Discord API bot token to log in with.
        """
        if self.open:
            raise RuntimeError(
                "connection is already open, did you call login() twice?"
            )

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
            about losing the reference. By default, this task will
            never get `await`ed, so this function will not keep the
            event loop running. If you want to keep the event loop running,
            make sure to `await` the returned task object later.

        Example:
            ```py
            import asyncio
            import os

            import discobase


            async def main():
                db = discobase.Database("test")
                db.login_task("...")
                await db.wait_ready()
                # ...
                await db  # Keep the event loop running

            asyncio.run(main())
            ```
        """
        task = asyncio.create_task(self.login(bot_token))
        self._task = task
        return task

    async def close(self) -> None:
        """
        Close the bot connection.
        """
        if not self.open:
            raise ValueError(
                "cannot close a connection that is not open",
            )
        self.open = False
        await self.bot.close()

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
            await self.wait_ready()
            yield
        finally:
            await self.close()

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
