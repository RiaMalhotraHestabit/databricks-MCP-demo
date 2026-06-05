from __future__ import annotations

from urllib.parse import urljoin

DEFAULT_MCP_ENDPOINTS: dict[str, str] = {
    "sql": "api/2.0/mcp/sql",
    "ai_functions": "api/2.0/mcp/functions/system/ai",
}


def normalize_host(host: str) -> str:
    host = host.strip()
    if not host:
        raise ValueError("DATABRICKS_HOST is empty")
    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"
    return host.rstrip("/")


def build_url(host: str, path_or_url: str) -> str:
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return urljoin(f"{host}/", path_or_url.lstrip("/"))


def parse_endpoint_map(raw_endpoints: str | None) -> dict[str, str]:
    endpoints = dict(DEFAULT_MCP_ENDPOINTS)
    text = (raw_endpoints or "").strip()
    if not text:
        return endpoints

    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            name, path = item.split("=", 1)
            endpoints[name.strip()] = path.strip()
        else:
            name = item.rstrip("/").split("/")[-1] or "custom"
            endpoints[name] = item

    return endpoints
