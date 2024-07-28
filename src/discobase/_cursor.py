from __future__ import annotations

import asyncio
import hashlib
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import Iterable
from datetime import timedelta
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, List, Optional

import discord
from aiocache import cached
from discord.utils import snowflake_time, time_snowflake
from loguru import logger
from pydantic import BaseModel, ValidationError

from ._metadata import Metadata
from .exceptions import (DatabaseCorruptionError, DatabaseLookupError,
                         DatabaseStorageError)

if TYPE_CHECKING:
    from .table import Table

__all__ = ("TableCursor",)


class _Record(BaseModel):
    content: str
    """Base64 encoded Pydantic model dump of the record."""

    @classmethod
    def from_data(cls, data: Table) -> _Record:
        logger.debug(f"Generating a _Record from data: {data}")
        return _Record(
            content=urlsafe_b64encode(  # Record JSON data is stored in base64
                data.model_dump_json().encode("utf-8"),
            ).decode("utf-8"),
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
            _IndexableRecord | None: An `_IndexableRecord` instance, or `None`,
                if the message was `null`.
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


class _HashTransport:
    """
    Hacky object to use `hash()` for tuples and dictionaries
    that retains the value between interpreters.
    """

    def __init__(self, hash_num: int) -> None:
        self.hash_num = hash_num

    def __hash__(self) -> int:
        return self.hash_num


class TableCursor:
    def __init__(
        self,
        metadata: Metadata,
        metadata_channel: discord.TextChannel,
        guild: discord.Guild,
    ) -> None:
        self.metadata = metadata
        self.metadata_channel = metadata_channel
        self.guild = guild

    @lru_cache
    def _find_channel(self, channel_id: int) -> discord.TextChannel:
        for channel in self.guild.channels:
            if channel.id != channel_id:
                continue

            if not isinstance(channel, discord.TextChannel):
                raise DatabaseCorruptionError(
                    f"{channel!r} is not a TextChannel"
                )

            return channel

        raise DatabaseCorruptionError(
            f"could not find channel with id {channel_id}"
        )

    async def _find_collision_message(
        self,
        channel: discord.TextChannel,
        index: int,
        *,
        search_func: Callable[[str], bool] = lambda s: s == "null",
    ) -> discord.Message:
        """
        Search for a message via a worst-case O(n) search in the event
        of a hash collision.

        Args:
            channel: Index channel to search.
            index: The index to start at.
            search_func: Function to check if the message content is good.

        Returns:
            discord.Message: The message that satisfies search_func
        """
        logger.debug(
            f"Looking up hash collision entry using search function: {search_func}"  # noqa
        )
        offset: int = index
        while True:
            if (offset + 1) >= self.metadata.max_records:
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
        editable_message = await channel.fetch_message(mid)
        logger.debug(f"Editing message (ID {mid}) to {content}")
        await editable_message.edit(content=content)

    def _to_index(self, value: int) -> int:
        """
        Generate an index from a hash number based
        on the metadata's `max_records`.

        Args:
            value: Integer hash, positive or negative.

        Returns:
            int: Index in range of `metadata.max_records`.
        """
        index = (value & 0x7FFFFFFF) % self.metadata.max_records
        logger.debug(
            f"Hashed value {value} turned into index: {index} ({self.metadata.max_records=})"  # noqa
        )
        return index

    @lru_cache()
    def _hash(
        self,
        value: Any,
    ) -> int:
        """
        Hash the field into an integer.

        Args:
            value: Any discobase-hashable object.

        Returns:
            int: An integer, positive or negative, representing a unique hash.
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
        elif isinstance(value, dict):
            transport: dict[_HashTransport, _HashTransport] = {}

            for k, v in value.items():
                transport[_HashTransport(self._hash(k))] = _HashTransport(
                    self._hash(v)
                )

            hashed_dict = hash(transport)
            logger.debug(f"Hashed dictionary {value!r} into {hashed_dict}")
            return hashed_dict
        elif isinstance(value, Iterable):
            hashes: list[_HashTransport] = []
            for item in value:
                hashes.append(_HashTransport(self._hash(item)))

            hashed_tuple = hash(tuple(hashes))
            logger.debug(f"Hashed iterable {value!r} into {hashed_tuple}")
            return hashed_tuple
        elif isinstance(value, int):
            return value
        else:
            raise DatabaseStorageError(f"unhashable: {value!r}")

    def _as_hashed(
        self,
        value: Any,
    ) -> tuple[int, int]:
        """
        Get the hash number and index for `value`.
        """
        hashed = self._hash(value)
        return hashed, self._to_index(hashed)

    @cached()
    async def _lookup_message_impl(
        self,
        channel: discord.TextChannel,
        index: int,
    ) -> discord.Message:
        """
        The *implementation* of looking up a message by
        it's index in the table. You need to call `fetch()`
        on the result of this function due to caching.

        Args:
            channel: Index channel to search.
            index: Index to get.

        Returns:
            discord.Message: The found message.

        Raises:
            DatabaseCorruptionError: Could not find the index.
        """
        metadata = self.metadata
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
                limit=end - start,
                before=snowflake_time(timestamp),
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

    async def _lookup_message(
        self,
        channel: discord.TextChannel,
        index: int,
    ) -> discord.Message:
        """
        Lookup a message by it's index in the table.

        Args:
            channel: Index channel to search.
            index: Index to get.

        Returns:
            discord.Message: The found message.

        Raises:
            DatabaseCorruptionError: Could not find the index.
        """
        # We need to refetch it for the latest content.
        return await (await self._lookup_message_impl(channel, index)).fetch()

    async def _resize_hash(
        self,
        index_channel: discord.TextChannel,
        amount: int,
    ) -> int:
        """
        Increases the hash for `index_channel` by amount

        Args:
            index_channel: the channel that contains index data for a database
            amount: the amount to increase the size by

        Returns:
            int: snowflake representation of when the last message of the
                resize was created
        """
        last_message: discord.Message | None = None

        # Here be dragons: ratelimit makes gathering this actually worse.
        for _ in range(amount):
            last_message = await index_channel.send("null", silent=True)

        if not last_message:
            raise DatabaseCorruptionError("last_message is None somehow")
        # 5 seconds, per the Discord ratelimit
        last_timestamp = timedelta(seconds=5) + last_message.created_at
        return time_snowflake(last_timestamp)

    async def _resize_channel(
        self,
        channel: discord.TextChannel,
    ) -> None:
        """
        The implementation of resizing a channel. This method assumes
        that `self.metadata.max_records` has already been doubled.

        This is meant for use in `gather()`, for optimal performance.

        Args:
            channel: Index channel to resize.
        """
        metadata = self.metadata
        logger.debug(
            f"Resizing channel: {channel!r} for table {metadata.name}",
        )
        old_size: int = metadata.max_records // 2
        timestamp_snowflake = await self._resize_hash(channel, old_size)
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

        metadata.time_table[timestamp_snowflake] = rng
        # Now, we have to move everything into the correct position.
        #
        # Note that this shouldn't put everything into memory, as
        # each previous iteration will be freed -- this is good
        # for scalability.
        #
        # Due to Discord's ratelimit, gathering the coros in this loop
        # is actually a bad idea.
        async for msg in channel.history(
            limit=old_size,
            oldest_first=True,
        ):
            # msg = await channel.fetch_message(msg.id)
            record = _IndexableRecord.from_message(msg.content)
            if not record:
                continue

            new_index: int = self._to_index(record.key)
            target = await self._lookup_message(
                channel,
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
                        # with `None` to prevent a doubly-nested copy in
                        # the JSON, we have to mark this message to *not*
                        # be overwritten, otherwise we lose that data.
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
                    "Target index does not have an entry, updating in-place."  # noqa
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
        # This algorithm is pretty much infinitely scalable
        # in terms of memory, but we're limited by Discord's ratelimit.
        async for msg in channel.history(
            limit=metadata.max_records,
            oldest_first=True,
        ):
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

    async def _resize_table(self) -> None:
        """
        Resize all the index channels in a table.
        """
        metadata = self.metadata
        metadata.max_records *= 2
        logger.info(
            f"Resizing table {metadata.name} to {metadata.max_records}"  # noqa
        )
        await asyncio.gather(
            *[
                self._resize_channel(self._find_channel(cid))
                for cid in metadata.index_channels.values()
            ]
        )

        # Dump the new metadata
        await self._edit_message(
            self.metadata_channel,
            metadata.message_id,
            metadata.model_dump_json(),
        )
        logger.info(
            f"Table {metadata.name} is now of size {metadata.max_records}"
        )

    async def _inc_records(self) -> None:
        """
        Increment the `current_records` number on the
        target metadata. This resizes the table if the maximum
        size is reached.
        """
        metadata = self.metadata
        metadata.current_records += 1
        if metadata.current_records > metadata.max_records:
            logger.info("The table is full! We need to resize it.")
            await self._resize_table()

        await self._edit_message(
            self.metadata_channel,
            metadata.message_id,
            metadata.model_dump_json(),
        )

    async def _write_index_record(
        self,
        channel: discord.TextChannel,
        index: int,
        hashed: int,
        record_id: int,
    ) -> None:
        """
        Write an index record to the specified channel, using
        a known hash and index.

        Args:
            channel: Target index channel to store the index record at.
            index: Index to store the record at in the table.
            hashed: Integer hash of the original value e.g. from `_hash`.
            record_id: Message ID of the record in the main table.
        """
        entry_message: discord.Message = await self._lookup_message(
            channel,
            index,
        )
        serialized_content = _IndexableRecord.from_message(
            entry_message.content
        )

        if not serialized_content:
            logger.info("This is a null entry, we can just update in place.")
            await self._inc_records()
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
            await self._inc_records()
            index_message = await self._find_collision_message(
                channel,
                index,
            )
            collision_entry = _IndexableRecord(
                key=hashed,
                record_ids=[
                    record_id,
                ],
            )
            await index_message.edit(content=collision_entry.model_dump_json())

    async def add_record(self, record: Table) -> discord.Message:
        """
        Writes a record to an existing table.

        Args:
            record: The record object being written to the table

        Returns:
            discord.Message: The `discord.Message` that contains the new entry.
        """

        metadata = self.metadata
        record_data = _Record.from_data(record)
        main_table: discord.TextChannel = self._find_channel(
            metadata.table_channel
        )
        message = await main_table.send(
            record_data.model_dump_json(), silent=True
        )

        for field, value in record.model_dump().items():
            channel = self._find_channel(
                metadata.index_channels[f"{record.__disco_name__}_{field}"]
            )
            hashed_field, target_index = self._as_hashed(value)
            await self._write_index_record(
                channel,
                target_index,
                hashed_field,
                message.id,
            )

        return await message.edit(content=record_data.model_dump_json())

    async def update_record(self, record: Table) -> discord.Message:
        """
        Updates an existing record in a table.

        Args:
            record: The record object being written to the table

        Returns:
            discord.Message: The `discord.Message` that contains the new entry.
        """
        if record.__disco_id__ == -1:
            # Sanity check
            raise DatabaseCorruptionError("record must have an id to update")

        metadata = self.metadata
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
                logger.info("Nothing changed.")
                continue

            channel = self._find_channel(
                metadata.index_channels[f"{record.__disco_name__}_{field}"]
            )
            hashed_field, target_index = self._as_hashed(new_value)
            await self._write_index_record(
                channel,
                target_index,
                hashed_field,
                msg.id,
            )

            old_index = self._to_index(self._hash(old_value))
            old_msg = await self._lookup_message(channel, old_index)
            old_record = _IndexableRecord.from_message(old_msg.content)
            if not old_record:
                raise DatabaseCorruptionError(
                    "got null record somehow",
                )

            if len(old_record.record_ids) == 1:
                logger.info("We can nullify this entry.")
                await old_msg.edit(content="null")
                self.metadata.current_records -= 1
            else:
                logger.info(
                    "There are other entries with this value, only remove this ID."  # noqa
                )
                old_record.record_ids.remove(msg.id)
                await old_msg.edit(content=old_record.model_dump_json())

        return msg

    async def find_records(
        self,
        table: type[Table],
        query: dict[str, Any],
    ) -> list[Table]:
        """
        Find a record based on the specified field values.

        Args:
            table: Table type to find records for.
            query: Dictionary containing field-value pairs.

        Returns:
            list[Table]: A list of `Table` objects (or really, a list of
                objects that inherit from `Table`), with the appropriate values
                specified by `query`.
        """
        metadata = self.metadata
        name = table.__disco_name__
        sets_list: list[set[int]] = []

        logger.debug(f"Looking for query {query!r} in {name}")
        for field, value in query.items():
            if field not in metadata.keys:
                raise DatabaseLookupError(
                    f"table {metadata.name} has no field {field}"
                )

            channel = self._find_channel(
                metadata.index_channels[f"{name}_{field}"]
            )

            hashed_field, target_index = self._as_hashed(value)
            entry_message = await self._lookup_message(
                channel,
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
                    channel,
                    target_index,
                    search_func=find_hash,
                )

                rec = _IndexableRecord.from_message(entry.content)
                logger.debug(f"Found hash collision index entry: {rec}")  # noqa
                if not rec:
                    # This shouldn't be possible, considering the
                    # search function explicitly disallows that.
                    raise DatabaseCorruptionError(
                        "search function found null entry somehow"
                    )

                sets_list.append(set(rec.record_ids))

        if not query:
            logger.info("Query is empty, finding all entries!")
            channel = self._find_channel(metadata.table_channel)
            async for msg in channel.history(limit=None):
                logger.debug(f"Found message in channel: {msg}")
                sets_list.append({msg.id})

        main_table = self._find_channel(metadata.table_channel)
        if not isinstance(main_table, discord.TextChannel):
            raise DatabaseCorruptionError(
                f"expected {main_table!r} to be a TextChannel"
            )

        logger.debug(f"Got IDs: {sets_list}")
        records: list[Table] = []

        for record_ids in sets_list:
            for record_id in record_ids:
                message = await main_table.fetch_message(record_id)
                record = _Record.model_validate_json(message.content)
                entry = record.decode_content(table)
                entry.__disco_id__ = message.id
                records.append(entry)

        return records

    async def _gen_key_channel(
        self,
        table: str,
        key_name: str,
        *,
        initial_size: int = 4,
    ) -> tuple[str, int, int]:
        """
        Generate a key channel from the given information.
        This does not check if it exists.

        Args:
            table: Processed channel name of the table.
            key_name: Name of the key, per `__disco_keys__`.
            initial_size: Equivalent to `initial_size` in `create_table`.

        Returns:
            tuple[int, int, int]: Tuple containing the channel name,
                the ID of the created channel, and the snowflake time of the
                last message created in the hash table.
        """
        # Key channels are stored in
        # the format of <table_name>_<field_name>
        index_channel = await self.guild.create_text_channel(
            f"{table}_{key_name}"
        )
        logger.debug(f"Generated key channel: {index_channel}")
        last_message_snowflake = await self._resize_hash(
            index_channel, initial_size
        )
        return index_channel.name, index_channel.id, last_message_snowflake

    @classmethod
    async def create_table(
        cls,
        table: type[Table],
        metadata_channel: discord.TextChannel,
        guild: discord.Guild,
        initial_size: int = 4,
    ) -> TableCursor:
        """
        Creates a new table and all index tables that go with it.
        This writes the table metadata.

        If the table already exists, this method does (almost) nothing.

        Args:
            table: Table schema to create channels for.
            initial_hash_size: the size the index hash tables should start at.

        Returns:
            TableCursor: An object used to manage a table
        """

        logger.debug(f"create_table called with table: {table!r}")
        name = table.__disco_name__
        existing_metadata: Metadata | None = None

        async for msg in metadata_channel.history(limit=None):
            try:
                parsed_meta = Metadata.model_validate_json(msg.content)
            except ValidationError as e:
                raise DatabaseCorruptionError("got invalid metadata") from e

            if parsed_meta.name == name:
                logger.debug(
                    f"Found existing metadata for table {name}: {parsed_meta}"
                )
                existing_metadata = parsed_meta
                break

        if existing_metadata and (
            set(existing_metadata.keys) != table.__disco_keys__
        ):
            logger.error(
                f"stored keys: {', '.join(existing_metadata.keys)} -- table keys: {', '.join(table.__disco_keys__)}"  # noqa
            )
            raise DatabaseCorruptionError(f"schema for table {name} changed")

        matching: list[str] = []
        for channel in guild.channels:
            for key in table.__disco_keys__:
                if channel.name == f"{name}_{key}":
                    matching.append(key)

        if existing_metadata and matching:
            if not len(matching) == len(table.__disco_keys__):
                raise DatabaseCorruptionError(
                    f"only some key channels exist: {', '.join(matching)}",
                )

            logger.info(f"Table is already set up: {table.__disco_name__}")
            cursor = TableCursor(existing_metadata, metadata_channel, guild)
            table.__disco_cursor__ = cursor
            return cursor

        logger.info(f"Building table: {table.__disco_name__}")

        # The primary table holds the actual records
        primary_table = await guild.create_text_channel(name)
        logger.debug(f"Generated primary table: {primary_table!r}")

        metadata = Metadata(
            name=name,
            keys=tuple(table.__disco_keys__),
            table_channel=primary_table.id,
            index_channels={},
            current_records=0,
            max_records=initial_size,
            time_table={},
            message_id=0,
        )
        self = TableCursor(metadata, metadata_channel, guild)
        timestamp_snowflake: int | None = None

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
            channel_name, channel_id, timestamp_snowflake = data
            index_channels[channel_name] = channel_id

        assert timestamp_snowflake is not None
        metadata.time_table = {timestamp_snowflake: (0, initial_size)}
        metadata.index_channels = index_channels
        message = await self.metadata_channel.send(
            metadata.model_dump_json(), silent=True
        )

        table.__disco_cursor__ = self
        # Since Discord generates the message ID, we have to do these
        # message editing shenanigans.
        metadata.message_id = message.id
        await message.edit(content=metadata.model_dump_json())
        logger.debug(f"Generated table metadata: {metadata!r}")
        return self

    async def delete_record(self, record: Table) -> None:
        """
        Deletes an existing record in a table.

        Args:
            record: The record object being deleted from the table.
        """
        if record.__disco_id__ == -1:
            # Sanity check
            raise DatabaseCorruptionError("record must have an id to update")

        metadata = self.metadata
        main_table: discord.TextChannel = self._find_channel(
            metadata.table_channel
        )
        msg = await main_table.fetch_message(record.__disco_id__)
        current = _Record.model_validate_json(msg.content).decode_content(
            record
        )

        for field, value in current.model_dump().items():
            channel = self._find_channel(
                metadata.index_channels[f"{current.__disco_name__}_{field}"]
            )

            index = self._to_index(self._hash(value))
            index_message = await self._lookup_message(channel, index)
            index_record = _IndexableRecord.from_message(index_message.content)

            if not index_record:
                raise DatabaseCorruptionError("got null record somehow")

            if len(index_record.record_ids) == 1:
                logger.info("We can nullify this entry.")
                await index_message.edit(content="null")
                self.metadata.current_records -= 1
            else:
                logger.info(
                    "There are other entries with this value, only remove this ID."  # noqa
                )
                index_record.record_ids.remove(msg.id)
                await index_message.edit(
                    content=index_record.model_dump_json(),
                )

        record.__disco_id__ = -1
        await msg.delete()
