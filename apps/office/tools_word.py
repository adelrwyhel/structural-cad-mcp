"""Word tools. Indexes are 1-based (as in Word)."""
from mcpkit import core
from mcpkit.core import GuardError, safe_path, tool

from .adapter import A

IMG = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".emf", ".tif", ".tiff")


@tool()
def read_text(offset: int = 0, limit: int = 100) -> dict:
    """Paragraphs of the active document (text, style, outline level), paginated."""
    ps = A.doc().Paragraphs
    n = ps.Count
    items = []
    for i in range(offset + 1, min(n, offset + limit) + 1):
        p = ps.Item(i)
        items.append({"index": i, "text": p.Range.Text.rstrip("\r\x07"), "style": str(p.Style.NameLocal)})
    return {"total": n, "offset": offset, "items": items}


@tool()
def outline() -> list:
    """Headings (Heading 1-9 / outline levels) with their paragraph index."""
    ps = A.doc().Paragraphs
    out = []
    for i in range(1, ps.Count + 1):
        p = ps.Item(i)
        lvl = p.OutlineLevel
        if 1 <= lvl <= 9:
            out.append({"index": i, "level": lvl, "text": p.Range.Text.rstrip("\r\x07")})
    return out


@tool()
def list_tables() -> list:
    """Tables with size and first cell text."""
    ts = A.doc().Tables
    return [{"index": i, "rows": ts.Item(i).Rows.Count, "columns": ts.Item(i).Columns.Count,
             "first_cell": ts.Item(i).Cell(1, 1).Range.Text.rstrip("\r\x07")} for i in range(1, ts.Count + 1)]


@tool()
def read_table(index: int, max_rows: int = 200) -> dict:
    """Read a table as a 2D list of strings."""
    t = A.doc().Tables.Item(index)
    rows = []
    for r in range(1, min(t.Rows.Count, max_rows) + 1):
        rows.append([t.Cell(r, c).Range.Text.rstrip("\r\x07") for c in range(1, t.Columns.Count + 1)])
    return {"index": index, "total_rows": t.Rows.Count, "rows": rows}


@tool(write=True)
def add_paragraph(text: str, style: str = "Normal") -> str:
    """Append a paragraph at the end of the document."""
    d = A.doc()
    r = d.Content
    r.InsertParagraphAfter()
    r = d.Paragraphs.Item(d.Paragraphs.Count).Range
    r.Text = text
    r.Style = style
    return "ok"


@tool(write=True)
def add_heading(text: str, level: int = 1) -> str:
    """Append a heading (level 1-9)."""
    if not 1 <= level <= 9:
        raise RuntimeError("level must be 1-9")
    d = A.doc()
    d.Content.InsertParagraphAfter()
    r = d.Paragraphs.Item(d.Paragraphs.Count).Range
    r.Text = text
    r.Style = f"Heading {level}"
    return "ok"


@tool(write=True)
def add_table(rows: list, style: str = "Table Grid", header: bool = True) -> str:
    """Append a table from a 2D list of values."""
    if not rows or not isinstance(rows[0], list):
        raise RuntimeError("rows must be a 2D list")
    d = A.doc()
    d.Content.InsertParagraphAfter()
    rng = d.Paragraphs.Item(d.Paragraphs.Count).Range
    w = max(len(r) for r in rows)
    t = d.Tables.Add(rng, len(rows), w)
    try:
        t.Style = style
    except Exception:
        pass
    for i, r in enumerate(rows, 1):
        for j in range(w):
            t.Cell(i, j + 1).Range.Text = str(r[j]) if j < len(r) and r[j] is not None else ""
    if header:
        t.Rows.Item(1).Range.Font.Bold = True
    return f"table {d.Tables.Count}"


@tool(write=True)
def find_replace(find: str, replace: str, match_case: bool = False) -> str:
    """Replace all occurrences of text."""
    f = A.doc().Content.Find
    f.ClearFormatting()
    f.Replacement.ClearFormatting()
    ok = f.Execute(find, match_case, False, False, False, False, True, 1, False, replace, 2)
    return "replaced" if ok else "not found"


@tool(write=True)
def insert_picture(path: str, width_cm: float = 12.0) -> str:
    """Append a picture (png/jpg/...) at the end of the document."""
    p = safe_path(path, IMG, must_exist=True)
    d = A.doc()
    d.Content.InsertParagraphAfter()
    r = d.Paragraphs.Item(d.Paragraphs.Count).Range
    pic = d.InlineShapes.AddPicture(p, False, True, r)
    ratio = pic.Height / pic.Width
    pic.Width = width_cm * 28.35
    pic.Height = pic.Width * ratio
    return "ok"


@tool(write=True)
def add_page_break() -> str:
    """Append a page break."""
    d = A.doc()
    d.Content.InsertParagraphAfter()
    d.Paragraphs.Item(d.Paragraphs.Count).Range.InsertBreak(7)
    return "ok"
