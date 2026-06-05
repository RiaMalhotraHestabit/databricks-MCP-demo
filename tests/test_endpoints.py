from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dbx_mcp_demo.endpoints import build_url, normalize_host, parse_endpoint_map


class EndpointTests(unittest.TestCase):
    def test_normalize_host(self) -> None:
        self.assertEqual(normalize_host("dbc.example"), "https://dbc.example")

    def test_build_url(self) -> None:
        self.assertEqual(
            build_url("https://dbc.example", "api/2.0/mcp/sql"),
            "https://dbc.example/api/2.0/mcp/sql",
        )

    def test_parse_endpoint_map(self) -> None:
        parsed = parse_endpoint_map("sql=api/2.0/mcp/sql,custom=https://example.com/mcp")
        self.assertEqual(parsed["sql"], "api/2.0/mcp/sql")
        self.assertEqual(parsed["custom"], "https://example.com/mcp")


if __name__ == "__main__":
    unittest.main()
