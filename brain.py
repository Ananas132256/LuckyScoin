import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from db import DB
from menu import Menu
from game import Game
from admin import Admin
from shop import Shop
from trade import Trade
from tycoon import Tycoon
from middleware import MaintenanceMiddleware
from notifier import notifier_loop
from admin import ADMIN_IDS


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

    async def start(self):
        # Middleware техперерыва — на все апдейты
        mw = MaintenanceMiddleware(self, ADMIN_IDS)
        self.dp.message.middleware(mw)
        self.dp.callback_query.middleware(mw)

        # Регистрация хендлеров
        self.menu.register(self.dp)
        self.game.register(self.dp)
        self.admin.register(self.dp)
        self.shop.register(self.dp)
        self.trade.register(self.dp)
        self.tycoon.register(self.dp)
        self.friends.register(self.dp)

        # Фоновая задача для пушей о переполнении
        asyncio.create_task(notifier_loop(self))

        await self.dp.start_polling(self.bot)