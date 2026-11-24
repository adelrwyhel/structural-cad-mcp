"""PowerPoint tools. Slide indexes are 1-based (as in PowerPoint)."""
from mcpkit.core import safe_path, tool

from .adapter import A

IMG = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".emf", ".tif", ".tiff")


def _text_of(slide):
    out = []
    for i in range(1, slide.Shapes.Count + 1):
        sh = slide.Shapes.Item(i)
        if sh.HasTextFrame and sh.TextFrame.HasText:
            out.append({"shape": sh.Name, "text": sh.TextFrame.TextRange.Text})
    return out


@tool()
def list_slides() -> list:
    """Slides with index, layout and title."""
    sl = A.doc().Slides
    out = []
    for i in range(1, sl.Count + 1):
        s = sl.Item(i)
        title = s.Shapes.Title.TextFrame.TextRange.Text if s.Shapes.HasTitle else ""
        out.append({"index": i, "title": title, "shapes": s.Shapes.Count})
    return out


@tool()
def read_slide(index: int) -> dict:
    """All text on a slide plus speaker notes."""
    s = A.doc().Slides.Item(index)
    notes = ""
    try:
        notes = s.NotesPage.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text
    except Exception:
        pass
    return {"index": index, "text": _text_of(s), "notes": notes}


@tool(write=True)
def add_slide(title: str, body: str = "", layout: int = 2) -> int:
    """Append a slide (layout 1 = title, 2 = title + content, 12 = blank). Returns its index."""
    d = A.doc()
    s = d.Slides.Add(d.Slides.Count + 1, layout)
    if s.Shapes.HasTitle:
        s.Shapes.Title.TextFrame.TextRange.Text = title
    if body and s.Shapes.Count >= 2:
        s.Shapes.Item(2).TextFrame.TextRange.Text = body
    return s.SlideIndex


@tool(write=True)
def set_shape_text(index: int, shape: str, text: str) -> str:
    """Set the text of a named shape on a slide (names from read_slide)."""
    A.doc().Slides.Item(index).Shapes.Item(shape).TextFrame.TextRange.Text = text
    return "ok"


@tool(write=True)
def add_picture(index: int, path: str, left: float = 50, top: float = 120, width: float = 400) -> str:
    """Place a picture on a slide (points)."""
    p = safe_path(path, IMG, must_exist=True)
    A.doc().Slides.Item(index).Shapes.AddPicture(p, False, True, left, top, width, -1)
    return "ok"


@tool(write=True)
def add_notes(index: int, text: str) -> str:
    """Set speaker notes of a slide."""
    A.doc().Slides.Item(index).NotesPage.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text = text
    return "ok"


@tool(write=True)
def delete_slide(index: int) -> str:
    """Delete a slide."""
    A.doc().Slides.Item(index).Delete()
    return f"deleted slide {index}"
