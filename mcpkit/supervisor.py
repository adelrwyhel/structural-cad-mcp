"""Crash-proof stdio proxy for an MCP server.

    python mcpkit/supervisor.py <run.py> <app> [variant]

Sits between the MCP client and the real server process. If the real server dies (crash, os._exit, kill),
it is restarted automatically and the MCP handshake (initialize / initialized) is replayed, so the client
connection survives. Requests that were in flight get a clean JSON-RPC error ("restarted, please retry").
A crash loop is throttled with a growing back-off instead of spinning.
"""
import json
import os
import subprocess
import sys
import threading
import time
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)
_log = open(LOGS / "supervisor.log", "a", encoding="utf8", buffering=1)


def log(msg):
    _log.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


out_lock = threading.Lock()
state_lock = threading.RLock()
child = None
restarts = 0
init_req = None        # raw bytes of the client's initialize request
init_note = None       # raw bytes of notifications/initialized
pending = {}           # id -> raw request line (only requests that expect a response)
swallow = set()        # ids of our own replayed requests
stopping = False
CMD = [sys.executable, "-u"] + sys.argv[1:]


def to_client(line: bytes):
    with out_lock:
        sys.stdout.buffer.write(line if line.endswith(b"\n") else line + b"\n")
        sys.stdout.buffer.flush()


def spawn():
    global child
    env = dict(os.environ, MCP_SUPERVISED="1", MCP_RESTARTS=str(restarts), PYTHONUNBUFFERED="1")
    err = open(LOGS / "child-stderr.log", "ab")
    child = subprocess.Popen(CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, env=env, bufsize=0,
                             cwd=str(ROOT))
    log(f"spawned pid={child.pid} restarts={restarts} cmd={CMD}")
    threading.Thread(target=pump_child, args=(child,), daemon=True).start()


def write_child(raw: bytes):
    with state_lock:
        try:
            child.stdin.write(raw if raw.endswith(b"\n") else raw + b"\n")
            child.stdin.flush()
            return True
        except Exception as e:  # child is dead; the pump thread will restart it
            log(f"write to child failed: {e}")
            return False


def pump_child(proc):
    """Forward child stdout to the client; detect death."""
    try:
        for raw in iter(proc.stdout.readline, b""):
            try:
                msg = json.loads(raw)
            except Exception:
                to_client(raw)
                continue
            mid = msg.get("id")
            if "method" not in msg and mid is not None:
                with state_lock:
                    if mid in swallow:
                        swallow.discard(mid)
                        continue
                    pending.pop(mid, None)
            to_client(raw)
    except Exception as e:
        log(f"pump error: {e}")
    if not stopping and proc is child:
        threading.Thread(target=recover, args=(proc,), daemon=True).start()


recent = []


def recover(dead):
    global restarts
    with state_lock:
        if dead is not child:
            return
        code = dead.poll()
        log(f"child exited (code={code}); recovering")
        failed = list(pending.items())
        pending.clear()
        swallow.clear()
    for mid, _ in failed:
        to_client(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {
            "code": -32603, "message": "The tool server restarted (it crashed or was restarted). Please retry the call."}}).encode())
    now = time.time()
    recent[:] = [t for t in recent if now - t < 60] + [now]
    if len(recent) > 3:
        delay = min(30, 2 ** (len(recent) - 3))
        log(f"crash loop ({len(recent)} in 60s): backing off {delay}s")
        time.sleep(delay)
    restarts += 1
    with state_lock:
        spawn()
        if init_req:
            try:
                msg = json.loads(init_req)
                mid = f"sup-init-{restarts}"
                msg["id"] = mid
                swallow.add(mid)
                write_child(json.dumps(msg).encode())
                time.sleep(0.2)
                if init_note:
                    write_child(init_note)
                log("handshake replayed")
            except Exception as e:
                log(f"handshake replay failed: {e}")


def main():
    global init_req, init_note, stopping
    with state_lock:
        spawn()
    stdin = sys.stdin.buffer
    for raw in iter(stdin.readline, b""):
        try:
            msg = json.loads(raw)
        except Exception:
            write_child(raw)
            continue
        method = msg.get("method")
        with state_lock:
            if method == "initialize":
                init_req = raw
            elif method == "notifications/initialized":
                init_note = raw
            if method and "id" in msg:
                pending[msg["id"]] = raw
        if not write_child(raw):
            time.sleep(1.5)  # child just died; recover() restarts it, then retry once
            write_child(raw)
    stopping = True
    log("client closed stdin; shutting down")
    try:
        child.terminate()
    except Exception:
        pass


if __name__ == "__main__":
    main()
