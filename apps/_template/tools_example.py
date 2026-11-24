"""Example tool module. Every function decorated with @tool becomes an MCP tool automatically.

Rules of thumb
* Docstring = the description Claude sees. Type hints = the input schema. Keep both precise.
* Read tools: @tool().  Tools that change anything: @tool(write=True) -> the app guard runs first.
* Long operations: @tool(timeout=1800).
* Raise RuntimeError("clear message") for expected problems; anything else is converted to a clean error too.
* Return JSON-friendly values (dict/list/str/number). Big results are clipped automatically; add offset/limit.
* Never print() - stdout carries the MCP protocol. Use logging if you need traces.
"""
from mcpkit.core import tool


@tool()
def hello(name: str = "world") -> str:
    """Say hello (read-only example)."""
    return f"hello {name}"


@tool(write=True)
def do_something_risky(value: float) -> str:
    """Example of a tool that modifies the document (blocked on non-sandbox documents by the guard)."""
    return f"would change {value}"
