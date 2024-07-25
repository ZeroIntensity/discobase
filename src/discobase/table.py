from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Optional, Set

from pydantic import BaseModel
from typing_extensions import Self

if TYPE_CHECKING:
    from .database import Database

from .exceptions import DatabaseTableError

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

    @classmethod
    def _ensure_db(cls) -> None:
        if not cls.__disco_database__:
            raise DatabaseTableError(
                f"{cls.__name__} has no attached database, did you forget to call @db.table?"  # noqa
            )

        if not cls.__disco_database__.open:
            raise DatabaseTableError(
                "database is not connected! did you forget to open it?"
            )

        if not cls.__disco_ready__:
            raise DatabaseTableError(
                f"{cls.__name__} is not ready, you might want to add a call to build_tables()",  # noqa
            )

    async def save(self) -> None:
        """
        Commit the current object to the database.

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
        await self.__disco_database__._add_record(self)

    @classmethod
    async def find(cls, **kwargs: Any) -> list[Self]:
        cls._ensure_db()
        assert cls.__disco_database__
        return await cls.__disco_database__._find_records(
            cls.__disco_name__,
            kwargs,
        )
