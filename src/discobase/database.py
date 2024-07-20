from __future__ import annotations

import discord

__all__ = ("Database",)


class Database:
    """
    Top level class representing a Discord-server database.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        intents = discord.Intents.all()
        self.bot = discord.Client(intents=intents)
        self.guild: discord.Guild | None = None

    def login(self, bot_token: str) -> None:
        """
        Start running the bot.
        This starts the `asyncio` event loop.
        """

        @self.bot.event
        async def on_ready() -> None:
            """When bot is online, creates DB server."""
            await self.bot.wait_until_ready()
            found_guild: discord.Guild | None = None
            for guild in self.bot.guilds:
                if guild.name == self.name:
                    found_guild = guild

            if not found_guild:
                self.guild = await self.bot.create_guild(name=self.name)
            else:
                self.guild = found_guild

        # Initialize the bot with the given token
        self.bot.run(token=bot_token)
