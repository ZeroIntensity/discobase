import discord
from discord import app_commands

import discobase


class DiscobaseClient(discord.Client):
    def __init__(self, database_name):
        super().__init__(intents=discord.Intents.all())
        self.database = discobase.Database(name=database_name, bot=self)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        await super().setup_hook()

    async def on_ready(self):
        await self.database.login()


def run_client(database_name: str, bot_id: str):
    client = DiscobaseClient(database_name)
    client.run(bot_id)
