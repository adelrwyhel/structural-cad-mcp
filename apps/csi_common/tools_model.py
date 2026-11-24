"""Geometry, properties, groups."""
import csv
import os

from mcpkit import core
from mcpkit.core import GuardError, export_path, safe_path, tool

from .adapter import A
from .constants import COMBO_TYPES, LOAD_TYPES, MAT_TYPES, UNITS

# ---- geometry (read)

@tool()
def object_counts() -> dict:
    """Number of points, frames, areas."""
    p, f, a = A.counts(A.sap())
    return {"points": p, "frames": f, "areas": a}


@tool()
def list_points(offset: int = 0, limit: int = 200) -> dict:
    """Points with coordinates (current units), paginated."""
    m = A.sap()
    names = list(A.out(m.PointObj.GetNameList(), "PointObj.GetNameList")[1])
    items = []
    for n in names[offset:offset + limit]:
        x, y, z, _ = m.PointObj.GetCoordCartesian(n)
        items.append({"name": n, "x": x, "y": y, "z": z})
    return {"total": len(names), "offset": offset, "items": items}


@tool()
def list_frames(offset: int = 0, limit: int = 200) -> dict:
    """Frames with end points and section, paginated."""
    m = A.sap()
    names = list(A.out(m.FrameObj.GetNameList(), "FrameObj.GetNameList")[1])
    items = []
    for n in names[offset:offset + limit]:
        p1, p2, _ = m.FrameObj.GetPoints(n)
        d = {"name": n, "p1": p1, "p2": p2, "section": m.FrameObj.GetSection(n)[0]}
        if A.prog == "etabs":
            d["story"] = m.FrameObj.GetLabelFromName(n)[1]
        items.append(d)
    return {"total": len(names), "offset": offset, "items": items}


@tool()
def list_areas(offset: int = 0, limit: int = 200) -> dict:
    """Areas (slabs/walls) with points and property, paginated."""
    m = A.sap()
    names = list(A.out(m.AreaObj.GetNameList(), "AreaObj.GetNameList")[1])
    items = []
    for n in names[offset:offset + limit]:
        d = {"name": n, "points": list(m.AreaObj.GetPoints(n)[1]), "property": m.AreaObj.GetProperty(n)[0]}
        if A.prog == "etabs":
            d["story"] = m.AreaObj.GetLabelFromName(n)[1]
        items.append(d)
    return {"total": len(names), "offset": offset, "items": items}



# ---- geometry (write)

@tool(write=True)
def add_point(x: float, y: float, z: float) -> str:
    """Add a point by coordinates. Returns its name."""
    return A.out(A.sap().PointObj.AddCartesian(x, y, z, "", "", "Global"), "PointObj.AddCartesian")[0]


@tool(write=True)
def add_frame(x1: float, y1: float, z1: float, x2: float, y2: float, z2: float, section: str = "Default",
              name: str = "") -> str:
    """Add a frame by coordinates. Returns its name."""
    r = A.sap().FrameObj.AddByCoord(x1, y1, z1, x2, y2, z2, "", section, name, "Global")
    return A.out(r, "FrameObj.AddByCoord")[0]


@tool(write=True)
def add_area(points: list, section: str = "Default", name: str = "") -> str:
    """Add an area from a list of [x, y, z] corner points. (SAFE slabs must lie in the plane z=0.)"""
    if len(points) < 3 or any(len(p) != 3 for p in points):
        raise RuntimeError("points must be at least 3 items of [x, y, z]")
    xs, ys, zs = ([float(p[i]) for p in points] for i in range(3))
    r = A.sap().AreaObj.AddByCoord(len(points), xs, ys, zs, "", section, name, "Global")
    return A.out(r, "AreaObj.AddByCoord")[3]


@tool(write=True)
def delete_object(kind: str, name: str) -> str:
    """Delete one object. kind: 'frame' | 'area' | 'point' (points: isolated/special only). Model must be unlocked."""
    m = A.sap()
    if m.GetModelIsLocked():
        raise RuntimeError("Model is locked (analysis results exist). Call unlock_model() first; this deletes results.")
    if kind == "point":
        A.chk(m.PointObj.DeleteSpecialPoint(name), "DeleteSpecialPoint")
    elif kind in ("frame", "area"):
        A.chk({"frame": m.FrameObj, "area": m.AreaObj}[kind].Delete(name, 0), "Delete")
    else:
        raise RuntimeError("kind must be frame, area or point")
    return f"deleted {kind} {name}"


@tool(write=True)
def assign_frame_section(frame: str, section: str) -> str:
    """Assign an existing section to a frame."""
    A.chk(A.sap().FrameObj.SetSection(frame, section, 0, 0), "FrameObj.SetSection")
    return "ok"


@tool(write=True)
def assign_area_property(area: str, prop: str) -> str:
    """Assign an existing area property (slab/wall/shell) to an area."""
    A.chk(A.sap().AreaObj.SetProperty(area, prop), "AreaObj.SetProperty")
    return "ok"


@tool(write=True)
def set_frame_modifiers(frame: str, area: float = 1, shear2: float = 1, shear3: float = 1, torsion: float = 1,
                        i22: float = 1, i33: float = 1, mass: float = 1, weight: float = 1) -> str:
    """Property modifiers for a frame (e.g. i33=0.35 for cracked beams)."""
    A.chk(A.sap().FrameObj.SetModifiers(frame, [area, shear2, shear3, torsion, i22, i33, mass, weight]), "SetModifiers")
    return "ok"


@tool(write=True)
def assign_support(point: str, fixed: bool = True) -> str:
    """Restrain a point: fixed (6 DOF) or pinned (translations only)."""
    dof = [True] * 6 if fixed else [True, True, True, False, False, False]
    A.out(A.sap().PointObj.SetRestraint(point, dof), "SetRestraint")
    return "fixed" if fixed else "pinned"


@tool(write=True)
def add_group(name: str) -> str:
    """Create a group."""
    if name.startswith("__MCP"):
        raise RuntimeError("group names starting with '__MCP' are reserved")
    A.chk(A.sap().GroupDef.SetGroup(name), "GroupDef.SetGroup")
    return name


@tool(write=True)
def assign_to_group(kind: str, name: str, group: str) -> str:
    """Add a point/frame/area to a group."""
    m = A.sap()
    obj = {"point": m.PointObj, "frame": m.FrameObj, "area": m.AreaObj}.get(kind)
    if obj is None:
        raise RuntimeError("kind must be point, frame or area")
    A.chk(obj.SetGroupAssign(name, group, False, 0), "SetGroupAssign")
    return "ok"



# ---- properties

@tool()
def list_materials() -> list:
    """Defined materials."""
    return list(A.out(A.sap().PropMaterial.GetNameList(), "PropMaterial.GetNameList")[1])


@tool(write=True)
def add_material(name: str, mat_type: str = "Concrete", e_modulus: float = 0.0, poisson: float = 0.2,
                 thermal: float = 1e-5) -> str:
    """Define an isotropic material (current units). mat_type: Steel, Concrete, Rebar, ..."""
    if mat_type not in MAT_TYPES:
        raise RuntimeError(f"unknown mat_type; use one of {list(MAT_TYPES)}")
    pm = A.sap().PropMaterial
    A.chk(pm.SetMaterial(name, MAT_TYPES[mat_type]), "SetMaterial")
    if e_modulus:
        A.chk(pm.SetMPIsotropic(name, e_modulus, poisson, thermal), "SetMPIsotropic")
    return name


@tool()
def list_frame_sections() -> list:
    """Defined frame sections."""
    return list(A.out(A.sap().PropFrame.GetNameList(), "PropFrame.GetNameList")[1])


@tool(write=True)
def add_rect_section(name: str, material: str, depth: float, width: float) -> str:
    """Define a rectangular frame section."""
    A.chk(A.sap().PropFrame.SetRectangle(name, material, depth, width), "SetRectangle")
    return name


@tool(write=True)
def add_circle_section(name: str, material: str, diameter: float) -> str:
    """Define a circular frame section."""
    A.chk(A.sap().PropFrame.SetCircle(name, material, diameter), "SetCircle")
    return name


@tool(write=True)
def add_i_section(name: str, material: str, depth: float, flange_width: float, flange_thickness: float,
                  web_thickness: float) -> str:
    """Define a symmetric I/H steel section."""
    A.chk(A.sap().PropFrame.SetISection(name, material, depth, flange_width, flange_thickness, web_thickness,
                                      flange_width, flange_thickness), "SetISection")
    return name


@tool(write=True)
def add_slab_section(name: str, material: str, thickness: float) -> str:
    """Define a thin slab/shell area section."""
    pa = A.sap().PropArea
    if A.prog == "sap2000":
        A.chk(pa.SetShell_1(name, 1, False, material, 0.0, thickness, thickness), "PropArea.SetShell_1")
    else:
        A.chk(pa.SetSlab(name, 0, 1, material, thickness), "PropArea.SetSlab")
    return name


