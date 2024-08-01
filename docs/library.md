---
hide:
    - navigation
---

# Core Library

## Introduction

Discobase turns a Discord bot into a database manager, through a server of `name`. The top-level class for Discobase is `Database`:

```py
import discobase

db = discobase.Database("My discord database")
```

Internally, this would create a server called "My discord database," and then use that for all storage. If this server already exists, it simply uses the existing server.

### Logging

By default, logging in Discobase is disabled. The `Database()` constructor has a `logging` parameter that you can pass to enable logging:

```py
import discobase

db = discobase.Database("My discord database", logging=True)
```

However, this only enables the Discobase logging, it does _not_ enable the logging for [discord.py](https://discordpy.readthedocs.io/en/latest/) (which is also disabled by default). If you would like to enable that, use their [setup_logging](https://discordpy.readthedocs.io/en/latest/api.html?highlight=setup_logging#discord.utils.setup_logging) function.

!!! note

    Note that Discobase *does not* use Python's built-in logging library. Instead, it uses [loguru](https://loguru.readthedocs.io/en/stable/).

## Logging in

It's worth noting that the `Database` constructor itself doesn't actually initialize the server. If we want to do anything useful, we need to log in &mdash; _that's_ when the server gets initialized.

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

`login()` has a bit of a pitfall: it blocks the function from proceeding (as in, the `await` never finishes, at least without some magic). In that case, you have two options: `login_task()` and `conn()`. Let's start with `login_task`, which runs the connection in the background as a free-flying task.

!!! note

    `login_task()` stores a reference to the task internally to prevent it from being accidentially deallocated while running, this is what we mean by "free-flying."

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

Notice the lack of an `await` before `db.login_task()` &mdash; that's intentional, and we'll talk about that more in a moment.

!!! warning

    A Discobase bot should generally *only* be used for a database, and not anything else. If you want to use Discobase in your own Discord bot, use two bot tokens: one for Discobase, and one for your bot.

### Waiting Until Ready

After calling `login_task()`, there isn't really a guarantee that the database is connected, which can cause some odd "it works on my machine" problems. To ensure that you're good to go, you should call `wait_ready()`:

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

Note that while the `asyncio.Task` object returned by `login_task()` is "free-flying," it does _not_ force the event loop to stay open indefinitely. To keep the connection alive, you must `await` the task:

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

`login_task()` and `wait_ready()` might suffice, depending on your application, but in many cases you might want to connect and disconnect, without running for the lifetime of the program.

For this use case, instead of just `login_task()` followed by `wait_ready()`, you want to use `conn()`, which is an [asynchronous context manager](https://docs.python.org/3/reference/datamodel.html#async-context-managers). This method calls `wait_ready()` for you, so you assume that the database is connected while in the `async with` block:

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

!!! note

    Throughout this documentation, we'll refer to a type that inherits from `discobase.Table` (and incidentially is also decorated with `table()`) as a "schema" or something similar.

However, we forgot something in the above example! `discobase.Table` only allows use of `User` as a schema, but the database still needs to know that it exists. We can do this via the `table()` decorator:

```py
import discobase

db = discobase.Database("My discord database")

@db.table
class User(discobase.Table):
    name: str
    password: str
```

!!! warning

    It is not allowed to have multiple tables of the same name (*i.e.*, the name of the class). For example, the following will **not** work:

    ```py

    import discobase

    db = discobase.Database("My discord database")

    @db.table
    class User(discobase.Table):
        name: str
        password: str


    @db.table
    class User(discobase.Table):
        some_other_field: str
    ```

Great, now `User` is visible to our `Database` object!

### Late Tables

At first glance, it may look like `@db.table()` will set everything up for you &mdash; this is not the case. In fact, `@db.table()` simply sets a few attributes, but the key is that it _marks_ the type as a schema. We can't do any actual initialization until the bot is logged in, so initialization happens _then_.

For example, the following would cause some errors if we try to use the table, since we use our table after the bot has already been initialized:

```py
import discobase
import asyncio

db = discobase.Database("My discord database")

async def main():
    async with db.conn("My bot token..."):
        # By default, this is not allowed!
        @db.table
        class User(discobase.Table):
            name: str
            password: str

        # ...

if __name__ == "__main__":
    asyncio.run(main())
```

OK, so what's the fix? The `table()` decorator still _marks_ the `User` type as part of the database in the above example, so all we need to do is tell the database to do it's table construction a second time &mdash; we can do this through the `build_tables()` method. Our fixed version of the example above would look like:

```py
import discobase
import asyncio

db = discobase.Database("My discord database")

async def main():
    async with db.conn("My bot token..."):
        @db.table
        class User(discobase.Table):
            name: str
            password: str

        await db.build_tables()  # Initialize `User` internally
        # Using `User` is now OK!

if __name__ == "__main__":
    asyncio.run(main())
```

!!! question "Why not call `build_tables()` automatically in `table()`?"

    Initializing is an *asynchronous* operation, and `table()` is not an asynchronous function.
    We'd have to do lots of weird event loop hacks to get it to work this way.

## Saving

Now, let's write to the database &mdash; we can do this via calling `save()` on an instance of our schema type:

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

Note that in the above, we used `await` with `save()`. This isn't actually required, since `save()` returns a `Task`, not a coroutine! In many cases, you don't need to save the record right then and there, and you can run it as a background task. This is especially important when it comes to Discobase &mdash; the ratelimit can make saving very slow, so it might be useful to save in the background and not block the current function. For example, if you were to use Discobase in a web application:

```py
@app.get("/signup")
def signup(username: str, password: str):
    User(name=username, password=password).save()  # This is launched as a background task!
    return "..."
```

If we were to `await` the result of `save()` above,

## Querying

We can look up an instance of it via `find()` (or `find_unique()`, if you want a unique database entry):

```py
async def main():
    async with db.conn("My bot token..."):
        users = await User.find(name="Peter")
        for user in users:
            print(f"Name: {user.name}, password: {user.password}")
```

Note that this works in a whitelist manner &mdash; as in, we search for values in the query, not get everything and exclude those that don't match it. However, calling `find()` with nothing is a special case that gets every entry in the table (note that this is a slow operation).

### Unique Entries

As mentioned above, you can also use `find_unique()` to get a unique entry:

```py
async def main():
    async with db.conn("My bot token..."):
        peter = await User.find_unique(name="Peter")
```

By default, `find_unique` is set to strict mode, which ensures the following:

-   The instance actually exists, and an exception is raised if the record wasn't found (_i.e._, `find_unique()` cannot return `None` when strict mode is enabled.)
-   Only one of the entry was found. If strict mode is disabled and multiple entries are found, the first entry is returned. Otherwise, an exception is thrown.

!!! info

    This is type safe through `@typing.overload()` &mdash; if you pass `strict=True`, the signature of `find_unique()` will not hint a return value that can be `None`.

## Updating

It's worth noting that `save()` can only be used on non-saved instances &mdash; as in, they haven't had `save()` called on them already. Instances created by their constructor manually (for example, calling `User(...)` above) are _not_ saved, while objects returned by something like `find` are considered to be saved, as they are already in the database.

So what about when you want to update an existing record? For that, you should call `update()`, which updates an existing record in-place. For example, if you wanted to change the record from the previous example:

```py
async def main():
    async with db.conn("My bot token..."):
        peter = await User.find_unique(name="Peter")
        peter.password = "barfoo"
        await peter.update()
```

Note that just like `save()`, `update()` returns a `Task`, meaning you can omit the `await` if you would like to perform the operation as a background task.

```py
peter = await User.find_unique(name="Peter")
peter.password = "barfoo"
peter.update()  # Run this in the background
```

### Deleting

You can also delete a saved record via the `delete()` method:

```py
async def main():
    async with db.conn("My bot token..."):
        peter = await User.find_unique(name="Peter")
        peter.delete()
```

Per `update()` and `save()`, this returns a `Task` that can be awaited or ran in the background.

### Committing

As you might have guessed, `update()` is the inverse of `save()`, in the sense that it only works for _saved_ objects. But what if you don't know if the object is saved or not? Technically speaking, you could check if the `__disco_id__` attribute is `-1` (e.g. `saved = peter.__disco_id__ != -1`), but that's not too convenient.

Instead, you can use `commit()`, which does this check for you. `commit()` works for _both_ saved and non-saved objects, and also can be used as a background task:

```py
peter = (await User.find_unique(name="Peter", strict=False)) or User(name="Peter", password="foobar")
peter.password = "barfoo"
peter.commit()  # Works with both cases!
```

## Admin Commands

Discobase comes with a set of admin commands to interact with your database right from Discord. First, you'll need to join the server, which is printed in the logs (see above on how to enable logging.)

Once you've joined, you're ready to try the admin commands! See the next section on what commands exist.
