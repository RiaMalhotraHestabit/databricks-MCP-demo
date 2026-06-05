from __future__ import annotations

from databricks.sdk import WorkspaceClient

from .report import EndpointReport, build_endpoint_reports, format_endpoint_reports, endpoint_report_to_json


def probe_mcp_tools(
    endpoint_map: dict[str, str],
    workspace_client: WorkspaceClient,
    host: str,
) -> list[EndpointReport]:
    return build_endpoint_reports(endpoint_map, workspace_client, host)


__all__ = [
    "EndpointReport",
    "build_endpoint_reports",
    "endpoint_report_to_json",
    "format_endpoint_reports",
    "probe_mcp_tools",
]
