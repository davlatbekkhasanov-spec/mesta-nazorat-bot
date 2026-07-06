from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from bot.database.url import normalize_database_url, resolve_database_url
from bot.employee_registry import BUILTIN_ADMIN_IDS, DEFAULT_GROUP_ID, builtin_team_ids

_BUILTIN_ADMIN_IDS: frozenset[int] = BUILTIN_ADMIN_IDS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    database_url: str = ""
    group_chat_id: int = 0
    admin_ids: str = ""
    minutes_per_position: float = 3.0
    monitor_interval_minutes: int = 15
    tz: str = "Asia/Tashkent"

    @staticmethod
    def _parse_int(v: object) -> int:
        if v is None:
            return 0
        s = str(v).strip().strip('"').strip("'")
        if not s or s.lower() in ("0", "none", "null", "—", "-"):
            return 0
        try:
            return int(s)
        except ValueError:
            return 0

    @field_validator("group_chat_id", mode="before")
    @classmethod
    def _group_chat(cls, v: object) -> int:
        return cls._parse_int(v)

    @model_validator(mode="before")
    @classmethod
    def _fill_database_url(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        if not str(data.get("database_url") or "").strip():
            resolved = resolve_database_url()
            if resolved:
                data["database_url"] = resolved
        return data

    @field_validator("database_url", mode="before")
    @classmethod
    def _db_url(cls, v: object) -> str:
        s = str(v or "").strip()
        if s:
            return normalize_database_url(s)
        return resolve_database_url()

    @field_validator("minutes_per_position", mode="before")
    @classmethod
    def _mpp(cls, v: object) -> float:
        try:
            n = float(v or 3)
            return n if n > 0 else 3.0
        except (TypeError, ValueError):
            return 3.0

    yordamchi_hub_url: str = ""
    yordamchi_hub_secret: str = ""

    def admin_id_set(self) -> set[int]:
        out: set[int] = set(_BUILTIN_ADMIN_IDS)
        for part in self.admin_ids.replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit():
                out.add(int(part))
        return out

    def team_id_set(self) -> frozenset[int]:
        extra: set[int] = set()
        for part in self.admin_ids.replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit():
                extra.add(int(part))
        return builtin_team_ids() | frozenset(extra)

    def effective_group_chat_id(self) -> int:
        return self.group_chat_id or DEFAULT_GROUP_ID


@lru_cache
def get_settings() -> Settings:
    return Settings()
