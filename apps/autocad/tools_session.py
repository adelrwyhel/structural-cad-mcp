"""Session: health, drawings, files, plot, raw commands."""
import os

from mcpkit import core
from mcpkit.core import GuardError, export_path, safe_path, tool

from .adapter import A

DWG = (".dwg",)


@tool()
def ping() -> dict:
    """Health check: is AutoCAD reachable, which drawing is active, and may the tools modify it?"""
    info = {"server": "autocad", "sandbox_folder": str(core.SANDBOX), "log": str(core.LOGS / "autocad.log"),
            "allow_edit_existing_env": core.ALLOW_EDIT_EXISTING}
    info.update(A.info())
    if info.get("program_running"):
        info.update(A.support_info())
    if info.get("program_running") and info.get("drawings_open"):
        try:
            A.guard("ping-check")
            info["writable"] = True
        except GuardError as e:
            info["writable"] = False
            info["why_read_only"] = str(e)
    return info


@tool()
def status() -> dict:
    """AutoCAD version and the active drawing's key facts."""
    a = A.app()
    d = {"version": a.Version, "drawings_open": a.Documents.Count}
    if a.Documents.Count:
        doc = a.ActiveDocument
        d.update({"drawing": doc.Name, "path": doc.FullName if doc.Path else "(unsaved)", "saved": doc.Saved,
                  "modelspace_entities": doc.ModelSpace.Count, "layers": doc.Layers.Count,
                  "blocks": doc.Blocks.Count, "units_insunits": doc.GetVariable("INSUNITS")})
    return d


@tool()
def list_drawings() -> list:
    """All open drawings."""
    docs = A.app().Documents
    return [{"name": docs.Item(i).Name, "path": docs.Item(i).FullName if docs.Item(i).Path else "(unsaved)",
             "entities": docs.Item(i).ModelSpace.Count} for i in range(docs.Count)]


@tool()
def set_active_drawing(name: str) -> str:
    """Make an open drawing active."""
    A.doc(name).Activate()
    return name


@tool(timeout=300)
def new_drawing() -> str:
    """Create a NEW drawing (sandbox-safe: write tools may edit it). Does not touch any open drawing."""
    d = A.app().Documents.Add()
    A.ours_docs.add(d.Name)
    lay = d.Layers.Add(core.MARKER)      # in-file marker: survives restarts and Save As
    lay.LayerOn = False
    return d.Name


@tool(timeout=300)
def open_drawing(path: str, read_only: bool = True) -> str:
    """Open an existing .dwg READ-ONLY by default. read_only=False (needed to save changes) requires the user's
    explicit request and a prior allow_edit(path=...) grant, unless the file lives in the sandbox folder."""
    p = safe_path(path, DWG, must_exist=True)
    if not read_only and not (core.is_sandbox(p) or core.is_granted(p)):
        raise GuardError("opening a real drawing for editing needs allow_edit(path=<this file>) first - and only when "
                         "the user explicitly asked to modify it.")
    d = A.app().Documents.Open(p, read_only)
    return f"{d.Name}" + (" (read-only)" if read_only else "")


@tool(write=True)
def save_drawing() -> str:
    """Save the active drawing in place (it must already be a sandbox file)."""
    d = A.doc()
    if not d.Path:
        raise RuntimeError("Drawing has never been saved; use save_as('name.dwg').")
    d.Save()
    return d.FullName


@tool(write=True)
def save_as(path: str, overwrite: bool = False) -> str:
    """Save the active drawing as a new .dwg (relative names go to the sandbox folder)."""
    p = path if os.path.splitext(path)[1] else path + ".dwg"
    p = safe_path(p, DWG, write=True, overwrite=overwrite)
    d = A.doc()
    d.SaveAs(p)
    core.register_sandbox(p)
    A.ours_docs.discard(d.Name)
    return p


@tool(write=True)
def close_drawing(name: str, save: bool = False) -> str:
    """Close an open drawing that these tools created (never your own drawings)."""
    d = A.doc(name)
    path = d.FullName if d.Path else ""
    if not (core.is_sandbox(path) or (not path and d.Name in A.ours_docs)):
        raise GuardError(f"'{name}' was not created by these tools; close it yourself in AutoCAD.")
    d.Close(save)
    A.ours_docs.discard(name)
    return f"closed {name}"


@tool(timeout=300)
def plot_pdf(filename: str = "drawing", layout: str = "") -> str:
    """Plot the active drawing (or a named layout) to exports/<name>.pdf using 'DWG To PDF.pc3'."""
    d = A.doc()
    p = export_path(filename, ".pdf")
    if layout:
        d.ActiveLayout = d.Layouts.Item(layout)
    d.ActiveLayout.ConfigName = "DWG To PDF.pc3"
    d.Plot.PlotToFile(p)
    return p


@tool(write=True)
def send_command(command: str) -> str:
    """Send a raw command string to the AutoCAD command line (end with a space to execute, e.g. 'ZOOM E ').
    Commands that save/close/open files or run programs are blocked."""
    A.check_command(command)
    A.doc().SendCommand(command)
    return "sent"


@tool()
def zoom_extents() -> str:
    """Zoom to the drawing extents."""
    A.app().ZoomExtents()
    return "ok"


@tool()
def regen() -> str:
    """Regenerate the active drawing."""
    A.doc().Regen(1)
    return "ok"


# ---- installations / launching (any AutoCAD release; only 2026 is verified)
import glob
import subprocess
import time


def _installs() -> list:
    out = []
    for root in (r"C:\Program Files\Autodesk", r"C:\Program Files (x86)\Autodesk"):
        for d in glob.glob(os.path.join(root, "AutoCAD 20*")):
            exe = os.path.join(d, "acad.exe")
            if os.path.isfile(exe):
                year = os.path.basename(d).split()[-1]
                out.append({"year": year, "exe": exe, "verified": year == "2026"})
    return sorted(out, key=lambda x: x["year"])


@tool()
def list_installations() -> dict:
    """AutoCAD releases installed on this PC (2026 is the only verified one) and the running version, if any."""
    running = None
    try:
        running = A.app().Version
    except Exception:
        pass
    return {"installed": _installs(), "running_version": running, "server_year": A.year or "(any running)"}


@tool(timeout=300, unverified=True)
def launch_program(year: str = "", wait_seconds: int = 150) -> dict:
    """Start an installed AutoCAD release (e.g. '2026', '2014') and wait until its COM interface answers.
    A running AutoCAD is never closed."""
    from mcpkit import winutil
    installs = _installs()
    if not installs:
        raise RuntimeError("no AutoCAD installation found in the standard folders")
    target = next((i for i in installs if i["year"] == year), None) if year else installs[-1]
    if not target:
        raise RuntimeError(f"AutoCAD {year} is not installed. Installed: {[i['year'] for i in installs]}")
    try:
        return {"already_running": True, "version": A.app().Version}
    except Exception:
        pass
    subprocess.Popen([target["exe"]], cwd=os.path.dirname(target["exe"]), creationflags=0x00000008 | 0x00000200)
    deadline = time.time() + max(20, min(wait_seconds, 280))
    while time.time() < deadline:
        time.sleep(4)
        lic = winutil.license_problem("acad.exe")
        if lic:
            raise RuntimeError(f"AutoCAD shows a license problem: \"{lic[:300]}\"")
        try:
            v = A.app().Version
            time.sleep(10)
            return {"launched": target["exe"], "version": v}
        except Exception:
            continue
    raise RuntimeError(f"started {target['exe']} but its COM interface did not answer within {wait_seconds}s")