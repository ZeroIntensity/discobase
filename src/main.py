import asyncio
import os

import discobase


async def main():
    db = discobase.Database("test")
    async with db.conn(os.getenv("TEST_BOT_TOKEN")):
        print("Hello! I wasn't blocked by conn()")


asyncio.run(main())
