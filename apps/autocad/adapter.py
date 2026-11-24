"""AutoCAD adapter (COM automation through pywin32, early-bound). Tool modules use the proxy `A`."""
import re

import pythoncom
import win32com.client
from win32com.client import VARIANT

from mcpkit import core
from mcpkit.core import App

MODULES = (
    "apps.autocad.tools_session",
    "apps.autocad.tools_layers",
    "apps.autocad.tools_query",
    "apps.autocad.tools_draw",
    "apps.autocad.tools_edit",
)

# interface to cast to for typed property access
TYPED = {
    "AcDbLine": "IAcadLine", "AcDbPolyline": "IAcadLWPolyline", "AcDb2dPolyline": "IAcad2DPolyline",
    "AcDbCircle": "IAcadCircle", "AcDbArc": "IAcadArc", "AcDbText": "IAcadText", "AcDbMText": "IAcadMText",
    "AcDbBlockReference": "IAcadBlockReference", "AcDbHatch": "IAcadHatch", "AcDbPoint": "IAcadPoint",
    "AcDbEllipse": "IAcadEllipse", "AcDbSpline": "IAcadSpline",
    "AcDbAlignedDimension": "IAcadDimAligned", "AcDbRotatedDimension": "IAcadDimRotated",
}

# commands that would let a tool call leave the sandbox (close/save/open files, run programs, delete files)
_DENY = re.compile(
    r"(?i)(^|[\s(\"'_.-])(quit|exit|closeall|close|shell|sh|startapp|open|qsave|save|saveas|new|qnew|recover|"
    r"script|netload|appload|filedia|vl-file-delete|vl-file-rename|vl-file-copy|vl-registry-write|vl-registry-delete|"
    r"vl-mkdir|dos_|vlax-create-object)($|[\s)\"'])")


def pt(*xyz):
    v = [float(x) for x in xyz] + [0.0] * (3 - len(xyz))
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, v)


def arr(values):
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(v) for v in values])


class AutoCadApp(App):
    name = "autocad"
    title = "AutoCAD"
    modules = MODULES
    edit_exts = (".dwg",)

    def __init__(self):
        self._app = None
        self.ours_docs = set()   # names of unsaved drawings created by these tools

    # ---- connection ----------------------------------------------------
    def reset(self):
        self._app = None

    def app(self):
        if self._app is not None:
            try:
                self._app.Version
                return self._app
            except Exception:
                self._app = None
        try:
            obj = win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception as e:
            raise RuntimeError(f"AutoCAD is not running or COM attach failed: {core.friendly(e)}")
        try:  # early binding (typelib) is far more reliable than late binding for AutoCAD
            obj = win32com.client.gencache.EnsureDispatch(obj)
        except Exception:
            pass
        self._app = obj
        return obj

    def doc(self, name=""):
        a = self.app()
        if a.Documents.Count == 0:
            raise RuntimeError("No drawing is open in AutoCAD. Call new_drawing() or open_drawing(path) first.")
        if name:
            for i in range(a.Documents.Count):
                d = a.Documents.Item(i)
                if d.Name.lower() == name.lower():
                    return d
            raise RuntimeError(f"no open drawing named '{name}'")
        return a.ActiveDocument

    def typed(self, e):
        iface = TYPED.get(e.ObjectName)
        if iface:
            try:
                return win32com.client.CastTo(e, iface)
            except Exception:
                pass
        return e

    def entity(self, handle):
        return self.typed(self.doc().HandleToObject(handle))

    @staticmethod
    def check_command(cmd: str):
        if _DENY.search(cmd):
            raise core.GuardError(f"command blocked (could save/close/open files or run programs): {cmd!r}")

    # ---- guard ---------------------------------------------------------
    def guard(self, action, replacing=False):
        d = self.doc()
        path = d.FullName if d.Path else ""
        empty = d.ModelSpace.Count == 0
        ours = (d.Name in self.ours_docs) or self.has_marker(d)
        core.check_target(path, empty=empty, ours=ours, action=action, replacing=replacing)

    def has_marker(self, d) -> bool:
        try:
            d.Layers.Item(core.MARKER)
            return True
        except Exception:
            return False

    def current_path(self):
        d = self.doc()
        return d.FullName if d.Path else ""

    def info(self):
        try:
            a = self.app()
            d = {"program_running": True, "version": a.Version, "drawings_open": a.Documents.Count}
            if a.Documents.Count:
                d["active"] = a.ActiveDocument.FullName or a.ActiveDocument.Name
            return d
        except Exception as e:  # noqa
            return {"program_running": False, "error": str(e)}


_inst = None


def set_instance(app):
    global _inst
    _inst = app


class _Proxy:
    def __getattr__(self, n):
        return getattr(_inst, n)

    def __setattr__(self, n, v):
        setattr(_inst, n, v)


A = _Proxy()
