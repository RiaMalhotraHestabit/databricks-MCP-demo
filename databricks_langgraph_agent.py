from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dbx_mcp_demo.langgraph_agent import build_agent, ask_agent, interactive_loop, build_tools


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Natural-language Databricks assistant using LangGraph and Databricks MCP."
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Natural-language question to ask. Omit for interactive mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        agent = build_agent()
    except Exception as exc:
        print(f"Setup error: {exc}")
        return 2

    question = " ".join(args.question).strip()
    tools = build_tools()
    if question:
        ask_agent(agent, question)
    else:
        interactive_loop(agent, tools=tools)
    return 0


if __name__ == "__main__":
    sys.exit(main())
