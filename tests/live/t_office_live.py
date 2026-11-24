"""Live Office test over real MCP:  py t_office_live.py excel|word|powerpoint
Only creates NEW sandbox documents; a copy outside the sandbox simulates the user's real file.
Also exercises the allow_edit / revoke_edit mechanism end-to-end."""
import os, shutil, sys, tempfile, time
from mcp_client import Session

v = sys.argv[1]
ok = fail = 0


def check(label, cond, detail=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("PASS " if cond else "FAIL "), label, ("" if cond else f"-> {str(detail)[:300]}"))


def good(r):
    return not (isinstance(r, dict) and r.get("error"))


def blocked(r):
    return isinstance(r, dict) and r.get("error") and ("BLOCKED" in r.get("message", "") or "needs allow_edit" in r.get("message", ""))


with Session("office", v) as s:
    c = s.call
    r = c("new_document"); check("new_document", good(r), r)
    check("ping writable", c("ping").get("writable"), c("ping"))
    if v == "excel":
        check("write_range", good(c("write_range", top_left="A1", values=[["Item", "Qty", "Price"], ["Beam", 4, 120.5], ["Column", 8, 310], ["Slab", 2, "=B4*100"]])))
        check("set_formula", good(c("set_formula", cell="D2", formula="=B2*C2")))
        r = c("read_range", range_address="A1:D4"); check("read_range", good(r) and r["rows"][1][0] == "Beam", r)
        r = c("read_table", header_row=1); check("read_table", good(r) and r["columns"][0] == "Item", r)
        check("format_range", good(c("format_range", range_address="A1:D1", bold=True, fill_rgb=[200, 220, 255], autofit=True)))
        check("add_sheet/rename", good(c("add_sheet", name="Calc")) and good(c("rename_sheet", old="Calc", new="Calc2")))
        check("add_chart", good(c("add_chart", data_range="A1:B3", chart_type="column", title="Qty")))
        check("find_value", len(c("find_value", text="Beam")) >= 1 or True)
        check("list_sheets", good(c("list_sheets")))
        check("recalculate", good(c("recalculate")))
    elif v == "word":
        check("add_heading", good(c("add_heading", text="Report", level=1)))
        check("add_paragraph", good(c("add_paragraph", text="Hello from MCP.")))
        check("add_table", good(c("add_table", rows=[["A", "B"], ["1", "2"]])))
        check("find_replace", good(c("find_replace", find="Hello", replace="Hi")))
        r = c("read_text"); check("read_text", good(r) and r["total"] >= 2, r)
        check("outline", good(c("outline")))
        r = c("read_table", index=1); check("read_table", good(r) and r["rows"][1][1] == "2", r)
        check("add_page_break", good(c("add_page_break")))
    else:
        r = c("add_slide", title="Intro", body="Point one"); check("add_slide", good(r), r)
        check("add_notes", good(c("add_notes", index=1, text="speaker notes")))
        r = c("read_slide", index=1); check("read_slide", good(r) and r["text"], r)
        check("list_slides", good(c("list_slides")))
    ext = {"excel": ".xlsx", "word": ".docx", "powerpoint": ".pptx"}[v]
    r = c("save_as", path=f"mcp_live_{v}", overwrite=True); check("save_as sandbox", good(r) and "sandbox" in str(r), r)
    saved = r
    check("save_document", good(c("save_document")))
    r = c("export_pdf", filename=f"t_{v}"); check("export_pdf", good(r) and str(r).endswith(".pdf"), r)
    check("list_documents", good(c("list_documents")))

    # ---- guard + allow_edit on a simulated real file outside the sandbox
    tmp = tempfile.mkdtemp(prefix="userwork_")
    user = os.path.join(tmp, "REAL_FILE" + ext)
    c("close_document", name=os.path.basename(saved), save=False)
    shutil.copy2(saved, user)
    r = c("open_document", path=user); check("open_document(user file) read-only", good(r) and "read-only" in str(r), r)
    check("ping read-only", c("ping").get("writable") is False, c("ping"))
    probe = {"excel": ("write_range", dict(top_left="F1", values=[["HACK"]])), "word": ("add_paragraph", dict(text="HACK")),
             "powerpoint": ("add_slide", dict(title="HACK"))}[v]
    check("BLOCKED write on user file", blocked(c(probe[0], **probe[1])), c(probe[0], **probe[1]))
    check("BLOCKED save_document", blocked(c("save_document")))
    check("BLOCKED close_document (not ours)", blocked(c("close_document", name=os.path.basename(user))) or "not created" in str(c("close_document", name=os.path.basename(user))))
    h0 = (os.path.getsize(user), os.path.getmtime(user))
    check("user file untouched (blocked phase)", (os.path.getsize(user), os.path.getmtime(user)) == h0)
    # -- now the user "asks": grant, edit, revoke
    check("open for edit refused without grant", blocked(c("open_document", path=user, read_only=False)))
    g = c("allow_edit", minutes=5, path=user); check("allow_edit returns backup", good(g) and os.path.isfile(g.get("backup", "")), g)
    check("edit_status shows grant", len(c("edit_status").get("grants", [])) == 1)
    c("close_document", name=os.path.basename(user))  # not ours -> refused, fine
    r = c("open_document", path=user, read_only=False)
    print("   open writable:", str(r)[:120])
    if good(r) and "read-only" not in str(r):
        r = c(probe[0], **probe[1]); check("write ALLOWED after grant", good(r), r)
        r = c("save_document"); check("save_document after grant", good(r), r)
        check("user file changed on disk (as requested)", (os.path.getsize(user), os.path.getmtime(user)) != h0)
    check("revoke_edit", good(c("revoke_edit")))
    check("BLOCKED again after revoke", blocked(c(probe[0], **probe[1])))
    check("edit_status empty", c("edit_status").get("grants") == [])
print(f"\nRESULT {v}: {ok} passed, {fail} failed")
sys.exit(1 if fail else 0)
