import discobase
import asyncio
import os


async def main():
    db = discobase.Database("discobase test")

    @db.table
    class User(discobase.Table):
        name: str
        password: str

    async with db.conn(os.environ["TEST_BOT_TOKEN"]):
        await User(name="Peter", password="foobar").save()


asyncio.run(main())
