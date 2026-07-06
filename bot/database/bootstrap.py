from __future__ import annotations

import logging
import os

from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import create_async_engine

from bot.config import get_settings
from bot.database.base import Base
from bot.database.models import Admin
from bot.database.session import configure_database
from bot.database.url import (
    alembic_sync_url,
    async_connect_variants,
    database_url_candidates,
    db_host,
    sync_connect_variants,
    to_sync_env_url,
)

log = logging.getLogger(__name__)

_sync_url: str | None = None
_sync_connect_args: dict | None = None


def get_sync_url() -> str | None:
    return _sync_url


def get_sync_connect_args() -> dict | None:
    return _sync_connect_args


async def setup_database() -> tuple[str, dict]:
    global _sync_url, _sync_connect_args
    candidates = database_url_candidates()
    if not candidates:
        raise RuntimeError("DATABASE_URL topilmadi — Railway Postgres ulang")

    last_err: Exception | None = None
    for url in candidates:
        for connect_args in async_connect_variants(url):
            try:
                probe = create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)
                async with probe.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                await probe.dispose()
                configure_database(url, connect_args)
                os.environ["DATABASE_URL"] = to_sync_env_url(url)
                get_settings.cache_clear()
                log.info("Database OK host=%s", db_host(url))
                return url, connect_args
            except Exception as exc:
                last_err = exc
                log.warning("DB probe failed: %s", exc)

    raise RuntimeError(f"DB ulanmadi: {last_err}")


def run_migrations(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    global _sync_url, _sync_connect_args
    sync = alembic_sync_url(url)
    engine = None
    last_err: Exception | None = None
    for connect_args in sync_connect_variants(url):
        try:
            probe = create_engine(sync, connect_args=connect_args)
            with probe.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine = probe
            _sync_url = sync
            _sync_connect_args = connect_args
            break
        except Exception as exc:
            last_err = exc
            log.warning("Migration DB probe failed: %s", exc)

    if engine is None:
        raise RuntimeError(f"Migration DB ulanmadi: {last_err}")

    cfg = Config("alembic.ini")
    _apply_schema_patches(engine)
    try:
        with engine.connect() as conn:
            has_users = bool(conn.execute(text("SELECT to_regclass('public.users')")).scalar())
        if has_users:
            log.info("Mavjud DB — Alembic o'tkazib yuborildi (schema patches yetarli)")
        else:
            command.upgrade(cfg, "head")
            log.info("Alembic upgrade head OK")
    except Exception as exc:
        last_err = exc
        log.warning("Alembic migrate failed: %s", exc)
        try:
            Base.metadata.create_all(engine)
        except Exception as exc2:
            log.warning("create_all fallback failed: %s", exc2)

    engine.dispose()


def _apply_schema_patches(engine) -> None:
    """Alembic ishlamasa — 002 ustunlari va hub jadvali."""
    patches = [
        "ALTER TABLE work_sessions ADD COLUMN IF NOT EXISTS paused_at TIMESTAMPTZ",
        "ALTER TABLE work_sessions ADD COLUMN IF NOT EXISTS total_pause_sec INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE work_sessions ADD COLUMN IF NOT EXISTS hub_pushed_at TIMESTAMPTZ",
        "ALTER TABLE work_sessions ADD COLUMN IF NOT EXISTS work_type VARCHAR(32) NOT NULL DEFAULT 'inventarizatsiya'",
        """
        DO $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'work_sessions'
              AND column_name = 'status' AND character_maximum_length < 32
          ) THEN
            ALTER TABLE work_sessions ALTER COLUMN status TYPE VARCHAR(32);
          END IF;
        END $$
        """,
        """
        CREATE TABLE IF NOT EXISTS hub_day_push (
            day VARCHAR(10) NOT NULL,
            tg_id BIGINT NOT NULL,
            summary TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (day, tg_id)
        )
        """,
    ]
    with engine.begin() as conn:
        for sql in patches:
            conn.execute(text(sql.strip()))
    log.info("Schema patches applied")


async def sync_admins_from_env() -> None:
    from bot.database.session import require_session_local

    settings = get_settings()
    ids = settings.admin_id_set()
    if not ids:
        return
    factory = require_session_local()
    async with factory() as session:
        for tid in ids:
            exists = await session.scalar(select(Admin.id).where(Admin.telegram_id == tid))
            if not exists:
                session.add(Admin(telegram_id=tid))
        await session.commit()
