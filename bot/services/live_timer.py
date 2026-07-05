from __future__ import annotations

import asyncio
import html
import logging
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from bot.config import get_settings
from bot.database.models import SessionStatus, WorkSession
from bot.database.session import require_session_local
from bot.services.mesta import get_open_session
from bot.utils.time_fmt import session_pause_seconds, session_work_seconds
from bot.utils.visual import clock_box, fmt_stopwatch
from bot.work_types import WorkType, minutes_per_position, timer_header

log = logging.getLogger(__name__)

_SEP = "━━━━━━━━━━━━━━━━━"
_TICK_SEC = 1.0
_LOOP_DELAY_SEC = 0.5
_RUN_FRAMES = ("▶️", "🔸", "▶️", "🔹")


def _open_status(status) -> bool:
    s = str(status)
    return s in {SessionStatus.active, SessionStatus.paused, "active", "paused"}


def _paused(status) -> bool:
    return str(status) in {SessionStatus.paused, "paused"}


@dataclass
class _TimerEntry:
    chat_id: int
    message_id: int
    name: str
    tick: int = 0
    task: asyncio.Task | None = field(default=None, repr=False)


class LiveTimerService:
    def __init__(self) -> None:
        self._entries: dict[int, _TimerEntry] = {}

    def _safe_name(self, name: str) -> str:
        return html.escape((name or "Noma'lum").strip() or "Noma'lum")

    def render(
        self,
        name: str,
        *,
        work_sec: float,
        pause_sec: float,
        paused: bool,
        work_type: WorkType | str = WorkType.inventarizatsiya,
        tick: int = 0,
    ) -> str:
        mpp = minutes_per_position(work_type)
        clock = fmt_stopwatch(work_sec)
        safe = self._safe_name(name)

        if paused:
            header = timer_header(paused=True, work_type=work_type)
            sub = "Sekundomer to'xtatilgan"
        else:
            pulse = _RUN_FRAMES[tick % len(_RUN_FRAMES)]
            header = timer_header(paused=False, work_type=work_type, pulse=pulse)
            sub = "Ish vaqti hisoblanmoqda..."

        lines = [
            header,
            "",
            f"👤 <b>{safe}</b>",
            clock_box(clock),
            f"<i>{sub}</i>",
        ]
        if pause_sec >= 1:
            lines.append(f"⏸ Pauza: <b>{fmt_stopwatch(pause_sec)}</b>")
        lines.extend(
            [
                "",
                _SEP,
                f"📐 Norma: <b>1 poz = {mpp:g} daq</b>",
                "<i>Tayyor bo'lsa «Yakunlash» bosing</i>",
            ]
        )
        return "\n".join(lines)

    def render_ws(self, ws: WorkSession, name: str, *, tick: int = 0) -> str:
        return self.render(
            name,
            work_sec=session_work_seconds(ws),
            pause_sec=session_pause_seconds(ws),
            paused=_paused(ws.status),
            work_type=ws.work_type or WorkType.inventarizatsiya,
            tick=tick,
        )

    async def _edit(self, bot: Bot, entry: _TimerEntry, text: str) -> bool:
        for attempt in range(2):
            try:
                await bot.edit_message_text(
                    text,
                    chat_id=entry.chat_id,
                    message_id=entry.message_id,
                    parse_mode=ParseMode.HTML,
                )
                return True
            except TelegramBadRequest as exc:
                msg = str(exc).lower()
                if "message is not modified" in msg:
                    return True
                if attempt == 0:
                    await asyncio.sleep(0.4)
                    continue
                log.error("timer edit bad request chat=%s: %s", entry.chat_id, exc)
            except TelegramAPIError as exc:
                log.error("timer edit failed chat=%s: %s", entry.chat_id, exc)
            return False
        return False

    async def _loop(self, bot: Bot, tg_id: int) -> None:
        try:
            while True:
                entry = self._entries.get(tg_id)
                if not entry:
                    return

                factory = require_session_local()
                async with factory() as session:
                    ws = await get_open_session(session, tg_id)

                if not ws or not _open_status(ws.status):
                    self._entries.pop(tg_id, None)
                    return

                text = self.render_ws(ws, entry.name, tick=entry.tick)
                await self._edit(bot, entry, text)
                entry.tick += 1
                await asyncio.sleep(_TICK_SEC)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("live timer loop error tg_id=%s", tg_id)

    async def _deferred_loop(self, bot: Bot, tg_id: int) -> None:
        await asyncio.sleep(_LOOP_DELAY_SEC)
        if tg_id in self._entries:
            await self._loop(bot, tg_id)

    async def attach(
        self,
        bot: Bot,
        *,
        tg_id: int,
        chat_id: int,
        message_id: int,
        name: str,
    ) -> None:
        """Xabar allaqachon sekundomer matni bilan yuborilgan — faqat yangilash tsiklini boshlash."""
        await self.stop(tg_id)
        entry = _TimerEntry(chat_id=chat_id, message_id=message_id, name=name)
        self._entries[tg_id] = entry
        entry.task = asyncio.create_task(self._deferred_loop(bot, tg_id))

    async def refresh(self, bot: Bot, tg_id: int) -> None:
        entry = self._entries.get(tg_id)
        if not entry:
            return
        factory = require_session_local()
        async with factory() as session:
            ws = await get_open_session(session, tg_id)
        if not ws or not _open_status(ws.status):
            await self.stop(tg_id)
            return
        await self._edit(bot, entry, self.render_ws(ws, entry.name, tick=entry.tick))

    async def stop(self, tg_id: int, *, bot: Bot | None = None, final_text: str | None = None) -> None:
        entry = self._entries.pop(tg_id, None)
        if not entry:
            return
        if entry.task and not entry.task.done():
            entry.task.cancel()
            try:
                await entry.task
            except asyncio.CancelledError:
                pass
        if bot and final_text:
            await self._edit(bot, entry, final_text)

    async def stop_with_work_time(self, bot: Bot, tg_id: int, *, header: str) -> None:
        entry = self._entries.get(tg_id)
        if not entry:
            return
        factory = require_session_local()
        async with factory() as session:
            ws = await get_open_session(session, tg_id)
        work = fmt_stopwatch(session_work_seconds(ws)) if ws else "00:00"
        final = f"{header}\n\n{clock_box(work)}"
        await self.stop(tg_id, bot=bot, final_text=final)


live_timer = LiveTimerService()
