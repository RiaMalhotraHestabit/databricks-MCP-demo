from __future__ import annotations

import re
from dataclasses import dataclass

from .config import Settings

READ_ONLY_SQL_STARTERS = (
    "select",
    "show",
    "describe",
    "desc",
    "explain",
    "with",
)

WRITE_SQL_STARTERS = (
    "alter",
    "create",
    "delete",
    "drop",
    "insert",
    "merge",
    "truncate",
    "update",
)


def first_word(text: str) -> str:
    match = re.search(r"[A-Za-z]+", text.strip())
    return match.group(0).lower() if match else ""


def looks_like_read_only_sql(text: str) -> bool:
    return first_word(text) in READ_ONLY_SQL_STARTERS


def looks_like_write_sql(text: str) -> bool:
    return first_word(text) in WRITE_SQL_STARTERS


def _contains_whole_word(text: str, needle: str) -> bool:
    return re.search(rf"\b{re.escape(needle)}\b", text, flags=re.IGNORECASE) is not None


def _references_unallowed_catalog(text: str, allowed_catalogs: tuple[str, ...]) -> bool:
    if not allowed_catalogs:
        return False

    matches = re.findall(
        r"\b([A-Za-z_][\w]*)\.[A-Za-z_][\w]*\.[A-Za-z_][\w]*\b",
        text,
    )
    if not matches:
        return False

    allowed = {catalog.lower() for catalog in allowed_catalogs}
    return any(match.lower() not in allowed for match in matches)


def apply_default_limit(query: str, max_rows: int) -> str:
    stripped = query.strip()
    if max_rows <= 0:
        return stripped
    if first_word(stripped) not in {"select", "with"}:
        return stripped
    if re.search(r"\blimit\b", stripped, flags=re.IGNORECASE):
        return stripped
    return f"{stripped.rstrip(';')} LIMIT {max_rows}"


def validate_sql(
    query: str,
    settings: Settings,
    allow_write_override: bool = False,
) -> str:
    stripped = query.strip()
    if not stripped:
        raise ValueError("SQL query is empty")

    write_sql = looks_like_write_sql(stripped)
    write_allowed = settings.allow_write_sql or allow_write_override

    if settings.safe_mode and looks_like_write_sql(stripped):
        if not write_allowed:
            raise ValueError("Write SQL is disabled. Re-run with --allow-write if needed.")
        if settings.require_write_confirmation and not allow_write_override and not settings.allow_write_sql:
            raise ValueError("Write SQL requires explicit confirmation.")

    if not (write_sql and write_allowed):
        for keyword in settings.blocked_sql_keywords:
            if _contains_whole_word(stripped, keyword):
                if not looks_like_read_only_sql(stripped):
                    raise ValueError(f"SQL contains blocked keyword: {keyword}")

    if _references_unallowed_catalog(stripped, settings.allowed_catalogs):
        raise ValueError("SQL references a catalog outside ALLOWED_CATALOGS")

    return apply_default_limit(stripped, settings.max_rows)


def prepare_sql_query(
    query: str,
    settings: Settings,
    allow_write_override: bool = False,
) -> str:
    return validate_sql(query, settings, allow_write_override=allow_write_override)
