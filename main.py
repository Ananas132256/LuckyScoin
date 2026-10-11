import asyncio
import os
from brain import Brain

TOKEN = os.getenv("BOT_TOKEN")

async def main():
    if not TOKEN:
        raise RuntimeError("❌ Не задан BOT_TOKEN в переменных окружения")
    brain = Brain(TOKEN)
    await brain.start()

if __name__ == "__main__":
    asyncio.run(main())