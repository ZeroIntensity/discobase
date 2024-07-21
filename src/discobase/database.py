from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from threading import Thread

import discord

from .table import Table

__all__ = ("Database",)


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

            if not found_guild:
                self.guild = await self.bot.create_guild(name=self.name)
            else:
                self.guild = found_guild

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

    def table(self, clas: type[Table]):
        if not issubclass(clas, Table):
            raise TypeError(
                f"{clas} is not a subclass of Table, did you forget it?",
            )

        clas.database = self
        for field in clas.__pydantic_fields_set__:
            clas.keys.add(field)

        self.tables.add(clas)
