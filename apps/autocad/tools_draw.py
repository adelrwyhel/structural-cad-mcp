"""Drawing tools (write)."""
import math

import pythoncom
from win32com.client import VARIANT

from mcpkit.core import tool

from .adapter import A, arr, pt


def _place(e, layer):
    if layer:
        e.Layer = layer
    return e.Handle


@tool(write=True)
def add_line(x1: float, y1: float, x2: float, y2: float, z1: float = 0, z2: float = 0, layer: str = "") -> str:
    """Draw a line. Returns the entity handle."""
    return _place(A.doc().ModelSpace.AddLine(pt(x1, y1, z1), pt(x2, y2, z2)), layer)


@tool(write=True)
def add_polyline(points: list, closed: bool = False, layer: str = "") -> str:
    """Draw a lightweight polyline from [[x, y], ...] points."""
    if len(points) < 2:
        raise RuntimeError("a polyline needs at least 2 points")
    flat = [c for p in points for c in (float(p[0]), float(p[1]))]
    e = A.doc().ModelSpace.AddLightWeightPolyline(arr(flat))
    e.Closed = closed
    return _place(e, layer)


@tool(write=True)
def add_rectangle(x1: float, y1: float, x2: float, y2: float, layer: str = "") -> str:
    """Draw a closed rectangle polyline from two opposite corners."""
    flat = [x1, y1, x2, y1, x2, y2, x1, y2]
    e = A.doc().ModelSpace.AddLightWeightPolyline(arr(flat))
    e.Closed = True
    return _place(e, layer)


@tool(write=True)
def add_circle(cx: float, cy: float, radius: float, layer: str = "") -> str:
    """Draw a circle."""
    return _place(A.doc().ModelSpace.AddCircle(pt(cx, cy, 0), float(radius)), layer)


@tool(write=True)
def add_arc(cx: float, cy: float, radius: float, start_deg: float, end_deg: float, layer: str = "") -> str:
    """Draw a counter-clockwise arc (angles in degrees)."""
    return _place(A.doc().ModelSpace.AddArc(pt(cx, cy, 0), float(radius), math.radians(start_deg),
                                            math.radians(end_deg)), layer)


@tool(write=True)
def add_text(x: float, y: float, text: str, height: float = 2.5, rotation_deg: float = 0, layer: str = "") -> str:
    """Add single-line text."""
    e = A.doc().ModelSpace.AddText(text, pt(x, y, 0), float(height))
    e.Rotation = math.radians(rotation_deg)
    return _place(e, layer)


@tool(write=True)
def add_mtext(x: float, y: float, width: float, text: str, height: float = 2.5, layer: str = "") -> str:
    """Add multi-line text in a box of the given width."""
    e = A.doc().ModelSpace.AddMText(pt(x, y, 0), float(width), text)
    e.Height = float(height)
    return _place(e, layer)


@tool(write=True)
def add_linear_dimension(x1: float, y1: float, x2: float, y2: float, offset_x: float, offset_y: float,
                         layer: str = "") -> str:
    """Add an aligned dimension between two points; offset_x/y places the dimension line."""
    return _place(A.doc().ModelSpace.AddDimAligned(pt(x1, y1, 0), pt(x2, y2, 0), pt(offset_x, offset_y, 0)), layer)


@tool(write=True)
def add_hatch(points: list, pattern: str = "SOLID", layer: str = "") -> str:
    """Hatch a closed region given by [[x, y], ...] corner points (patterns: SOLID, ANSI31, ANSI37, ...)."""
    flat = [c for p in points for c in (float(p[0]), float(p[1]))]
    ms = A.doc().ModelSpace
    boundary = ms.AddLightWeightPolyline(arr(flat))
    boundary.Closed = True
    h = ms.AddHatch(0, pattern, True)
    h.AppendOuterLoop(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, [boundary]))
    h.Evaluate()
    if layer:
        h.Layer = layer
        boundary.Layer = layer
    return h.Handle


@tool(write=True)
def insert_block(name: str, x: float, y: float, scale: float = 1.0, rotation_deg: float = 0, layer: str = "") -> str:
    """Insert an existing block definition at a point."""
    e = A.doc().ModelSpace.InsertBlock(pt(x, y, 0), name, scale, scale, scale, math.radians(rotation_deg))
    return _place(e, layer)
