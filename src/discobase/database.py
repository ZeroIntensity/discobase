from __future__ import annotations

import asyncio
from base64 import urlsafe_b64decode, urlsafe_b64encode
from contextlib import asynccontextmanager
from threading import Thread
from typing import Coroutine, Dict, NoReturn, Type, TypeVar

import discord
from discord.ext import commands
from pydantic import BaseModel

from ._metadata import Metadata
from .exceptions import DatabaseCorruptionError, NotConnectedError
from .table import Table

__all__ = ("Database",)

T = TypeVar("T", bound=Type[Table])


class _Record(BaseModel):
    content: str
    """Base64 encoded Pydantic model dump of the record."""
    indexes: Dict
    record_ids: list[int]


class Database:
    """
    Top level class representing a Discord
    database bot controller.
    """

    def __init__(self, name: str) -> None:
        """
        Args:
            name: Name of the Discord server that will be used as the database.
        """
        self.name = name
        """Name of the Discord-database server."""
        self.bot = commands.Bot(
            intents=discord.Intents.all(), command_prefix="!"
        )
        """discord.py `Bot` instance."""
        self.guild: discord.Guild | None = None
        """discord.py `Guild` used as the database server."""
        self.tables: set[type[Table]] = set()
        """Set of `Table` objects attached to this database."""
        self.open: bool = False
        """Whether the database is connected."""
        self._metadata_channel: discord.TextChannel | None = None
        """discord.py `TextChannel` that acts as the metadata channel."""
        self._database_metadata: dict[str, Metadata] = {}
        """A dictionary containing all of the table `Metadata` entries"""
        self._task: asyncio.Task[None] | None = None
        # We need to keep a strong reference to the free-flying
        # task
        self._setup_event = asyncio.Event()

        @self.bot.event
        async def on_ready() -> None:
            await self.init()

    @staticmethod
    def _not_connected() -> NoReturn:
        raise NotConnectedError(
            "not connected to the database, did you forget to login?"
        )

    async def init(self) -> None:
        """
        Initializes the database server.
        Generally, you don't want to call this manually.
        """
        await self.bot.wait_until_ready()
        found_guild: discord.Guild | None = None
        for guild in self.bot.guilds:
            if guild.name == self.name:
                found_guild = guild
                break

        if not found_guild:
            self.guild = await self.bot.create_guild(name=self.name)
        else:
            self.guild = found_guild

        metadata_channel_name = f"{self.name}_db_metadata"
        found_channel: discord.TextChannel | None = None
        for channel in self.guild.text_channels:
            if channel.name == metadata_channel_name:
                found_channel = channel
                break

        if not found_channel:
            self._metadata_channel = await self.guild.create_text_channel(
                name=metadata_channel_name
            )
        else:
            self._metadata_channel = found_channel
            async for message in self._metadata_channel.history():
                model = Metadata.model_validate_json(message.content)
                self._database_metadata[model.name] = model

        for table in self.tables:
            await self._create_table(table)

        self._setup_event.set()

    async def wait_ready(self) -> None:
        """Wait until the database is ready."""
        await self._setup_event.wait()

    async def _create_table(
        self,
        table: type[Table],
        initial_size: int = 16,
    ) -> discord.Message | None:
        """
        Creates a new table and all index tables that go with it.
        This writes the table metadata.

        If the table already exists, this method does (almost) nothing.

        Args:
            table: Table schema to create channels for.
            initial_hash_size: the size the index hash tables should start at.

        Returns:
            The `discord.Message` containing all of the metadata
            for the table. This can be useful for testing or
            returning the data back to the user. If this is `None`,
            then the table already existed.
        """

        if not self.guild or not self._metadata_channel:
            self._not_connected()

        name = table.__name__.lower()
        for channel in self.guild.channels:
            if channel == name:
                # The table is already set up, no need to do anything more.
                return

        # The primary table holds the actual records
        primary_table = await self.guild.create_text_channel(name)
        index_channels: dict[str, int] = {}

        for key_name in table.__disco_keys__:
            # Key channels are stored in
            # the format of <table_name>_<field_name>
            index_channel = await self.guild.create_text_channel(
                f"{name}_{key_name}"
            )
            index_channels[index_channel.name] = index_channel.id
            await self._resize_hash(index_channel, initial_size)

        table_metadata = Metadata(
            name=name,
            keys=tuple(table.__disco_keys__),
            table_channel=primary_table.id,
            index_channels=index_channels,
            current_records=0,
            max_records=initial_size,
            message_id=0,
        )
        self._database_metadata[name] = table_metadata
        message = await self._metadata_channel.send(
            table_metadata.model_dump_json()
        )
        # Since Discord generates the message ID, we have to do these
        # message editing shenanigans.
        table_metadata.message_id = message.id
        return await message.edit(content=table_metadata.model_dump_json())

    async def _delete_table(self, table_name: str) -> None:
        """
        Deletes the table and all associated tables.
        This also removes the table metadata
        """

        if not self.guild or not self._metadata_channel:
            self._not_connected()

        table_name = table_name.lower()
        new_table_set: set[type[Table]] = set()

        for table in self.tables:
            if table.__name__.lower() != table_name:
                new_table_set.add(table)
        self.tables = new_table_set

        coros: list[Coroutine] = []
        # This makes sure to only delete channels that relate to the table
        # that is represented by table_name and not channels that contain
        # table_name as a substring of the full name
        for channel in self.guild.channels:
            split_channel_name = channel.name.lower().split("_")
            if split_channel_name[0].lower() == table_name:
                coros.append(channel.delete())

        async for message in self._metadata_channel.history():
            table_metadata = Metadata.model_validate_json(message.content)
            # For some reason, deleting messages with `message.delete()` wasn't
            # working, so we fetch the message again to delete it.
            if table_metadata.name == table_name:
                message_to_delete = await self._metadata_channel.fetch_message(
                    message.id
                )
                coros.append(message_to_delete.delete())

        # We gather() here for performance
        await asyncio.gather(*coros)
        del self._database_metadata[table_name]

    async def _add_record(self, record: Table) -> discord.Message:
        """
        Adds a record to an existing table

        Args:
            record: The record object being written to the table

        Returns:
            The `discord.Message` that contains the new entry. This is helpful
            for saving the direct id of the message in memory if wanted and for
            the message.Content
        """

        if not self.guild or not self._metadata_channel:
            self._not_connected()

        table_metadata = self._get_table_metadata(
            record.__class__.__name__.lower()
        )
        table_metadata.current_records += 1
        if table_metadata.current_records > table_metadata.max_records:
            raise IndexError("The table is full")

        metadata_message = await self._metadata_channel.fetch_message(
            table_metadata.message_id
        )
        metadata_message = await metadata_message.edit(
            content=table_metadata.model_dump_json()
        )

        record_data = _Record(
            content=urlsafe_b64encode(
                record.model_dump_json().encode("utf-8"),
            ).decode("utf-8"),
            indexes={},
        )

        main_table = [
            channel
            for channel in self.guild.channels
            if channel.id == table_metadata.table_channel
        ][0]

        if not isinstance(main_table, discord.TextChannel):
            raise DatabaseCorruptionError(
                f"expected {main_table!r} to be a TextChannel",
            )

        message = await main_table.send(record_data.model_dump_json())
        message_id = message.id

        for field, value in record.model_dump().items():
            for name, cid in table_metadata.index_channels.items():
                if name.lower().split("_")[1] == field.lower():
                    continue

                index_channel = [
                    channel
                    for channel in self.guild.channels
                    if channel.id == cid
                ][0]

                if not isinstance(index_channel, discord.TextChannel):
                    raise DatabaseCorruptionError(
                        f"expected {index_channel!r} to be a TextChannel"
                    )

                messages = [
                    message
                    async for message in index_channel.history(
                        limit=table_metadata.max_records
                    )
                ]
                hashed_field = hash(value)
                message_hash = (
                    hashed_field & 0x7FFFFFFF
                ) % table_metadata.message_id
                content = messages[message_hash].content
                serialized_content: Table | None = (
                    record.model_validate_json(urlsafe_b64decode(content))
                    if content != "null"
                    else None
                )

                if not serialized_content:
                    # This is a null entry, we can just update in place
                    message_content = {
                        "key": hashed_field,
                        "record_ids": [
                            message_id,
                        ],
                    }
                    editable_message = await index_channel.fetch_message(
                        messages[message_hash].id
                    )
                    await editable_message.edit(
                        content=orjson.dumps(message_content).decode("utf-8")
                    )
                    record_data.indexes[field] = editable_message.id

                elif serialized_content.key == hashed_field:
                    existing_content["record_ids"].append(message_id)
                    messages[message_hash].edit(
                        content=orjson.dumps(existing_content).decode("utf-8")
                    )
                    record_dict["indexes"][field] = messages[message_hash].id
                else:
                    index = 1
                    index_message = messages[message_hash + index]
                    while index_message.content != "null":
                        index += 1
                        if (message_hash + index) >= len(messages):
                            index = 0 - message_hash
                        elif message_hash + index == message_hash:
                            raise IndexError("The database is full")

                        index_message = index_channel.messages[
                            message_hash + index
                        ]
                    message_content = {
                        "key": hashed_field,
                        "record_ids": [
                            message_id,
                        ],
                    }
                    editable_message = await index_channel.fetch_message(
                        index_message.id
                    )
                    await editable_message.edit(
                        content=orjson.dumps(message_content).decode("utf-8")
                    )
                    record_dict["indexes"][field] = editable_message.id
                    break
        return await message.edit(content=record_data.model_dump_json())

    async def _find_records(self, table_name: str, **kwargs) -> list[dict]:
        """
        Finds a record based on field values
        """

        if not self.guild:
            self._not_connected()

        table_metadata = self._get_table_metadata(table_name.lower())
        sets_list: list[set[int]] = []

        for field, value in kwargs.items():
            if field not in table_metadata.keys:
                raise AttributeError(
                    f"Table '{table_metadata.name}' has no '{field}' attribute"
                )
            for name, id in table_metadata["index_channels"].items():
                if name.lower().split("_")[1] != field.lower():
                    continue

                index_channel = [
                    channel
                    for channel in self.guild.channels
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
                if (
                    existing_content != "null"
                    or existing_content["key"] != hashed_field
                ):
                    sets_list.append(set(existing_content["record_ids"]))
                    break
                else:
                    i = 1
                    index_message = index_messages[message_hash + i]
                    existing_content = orjson.loads(index_message.content)
                    while (
                        existing_content == "null"
                        or message_hash + i != message_hash
                    ):
                        i += 1
                        index_message = index_channel.messages[message_hash + i]
                        existing_content = orjson.loads(index_message.content)
                        if (message_hash + i) >= len(index_messages):
                            i = 0 - message_hash
                        elif (
                            existing_content != "null"
                            and existing_content["keys"] == value
                        ):
                            sets_list.append(
                                set(existing_content["record_ids"])
                            )
                            break
        records_set = set.intersection(*sets_list)

        main_table = await self.guild.fetch_channel(
            table_metadata.table_channel
        )
        records = []
        for record_id in records_set:
            message = await main_table.fetch_message(record_id)
            records.append(orjson.loads(message.content))

        return records

    def _get_table_metadata(self, table_name: str) -> Metadata:
        """
        Gets the table metadata from the database metadata.
        This raises an exception if the table doesn't exist.

        Args:
            table_name: name of the table to retrieve
        """

        meta: Metadata = self._database_metadata[table_name]
        if not meta:
            raise ValueError(f"table {table_name} does not exist")

        return meta

    async def _resize_hash(
        self,
        index_channel: discord.TextChannel,
        amount: int,
    ) -> None:
        """
        Increases the hash for `index_channel` by amount

        Args:
            index_channel: the channel that contains index data for a database
            amount: the amount to increase the size by
        """
        for _ in range(amount):
            await index_channel.send("null")

    # This needs to be async for use in gather()
    async def _set_open(self) -> None:
        self.open = True

    async def login(self, bot_token: str) -> None:
        """
        Start running the bot.
        """
        # We use _set_open() with a gather to keep a finer link
        # between the `open` attribute and whether it's actually
        # running.
        await asyncio.gather(self.bot.start(token=bot_token), self._set_open())

    def login_task(self, bot_token: str) -> asyncio.Task[None]:
        """
        Call `login()` as a free-flying task, instead of
        blocking the event loop.

        Note that this method stores a reference to the created
        task object, allowing it to be truly "free-flying."

        Args:
            bot_token: Discord API bot token to log in to.

        Returns:
            Created `asyncio.Task` object. Note that the database
            will store this internally, so you don't have to worry
            about `await`ing it later. In most cases, you don't need
            the returned `asyncio.Task` object.

        Example:
            ```py
            import asyncio
            import os

            import discobase


            async def main():
                db = discobase.Database("test")
                db.login_task("...")


            asyncio.run(main())
            ```
        """
        task = asyncio.create_task(self.login(bot_token))
        self._task = task
        return task

    async def close(self) -> None:
        """
        Close the bot connection.
        """
        if not self.open:
            raise ValueError(
                "cannot close a connection that is not open",
            )
        await self.bot.close()

    @asynccontextmanager
    async def conn(self, bot_token: str):
        """
        Connect to the bot under a context manager.
        This is the recommended method to use for logging in.

        Args:
            bot_token: Discord API bot token to log in to.

        Returns:
            An asynchronous context manager.
            See `contextlib.asynccontextmanager` for details.

        Example:
            ```py
            import asyncio
            import os

            import discobase


            async def main():
                db = discobase.Database("test")
                async with db.conn(os.getenv("BOT_TOKEN")):
                    ...  # Your database code


            asyncio.run(main())
            ```
        """
        try:
            self.login_task(bot_token)
            await self.wait_ready()
            yield
        finally:
            await self.close()

    def login_thread(
        self,
        bot_token: str,
        *,
        daemon: bool = False,
        autostart: bool = True,
    ) -> Thread:
        """
        Run the bot in a seperate thread.

        Args:
            bot_token: Discord API bot token.
            daemon: Equivalent to `daemon` parameter in `threading.Thread`
            autostart: Whether to automatically call `start`

        Returns:
            The `Thread` instance used to start the bot.
        """
        thread = Thread(
            target=asyncio.run,
            args=(self.login(bot_token),),
            daemon=daemon,
        )

        if autostart:
            thread.start()

        return thread

    def table(self, clas: T) -> T:
        if not issubclass(clas, Table):
            raise TypeError(
                f"{clas} is not a subclass of Table, did you forget it?",
            )

        clas.__disco_database__ = self
        for field in clas.model_fields:
            clas.__disco_keys__.add(field)

        self.tables.add(clas)
        return clas
