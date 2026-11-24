"""Editing existing entities (write)."""
import math

import pythoncom
from win32com.client import VARIANT

from mcpkit.core import tool

from .adapter import A, pt


@tool(write=True)
def erase_entity(handle: str) -> str:
    """Erase an entity by handle."""
    A.entity(handle).Delete()
    return f"erased {handle}"


@tool(write=True)
def move_entity(handle: str, dx: float, dy: float, dz: float = 0) -> str:
    """Move an entity by a displacement vector."""
    A.entity(handle).Move(pt(0, 0, 0), pt(dx, dy, dz))
    return "moved"


@tool(write=True)
def copy_entity(handle: str, dx: float, dy: float, dz: float = 0) -> str:
    """Copy an entity displaced by a vector. Returns the new handle."""
    c = A.entity(handle).Copy()
    c.Move(pt(0, 0, 0), pt(dx, dy, dz))
    return c.Handle


@tool(write=True)
def rotate_entity(handle: str, base_x: float, base_y: float, angle_deg: float) -> str:
    """Rotate an entity about a base point (counter-clockwise degrees)."""
    A.entity(handle).Rotate(pt(base_x, base_y, 0), math.radians(angle_deg))
    return "rotated"


@tool(write=True)
def scale_entity(handle: str, base_x: float, base_y: float, factor: float) -> str:
    """Scale an entity about a base point."""
    if factor <= 0:
        raise RuntimeError("factor must be > 0")
    A.entity(handle).ScaleEntity(pt(base_x, base_y, 0), float(factor))
    return "scaled"


@tool(write=True)
def mirror_entity(handle: str, x1: float, y1: float, x2: float, y2: float) -> str:
    """Mirror a copy of an entity about the line through two points. Returns the new handle."""
    return A.entity(handle).Mirror(pt(x1, y1, 0), pt(x2, y2, 0)).Handle


@tool(write=True)
def offset_entity(handle: str, distance: float) -> list:
    """Offset a curve by a distance. Returns the new handles."""
    res = A.entity(handle).Offset(float(distance))
    return [r.Handle for r in res]


@tool(write=True)
def set_entity_layer(handle: str, layer: str) -> str:
    """Move an entity to another (existing) layer."""
    A.doc().Layers.Item(layer)  # raises if the layer does not exist
    A.entity(handle).Layer = layer
    return "ok"


@tool(write=True)
def set_entity_color(handle: str, color: int) -> str:
    """Set an entity's color (ACI index; 256 = ByLayer)."""
    A.entity(handle).color = int(color)
    return "ok"


@tool(write=True)
def purge_unused() -> str:
    """Purge unused blocks, layers, linetypes and styles in the active (sandbox) drawing."""
    A.doc().PurgeAll()
    return "purged"
