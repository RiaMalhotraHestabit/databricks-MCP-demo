import argparse
import json
import os
import re
import sys
from urllib.parse import urljoin

from databricks.sdk import WorkspaceClient
from databricks_mcp import DatabricksMCPClient
from dotenv import load_dotenv


load_dotenv()

READ_ONLY_SQL_STARTERS = (
    "select",
    "show",
    "describe",
    "desc",
    "explain",
    "with",
)

WRITE_SQL_STARTERS = (
    "alter",
    "create",
    "delete",
    "drop",
    "insert",
    "merge",
    "truncate",
    "update",
)


def normalize_host(host: str) -> str:
    host = host.strip()
    if not host:
        raise ValueError("DATABRICKS_HOST is empty")
    if not host.startswith(("http://", "https://")):
        host = f"https://{host}"
    return host.rstrip("/")


def make_workspace_client() -> WorkspaceClient:
    host = normalize_host(os.getenv("DATABRICKS_HOST", ""))
    token = os.getenv("DATABRICKS_TOKEN")
    return WorkspaceClient(host=host, token=token)


def make_mcp_client(workspace_client: WorkspaceClient, path: str) -> DatabricksMCPClient:
    host = normalize_host(os.getenv("DATABRICKS_HOST", ""))
    return DatabricksMCPClient(
        server_url=urljoin(f"{host}/", path),
        workspace_client=workspace_client,
    )


def extract_text(result) -> str:
    parts = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(item))

    if parts:
        return "\n".join(parts)
    return str(result)


def pretty_print_result(result) -> None:
    text = extract_text(result).strip()
    if not text:
        print("(No output)")
        return

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        print(text)
        return

    if print_python_result(parsed):
        return
    if print_sql_result(parsed):
        return

    print(json.dumps(parsed, indent=2))


def scalar_value(value: dict) -> str:
    if not isinstance(value, dict):
        return str(value)
    if "string_value" in value:
        return value["string_value"]
    if "long_value" in value:
        return str(value["long_value"])
    if "double_value" in value:
        return str(value["double_value"])
    if "boolean_value" in value:
        return str(value["boolean_value"])
    if "null_value" in value:
        return "NULL"
    return json.dumps(value)


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not headers:
        print("(No columns)")
        return

    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))

    header_line = " | ".join(
        header.ljust(widths[index]) for index, header in enumerate(headers)
    )
    separator = "-+-".join("-" * width for width in widths)
    print(header_line)
    print(separator)
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def print_python_result(parsed: object) -> bool:
    if not isinstance(parsed, dict):
        return False
    if parsed.get("columns") != ["output"] or "rows" not in parsed:
        return False

    rows = parsed.get("rows") or []
    output = "".join(row[0] for row in rows if row)
    print(output.rstrip() or "(No output)")
    return True


def print_sql_result(parsed: object) -> bool:
    if not isinstance(parsed, dict):
        return False
    manifest = parsed.get("manifest") or {}
    result = parsed.get("result") or {}
    schema = manifest.get("schema") or {}
    columns = schema.get("columns") or []
    data = result.get("data_array")

    if data is None or not columns:
        return False

    headers = [column.get("name", f"column_{index}") for index, column in enumerate(columns)]
    rows = []
    for item in data:
        values = item.get("values", [])
        rows.append([scalar_value(value) for value in values])

    print_table(headers, rows)
    row_count = manifest.get("total_row_count", len(rows))
    print(f"\n{row_count} row(s)")
    return True


def first_word(text: str) -> str:
    match = re.search(r"[A-Za-z]+", text.strip())
    return match.group(0).lower() if match else ""


def looks_like_read_only_sql(text: str) -> bool:
    return first_word(text) in READ_ONLY_SQL_STARTERS


def looks_like_write_sql(text: str) -> bool:
    return first_word(text) in WRITE_SQL_STARTERS


def run_sql(sql_client: DatabricksMCPClient, query: str, allow_write: bool = False) -> None:
    tool_name = "execute_sql"
    if not allow_write:
        tool_name = "execute_sql_read_only"

    print(f"\nRunning {tool_name}...")
    result = sql_client.call_tool(tool_name, {"query": query})
    pretty_print_result(result)


def run_python(ai_client: DatabricksMCPClient, code: str) -> None:
    print("\nRunning system__ai__python_exec...")
    result = ai_client.call_tool("system__ai__python_exec", {"code": code})
    pretty_print_result(result)


def print_help() -> None:
    print(
        """
Commands:
  SQL directly:
    show catalogs
    show schemas in main
    select current_catalog(), current_schema()

  SQL with prefix:
    sql show catalogs
    sql show schemas in hr_compliance

  Python:
    py print(2 + 2)
    python import math; print(math.sqrt(16))

  Write SQL, only when you intentionally pass --allow-write:
    create table catalog.schema.table_name (...)

  Other:
    help
    quit
""".strip()
    )


def handle_query(
    query: str,
    sql_client: DatabricksMCPClient,
    ai_client: DatabricksMCPClient,
    allow_write: bool,
) -> None:
    stripped = query.strip()
    lowered = stripped.lower()

    if not stripped:
        return
    if lowered in {"help", "?"}:
        print_help()
        return
    if lowered in {"quit", "exit"}:
        raise KeyboardInterrupt

    if lowered.startswith("sql "):
        sql = stripped.split(" ", 1)[1].strip().strip('"')
        if looks_like_write_sql(sql):
            if not allow_write:
                print(
                    "That looks like write SQL. Re-run with --allow-write if you really want to execute it."
                )
                return
            run_sql(sql_client, sql, allow_write=True)
            return
        run_sql(sql_client, sql, allow_write=False)
        return

    if lowered.startswith(("py ", "python ")):
        code = stripped.split(" ", 1)[1]
        run_python(ai_client, code)
        return

    if looks_like_read_only_sql(stripped):
        run_sql(sql_client, stripped, allow_write=False)
        return

    if looks_like_write_sql(stripped):
        if not allow_write:
            print(
                "That looks like write SQL. Re-run with --allow-write if you really want to execute it."
            )
            return
        run_sql(sql_client, stripped, allow_write=True)
        return

    print(
        "I can run SQL or Python through your current MCP endpoints. "
        "Type a SQL statement, or prefix Python with 'py '. Type 'help' for examples."
    )


def interactive_loop(
    sql_client: DatabricksMCPClient,
    ai_client: DatabricksMCPClient,
    allow_write: bool,
) -> None:
    print("Databricks MCP assistant")
    print("Type SQL, or prefix Python with 'py '. Type 'help' for examples, 'quit' to exit.")

    while True:
        try:
            query = input("\ndatabricks> ")
            handle_query(query, sql_client, ai_client, allow_write)
        except KeyboardInterrupt:
            print("\nBye.")
            return
        except Exception as exc:
            print(f"Error: {exc}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Small terminal assistant for Databricks MCP SQL and Python tools."
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="SQL to run, or Python when used with --python.",
    )
    parser.add_argument(
        "--python",
        action="store_true",
        help="Treat the query argument as Python code.",
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Allow write SQL through execute_sql. Defaults to read-only SQL.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    workspace_client = make_workspace_client()
    sql_client = make_mcp_client(workspace_client, "api/2.0/mcp/sql")
    ai_client = make_mcp_client(workspace_client, "api/2.0/mcp/functions/system/ai")

    query = " ".join(args.query).strip()
    if args.python:
        if not query:
            print("Pass Python code after --python.")
            return 2
        run_python(ai_client, query)
        return 0

    if query:
        handle_query(query, sql_client, ai_client, args.allow_write)
        return 0

    interactive_loop(sql_client, ai_client, args.allow_write)
    return 0


if __name__ == "__main__":
    sys.exit(main())
