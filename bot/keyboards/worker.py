from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_START = "▶️ Boshlash"
BTN_START_INV = "▶️ Inventarizatsiya"
BTN_START_PRIHOD = "▶️ Prihodni boshlash"
BTN_PAUSE = "⏸ Pauza"
BTN_RESUME = "▶️ Davom etish"
BTN_FINISH = "🏁 Yakunlash"


def worker_idle_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_START_INV)],
            [KeyboardButton(text=BTN_START_PRIHOD)],
        ],
        resize_keyboard=True,
    )


def worker_active_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_PAUSE), KeyboardButton(text=BTN_FINISH)],
        ],
        resize_keyboard=True,
    )


def worker_paused_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_RESUME), KeyboardButton(text=BTN_FINISH)],
        ],
        resize_keyboard=True,
    )
