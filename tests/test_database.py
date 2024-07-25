import os

import discord
import pytest

import discobase
from discobase.exceptions import DatabaseTableError


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
    assert database._metadata_channel.name == "_dbmetadata"
    assert database.guild is not None
    found: bool = False

    for channel in database.guild.channels:
        if channel == database._metadata_channel:
            found = True
            break

    assert found is True


async def test_schemas(database: discobase.Database):
    class User(discobase.Table):
        name: str
        password: str

    with pytest.raises(DatabaseTableError):
        # No database attached
        await User(name="Peter", password="foobar").save()

    with pytest.raises(DatabaseTableError):
        # Missing `Table` subclass
        @database.table  # type: ignore
        class Foo:
            name: str
            password: str

    User = database.table(User)
    with pytest.raises(DatabaseTableError):
        # Not ready
        await User(name="Peter", password="foobar").save()

    await database.build_tables()
    user = User(name="Peter", password="foobar")
    await user.save()
    assert (await User.find(name="Peter"))[0] == user

    with pytest.raises(DatabaseTableError):
        # Duplicate table name
        @database.table
        class User(discobase.Table):
            name: str
            password: str
