from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from bot.database.models import PositionLog, SessionStatus, User, WorkSession
from bot.utils.norm import NormStatus, evaluate_norm
from bot.utils.time_fmt import now_dt, session_pause_seconds, session_work_seconds


@dataclass
class SessionView:
    session: WorkSession
    user: User
    norm: NormStatus


def _norm_for(ws: WorkSession, *, actual: int | None = None, end=None) -> NormStatus:
    work_sec = session_work_seconds(ws, end)
    pause_sec = session_pause_seconds(ws, end)
    work_min = work_sec / 60.0
    pause_min = pause_sec / 60.0
    pos = actual if actual is not None else ws.total_positions
    return evaluate_norm(pos, work_min, pause_minutes=pause_min)


def _as_aware(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        from bot.utils.time_fmt import tz

        return dt.replace(tzinfo=tz())
    return dt


def _close_pause(ws: WorkSession) -> None:
    if ws.paused_at and ws.status == SessionStatus.paused:
        paused_at = _as_aware(ws.paused_at)
        delta = max(0, int((now_dt() - paused_at).total_seconds()))
        ws.total_pause_sec = int(ws.total_pause_sec or 0) + delta
        ws.paused_at = None


async def get_or_create_user(session: AsyncSession, telegram_id: int, full_name: str) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user:
        if full_name and user.full_name != full_name:
            user.full_name = full_name
        return user
    user = User(telegram_id=telegram_id, full_name=full_name or "Noma'lum")
    session.add(user)
    await session.flush()
    return user


async def cancel_open_sessions(session: AsyncSession, telegram_id: int) -> int:
    """Ochiq sessiyalarni bekor qilish (/start — eski ish tozalanadi)."""
    open_statuses = (
        SessionStatus.active,
        SessionStatus.paused,
        SessionStatus.awaiting_positions,
    )
    q = (
        select(WorkSession)
        .join(User)
        .where(User.telegram_id == telegram_id, WorkSession.status.in_(open_statuses))
        .options(joinedload(WorkSession.user))
    )
    rows = (await session.scalars(q)).all()
    if not rows:
        return 0
    now = now_dt()
    for ws in rows:
        _close_pause(ws)
        ws.status = SessionStatus.cancelled
        ws.finished_at = now
        ws.total_positions = 0
    await session.flush()
    return len(rows)


async def get_open_session(session: AsyncSession, telegram_id: int) -> WorkSession | None:
    open_statuses = (
        SessionStatus.active,
        SessionStatus.paused,
        SessionStatus.awaiting_positions,
    )
    q = (
        select(WorkSession)
        .join(User)
        .where(User.telegram_id == telegram_id, WorkSession.status.in_(open_statuses))
        .options(joinedload(WorkSession.user))
    )
    return await session.scalar(q)


async def start_session(session: AsyncSession, telegram_id: int, full_name: str) -> tuple[WorkSession | None, str]:
    existing = await get_open_session(session, telegram_id)
    if existing:
        return None, "Sizda ochiq inventarizatsiya bor. Avval yakunlang yoki davom eting."

    user = await get_or_create_user(session, telegram_id, full_name)
    ws = WorkSession(
        user_id=user.id,
        started_at=now_dt(),
        status=SessionStatus.active,
        total_positions=0,
        total_pause_sec=0,
    )
    session.add(ws)
    await session.flush()
    ws.user = user
    return ws, ""


async def pause_session(session: AsyncSession, telegram_id: int) -> tuple[SessionView | None, str]:
    ws = await get_open_session(session, telegram_id)
    if not ws:
        return None, "Ochiq inventarizatsiya yo'q."
    if ws.status == SessionStatus.awaiting_positions:
        return None, "Pozitsiya sonini kiriting."
    if ws.status == SessionStatus.paused:
        return None, "Allaqachon pauzada."

    ws.status = SessionStatus.paused
    ws.paused_at = now_dt()
    await session.flush()
    return SessionView(session=ws, user=ws.user, norm=_norm_for(ws)), ""


async def resume_session(session: AsyncSession, telegram_id: int) -> tuple[SessionView | None, str]:
    ws = await get_open_session(session, telegram_id)
    if not ws:
        return None, "Ochiq inventarizatsiya yo'q."
    if ws.status != SessionStatus.paused:
        return None, "Pauza yo'q."

    _close_pause(ws)
    ws.status = SessionStatus.active
    await session.flush()
    return SessionView(session=ws, user=ws.user, norm=_norm_for(ws)), ""


async def request_finish(session: AsyncSession, telegram_id: int) -> tuple[WorkSession | None, str]:
    ws = await get_open_session(session, telegram_id)
    if not ws:
        return None, "Ochiq inventarizatsiya yo'q."
    if ws.status == SessionStatus.awaiting_positions:
        return ws, ""

    _close_pause(ws)
    ws.finished_at = now_dt()
    ws.status = SessionStatus.awaiting_positions
    await session.flush()
    return ws, ""


async def complete_finish(
    session: AsyncSession, telegram_id: int, positions: int
) -> tuple[SessionView | None, str]:
    if positions <= 0:
        return None, "Pozitsiya soni 0 dan katta bo'lishi kerak."

    ws = await get_open_session(session, telegram_id)
    if not ws or ws.status != SessionStatus.awaiting_positions:
        return None, "Yakunlash jarayoni topilmadi. «Yakunlash» tugmasini bosing."

    ws.total_positions = positions
    ws.status = SessionStatus.finished
    if not ws.finished_at:
        ws.finished_at = now_dt()

    session.add(
        PositionLog(
            session_id=ws.id,
            count=positions,
            total_after=positions,
            logged_at=now_dt(),
        )
    )
    norm = _norm_for(ws, actual=positions, end=ws.finished_at)
    await session.flush()
    return SessionView(session=ws, user=ws.user, norm=norm), ""


async def list_active_sessions(session: AsyncSession) -> list[SessionView]:
    q = (
        select(WorkSession)
        .where(WorkSession.status.in_((SessionStatus.active, SessionStatus.paused)))
        .options(joinedload(WorkSession.user))
        .order_by(WorkSession.started_at.asc())
    )
    rows = (await session.scalars(q)).all()
    return [SessionView(session=ws, user=ws.user, norm=_norm_for(ws)) for ws in rows]


async def list_active_for_monitor(session: AsyncSession) -> list[SessionView]:
    q = (
        select(WorkSession)
        .where(WorkSession.status == SessionStatus.active)
        .options(joinedload(WorkSession.user))
        .order_by(WorkSession.started_at.asc())
    )
    rows = (await session.scalars(q)).all()
    out: list[SessionView] = []
    for ws in rows:
        work_min = session_work_seconds(ws) / 60.0
        if work_min < 15:
            continue
        out.append(SessionView(session=ws, user=ws.user, norm=_norm_for(ws)))
    return out


async def mark_alerted(session: AsyncSession, ws: WorkSession) -> None:
    ws.last_alert_at = now_dt()
    await session.flush()
