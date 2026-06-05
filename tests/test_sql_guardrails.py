from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dbx_mcp_demo.config import Settings
from dbx_mcp_demo.sql_guardrails import prepare_sql_query


def make_settings() -> Settings:
    return Settings(
        databricks_host="https://dbc.example",
        databricks_token="token",
        mcp_endpoints=("api/2.0/mcp/sql",),
        safe_mode=True,
        allow_write_sql=False,
        require_write_confirmation=True,
        max_rows=50,
        allowed_catalogs=("main",),
        blocked_sql_keywords=("DROP", "DELETE", "UPDATE"),
        anthropic_api_key=None,
        anthropic_model=None,
        genie_space_id=None,
        ai_search_catalog=None,
        ai_search_schema=None,
        ai_search_index=None,
        external_mcp_connection=None,
    )


class SqlGuardrailTests(unittest.TestCase):
    def test_prepare_sql_query_adds_limit(self) -> None:
        sql = prepare_sql_query("select * from main.table_name", make_settings())
        self.assertTrue(sql.endswith("LIMIT 50"))

    def test_prepare_sql_query_blocks_write_sql(self) -> None:
        with self.assertRaises(ValueError):
            prepare_sql_query("drop table main.table_name", make_settings())

    def test_prepare_sql_query_allows_override(self) -> None:
        sql = prepare_sql_query("drop table main.table_name", make_settings(), allow_write_override=True)
        self.assertEqual(sql, "drop table main.table_name")


if __name__ == "__main__":
    unittest.main()
