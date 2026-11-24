"""TEMPLATE for a new application plugin.  Copy this folder to apps/<yourapp>/ and edit.

1. Rename the class / `name` / `title`.
2. Implement connect (reset/connect), guard() and info().
3. Put tools in tools_*.py files (see tools_example.py) and list them in `modules`.
4. Register it for Claude with:
       claude mcp add --scope user <yourapp> -- <python> <mcp-servers>/mcpkit/supervisor.py <mcp-servers>/run.py <yourapp>
(Folders starting with '_' are ignored by tooling; a copy named e.g. 'revit' is picked up by run.py automatically.)
"""
from mcpkit import core
from mcpkit.core import App


class TemplateApp(App):
    name = "template"          # MCP server name (what Claude sees as the prefix)
    title = "Template App"     # window-title prefix of the program
    modules = ("apps._template.tools_example",)   # dotted paths of your tool modules

    def __init__(self):
        self._conn = None

    def reset(self):           # called after a crash/timeout: forget cached connections
        self._conn = None

    def connect(self):         # lazily attach to the RUNNING program; raise a clear error if it is not running
        if self._conn is None:
            raise RuntimeError(f"{self.title} is not running")
        return self._conn

    def guard(self, action: str):
        """Block write tools unless the open document is a sandbox file / empty / created by us.
        Typical body:  core.check_target(path_or_empty_string, empty=is_empty, ours=created_by_us, action=action)"""
        core.check_target("", empty=True, ours=True, action=action)

    def info(self) -> dict:
        return {"program_running": False}


_inst = None


def create(variant=None):
    global _inst
    _inst = TemplateApp()
    return _inst
