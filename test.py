import asyncio
import os

import discobase


async def main():
    db = discobase.Database("discobase test")

    @db.table
    class User(discobase.Table):
        name: str
        password: str

    async with db.conn(os.environ["TEST_BOT_TOKEN"]):
        print("test")
        await User(name="peter", password="foobar").save()


asyncio.run(main())
