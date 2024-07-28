from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from loguru import logger

__all__ = "gather_group", "GatherGroup", "free_fly"

T = TypeVar("T")


class GatherGroup:
    def __init__(self) -> None:
        self.tasks: list[asyncio.Task] = []

    def add(self, awaitable: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        task = asyncio.create_task(awaitable)
        self.tasks.append(task)
        return task


# A partial reimplementation of asyncio.TaskGroup, but
# that's only on 3.11+ anyway.
@asynccontextmanager
async def gather_group():
    group = GatherGroup()

    try:
        yield group
    finally:
        logger.debug(f"Gathering tasks: {group.tasks}")
        await asyncio.gather(*group.tasks)


_TASKS = set()


def free_fly(coro: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
    task = asyncio.create_task(coro)
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task
