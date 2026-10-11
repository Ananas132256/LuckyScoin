from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from db import DB
from menu import Menu
from game import Game
from admin import Admin
from shop import Shop
from trade import Trade
from tycoon import Tycoon
from badges import Badges


class Brain:
    def __init__(self, token):
        self.bot = Bot(token=token)
        self.dp = Dispatcher(storage=MemoryStorage())
        self.db = DB()
        self.menu = Menu(self)
        self.game = Game(self)
        self.admin = Admin(self)
        self.shop = Shop(self)
        self.trade = Trade(self)
        self.tycoon = Tycoon(self)
        self.badges = Badges(self)

    async def start(self):
        self.menu.register(self.dp)
        self.game.register(self.dp)
        self.admin.register(self.dp)
        self.shop.register(self.dp)
        self.trade.register(self.dp)
        self.tycoon.register(self.dp)
        self.badges.register(self.dp)
        await self.dp.start_polling(self.bot)