from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from threading import Thread
from typing import Type, TypeVar

import discord
import orjson
from discord.ext import commands

from .table import Table

__all__ = ("Database",)

T = TypeVar("T", bound=Type[Table])


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
        self._database_metadata: list[dict] = []
        """a list containing all of the table metadata entries"""
        self._task: asyncio.Task[None] | None = None
        # We need to keep a strong reference to the free-flying
        # task
        self._setup_event = asyncio.Event()

        @self.bot.event
        async def on_ready() -> None:
            await self.init()

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

        table_metadata: list[dict] = []
        if not found_channel:
            self._metadata_channel = await self.guild.create_text_channel(
                name=metadata_channel_name
            )
        else:
            self._metadata_channel = found_channel
            self._database_metadata = [
                orjson.loads(message.content)
                async for message in self._metadata_channel.history()
            ]

        if len(table_metadata) > 0:
            self._load_table_classes(table_metadata)

        for table in self.tables:
            await self._create_table(table)

        self._setup_event.set()

    async def wait_ready(self) -> None:
        """Wait until the database is ready."""
        await self._setup_event.wait()

    def _load_table_classes(self, table_metadata: list[dict]) -> None:
        """
        This reloads all of the Table classes using the metadata from the
        metadata_channel

        Args:
            table_metadata: List of dictionary representations of each table's metadata
              dictionary_keys:
                name: The table name,
                keys: a tuple containing the name of all keys(fields) of the table,
                table_channel: the channel ID that holds the main table,
                index_channels: a dictionary of (index_channel_name: index_channel_id) key, value pairs
                current_records: The current number of records in the table,
                max_records: the max number of records in the table before a resize is required,
        """
        pass

    async def _create_table(
        self, table: type[Table], initial_hash_size: int = 16
    ) -> discord.Message:
        """
        Creates a new table and all index tables that go with it.
        This writes the table metadata.

        If the table already exists, this method does (almost) nothing.

        Args:
            table: Table schema to create channels for.
            initial_hash_size: the size the index hash tables should start at.

        Returns:
            The `discord.Message` containing all of the metadata for the table. This
            can be useful for testing or returning the data back to the user
        """

        if self.guild is None:
            raise TypeError("(internal error) guild is None")

        name = table.__name__.lower()
        for channel in self.guild.channels:
            if channel == name:
                # The table is already set up, no need to do anything more.
                return
        primary_table = await self.guild.create_text_channel(name)
        index_channels: dict[str, int] = dict()
        for key_name in table.model_fields.keys():
            index_channel = await self.guild.create_text_channel(
                f"{name}_{key_name}"
            )
            index_channels[index_channel.name] = index_channel.id
            await self._resize_hash(index_channel, initial_hash_size)

        table_metadata = {
            "name": name,
            "keys": tuple(table.model_fields.keys()),
            "table_channel": primary_table.id,
            "index_channels": index_channels,
            "current_records": 0,
            "max_records": initial_hash_size,
        }

        self._database_metadata.append(table_metadata)

        message_text = orjson.dumps(table_metadata).decode("utf-8")

        if not self._metadata_channel:
            raise TypeError(
                "(internal error) expected _metadata_channel to be non-None"
            )

        message = await self._metadata_channel.send(message_text)
        table_metadata["my_message_id"] = message.id

        return await message.edit(
            content=orjson.dumps(table_metadata).decode("utf-8")
        )

    async def _delete_table(self, table_name: str):
        """
        Deletes the table and all associated tables.
        This also removes the table metadata
        """

        table_name = table_name.lower()

        new_table_set: set[type[Table]] = set()
        for table in self.tables:
            if table.__name__.lower() != table_name:
                new_table_set.add(table)
        self.tables = new_table_set

        # This makes sure to only delete channels that relate to the table that is represented by table_name
        # and not channels that contain table_name as a substring of the full name
        for channel in self.guild.channels:
            split_channel_name = channel.name.lower().split("_")
            if split_channel_name[0].lower() == table_name:
                await channel.delete()

        metadata_messages = [
            message async for message in self._metadata_channel.history()
        ]

        # For some reason deleting messages with `await message.delete()` was not working
        # That is why I fetch the message again to delete it.
        for message in metadata_messages:
            table_metadata = orjson.loads(message.content)
            if table_metadata["name"] == table_name:
                message_to_delete = await self._metadata_channel.fetch_message(
                    message.id
                )
                await message_to_delete.delete()

        database_metadata = []
        for table in self._database_metadata:
            if table["name"] != table_name:
                database_metadata.append(table)
        self._database_metadata = database_metadata

    async def _add_record(self, record: Table) -> discord.Message:
        """
        Adds a record to an existing table

        Args:
            record: The record object being written to the table

        Return:
            The `discord.Message` that contains the new entry. This is helpful
            for saving the direct id of the message in memory if wanted and for
            the message.Content
        """

        table_metadata = self._get_table_metadata(
            record.__class__.__name__.lower()
        )
        if table_metadata is None:
            raise TypeError(
                f"Table({record.__class__.__name__}) does not exist."
            )

        table_metadata["current_records"] += 1
        if table_metadata["current_records"] > table_metadata["max_records"]:
            raise IndexError("The table is full")

        metadata_message = await self._metadata_channel.fetch_message(
            table_metadata["my_message_id"]
        )
        metadata_message = await metadata_message.edit(
            content=orjson.dumps(table_metadata).decode("utf-8")
        )

        record_dict = {}
        record_dict["content"] = record.model_dump()
        record_dict["indexes"] = {}

        main_table = [
            channel
            for channel in self.guild.channels
            if channel.id == table_metadata["table_channel"]
        ][0]

        message = await main_table.send(
            orjson.dumps(record_dict).decode("utf-8")
        )
        message_id = message.id

        for field, value in record_dict["content"].items():
            for name, id in table_metadata["index_channels"].items():
                if name.lower().split("_")[1] == field.lower():
                    index_channel = [
                        channel
                        for channel in self.guild.channels
                        if channel.id == id
                    ][0]
                    messages = [
                        message
                        async for message in index_channel.history(
                            limit=table_metadata["max_records"]
                        )
                    ]
                    hashed_field = hash(value)
                    message_hash = (
                        hashed_field & 0x7FFFFFFF
                    ) % table_metadata["max_records"]
                    content = messages[message_hash].content
                    existing_content = (
                        orjson.loads(content) if content != "null" else content
                    )

                    if (
                        existing_content != "null"
                        and existing_content["key"] == hashed_field
                    ):
                        existing_content["record_ids"].append(message_id)
                        messages[message_hash].edit(
                            content=orjson.dumps(existing_content)
                        )
                        record_dict["indexes"][field] = messages[
                            message_hash
                        ].id
                    elif existing_content == "null":
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
                            content=orjson.dumps(message_content).decode(
                                "utf-8"
                            )
                        )
                        record_dict["indexes"][field] = editable_message.id
                    else:
                        i = 1
                        index_message = messages[message_hash + i]
                        while index_message.content != "null":
                            i += 1
                            if (message_hash + i) >= len(messages):
                                i = 0 - message_hash
                            elif message_hash + i == message_hash:
                                raise IndexError("The database is full")
                            index_message = index_channel.messages[
                                message_hash + i
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
                            content=orjson.dumps(message_content).decode(
                                "utf-8"
                            )
                        )
                        record_dict["indexes"][field] = editable_message.id
                        break
        return await message.edit(
            content=orjson.dumps(record_dict).decode("utf-8")
        )

    async def _find_records(self, table_name: str, **kwargs) -> list[dict]:
        """
        Finds a record based on field values
        """

        table_metadata = self._get_table_metadata(table_name.lower())

        sets_list: list[set[int]] = []

        for field, value in kwargs.items():
            if field not in table_metadata["keys"]:
                raise AttributeError(
                    f"Table '{table_metadata["name"]}' has no '{field}' attribute"
                )
            for name, id in table_metadata["index_channels"].items():
                if name.lower().split("_")[1] == field.lower():
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
                    message_hash = (
                        hashed_field & 0x7FFFFFFF
                    ) % table_metadata["max_records"]
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
                            index_message = index_channel.messages[
                                message_hash + i
                            ]
                            existing_content = orjson.loads(
                                index_message.content
                            )
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
            table_metadata["table_channel"]
        )
        records = []
        for record_id in records_set:
            message = await main_table.fetch_message(record_id)
            records.append(orjson.loads(message.content))

        return records

    def _get_table_metadata(self, table_name: str) -> dict | None:
        """
        Gets the table metadata from the database metadata

        Args:
            table_name: name of the table to retrieve

        Returns:
            dict: The table was found successfully
            None: The table does not exist
        """
        for table in self._database_metadata:
            if table_name.lower() == table["name"]:
                return table
        return None

    async def _resize_hash(
        self, index_channel: discord.TextChannel, amount: int
    ) -> None:
        """
        Increases the hash for index_channel by amount

        Args:
            index_channel: the channel that contains index data for a database
            amount: the amount to increase the size by
        """
        for _ in range(0, amount):
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
                dv.login_task("...")


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
