from __future__ import annotations

import html
from enum import StrEnum

from bot.config import get_settings


class WorkType(StrEnum):
    inventarizatsiya = "inventarizatsiya"
    prihod = "prihod"


def minutes_per_position(work_type: WorkType | str) -> float:
    settings = get_settings()
    if str(work_type) == WorkType.prihod:
        return settings.minutes_per_position_prihod
    return settings.minutes_per_position


def work_label(work_type: WorkType | str) -> str:
    if str(work_type) == WorkType.prihod:
        return "prihod"
    return "inventarizatsiya"


def work_label_title(work_type: WorkType | str) -> str:
    if str(work_type) == WorkType.prihod:
        return "Prihod"
    return "Inventarizatsiya"


def open_session_error(work_type: WorkType | str) -> str:
    if str(work_type) == WorkType.prihod:
        return "Sizda ochiq prihod ishi bor. Avval yakunlang yoki davom eting."
    return "Sizda ochiq inventarizatsiya bor. Avval yakunlang yoki davom eting."


def no_open_work_error() -> str:
    return "Ochiq ish yo'q. «Inventarizatsiya» yoki «Prihodni boshlash» tugmasini bosing."


def _he(name: str) -> str:
    return html.escape((name or "Noma'lum").strip() or "Noma'lum")


def group_started_message(*, name: str, work_type: WorkType | str) -> str:
    safe = _he(name)
    if str(work_type) == WorkType.prihod:
        return f"📥  <b>{safe}</b> prikhod qilishni boshladi"
    return f"🚛  <b>{safe}</b> inventarizatsiya ishlarini boshladi"


def group_finished_message(*, name: str, work_type: WorkType | str) -> str:
    safe = _he(name)
    if str(work_type) == WorkType.prihod:
        return f"🏁  <b>{safe}</b> prikhod qilishni yakunladi"
    return f"🏁  <b>{safe}</b> inventarizatsiya ishlarini yakunladi"


def timer_header(*, paused: bool, work_type: WorkType | str, pulse: str = "") -> str:
    if paused:
        return "⏸ <b>PAUZADA</b>"
    if str(work_type) == WorkType.prihod:
        return f"{pulse} <b>PRIKHOD — ONLAYN SEKUNDOMER</b> {pulse}".strip()
    return f"{pulse} <b>INVENTARIZATSIYA — ONLAYN SEKUNDOMER</b> {pulse}".strip()


def finish_title(work_type: WorkType | str) -> str:
    if str(work_type) == WorkType.prihod:
        return "📊 <b>PRIKHOD YAKUNLANDI</b>"
    return "📊 <b>INVENTARIZATSIYA YAKUNLANDI</b>"


def positions_question(work_type: WorkType | str) -> str:
    if str(work_type) == WorkType.prihod:
        return "Nechta pozitsiya prihod qildingiz?"
    return "Nechta pozitsiya qildingiz?"


def positions_unit(work_type: WorkType | str) -> str:
    if str(work_type) == WorkType.prihod:
        return "pozitsiya prihod"
    return "pozitsiya"
