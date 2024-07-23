from __future__ import annotations

import asyncio
import os
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from contextlib import asynccontextmanager
from threading import Thread
from typing import (Any, Coroutine, Dict, Hashable, List, NoReturn, Type,
                    TypeVar)

import discord
from discord.ext import commands
from pydantic import BaseModel, ValidationError

from ._metadata import Metadata
from .exceptions import DatabaseCorruptionError, NotConnectedError
from .table import Table

__all__ = ("Database",)

T = TypeVar("T", bound=Type[Table])


class _Record(BaseModel):
    content: str
    """Base64 encoded Pydantic model dump of the record."""
    indexes: Dict


class _IndexableRecord(BaseModel):
    key: int
    record_ids: List[int]

    @classmethod
    def from_message(cls, message: str) -> _IndexableRecord | None:
        try:
            return (
                cls.model_validate_json(message) if message != "null" else None
            )
        except ValidationError as e:
            raise DatabaseCorruptionError(
                f"got bad _IndexableRecord entry: {message}"
            ) from e


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
        self._tables: dict[str, type[Table]] = {}
        """Dictionary of `Table` objects attached to this database."""
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

    async def _metadata_init(self) -> discord.TextChannel:
        """
        Find the metadata channel.
        If it doesn't exist, this method creates one.
        """
        metadata_channel_name = "_dbmetadata"
        found_channel: discord.TextChannel | None = None
        assert self.guild is not None

        for channel in self.guild.text_channels:
            if channel.name == metadata_channel_name:
                found_channel = channel
                break

        return found_channel or await self.guild.create_text_channel(
            name=metadata_channel_name
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

        self._metadata_channel = await self._metadata_init()
        async for message in self._metadata_channel.history():
            # We need to populate the metadata in-memory, if it exists
            model = Metadata.model_validate_json(message.content)
            self._database_metadata[model.name] = model

        await asyncio.gather(
            *[self._create_table(table) for table in self._tables.values()]
        )
        # At this point, the database is marked as "ready" to the user.
        self._setup_event.set()

    async def wait_ready(self) -> None:
        """Wait until the database is ready."""
        await self._setup_event.wait()

    def _find_channel(self, cid: int) -> discord.TextChannel:
        if not self.guild:
            self._not_connected()

        index_channel = [
            channel for channel in self.guild.channels if channel.id == cid
        ][0]

        if not isinstance(index_channel, discord.TextChannel):
            raise DatabaseCorruptionError(
                f"expected {index_channel!r} to be a TextChannel"
            )

        return index_channel

    def _find_free_message(
        self,
        messages: list[discord.Message],
        message_hash: int,
    ) -> discord.Message:
        offset = 1
        index_message = messages[message_hash + offset]
        while index_message.content != "null":
            offset += 1
            if (message_hash + offset) >= len(messages):
                offset = 0 - message_hash
            elif message_hash + offset == message_hash:
                raise IndexError("The database is full")

            index_message = messages[message_hash + offset]

        return index_message

    async def _edit_message(
        self,
        channel: discord.TextChannel,
        mid: int,
        content: str,
    ) -> None:
        # TODO: Implement caching of the message ID
        editable_message = await channel.fetch_message(mid)
        await editable_message.edit(content=content)

    async def _gen_key_channel(
        self,
        table: str,
        key_name: str,
        *,
        initial_size: int = 4,
    ) -> tuple[str, int]:
        """
        Generate a key channel from the given information.
        This does not check if it exists.

        Args:
            table: Processed channel name of the table.
            key_name: Name of the key, per `__disco_keys__`.
            initial_size: Equivalent to `initial_size` in `_create_table`.

        Returns:
            Tuple containing the channel name
            and the ID of the created channel.
        """
        if not self.guild:
            self._not_connected()

        # Key channels are stored in
        # the format of <table_name>_<field_name>
        index_channel = await self.guild.create_text_channel(
            f"{table}_{key_name}"
        )
        await self._resize_hash(index_channel, initial_size)
        return index_channel.name, index_channel.id

    def _hash(self, metadata: Metadata, value: Hashable) -> tuple[int, int]:
        os.environ["PYTHONHASHSEED"] = str(metadata.hash_seed)
        hashed_field = hash(value)
        message_hash = (hashed_field & 0x7FFFFFFF) % metadata.max_records
        return hashed_field, message_hash

    async def _create_table(
        self,
        table: type[Table],
        initial_size: int = 4,
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

        matching: list[str] = []
        name = table.__disco_name__
        for channel in self.guild.channels:
            for key in table.__disco_keys__:
                if channel.name == f"{name}_{key}":
                    matching.append(key)

        if matching:
            if not len(matching) == len(table.__disco_keys__):
                raise DatabaseCorruptionError(
                    f"only some key channels exist: {', '.join(matching)}",
                )
            # The table is already set up, no need to do anything more.
            return

        # The primary table holds the actual records
        primary_table = await self.guild.create_text_channel(name)
        index_channels: dict[str, int] = {}

        # This is ugly, but this is fast: we generate
        # the key channels in parallel.
        for data in await asyncio.gather(
            *[
                self._gen_key_channel(
                    name,
                    key_name,
                    initial_size=initial_size,
                )
                for key_name in table.__disco_keys__
            ]
        ):
            channel_name, channel_id = data
            index_channels[channel_name] = channel_id

        table_metadata = Metadata(
            name=name,
            keys=tuple(table.__disco_keys__),
            table_channel=primary_table.id,
            index_channels=index_channels,
            current_records=0,
            max_records=initial_size,
            message_id=0,
            hash_seed=secrets.randbelow(10**20),
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

        del self._tables[table_name]
        coros: list[Coroutine] = []
        # This makes sure to only delete channels that relate to the table
        # that is represented by table_name and not channels that contain
        # table_name as a substring of the full name
        for channel in self.guild.channels:
            split_channel_name = channel.name.lower().split("_", maxsplit=1)
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
        Writes a record to an existing table.

        Args:
            record: The record object being written to the table

        Returns:
            The `discord.Message` that contains the new entry.
        """

        if not self.guild or not self._metadata_channel:
            self._not_connected()

        table_metadata = self._get_table_metadata(record.__disco_name__)
        table_metadata.current_records += 1
        if table_metadata.current_records > table_metadata.max_records:
            # TODO: Resize the table here
            raise IndexError("The table is full")

        await self._edit_message(
            self._metadata_channel,
            table_metadata.message_id,
            table_metadata.model_dump_json(),
        )

        record_data = _Record(
            content=urlsafe_b64encode(  # Record JSON data is stored in base64
                record.model_dump_json().encode("utf-8"),
            ).decode("utf-8"),
            indexes={},
        )

        main_table: discord.TextChannel = self._find_channel(
            table_metadata.table_channel
        )
        message = await main_table.send(record_data.model_dump_json())

        for field, value in record.model_dump().items():
            for name, cid in table_metadata.index_channels.items():
                if name.lower().split("_", maxsplit=1)[1] != field.lower():
                    continue

                index_channel: discord.TextChannel = self._find_channel(cid)
                # Load the messages into memory.
                # TODO: Either implement some caching here, or add a limit
                messages = [
                    message
                    async for message in index_channel.history(
                        limit=table_metadata.max_records
                    )
                ]

                hashed_field, target_index = self._hash(table_metadata, value)
                content: str = messages[target_index].content
                serialized_content = _IndexableRecord.from_message(content)

                if not serialized_content:
                    # This is a null entry, we can just update in place
                    message_content = _IndexableRecord(
                        key=hashed_field,
                        record_ids=[
                            message.id,
                        ],
                    )
                    await self._edit_message(
                        index_channel,
                        messages[target_index].id,
                        content=message_content.model_dump_json(),
                    )
                elif serialized_content.key == hashed_field:
                    # This already exists, let's append to the data
                    serialized_content.record_ids.append(message.id)
                    await messages[target_index].edit(
                        content=serialized_content.model_dump_json()
                    )
                else:
                    # Hash collision!
                    index_message: discord.Message = self._find_free_message(
                        messages,
                        target_index,
                    )
                    message_content = _IndexableRecord(
                        key=hashed_field,
                        record_ids=[
                            message.id,
                        ],
                    )
                    await self._edit_message(
                        index_channel,
                        index_message.id,
                        message_content.model_dump_json(),
                    )
                    break

        return await message.edit(content=record_data.model_dump_json())

    async def _find_records(
        self, table_name: str, kwargs: dict[str, Any]
    ) -> list[dict]:
        """
        Find a record based on the specified field values.
        """

        if not self.guild:
            self._not_connected()

        table_metadata = self._get_table_metadata(table_name.lower())
        sets_list: list[set[int]] = []

        for field, value in kwargs.items():
            if field not in table_metadata.keys:
                raise DatabaseCorruptionError(
                    f"table '{table_metadata.name}' has no '{field}' attribute"
                )
            for name, cid in table_metadata.index_channels.items():
                if name.lower().split("_")[1] != field.lower():
                    continue

                index_channel: discord.TextChannel = self._find_channel(cid)
                index_messages = [
                    message
                    async for message in index_channel.history(
                        limit=table_metadata.max_records
                    )
                ]
                hashed_field, target_index = self._hash(table_metadata, value)
                content: str = index_messages[target_index].content
                serialized_content = _IndexableRecord.from_message(content)

                if not serialized_content:
                    # Nothing was found
                    continue

                if serialized_content.key == hashed_field:
                    sets_list.append(set(serialized_content.record_ids))
                else:
                    raise DatabaseCorruptionError(
                        "not implemented: hash collision"
                    )
                    # content: str = index_messages[target_index].content

        main_table = await self.guild.fetch_channel(
            table_metadata.table_channel
        )
        if not isinstance(main_table, discord.TextChannel):
            raise DatabaseCorruptionError(
                f"expected {main_table!r} to be a TextChannel"
            )

        table = self._tables[table_name]
        records = []
        for record_ids in sets_list:
            for record_id in record_ids:
                message = await main_table.fetch_message(record_id)
                record = _Record.model_validate_json(message.content)
                records.append(
                    table.model_validate_json(
                        urlsafe_b64decode(record.content),
                    )
                )

        return records

    def _get_table_metadata(self, table_name: str) -> Metadata:
        """
        Gets the table metadata from the database metadata.
        This raises an exception if the table doesn't exist.

        Args:
            table_name: name of the table to retrieve
        """

        meta: Metadata | None = self._database_metadata.get(table_name)
        if not meta:
            tables = ", ".join(
                [i.name for i in self._database_metadata.values()]
            )
            raise DatabaseCorruptionError(
                f"table metadata for {table_name} was not found. available tables (in metadata) are: {tables}"  # noqa
            )

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

        clas.__disco_name__ = clas.__name__.lower()
        self._tables[clas.__disco_name__] = clas
        return clas
