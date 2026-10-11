from aiogram import Bot, Dispatcher
from db import DB
from menu import Menu
from game import Game
from admin import Admin


class Brain:
    def __init__(self, token):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.db = DB()
        self.menu = Menu(self)
        self.game = Game(self)
        self.admin = Admin(self)

    async def start(self):
        self.menu.register(self.dp)
        self.game.register(self.dp)
        self.admin.register(self.dp)
        await self.dp.start_polling(self.bot)