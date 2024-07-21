from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from threading import Thread
import time

import discord

from .config import BOT_TOKEN

__all__ = ("Database",)




class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        
        self.guild: discord.Guild | None = None
        self._task: asyncio.Task[None] | None = None
        
        
    def startup(self, bot_token: str) -> None:
        self.starttime = time.time()
        self.run(bot_token)

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user}")
    
    async def on_message(self, message: discord.Message) -> None:
        if message.content.startswith("!demobot!ping"):
            await message.channel.send("Pong!")
        if message.content.startswith("!demobot!shutdown"):
            self._task = asyncio.create_task(self.close())
        if message.content.startswith("!demobot!uptime"):
            uptime = time.time() - self.starttime
            # format uptime
            uptime = time.strftime("%H:%M:%S", time.gmtime(uptime))
            await message.channel.send(f"Uptime: {uptime}")
    
# bot will
# store bookmarks
# query them

def main() -> None:
    bot = Bot()
    bot.startup(BOT_TOKEN)