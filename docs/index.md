---
hide:
    - navigation
---

# Discobase

## What is Discobase?

**Python Discord Codejam 2024**

Discobase is a database library that works solely through Discord (_i.e._, nothing is stored locally!)

## Features

-   Pure Python, and pure Discord
-   Async-ready
-   Type safe

## Installation

```
$ pip install discobase
```

## Quickstart

```py
import discobase
import asyncio

db = discobase.Database("My discord database")

@db.table
class User(discobase.Table):
    name: str
    password: str

async def main():
    async with db.conn("my bot token"):
        ...

asyncio.run(main())
```

## Copyright

`discobase` is distributed under the MIT license.
