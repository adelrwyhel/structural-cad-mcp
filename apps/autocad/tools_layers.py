"""Layers."""
from mcpkit.core import tool

from .adapter import A


@tool()
def list_layers() -> list:
    """All layers with color, on/frozen/locked state."""
    layers = A.doc().Layers
    return [{"name": l.Name, "color": l.color, "on": l.LayerOn, "frozen": l.Freeze, "locked": l.Lock,
             "linetype": l.Linetype} for l in (layers.Item(i) for i in range(layers.Count))]


@tool(write=True)
def add_layer(name: str, color: int = 7) -> str:
    """Create a layer (color = ACI index 1-255)."""
    if name.startswith("__MCP"):
        raise RuntimeError("layer names starting with '__MCP' are reserved")
    layer = A.doc().Layers.Add(name)
    layer.color = int(color)
    return layer.Name


@tool(write=True)
def set_current_layer(name: str) -> str:
    """Make a layer current."""
    d = A.doc()
    d.ActiveLayer = d.Layers.Item(name)
    return name


@tool(write=True)
def set_layer_state(name: str, on: bool = True, frozen: bool = False, locked: bool = False) -> str:
    """Set on/off, frozen and locked state of a layer."""
    l = A.doc().Layers.Item(name)
    l.LayerOn, l.Freeze, l.Lock = on, frozen, locked
    return f"{name}: on={on} frozen={frozen} locked={locked}"


@tool(write=True)
def rename_layer(old: str, new: str) -> str:
    """Rename a layer."""
    if old == "0":
        raise RuntimeError("layer 0 cannot be renamed")
    A.doc().Layers.Item(old).Name = new
    return new


@tool(write=True)
def delete_layer(name: str) -> str:
    """Delete an EMPTY, non-current layer (AutoCAD refuses otherwise)."""
    if name == "0":
        raise RuntimeError("layer 0 cannot be deleted")
    A.doc().Layers.Item(name).Delete()
    return f"deleted {name}"
