from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from threading import Thread

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

    async def login(self, bot_token: str) -> None:
        """
        Start running the bot.
        """
        await self.bot.start(token=bot_token)

    def login_task(self, bot_token: str) -> asyncio.Task[None]:
        task = asyncio.create_task(self.bot.start(bot_token))
        self._task = task
        return task

    @asynccontextmanager
    async def conn(self, bot_token: str):
        """
        Connect to the bot under a context manager.
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
