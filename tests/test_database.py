import os
import random
import string
import sys

import discord
import pytest

import discobase
from discobase.exceptions import DatabaseTableError


@pytest.fixture
async def database():
    db = discobase.Database("discobase test")
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
    class Bar(discobase.Table):
        name: str
        password: str

    with pytest.raises(DatabaseTableError):
        # No database attached
        await Bar(name="Peter", password="foobar").save()

    with pytest.raises(DatabaseTableError):
        # Missing `Table` subclass
        @database.table  # type: ignore
        class Foo:
            name: str
            password: str

    Bar = database.table(Bar)
    with pytest.raises(DatabaseTableError):
        # Not ready
        await Bar(name="Peter", password="foobar").save()

    await database.build_tables()
    user = Bar(name="Peter", password="foobar")
    await user.save()
    assert (await Bar.find(name="Peter"))[0] == user

    with pytest.raises(DatabaseTableError):
        # Duplicate table name
        @database.table
        class Bar(discobase.Table):
            name: str
            password: str


async def test_resizing(database: discobase.Database):
    @database.table
    class User(discobase.Table):
        name: str
        password: str

    await database.build_tables()

    things: list[str] = [
        "aa",
        "bbbbbb",
        f"cc{random.randint(100, 10000)}",
        f"{random.randint(1000, 100000)}dd{random.randint(10000, 100000)}",
        "".join(
            random.choices(
                string.ascii_letters,
                k=random.randint(10, 40),
            )
        ),
    ]

    for name in things:
        await User(name=name, password="test").save()

    items = await User.find(password="test")
    assert len(items) == len(things)
    for i in items:
        assert i.name in things


@pytest.mark.skipif(
    sys.version_info[1] != 12,
    reason="Very long, only run on 3.12",
)
async def test_long_resize(database: discobase.Database):
    @database.table
    class X(discobase.Table):
        foo: str

    await database.build_tables()

    for char in string.ascii_letters:
        await X(foo=char).save()

    items = await X.find()
    assert len(items) == len(string.ascii_letters)
    for i in items:
        assert i.foo in string.ascii_letters


async def test_clean(database: discobase.Database):
    await database.clean()

    with pytest.raises(DatabaseTableError):

        @database.table
        class User(discobase.Table):
            test: str

    @database.table
    class Whatever(discobase.Table):
        foo: str

    await Whatever(foo="bar").save()
    await database.clean()

    assert len(await Whatever.find()) == 0
