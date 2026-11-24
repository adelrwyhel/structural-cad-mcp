"""Session: health, status, summary, units, model files."""
import csv
import os

from mcpkit import core
from mcpkit.core import GuardError, export_path, safe_path, tool

from .adapter import A
from .constants import COMBO_TYPES, LOAD_TYPES, MAT_TYPES, UNITS

# ---- health / status

@tool()
def ping() -> dict:
    """Health check: is the program reachable, which model is open, and may the tools modify it?"""
    info = {"server": A.prog, "sandbox_folder": str(core.SANDBOX),
            "log": str(core.LOGS / f"{A.prog}.log"), "allow_edit_existing_env": core.ALLOW_EDIT_EXISTING}
    try:
        m = A.sap()
    except Exception as e:
        return {**info, "program_running": False, "error": str(e)}
    info.update({"program_running": True, "version": m.GetVersion()[0], "file": A.filename(m) or "(untitled)"})
    try:
        A.guard("ping-check")
        info["writable"] = True
    except GuardError as e:
        info["writable"] = False
        info["why_read_only"] = str(e)
    return info


@tool()
def status() -> dict:
    """Program version, open model file, units and lock state."""
    m = A.sap()
    inv = {v: k for k, v in UNITS.items()}
    u = m.GetPresentUnits()
    return {"program": A.title, "version": m.GetVersion()[0], "file": A.filename(m) or "(untitled)",
            "units": inv.get(u, u), "locked": m.GetModelIsLocked()}


@tool()
def model_summary() -> dict:
    """One-call overview: counts, units, load cases/patterns/combos, materials, sections, stories (ETABS)."""
    m = A.sap()
    inv = {v: k for k, v in UNITS.items()}
    p, f, a = A.counts(m)
    names = lambda obj: list(obj.GetNameList()[1])  # noqa
    out = {"file": A.filename(m) or "(untitled)", "units": inv.get(m.GetPresentUnits()), "locked": m.GetModelIsLocked(),
           "points": p, "frames": f, "areas": a,
           "load_patterns": names(m.LoadPatterns), "load_cases": names(m.LoadCases), "combinations": names(m.RespCombo),
           "materials": names(m.PropMaterial), "frame_sections": len(names(m.PropFrame))}
    if A.prog == "etabs":
        try:
            cols, rows = A.fetch(m, "Story Definitions", try_select=False)
            out["stories"] = [{"story": r[cols.index("Story")], "height": r[cols.index("Height")]} for r in rows]
        except Exception:
            out["stories"] = []
    return out


@tool()
def set_units(units: str) -> str:
    """Set present units, e.g. kN_m_C, kgf_m_C, Tonf_m_C, N_mm_C, kip_ft_F (see UNITS)."""
    if units not in UNITS:
        raise RuntimeError(f"unknown units '{units}'. Use one of: {', '.join(UNITS)}")
    A.chk(A.sap().SetPresentUnits(UNITS[units]), "SetPresentUnits")
    return units



# ---- model files

@tool(write=True, timeout=180)
def new_blank_model(units: str = "kN_m_C") -> str:
    """Start a NEW blank model. Refused if your own real model is open (it would be replaced)."""
    A.guard("new_blank_model", replacing=True)
    m = A.sap()
    _new_model(m, UNITS[units], lambda: m.File.NewBlank(), "NewBlank")
    A.ours_untitled = True
    return "new blank model (untitled, sandbox-safe). Save it with save_model('name') before running analysis."


@tool(write=True, timeout=180)
def new_grid_model(stories: int = 3, story_height: float = 3.0, bottom_height: float = 3.0, lines_x: int = 3,
                   lines_y: int = 3, spacing_x: float = 6.0, spacing_y: float = 6.0, units: str = "kN_m_C") -> str:
    """ETABS: start a NEW model with a regular grid and stories."""
    A.etabs_only("new_grid_model")
    A.guard("new_grid_model", replacing=True)
    m = A.sap()
    _new_model(m, UNITS[units], lambda: m.File.NewGridOnly(stories, story_height, bottom_height, lines_x, lines_y,
                                                          spacing_x, spacing_y), "NewGridOnly")
    A.ours_untitled = True
    return "new grid model"


@tool(write=True, timeout=300)
def open_model(path: str) -> str:
    """Open a model file. Allowed only while no real work of yours is open; opened user files stay READ-ONLY for write tools."""
    p = safe_path(path, A.exts, must_exist=True)
    A.guard("open_model", replacing=True)
    A.chk(A.sap().File.OpenFile(p), "OpenFile")
    A.ours_untitled = False
    return f"opened {p}" + ("" if core.is_sandbox(p) else "  (not a sandbox file: write tools are blocked on it)")


@tool(write=True, timeout=300)
def save_model(path: str = "", overwrite: bool = False) -> str:
    """Save the model. A relative name goes to the sandbox folder. New files are registered as sandbox models."""
    m = A.sap()
    if not path:
        if not A.filename(m):
            raise RuntimeError("model has no file name yet; pass a name, e.g. save_model('test1')")
        A.chk(m.File.Save(), "Save")
        return A.filename(m)
    p = path if os.path.splitext(path)[1] else path + A.exts[0]
    p = safe_path(p, A.exts, write=True, overwrite=overwrite)
    A.chk(m.File.Save(p), "Save")
    core.register_sandbox(p)
    A.ours_untitled = False
    return p


@tool(write=True)
def unlock_model() -> str:
    """Unlock the model (deletes analysis results)."""
    A.chk(A.sap().SetModelIsLocked(False), "SetModelIsLocked")
    return "unlocked"


# ---- installations / launching
import glob
import subprocess
import time

_ROOTS = (r"C:\Program Files\Computers and Structures", r"C:\Program Files (x86)\Computers and Structures")
_EXE = {"etabs": "ETABS.exe", "sap2000": "SAP2000.exe", "safe": "SAFE.exe"}


def _major(label: str) -> int:
    """'2016' -> 16, '21' -> 21"""
    digits = "".join(ch for ch in label if ch.isdigit())
    n = int(digits) if digits else 0
    return n - 2000 if n >= 1000 else n


def _installs() -> list:
    out = []
    for root in _ROOTS:
        for d in glob.glob(os.path.join(root, f"{A.title}*")):
            exe = os.path.join(d, _EXE[A.prog])
            if os.path.isfile(exe):
                label = os.path.basename(d)[len(A.title):].strip()
                out.append({"version": label, "major": _major(label), "exe": exe})
    return sorted(out, key=lambda x: x["major"])


@tool()
def list_installations() -> dict:
    """Installed versions of this program on this PC and which version (if any) is running right now."""
    running = None
    try:
        running = A.sap().GetVersion()[0]
    except Exception:
        pass
    return {"program": A.title, "installed": _installs(), "running_version": running}


@tool(timeout=300)
def launch_program(version: str = "", wait_seconds: int = 120) -> dict:
    """Start an installed version (e.g. '22' for ETABS 22, '2016', '26' for SAP2000) and wait until its API answers.
    Without `version` the newest installed one is used. If a DIFFERENT version is already running it is NOT closed:
    close it yourself first (so no work is lost)."""
    installs = _installs()
    if not installs:
        raise RuntimeError(f"no {A.title} installation found in the standard folders")
    want = None
    if version:
        want = [i for i in installs if _major(i["version"]) == _major(version)]
        if not want:
            raise RuntimeError(f"{A.title} {version} is not installed. Installed: {[i['version'] for i in installs]}")
    target = (want or installs[-1:])[-1] if not want else want[0]
    try:
        running = A.sap().GetVersion()[0]
    except Exception:
        running = None
    if running:
        if _major(running.split(".")[0]) == target["major"] or not version:
            return {"already_running": True, "version": running}
        raise RuntimeError(f"{A.title} {running} is already running; close it before launching {version}.")
    subprocess.Popen([target["exe"]], cwd=os.path.dirname(target["exe"]),
                     creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    deadline = time.time() + max(10, min(wait_seconds, 280))
    last = None
    from mcpkit import winutil
    while time.time() < deadline:
        time.sleep(3)
        lic = winutil.license_problem(_EXE[A.prog])
        if lic:
            raise RuntimeError(f"{A.title} {target['version']} shows a license problem and cannot be used: \"{lic[:300]}\". "
                               f"Fix the license (or use another installed version); the dialog is still open in the program.")
        try:
            v = A.sap().GetVersion()[0]
            time.sleep(12)   # the API answers before the UI is fully ready
            return {"launched": target["exe"], "version": v}
        except Exception as e:  # noqa
            last = e
    raise RuntimeError(f"started {target['exe']} but its API did not answer within {wait_seconds}s "
                       f"(license dialog or slow start?): {core.friendly(last)}")


def _new_model(m, units_code, create, what, attempts=15):
    """InitializeNewModel + create(), retrying while the program is still starting up (its API answers before its UI
    is ready, which makes these calls fail with return code 1 / 'invalid pointer' on some versions)."""
    last = None
    for _ in range(attempts):
        A.ensure_visible()
        try:
            r = m.InitializeNewModel(units_code)
            if r == 0:
                r2 = create()
                r2 = r2[-1] if isinstance(r2, (tuple, list)) else r2
                if r2 == 0:
                    A.mark(m)
                    return
                last = f"{what} returned {r2}"
            else:
                last = f"InitializeNewModel returned {r}"
        except Exception as e:  # noqa
            last = core.friendly(e)
        time.sleep(3)
    raise RuntimeError(f"{A.title} would not start a new model after {attempts} attempts ({last}). "
                       f"Is a dialog open in the program?")