"""Structure + crash-recovery test (needs NO CAD program running)."""
import sys, time, subprocess, json
from mcp_client import Session

app = sys.argv[1:] or ["etabs"]
with Session(*app) as s:
    names = s.tools()
    print("tools:", len(names))
    info = s.call("server_info")
    bad = {k: v for k, v in info["modules"].items() if not v["ok"]}
    print("modules:", {k: len(v["tools"]) for k, v in info["modules"].items()}, "FAILED:", bad)
    print("ping:", json.dumps(s.call("ping"))[:200])
    print("restarts before:", info["supervisor_restarts"])
    # crash 1: process exits via restart_server tool
    print("restart_server:", s.call("restart_server"))
    time.sleep(3)
    print("after restart ping:", json.dumps(s.call("ping"))[:120])
    print("restarts after:", s.call("server_info")["supervisor_restarts"])
    # crash 2: hard kill of the child while idle
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process -Filter \"Name LIKE 'python%'\" | Where-Object { $_.CommandLine -match 'run.py' -and $_.CommandLine -notmatch 'supervisor' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; $_.ProcessId }"],
        capture_output=True, text=True)
    print("killed child pids:", out.stdout.split())
    time.sleep(3)
    r = s.call("server_info")
    print("after kill: restarts =", r.get("supervisor_restarts"), "ok =", "error" not in r)

