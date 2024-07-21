import os

import discord
import pytest

import discobase


@pytest.fixture
async def database():
    db = discobase.Database("test")
    db.login_task(os.environ["TEST_BOT_TOKEN"])
    if db.guild:
        await db.guild.delete()
        db.guild = None
        await db.init()

    try:
        await db.wait_ready()
        yield db
    finally:
        await db.close()


@pytest.fixture
def bot(database: discobase.Database):
    return database.bot


def test_about():
    assert isinstance(discobase.__version__, str)
    assert discobase.__license__ == "MIT"


async def test_creation(database: discobase.Database, bot: discord.Client):
    found_guild: discord.Guild | None = None
    for guild in bot.guilds:
        if guild.name == database.name:
            found_guild = guild

    assert found_guild == database.guild


async def test_metadata_channel(database: discobase.Database):
    assert database._metadata_channel is not None
    assert database._metadata_channel.name == f"{database.name}_metadata"
    assert database.guild is not None
    found: bool = False

    for channel in database.guild.channels:
        if channel == database._metadata_channel:
            found = True
            break

    assert found is True


async def test_key_channels(database: discobase.Database):
    assert database.guild is not None
    names = [channel.name for channel in database.guild.channels]

    for table in database.tables:
        for key in table.__disco_keys__:
            assert f"{table.__name__}_{key}" in names

    for table in database.tables:
        for key in table.__disco_keys__:
            for channel in database.guild.channels:
                if channel.name == f"{table.__name__}_{key}":
                    assert len(await channel.history()) == 16
