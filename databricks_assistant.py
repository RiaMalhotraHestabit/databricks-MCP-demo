from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dbx_mcp_demo.cli import run_assistant


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Interactive Databricks assistant using MCP-backed SQL and Python tools."
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Allow write SQL in interactive or one-shot mode.",
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="Optional one-shot prompt. Omit for interactive mode.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    question = " ".join(args.question).strip() or None
    return run_assistant(question=question, allow_write_override=args.allow_write)


if __name__ == "__main__":
    sys.exit(main())
