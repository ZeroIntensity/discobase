import asyncio
import os

import discobase

db = discobase.Database("test")


async def main():
    db.login_task(os.getenv("TEST_BOT_TOKEN"))


asyncio.run(main())
