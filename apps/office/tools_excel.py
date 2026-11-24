"""Excel tools."""
from mcpkit.core import tool

from .adapter import A

CHART_TYPES = {"column": 51, "bar": 57, "line": 4, "line_markers": 65, "pie": 5, "scatter": 74, "area": 1}


def _ws(sheet):
    wb = A.doc()
    if not sheet:
        return wb.ActiveSheet
    try:
        return wb.Worksheets.Item(sheet)
    except Exception:
        raise RuntimeError(f"no sheet named '{sheet}'. Sheets: {[wb.Worksheets.Item(i).Name for i in range(1, wb.Worksheets.Count + 1)]}")


def _grid(v):
    if v is None:
        return [[None]]
    if not isinstance(v, tuple):
        return [[v]]
    return [list(r) if isinstance(r, tuple) else [r] for r in v]


@tool()
def list_sheets() -> list:
    """Sheets of the active workbook with used range."""
    wb = A.doc()
    return [{"name": wb.Worksheets.Item(i).Name, "used_range": wb.Worksheets.Item(i).UsedRange.Address(False, False),
             "visible": wb.Worksheets.Item(i).Visible == -1} for i in range(1, wb.Worksheets.Count + 1)]


@tool()
def read_range(range_address: str, sheet: str = "", formulas: bool = False, max_cells: int = 20000) -> dict:
    """Read a range such as 'A1:F40' (values, or formulas with formulas=True). Empty range_address = used range."""
    ws = _ws(sheet)
    rng = ws.Range(range_address) if range_address else ws.UsedRange
    if rng.Count > max_cells:
        raise RuntimeError(f"{rng.Count} cells requested (max {max_cells}); read a smaller range")
    v = rng.Formula if formulas else rng.Value
    rows = _grid(v)
    return {"sheet": ws.Name, "range": rng.Address(False, False), "rows": rows, "total_rows": len(rows)}


@tool()
def read_table(sheet: str = "", header_row: int = 1, max_rows: int = 500) -> dict:
    """Read the used range as records using `header_row` as column names."""
    ws = _ws(sheet)
    ur = ws.UsedRange
    grid = _grid(ur.Value)
    first = ur.Row
    hi = header_row - first
    if hi < 0 or hi >= len(grid):
        raise RuntimeError("header_row is outside the used range")
    cols = [str(c) if c not in (None, "") else f"col{i + 1}" for i, c in enumerate(grid[hi])]
    recs = [dict(zip(cols, r)) for r in grid[hi + 1:hi + 1 + max_rows]]
    return {"sheet": ws.Name, "columns": cols, "total_records": len(grid) - hi - 1, "records": recs}


@tool()
def find_value(text: str, sheet: str = "", limit: int = 50) -> list:
    """Find cells containing text (whole workbook if sheet is empty)."""
    wb = A.doc()
    sheets = [_ws(sheet)] if sheet else [wb.Worksheets.Item(i) for i in range(1, wb.Worksheets.Count + 1)]
    out = []
    for ws in sheets:
        first = ws.UsedRange.Find(text)
        if first is None:
            continue
        addr0, c = first.Address, first
        while c is not None and len(out) < limit:
            out.append({"sheet": ws.Name, "cell": c.Address(False, False), "value": c.Value})
            c = ws.UsedRange.FindNext(c)
            if c is None or c.Address == addr0:
                break
    return out


@tool()
def list_named_ranges() -> list:
    """Defined names in the active workbook."""
    names = A.doc().Names
    return [{"name": names.Item(i).Name, "refers_to": names.Item(i).RefersTo} for i in range(1, names.Count + 1)]


@tool(write=True)
def write_range(top_left: str, values: list, sheet: str = "") -> dict:
    """Write a 2D list of values starting at top_left (e.g. 'A1'). Strings starting with '=' become formulas."""
    if not values or not isinstance(values[0], list):
        raise RuntimeError("values must be a 2D list: [[row1...], [row2...]]")
    ws = _ws(sheet)
    w = max(len(r) for r in values)
    grid = tuple(tuple((r[i] if i < len(r) else None) for i in range(w)) for r in values)
    rng = ws.Range(top_left).Resize(len(values), w)
    rng.Formula = grid
    return {"sheet": ws.Name, "written": rng.Address(False, False)}


@tool(write=True)
def set_formula(cell: str, formula: str, sheet: str = "") -> str:
    """Set one cell's formula, e.g. '=SUM(B2:B20)'."""
    _ws(sheet).Range(cell).Formula = formula
    return "ok"


@tool(write=True)
def clear_range(range_address: str, sheet: str = "", contents_only: bool = True) -> str:
    """Clear a range (contents only by default; keeps formatting)."""
    r = _ws(sheet).Range(range_address)
    r.ClearContents() if contents_only else r.Clear()
    return "cleared"


@tool(write=True)
def add_sheet(name: str) -> str:
    """Add a worksheet at the end."""
    wb = A.doc()
    ws = wb.Worksheets.Add(None, wb.Worksheets.Item(wb.Worksheets.Count))
    ws.Name = name
    return ws.Name


@tool(write=True)
def rename_sheet(old: str, new: str) -> str:
    """Rename a worksheet."""
    _ws(old).Name = new
    return new


@tool(write=True)
def delete_sheet(name: str) -> str:
    """Delete a worksheet (the last remaining sheet cannot be deleted)."""
    wb = A.doc()
    if wb.Worksheets.Count == 1:
        raise RuntimeError("cannot delete the only sheet")
    app = A.app()
    prev = app.DisplayAlerts
    app.DisplayAlerts = False
    try:
        _ws(name).Delete()
    finally:
        app.DisplayAlerts = prev
    return f"deleted {name}"


@tool(write=True)
def format_range(range_address: str, sheet: str = "", bold: bool = None, number_format: str = "",
                 fill_rgb: list = None, font_rgb: list = None, autofit: bool = False, borders: bool = False) -> str:
    """Basic formatting. fill_rgb/font_rgb = [r, g, b]; number_format e.g. '0.00', '#,##0', '0.0%'."""
    r = _ws(sheet).Range(range_address)
    if bold is not None:
        r.Font.Bold = bold
    if number_format:
        r.NumberFormat = number_format
    if fill_rgb:
        r.Interior.Color = fill_rgb[0] + fill_rgb[1] * 256 + fill_rgb[2] * 65536
    if font_rgb:
        r.Font.Color = font_rgb[0] + font_rgb[1] * 256 + font_rgb[2] * 65536
    if borders:
        r.Borders.LineStyle = 1
    if autofit:
        r.Columns.AutoFit()
    return "ok"


@tool(write=True)
def add_chart(data_range: str, chart_type: str = "column", title: str = "", sheet: str = "", at_cell: str = "H2") -> str:
    """Add a chart from a range (first row/column used as labels). chart_type: column, bar, line, line_markers, pie, scatter, area."""
    if chart_type not in CHART_TYPES:
        raise RuntimeError(f"chart_type must be one of {list(CHART_TYPES)}")
    ws = _ws(sheet)
    top = ws.Range(at_cell)
    co = ws.ChartObjects().Add(top.Left, top.Top, 420, 260)
    co.Chart.SetSourceData(ws.Range(data_range))
    co.Chart.ChartType = CHART_TYPES[chart_type]
    if title:
        co.Chart.HasTitle = True
        co.Chart.ChartTitle.Text = title
    return co.Name


@tool(write=True, timeout=300)
def recalculate() -> str:
    """Force a full recalculation."""
    A.app().CalculateFull()
    return "recalculated"
