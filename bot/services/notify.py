from __future__ import annotations

import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import get_settings
from bot.utils.norm import NormStatus, kaizen_points, norm_time_minutes, time_saved_minutes, time_waste_minutes
from bot.utils.time_fmt import fmt_datetime, fmt_hm, fmt_minutes
from bot.utils.visual import progress_bar
from bot.work_types import (
    WorkType,
    finish_title,
    group_finished_message,
    group_started_message,
    positions_unit,
)

log = logging.getLogger(__name__)

_SEP = "━━━━━━━━━━━━━━━━━"


def _he(name: str) -> str:
    return html.escape((name or "Noma'lum").strip() or "Noma'lum")


async def send_worker(bot: Bot, telegram_id: int, text: str) -> bool:
    """Shaxsiy chat — eslatmalar va xizmat xabarlari."""
    try:
        await bot.send_message(telegram_id, text)
        return True
    except TelegramAPIError as exc:
        log.warning("Xodimga yuborish xato (%s): %s", telegram_id, exc)
        return False


async def send_group(bot: Bot, text: str) -> bool:
    gid = get_settings().effective_group_chat_id()
    if not gid:
        log.warning("GROUP_CHAT_ID yo'q — guruhga yuborilmadi")
        return False
    try:
        await bot.send_message(gid, text)
        return True
    except TelegramAPIError as exc:
        log.error("Guruhga yuborish xato (%s): %s", gid, exc)
        return False


def start_message(*, name: str, started_at) -> str:
    return group_started_message(name=name, work_type=WorkType.inventarizatsiya)


def pause_message(*, name: str) -> str:
    return f"⏸ <b>Pauza</b>\n\n👤 <b>{name}</b>"


def resume_message(*, name: str) -> str:
    return f"▶️ <b>Davom etdi</b>\n\n👤 <b>{name}</b>"


def work_reminder_message(*, name: str, work_minutes: float) -> str:
    return (
        "⏰ <b>Eslatma</b>\n\n"
        f"👤 <b>{name}</b>\n"
        f"⏱ Ish vaqti: <b>{fmt_minutes(work_minutes)}</b>\n\n"
        "Tayyor bo'lgach «Yakunlash» tugmasini bosing va pozitsiya sonini kiriting."
    )


def _finish_banner(*, waste: float, saved: float, mpp: float, pts: int) -> tuple[str, str, str]:
    """banner, verdict, accent bar line."""
    if waste >= 0.5:
        pct = min(100.0, waste / max(waste + 0.01, 1) * 100)
        if waste >= mpp * 2:
            banner = "🚨 <b>DIQQAT! JIDDIY KECHIKISH</b> 🚨"
        else:
            banner = "⚠️ <b>NORMADAN SEKIN</b> ⚠️"
        verdict = f"❌ Ortiqcha vaqt: <b>{fmt_minutes(waste)}</b>"
        bar = progress_bar(pct, positive=False)
        return banner, verdict, bar

    if saved >= mpp:
        pct = min(100.0, saved / max(saved + 0.01, 1) * 100)
        if pts >= 3:
            banner = "🔥🔥 <b>AJOYIB! SUPER TEZ!</b> 🔥🔥"
        else:
            banner = "🔥 <b>AJOYIB! VAQT TEJALDINGIZ!</b> 🔥"
        verdict = f"⚡ Tejash: <b>{fmt_minutes(saved)}</b>"
        bar = progress_bar(pct, positive=True)
        return banner, verdict, bar

    if saved > 0.5:
        banner = "✨ <b>YAXSHI! NORMADA</b> ✨"
        verdict = f"⚡ Tejash: <b>{fmt_minutes(saved)}</b>"
        bar = progress_bar(min(100.0, saved / mpp * 100), positive=True)
        return banner, verdict, bar

    banner = "✅ <b>NORMADA YAKUNLANDI</b> ✅"
    return banner, "", progress_bar(100, positive=True)


def finish_message(
    *,
    name: str,
    started_at,
    finished_at,
    norm: NormStatus,
    minutes_per_position: float,
    work_type: WorkType | str = WorkType.inventarizatsiya,
) -> str:
    mpp = minutes_per_position if minutes_per_position > 0 else 3.0
    actual = norm.actual
    norm_time = norm_time_minutes(actual, mpp)
    saved = time_saved_minutes(actual, norm.work_minutes, mpp, pause_minutes=norm.pause_minutes)
    waste = time_waste_minutes(actual, norm.work_minutes, mpp, pause_minutes=norm.pause_minutes)
    pts = kaizen_points(saved, mpp)

    date_str = fmt_datetime(started_at).split(" ", 1)[0]
    work_str = fmt_minutes(norm.work_minutes)
    norm_str = fmt_minutes(norm_time)
    total_min = norm.total_minutes
    total_str = fmt_minutes(total_min)

    banner, verdict, bar = _finish_banner(waste=waste, saved=saved, mpp=mpp, pts=pts)

    kaizen_line = ""
    if pts > 0:
        stars = "⭐" * min(pts, 5)
        kaizen_line = f"🏆 Kaizen: <b>+{pts}</b> ball {stars}"

    pause_part = ""
    if norm.pause_minutes >= 0.5:
        pause_part = f"\n⏸ Pauza: <b>{fmt_minutes(norm.pause_minutes)}</b> <i>(normaga qo'shiladi)</i>"

    lines = [
        banner,
        "",
        finish_title(work_type),
        "",
        f"👤 <b>{name}</b>",
        f"🕐 {date_str}  ·  <b>{fmt_hm(started_at)}</b> → <b>{fmt_hm(finished_at)}</b>",
        "",
        _SEP,
        f"📦 <b>{actual}</b> {positions_unit(work_type)}{pause_part}",
    ]
    if verdict:
        lines.append(verdict)
    if kaizen_line:
        lines.append(kaizen_line)
    lines.extend(
        [
            bar,
            "",
            _SEP,
            f"🕐 Jami: <b>{total_str}</b>  ·  📐 Norma: <b>{norm_str}</b>",
            f"▶️ Ish: <b>{work_str}</b>",
        ]
    )

    return "\n".join(lines)
