from __future__ import annotations

import json
import os

from .clients import make_mcp_client, make_workspace_client
from .config import Settings, load_settings
from .endpoints import DEFAULT_MCP_ENDPOINTS, parse_endpoint_map
from .report import build_endpoint_reports, format_endpoint_reports
from .sql_guardrails import looks_like_read_only_sql, looks_like_write_sql, prepare_sql_query


def extract_text(result) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(item))

    if parts:
        return "\n".join(parts)
    return str(result)


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


def run_sql(sql_client, query: str) -> None:
    print("\nRunning execute_sql_read_only...")
    result = sql_client.call_tool("execute_sql_read_only", {"query": query})
    pretty_print_result(result)


def run_python(ai_client, code: str) -> None:
    print("\nRunning system__ai__python_exec...")
    result = ai_client.call_tool("system__ai__python_exec", {"code": code})
    pretty_print_result(result)


def handle_query(
    query: str,
    settings: Settings,
    sql_client,
    ai_client,
    allow_write_override: bool = False,
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
        validated = prepare_sql_query(sql, settings, allow_write_override=allow_write_override)
        run_sql(sql_client, validated)
        return

    if lowered.startswith(("py ", "python ")):
        code = stripped.split(" ", 1)[1]
        run_python(ai_client, code)
        return

    if looks_like_read_only_sql(stripped):
        validated = prepare_sql_query(stripped, settings, allow_write_override=False)
        run_sql(sql_client, validated)
        return

    if looks_like_write_sql(stripped):
        if not allow_write_override:
            print("That looks like write SQL. Re-run with --allow-write if you want to execute it.")
            return
        validated = prepare_sql_query(stripped, settings, allow_write_override=True)
        run_sql(sql_client, validated)
        return

    print(
        "I could not classify that input. Try prefixing with `sql ` or `py `, or type `help`."
    )


def build_clients(settings: Settings):
    workspace_client = make_workspace_client(settings)
    sql_client = make_mcp_client(
        workspace_client,
        DEFAULT_MCP_ENDPOINTS["sql"],
        host=settings.databricks_host,
    )
    ai_client = make_mcp_client(
        workspace_client,
        DEFAULT_MCP_ENDPOINTS["ai_functions"],
        host=settings.databricks_host,
    )
    return workspace_client, sql_client, ai_client


def run_assistant(question: str | None = None, allow_write_override: bool = False) -> int:
    settings = load_settings()
    _, sql_client, ai_client = build_clients(settings)

    if question:
        handle_query(question, settings, sql_client, ai_client, allow_write_override=allow_write_override)
        return 0

    print("Databricks assistant")
    print("Type 'help' for commands. Type 'quit' to exit.")

    while True:
        try:
            user_input = input("\n> ").strip()
            if not user_input:
                continue
            handle_query(user_input, settings, sql_client, ai_client, allow_write_override=allow_write_override)
        except KeyboardInterrupt:
            print("\nBye.")
            return 0
        except Exception as exc:
            print(f"Error: {exc}")


def run_endpoint_probe() -> int:
    settings = load_settings()
    endpoint_map = parse_endpoint_map(os.getenv("DATABRICKS_MCP_ENDPOINTS"))
    workspace_client = make_workspace_client(settings)
    reports = build_endpoint_reports(
        endpoint_map=endpoint_map,
        workspace_client=workspace_client,
        host=settings.databricks_host,
    )
    print(f"Checking {len(reports)} MCP endpoint(s).")
    print(format_endpoint_reports(reports))
    return 0
