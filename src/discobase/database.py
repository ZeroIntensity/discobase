from __future__ import annotations

import discord

__all__ = ("Database",)


class Database:
    """
    Top level class representing a Discord
    database bot controller.
    """

    def __init__(self, name: str, bot: discord.Client) -> None:
        self.name = name
        self.bot = bot
        self.guild: discord.Guild | None = None

    async def login(self) -> None:
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
