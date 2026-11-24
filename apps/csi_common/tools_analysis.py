"""Analysis and design."""
import csv
import os

from mcpkit import core
from mcpkit.core import GuardError, export_path, safe_path, tool

from .adapter import A
from .constants import COMBO_TYPES, LOAD_TYPES, MAT_TYPES, UNITS

# ---- analysis & design

@tool(write=True, timeout=3600)
def run_analysis() -> str:
    """Run the analysis (can take long on big models). The model must be saved first: save_model('name')."""
    m = A.sap()
    if not A.filename(m):
        raise RuntimeError("Model has no file name. Call save_model('name') first.")
    A.chk(m.Analyze.RunAnalysis(), "RunAnalysis")
    return "analysis complete"


@tool(write=True, timeout=3600)
def run_design(kind: str = "concrete") -> str:
    """ETABS/SAFE: run concrete or steel design after analysis, then read results with list_tables(contains='Design')."""
    m = A.sap()
    if kind == "concrete":
        d = m.DesignConcrete
    elif kind == "steel" and A.prog == "etabs":
        d = m.DesignSteel
    else:
        raise RuntimeError("kind must be 'concrete' (or 'steel' for ETABS)")
    if not m.GetModelIsLocked():
        raise RuntimeError("Design needs analysis results: run run_analysis first (and do not unlock the model).")
    d.StartDesign()   # its return value is unreliable; check the results flag instead
    if not d.GetResultsAvailable():
        raise RuntimeError(f"{kind} design produced no results. Check design code, combos and that members have "
                           f"design sections; inspect with get_table.")
    return f"{kind} design finished; see list_tables(contains='Design')"


@tool()
def refresh_view() -> str:
    """Refresh the program window."""
    A.chk(A.sap().View.RefreshView(0, False), "RefreshView")
    return "ok"
