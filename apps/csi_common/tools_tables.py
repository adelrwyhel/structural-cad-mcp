"""Database tables and result readers."""
import csv
import os

from mcpkit import core
from mcpkit.core import GuardError, export_path, safe_path, tool

from .adapter import A
from .constants import COMBO_TYPES, LOAD_TYPES, MAT_TYPES, UNITS

# ---- tables & generic results

@tool()
def list_tables(contains: str = "") -> list:
    """Database table keys (optionally filtered by text), e.g. contains='Drift' or 'Design'."""
    m = A.sap()
    if not A.has_tables(m):
        if A.legacy_keys:
            return [k for k in A.legacy_keys if not contains or contains.lower() in k.lower()]
        raise RuntimeError(f"{A.title} {m.GetVersion()[0]} has no database-tables API.")
    r = A.out(m.DatabaseTables.GetAvailableTables(), "GetAvailableTables")
    c = contains.lower()
    return [k for k in r[1] if not c or c in k.lower()]


@tool()
def get_table(table_key: str, where: dict = None, columns: list = None, offset: int = 0, max_rows: int = 200,
              group: str = "All") -> dict:
    """Fetch a database table. where={'OutputCase':'Dead','Story':['Story1','Story2']} filters rows; columns picks
    columns; offset/max_rows paginate. Result tables need an analyzed model."""
    cols, rows = A.fetch(A.sap(), table_key, group)
    if where:
        idx = {c: cols.index(c) for c in where if c in cols}
        missing = [c for c in where if c not in cols]
        if missing:
            raise RuntimeError(f"unknown column(s) {missing}; columns are {cols}")
        want = {c: (set(map(str, v)) if isinstance(v, (list, tuple)) else {str(v)}) for c, v in where.items()}
        rows = [r for r in rows if all(r[idx[c]] in want[c] for c in idx)]
    if columns:
        bad = [c for c in columns if c not in cols]
        if bad:
            raise RuntimeError(f"unknown column(s) {bad}; columns are {cols}")
        ix = [cols.index(c) for c in columns]
        cols, rows = columns, [[r[i] for i in ix] for r in rows]
    total = len(rows)
    return {"columns": cols, "total_rows": total, "offset": offset, "rows": rows[offset:offset + max_rows]}


@tool(timeout=300)
def export_table_csv(table_key: str, filename: str = "") -> str:
    """Write a whole table to exports/<name>.csv (no row limit). Returns the file path."""
    cols, rows = A.fetch(A.sap(), table_key)
    p = export_path(filename or table_key, ".csv")
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return f"{p} ({len(rows)} rows)"


@tool(write=True, timeout=300)
def set_table(table_key: str, columns: list, rows: list) -> dict:
    """Edit/add records in a database table (the generic way to set anything: stories, grids, mass source, seismic
    parameters, response-spectrum functions...). `rows` is a list of lists of strings matching `columns`.
    Use get_table first to see the exact column keys. Applies the edit and returns the import log."""
    m = A.sap()
    if not A.has_tables(m):
        raise RuntimeError(f"{A.title} {m.GetVersion()[0]} has no database-tables API, so tables cannot be edited.")
    dt = m.DatabaseTables
    flat = [str(v) for r in rows for v in r]
    if any(len(r) != len(columns) for r in rows):
        raise RuntimeError("every row must have the same number of values as `columns`")
    r = dt.SetTableForEditingArray(table_key, 0, columns, len(rows), flat)
    A.chk(r[-1] if isinstance(r, (tuple, list)) else r, "SetTableForEditingArray")
    a = dt.ApplyEditedTables(True, 0, 0, 0, 0, "")
    fatal, errs, warns, infos, log = a[0], a[1], a[2], a[3], a[4]
    if fatal or errs:
        try:
            dt.CancelTableEditing()
        except Exception:
            pass
        raise RuntimeError(f"table edit rejected: {fatal} fatal, {errs} errors. Log: {str(log)[:1500]}")
    return {"applied": True, "warnings": warns, "log": str(log)[:1500]}


# convenience result tables ------------------------------------------------------------------

def _result(key, where, max_rows, offset):
    cols, rows = A.fetch(A.sap(), key)
    if where:
        for c, v in where.items():
            if c not in cols:
                raise RuntimeError(f"unknown column '{c}'; columns are {cols}")
            i = cols.index(c)
            want = set(map(str, v)) if isinstance(v, (list, tuple)) else {str(v)}
            rows = [r for r in rows if r[i] in want]
    return {"columns": cols, "total_rows": len(rows), "offset": offset, "rows": rows[offset:offset + max_rows]}


@tool()
def joint_reactions(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Joint reactions. where e.g. {'OutputCase': 'Dead'}."""
    return _result("Joint Reactions", where, max_rows, offset)


@tool()
def joint_displacements(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Joint displacements."""
    return _result("Joint Displacements", where, max_rows, offset)


@tool()
def base_reactions(where: dict = None, max_rows: int = 100, offset: int = 0) -> dict:
    """Base reactions."""
    return _result("Base Reactions", where, max_rows, offset)


@tool()
def frame_forces(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Frame/beam/column forces (ETABS: columns table; use get_table for 'Element Forces - Beams')."""
    key = {"etabs": "Element Forces - Columns", "sap2000": "Element Forces - Frames"}.get(A.prog)
    if not key:
        raise RuntimeError("SAFE: use list_tables(contains='Force') and get_table.")
    return _result(key, where, max_rows, offset)


@tool()
def modal_summary(max_modes: int = 12) -> dict:
    """Periods of the first modes and the mode at which 90% mass participation is reached (ETABS/SAP2000)."""
    if A.prog == "safe":
        raise RuntimeError("SAFE has no modal analysis.")
    m = A.sap()
    try:
        cols, rows = A.fetch(m, "Modal Participating Mass Ratios")
    except Exception:
        cols, rows = A.fetch(m, "Modal Periods And Frequencies")
    ci = {c: i for i, c in enumerate(cols)}
    per_key = "Period"
    modes = []
    reach = {}
    for r in rows:
        mode = {"mode": r[ci["Mode"]] if "Mode" in ci else r[ci.get("StepNum", 0)], "period_s": A.num(r[ci[per_key]])}
        for k in ("UX", "UY", "RZ", "SumUX", "SumUY", "SumRZ"):
            if k in ci:
                mode[k] = A.num(r[ci[k]])
        modes.append(mode)
        for s in ("SumUX", "SumUY"):
            if s in mode and mode[s] >= 0.9 and s not in reach:
                reach[s] = mode["mode"]
    return {"modes": modes[:max_modes], "total_modes": len(modes), "mode_reaching_90pct": reach}


@tool(timeout=300)
def export_report(filename: str = "report") -> str:
    """Write a Markdown report (summary, modal, base reactions, drifts when available) to exports/."""
    m = A.sap()
    lines = [f"# {A.title} model report", "", f"File: `{A.filename(m) or '(untitled)'}`", ""]

    def table(title, key, maxr=40):
        try:
            cols, rows = A.fetch(m, key)
        except Exception as e:
            lines.extend([f"## {title}", f"_not available: {str(e)[:80]}_", ""])
            return
        lines.extend([f"## {title}", "| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)])
        lines.extend("| " + " | ".join(str(x) for x in r) + " |" for r in rows[:maxr])
        if len(rows) > maxr:
            lines.append(f"\n_{len(rows) - maxr} more rows omitted_")
        lines.append("")

    p, f, a = A.counts(m)
    lines.extend([f"Objects: {p} points, {f} frames, {a} areas", ""])
    if A.prog == "etabs":
        table("Stories", "Story Definitions")
    if A.prog != "safe":
        table("Modal periods", "Modal Periods And Frequencies" if A.prog == "sap2000" else "Modal Participating Mass Ratios", 20)
    table("Base reactions", "Base Reactions", 30)
    if A.prog == "etabs":
        table("Story drifts", "Story Drifts", 60)
    p = export_path(filename, ".md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return p
