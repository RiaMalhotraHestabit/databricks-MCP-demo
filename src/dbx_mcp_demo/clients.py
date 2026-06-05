from __future__ import annotations

from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksMCPClient

from .config import Settings, load_settings
from .endpoints import build_url


def make_workspace_client(settings: Settings | None = None) -> WorkspaceClient:
    settings = settings or load_settings()
    return WorkspaceClient(host=settings.databricks_host, token=settings.databricks_token)


def make_mcp_client(
    workspace_client: WorkspaceClient,
    path_or_url: str,
    host: str | None = None,
) -> DatabricksMCPClient:
    if host is None:
        host = getattr(workspace_client.config, "host", None)
    if not host:
        raise ValueError("A Databricks host is required to build an MCP client")

    return DatabricksMCPClient(
        server_url=build_url(host, path_or_url),
        workspace_client=workspace_client,
    )
