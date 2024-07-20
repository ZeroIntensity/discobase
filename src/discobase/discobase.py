import discord
from discord.ext import commands


class Database:
    def __init__(self, name) -> None:
        self.name = name
        intents = discord.Intents.all()
        self.bot = discord.Client(intents=intents)

    def login(self, bot_token) -> None:
        @self.bot.event
        async def on_ready() -> None:
            """When bot is online, creates DB server."""
            # Create a new server for the DB
            guild = await self.bot.create_guild(name=self.name)

            # Get the invite link for the server
            landing_channel = await guild.create_text_channel(name="landing", reason="creating invite")
            invite = await landing_channel.create_invite()

        # Initialize the bot with the given token
        self.bot.run(token=bot_token)


