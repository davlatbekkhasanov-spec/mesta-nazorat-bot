"""Hub ga yuborilmagan yakuniy sessiyalar — deploydan keyin qayta yuborish."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.database.models import SessionStatus, User, WorkSession
from bot.services.hub_summary import compact_hub_summary
from bot.services.mesta import _norm_for
from bot.utils.time_fmt import tz


def _day_bounds(day: str) -> tuple[datetime, datetime]:
    y, m, d = (int(x) for x in day.split("-"))
    start = datetime.combine(date(y, m, d), time.min, tzinfo=tz())
    return start, start + timedelta(days=1)


async def list_unpushed_finishes(session: AsyncSession, day: str) -> list[tuple[int, str, int]]:
    """(telegram_id, hub_summary, session_id) — kun bo'yicha, eskidan yangiga."""
    start, end = _day_bounds(day)
    q = (
        select(WorkSession)
        .join(User)
        .where(
            WorkSession.status == SessionStatus.finished,
            WorkSession.total_positions > 0,
            WorkSession.hub_pushed_at.is_(None),
            WorkSession.finished_at >= start,
            WorkSession.finished_at < end,
        )
        .options(joinedload(WorkSession.user))
        .order_by(WorkSession.finished_at.asc(), WorkSession.id.asc())
    )
    rows = (await session.scalars(q)).all()
    out: list[tuple[int, str, int]] = []
    for ws in rows:
        if not ws.user:
            continue
        norm = _norm_for(ws, actual=ws.total_positions, end=ws.finished_at)
        summary = compact_hub_summary(ws, norm)
        if summary:
            out.append((int(ws.user.telegram_id), summary, int(ws.id)))
    return out


async def mark_hub_pushed(session: AsyncSession, session_id: int) -> None:
    ws = await session.get(WorkSession, session_id)
    if not ws:
        return
    ws.hub_pushed_at = datetime.now(tz())
    await session.flush()
