from __future__ import annotations

import asyncio
import os

import discord
from demobot_config import db
from discord.ext import commands


class BookmarkBot(commands.Bot):
    def __init__(self):
        super().__init__(intents=discord.Intents.all(), command_prefix="!")

    async def on_ready(self) -> None:
        try:
            await self.load_extension("demobot_commands")
            await self.tree.sync()
            print(f"Logged in as {self.user}")
            print(f"Loaded the following commands: {await self.tree.fetch_commands()}")
        except Exception as e:
            print(f"{e.__class__.__name__}: {e}")

    async def on_error(self, event_method: str, /, *args: asyncio.Any, **kwargs: asyncio.Any) -> None:
        return await super().on_error(event_method, *args, **kwargs)


bot = BookmarkBot()

async def main():
        async with db.conn(os.getenv("DB_BOT_TOKEN")):
            try:
                await bot.start(os.getenv("BOOKMARK_BOT_TOKEN"))
            finally:
                await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
