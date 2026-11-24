# Contributing

Thanks for helping! The project is small on purpose: an engine (`mcpkit/`) plus one folder per application (`apps/<name>/`).

## Setup
```powershell
git clone <your fork>
cd structural-cad-mcp
pip install -e ".[dev]"
python -m pytest            # unit tests, no CAD program needed
```

## Add a tool (30 seconds)
Open any `apps/<app>/tools_*.py` and add:
```python
from mcpkit.core import tool
from .adapter import A            # A.sap() / A.doc() ... the connected program

@tool()                           # read-only
def my_read_tool(x: int) -> dict:
    """What it does (this text is what the AI sees)."""
    ...

@tool(write=True)                 # changes the model/drawing -> guarded
def my_write_tool(name: str) -> str:
    """..."""
```
Rules: precise docstring + type hints; raise `RuntimeError("clear message")` for expected problems; never `print()` (stdout is the MCP channel); paginate anything that can be large; **every tool that changes a document must be `write=True`**.

## Add an application
Copy `apps/_template`, implement `connect/guard/info/current_path`, add tool modules, list them in `modules`. Add the app to `tests/unit/test_plugins.py::CASES` so CI checks it loads.

## Tests
* `tests/unit` - run in CI, must not need any CAD program.
* `tests/live` - need the real program running (they only create *new* sandbox documents). `tests/live/run_matrix.py` runs every installed ETABS/SAP2000/SAFE version.
If you change behaviour for a program version, say which version you tested in the PR.

## Safety rules for changes
* Never weaken the guard (`mcpkit/core.py: check_target`) without a test proving user documents stay protected.
* Read tools must stay read-only: no saving, no unlocking, no "refresh that dirties the file".
* No network calls, no telemetry, no secrets in logs.
