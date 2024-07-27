from __future__ import annotations

import asyncio
import os

import discord
from commands import bookmark_message_callback, clean_database, get_bookmarks
from demobot_config import db


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = discord.app_commands.CommandTree(self)
        self.bookmark_context_menu = discord.app_commands.ContextMenu(name="Bookmark", callback=bookmark_message_callback)
        self.tree.add_command(get_bookmarks)
        self.tree.add_command(clean_database)
        self.tree.add_command(self.bookmark_context_menu)

    async def on_ready(self) -> None:
        await self.tree.sync()
        print(f"Logged in as {self.user}")
        print(f"Loaded the following commands: {await self.tree.fetch_commands()}")

    async def on_error(self, event_method: str, /, *args: asyncio.Any, **kwargs: asyncio.Any) -> None:
        return await super().on_error(event_method, *args, **kwargs)


discord.utils.setup_logging()
bot = Bot()

async def main():
        async with db.conn(os.getenv("DB_BOT_TOKEN")):
            try:
                await bot.start(os.getenv("BOOKMARK_BOT_TOKEN"))
            finally:
                await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
