from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from sqlalchemy import text

from bot.config import get_settings
from bot.database.bootstrap import run_migrations, setup_database, sync_admins_from_env
from bot.database.session import require_session_local
from bot.handlers import setup_routers
from bot.middlewares.access import TeamAccessMiddleware
from bot.middlewares.db import DbSessionMiddleware
from bot.services.hub_replay import list_unpushed_finishes, mark_hub_pushed
from bot.services.monitor import run_norm_monitor
from bot.yordamchi_push import hub_status_line, push_to_yordamchi_hub, today_iso

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    db_url = ""
    last_exc: Exception | None = None
    for attempt in range(1, 13):
        try:
            db_url, _ = await setup_database()
            run_migrations(db_url)
            await sync_admins_from_env()
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            log.warning("Database setup attempt %s/12 failed: %s", attempt, exc)
            await asyncio.sleep(10)
    if last_exc:
        log.error("Database setup failed: %s", last_exc)
        raise last_exc

    factory = require_session_local()
    async with factory() as session:
        await session.execute(text("SELECT 1"))
    log.info("Database connection OK")

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    log.info(
        "Mesta Nazorat Bot @%s | group=%s | norm=%s min/pos | admins=%s",
        me.username,
        settings.effective_group_chat_id() or "—",
        settings.minutes_per_position,
        sorted(settings.admin_id_set()),
    )
    log.info(
        "Notify policy v3: guruh=ish boshlash+yakun; pauza/eslatma=faqat lichka | Hub: %s | kaizen=hub summary",
        hub_status_line(),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(TeamAccessMiddleware())
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.include_router(setup_routers())

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Handler error: %s", event.exception)
        upd = event.update
        try:
            if upd.message:
                await upd.message.answer("⚠️ Ichki xato. Qayta urinib ko'ring.")
            elif upd.callback_query:
                await upd.callback_query.answer("Xato", show_alert=True)
        except Exception:
            pass
        return True

    try:
        day = today_iso()
        factory = require_session_local()
        async with factory() as session:
            pending = await list_unpushed_finishes(session, day)
            sent = 0
            for tg_id, summary, session_id in pending:
                ok, _via = await push_to_yordamchi_hub(
                    tg_id=tg_id,
                    bot_key="mesta",
                    summary=summary,
                    day_iso=day,
                )
                if ok:
                    await mark_hub_pushed(session, session_id)
                    sent += 1
            await session.commit()
        if pending:
            log.info("Mesta hub replay: %s/%s sessiya for %s", sent, len(pending), day)
    except Exception:
        log.exception("mesta hub replay xato")

    monitor_task = asyncio.create_task(run_norm_monitor(bot))
    try:
        await dp.start_polling(bot)
    finally:
        monitor_task.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
