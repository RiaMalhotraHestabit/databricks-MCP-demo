from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from .endpoints import normalize_host, parse_endpoint_map

DEFAULT_MCP_ENDPOINTS = (
    "api/2.0/mcp/sql",
    "api/2.0/mcp/functions/system/ai",
)
DEFAULT_BLOCKED_SQL_KEYWORDS = (
    "DROP",
    "DELETE",
    "TRUNCATE",
    "ALTER",
    "MERGE",
    "UPDATE",
    "INSERT",
    "CREATE",
    "REPLACE",
    "GRANT",
    "REVOKE",
)


@dataclass(frozen=True)
class Settings:
    databricks_host: str
    databricks_token: str
    mcp_endpoints: tuple[str, ...]
    safe_mode: bool
    allow_write_sql: bool
    require_write_confirmation: bool
    max_rows: int
    allowed_catalogs: tuple[str, ...]
    blocked_sql_keywords: tuple[str, ...]
    anthropic_api_key: str | None
    anthropic_model: str | None
    genie_space_id: str | None
    ai_search_catalog: str | None
    ai_search_schema: str | None
    ai_search_index: str | None
    external_mcp_connection: str | None


def parse_csv(value: str | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or not value.strip():
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def parse_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def parse_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid integer value: {value!r}") from exc


def load_settings() -> Settings:
    load_dotenv()

    host = normalize_host(os.getenv("DATABRICKS_HOST", ""))
    token = parse_optional(os.getenv("DATABRICKS_TOKEN"))
    if not token:
        raise ValueError("DATABRICKS_TOKEN is empty")

    raw_endpoints = os.getenv("DATABRICKS_MCP_ENDPOINTS", "").strip()
    if raw_endpoints:
        endpoint_map = parse_endpoint_map(raw_endpoints)
        mcp_endpoints = tuple(endpoint_map.values())
    else:
        mcp_endpoints = DEFAULT_MCP_ENDPOINTS

    return Settings(
        databricks_host=host,
        databricks_token=token,
        mcp_endpoints=mcp_endpoints,
        safe_mode=parse_bool(os.getenv("SAFE_MODE"), default=True),
        allow_write_sql=parse_bool(os.getenv("ALLOW_WRITE_SQL"), default=False),
        require_write_confirmation=parse_bool(
            os.getenv("REQUIRE_WRITE_CONFIRMATION"), default=True
        ),
        max_rows=parse_int(os.getenv("MAX_ROWS"), default=100),
        allowed_catalogs=parse_csv(os.getenv("ALLOWED_CATALOGS")),
        blocked_sql_keywords=parse_csv(os.getenv("BLOCKED_SQL_KEYWORDS"))
        or DEFAULT_BLOCKED_SQL_KEYWORDS,
        anthropic_api_key=parse_optional(os.getenv("ANTHROPIC_API_KEY")),
        anthropic_model=parse_optional(os.getenv("ANTHROPIC_MODEL")),
        genie_space_id=parse_optional(os.getenv("DATABRICKS_GENIE_SPACE_ID")),
        ai_search_catalog=parse_optional(os.getenv("DATABRICKS_AI_SEARCH_CATALOG")),
        ai_search_schema=parse_optional(os.getenv("DATABRICKS_AI_SEARCH_SCHEMA")),
        ai_search_index=parse_optional(os.getenv("DATABRICKS_AI_SEARCH_INDEX")),
        external_mcp_connection=parse_optional(
            os.getenv("DATABRICKS_EXTERNAL_MCP_CONNECTION")
        ),
    )
