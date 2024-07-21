from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

__all__ = ("TableModel",)


class TableModel(BaseModel):
    pass


T = TypeVar("T", bound=TableModel)


class Table(Generic[T]):
    pass
