<div align="center">
    <img alt="discobase logo" src="https://raw.githubusercontent.com/ZeroIntensity/discobase/main/docs/assets/discobase_blurple.png" width=500>
    <br><br>
    <div align="center"><strong>Python Discord Codejam 2024 Submission: Spunky Sputniks</strong></div>
</div>
<br>

## Installation

### Library

```bash
$ pip install discobase
```

### Demo Bot

You can add the demo bot to a server with [this integration](https://discord.com/oauth2/authorize?client_id=1268247436699238542&permissions=8&integration_type=0&scope=bot), or self-host it using the following commands:

```bash
$ git clone https://github.com/zerointensity/discobase
$ cd discobase/src/demo
$ export DB_BOT_TOKEN="first bot token"
$ export BOOKMARK_BOT_TOKEN="second bot token"
$ python3 main.py
```

## Quickstart

```py
import asyncio
import discobase

db = discobase.Database("My database")

@db.table
class User(discobase.Table):
    name: str
    password: str

async def main():
    async with db.conn("My bot token"):
        admin = await User.find(name="admin")
        if not admin:
            User.save(name="admin", password="admin")

if __name__ == "__main__":
    asyncio.run(main())
```

## Documentation

Documentation is available [here](https://discobase.zintensity.dev).

## License

`discobase` is distributed under the `MIT` license.
