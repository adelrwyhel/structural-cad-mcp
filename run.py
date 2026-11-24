"""Entry point:  python run.py <app> [variant]      e.g.  run.py csi etabs   |   run.py autocad

Looks up apps/<app>/__init__.py, which must expose  create(variant) -> mcpkit.core.App.
Use mcpkit/supervisor.py as the launcher in MCP configs to get crash recovery.
"""
import importlib
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from mcpkit.core import Server  # noqa: E402


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: run.py <app> [variant]")
    app_name = sys.argv[1]
    variant = sys.argv[2] if len(sys.argv) > 2 else None
    pkg = importlib.import_module(f"apps.{app_name}")
    Server(pkg.create(variant)).run()


if __name__ == "__main__":
    main()
