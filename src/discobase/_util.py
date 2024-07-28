from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Coroutine, TypeVar

import discord
from loguru import logger

__all__ = "gather_group", "GatherGroup", "free_fly"

T = TypeVar("T")


class GatherGroup:
    def __init__(self) -> None:
        self.tasks: list[asyncio.Task] = []

    def add(self, awaitable: Coroutine[Any, Any, T]) -> asyncio.Task[T]:
        async def inner_coro():
            while True:
                try:
                    return await awaitable
                except discord.HTTPException as e:
                    if e.code == 429:
                        logger.warning("Ratelimited! Retrying...")
                        await asyncio.sleep(0.1)

        task = asyncio.create_task(inner_coro())
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
