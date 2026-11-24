"""CSI adapter: connection, guard and helpers shared by every CSI tool module (ETABS / SAP2000 / SAFE).

Tool modules use the proxy `A`, e.g.  m = A.sap();  A.chk(m.File.Save(p), "Save").
"""
import os

import comtypes.client

from mcpkit import core
from mcpkit.core import App

VARIANTS = {
    "etabs": {"title": "ETABS", "exts": (".edb",), "progids": ["CSI.ETABS.API.ETABSObject"]},
    "sap2000": {"title": "SAP2000", "exts": (".sdb",), "progids": ["CSI.SAP2000.API.SapObject"]},
    "safe": {"title": "SAFE", "exts": (".fdb",), "progids": ["CSI.SAFE.API.ETABSObject", "CSI.SAFE.API.SAFEObject"]},
}

MODULES = (
    "apps.csi.tools_session",
    "apps.csi.tools_tables",
    "apps.csi.tools_loads",
    "apps.csi.tools_model",
    "apps.csi.tools_etabs",
    "apps.csi.tools_analysis",
)


class CsiApp(App):
    def __init__(self, prog: str):
        v = VARIANTS[prog]
        self.prog, self.name, self.title = prog, prog, v["title"]
        self.exts, self.progids = v["exts"], v["progids"]
        self.modules = MODULES
        self.edit_exts = self.exts
        self.ours_untitled = False   # current untitled model was created by these tools
        self._obj = None

    # ---- connection ----------------------------------------------------
    def reset(self):
        self._obj = None

    def sap(self):
        """Cached SapModel; transparently re-attaches if the program was restarted."""
        if self._obj is not None:
            try:
                self._obj.SapModel.GetVersion()
                return self._obj.SapModel
            except Exception:
                self._obj = None
        err = None
        for pid in self.progids:
            try:
                self._obj = comtypes.client.GetActiveObject(pid)
                return self._obj.SapModel
            except Exception as e:  # noqa
                err = e
        raise RuntimeError(f"{self.title} is not running (or its COM interface is unavailable): {core.friendly(err)}")

    # ---- helpers -------------------------------------------------------
    def ensure_visible(self):
        """New-model calls fail while the program window is minimized."""
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        found = []
        title = self.title

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _):
            if u32.IsWindowVisible(hwnd):
                buf = ctypes.create_unicode_buffer(256)
                u32.GetWindowTextW(hwnd, buf, 256)
                if buf.value.startswith(title):
                    found.append(hwnd)
            return True

        u32.EnumWindows(cb, 0)
        for h in found:
            if u32.IsIconic(h):
                u32.ShowWindow(h, 3)

    def chk(self, ret, what):
        if isinstance(ret, (tuple, list)):   # calls with in/out args return [outs..., ret]
            ret = ret[-1]
        if ret != 0:
            raise RuntimeError(f"{self.title} rejected '{what}' (return code {ret}). Typical causes: model locked after "
                               f"analysis (call unlock_model), name not found, or invalid argument.")

    def out(self, r, what):
        if not isinstance(r, (tuple, list)):
            self.chk(r, what)
            return ()
        self.chk(r[-1], what)
        return tuple(r[:-1])

    def filename(self, m=None) -> str:
        fn = (m or self.sap()).GetModelFilename()
        return fn if (fn and os.path.isabs(fn)) else ""

    def counts(self, m=None):
        m = m or self.sap()
        return m.PointObj.Count(), m.FrameObj.Count(), m.AreaObj.Count()

    def etabs_only(self, what):
        if self.prog != "etabs":
            raise RuntimeError(f"{what} is available for ETABS only (this server is {self.title}).")

    @staticmethod
    def num(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    def select_all_outputs(self, m):
        """Select every load case/combo for results output (needed before result tables are readable)."""
        try:
            m.Results.Setup.DeselectAllCasesAndCombosForOutput()
            for n in m.LoadCases.GetNameList()[1]:
                m.Results.Setup.SetCaseSelectedForOutput(n, True)
            for n in m.RespCombo.GetNameList()[1]:
                m.Results.Setup.SetComboSelectedForOutput(n, True)
        except Exception:
            pass

    def fetch(self, m, key, group="All", try_select=True):
        """Return (columns, rows) of a database table; rows are lists of strings."""
        dt = m.DatabaseTables
        r = dt.GetTableForDisplayArray(key, [], group, 0, [], 0, [])
        if r[-1] != 0 and try_select:
            self.select_all_outputs(m)
            r = dt.GetTableForDisplayArray(key, [], group, 0, [], 0, [])
        if r[-1] != 0:
            raise RuntimeError(f"Table '{key}' is not available (code {r[-1]}). For result tables the model must be "
                               f"analyzed; use list_tables(contains=...) to find the exact key.")
        fields, n, data = list(r[2]), r[3], list(r[4])
        w = len(fields)
        return fields, [data[i * w:(i + 1) * w] for i in range(n)]

    # ---- guard ---------------------------------------------------------
    def guard(self, action, replacing=False):
        m = self.sap()
        fn = self.filename(m)
        empty = (not fn) and sum(self.counts(m)) == 0
        core.check_target(fn, empty=empty, ours=self.ours_untitled or self.has_marker(m), action=action,
                          replacing=replacing)

    def has_marker(self, m=None) -> bool:
        """True if the model contains the in-file group that marks it as created by these tools."""
        try:
            return core.MARKER in list((m or self.sap()).GroupDef.GetNameList()[1])
        except Exception:
            return False

    def mark(self, m=None):
        (m or self.sap()).GroupDef.SetGroup(core.MARKER)

    def current_path(self):
        return self.filename()

    def info(self):
        try:
            m = self.sap()
            return {"program_running": True, "version": m.GetVersion()[0], "file": self.filename(m) or "(untitled)"}
        except Exception as e:  # noqa
            return {"program_running": False, "error": str(e)}


_inst = None


def set_instance(app):
    global _inst
    _inst = app


class _Proxy:
    """`A` forwards attribute access to the active CsiApp (set by create())."""
    def __getattr__(self, n):
        return getattr(_inst, n)

    def __setattr__(self, n, v):
        setattr(_inst, n, v)


A = _Proxy()
