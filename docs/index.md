---
hide:
    - navigation
---

<div>
    <img alt="discobase logo" src="https://raw.githubusercontent.com/ZeroIntensity/discobase/main/docs/assets/discobase_blurple.png" width=500>
</div>

## What is Discobase?

**Python Discord Codejam 2024**

This year, the theme was "information overload." We took that to heart, and made a database library that turns Discord into a database through various algorithms, and wrote a library to interact with it, either programatically or through a Discord interface, as well as another bot to show the library off. Truly, we're overloading a Discord server with _lots_ of information.

We used [discord.py](https://discordpy.readthedocs.io/) to interact with Discord and turn it into a data store, and used [Pydantic](https://docs.pydantic.dev/) for serializing database models.

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

## Contributions

Per the presentation requirements, here's what each team member contributed:

-   Everyone: Laid out the concepts for the core implementation and how it would work. You can see [this issue](https://github.com/ZeroIntensity/discobase/issues/4) for the discussion.
-   [Zero](https://github.com/zerointensity/) and [Rubiks](https://github.com/Rubiks14): Implemented the core library functionality.
-   [Skye](https://github.com/enskyeing) and [Gimpy](https://github.com/Gimpy3887): Built all the admin commands based on the core library.
-   [Rubiks](https://github.com/Rubiks14): Wrote the demo bot as shown in the [demonstration section](https://discobase.zintensity.dev/demonstration/).

## Copyright

`discobase` is distributed under the MIT license.
