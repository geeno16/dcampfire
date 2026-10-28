import asyncio

from src.common import drop_database

if __name__ == "__main__":
    asyncio.run(drop_database())
