import os

import discord
import pytest

import discobase


@pytest.fixture
def database():
    db = discobase.Database("test")
    return db


@pytest.fixture
async def bot(database: discobase.Database):
    database.login_thread(os.environ["TEST_BOT_TOKEN"], daemon=True)
    if database.guild:
        await database.guild.delete()
        database.guild = None

    return database.bot


def test_version():
    assert isinstance(discobase.__version__, str)
    assert discobase.__license__ == "MIT"


async def test_creation(database: discobase.Database, bot: discord.Client):
    found_guild: discord.Guild | None = None
    for guild in bot.guilds:
        if guild.name == database.name:
            found_guild = guild

    assert found_guild == database.guild
