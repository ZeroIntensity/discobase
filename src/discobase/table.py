from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Optional, Set

from pydantic import BaseModel
from typing_extensions import Self

if TYPE_CHECKING:
    from .database import Database

__all__ = ("Table",)


# Note that we can't use 3.10+ type[] syntax
# here, since Pydantic can't handle it
class Table(BaseModel, frozen=True):
    __disco_database__: ClassVar[Optional[Database]] = None
    __disco_keys__: ClassVar[Set[str]] = set()
    __disco_name__: ClassVar[str] = "_notset"

    @classmethod
    def _ensure_db(cls) -> None:
        if not cls.__disco_database__:
            raise TypeError(
                f"{cls.__name__} has no attached database, did you forget to call @db.table?"  # noqa
            )

        if not cls.__disco_database__.open:
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

    @classmethod
    async def find(cls, **kwargs: Any) -> list[Self]:
        cls._ensure_db()
        assert cls.__disco_database__
        return await cls.__disco_database__._find_records(
            cls.__disco_name__,
            kwargs,
        )
