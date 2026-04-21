import asyncio
from maintenance_backend import search_users
import traceback

async def main():
    try:
        res = await search_users("a")
        print("Success:", res)
    except Exception as e:
        print("Failed!")
        traceback.print_exc()

asyncio.run(main())
