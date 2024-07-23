import os

import discord
import orjson
import pytest

import discobase


@pytest.fixture
async def database():
    db = discobase.Database("test")
    db.login_task(os.environ["TEST_BOT_TOKEN"])
    await db.wait_ready()
    if db.guild:
        await db.guild.delete()
        db.guild = None
        await db.init()

    try:
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
    assert database._metadata_channel.name == f"{database.name}_db_metadata"
    assert database.guild is not None
    found: bool = False

    for channel in database.guild.channels:
        if channel == database._metadata_channel:
            found = True
            break

    assert found is True


async def test_create_table(database: discobase.Database):
    @database.table
    class TestTable(discobase.Table):
        username: str
        password: str

    assert database.guild is not None
    assert database._metadata_channel is not None
    hash_size = 1
    metadata_message = await database._create_table(
        TestTable, initial_hash_size=hash_size
    )

    table_metadata = orjson.loads(metadata_message.content)
    assert table_metadata["max_records"] == hash_size

    for id in table_metadata["index_channels"].values():
        channel = database.guild.get_channel(id)
        assert isinstance(channel, discord.TextChannel)
        messages = [message async for message in channel.history()]
        assert len(messages) == hash_size

    names = [channel.name for channel in database.guild.channels]

    for table in database.tables:
        for key in table.__disco_keys__:
            assert f"{table.__name__.lower()}_{key.lower()}" in names


async def test_delete_table(database: discobase.Database):
    @database.table
    class TestTable(discobase.Table):
        username: str
        password: str

    await database._create_table(TestTable, initial_hash_size=0)
    database._metadata_channel = database.guild.get_channel(
        database._metadata_channel.id
    )
    names = [channel.name for channel in database.guild.channels]
    name_of_table_to_delete = list(database.tables)[0].__name__.lower()
    assert name_of_table_to_delete in names
    await database._delete_table(name_of_table_to_delete)

    updated_names = [channel.name for channel in database.guild.channels]
    for name in updated_names:
        assert name.find(name_of_table_to_delete) != 0

    assert len(database.tables) == 0

    async for message in database._metadata_channel.history():
        table_metadata = orjson.loads(message.content)
        assert isinstance(table_metadata, dict)
        assert table_metadata["name"] != name_of_table_to_delete


async def test_add_record(database: discobase.Database):
    @database.table
    class TestTable(discobase.Table):
        username: str
        password: str

    await database._create_table(TestTable, initial_hash_size=4)

    test_record = TestTable(username="rubiks14", password="secretPassword")
    message = await database._add_record(test_record)
    assert orjson.loads(message.content)["content"] == test_record.model_dump()

    table_metadata = database._get_table_metadata(TestTable.__name__.lower())

    for field, value in test_record.model_dump().items():
        for name, id in table_metadata["index_channels"].items():
            if name.lower().split("_")[1] == field.lower():
                index_channel = [
                    channel
                    for channel in database.guild.channels
                    if channel.id == id
                ][0]
                index_messages = [
                    message
                    async for message in index_channel.history(
                        limit=table_metadata["max_records"]
                    )
                ]
                hashed_field = hash(value)
                message_hash = (hashed_field & 0x7FFFFFFF) % table_metadata[
                    "max_records"
                ]
                existing_content = orjson.loads(
                    index_messages[message_hash].content
                )
                assert existing_content["key"] == hashed_field
                assert message.id in existing_content["record_ids"]
                break


async def test_find_records(database: discobase.Database):
    @database.table
    class TestTable(discobase.Table):
        username: str
        password: str

    await database._create_table(TestTable, initial_hash_size=4)

    test_record = TestTable(username="rubiks14", password="secretPassword")
    test_record2 = TestTable(username="rubberduck", password="secretPassword")
    await database._add_record(test_record)
    await database._add_record(test_record2)

    found_records = await database._find_records(
        "testtable", username="rubiks14", password="secretPassword"
    )

    assert len(found_records) == 1
