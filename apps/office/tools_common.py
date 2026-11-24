"""Tools shared by Excel / Word / PowerPoint: documents, files, PDF export."""
import os

from mcpkit import core
from mcpkit.core import GuardError, export_path, safe_path, tool

from .adapter import A


@tool()
def ping() -> dict:
    """Health check: is the program reachable, which document is active, and may the tools modify it?"""
    info = {"server": A.name, "sandbox_folder": str(core.SANDBOX), "log": str(core.LOGS / f"{A.name}.log"),
            "allow_edit_existing_env": core.ALLOW_EDIT_EXISTING}
    info.update(A.info())
    if info.get("program_running") and info.get("documents_open"):
        try:
            A.guard("ping-check")
            info["writable"] = True
        except GuardError as e:
            info["writable"] = False
            info["why_read_only"] = str(e)
    return info


@tool()
def list_documents() -> list:
    """All open documents with path and saved state."""
    d = A.docs()
    out = []
    for i in range(1, d.Count + 1):
        x = d.Item(i)
        out.append({"name": x.Name, "path": A.path_of(x) or "(unsaved)", "saved": x.Saved})
    return out


@tool()
def set_active_document(name: str) -> str:
    """Make an open document active."""
    A.doc(name).Activate()
    return name


@tool(timeout=300)
def new_document() -> str:
    """Create a NEW document (starts the program if needed). It is sandbox-safe: write tools may edit it."""
    d = A.docs(launch=True).Add()
    A.ours.add(d.Name)
    return d.Name


@tool(timeout=300)
def open_document(path: str, read_only: bool = True) -> str:
    """Open an existing file READ-ONLY by default. read_only=False requires the user's explicit request and a prior
    allow_edit(path=...) grant, unless the file lives in the sandbox folder."""
    p = safe_path(path, A.exts, must_exist=True)
    if not read_only and not (core.is_sandbox(p) or core.is_granted(p)):
        raise GuardError("opening a real file for editing needs allow_edit(path=<this file>) first - and only when the "
                         "user explicitly asked to modify it.")
    d = A.docs(launch=True)
    if A.variant == "excel":
        x = d.Open(p, 0, read_only)
    elif A.variant == "word":
        x = d.Open(p, False, read_only)
    else:
        x = d.Open(p, read_only, False, True)
    return x.Name + (" (read-only)" if read_only else "")


@tool(write=True)
def save_document() -> str:
    """Save the active document in place (it must already be a sandbox/granted file)."""
    x = A.doc()
    if not A.path_of(x):
        raise RuntimeError("Document has never been saved; use save_as('name').")
    x.Save()
    return A.path_of(x)


@tool(write=True, timeout=300)
def save_as(path: str, overwrite: bool = False) -> str:
    """Save the active document as a new file (relative names go to the sandbox folder). Format follows the extension."""
    ext0 = A.exts[0]
    p = path if os.path.splitext(path)[1] else path + ext0
    p = safe_path(p, A.exts, write=True, overwrite=overwrite)
    x = A.doc()
    fmt = A.save_fmt.get(os.path.splitext(p)[1].lower())
    old_alerts = None
    try:
        if A.variant == "excel":
            old_alerts = A.app().DisplayAlerts
            A.app().DisplayAlerts = False
            x.SaveAs(p, fmt)
        elif A.variant == "word":
            x.SaveAs2(p, fmt)
        else:
            x.SaveAs(p, fmt)
    finally:
        if old_alerts is not None:
            A.app().DisplayAlerts = old_alerts
    core.register_sandbox(p)
    A.ours.discard(x.Name)
    return p


@tool(write=True)
def close_document(name: str, save: bool = False) -> str:
    """Close an open document that these tools created (never the user's own documents)."""
    x = A.doc(name)
    path = A.path_of(x)
    if not (core.is_sandbox(path) or (not path and x.Name in A.ours)):
        raise GuardError(f"'{name}' was not created by these tools; close it yourself in {A.title}.")
    if A.variant == "excel":
        x.Close(save)
    elif A.variant == "word":
        x.Close(-1 if save else 0)
    else:
        if save and path:
            x.Save()
        x.Close()
    A.ours.discard(name)
    return f"closed {name}"


@tool(timeout=300)
def export_pdf(filename: str = "document") -> str:
    """Export the active document to exports/<name>.pdf."""
    p = export_path(filename, ".pdf")
    x = A.doc()
    if A.variant == "excel":
        x.ExportAsFixedFormat(0, p)
    elif A.variant == "word":
        x.ExportAsFixedFormat(p, 17)
    else:
        x.ExportAsFixedFormat(p, 2)
    return p
