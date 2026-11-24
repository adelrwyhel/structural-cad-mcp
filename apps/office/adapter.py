"""Microsoft Office adapter (Excel / Word / PowerPoint) over COM. Tool modules use the proxy `A`.

Documents are 1-based in COM; the tools expose 1-based indexes where an index is needed.
"""
import os

import win32com.client

from mcpkit import core
from mcpkit.core import App

VARIANTS = {
    "excel": {"title": "Excel", "progid": "Excel.Application", "coll": "Workbooks", "active": "ActiveWorkbook",
              "exts": (".xlsx", ".xlsm", ".xlsb", ".xls"), "save_fmt": {".xlsx": 51, ".xlsm": 52, ".xlsb": 50, ".xls": 56},
              "modules": ("apps.office.tools_common", "apps.office.tools_excel")},
    "word": {"title": "Word", "progid": "Word.Application", "coll": "Documents", "active": "ActiveDocument",
             "exts": (".docx", ".doc"), "save_fmt": {".docx": 16, ".doc": 0},
             "modules": ("apps.office.tools_common", "apps.office.tools_word")},
    "powerpoint": {"title": "PowerPoint", "progid": "PowerPoint.Application", "coll": "Presentations",
                   "active": "ActivePresentation", "exts": (".pptx", ".ppt"), "save_fmt": {".pptx": 24, ".ppt": 1},
                   "modules": ("apps.office.tools_common", "apps.office.tools_ppt")},
}


class OfficeApp(App):
    def __init__(self, variant: str):
        v = VARIANTS[variant]
        self.variant = variant
        self.name, self.title = variant, v["title"]
        self.progid, self.coll_name, self.active_name = v["progid"], v["coll"], v["active"]
        self.exts, self.edit_exts, self.save_fmt = v["exts"], v["exts"], v["save_fmt"]
        self.modules = v["modules"]
        self.ours = set()          # names of unsaved documents created by these tools
        self._app = None

    # ---- connection ----------------------------------------------------
    def reset(self):
        self._app = None

    def app(self, launch=False):
        if self._app is not None:
            try:
                self._app.Name
                return self._app
            except Exception:
                self._app = None
        try:
            self._app = win32com.client.GetActiveObject(self.progid)
        except Exception as e:
            if not launch:
                raise RuntimeError(f"{self.title} is not running (open it first): {core.friendly(e)}")
            self._app = win32com.client.Dispatch(self.progid)
            try:
                self._app.Visible = True
            except Exception:
                pass
        return self._app

    def docs(self, launch=False):
        return getattr(self.app(launch), self.coll_name)

    def count(self):
        return self.docs().Count

    def doc(self, name=""):
        d = self.docs()
        if d.Count == 0:
            raise RuntimeError(f"No document is open in {self.title}. Use new_document() or open_document(path).")
        if name:
            for i in range(1, d.Count + 1):
                if d.Item(i).Name.lower() == name.lower():
                    return d.Item(i)
            raise RuntimeError(f"no open document named '{name}'")
        return getattr(self.app(), self.active_name)

    @staticmethod
    def path_of(doc) -> str:
        try:
            return doc.FullName if doc.Path else ""
        except Exception:
            return ""

    # ---- emptiness (for the guard) ------------------------------------
    def is_empty(self, doc) -> bool:
        try:
            if self.variant == "excel":
                if doc.Worksheets.Count != 1:
                    return False
                return self.app().WorksheetFunction.CountA(doc.Worksheets.Item(1).UsedRange) == 0
            if self.variant == "word":
                return len(doc.Content.Text.strip()) == 0 and doc.Tables.Count == 0
            return doc.Slides.Count == 0
        except Exception:
            return False

    def guard(self, action, replacing=False):
        doc = self.doc()
        path = self.path_of(doc)
        core.check_target(path, empty=self.is_empty(doc), ours=(not path and doc.Name in self.ours),
                          action=action, replacing=replacing)

    def current_path(self):
        return self.path_of(self.doc())

    def info(self):
        try:
            a = self.app()
            d = {"program_running": True, "version": a.Version, "documents_open": getattr(a, self.coll_name).Count}
            if d["documents_open"]:
                d["active"] = self.path_of(self.doc()) or self.doc().Name
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
