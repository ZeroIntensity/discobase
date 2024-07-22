import os

import discord
import orjson
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
def test_table(database: discobase.Database):
    class TestTable(discobase.Table):
        __disco_keys__ = set(("username", "password"))

    return database.table(TestTable)


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


async def test_create_table(
    database: discobase.Database, test_table: discobase.Table
):
    assert database.guild is not None
    assert database._metadata_channel is not None
    hash_size = 1
    await database._create_table(test_table, initial_hash_size=hash_size)
    names = [channel.name for channel in database.guild.channels]

    table_metadata = orjson.loads(
        database._metadata_channel.last_message.content
    )
    assert table_metadata["max_records"] == hash_size

    for table in database.tables:
        for key in table.__disco_keys__:
            assert f"{table.__name__.lower()}_{key.lower()}" in names

    for index_id in table_metadata["index_channels"]:
        channel: discord.abc.GuildChannel = database.guild.get_channel(
            index_id
        )
        assert isinstance(channel, discord.TextChannel)
        messages = [message async for message in channel.history()]
        assert len(messages) == hash_size
