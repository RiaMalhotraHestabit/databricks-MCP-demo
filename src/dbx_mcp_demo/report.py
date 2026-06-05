from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

from databricks.sdk import WorkspaceClient

from databricks_mcp import DatabricksMCPClient

from .clients import make_mcp_client
from .endpoints import build_url


@dataclass(frozen=True)
class EndpointReport:
    name: str
    server_url: str
    tools: tuple[str, ...]
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def extract_tool_name(tool: Any) -> str:
    return getattr(tool, "name", str(tool))


def build_endpoint_reports(
    endpoint_map: dict[str, str],
    workspace_client: WorkspaceClient,
    host: str,
) -> list[EndpointReport]:
    reports: list[EndpointReport] = []
    for name, path_or_url in endpoint_map.items():
        server_url = build_url(host, path_or_url)
        try:
            client: DatabricksMCPClient = make_mcp_client(
                workspace_client=workspace_client,
                path_or_url=path_or_url,
                host=host,
            )
            tools = tuple(extract_tool_name(tool) for tool in client.list_tools())
            reports.append(EndpointReport(name=name, server_url=server_url, tools=tools))
        except Exception as exc:
            reports.append(
                EndpointReport(
                    name=name,
                    server_url=server_url,
                    tools=(),
                    error=str(exc),
                )
            )
    return reports


def endpoint_report_to_json(reports: list[EndpointReport]) -> str:
    return json.dumps([asdict(report) for report in reports], indent=2)


def format_endpoint_reports(reports: list[EndpointReport]) -> str:
    lines: list[str] = []
    for report in reports:
        lines.append(f"[{report.name}] {report.server_url}")
        if report.ok:
            lines.append("MCP connection successful.")
            lines.append("Available tools:")
            if report.tools:
                lines.extend(f"- {tool}" for tool in report.tools)
            else:
                lines.append("- (No tools reported)")
        else:
            lines.append(f"Connection failed: {report.error}")
        lines.append("")
    return "\n".join(lines).rstrip()
