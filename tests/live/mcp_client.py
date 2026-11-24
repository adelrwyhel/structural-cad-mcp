"""Tiny MCP test client: starts a server through the supervisor and calls tools over real stdio.

Usage (library):  from mcp_client import Session
    with Session("csi", "etabs") as s:  print(s.call("ping"))
"""
import asyncio
import json
import pathlib
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = pathlib.Path(__file__).resolve().parents[2]


class Session:
    def __init__(self, *app_args, supervised=True):
        script = [str(ROOT / "mcpkit" / "supervisor.py")] if supervised else []
        self.params = StdioServerParameters(command=sys.executable,
                                            args=script + [str(ROOT / "run.py"), *app_args])
        self.loop = asyncio.new_event_loop()

    def __enter__(self):
        self._stack = self.loop.run_until_complete(self._open())
        return self

    async def _open(self):
        from contextlib import AsyncExitStack
        st = AsyncExitStack()
        r, w = await st.enter_async_context(stdio_client(self.params))
        self.session = await st.enter_async_context(ClientSession(r, w))
        await self.session.initialize()
        return st

    def tools(self):
        res = self.loop.run_until_complete(self.session.list_tools())
        return [t.name for t in res.tools]

    def call(self, _tool, **args):
        async def go():
            return await self.session.call_tool(_tool, args)
        res = self.loop.run_until_complete(asyncio.wait_for(go(), 600))
        blocks = [getattr(c, "text", "") for c in res.content]
        text = "\n".join(blocks)

        def parse(t):
            try:
                return json.loads(t)
            except Exception:
                return t
        data = parse(blocks[0]) if len(blocks) == 1 else [parse(b) for b in blocks]
        return {"error": True, "message": text} if res.is_error else data

    def __exit__(self, *a):
        try:
            self.loop.run_until_complete(self._stack.aclose())
        except Exception:
            pass
        self.loop.close()



