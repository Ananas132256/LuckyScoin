import asyncio
import os
from core.brain import Brain

TOKEN = "8821292537:AAHixiDjq4SzpSgIx50QKQmyUPsOsVdW-i8"


async def main():
    if not TOKEN:
        raise RuntimeError("❌ Не задан BOT_TOKEN в переменных окружения")

    try:
        from version import VERSION
        print(f"🎰 LuckyScoin v{VERSION}")
    except Exception:
        print("🎰 LuckyScoin")

    brain = Brain(TOKEN)
    await brain.start()


if __name__ == "__main__":
    asyncio.run(main())