from __future__ import annotations

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

    def login(self, bot_token: str) -> None:
        """
        Start running the bot.
        This starts the `asyncio` event loop.
        """

        # Initialize the bot with the given token
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
