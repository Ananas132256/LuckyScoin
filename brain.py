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
from inventory import Inventory
from complaints import Complaints
from daily import Daily
from middleware import MaintenanceMiddleware, ActivityMiddleware
from notifier import notifier_loop, season_loop
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
        self.inventory = Inventory(self)
        self.complaints = Complaints(self)
        self.daily = Daily(self)

    async def start(self):
        mw = MaintenanceMiddleware(self, ADMIN_IDS)
        activity = ActivityMiddleware(self)
        self.dp.message.middleware(mw)
        self.dp.message.middleware(activity)
        self.dp.callback_query.middleware(mw)
        self.dp.callback_query.middleware(activity)

        self.menu.register(self.dp)
        self.game.register(self.dp)
        self.admin.register(self.dp)
        self.shop.register(self.dp)
        self.trade.register(self.dp)
        self.tycoon.register(self.dp)
        self.inventory.register(self.dp)
        self.complaints.register(self.dp)
        self.daily.register(self.dp)

        asyncio.create_task(notifier_loop(self))
        asyncio.create_task(season_loop(self))

        await self.dp.start_polling(self.bot)