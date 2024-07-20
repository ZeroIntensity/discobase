from threading import Thread

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
            guilds_list = [
                guild.name for guild in self.bot.guilds
            ]  # List of guild names the bot is in

            # Create a new server for the DB if not duplicate
            if self.name not in guilds_list:
                self.guild = await self.bot.create_guild(name=self.name)

        # Initialize the bot with the given token
        self.bot.run(token=bot_token)
