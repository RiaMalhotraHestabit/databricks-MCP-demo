import os
from urllib.parse import urljoin

from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksMCPClient
from dotenv import load_dotenv


load_dotenv()

DEFAULT_MCP_ENDPOINTS = {
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


def parse_extra_endpoints() -> dict[str, str]:
    raw_endpoints = os.getenv("DATABRICKS_MCP_ENDPOINTS", "").strip()
    endpoints = dict(DEFAULT_MCP_ENDPOINTS)

    if not raw_endpoints:
        return endpoints

    for item in raw_endpoints.split(","):
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


def build_url(host: str, path_or_url: str) -> str:
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return urljoin(f"{host}/", path_or_url.lstrip("/"))


def check_mcp_endpoint(
    name: str,
    server_url: str,
    workspace_client: WorkspaceClient,
) -> None:
    print(f"\n[{name}] {server_url}")

    try:
        mcp_client = DatabricksMCPClient(
            server_url=server_url,
            workspace_client=workspace_client,
        )
        tools = mcp_client.list_tools()
    except Exception as exc:
        print(f"Connection failed: {exc}")
        return

    print("MCP connection successful.")
    print("Available tools:")
    for tool in tools:
        print(f"- {tool.name}")


def main() -> None:
    host = normalize_host(os.getenv("DATABRICKS_HOST", ""))
    token = os.getenv("DATABRICKS_TOKEN")

    workspace_client = WorkspaceClient(host=host, token=token)
    endpoints = parse_extra_endpoints()

    print(f"Checking {len(endpoints)} MCP endpoint(s).")
    for name, path_or_url in endpoints.items():
        check_mcp_endpoint(
            name=name,
            server_url=build_url(host, path_or_url),
            workspace_client=workspace_client,
        )


if __name__ == "__main__":
    main()
