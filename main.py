import asyncio
from brain import Brain

TOKEN = "8993624686:AAFKzow0S_fgdU6mHxBEU-JgeTp_ia1GIA0"

async def main():
    brain = Brain(TOKEN)
    await brain.start()

if __name__ == "__main__":
    asyncio.run(main())
