from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dbx_mcp_demo.clients import make_workspace_client
from dbx_mcp_demo.config import load_settings


def main() -> int:
    settings = load_settings()
    workspace_client = make_workspace_client(settings)

    for catalog in workspace_client.catalogs.list():
        print(catalog.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
