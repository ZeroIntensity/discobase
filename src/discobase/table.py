from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Optional, Set

from pydantic import BaseModel

if TYPE_CHECKING:
    from .database import Database

__all__ = ("Table",)


# Note that we can't use 3.10+ type[] syntax
# here, since Pydantic can't handle it
class Table(BaseModel):
    __disco_database__: ClassVar[Optional[Database]] = None
    __disco_keys__: ClassVar[Set[str]] = set()
    __disco_name__: ClassVar[str] = "_notset"

    def _ensure_db(self) -> None:
        if not self.__disco_database__:
            raise TypeError(
                f"{self.__class__.__name__} has no attached database, did you forget to call @db.table?"  # noqa
            )

        if not self.__disco_database__.open:
            raise ValueError(
                "database is not connected! did you forget to open it?"
            )

    async def save(self) -> None:
        """
        Commit the current object to the database.
        """
        self._ensure_db()
        assert self.__disco_database__
        await self.__disco_database__._add_record(self)
