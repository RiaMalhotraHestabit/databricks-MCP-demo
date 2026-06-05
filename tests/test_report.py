from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dbx_mcp_demo.report import EndpointReport, build_endpoint_reports, endpoint_report_to_json


class DummyTool:
    def __init__(self, name: str) -> None:
        self.name = name


class DummyClient:
    def list_tools(self):
        return [DummyTool("execute_sql_read_only"), DummyTool("system__ai__python_exec")]


class DummyWorkspaceClient:
    pass


class ReportTests(unittest.TestCase):
    def test_build_endpoint_reports(self) -> None:
        with patch("dbx_mcp_demo.report.make_mcp_client", return_value=DummyClient()):
            reports = build_endpoint_reports(
                {"sql": "api/2.0/mcp/sql"},
                DummyWorkspaceClient(),
                "https://dbc.example",
            )

        self.assertEqual(reports[0].name, "sql")
        self.assertTrue(reports[0].ok)
        self.assertIn("execute_sql_read_only", reports[0].tools)

    def test_endpoint_report_to_json(self) -> None:
        payload = endpoint_report_to_json(
            [EndpointReport(name="sql", server_url="https://dbc.example", tools=("tool_a",))]
        )
        self.assertIsInstance(json.loads(payload), list)


if __name__ == "__main__":
    unittest.main()
