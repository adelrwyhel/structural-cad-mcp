"""Live ETABS test over real MCP. Only creates NEW sandbox models. Needs a blank ETABS running.
Includes the guard test: a copy of a model OUTSIDE the sandbox must be read-only for write tools."""
import json, os, shutil, sys, tempfile
from mcp_client import Session

ok = fail = 0


def check(label, cond, detail=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS " if cond else "FAIL "), label, ("" if cond else f"-> {str(detail)[:300]}"))


def good(r):
    return not (isinstance(r, dict) and r.get("error"))


def blocked(r):
    return isinstance(r, dict) and r.get("error") and "BLOCKED" in r.get("message", "")


with Session("etabs") as s:
    c = s.call
    p = c("ping"); check("ping program_running + writable", p.get("program_running") and p.get("writable"), p)
    r = c("new_blank_model", units="kN_m_C"); check("new_blank_model", good(r), r)
    r = c("define_stories", names=["S1", "S2", "S3"], heights=[3.5, 3.2, 3.2]); check("define_stories (empty model)", good(r) and len(r.get("stories", [])) == 3, r)
    r = c("add_diaphragm", name="DX"); check("add_diaphragm", good(r), r)
    check("set_units", good(c("set_units", units="kN_m_C")))
    check("add_material", good(c("add_material", name="C30", mat_type="Concrete", e_modulus=27e6, poisson=0.2)))
    check("add_rect_section", good(c("add_rect_section", name="C40x40", material="C30", depth=0.4, width=0.4)))
    check("add_circle_section", good(c("add_circle_section", name="CC40", material="C30", diameter=0.4)))
    check("add_i_section", good(c("add_i_section", name="IS", material="C30", depth=0.3, flange_width=0.15, flange_thickness=0.01, web_thickness=0.008)))
    check("add_slab_section", good(c("add_slab_section", name="S200", material="C30", thickness=0.2)))
    check("add_wall_section", good(c("add_wall_section", name="W250", material="C30", thickness=0.25)))
    fr = c("add_frame", x1=0, y1=0, z1=0, x2=0, y2=0, z2=3.5, section="C40x40"); check("add_frame", good(fr), fr)
    fr2 = c("add_frame", x1=0, y1=0, z1=3.5, x2=6, y2=0, z2=3.5, section="C40x40"); check("add_frame2", good(fr2), fr2)
    ar = c("add_area", points=[[0, 0, 3.5], [6, 0, 3.5], [6, 5, 3.5], [0, 5, 3.5]], section="S200"); check("add_area", good(ar), ar)
    check("assign_frame_section", good(c("assign_frame_section", frame=str(fr), section="CC40")))
    check("assign_area_property", good(c("assign_area_property", area=str(ar), prop="S200")))
    check("set_frame_modifiers", good(c("set_frame_modifiers", frame=str(fr2), i33=0.35)))
    check("assign_support", good(c("assign_support", point="1", fixed=True)))
    check("add_group+assign", good(c("add_group", name="G1")) and good(c("assign_to_group", kind="frame", name=str(fr), group="G1")))
    check("add_load_pattern", good(c("add_load_pattern", name="SDL", load_type="SuperDead")))
    check("point_load", good(c("point_load", point="1", pattern="SDL", fz=-5)))
    check("frame_uniform_load", good(c("frame_uniform_load", frame=str(fr2), pattern="SDL", value=-4)))
    check("area_uniform_load", good(c("area_uniform_load", area=str(ar), pattern="SDL", value=-2)))
    r = c("add_combination", name="COMB1", factors={"Dead": 1.4, "SDL": 1.4, "Live": 1.7}); check("add_combination", good(r), r)
    check("list_combinations has COMB1", "COMB1" in c("list_combinations"))
    r = c("assign_diaphragm_to_story", story="S1", diaphragm="DX"); check("assign_diaphragm_to_story", good(r) and r.get("assigned_points", 0) > 0, r)
    r = c("define_stories", names=["A"], heights=[3.0]); check("define_stories refused when objects exist", not good(r) and "no objects" in r["message"], r)
    r = c("model_summary"); check("model_summary", good(r) and r.get("frames", 0) >= 2, r)
    check("list_points/frames/areas", all(good(c(t, limit=5)) for t in ("list_points", "list_frames", "list_areas")))
    r = c("get_table", table_key="Story Definitions", columns=["Story", "Height"]); check("get_table columns", good(r) and r["total_rows"] >= 1, r)
    r = c("set_table", table_key="Load Pattern Definitions", columns=["Name", "IsAuto", "Type", "SelfWtMult"], rows=[["TEST_PAT", "No", "Other", "0"]])
    print("   set_table:", json.dumps(r)[:200])
    r = c("save_model", path="mcp_live_test", overwrite=True); check("save_model (sandbox)", good(r) and "sandbox" in str(r), r)
    saved = r
    r = c("run_analysis"); check("run_analysis", good(r), r)
    for t in ("base_reactions", "joint_reactions", "joint_displacements", "frame_forces"):
        r = c(t, max_rows=3); check(t, good(r) and r.get("total_rows", 0) >= 0 and "columns" in r, r)
    r = c("run_design", kind="concrete"); print("   run_design:", json.dumps(r)[:220])
    lt = c("list_tables", contains="Drift"); check("list_tables filter (after analysis)", (isinstance(lt, list) and lt) or isinstance(lt, str), lt)
    r = c("modal_summary"); check("modal_summary", good(r) and r.get("total_modes", 0) > 0, r)
    r = c("drift_check", limit=0.02); check("drift_check", good(r) and "max_per_direction" in r, r)
    r = c("export_table_csv", table_key="Base Reactions", filename="t_base"); check("export_table_csv", good(r), r)
    r = c("export_report", filename="t_report"); check("export_report", good(r), r)
    r = c("delete_object", kind="area", name=str(ar)); check("delete while locked is refused with clear msg", not good(r) and "locked" in r["message"].lower(), r)
    check("unlock_model", good(c("unlock_model")))
    r = c("delete_object", kind="area", name=str(ar)); check("delete_object area", good(r), r)
    r = c("set_run_case", name="Dead", run=True); check("set_run_case", good(r), r)
    check("refresh_view", good(c("refresh_view")))

    # ---------- GUARD: simulate the user's real model (a file outside the sandbox) ----------
    # Simulate the user's real model: a saved model WITHOUT the in-file sandbox marker, outside the sandbox folder.
    import comtypes.client
    tmp = tempfile.mkdtemp(prefix="userwork_")
    user_copy = os.path.join(tmp, "REAL_PROJECT.EDB")
    _m = comtypes.client.GetActiveObject("CSI.ETABS.API.ETABSObject").SapModel
    _m.SetModelIsLocked(False); _m.GroupDef.Delete("__MCP_SANDBOX__"); _m.File.Save(user_copy)
    h0 = os.path.getsize(user_copy), os.path.getmtime(user_copy)
    check("simulated user model is open (no marker)", os.path.normcase(os.path.splitext(str(c("status").get("file")))[0]) == os.path.normcase(os.path.splitext(user_copy)[0]), c("status"))
    check("ping says read-only", c("ping").get("writable") is False, c("ping"))
    check("READ works on user file", good(c("model_summary")) and good(c("list_tables", contains="Story")))
    for tool, args in [("add_frame", dict(x1=0, y1=0, z1=0, x2=1, y2=1, z2=1)), ("add_load_pattern", dict(name="HACK")),
                       ("add_combination", dict(name="HACK", factors={"Dead": 1})), ("unlock_model", {}),
                       ("run_analysis", {}), ("save_model", {}), ("save_model", dict(path="stolen", overwrite=True)),
                       ("new_blank_model", {}), ("open_model", dict(path=user_copy)), ("set_table", dict(table_key="Story Definitions", columns=["Story"], rows=[["X"]])),
                       ("delete_object", dict(kind="frame", name="1"))]:
        check(f"BLOCKED on user file: {tool}", blocked(c(tool, **args)), c(tool, **args) if tool != "save_model" else "")
    check("user file untouched on disk", (os.path.getsize(user_copy), os.path.getmtime(user_copy)) == h0)
    r = c("server_info"); print("server_info:", r["calls"], "calls,", r["failures"], "failures")

print(f"\nRESULT: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)

