"""Every app plugin must import and register its tools without any CAD program installed."""
import importlib

import pytest

from mcpkit.core import Server

CASES = [("etabs", None), ("sap2000", None), ("safe", None), ("autocad", None), ("autocad", "2014"),
         ("office", "excel"), ("office", "word"), ("office", "powerpoint")]
BUILTIN = ("server_info", "restart_server", "allow_edit", "revoke_edit", "edit_status", "ping")


def _server(app, variant):
    pkg = importlib.import_module(f"apps.{app}")
    srv = Server(pkg.create(variant))
    srv._builtin_tools()
    for m in srv.app.modules:
        srv.load_module(m)
    return srv


@pytest.mark.parametrize("app,variant", CASES)
def test_plugin_loads_all_modules(app, variant):
    srv = _server(app, variant)
    failed = {k: v["error"] for k, v in srv.modules.items() if not v["ok"]}
    assert not failed, failed
    assert len(srv.tools) > 15
    for needed in BUILTIN:
        assert needed in srv.tools, needed


@pytest.mark.parametrize("app", ["etabs", "sap2000", "safe"])
def test_tool_names_unique_per_server(app):
    srv = _server(app, None)
    names = []
    for m in srv.app.modules:
        mod = importlib.import_module(m)
        names += [n for n, f in vars(mod).items() if callable(f) and hasattr(f, "_mcp") and f.__module__ == mod.__name__]
    assert len(names) == len(set(names)), "duplicate tool name across modules"


def test_each_program_has_its_own_tools():
    etabs, sap, safe = (_server(a, None) for a in ("etabs", "sap2000", "safe"))
    assert {"define_stories", "drift_check", "new_grid_model", "add_wall_section"} <= set(etabs.tools)
    assert not ({"define_stories", "drift_check", "new_grid_model", "add_wall_section"} & set(sap.tools))
    assert not ({"define_stories", "drift_check"} & set(safe.tools))
    assert "legacy_api_status" in sap.tools and "slab_strip_forces" in safe.tools


def test_write_tools_are_flagged():
    srv = _server("etabs", None)
    for name in ("add_frame", "run_analysis", "set_table", "save_model", "delete_object", "new_blank_model",
                 "unlock_model", "define_stories", "new_grid_model"):
        assert srv.tools[name]["write"], f"{name} must be a guarded write tool"
    for name in ("get_table", "model_summary", "list_frames", "ping", "drift_check"):
        assert not srv.tools[name]["write"], f"{name} should be read-only"


def test_unverified_tools_are_marked():
    srv = _server("etabs", None)
    assert srv.tools["pier_forces"]["unverified"]
    assert not srv.tools["add_frame"]["unverified"]
    assert _server("sap2000", None).tools["legacy_api_status"]["unverified"]
    assert _server("autocad", None).tools["launch_program"]["unverified"]


@pytest.mark.parametrize("app,verified,other", [("etabs", "21.2.0", "19.1.0"), ("sap2000", "26.2.0", "20.0.0"),
                                               ("safe", "21.2.0", "16.0.1"), ("autocad", "25.1s (LMS Tech)", "19.1s")])
def test_version_support_status(app, verified, other):
    a = _server(app, None).app
    a.version_string = lambda: verified
    assert a.support_info()["support"] == "verified"
    a.version_string = lambda: other
    info = a.support_info()
    assert info["support"] == "UNVERIFIED" and "warning" in info