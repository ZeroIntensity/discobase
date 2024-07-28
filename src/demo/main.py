from __future__ import annotations

import asyncio
import os

import demobot_commands
import discord
from demobot_config import db
from loguru import logger


class BookmarkBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all(), command_prefix="!")
        self.tree = discord.app_commands.CommandTree(self)
        self.tree.add_command(demobot_commands.Bookmark(self))

    @logger.catch(reraise=True)
    async def on_ready(self) -> None:
        try:
            await self.tree.sync()
            logger.info(f"Logged in as {self.user}")
            logger.debug(f"{self.tree.client}")
            logger.debug(f"Loaded the following commands: {await self.tree.fetch_commands()}")
        except Exception as e:
            print(f"{e.__class__.__name__}: {e}")

    async def on_error(self, event_method: str, /, *args: asyncio.Any, **kwargs: asyncio.Any) -> None:
        return await super().on_error(event_method, *args, **kwargs)

discord.utils.setup_logging()
bot = BookmarkBot()

async def main() -> None:
        async with db.conn(os.getenv("DB_BOT_TOKEN")):
            try:
                await bot.start(os.getenv("BOOKMARK_BOT_TOKEN"))
            finally:
                await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
