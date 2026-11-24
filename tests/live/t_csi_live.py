"""Live SAP2000 / SAFE test over real MCP:  py t_csi_live.py sap2000|safe   (needs a blank instance running)."""
import os, shutil, sys, tempfile
from mcp_client import Session

prog = sys.argv[1]
ok = fail = 0


def check(label, cond, detail=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS " if cond else "FAIL "), label, ("" if cond else f"-> {str(detail)[:300]}"))


def good(r):
    return not (isinstance(r, dict) and r.get("error"))


def blocked(r):
    return isinstance(r, dict) and r.get("error") and "BLOCKED" in r.get("message", "")


z = 0 if prog == "safe" else 3
with Session(prog) as s:
    c = s.call
    p = c("ping"); check("ping running+writable", p.get("program_running") and p.get("writable"), p)
    check("new_blank_model", good(c("new_blank_model", units="kN_m_C")))
    check("add_material", good(c("add_material", name="C30", mat_type="Concrete", e_modulus=27e6, poisson=0.2)))
    check("add_rect_section", good(c("add_rect_section", name="B30x50", material="C30", depth=0.5, width=0.3)))
    check("add_circle_section", good(c("add_circle_section", name="CC40", material="C30", diameter=0.4)))
    check("add_slab_section", good(c("add_slab_section", name="S200", material="C30", thickness=0.2)))
    f1 = c("add_frame", x1=0, y1=0, z1=z, x2=6, y2=0, z2=z, section="B30x50"); check("add_frame", good(f1), f1)
    f2 = c("add_frame", x1=0, y1=0, z1=0, x2=0, y2=0, z2=3, section="B30x50") if prog != "safe" else f1
    a = c("add_area", points=[[0, 0, z], [6, 0, z], [6, 5, z], [0, 5, z]], section="S200"); check("add_area", good(a), a)
    check("assign_frame_section", good(c("assign_frame_section", frame=str(f1), section="CC40")))
    check("assign_area_property", good(c("assign_area_property", area=str(a), prop="S200")))
    check("set_frame_modifiers", good(c("set_frame_modifiers", frame=str(f1), i33=0.35)))
    check("assign_support", good(c("assign_support", point="1", fixed=True)))
    check("add_group+assign", good(c("add_group", name="G1")) and good(c("assign_to_group", kind="frame", name=str(f1), group="G1")))
    check("add_load_pattern", good(c("add_load_pattern", name="SDL", load_type="SuperDead")))
    check("point_load", good(c("point_load", point="1", pattern="SDL", fz=-5)))
    check("frame_uniform_load", good(c("frame_uniform_load", frame=str(f1), pattern="SDL", value=-4)))
    check("area_uniform_load", good(c("area_uniform_load", area=str(a), pattern="SDL", value=-2)))
    r = c("add_combination", name="COMB1", factors={"Dead": 1.4, "SDL": 1.4}); check("add_combination", good(r), r)
    check("model_summary", good(c("model_summary")))
    check("list_points/frames/areas", all(good(c(t, limit=5)) for t in ("list_points", "list_frames", "list_areas")))
    r = c("get_table", table_key="Joint Coordinates", max_rows=2) if prog == "sap2000" else {"ok": 1}
    check("get_table (geometry)", good(r), r)
    r = c("save_model", path=f"mcp_live_{prog}", overwrite=True); check("save_model", good(r), r)
    saved = r
    r = c("run_analysis"); check("run_analysis", good(r), r)
    for t in ("base_reactions", "joint_reactions", "joint_displacements"):
        r = c(t, max_rows=3); check(t, good(r) and "columns" in r, r)
    if prog == "sap2000":
        r = c("modal_summary"); check("modal_summary", good(r) and r.get("total_modes", 0) > 0, r)
        r = c("frame_forces", max_rows=3); check("frame_forces", good(r), r)
    r = c("export_table_csv", table_key="Joint Reactions", filename=f"t_{prog}"); check("export_table_csv", good(r), r)
    r = c("export_report", filename=f"t_report_{prog}"); check("export_report", good(r), r)
    r = c("delete_object", kind="area", name=str(a)); check("delete refused while locked (clear msg)", not good(r) and "locked" in r["message"].lower(), r)
    check("unlock_model", good(c("unlock_model")))
    check("delete_object area", good(c("delete_object", kind="area", name=str(a))))
    check("refresh_view", good(c("refresh_view")))

    # ---- guard: simulate the user's real model outside the sandbox
    ext = {"sap2000": ".sdb", "safe": ".fdb"}[prog]
    # Simulate the user's real model: a saved model WITHOUT the in-file sandbox marker, outside the sandbox folder.
    import comtypes.client
    tmp = tempfile.mkdtemp(prefix="userwork_")
    user_copy = os.path.join(tmp, "REAL_PROJECT" + ext)
    _pid = {"sap2000": "CSI.SAP2000.API.SapObject", "safe": "CSI.SAFE.API.ETABSObject"}[prog]
    _m = comtypes.client.GetActiveObject(_pid).SapModel
    _m.SetModelIsLocked(False); _m.GroupDef.Delete("__MCP_SANDBOX__"); _m.File.Save(user_copy)
    h0 = os.path.getsize(user_copy), os.path.getmtime(user_copy)
    check("simulated user model is open (no marker)", os.path.normcase(os.path.splitext(str(c("status").get("file")))[0]) == os.path.normcase(os.path.splitext(user_copy)[0]), c("status"))
    check("ping says read-only", c("ping").get("writable") is False)
    check("READ works on user file", good(c("model_summary")))
    for tool, args in [("add_frame", dict(x1=0, y1=0, z1=0, x2=1, y2=1, z2=0)), ("add_load_pattern", dict(name="HACK")),
                       ("unlock_model", {}), ("run_analysis", {}), ("save_model", {}),
                       ("save_model", dict(path="stolen", overwrite=True)), ("new_blank_model", {}),
                       ("delete_object", dict(kind="frame", name="1")),
                       ("set_table", dict(table_key="Joint Coordinates", columns=["Joint"], rows=[["9"]]))]:
        check(f"BLOCKED on user file: {tool}", blocked(c(tool, **args)), c(tool, **args) if tool != "save_model" else "")
    check("user file untouched on disk", (os.path.getsize(user_copy), os.path.getmtime(user_copy)) == h0)
print(f"\nRESULT {prog}: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
