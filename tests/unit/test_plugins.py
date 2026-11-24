"""Every app plugin must import and register its tools without any CAD program installed."""
import importlib

import pytest

from mcpkit.core import Server

CASES = [("csi", "etabs"), ("csi", "sap2000"), ("csi", "safe"), ("autocad", None),
         ("office", "excel"), ("office", "word"), ("office", "powerpoint")]


@pytest.mark.parametrize("app,variant", CASES)
def test_plugin_loads_all_modules(app, variant):
    pkg = importlib.import_module(f"apps.{app}")
    srv = Server(pkg.create(variant))
    srv._builtin_tools()
    for m in srv.app.modules:
        srv.load_module(m)
    failed = {k: v["error"] for k, v in srv.modules.items() if not v["ok"]}
    assert not failed, failed
    assert len(srv.tools) > 15
    for needed in ("server_info", "restart_server", "allow_edit", "revoke_edit", "edit_status", "ping"):
        assert needed in srv.tools, needed


def test_tool_names_unique_per_server():
    pkg = importlib.import_module("apps.csi")
    srv = Server(pkg.create("etabs"))
    srv._builtin_tools()
    names = []
    for m in srv.app.modules:
        mod = importlib.import_module(m)
        names += [n for n, f in vars(mod).items() if callable(f) and hasattr(f, "_mcp") and f.__module__ == mod.__name__]
    assert len(names) == len(set(names)), "duplicate tool name across modules"


def test_write_tools_are_flagged():
    pkg = importlib.import_module("apps.csi")
    srv = Server(pkg.create("etabs"))
    srv._builtin_tools()
    for m in srv.app.modules:
        srv.load_module(m)
    for name in ("add_frame", "run_analysis", "set_table", "save_model", "delete_object", "new_blank_model", "unlock_model"):
        assert srv.tools[name]["write"], f"{name} must be a guarded write tool"
    for name in ("get_table", "model_summary", "list_frames", "ping"):
        assert not srv.tools[name]["write"], f"{name} should be read-only"
