from __future__ import annotations

import asyncio
import hashlib
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Iterable
from contextlib import asynccontextmanager
from datetime import datetime
from pkgutil import iter_modules
from typing import (Any, Callable, Coroutine, Dict, List, NoReturn, Optional,
                    Type, TypeVar, Union)

import discord
from discord.ext import commands
from discord.utils import snowflake_time, time_snowflake
from loguru import logger
from pydantic import (BaseModel, ValidationError, ValidationInfo,
                      ValidatorFunctionWrapHandler, WrapValidator)
from typing_extensions import Annotated

from ._metadata import Metadata
from .exceptions import (DatabaseCorruptionError, DatabaseStorageError,
                         DatabaseTableError, NotConnectedError)
from .table import Table

__all__ = ("Database", "References")

T = TypeVar("T", bound=Type[Table])
SupportsDiscoHash = Union[str, int, Iterable["SupportsDiscoHash"]]


def _validate_ref(
    value: Any,
    handler: ValidatorFunctionWrapHandler,
    info: ValidationInfo,
) -> int:
    print(info.mode, repr(value), info)
    if info.mode == "json":
        if not isinstance(value, int):
            raise DatabaseCorruptionError("a")
        return handler(value)

    if not isinstance(value, Table):
        raise DatabaseCorruptionError("b")

    if value.__disco_id__ == -1:
        raise DatabaseStorageError(
            f"cannot store {value!r} as a reference, since it is not in the database"  # noqa
        )

    return value.__disco_id__


References = Annotated[T, WrapValidator(_validate_ref)]


class _Record(BaseModel):
    content: str
    """Base64 encoded Pydantic model dump of the record."""
    indexes: Dict

    @classmethod
    def from_data(cls, data: Table) -> _Record:
        logger.debug(f"Generating a _Record from data: {data}")
        return _Record(
            content=urlsafe_b64encode(  # Record JSON data is stored in base64
                data.model_dump_json().encode("utf-8"),
            ).decode("utf-8"),
            indexes={},
        )

    def decode_content(self, record: Table | type[Table]) -> Table:
        return record.model_validate_json(urlsafe_b64decode(self.content))


class _IndexableRecord(BaseModel):
    key: int
    """Hashed value of the key."""
    record_ids: List[int]
    """Message IDs of the records that correspond to this key."""
    next_value: Optional[_IndexableRecord] = None
    """
    Temporary placeholder value for the next entry.
    Only for use in resizing.
    """

    @classmethod
    def from_message(cls, message: str) -> _IndexableRecord | None:
        """
        Generate an `_IndexableRecord` instance from message content.

        Args:
            message: Message content to parse as JSON.

        Returns:
            An `_IndexableRecord` instance, or `None`, if the message
            was `null`.
        """
        logger.debug(f"Parsing {message} into an _IndexableRecord")
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
            intents=discord.Intents.all(),
            command_prefix="!",
        )
        """discord.py `Bot` instance."""
        self.guild: discord.Guild | None = None
        """discord.py `Guild` used as the database server."""
        self.tables: dict[str, type[Table]] = {}
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
        self._on_ready_exc: BaseException | None = None

        # Here be dragons: https://github.com/ZeroIntensity/discobase/issues/49
        #
        # `on_ready` in discord.py swallows all exceptions, which
        # goes against some connect-and-disconnect behavior
        # that we want to allow in discobase.
        #
        # We need to store the exception, and then raise in wait_ready()
        # in order to properly handle it, otherwise the discord.py
        # logger just swallows it and pretends nothing happened.
        #
        # This also caused a deadlock with _setup_event, which caused
        # CI to run indefinitely.
        @self.bot.event
        @logger.catch(reraise=True)
        async def on_ready() -> None:
            try:
                await self.init()
            except BaseException as e:
                await self.bot.close()
                if self._task:
                    self._task.cancel("bot startup failed")

                self._setup_event.set()
                self._on_ready_exc = e
                raise  # This is swallowed!

    def _not_connected(self) -> NoReturn:
        """
        Complain about the database not being connected.

        Generally speaking, this is called when `guild` or something
        other is `None`.
        """

        raise NotConnectedError(
            "not connected to the database, did you forget to login?"
        )

    async def _metadata_init(self) -> discord.TextChannel:
        """
        Find the metadata channel.
        If it doesn't exist, this method creates one.

        Returns:
            The metadata channel, either created or found.
        """
        metadata_channel_name = "_dbmetadata"
        found_channel: discord.TextChannel | None = None
        assert self.guild is not None

        for channel in self.guild.text_channels:
            if channel.name == metadata_channel_name:
                found_channel = channel
                logger.info("Found metadata channel!")
                break

        return found_channel or await self.guild.create_text_channel(
            name=metadata_channel_name
        )

    async def init(self) -> None:
        """
        Initializes the database server.

        Generally, you don't want to call this manually, but
        this is considered to be a public interface.
        """
        logger.info("Initializing the bot.")
        # Load external commands
        for module in iter_modules(path=["cogs"], prefix="cogs."):
            logger.debug(f"Loading module with cog: {module}")
            await self.bot.load_extension(module.name)

        await self.bot.tree.sync()
        logger.info("Waiting until bot is logged in.")
        await self.bot.wait_until_ready()
        logger.info("Bot is ready!")
        found_guild: discord.Guild | None = None
        for guild in self.bot.guilds:
            if guild.name == self.name:
                found_guild = guild
                break

        if not found_guild:
            logger.info("No guild found, making one.")
            self.guild = await self.bot.create_guild(name=self.name)
        else:
            logger.info("Found an existing guild.")
            self.guild = found_guild

        await self.build_tables()
        # At this point, the database is marked as "ready" to the user.
        self._setup_event.set()

        assert self._metadata_channel is not None
        logger.info(
            f"Invite to server: {await self._metadata_channel.create_invite()}"
        )

    async def build_tables(self) -> None:
        """
        Generate all internal metadata and construct tables.

        Calling this manually is useful if e.g. you want
        to load tables *after* calling `login` (or `login_task`, or
        `conn`, same difference.)

        This method is safe to call multiple times.

        Example:
            ```py
            import asyncio
            import discobase

            async def main():
                db = discobase.Database("My database")
                db.login_task("My bot token")

                @db.table
                class MyLateTable(discobase.Table):
                    something: str

                # Load MyLateTable into database
                await db.build_tables()

            asyncio.run(main())
            ```
        """
        self._metadata_channel = await self._metadata_init()
        async for message in self._metadata_channel.history():
            # We need to populate the metadata in-memory, if it exists
            model = Metadata.model_validate_json(message.content)
            self._database_metadata[model.name] = model

        tasks = [
            asyncio.create_task(self._create_table(table))
            for table in self.tables.values()
        ]
        logger.debug(f"Creating tables with gather(): {tasks}")
        await asyncio.gather(*tasks)

    async def wait_ready(self) -> None:
        """
        Wait until the database is ready.
        """
        logger.info("Waiting until the database is ready.")
        await self._setup_event.wait()
        logger.info("Done waiting!")
        # See #49, we need to propagate errors in `on_ready` here.
        if self._on_ready_exc:
            logger.error("on_ready() failed, propagating now.")
            raise self._on_ready_exc

    def _find_channel(self, cid: int) -> discord.TextChannel:
        # TODO: Implement caching for this function.
        if not self.guild:
            self._not_connected()

        index_channel = [
            channel for channel in self.guild.channels if channel.id == cid
        ][0]

        if not isinstance(index_channel, discord.TextChannel):
            raise DatabaseCorruptionError(
                f"expected {index_channel!r} to be a TextChannel"
            )

        logger.debug(f"Found channel ID {cid}: {index_channel!r}")
        return index_channel

    async def _find_collision_message(
        self,
        channel: discord.TextChannel,
        metadata: Metadata,
        index: int,
        *,
        search_func: Callable[[str], bool] = lambda s: s == "null",
    ) -> discord.Message:
        """
        Search for a message via a worst-case O(n) search in the event
        of a hash collision.

        Args:
            channel: Index channel to search.
            metadata: Metadata for the whole table.
            index: The index to start at.
            search_func: Function to check if the message content is good.
        """
        logger.debug(
            f"Looking up hash collision entry using search function: {search_func}"  # noqa
        )
        offset: int = index
        while True:
            if (offset + 1) >= metadata.max_records:
                logger.debug("We need to wrap around the table.")
                offset = 0
            else:
                offset += 1

            if offset == index:
                raise DatabaseCorruptionError(
                    f"index channel {channel!r} has no free messages, table was likely not resized."  # noqa
                )

            message = await self._lookup_message(
                channel,
                metadata,
                offset,
            )
            logger.debug(
                f"Hash collision search at index: {offset} {message=}",
            )
            if search_func(message.content):
                logger.debug(
                    f"Done searching for collision message: {message.content}"
                )
                return message

    async def _edit_message(
        self,
        channel: discord.TextChannel,
        mid: int,
        content: str,
    ) -> None:
        """
        Edit a message given the channel, message ID, and content.

        This should *not* be used over `discord.Message.edit`, it's simply
        a handy utility to use when you only have the message ID.
        """
        # TODO: Implement caching of the message ID
        editable_message = await channel.fetch_message(mid)
        logger.debug(f"Editing message (ID {mid}) to {content}")
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
        logger.debug(f"Generated key channel: {index_channel}")
        await self._resize_hash(index_channel, initial_size)
        return index_channel.name, index_channel.id

    @staticmethod
    def _to_index(metadata: Metadata, value: int) -> int:
        """
        Generate an index from a hash number based
        on the metadata's `max_records`.

        Args:
            metadata: Metadata object for the channel.
            value: Integer hash, positive or negative.

        Returns:
            Index in range of `metadata.max_records`.
        """
        index = (value & 0x7FFFFFFF) % metadata.max_records
        logger.debug(
            f"Hashed value {value} turned into index: {index} ({metadata.max_records=})"  # noqa
        )
        return index

    def _hash(
        self,
        value: SupportsDiscoHash,
    ) -> int:
        """
        Hash the field into an integer.

        Args:
            value: Any discobase-hashable object.

        Returns:
            An integer, positive or negative, representing the unique hash.
            This is always the same thing across programs.
        """
        logger.debug(f"Hashing object: {value!r}")
        if isinstance(value, str):
            hashed_str = int(
                hashlib.sha1(value.encode("utf-8")).hexdigest(),
                16,
            )
            logger.debug(f"Hashed string {value!r} into {hashed_str}")
            return hashed_str
        elif isinstance(value, Iterable):

            # This is a bit hacky, but this lets us support any
            # iterable object.
            class _Transport:
                def __init__(self, hash_num: int) -> None:
                    self.hash_num = hash_num

                def __hash__(self) -> int:
                    return self.hash_num

            hashes: list[_Transport] = []
            for item in value:
                hashes.append(_Transport(self._hash(item)))

            return hash(tuple(hashes))
        elif isinstance(value, int):
            return value
        elif isinstance(value, dict):
            raise NotImplementedError
        else:
            raise DatabaseStorageError(f"unhashable: {value!r}")

    def _as_hashed(
        self,
        metadata: Metadata,
        value: SupportsDiscoHash,
    ) -> tuple[int, int]:
        """
        Get the hash number and index for `value`.
        """
        hashed = self._hash(value)
        return hashed, self._to_index(metadata, hashed)

    async def _lookup_message(
        self,
        channel: discord.TextChannel,
        metadata: Metadata,
        index: int,
    ) -> discord.Message:
        """
        Lookup a message by it's index in the table.

        Args:
            channel: Index channel to search.
            metadata: Metadata for the entire table.
            index: Index to get.

        Returns:
            The found message.

        Raises:
            DatabaseCorruptionError: Could not find the index.
        """
        logger.debug(f"Looking up message: {index}")
        for timestamp, rng in metadata.time_table.items():
            start: int = rng[0]
            end: int = rng[1]
            if index not in range(
                start, end
            ):  # Pydantic doesn't support ranges
                continue

            logger.debug(f"In range: {start} - {end}")
            current_index: int = 0
            async for msg in channel.history(
                limit=end - start, before=snowflake_time(timestamp)
            ):
                if current_index == (index - start):
                    logger.debug(f"{msg} found at index {current_index}")
                    return msg
                current_index += 1

            raise DatabaseCorruptionError(
                f"range for {timestamp} in table {metadata.name} does not contain index {index}"  # noqa
            )

        raise DatabaseCorruptionError(
            f"message index out of range for table {metadata.name}: {index}"
        )

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

        name = table.__disco_name__

        try:
            existing_metadata = self._get_table_metadata(name)
        except DatabaseCorruptionError:
            logger.info("The metadata does not exist.")
        else:
            if set(existing_metadata.keys) != table.__disco_keys__:
                logger.error(
                    f"stored keys: {', '.join(existing_metadata.keys)}, table keys: {', '.join(table.__disco_keys__)}"  # noqa
                )
                raise DatabaseCorruptionError(
                    f"schema for table {name} changed"
                )

        matching: list[str] = []
        for channel in self.guild.channels:
            for key in table.__disco_keys__:
                if channel.name == f"{name}_{key}":
                    matching.append(key)

        if matching:
            if not len(matching) == len(table.__disco_keys__):
                raise DatabaseCorruptionError(
                    f"only some key channels exist: {', '.join(matching)}",
                )

            logger.info(f"Table is already set up: {table.__disco_name__}")
            table.__disco_ready__ = True
            return

        logger.info(f"Building table: {table.__disco_name__}")

        # The primary table holds the actual records
        primary_table = await self.guild.create_text_channel(name)
        logger.debug(f"Generated primary table: {primary_table!r}")
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
            time_table={time_snowflake(datetime.now()): (0, initial_size)},
            message_id=0,
        )
        self._database_metadata[name] = table_metadata
        logger.debug(f"Generated table metadata: {table_metadata!r}")
        message = await self._metadata_channel.send(
            table_metadata.model_dump_json()
        )

        table.__disco_ready__ = True
        # Since Discord generates the message ID, we have to do these
        # message editing shenanigans.
        table_metadata.message_id = message.id
        return await message.edit(content=table_metadata.model_dump_json())

    async def _delete_table(self, table_name: str) -> None:
        """
        Deletes the table and all associated tables.

        This also removes the table metadata from the
        metadata channel.
        """

        # TODO: Refactor this function
        if not self.guild or not self._metadata_channel:
            self._not_connected()

        del self.tables[table_name]
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

    async def _resize_channel(
        self,
        metadata: Metadata,
        channel: discord.TextChannel,
    ) -> None:
        """
        The implementation of resizing a channel. This method assumes
        that `metadata.max_records` has already been doubled.

        This is meant for use in `gather()`, for optimal performance.

        Args:
            metadata: Metadata for the entire table.
            channel: Index channel to resize.
        """
        logger.debug(
            f"Resizing channel: {channel!r} for table {metadata.name}",
        )
        old_size: int = metadata.max_records // 2
        await self._resize_hash(channel, old_size)
        rng = (
            old_size,
            metadata.max_records,
        )

        for snowflake, time_range in metadata.time_table.copy().items():
            # We only want one time stamp for the range, this forces
            # the latest one to always be used -- that's a good thing,
            # we don't want to risk having messages from the previous range
            # in this one.
            if time_range == rng:
                del metadata.time_table[snowflake]

        metadata.time_table[time_snowflake(datetime.now())] = rng
        # Now, we have to move everything into the correct position.
        #
        # Note that this shouldn't put everything into memory, as
        # each previous iteration will be freed -- this is good
        # for scalability.
        async for msg in channel.history(
            limit=old_size,
            oldest_first=True,
        ):
            msg = await channel.fetch_message(msg.id)  # TODO: Remove this
            record = _IndexableRecord.from_message(msg.content)
            if not record:
                continue

            new_index: int = self._to_index(metadata, record.key)
            target = await self._lookup_message(
                channel,
                metadata,
                new_index,
            )
            next_record = _IndexableRecord.from_message(target.content)
            inplace: bool = True
            overwrite: bool = True

            if next_record:
                if next_record.next_value:
                    logger.info("Hash collision in resize!")
                    target = await self._find_collision_message(
                        channel,
                        metadata,
                        new_index,
                    )
                    # `inplace` is True, so we fall
                    # through to the inplace edit.
                    #
                    # To be fair, I'm not too sure if this is
                    # the best approach, this might be worth
                    # refactoring in the future.
                else:
                    logger.info("Updating record at the new index.")
                    inplace = False
                    logger.debug(
                        f"{next_record} marked as the next value location ({target.id=})"  # noqa
                    )

                    if record.next_value:
                        record.next_value = None
                        # Here be dragons: if we overwrite the `next_value`
                        # with `None` to prevent a doubly-nested copy in the
                        # JSON, we have to mark this message to *not* be
                        # overwritten, otherwise we lose that data.
                        overwrite = False

                    next_record.next_value = record
                    content = next_record.model_dump_json()
                    logger.debug(f"Editing {target.content} to {content}")
                    await target.edit(content=content)

            if inplace:
                # In case of a hash collision, we want to mark
                # this as having a `next_value`, so it doesn't get
                # overwritten.
                #
                # We copy this to prevent a recursive model dump.
                if record.next_value:
                    record.next_value = None
                    overwrite = False

                copy = record.model_copy()
                copy.next_value = record
                logger.info(
                    "Target index does not have an entry, updating in-place."
                )
                content = copy.model_dump_json()
                logger.debug(f"Editing in-place null to {content}")
                assert target.content == "null"
                await target.edit(content=content)

            # Technically speaking, the index could
            # remain the same. We need to check for that.
            if (not record.next_value) and (target != msg) and overwrite:
                await msg.edit(content="null")

        # Finally, all the next_value attributes have been set, we can
        # go through and update each record.
        #
        # The overall algorithm is O(2n), but it's much more scalable
        # than trying to put the entire table into memory in order to
        # resize it.
        #
        # This algorithm is pretty much infinitely scalable, if you factor
        # out Discord's ratelimit.
        async for msg in channel.history(
            limit=metadata.max_records,
            oldest_first=True,
        ):
            msg = await channel.fetch_message(msg.id)  # TODO: Remove this
            record = _IndexableRecord.from_message(msg.content)
            if not record:
                continue

            logger.debug(f"Handling movement of {record!r}")
            if not record.next_value:
                raise DatabaseCorruptionError(
                    "all existing records after resize should have next_value",  # noqa
                )

            if record.next_value.next_value:
                raise DatabaseCorruptionError(
                    f"doubly nested next_value found: {record.next_value.next_value!r} in {record!r}"  # noqa
                )

            content = record.next_value.model_dump_json()
            logger.debug(f"Replacing {msg.content} with {content}")
            await msg.edit(content=content)

    async def _resize_table(self, metadata: Metadata) -> None:
        """
        Resize all the index channels in a table.

        Args:
            metadata: Metadata for the entire table.
        """
        if not self._metadata_channel:
            self._not_connected()

        metadata.max_records *= 2
        logger.info(
            f"Resizing table {metadata.name} to {metadata.max_records}"  # noqa
        )
        await asyncio.gather(
            *[
                self._resize_channel(metadata, self._find_channel(cid))
                for cid in metadata.index_channels.values()
            ]
        )

        # Dump the new metadata
        await self._edit_message(
            self._metadata_channel,
            metadata.message_id,
            metadata.model_dump_json(),
        )
        logger.info(
            f"Table {metadata.name} is now of size {metadata.max_records}"
        )

    async def _inc_records(self, metadata: Metadata) -> None:
        """
        Increment the `current_records` number on the
        target metadata. This resizes the table if the maximum
        size is reached.

        Args:
            metadata: Metadata object to increment `current_records` on.
        """
        if not self._metadata_channel:
            self._not_connected()

        metadata.current_records += 1
        if metadata.current_records > metadata.max_records:
            logger.info("The table is full! We need to resize it.")
            await self._resize_table(metadata)

        await self._edit_message(
            self._metadata_channel,
            metadata.message_id,
            metadata.model_dump_json(),
        )

    async def _write_index_record(
        self,
        channel: discord.TextChannel,
        metadata: Metadata,
        index: int,
        hashed: int,
        record_id: int,
    ) -> None:
        """
        Write an index record to the specified channel, using
        a known hash and index.

        Args:
            channel: Target index channel to store the index record at.
            metadata: Metadata for the entire table.
            index: Index to store the record at in the table.
            hashed: Integer hash of the original value e.g. from `_hash`.
            record_id: Message ID of the record in the main table.
        """
        entry_message: discord.Message = await self._lookup_message(
            channel,
            metadata,
            index,
        )
        serialized_content = _IndexableRecord.from_message(
            entry_message.content
        )

        if not serialized_content:
            logger.info("This is a null entry, we can just update in place.")
            await self._inc_records(metadata)
            message_content = _IndexableRecord(
                key=hashed,
                record_ids=[
                    record_id,
                ],
            )
            await entry_message.edit(content=message_content.model_dump_json())
        elif serialized_content.key == hashed:
            # See https://github.com/ZeroIntensity/discobase/issues/50
            #
            # We don't want to call _inc_records() here, because we aren't
            # using up a `null` space.
            logger.info("This already exists, let's append to the data.")
            serialized_content.record_ids.append(record_id)
            await entry_message.edit(
                content=serialized_content.model_dump_json()
            )
        else:
            logger.info("Hash collision!")
            await self._inc_records(metadata)
            index_message = await self._find_collision_message(
                channel,
                metadata,
                index,
            )
            collision_entry = _IndexableRecord(
                key=hashed,
                record_ids=[
                    record_id,
                ],
            )
            await index_message.edit(content=collision_entry.model_dump_json())

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

        record_data = _Record.from_data(record)
        main_table: discord.TextChannel = self._find_channel(
            table_metadata.table_channel
        )
        message = await main_table.send(record_data.model_dump_json())

        for field, value in record.model_dump().items():
            for name, cid in table_metadata.index_channels.items():
                if name.lower().split("_", maxsplit=1)[1] != field.lower():
                    continue

                index_channel: discord.TextChannel = self._find_channel(cid)
                hashed_field, target_index = self._as_hashed(
                    table_metadata,
                    value,
                )
                await self._write_index_record(
                    index_channel,
                    table_metadata,
                    target_index,
                    hashed_field,
                    message.id,
                )

        return await message.edit(content=record_data.model_dump_json())

    async def _update_record(self, record: Table) -> None:
        """
        Updates an existing record in a table.

        Args:
            record: The record object being written to the table

        Returns:
            The `discord.Message` that contains the new entry.
        """
        if record.__disco_id__ == -1:
            # Sanity check
            raise DatabaseCorruptionError("record must have an id to update")

        # TODO: Gather the coros in this function
        metadata = self._get_table_metadata(record.__disco_name__)
        main_table: discord.TextChannel = self._find_channel(
            metadata.table_channel
        )
        msg = await main_table.fetch_message(record.__disco_id__)
        current = _Record.model_validate_json(msg.content).decode_content(
            record
        )
        await msg.edit(content=_Record.from_data(record).model_dump_json())

        for new, old in zip(
            record.model_dump().items(),
            current.model_dump().items(),
        ):
            field = new[0]
            if field != old[0]:
                raise DatabaseCorruptionError(
                    f"field name {field} does not match {old[0]}"
                )

            new_value = new[1]
            old_value = old[1]
            if new_value == old_value:
                # Nothing changed
                continue

            channel = self._find_channel(
                metadata.index_channels[f"{record.__disco_name__}_{field}"]
            )
            hashed_field, target_index = self._as_hashed(
                metadata,
                new_value,
            )
            await self._write_index_record(
                channel,
                metadata,
                target_index,
                hashed_field,
                msg.id,
            )

            old_index = self._to_index(metadata, self._hash(old_value))
            old_msg = await self._lookup_message(channel, metadata, old_index)
            old_record = _IndexableRecord.from_message(old_msg.content)

            if not old_record:
                raise DatabaseCorruptionError("got null record somehow")

            if not len(old_record.record_ids):
                # We can nullify this entry
                await old_msg.edit(content="null")
            else:
                # There are other entries with this value, only remove this ID
                old_record.record_ids.remove(msg.id)
                await old_msg.edit(content=old_record.model_dump_json())

    async def _find_records(
        self,
        table_name: str,
        query: dict[str, Any],
    ) -> list[Table]:
        """
        Find a record based on the specified field values.

        Args:
            table_name: Name of the table, may be unprocessed.
            query: Dictionary containing field-value pairs.

        Returns:
            A list of `Table` objects (or really, a list of objects
            that inherit from `Table`), with the appropriate values
            specified by `query`.
        """

        if not self.guild:
            self._not_connected()

        table_metadata = self._get_table_metadata(table_name.lower())
        sets_list: list[set[int]] = []

        logger.debug(f"Looking for query {query!r} in {table_name}")
        for field, value in query.items():
            if field not in table_metadata.keys:
                raise ValueError(
                    f"table {table_metadata.name} has no field {field}"
                )

            for name, cid in table_metadata.index_channels.items():
                # TODO: Refactor this loop
                if name.lower().split("_", maxsplit=1)[1] != field.lower():
                    continue

                hashed_field, target_index = self._as_hashed(
                    table_metadata,
                    value,
                )
                index_channel: discord.TextChannel = self._find_channel(cid)
                entry_message: discord.Message = await self._lookup_message(
                    index_channel,
                    table_metadata,
                    target_index,
                )
                serialized_content = _IndexableRecord.from_message(
                    entry_message.content
                )

                if not serialized_content:
                    logger.info("Nothing was found.")
                    continue

                if serialized_content.key == hashed_field:
                    logger.debug(f"Key matches hash! {serialized_content}")
                    sets_list.append(set(serialized_content.record_ids))
                else:
                    # Hash collision!
                    def find_hash(message: str | None) -> bool:
                        if not message:
                            return False

                        index_record = _IndexableRecord.from_message(message)
                        if not index_record:
                            return False

                        return index_record.key == hashed_field

                    entry = await self._find_collision_message(
                        index_channel,
                        table_metadata,
                        target_index,
                        search_func=find_hash,
                    )

                    rec = _IndexableRecord.from_message(entry.content)
                    logger.debug(f"Found hash collision index entry: {rec}")
                    if not rec:
                        # This shouldn't be possible, considering the
                        # search function explicitly disallows that.
                        raise DatabaseCorruptionError(
                            "search function found null entry somehow"
                        )

                    sets_list.append(set(rec.record_ids))

        if not query:
            logger.info("Query is empty, finding all entries!")
            channel = self._find_channel(table_metadata.table_channel)
            async for msg in channel.history(limit=None):
                logger.debug(f"Found message in channel: {msg}")
                sets_list.append({msg.id})

        main_table = await self.guild.fetch_channel(
            table_metadata.table_channel
        )
        if not isinstance(main_table, discord.TextChannel):
            raise DatabaseCorruptionError(
                f"expected {main_table!r} to be a TextChannel"
            )

        logger.debug(f"Got IDs: {sets_list}")
        table = self.tables[table_name]
        records: list[Table] = []
        for record_ids in sets_list:
            for record_id in record_ids:
                message = await main_table.fetch_message(record_id)
                record = _Record.model_validate_json(message.content)
                entry = record.decode_content(table)
                entry.__disco_id__ = message.id
                records.append(entry)

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

    # This needs to be async for use in gather()
    async def _set_open(self) -> None:
        self.open = True

    async def clean(self) -> None:
        """
        Perform a full clean of the database.

        This method erases all metadata, all entries, and all tables. After
        calling this, a server loses any trace of the database ever being
        there.

        Note that this does *not* clean the existing tables from memory, but
        instead just marks them all as not ready.

        This action is irreversible.
        """
        logger.info("Cleaning the database!")

        if not self._metadata_channel:
            self._not_connected()

        coros: list[Coroutine] = []
        for table, metadata in self._database_metadata.items():
            logger.info(f"Cleaning table {table}")
            table_channel = self._find_channel(metadata.table_channel)
            coros.append(table_channel.delete())

            for cid in metadata.index_channels.values():
                channel = self._find_channel(cid)
                coros.append(channel.delete())

        for schema in self.tables.values():
            schema.__disco_ready__ = False

        logger.debug(f"Gathering deletion coros: {coros}")
        await asyncio.gather(*coros)
        logger.info("Deleting database metadata.")
        self._database_metadata = {}
        await self._metadata_channel.delete()

    async def login(self, bot_token: str) -> None:
        """
        Start running the bot.

        Args:
            bot_token: Discord API bot token to log in with.
        """
        if self.open:
            raise RuntimeError(
                "connection is already open, did you call login() twice?"
            )

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
            about losing the reference. By default, this task will
            never get `await`ed, so this function will not keep the
            event loop running. If you want to keep the event loop running,
            make sure to `await` the returned task object later.

        Example:
            ```py
            import asyncio
            import os

            import discobase


            async def main():
                db = discobase.Database("test")
                task = await db.login_task("...")
                await db.wait_ready()
                # ...
                await task  # Keep the event loop running

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
            # If something went wrong in startup, for example, then
            # we need to release the setup lock.
            self._setup_event.set()
            raise ValueError(
                "cannot close a connection that is not open",
            )
        self.open = False
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
            if self.open:  # Something could have gone wrong
                await self.close()

    def table(self, clas: T) -> T:
        """
        Mark a `Table` type as part of a database.
        This method is meant to be used as a decorator.

        Args:
            clas: Type object to attach.

        Example:
            ```py
            import discobase

            db = discobase.Database("My database")

            @db.table
            class MySchema(discobase.Table):
                foo: int
                bar: str

            # ...
            ```

        Returns:
            The same object passed to `clas` -- this is in order
            to allow use as a decorator.
        """
        if not issubclass(clas, Table):
            raise DatabaseTableError(
                f"{clas} is not a subclass of discobase.Table, did you forget it?",  # noqa
            )

        clas.__disco_name__ = clas.__name__.lower()
        if clas.__disco_name__ in self.tables:
            raise DatabaseTableError(f"table {clas.__name__} already exists")

        if clas.__disco_database__ is not None:
            raise DatabaseTableError(
                f"{clas!r} can only be attached to one database"
            )

        # Some implementation information.
        # __disco_database__ stores a reference to the database object, to
        # allow access to storage methods from table objects.
        #
        # Technically speaking, we're violating some rules related to
        # method privacy, as a table will access methods prefixed with _ from
        # outside the database class. It's not *that* big a deal, but it's
        # worth noting.
        clas.__disco_database__ = self

        # This is up for criticism -- instead of using Pydantic's
        # `model_fields` attribute, we invent our own `__disco_keys__` instead.
        #
        # Partially, this is due to the fact that we want `__disco_keys__` to
        # be, more or less, stable throughout the codebase.
        #
        # However, I don't think Pydantic would mess with `model_fields`, as
        # that's a public API, and hence why this could possibly be
        # considered as bad design.
        for field in clas.model_fields:
            clas.__disco_keys__.add(field)

        self.tables[clas.__disco_name__] = clas
        return clas
