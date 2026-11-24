"""mcpkit.core - the shared engine for every app server (CSI family, AutoCAD, and future apps).

Concepts
--------
* App plugin   : a package under apps/<name> exposing  create(variant) -> App  (see apps/_template).
* Tool module  : a plain .py file whose functions are decorated with @tool(...). Loaded in isolation:
                 a module that fails to import is reported by `server_info` and everything else still works.
* Server       : wraps MCPServer. All COM/app calls run on ONE worker thread; every call has a timeout,
                 logging and clean errors. A hung call replaces the worker; connection errors on read tools
                 trigger one automatic reconnect+retry.
* Guard        : write tools are blocked on anything that is not a sandbox file (see check_target).
* Supervisor   : mcpkit/supervisor.py restarts the whole server process if it ever dies and replays the MCP
                 handshake, so the client never loses the connection.
"""
import faulthandler
import functools
import importlib
import json
import logging
import logging.handlers
import os
import pathlib
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

HOME = pathlib.Path(os.environ.get("CSI_MCP_HOME", pathlib.Path(__file__).resolve().parents[1]))
SANDBOX = HOME / "sandbox"      # models/drawings created by the tools live here
EXPORTS = HOME / "exports"      # csv / md / pdf outputs
BACKUPS = HOME / "backups"
LOGS = HOME / "logs"
for _d in (SANDBOX, EXPORTS, BACKUPS, LOGS):
    _d.mkdir(parents=True, exist_ok=True)

MARKER = "__MCP_SANDBOX__"   # name of the group/layer that marks a document as created by these tools
ALLOW_EDIT_EXISTING = os.environ.get("CSI_MCP_ALLOW_EDIT_EXISTING") == "1"
MAX_CHARS = int(os.environ.get("CSI_MCP_MAX_CHARS", "60000"))
_REGISTRY = HOME / "sandbox_registry.json"
_reg_lock = threading.Lock()

try:  # hard crashes (access violations in COM servers) leave a trace instead of silence
    faulthandler.enable(open(LOGS / "faulthandler.log", "a"), all_threads=True)
except Exception:
    pass


class GuardError(RuntimeError):
    """Raised when a safety rule blocks an action."""


# ================================================================== tool marker (decoupled from any server)
def tool(write: bool = False, timeout: float = 120.0):
    """Mark a function as an MCP tool. The server registers it when the module is loaded.
    write=True  -> the app's guard runs first (blocked on non-sandbox documents).
    timeout     -> seconds before the call is abandoned (the worker is replaced)."""
    def deco(fn):
        fn._mcp = {"write": write, "timeout": timeout}
        return fn
    return deco


# ================================================================== paths & guard
def norm(p) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _load_registry() -> set:
    try:
        return set(json.loads(_REGISTRY.read_text(encoding="utf8")))
    except Exception:
        return set()


def register_sandbox(path) -> None:
    with _reg_lock:
        reg = _load_registry()
        reg.add(norm(path))
        _REGISTRY.write_text(json.dumps(sorted(reg)), encoding="utf8")


def is_sandbox(path) -> bool:
    if not path:
        return False
    n = norm(path)
    return n.startswith(norm(SANDBOX) + os.sep) or n in _load_registry()


# ---- time-limited, per-document edit grants (the "edit when the user asks" mechanism)
_grants = {}   # normalized path -> expiry (epoch seconds)
_grant_lock = threading.Lock()


def _audit(msg: str):
    try:
        with open(LOGS / "audit.log", "a", encoding="utf8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def grant_edit(path, minutes: int) -> str:
    """Allow write tools on ONE existing document for a limited time. Makes a backup copy first. Returns the backup path."""
    n = norm(path)
    b = backup_once(path, force=True)
    with _grant_lock:
        _grants[n] = time.time() + 60 * minutes
    _audit(f"GRANT {minutes}min {path} backup={b}")
    return b


def is_granted(path) -> bool:
    if not path:
        return False
    n = norm(path)
    with _grant_lock:
        exp = _grants.get(n)
        if exp and exp < time.time():
            _grants.pop(n, None)
            _audit(f"EXPIRED {path}")
            return False
        return bool(exp)


def revoke_edit(path=None) -> int:
    with _grant_lock:
        keys = [norm(path)] if path else list(_grants)
        n = sum(1 for k in keys if _grants.pop(k, None))
    _audit(f"REVOKE {path or '*'} ({n})")
    return n


def active_grants() -> list:
    now = time.time()
    with _grant_lock:
        return [{"path": k, "minutes_left": round((v - now) / 60, 1)} for k, v in _grants.items() if v > now]


_BAD = re.compile(r"(^\\\\\.\\)|(^\\\\\?\\)|[\x00-\x1f<>\"|?*]")
_DEVICE = re.compile(r"^(con|prn|aux|nul|com\d|lpt\d)$", re.I)


def safe_path(path: str, exts: tuple, *, must_exist=False, write=False, overwrite=False) -> str:
    """Validate a user supplied path. Relative paths go to the sandbox folder."""
    if not path or not isinstance(path, str):
        raise GuardError("path is empty")
    p = path.strip().strip('"')
    if _BAD.search(p.replace(":", "", 1)) or ".." in pathlib.PurePath(p).parts:
        raise GuardError(f"illegal characters or '..' in path: {path!r}")
    if not os.path.isabs(p):
        p = str(SANDBOX / p)
    p = os.path.abspath(p)
    if _DEVICE.match(pathlib.Path(p).stem):
        raise GuardError("device names are not allowed")
    if pathlib.Path(p).suffix.lower() not in exts:
        raise GuardError(f"extension must be one of {', '.join(exts)}")
    if must_exist and not os.path.isfile(p):
        raise FileNotFoundError(p)
    if write and os.path.exists(p):
        inside = norm(p).startswith((norm(SANDBOX) + os.sep, norm(EXPORTS) + os.sep))
        if not overwrite:
            raise GuardError(f"{p} already exists; pass overwrite=True (allowed only inside the sandbox/exports folders)")
        if not inside and not ALLOW_EDIT_EXISTING and not is_granted(p):
            raise GuardError(f"refusing to overwrite {p}: it is outside the sandbox folder {SANDBOX}")
    if write:
        os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def export_path(filename: str, ext: str) -> str:
    stem = re.sub(r"[^\w\-. ]", "_", pathlib.Path(filename).stem)[:80] or "export"
    return str(EXPORTS / f"{stem}{ext}")


_backed_up = set()


def backup_once(path, force: bool = False) -> str:
    if not path or not os.path.isfile(path) or (norm(path) in _backed_up and not force):
        return ""
    ts = time.strftime("%Y%m%d-%H%M%S")
    dst = BACKUPS / f"{pathlib.Path(path).stem}.{ts}{pathlib.Path(path).suffix}.bak"
    shutil.copy2(path, dst)
    _backed_up.add(norm(path))
    return str(dst)


def check_target(path, *, empty: bool, ours: bool, action: str, replacing: bool = False) -> None:
    """Central decision: may `action` modify the document identified by `path`?"""
    if not path:  # untitled / unsaved
        if ours or empty:
            return
        raise GuardError(
            f"BLOCKED '{action}': the open document is unsaved and has content that was NOT created by this server "
            f"(your own work?). Save it yourself first, or work on a document created with the new_* tools.")
    if is_sandbox(path) or ours:   # `ours` = the document carries our in-file marker (survives restarts and Save As)
        return
    if is_granted(path):
        _audit(f"WRITE-ALLOWED {action} on {path}")
        return
    if ALLOW_EDIT_EXISTING:
        b = backup_once(path)
        logging.getLogger("guard").warning("edit of existing file allowed by env: %s (backup %s)", path, b)
        return
    what = "replace" if replacing else "modify"
    raise GuardError(
        f"BLOCKED '{action}': would {what} '{path}', which is not a sandbox file. Read-only tools still work. "
        f"To work on it safely, save a COPY into {SANDBOX} (Save As in the program), then open that copy. "
        f"If the USER explicitly asked you to modify this document, call allow_edit() first (it makes a backup and expires). "
        f"Otherwise do not try to bypass this.")


# ================================================================== output limiting / errors
def clip(obj, limit: int = MAX_CHARS):
    """Trim big results so the JSON stays under `limit` characters."""
    try:
        s = json.dumps(obj, default=str)
    except Exception:
        return obj
    if len(s) <= limit:
        return obj

    def fit(items, wrap):
        lo, hi = 0, len(items)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if len(json.dumps(wrap(items[:mid]), default=str)) <= limit:
                lo = mid
            else:
                hi = mid - 1
        return lo

    if isinstance(obj, dict) and isinstance(obj.get("rows"), list):
        rows = obj["rows"]
        n = fit(rows, lambda r: {**obj, "rows": r})
        return {**obj, "rows": rows[:n], "truncated": True,
                "note": f"output clipped to {n} of {len(rows)} rows; use offset/where/columns to narrow"}
    if isinstance(obj, dict) and isinstance(obj.get("items"), list):
        it = obj["items"]
        n = fit(it, lambda r: {**obj, "items": r})
        return {**obj, "items": it[:n], "truncated": True, "note": f"clipped to {n} of {len(it)} items"}
    if isinstance(obj, list):
        n = fit(obj, lambda r: r)
        return {"items": obj[:n], "truncated": True, "total": len(obj), "note": "list clipped; narrow the query"}
    return {"truncated": True, "preview": s[:limit]}


_HR = {
    -2147221021: "the program is not running (COM 'Operation unavailable')",
    -2147221005: "the program's COM interface is not registered / cannot be created",
    -2147418111: "the program is busy and rejected the call (modal dialog open or a long operation running)",
    -2147417846: "the program is busy; try again in a moment",
    -2147023174: "the program was closed (RPC server unavailable)",
    -2147023170: "the program was closed during the call (RPC failed)",
    -2147467261: "invalid pointer inside the program (its window is probably minimized or a dialog is open)",
}
RECONNECT_HR = {-2147023174, -2147023170, -2147221021}
BUSY_HR = {-2147418111, -2147417846}   # call rejected / retry later: the app refused BEFORE executing, so retrying is always safe


def hresult(e: BaseException):
    hr = getattr(e, "hresult", None)
    if hr is None and getattr(e, "args", None) and isinstance(e.args[0], int):
        hr = e.args[0]
    return hr


def friendly(e: BaseException) -> str:
    hr = hresult(e)
    if hr in _HR:
        return f"{_HR[hr]} [hr={hr}]"
    return f"{type(e).__name__}: {e}"


# ================================================================== App contract
class App:
    """Base class for an app plugin. Subclass in apps/<name>/__init__.py (see apps/_template)."""
    name = "app"          # MCP server name
    title = "App"         # window title prefix / display name
    modules = ()          # dotted module paths containing @tool functions

    def reset(self):
        """Drop cached connections (called after crashes/timeouts)."""

    def guard(self, action: str):
        """Raise GuardError if `action` must not run on the current document."""

    def info(self) -> dict:
        """Extra fields for ping()."""
        return {}

    edit_exts = ()        # file extensions allow_edit may grant (lowercase, with dot)

    def current_path(self) -> str:
        """Path of the active saved document ('' if none/unsaved). Used by allow_edit()."""
        return ""


# ================================================================== Server
class Server:
    """MCPServer + single COM worker + logging + guard + recovery + plugin loader."""

    def __init__(self, app: App):
        self.app = app
        self.name, self.title = app.name, app.title
        self.mcp = MCPServer(app.name)
        self.started = time.time()
        self.calls = self.failures = 0
        self.modules = {}   # module path -> {"ok": bool, "tools": [...], "error": str}
        self.tools = {}
        self.log = logging.getLogger(app.name)
        self.log.setLevel(logging.INFO)
        if not self.log.handlers:
            h = logging.handlers.RotatingFileHandler(LOGS / f"{app.name}.log", maxBytes=1_000_000, backupCount=3,
                                                     encoding="utf8")
            h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self.log.addHandler(h)
            self.log.propagate = False
        logging.getLogger("guard").addHandler(self.log.handlers[0])
        sys.excepthook = lambda *a: self.log.critical("uncaught exception", exc_info=a)
        threading.excepthook = lambda a: self.log.critical("thread exception in %s", a.thread, exc_info=(
            a.exc_type, a.exc_value, a.exc_traceback))
        self._pool_lock = threading.Lock()
        self.pool = self._new_pool()

    # ---- worker management -------------------------------------------------
    def _new_pool(self):
        return ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"{self.name}-com", initializer=self._coinit)

    @staticmethod
    def _coinit():
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

    def _replace_worker(self, why: str):
        """A call hung: abandon the stuck worker thread, start a fresh one, drop cached app connections."""
        with self._pool_lock:
            old, self.pool = self.pool, self._new_pool()
        old.shutdown(wait=False, cancel_futures=True)
        self.log.error("worker replaced: %s", why)
        try:
            self.app.reset()
        except Exception:
            self.log.exception("app.reset failed")

    # ---- registration ------------------------------------------------------
    def add_tool(self, fn):
        opts = fn._mcp
        write, timeout = opts["write"], opts["timeout"]
        name = fn.__name__

        @functools.wraps(fn)
        def inner(*a, **kw):
            self.calls += 1
            t0 = time.time()
            argtxt = json.dumps({"a": a, "kw": kw}, default=str)[:300]

            def job():
                if write:
                    self.app.guard(name)
                return clip(fn(*a, **kw))

            attempt, busy_tries = 1, 0
            while True:
                try:
                    with self._pool_lock:
                        pool = self.pool
                    r = pool.submit(job).result(timeout=timeout)
                    self.log.info("OK   %-28s %.2fs %s", name, time.time() - t0, argtxt)
                    return r
                except FutureTimeout:
                    self.failures += 1
                    self._replace_worker(f"{name} exceeded {timeout}s")
                    raise ToolError(f"{name} did not finish within {timeout:.0f}s and was abandoned. It may still be "
                                       f"running inside {self.title} (check for a dialog). The server has recovered "
                                       f"and is ready for the next call.") from None
                except GuardError as e:
                    self.log.warning("BLOCK %s: %s", name, e)
                    raise ToolError(str(e)) from None
                except Exception as e:  # noqa
                    hr = hresult(e)
                    if hr in BUSY_HR and busy_tries < 20 and time.time() - t0 < timeout * 0.8:
                        busy_tries += 1
                        time.sleep(0.5)
                        continue
                    if attempt == 1 and not write and hr in RECONNECT_HR:
                        attempt = 2
                        self.log.warning("%s: connection lost (%s); reconnecting once", name, friendly(e))
                        try:
                            self.app.reset()
                        except Exception:
                            pass
                        continue
                    self.failures += 1
                    msg = friendly(e)
                    self.log.error("FAIL %s: %s %s", name, msg, argtxt)
                    raise ToolError(f"{name} failed: {msg}") from None

        self.mcp.tool()(inner)
        self.tools[name] = opts

    def load_module(self, path: str):
        """Import a tool module in isolation and register its @tool functions."""
        try:
            mod = importlib.import_module(path)
            names = []
            for fn in vars(mod).values():
                if callable(fn) and hasattr(fn, "_mcp") and fn.__module__ == mod.__name__:
                    self.add_tool(fn)
                    names.append(fn.__name__)
            self.modules[path] = {"ok": True, "tools": names}
            self.log.info("module %s loaded (%d tools)", path, len(names))
        except Exception as e:  # noqa
            self.modules[path] = {"ok": False, "error": f"{type(e).__name__}: {e}", "tools": []}
            self.log.exception("module %s FAILED to load", path)

    def _builtin_tools(self):
        srv = self

        @tool()
        def server_info() -> dict:
            """Server health: uptime, call/failure counts, which tool modules loaded or failed, supervisor restarts."""
            return {"server": srv.name, "uptime_s": round(time.time() - srv.started),
                    "calls": srv.calls, "failures": srv.failures,
                    "supervisor_restarts": int(os.environ.get("MCP_RESTARTS", "0")),
                    "modules": srv.modules, "tool_count": len(srv.tools), "log": str(LOGS / f"{srv.name}.log"),
                    "sandbox": str(SANDBOX), "allow_edit_existing": ALLOW_EDIT_EXISTING}

        @tool()
        def restart_server() -> str:
            """Restart this server process (picks up code changes). The supervisor brings it back in ~1 second."""
            if not os.environ.get("MCP_SUPERVISED"):
                raise ToolError("not running under the supervisor; restart from the client (/mcp) instead")
            threading.Timer(0.5, lambda: os._exit(3)).start()
            return "restarting"

        @tool()
        def allow_edit(minutes: int = 60, path: str = "") -> dict:
            """UNLOCK editing of the user's REAL document (current one, or `path`) for a limited time.
            Call this ONLY when the user has explicitly asked you to modify their own model/drawing - never on your own.
            A backup copy is saved first (see result); the grant is for that one file and expires. Unsaved changes made
            inside the program are NOT in the backup, so ask the user to save first when relevant."""
            if not 1 <= minutes <= 480:
                raise ToolError("minutes must be between 1 and 480")
            target = path.strip() if path else srv.app.current_path()
            if not target:
                raise ToolError("no saved document is open. Ask the user to save it (or pass path=).")
            target = os.path.abspath(target)
            if not os.path.isfile(target):
                raise ToolError(f"file not found: {target}")
            if srv.app.edit_exts and pathlib.Path(target).suffix.lower() not in srv.app.edit_exts:
                raise ToolError(f"unsupported file type; allowed: {', '.join(srv.app.edit_exts)}")
            b = grant_edit(target, minutes)
            return {"granted": target, "minutes": minutes, "backup": b,
                    "note": "backup contains the last SAVED version; changes made after this point are the user's responsibility to review"}

        @tool()
        def revoke_edit() -> dict:
            """Cancel all edit grants immediately (back to read-only on real documents)."""
            return {"revoked": globals()["revoke_edit"]()}

        @tool()
        def edit_status() -> dict:
            """Which real documents are currently unlocked for editing, and for how long."""
            return {"grants": active_grants(), "allow_edit_existing_env": ALLOW_EDIT_EXISTING}

        self.add_tool(server_info)
        self.add_tool(allow_edit)
        self.add_tool(revoke_edit)
        self.add_tool(edit_status)
        self.add_tool(restart_server)

    def run(self):
        self._builtin_tools()
        for m in self.app.modules:
            self.load_module(m)
        self.log.info("server %s starting; %d tools; allow_edit_existing=%s", self.name, len(self.tools),
                      ALLOW_EDIT_EXISTING)
        self.mcp.run()
