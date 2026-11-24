"""ETABS-only tools: stories, diaphragms, drift/story results, walls, seismic-related readers."""
import csv
import os

from mcpkit import core
from mcpkit.core import GuardError, export_path, safe_path, tool

from apps.csi_common.adapter import A
from apps.csi_common.constants import COMBO_TYPES, LOAD_TYPES, MAT_TYPES, UNITS
from apps.csi_common.tools_session import _new_model
from apps.csi_common.tools_tables import _result

# ---- ETABS: stories & diaphragms

@tool(write=True)
def define_stories(names: list, heights: list, base_elevation: float = 0.0) -> dict:
    """ETABS: define the story stack on an EMPTY model (ETABS refuses once objects exist). `names` and `heights` are
    listed from the BOTTOM story up (heights in current units). The top story is the master; the others are similar to it."""
    A.etabs_only("define_stories")
    n = len(names)
    if n == 0 or n != len(heights):
        raise RuntimeError("names and heights must be non-empty and the same length")
    m = A.sap()
    if sum(A.counts(m)) > 0:
        raise RuntimeError("ETABS only allows redefining stories on a model with no objects. Use new_blank_model first, "
                           "or edit the 'Story Definitions' table with set_table.")
    top = names[-1]
    A.chk(m.Story.SetStories_2(float(base_elevation), n, list(names), [float(h) for h in heights],
                               [i == n - 1 for i in range(n)], [top if i < n - 1 else "None" for i in range(n)],
                               [False] * n, [0.0] * n, [0] * n), "Story.SetStories_2")
    cols, rows = A.fetch(m, "Story Definitions", try_select=False)
    return {"stories": [{"story": r_[cols.index("Story")], "height": r_[cols.index("Height")]} for r_ in rows]}

@tool(write=True)
def add_diaphragm(name: str, semi_rigid: bool = False) -> str:
    """ETABS: define a diaphragm constraint."""
    A.etabs_only("add_diaphragm")
    m = A.sap()
    if name in list(m.Diaphragm.GetNameList()[1]):
        return f"{name} already exists"
    A.chk(m.Diaphragm.SetDiaphragm(name, semi_rigid), "Diaphragm.SetDiaphragm")
    return name


@tool(write=True)
def assign_diaphragm_to_story(story: str, diaphragm: str) -> dict:
    """ETABS: assign a diaphragm to every point on a story."""
    A.etabs_only("assign_diaphragm_to_story")
    m = A.sap()
    n = 0
    for p in list(m.PointObj.GetNameList()[1]):
        if m.PointObj.GetLabelFromName(p)[1] == story:
            A.chk(m.PointObj.SetDiaphragm(p, 3, diaphragm), "PointObj.SetDiaphragm")
            n += 1
    return {"assigned_points": n}


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


@tool()
def story_forces(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """ETABS: story forces."""
    A.etabs_only("story_forces")
    return _result("Story Forces", where, max_rows, offset)


@tool()
def drift_check(limit: float = 0.02, case_contains: str = "") -> dict:
    """ETABS: maximum story drift ratio per direction and the stories that exceed `limit` (default 2%)."""
    A.etabs_only("drift_check")
    cols, rows = A.fetch(A.sap(), "Story Drifts")
    ci = {c: i for i, c in enumerate(cols)}
    best, exceed = {}, []
    for r in rows:
        case = r[ci["OutputCase"]]
        if case_contains and case_contains.lower() not in case.lower():
            continue
        d = abs(A.num(r[ci["Drift"]]))
        direction = r[ci["Direction"]]
        rec = {"story": r[ci["Story"]], "case": case, "direction": direction, "drift": d}
        if d > best.get(direction, {}).get("drift", -1):
            best[direction] = rec
        if d > limit:
            exceed.append(rec)
    exceed.sort(key=lambda x: -x["drift"])
    return {"limit": limit, "max_per_direction": best, "exceeding": exceed[:50], "n_exceeding": len(exceed),
            "ok": not exceed}


@tool(write=True)
def add_wall_section(name: str, material: str, thickness: float) -> str:
    """ETABS: define a thin shell wall section."""
    A.etabs_only("add_wall_section")
    A.chk(A.sap().PropArea.SetWall(name, 0, 1, material, thickness), "PropArea.SetWall")
    return name


# ---- more ETABS result readers (table based; UNVERIFIED: not exercised on a model that has these results)
@tool(unverified=True)
def pier_forces(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Shear-wall pier forces (needs piers defined and the model analyzed)."""
    return _result("Pier Forces", where, max_rows, offset)


@tool(unverified=True)
def spandrel_forces(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Spandrel forces (needs spandrels defined and the model analyzed)."""
    return _result("Spandrel Forces", where, max_rows, offset)


@tool(unverified=True)
def joint_drifts(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Joint drifts."""
    return _result("Joint Drifts", where, max_rows, offset)


@tool(unverified=True)
def center_of_mass_and_rigidity(where: dict = None, max_rows: int = 100, offset: int = 0) -> dict:
    """Story centers of mass and rigidity."""
    return _result("Centers of Mass and Rigidity", where, max_rows, offset)


@tool(unverified=True)
def story_stiffness(where: dict = None, max_rows: int = 100, offset: int = 0) -> dict:
    """Story stiffness / soft-story check data (Story Stiffness table)."""
    return _result("Story Stiffness", where, max_rows, offset)


@tool(unverified=True)
def mass_summary(where: dict = None, max_rows: int = 100, offset: int = 0) -> dict:
    """Assembled mass by story (Mass Summary by Story)."""
    return _result("Mass Summary by Story", where, max_rows, offset)
