---
hide:
    - navigation
---

# Discobase

## What is Discobase?

**Python Discord Codejam 2024**

Discobase is a database library that works solely through Discord (_i.e._, nothing is stored locally!)

## Features

-   Pure Python, and pure Discord.
-   Asynchronous.
-   Fully type safe.

## Installation

### Stable

Install the stable version of `discobase` using this commit:

```
$ pip install git+https://github.com/ZeroIntensity/discobase@e7604673d136d2eefcf727ef9326974a2ecc22ff
```

You can also install the latest version:

```
$ pip install discobase
```

!!! bug

    The stable version includes the admin commands for your database, but lacks <3.11 support, while the latest version is the opposite, as it has down to 3.8 support, but lacks admin commands. This is due to a last-minute oversight on our part, but there is nothing we can do at this point.

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
    async with db.conn("My bot token"):
        ...

asyncio.run(main())
```

## Copyright

`discobase` is distributed under the MIT license.
