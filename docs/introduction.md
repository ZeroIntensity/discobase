# Introduction

## Server name

Discobase turns a Discord bot into a database manager, through a server of `name`. The top-level class for Discobase is `Database`:

```py
import discobase

db = discobase.Database("My discord database")
```

Internally, this would create a server called "My discord database," and then use that for all storage. If this server already exists, it simply uses the existing server.

## Logging in

It's worth noting that the `Database` constructor itself doesn't actually initialize the server. If we want to do anything useful, we need to log in -- _that's_ when the server gets initialized.

There are a few methods to log in, that depend on your use case, the simplest being `login()`:

```py
import discobase
import asyncio

db = discobase.Database("My discord database")

async def main():
    await db.login("My bot token...")

if __name__ == "__main__":
    asyncio.run(main())
```

`login` has a bit of a pitfall: it blocks the function from proceeding (as in, the `await` never finishes, at least without some magic). In that case, you have two options: `login_task` and `login_thread`. Generally speaking, you'll want to use `login_task`, as that runs the connection in the background as a free-flying task.

!!! note

    `login_task` stores a reference to the task internally to prevent it from being accidentially deallocated while running, this is what we mean by "free-flying."

For example:

```py
import discobase
import asyncio

db = discobase.Database("My discord database")

async def main():
    db.login_task("My bot token...")
    # Do something else, the bot is now running in the background

if __name__ == "__main__":
    asyncio.run(main())
```

However, after calling `login_task`, there isn't really a guarantee that the database is connected, which can cause some odd "it works on my machine" problems. To ensure that you're good to go, you should call `wait_ready`:

```py
import discobase
import asyncio

db = discobase.Database("My discord database")

async def main():
    db.login_task("My bot token...")
    await db.wait_ready()
    # We can now safely use the database!

if __name__ == "__main__":
    asyncio.run(main())
```

Note that while the `asyncio.Task` object returned by `login_task` is "free-flying," it does _not_ force the event loop to stay open indefinitely. To keep the connection alive, you must `await` the task:

```py
import discobase
import asyncio

db = discobase.Database("My discord database")

async def main():
    task = db.login_task("My bot token...")
    await db.wait_ready()
    # We can now safely use the database!
    # ...
    await task  # Keeps the connection open

if __name__ == "__main__":
    asyncio.run(main())
```

`login_task` and `wait_ready` might suffice, depending on your application, but in many cases you might want to connect and disconnect, without running for the lifetime of the program.

For this use case, instead of just `login_task` followed by `wait_ready`, you want to use `conn()`, which is an [asynchronous context manager](https://docs.python.org/3/reference/datamodel.html#async-context-managers). This method calls `wait_ready()` for you, so you assume that the database is connected while in the `async with` block:

```py
import discobase
import asyncio

db = discobase.Database("My discord database")

async def main():
    async with db.conn("My bot token..."):
        # Do something with the database

if __name__ == "__main__":
    asyncio.run(main())
```

## Tables

Now that your database is ready to go, let's make a table. Discobase uses [Pydantic](https://docs.pydantic.dev/latest/) to define schemas, through the `discobase.Table` type, which is, more or less, a drop in for `pydantic.BaseModel`:

```py
import discobase

db = discobase.Database("My discord database")

class User(discobase.Table):
    name: str
    password: str
```

However, we forgot something in the above example! `discobase.Table` only allows use of `User` as a schema, but the database still needs to know that it exists. We can do this via the `table` decorator:

```py
import discobase

db = discobase.Database("My discord database")

@db.table
class User(discobase.Table):
    name: str
    password: str
```

Great, now `User` is visible to our `Database` object! Now, let's write to the database -- we can do this via calling `save()` on an instance:

```py
import discobase
import asyncio

db = discobase.Database("My discord database")

@db.table
class User(discobase.Table):
    name: str
    password: str

async def main():
    async with db.conn("My bot token..."):
        user = User(name="Peter", password="foobar")
        await user.save()  # Saves this record to the database

if __name__ == "__main__":
    asyncio.run(main())
```

We can look up an instance of it via `find` (or `find_unique`, if you want a unique database entry):

```py
async def main():
    async with db.conn("My bot token..."):
        users = User.find(name="Peter")
        for user in users:
            print(f"Name: {user.name}, password: {user.password}")
```
