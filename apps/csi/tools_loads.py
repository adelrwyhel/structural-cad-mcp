"""Load patterns, combinations and loads on objects."""
import csv
import os

from mcpkit import core
from mcpkit.core import GuardError, export_path, safe_path, tool

from .adapter import A
from .constants import COMBO_TYPES, LOAD_TYPES, MAT_TYPES, UNITS

# ---- loads: cases / patterns / combos

@tool()
def list_load_cases() -> list:
    """Names of all load cases."""
    return list(A.out(A.sap().LoadCases.GetNameList(), "LoadCases.GetNameList")[1])


@tool()
def list_load_patterns() -> list:
    """Names of all load patterns."""
    return list(A.out(A.sap().LoadPatterns.GetNameList(), "LoadPatterns.GetNameList")[1])


@tool()
def list_combinations() -> list:
    """Names of all load combinations."""
    return list(A.out(A.sap().RespCombo.GetNameList(), "RespCombo.GetNameList")[1])


@tool(write=True)
def add_load_pattern(name: str, load_type: str = "Dead", self_weight_mult: float = 0.0) -> str:
    """Add a load pattern. load_type: Dead, SuperDead, Live, Quake, Wind, Snow, Other, ... (also creates its linear case)."""
    if load_type not in LOAD_TYPES:
        raise RuntimeError(f"unknown load_type; use one of {list(LOAD_TYPES)}")
    A.chk(A.sap().LoadPatterns.Add(name, LOAD_TYPES[load_type], self_weight_mult, True), "LoadPatterns.Add")
    return name


@tool(write=True)
def add_combination(name: str, factors: dict, combo_type: str = "Linear") -> str:
    """Add a load combination. factors maps load case/combo names to scale factors, e.g. {'Dead':1.4,'Live':1.7}."""
    m = A.sap()
    cases = set(m.LoadCases.GetNameList()[1])
    combos = set(m.RespCombo.GetNameList()[1])
    if not factors:
        raise RuntimeError("factors is empty")
    lookup = {n.lower(): n for n in list(cases) + list(combos)}   # SAP2000 calls it 'DEAD', ETABS 'Dead'
    resolved = {}
    for k, sf in factors.items():
        if k.lower() not in lookup:
            raise RuntimeError(f"'{k}' is not an existing load case or combination. Existing: {sorted(lookup.values())}")
        resolved[lookup[k.lower()]] = sf
    factors = resolved
    if combo_type not in COMBO_TYPES:
        raise RuntimeError(f"combo_type must be one of {list(COMBO_TYPES)}")
    rc = m.RespCombo
    A.chk(rc.Add(name, COMBO_TYPES[combo_type]), "RespCombo.Add")
    for k, sf in factors.items():
        kind = 0 if k in cases else 1
        A.chk(rc.SetCaseList(name, kind, k, float(sf)), "RespCombo.SetCaseList")
    return name


@tool(write=True)
def delete_combination(name: str) -> str:
    """Delete a load combination."""
    A.chk(A.sap().RespCombo.Delete(name), "RespCombo.Delete")
    return f"deleted {name}"


@tool(write=True)
def set_run_case(name: str, run: bool = True) -> str:
    """Include/exclude one load case in the next analysis run."""
    A.chk(A.sap().Analyze.SetRunCaseFlag(name, run, False), "SetRunCaseFlag")
    return f"{name}: run={run}"



# ---- loads on objects

@tool(write=True)
def point_load(point: str, pattern: str, fx: float = 0, fy: float = 0, fz: float = 0, mx: float = 0, my: float = 0,
               mz: float = 0, replace: bool = False) -> str:
    """Assign a force/moment to a point (global axes, current units)."""
    A.out(A.sap().PointObj.SetLoadForce(point, pattern, [fx, fy, fz, mx, my, mz], replace), "SetLoadForce")
    return "ok"


@tool(write=True)
def frame_uniform_load(frame: str, pattern: str, value: float, direction: int = 6, replace: bool = False) -> str:
    """Uniform load on a frame (force/length). direction 1-3 local, 4-6 global X/Y/Z (6 = global Z; negative = down)."""
    A.out(A.sap().FrameObj.SetLoadDistributed(frame, pattern, 1, direction, 0, 1, value, value, "Global", True, replace),
         "SetLoadDistributed")
    return "ok"


@tool(write=True)
def area_uniform_load(area: str, pattern: str, value: float, direction: int = 6, replace: bool = False) -> str:
    """Uniform load on an area (force/area). direction 6 = global Z (negative = down)."""
    A.out(A.sap().AreaObj.SetLoadUniform(area, pattern, value, direction, replace, "Global"), "SetLoadUniform")
    return "ok"
