"""ETABS-only: stories and diaphragms."""
import csv
import os

from mcpkit import core
from mcpkit.core import GuardError, export_path, safe_path, tool

from .adapter import A
from .constants import COMBO_TYPES, LOAD_TYPES, MAT_TYPES, UNITS

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
