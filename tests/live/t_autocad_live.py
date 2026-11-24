"""Live AutoCAD test over real MCP (needs AutoCAD running with NO real drawings open)."""
import os, shutil, sys, tempfile
from mcp_client import Session

ok = fail = 0


def check(label, cond, detail=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS " if cond else "FAIL "), label, ("" if cond else f"-> {str(detail)[:300]}"))


def good(r):
    return not (isinstance(r, dict) and r.get("error"))


def blocked(r):
    return isinstance(r, dict) and r.get("error") and ("BLOCKED" in r.get("message", "") or "blocked" in r.get("message", "") or "not created by these tools" in r.get("message", ""))


with Session("autocad") as s:
    c = s.call
    p = c("ping"); check("ping running", p.get("program_running"), p)
    r = c("new_drawing"); check("new_drawing", good(r), r)
    check("status", good(c("status")))
    check("add_layer", good(c("add_layer", name="WALLS", color=1)) and good(c("add_layer", name="DIMS", color=3)))
    check("set_current_layer", good(c("set_current_layer", name="WALLS")))
    check("set_layer_state", good(c("set_layer_state", name="DIMS", on=True, frozen=False, locked=False)))
    l1 = c("add_line", x1=0, y1=0, x2=10, y2=0, layer="WALLS"); check("add_line", good(l1), l1)
    pl = c("add_polyline", points=[[0, 0], [10, 0], [10, 5]], closed=False, layer="WALLS"); check("add_polyline", good(pl), pl)
    rc = c("add_rectangle", x1=0, y1=0, x2=6, y2=4, layer="WALLS"); check("add_rectangle", good(rc), rc)
    ci = c("add_circle", cx=3, cy=2, radius=1, layer="WALLS"); check("add_circle", good(ci), ci)
    check("add_arc", good(c("add_arc", cx=0, cy=0, radius=2, start_deg=0, end_deg=90)))
    tx = c("add_text", x=1, y=1, text="Hello", height=0.5, layer="WALLS"); check("add_text", good(tx), tx)
    check("add_mtext", good(c("add_mtext", x=1, y=8, width=5, text="Line one\\PLine two", height=0.4)))
    check("add_linear_dimension", good(c("add_linear_dimension", x1=0, y1=0, x2=6, y2=0, offset_x=3, offset_y=-1, layer="DIMS")))
    r = c("add_hatch", points=[[0, 0], [6, 0], [6, 4], [0, 4]], pattern="ANSI31"); check("add_hatch", good(r), r)
    check("entity_counts", good(c("entity_counts")))
    check("layer_summary", good(c("layer_summary")))
    r = c("list_entities", layer="WALLS", limit=3); check("list_entities", good(r) and r["items"], r)
    r = c("get_entity", handle=str(l1)); check("get_entity", good(r) and "StartPoint" in r, r)
    r = c("get_text_content"); check("get_text_content", good(r), r)
    r = c("drawing_extents"); check("drawing_extents", good(r) and r["width"] > 0, r)
    r = c("measure_layer", layer="WALLS"); check("measure_layer", good(r) and r["total_length"] > 10, r)
    r = c("entities_in_window", x1=-1, y1=-1, x2=11, y2=6); check("entities_in_window", good(r) and r["count"] > 0, r)
    check("list_blocks", good(c("list_blocks")))
    check("get_variable", good(c("get_variable", name="INSUNITS")))
    check("move_entity", good(c("move_entity", handle=str(l1), dx=1, dy=1)))
    cp = c("copy_entity", handle=str(l1), dx=0, dy=2); check("copy_entity", good(cp), cp)
    check("rotate_entity", good(c("rotate_entity", handle=str(cp), base_x=0, base_y=0, angle_deg=15)))
    check("scale_entity", good(c("scale_entity", handle=str(cp), base_x=0, base_y=0, factor=1.5)))
    check("mirror_entity", good(c("mirror_entity", handle=str(cp), x1=0, y1=0, x2=0, y2=10)))
    r = c("offset_entity", handle=str(rc), distance=0.5); check("offset_entity", good(r), r)
    check("set_entity_layer", good(c("set_entity_layer", handle=str(ci), layer="DIMS")))
    check("set_entity_color", good(c("set_entity_color", handle=str(ci), color=2)))
    check("erase_entity", good(c("erase_entity", handle=str(cp))))
    check("rename_layer", good(c("rename_layer", old="DIMS", new="DIMENSIONS")))
    check("zoom_extents + regen", good(c("zoom_extents")) and good(c("regen")))
    check("send_command (safe)", good(c("send_command", command="_REGEN ")))
    for bad in ("_QUIT Y ", "(vl-file-delete \"C:/x.txt\")", "_SHELL notepad ", "_OPEN ", "_QSAVE ", "(startapp \"calc\")"):
        r = c("send_command", command=bad); check(f"send_command denylist: {bad.strip()[:22]}", blocked(r), r)
    r = c("save_as", path="mcp_live_acad", overwrite=True); check("save_as sandbox", good(r) and "sandbox" in str(r), r)
    saved = r
    check("save_drawing", good(c("save_drawing")))
    r = c("plot_pdf", filename="t_acad"); check("plot_pdf", good(r) and str(r).endswith(".pdf"), r)

    # ---- guard: simulate the user's real drawing (a DWG outside the sandbox), opened read-only
    # Simulate the user's real drawing: a saved DWG WITHOUT the in-file sandbox marker layer, outside the sandbox folder.
    import win32com.client
    _d = win32com.client.GetActiveObject("AutoCAD.Application").ActiveDocument
    _d.ActiveLayer = _d.Layers.Item("0")
    _d.Layers.Item("__MCP_SANDBOX__").Delete()
    _d.Save()
    tmp = tempfile.mkdtemp(prefix="userwork_")
    user_copy = os.path.join(tmp, "REAL_PLAN.dwg")
    shutil.copy2(saved, user_copy)
    h0 = os.path.getsize(user_copy), os.path.getmtime(user_copy)
    r = c("open_drawing", path=user_copy); check("open_drawing(user file)", good(r), r)
    check("ping says read-only", c("ping").get("writable") is False, c("ping"))
    check("READ works on user drawing", good(c("entity_counts")) and good(c("layer_summary")))
    for tool, args in [("add_line", dict(x1=0, y1=0, x2=1, y2=1)), ("add_text", dict(x=0, y=0, text="HACK")),
                       ("erase_entity", dict(handle=str(l1))), ("move_entity", dict(handle=str(l1), dx=1, dy=1)),
                       ("add_layer", dict(name="HACK")), ("save_drawing", {}), ("save_as", dict(path=os.path.join(tmp, "x.dwg"))),
                       ("send_command", dict(command="_ERASE ALL ")), ("purge_unused", {}), ("set_layer_state", dict(name="WALLS", on=False))]:
        check(f"BLOCKED on user drawing: {tool}", blocked(c(tool, **args)), c(tool, **args))
    name = os.path.basename(user_copy)
    r = c("close_drawing", name=name); check("close_drawing refuses non-owned drawing", blocked(r), r)
    check("user drawing untouched on disk", (os.path.getsize(user_copy), os.path.getmtime(user_copy)) == h0)
    info = c("server_info"); print("server_info:", info["calls"], "calls,", info["failures"], "failures")
print(f"\nRESULT autocad: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
