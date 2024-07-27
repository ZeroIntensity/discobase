from __future__ import annotations

from typing import (TYPE_CHECKING, Any, ClassVar, Literal, Optional, Set,
                    overload)

from pydantic import BaseModel
from typing_extensions import Self

if TYPE_CHECKING:
    from .database import Database

from .exceptions import (DatabaseLookupError, DatabaseStorageError,
                         DatabaseTableError, NotConnectedError)

__all__ = ("Table",)


# Note that we can't use 3.10+ type[] syntax
# here, since Pydantic can't handle it
class Table(BaseModel):
    __disco_database__: ClassVar[Optional[Database]] = None
    """Attached `Database` object. Set by the `table()` decorator."""
    __disco_keys__: ClassVar[Set[str]] = set()
    """All keys of the table, this may not change once set by `table()`."""
    __disco_name__: ClassVar[str] = "_notset"
    """Internal name of the table. Set by the `table()` decorator."""
    __disco_ready__: ClassVar[bool] = False
    """Whether the `Table` object has it's database channels set up."""
    __disco_id__: int = -1
    """Message ID of the record. This is only present if it was saved."""

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

        if not cls.__disco_ready__:
            raise DatabaseTableError(
                f"{cls.__name__} is not ready, you might want to add a call to build_tables()",  # noqa
            )

    async def save(self) -> None:
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
        assert self.__disco_database__
        if self.__disco_id__ != -1:
            raise DatabaseStorageError(
                "this entry has already been written, did you mean to call update()?",  # noqa
            )
        msg = await self.__disco_database__._add_record(self)
        self.__disco_id__ = msg.id

    async def update(self) -> None:
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
        assert self.__disco_database__
        if self.__disco_id__ == -1:
            raise DatabaseStorageError(
                "this entry has not been written, did you mean to call save()?",  # noqa
            )
        await self.__disco_database__._update_record(self)

    async def commit(self) -> None: ...

    @classmethod
    async def find(cls, **kwargs: Any) -> list[Self]:
        """
        Find a list of entries in the database.

        Args:
            **kwargs: Values to search for. These should be keys in the schema.

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
        assert cls.__disco_database__
        return await cls.__disco_database__._find_records(
            cls.__disco_name__,
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
