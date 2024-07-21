from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Optional

from pydantic import BaseModel

if TYPE_CHECKING:
    from .database import Database

__all__ = ("Table",)


# Note that we can't use 3.10+ type[] syntax
# here, since Pydantic can't handle it
class Table(BaseModel):
    database: ClassVar[Optional[Database]] = None
    keys: ClassVar[set[str]] = set()

    def _ensure_db(self) -> None:
        if not self.database:
            raise TypeError(
                f"{self.__class__.__name__} has no attached database, did you forget to call @db.table?"  # noqa
            )

        if not self.database.open:
            raise ValueError(
                "database is not connected! did you forget to open it?"
            )

    async def save(self) -> None:
        """
        Commit the current object to the database.
        """
        self._ensure_db()
