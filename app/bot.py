import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import load_config
from app.db import Database
from app.handlers.main import router
from app.services.schedule import refresh_schedule

LOG = logging.getLogger(__name__)

async def main():
    config = load_config()
    db = Database(config.database_path)
    await db.init()

    bot = Bot(config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp["db"] = db
    dp["config"] = config
    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    async def refresh_job():
        try:
            await refresh_schedule(db, config.schedule_url)
            LOG.info("Расписание обновлено")
        except Exception:
            LOG.exception("Фоновое обновление расписания не удалось")
    scheduler.add_job(refresh_job, "interval", minutes=config.schedule_refresh_minutes, id="schedule_refresh")
    scheduler.start()

    try:
        await refresh_job()
        await bot.delete_webhook(drop_pending_updates=True)
        LOG.info("VPT Bot запущен")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), db=db, config=config)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
