import os

import discord
import pytest

import discobase


@pytest.fixture
def database():
    db = discobase.Database("test")

    @db.table
    class User(discobase.Table):
        name: str
        password: str

    return db


@pytest.fixture
async def bot(database: discobase.Database):
    database.login_thread(os.environ["TEST_BOT_TOKEN"], daemon=True)
    if database.guild:
        await database.guild.delete()
        database.guild = None

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

    assert found is True


async def test_key_channels(database: discobase.Database):
    assert database.guild is not None
    names = [guild.name for guild in database.guild.channels]

    for table in database.tables:
        for key in table.__disco_keys__:
            assert f"{table.__name__}_{key}" in names
