from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.keyboards.worker import worker_idle_kb
from bot.services.live_timer import live_timer
from bot.services.mesta import cancel_open_sessions

router = Router(name="common")


@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot, db: AsyncSession, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    await live_timer.stop(uid)
    cleared = await cancel_open_sessions(db, uid)
    await state.clear()

    mpp = get_settings().minutes_per_position
    extra = ""
    if cleared:
        extra = (
            f"\n\n🔄 Eski ochiq inventarizatsiya bekor qilindi (<b>{cleared}</b> ta). "
            "Yangi ishni boshlashingiz mumkin."
        )

    await message.answer(
        "👋 <b>Hisobchi Bot</b>\n\n"
        f"Inventarizatsiya jarayoni — norma: <b>1 pozitsiya = {mpp:g} daqiqa</b>.\n\n"
        "<b>Jarayon:</b>\n"
        "▶️ Boshlash → onlayn sekundomer ishlaydi\n"
        "⏸ Pauza → vaqt to'xtaydi\n"
        "🏁 Yakunlash → nechta pozitsiya qilganingizni kiriting\n\n"
        "Har tejalgan 2 daqiqaga 1 ochko beriladi."
        f"{extra}\n\n"
        "Admin: /stat_today · /stat_week · /stat_month",
        reply_markup=worker_idle_kb(),
    )
