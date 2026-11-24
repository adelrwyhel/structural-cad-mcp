# structural-cad-mcp

**MCP servers that let an AI assistant (Claude and any MCP client) drive ETABS, SAP2000, SAFE and AutoCAD** through their official COM APIs - with a built-in safety guard so your real models are never modified by accident, automatic crash recovery, and a plugin architecture that makes adding tools or whole applications easy.

> Unofficial project. Not affiliated with or endorsed by Computers and Structures, Inc. (CSI), Autodesk or Microsoft. ETABS, SAP2000, SAFE, AutoCAD are trademarks of their owners. You need your own licenses; this repository contains no vendor code, SDKs or binaries.

## What you can do
Ask your assistant things like:
* "Read the story drifts from the open ETABS model and tell me which stories exceed 1/400."
* "Build a 3-story frame in a new model, add loads and combinations, run it and summarize the modal periods."
* "List the layers of the open drawing and measure the total length of the WALLS layer."
* "Export the base reactions to CSV and write a Markdown report."

| Server | Programs / versions | Tools |
|---|---|---|
| `etabs` | ETABS 21 | ~65: model, stories, diaphragms, sections, loads, combos, tables, results, drift/modal checks, design, reports |
| `sap2000` | SAP2000 26 | ~60 |
| `safe` | SAFE 21 | ~55 |
| `autocad` | AutoCAD 2026 (COM) | ~50: layers, drawing, query, edit, blocks, hatch, PDF plot |

Every server also provides `ping`, `server_info`, `restart_server`, `allow_edit`, `revoke_edit`, `edit_status`. (`apps/office` - Excel/Word/PowerPoint - is included as an experimental extra.)

## Supported versions

Only versions that were **actually tested** are supported. **Older versions are not supported** - they may partly work, but they differ in API and are not tested or maintained.

| Program | Supported (tested) | Not supported |
|---|---|---|
| ETABS | **21** (v21.2.0) | 22 (not verified yet), 2016, 19, 20 |
| SAP2000 | **26** (v26.2.0) | 25 (not verified), 20 and older |
| SAFE | **21** (v21.2.0) | 2016 and older |
| AutoCAD | **2026** | anything older |

Notes: SAP2000 20 has no `DatabaseTables` API, so the table/result tools cannot work there. Every tool listed passes the live suite in `tests/live` (ETABS 61, SAP2000 47, SAFE 45, AutoCAD 61 checks, including the safety-guard tests). Contributions that verify or add other versions are welcome (see `tests/live/run_matrix.py`).

## Safety model (important)
1. **Read tools work on any open model/drawing.** They never save, unlock or "refresh dirty" the file.
2. **Write tools only act on documents the tools created** (inside `sandbox/`) or on empty new ones. On anything else they return `BLOCKED ...` *before* touching it.
3. **Editing your real document, when you ask for it:** the assistant calls `allow_edit(minutes, path)`. That makes a backup copy first, unlocks **that one file** for a limited time, logs it to `logs/audit.log`, and `revoke_edit` (or expiry) locks it again. The tool's description tells the AI to call it only when *you* explicitly request a change.
4. Files: extension allow-list, no `..`/device names, never overwrite outside `sandbox/` and `exports/`.
5. AutoCAD `send_command` blocks save/close/open/shell/file-delete commands.
6. Owner-only override for power users: environment variable `CSI_MCP_ALLOW_EDIT_EXISTING=1` (still makes a backup).

## Stability and recovery
* All COM calls run on one dedicated worker thread, with per-call timeouts; a hung call is abandoned and the worker is replaced.
* Reads auto-reconnect once if the program was restarted; "application busy" rejections are retried.
* A broken tool module never stops the others (`server_info` shows what failed to load).
* `mcpkit/supervisor.py` restarts a crashed server in about a second and replays the MCP handshake so the client stays connected (with crash-loop back-off).
* Logs: `logs/<server>.log`, `logs/audit.log`, `logs/supervisor.log`, `logs/faulthandler.log`.

## Install
Requirements: Windows, Python 3.10+, the program(s) installed and licensed.
```powershell
git clone https://github.com/adelrwyhel/structural-cad-mcp
cd structural-cad-mcp
pip install -e .
```
Register with Claude Code (use the absolute path of your python and the repo):
```powershell
$py  = (Get-Command python).Source
$dir = (Get-Location).Path
claude mcp add --scope user etabs   -- $py "$dir\mcpkit\supervisor.py" "$dir\run.py" csi etabs
claude mcp add --scope user sap2000 -- $py "$dir\mcpkit\supervisor.py" "$dir\run.py" csi sap2000
claude mcp add --scope user safe    -- $py "$dir\mcpkit\supervisor.py" "$dir\run.py" csi safe
claude mcp add --scope user autocad -- $py "$dir\mcpkit\supervisor.py" "$dir\run.py" autocad
```
Other MCP clients: the same command line as a stdio server.

Open the program (and, for editing real work, work on a **copy** in `sandbox/` or ask the assistant to unlock your file with `allow_edit`).
Helpers: `list_installations` shows installed versions, `launch_program(version)` starts one. Only one version of a program should run at a time (the API attaches to the running instance).

## Architecture
```
run.py                      entry: run.py csi etabs|sap2000|safe | run.py autocad | run.py office excel|word|powerpoint
mcpkit/core.py              engine: plugin loader, COM worker, timeouts, guard, grants, clipping, recovery
mcpkit/supervisor.py        crash-proof launcher
apps/<app>/adapter.py       connection + guard hooks for the program
apps/<app>/tools_*.py       tools: any function decorated with @tool() is registered automatically
apps/_template/             copy to add a new application
tests/unit                  CI tests (no CAD program needed)
tests/live                  live tests + version matrix runner (need the programs installed)
```
Adding a tool = one decorated function; adding an application = copy `_template`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Disclaimer
This software is provided "as is" (MIT License). It automates third-party engineering software; **results must be verified by a qualified engineer**. The authors accept no liability for modeling errors, lost data or design decisions. Always keep backups of your models.

## License
[MIT](LICENSE). See also [SECURITY.md](SECURITY.md).