from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.keyboards.worker import worker_idle_kb
from bot.services.live_timer import live_timer
from bot.services.mesta import cancel_open_sessions, get_open_session
from bot.handlers.mesta import _reply_open_session

router = Router(name="common")


@router.message(CommandStart())
@router.message(Command("start"))
async def cmd_start(message: Message, bot: Bot, db: AsyncSession, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    ws = await get_open_session(db, uid)

    if ws:
        return await _reply_open_session(message, ws, bot=bot, state=state)

    await live_timer.stop(uid)
    await state.clear()

    mpp = get_settings().minutes_per_position
    mpp_prihod = get_settings().minutes_per_position_prihod
    await message.answer(
        "👋 <b>Hisobchi Bot</b>\n\n"
        f"📦 <b>Inventarizatsiya</b> — norma: <b>1 poz = {mpp:g} daqiqa</b>\n"
        f"📥 <b>Prihod</b> — norma: <b>1 poz = {mpp_prihod:g} daqiqa</b>\n\n"
        "<b>Jarayon:</b>\n"
        "▶️ Inventarizatsiya yoki ▶️ Prihodni boshlash\n"
        "⏸ Pauza → vaqt to'xtaydi\n"
        "🏁 Yakunlash → nechta pozitsiya qilganingizni kiriting\n\n"
        "Har tejalgan norma vaqtiga 1 ochko beriladi.\n\n"
        "Admin: /stat_today · /stat_week · /stat_month",
        reply_markup=worker_idle_kb(),
    )


@router.message(Command("reset"))
async def cmd_reset(message: Message, bot: Bot, db: AsyncSession, state: FSMContext) -> None:
    uid = message.from_user.id if message.from_user else 0
    await live_timer.stop(uid)
    cleared = await cancel_open_sessions(db, uid)
    await state.clear()
    extra = f" ({cleared} ta bekor qilindi)" if cleared else ""
    await message.answer(
        f"🔄 Ochiq ishlar tozalandi{extra}. Endi «Inventarizatsiya» yoki «Prihodni boshlash» bosing.",
        reply_markup=worker_idle_kb(),
    )
