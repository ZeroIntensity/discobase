import asyncio
import os

import discobase


async def main():
    db = discobase.Database("test")

    @db.table
    class MyTable(discobase.Table):
        test: str

    async with db.conn(os.environ["TEST_BOT_TOKEN"]):
        for table in db.tables:
            print(table.keys)


asyncio.run(main())
