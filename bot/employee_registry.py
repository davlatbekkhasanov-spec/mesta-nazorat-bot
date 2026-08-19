"""Jamoa Telegram ID — barcha nazorat botlari bilan bir xil ro'yxat."""

from __future__ import annotations

import re

PULAT_TG_ID = 7987730795
CANONICAL_PULAT = "Rajabboev Pulat"
SHOXIJAXON_TG_ID = 6706402440
CANONICAL_SHOXIJAXON = "Ibodullaev Shoxijaxon"
DAVLATBEK_ADMIN_ID = 1432810519
DEFAULT_GROUP_ID = -1001877019294

TUVALOV_FARRUX_TG_ID = PULAT_TG_ID
CANONICAL_TUVALOV = CANONICAL_PULAT
OZODBEK_TG_ID = SHOXIJAXON_TG_ID
CANONICAL_OZODBEK = CANONICAL_SHOXIJAXON

BUILTIN_ADMIN_IDS: frozenset[int] = frozenset({DAVLATBEK_ADMIN_ID})

# Eski tg_id → (yangi tg_id, kanonik ism)
LEGACY_TG_ID_MAP: dict[int, tuple[int, str]] = {
    7703650930: (PULAT_TG_ID, CANONICAL_PULAT),
    7844168817: (SHOXIJAXON_TG_ID, CANONICAL_SHOXIJAXON),
    924612402: (SHOXIJAXON_TG_ID, CANONICAL_SHOXIJAXON),
}

TUVALOV_LEGACY_NAMES: frozenset[str] = frozenset(
    {
        "tuvalov farrux",
        "тувалов фаррух",
        "тувалов farrux",
        "фаррух",
        "farrux",
    }
)

PULAT_NAME_KEYS: frozenset[str] = frozenset(
    {
        "rajabboev pulat",
        "rahabboev pulat",
        "ражаббоев пулат",
        "рахаббоев пулат",
        "pulat",
    }
)

OZODBEK_LEGACY_NAMES: frozenset[str] = frozenset(
    {
        "ergashev ozodbek",
        "ozodbek",
        "эргашев",
        "yadullaev umid",
        "yadullaev umidjon",
        "ядуллаев умид",
        "ядуллаев умиджон",
        "umid",
        "umidjon",
    }
)

SHOXIJAXON_NAME_KEYS: frozenset[str] = frozenset(
    {
        "ibodullaev shoxijaxon",
        "ibodullaev shohijaxon",
        "шохижахон",
        "ибодуллаев шохижахон",
        "shoxijaxon",
        "shohijaxon",
    }
)

TG_EMPLOYEE: dict[int, str] = {
    SHOXIJAXON_TG_ID: CANONICAL_SHOXIJAXON,
    5412958249: "Ravshanov Oxunjon",
    8547365654: "Ruziboev Sindor",
    6931958983: "Mustafoev Abdullo",
    6991673998: "Sagdullaev Yunus",
    5465963344: "Shernazarov Tolib",
    6001619806: "Samadov Tulqin",
    5732350707: "Toxirov Muslimbek",
    8440127425: "Ravshanov Ziyodullo",
    PULAT_TG_ID: CANONICAL_PULAT,
}

EMPLOYEE_NAME_ALIASES: dict[str, int] = {
    CANONICAL_SHOXIJAXON: SHOXIJAXON_TG_ID,
    "Ibodullaev Shohijaxon": SHOXIJAXON_TG_ID,
    "Ergashev Ozodbek": SHOXIJAXON_TG_ID,
    "Ozodbek": SHOXIJAXON_TG_ID,
    "Yadullaev Umidjon": SHOXIJAXON_TG_ID,
    "Yadullaev Umid": SHOXIJAXON_TG_ID,
    CANONICAL_PULAT: PULAT_TG_ID,
    "Rahabboev Pulat": PULAT_TG_ID,
    "Tuvalov Farrux": PULAT_TG_ID,
    "Тувалов Фаррух": PULAT_TG_ID,
}


def _alias_key(raw: str) -> str:
    s = (raw or "").strip().lower()
    for ch in ("õ", "ö", "ó", "ô", "'", "'", "`", "ʻ", "ʼ", "’"):
        s = s.replace(ch, "o" if ch in ("õ", "ö", "ó", "ô") else "")
    return " ".join(s.split())


def is_pulat_name(name: str) -> bool:
    key = _alias_key(name)
    return key in PULAT_NAME_KEYS or name.strip() == CANONICAL_PULAT


def is_tuvalov_legacy(name: str) -> bool:
    return _alias_key(name) in TUVALOV_LEGACY_NAMES


def is_ozodbek_legacy(name: str) -> bool:
    return _alias_key(name) in OZODBEK_LEGACY_NAMES


def is_shoxijaxon_name(name: str) -> bool:
    key = _alias_key(name)
    return key in SHOXIJAXON_NAME_KEYS or name.strip() == CANONICAL_SHOXIJAXON


def canonical_employee_name(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return raw
    if is_tuvalov_legacy(raw) or is_pulat_name(raw):
        return CANONICAL_PULAT
    if is_ozodbek_legacy(raw) or is_shoxijaxon_name(raw):
        return CANONICAL_SHOXIJAXON
    tid = resolve_employee_tg_id(raw)
    if tid:
        return TG_EMPLOYEE.get(tid, raw)
    return raw


def builtin_team_ids() -> frozenset[int]:
    return frozenset(TG_EMPLOYEE.keys()) | BUILTIN_ADMIN_IDS


def is_team_member(telegram_id: int | None) -> bool:
    if not telegram_id:
        return False
    uid = int(telegram_id)
    if uid in builtin_team_ids():
        return True
    return uid in LEGACY_TG_ID_MAP


def operator_display_name(tg_id: int) -> str:
    return TG_EMPLOYEE.get(int(tg_id), f"ID {tg_id}")


def resolve_employee_tg_id(name: str) -> int | None:
    raw = (name or "").strip()
    if not raw:
        return None
    canon = canonical_employee_name(raw)
    if canon in EMPLOYEE_NAME_ALIASES:
        return int(EMPLOYEE_NAME_ALIASES[canon])
    key = _alias_key(raw)
    for alias, tid in EMPLOYEE_NAME_ALIASES.items():
        if _alias_key(alias) == key:
            return int(tid)
    for tid, emp in TG_EMPLOYEE.items():
        if _alias_key(emp) == _alias_key(canon):
            return int(tid)
    return None


def display_name_for_user(telegram_id: int, telegram_full_name: str = "") -> str:
    tid = int(telegram_id)
    if tid in TG_EMPLOYEE:
        return TG_EMPLOYEE[tid]
    if tid in LEGACY_TG_ID_MAP:
        return LEGACY_TG_ID_MAP[tid][1]
    return canonical_employee_name(telegram_full_name) or (telegram_full_name or "").strip() or str(tid)
