"""Read-only drawing queries."""
import math

import pythoncom
from win32com.client import VARIANT

from mcpkit.core import tool

from .adapter import A, pt

PROPS = ("StartPoint", "EndPoint", "Center", "Radius", "Length", "Area", "TextString", "InsertionPoint", "Closed",
         "Coordinates", "Name", "Height", "StartAngle", "EndAngle", "Rotation", "XScaleFactor", "YScaleFactor",
         "Measurement", "Linetype", "Lineweight")


def _info(e):
    d = {"handle": e.Handle, "type": e.ObjectName, "layer": e.Layer}
    try:
        d["color"] = e.color
    except Exception:
        pass
    return d


@tool()
def entity_counts() -> dict:
    """Count of model-space entities by type."""
    ms = A.doc().ModelSpace
    counts = {}
    for i in range(ms.Count):
        t = ms.Item(i).ObjectName
        counts[t] = counts.get(t, 0) + 1
    return counts


@tool()
def layer_summary() -> dict:
    """Entity count per layer (model space)."""
    ms = A.doc().ModelSpace
    counts = {}
    for i in range(ms.Count):
        l = ms.Item(i).Layer
        counts[l] = counts.get(l, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


@tool()
def list_entities(layer: str = "", entity_type: str = "", offset: int = 0, limit: int = 200) -> dict:
    """List model-space entities filtered by layer and/or type (e.g. 'AcDbLine', 'AcDbPolyline', 'AcDbText'), paginated."""
    ms = A.doc().ModelSpace
    items, seen = [], 0
    for i in range(ms.Count):
        e = ms.Item(i)
        if layer and e.Layer != layer:
            continue
        if entity_type and e.ObjectName != entity_type:
            continue
        seen += 1
        if seen > offset and len(items) < limit:
            items.append(_info(e))
        if len(items) >= limit and seen >= offset + limit + 1000:
            break
    return {"matched_at_least": seen, "offset": offset, "items": items}


@tool()
def get_entity(handle: str) -> dict:
    """Geometry/properties of an entity by handle."""
    e = A.entity(handle)
    d = _info(e)
    for prop in PROPS:
        try:
            v = getattr(e, prop)
            d[prop] = list(v) if isinstance(v, tuple) else v
        except Exception:
            pass
    return d


@tool()
def get_text_content(layer: str = "", limit: int = 500) -> list:
    """All TEXT and MTEXT strings in model space with position and layer."""
    ms = A.doc().ModelSpace
    out = []
    for i in range(ms.Count):
        e = ms.Item(i)
        if e.ObjectName in ("AcDbText", "AcDbMText") and (not layer or e.Layer == layer):
            t = A.typed(e)
            out.append({"handle": t.Handle, "text": t.TextString, "layer": t.Layer, "at": list(t.InsertionPoint)})
            if len(out) >= limit:
                break
    return out


def _bbox(e):
    try:
        lo, hi = e.GetBoundingBox()
        return list(lo), list(hi)
    except Exception:
        return None


@tool()
def drawing_extents() -> dict:
    """Model-space extents computed from entity bounding boxes (independent of the current view) and size."""
    ms = A.doc().ModelSpace
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    n = 0
    for i in range(ms.Count):
        b = _bbox(ms.Item(i))
        if b:
            n += 1
            for k in range(3):
                lo[k], hi[k] = min(lo[k], b[0][k]), max(hi[k], b[1][k])
    if not n:
        return {"entities": 0, "note": "model space is empty"}
    return {"entities": n, "min": lo, "max": hi, "width": hi[0] - lo[0], "height": hi[1] - lo[1]}

@tool()
def measure_layer(layer: str) -> dict:
    """Total length of lines/arcs/polylines/circles and total area of closed polylines/circles on a layer."""
    ms = A.doc().ModelSpace
    length = area = 0.0
    n = 0
    for i in range(ms.Count):
        e = ms.Item(i)
        if e.Layer != layer:
            continue
        t = A.typed(e)
        try:
            if e.ObjectName in ("AcDbLine", "AcDbArc", "AcDbPolyline", "AcDb2dPolyline", "AcDbSpline"):
                length += float(t.Length)
                n += 1
            if e.ObjectName == "AcDbCircle":
                length += 2 * math.pi * float(t.Radius)
                area += math.pi * float(t.Radius) ** 2
                n += 1
            if e.ObjectName == "AcDbPolyline" and t.Closed:
                area += abs(float(t.Area))
        except Exception:
            continue
    return {"layer": layer, "entities_measured": n, "total_length": length, "total_area_closed": area}


@tool()
def entities_in_window(x1: float, y1: float, x2: float, y2: float, limit: int = 500) -> dict:
    """Entities whose bounding box lies fully inside the rectangular window."""
    xa, xb = sorted((x1, x2))
    ya, yb = sorted((y1, y2))
    ms = A.doc().ModelSpace
    items, total = [], 0
    for i in range(ms.Count):
        e = ms.Item(i)
        b = _bbox(e)
        if b and b[0][0] >= xa and b[0][1] >= ya and b[1][0] <= xb and b[1][1] <= yb:
            total += 1
            if len(items) < limit:
                items.append(_info(e))
    return {"count": total, "items": items}

@tool()
def list_blocks() -> list:
    """User-defined block definitions (name and number of entities)."""
    bl = A.doc().Blocks
    out = []
    for i in range(bl.Count):
        b = bl.Item(i)
        if not b.Name.startswith("*") and not b.IsXRef and not b.IsLayout:
            out.append({"name": b.Name, "entities": b.Count})
    return out


@tool()
def block_references(name: str, limit: int = 300) -> list:
    """Insertions of a block with position, scale, rotation and attribute values."""
    ms = A.doc().ModelSpace
    out = []
    for i in range(ms.Count):
        e = ms.Item(i)
        if e.ObjectName != "AcDbBlockReference":
            continue
        b = A.typed(e)
        if b.Name != name:
            continue
        rec = {"handle": b.Handle, "layer": b.Layer, "at": list(b.InsertionPoint), "xscale": b.XScaleFactor,
               "yscale": b.YScaleFactor, "rotation_deg": math.degrees(b.Rotation)}
        try:
            if b.HasAttributes:
                rec["attributes"] = {a.TagString: a.TextString for a in b.GetAttributes()}
        except Exception:
            pass
        out.append(rec)
        if len(out) >= limit:
            break
    return out


@tool()
def get_variable(name: str):
    """Read an AutoCAD system variable (read-only), e.g. INSUNITS, LUNITS, DIMSCALE, CLAYER."""
    return A.doc().GetVariable(name)
