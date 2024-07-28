from __future__ import annotations

import asyncio
from typing import (TYPE_CHECKING, Any, ClassVar, Literal, Optional, Set,
                    overload)

import discord
from pydantic import BaseModel, ConfigDict
from typing_extensions import Self, Unpack

from ._util import free_fly

if TYPE_CHECKING:
    from .database import Database

from ._cursor import TableCursor
from .exceptions import (DatabaseLookupError, DatabaseStorageError,
                         DatabaseTableError, NotConnectedError)

__all__ = ("Table",)


# Note that we can't use 3.10+ type[] syntax
# here, since Pydantic can't handle it
class Table(BaseModel):
    __disco_database__: ClassVar[Optional[Database]]
    """Attached `Database` object. Set by the `table()` decorator."""
    __disco_cursor__: ClassVar[Optional[TableCursor]]
    """Internal table cursor, set at initialization time."""
    __disco_keys__: ClassVar[Set[str]]
    """All keys of the table, this may not change once set by `table()`."""
    __disco_name__: ClassVar[str]
    """Internal name of the table. Set by the `table()` decorator."""
    __disco_id__: int = -1
    """Message ID of the record. This is only present if it was saved."""

    def __init__(self, /, **data: Any) -> None:
        super().__init__(**data)
        self.__disco_id__ = -1

    def __init_subclass__(cls, **kwargs: Unpack[ConfigDict]) -> None:
        super().__init_subclass__(**kwargs)
        cls.__disco_database__ = None
        cls.__disco_cursor__ = None
        cls.__disco_keys__ = set()
        cls.__disco_name__ = "_notset"

    @classmethod
    def _ensure_db(cls) -> None:
        if not cls.__disco_database__:
            raise DatabaseTableError(
                f"{cls.__name__} has no attached database, did you forget to call @db.table?"  # noqa
            )

        if not cls.__disco_database__.open:
            raise NotConnectedError(
                "database is not connected! did you forget to open it?"
            )

        if not cls.__disco_cursor__:
            raise DatabaseTableError(
                f"{cls.__name__} is not ready, you might want to add a call to build_tables()",  # noqa
            )

    def save(self) -> asyncio.Task[discord.Message]:
        """
        Save the entry to the database as a new record.

        Example:
            ```py
            import discobase

            db = discobase.Database("My database")

            @db.table
            class User(discobase.Table):
                name: str
                password: str

            # Using top-level await for this example
            await User(name="Peter", password="foobar").save()
            ```
        """
        self._ensure_db()
        assert self.__disco_cursor__

        if self.__disco_id__ != -1:
            raise DatabaseStorageError(
                "this entry has already been written, did you mean to call update()?",  # noqa
            )
        task = free_fly(self.__disco_cursor__.add_record(self))

        def _cb(fut: asyncio.Task[discord.Message]) -> None:
            msg = fut.result()
            self.__disco_id__ = msg.id

        task.add_done_callback(_cb)
        return task

    def _ensure_written(self) -> None:
        if self.__disco_id__ == -1:
            raise DatabaseStorageError(
                "this entry has not been written, did you mean to call save()?",  # noqa
            )

    def update(self) -> asyncio.Task[discord.Message]:
        """
        Update the entry in-place.

        Example:
            ```py
            import discobase

            db = discobase.Database("My database")

            @db.table
            class User(discobase.Table):
                name: str
                password: str

            # Using top-level await for this example
            user = await User.find_unique(name="Peter", password="foobar")
            user.password = str(hash(password))
            await user.update()
            ```
        """

        self._ensure_db()
        self._ensure_written()
        assert self.__disco_cursor__
        if self.__disco_id__ == -1:
            raise DatabaseStorageError(
                "this entry has not been written, did you mean to call save()?",  # noqa
            )
        return free_fly(self.__disco_cursor__.update_record(self))

    def commit(self) -> asyncio.Task[discord.Message]:
        """
        Save the current entry, or update it if it already exists in the
        database.
        """
        if self.__disco_id__ == -1:
            return self.save()
        else:
            return self.update()

    def delete(self) -> asyncio.Task[None]:
        """
        Delete the current entry from the database.
        """

        self._ensure_written()
        assert self.__disco_cursor__
        return free_fly(self.__disco_cursor__.delete_record(self))

    @classmethod
    async def find(cls, **kwargs: Any) -> list[Self]:
        """
        Find a list of entries in the database.

        Args:
            **kwargs: Values to search for. These should be keys in the schema.

        Returns:
            list[Table]: The list of objects that match the values in `kwargs`.

        Example:
            ```py
            import discobase
            db = discobase.Database("My database")
            @db.table
            class User(discobase.Table):
                name: str
                password: str
            # Using top-level await for this example
            await User.find(password="foobar").save()
            ```
        """
        cls._ensure_db()
        assert cls.__disco_cursor__
        return await cls.__disco_cursor__.find_records(
            cls,
            kwargs,
        )

    @classmethod
    @overload
    async def find_unique(
        cls,
        *,
        strict: Literal[True] = True,
        **kwargs: Any,
    ) -> Self: ...

    @classmethod
    @overload
    async def find_unique(
        cls,
        *,
        strict: Literal[False] = False,
        **kwargs: Any,
    ) -> Self | None: ...

    @classmethod
    async def find_unique(
        cls,
        *,
        strict: bool = True,
        **kwargs: Any,
    ) -> Self | None:
        """
        Find a unique entry in the database.

        Args:
            **kwargs: Values to search for. These should be keys in the schema.

        Returns:
            Table: Returns a single object that matches the values in`kwargs`.
            None: Nothing was found, and `strict` is `False`.
        """

        if not kwargs:
            raise ValueError("a query must be passed to find_unique")

        values: list[Self] = await cls.find(**kwargs)

        if not len(values):
            if strict:
                raise DatabaseLookupError(
                    f"no entry found with query {kwargs}",
                )

            return None

        if strict and (1 < len(values)):
            raise DatabaseLookupError(
                "more than one entry was found with find_unique"
            )

        return values[0]
