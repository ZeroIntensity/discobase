from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Coroutine, NoReturn, Type, TypeVar

import discord
from discord.ext import commands
from loguru import logger

from ._cursor import TableCursor
from .cogs.utility import Utility
from .cogs.visualization import Visualization
from .exceptions import (DatabaseCorruptionError, DatabaseTableError,
                         NotConnectedError)
from .table import Table

__all__ = ("Database",)

T = TypeVar("T", bound=Type[Table])


class Database:
    """
    Top level class representing a Discord
    database bot controller.
    """

    def __init__(
        self,
        name: str,
        logging: bool = False,
    ) -> None:
        """
        Args:
            name: Name of the Discord server that will be used as the database.
            logging: Whether to enable logging.
        """
        if logging:
            logger.enable("discobase")
        else:
            logger.disable("discobase")

        self.name = name
        """Name of the Discord-database server."""
        self.bot = commands.Bot(
            intents=discord.Intents.all(),
            command_prefix="!",
        )
        """discord.py `Bot` instance."""
        self.guild: discord.Guild | None = None
        """discord.py `Guild` used as the database server."""
        self.tables: dict[str, type[Table]] = {}
        """Dictionary of `Table` objects attached to this database."""
        self.open: bool = False
        """Whether the database is connected."""
        self._metadata_channel: discord.TextChannel | None = None
        """discord.py `TextChannel` that acts as the metadata channel."""
        self._database_cursors: dict[str, TableCursor] = {}
        """A dictionary containing all of the table `Metadata` entries"""
        self._task: asyncio.Task[None] | None = None
        self.bot.db = self  # type: ignore
        # We need to keep a strong reference to the free-flying
        # task
        self._setup_event = asyncio.Event()
        self._internal_setup_event = asyncio.Event()
        self._on_ready_exc: BaseException | None = None

        # Here be dragons: https://github.com/ZeroIntensity/discobase/issues/49
        #
        # `on_ready` in discord.py swallows all exceptions, which
        # goes against some connect-and-disconnect behavior
        # that we want to allow in discobase.
        #
        # We need to store the exception, and then raise in wait_ready()
        # in order to properly handle it, otherwise the discord.py
        # logger just swallows it and pretends nothing happened.
        #
        # This also caused a deadlock with _setup_event, which caused
        # CI to run indefinitely.
        @self.bot.event
        @logger.catch(reraise=True)
        async def on_ready() -> None:
            try:
                await self.bot.add_cog(Utility(self.bot))
                await self.bot.add_cog(Visualization(self.bot))
                await self.init()
            except BaseException as e:
                await self.bot.close()
                if self._task:
                    self._task.cancel("bot startup failed")

                self._setup_event.set()
                self._on_ready_exc = e
                raise  # This is swallowed!

    def _not_connected(self) -> NoReturn:
        """
        Complain about the database not being connected.

        Generally speaking, this is called when `guild` or something
        other is `None`.
        """

        raise NotConnectedError(
            "not connected to the database, did you forget to login?"
        )

    async def _metadata_init(self) -> discord.TextChannel:
        """
        Find the metadata channel.
        If it doesn't exist, this method creates one.

        Returns:
            discord.TextChannel: The metadata channel, either created or found.
        """
        metadata_channel_name = "_dbmetadata"
        found_channel: discord.TextChannel | None = None
        assert self.guild is not None

        for channel in self.guild.text_channels:
            if channel.name == metadata_channel_name:
                found_channel = channel
                logger.info("Found metadata channel!")
                break

        return found_channel or await self.guild.create_text_channel(
            name=metadata_channel_name
        )

    # This needs to be async for use in gather()
    async def _set_open(self) -> None:
        logger.debug("_set_open waiting on internal setup event")
        await self._internal_setup_event.wait()
        logger.debug(
            "Internal setup event dispatched! Database has been marked as open."  # noqa
        )
        self.open = True
        # See https://github.com/ZeroIntensity/discobase/issues/68
        #
        # If `wait_ready()` is never called, then the error does not propagate.
        if self._on_ready_exc:
            raise self._on_ready_exc

    async def init(self) -> None:
        """
        Initializes the database server.

        Generally, you don't want to call this manually, but
        this is considered to be a public interface.
        """
        logger.info("Waiting until bot is logged in.")
        await self.bot.wait_until_ready()
        logger.info("Bot is ready!")
        found_guild: discord.Guild | None = None
        for guild in self.bot.guilds:
            if guild.name == self.name:
                found_guild = guild
                break

        if not found_guild:
            logger.info("No guild found, making one.")
            self.guild = await self.bot.create_guild(name=self.name)
        else:
            logger.info("Found an existing guild.")
            self.guild = found_guild

        # Unlock database, but don't wakeup the user.
        self._internal_setup_event.set()
        await self.build_tables()
        # At this point, the database is marked as "ready" to the user.
        self._setup_event.set()

        assert self._metadata_channel is not None
        logger.info(
            f"Invite to server: {await self._metadata_channel.create_invite()}"
        )
        logger.info("Syncing slash commands, this might take a minute.")
        logger.debug(f"Synced slash commands: {await self.bot.tree.sync()}")

    async def build_tables(self) -> None:
        """
        Generate all internal metadata and construct tables.

        Calling this manually is useful if e.g. you want
        to load tables *after* calling `login` (or `login_task`, or
        `conn`, same difference.)

        This method is safe to call multiple times.

        Example:
            ```py
            import asyncio
            import discobase

            async def main():
                db = discobase.Database("My database")
                db.login_task("My bot token")

                @db.table
                class MyLateTable(discobase.Table):
                    something: str

                # Load MyLateTable into database
                await db.build_tables()

            asyncio.run(main())
            ```
        """
        if not self.guild:
            self._not_connected()

        self._metadata_channel = await self._metadata_init()
        tasks = [
            asyncio.ensure_future(
                TableCursor.create_table(
                    table,
                    self._metadata_channel,
                    self.guild,
                )
            )
            for table in self.tables.values()
        ]
        logger.debug(f"Creating tables with gather(): {tasks}")
        await asyncio.gather(*tasks)

    async def wait_ready(self) -> None:
        """
        Wait until the database is ready.
        """
        logger.info("Waiting until the database is ready.")
        await self._setup_event.wait()
        logger.info("Done waiting!")
        # See #49, we need to propagate errors in `on_ready` here.
        if self._on_ready_exc:
            logger.error("on_ready() failed, propagating now.")
            raise self._on_ready_exc

    def _find_channel(self, cid: int) -> discord.TextChannel:
        # TODO: Implement caching for this function.
        if not self.guild:
            self._not_connected()

        index_channel = [
            channel for channel in self.guild.channels if channel.id == cid
        ][0]

        if not isinstance(index_channel, discord.TextChannel):
            raise DatabaseCorruptionError(
                f"expected {index_channel!r} to be a TextChannel"
            )

        logger.debug(f"Found channel ID {cid}: {index_channel!r}")
        return index_channel

    async def clean(self) -> None:
        """
        Perform a full clean of the database.

        This method erases all metadata, all entries, and all tables. After
        calling this, a server loses any trace of the database ever being
        there.

        Note that this does *not* clean the existing tables from memory, but
        instead just marks them all as not ready.

        This action is irreversible.
        """
        if not self._metadata_channel:
            self._not_connected()

        logger.info("Cleaning the database!")

        coros: list[Coroutine] = []
        for table, cursor in self._database_cursors.items():
            metadata = cursor.metadata
            logger.info(f"Cleaning table {table}")
            table_channel = self._find_channel(metadata.table_channel)
            coros.append(table_channel.delete())

            for cid in metadata.index_channels.values():
                channel = self._find_channel(cid)
                coros.append(channel.delete())

        for schema in self.tables.values():
            schema.__disco_cursor__ = None

        logger.debug(f"Gathering deletion coros: {coros}")
        await asyncio.gather(*coros)
        logger.info("Deleting database metadata.")
        self._database_cursors = {}
        await self._metadata_channel.delete()

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
            asyncio.Task[None]: The created `asyncio.Task` object.
                Note that the database will store this internally, so you
                don't have to worry about losing the reference. By default,
                this task will never get `await`ed, so this function will not
                keep the event loop running. If you want to keep the event loop
                running, make sure to `await` the returned task object later.

        Example:
            ```py
            import asyncio
            import os

            import discobase


            async def main():
                db = discobase.Database("test")
                task = await db.login_task("...")
                await db.wait_ready()
                # ...
                await task  # Keep the event loop running

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
            # If something went wrong in startup, for example, then
            # we need to release the setup lock.
            self._setup_event.set()
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
            AsyncGeneratorContextManager: An asynchronous context manager.
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
            if self.open:  # Something could have gone wrong
                await self.close()

    def table(self, clas: T) -> T:
        """
        Mark a `Table` type as part of a database.
        This method is meant to be used as a decorator.

        Args:
            clas: Type object to attach.

        Example:
            ```py
            import discobase

            db = discobase.Database("My database")

            @db.table
            class MySchema(discobase.Table):
                foo: int
                bar: str

            # ...
            ```

        Returns:
            Type[Table]: The same object passed to `clas` -- this is in order
                to allow use as a decorator.
        """
        if not issubclass(clas, Table):
            raise DatabaseTableError(
                f"{clas} is not a subclass of discobase.Table, did you forget it?",  # noqa
            )

        clas.__disco_name__ = clas.__name__.lower()
        if clas.__disco_name__ in self.tables:
            raise DatabaseTableError(f"table {clas.__name__} already exists")

        if clas.__disco_database__ is not None:
            raise DatabaseTableError(
                f"{clas!r} can only be attached to one database"
            )

        clas.__disco_database__ = self

        # This is up for criticism -- instead of using Pydantic's
        # `model_fields` attribute, we invent our own `__disco_keys__` instead.
        #
        # Partially, this is due to the fact that we want `__disco_keys__` to
        # be, more or less, stable throughout the codebase.
        #
        # However, I don't think Pydantic would mess with `model_fields`, as
        # that's a public API, and hence why this could possibly be
        # considered as bad design.
        for field in clas.model_fields:
            clas.__disco_keys__.add(field)

        self.tables[clas.__disco_name__] = clas
        return clas
