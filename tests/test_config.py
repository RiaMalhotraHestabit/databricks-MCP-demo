from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dbx_mcp_demo.config import load_settings, parse_bool, parse_csv


class ConfigTests(unittest.TestCase):
    def test_parse_csv(self) -> None:
        self.assertEqual(parse_csv("a, b, ,c"), ("a", "b", "c"))

    def test_parse_bool(self) -> None:
        self.assertTrue(parse_bool("true"))
        self.assertFalse(parse_bool("off"))
        self.assertFalse(parse_bool(None, default=False))

    def test_load_settings(self) -> None:
        env = {
            "DATABRICKS_HOST": "dbc-example.cloud.databricks.com",
            "DATABRICKS_TOKEN": "dapi-test",
            "SAFE_MODE": "false",
            "ALLOW_WRITE_SQL": "true",
            "REQUIRE_WRITE_CONFIRMATION": "false",
            "MAX_ROWS": "25",
            "ALLOWED_CATALOGS": "main,samples",
            "BLOCKED_SQL_KEYWORDS": "DROP,DELETE",
        }
        with patch("dbx_mcp_demo.config.load_dotenv", lambda: None), patch.dict(
            os.environ, env, clear=True
        ):
            settings = load_settings()

        self.assertEqual(settings.databricks_host, "https://dbc-example.cloud.databricks.com")
        self.assertEqual(settings.databricks_token, "dapi-test")
        self.assertFalse(settings.safe_mode)
        self.assertTrue(settings.allow_write_sql)
        self.assertFalse(settings.require_write_confirmation)
        self.assertEqual(settings.max_rows, 25)
        self.assertEqual(settings.allowed_catalogs, ("main", "samples"))
        self.assertEqual(settings.blocked_sql_keywords, ("DROP", "DELETE"))


if __name__ == "__main__":
    unittest.main()
