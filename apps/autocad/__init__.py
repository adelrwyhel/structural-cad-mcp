"""AutoCAD plugin (its own MCP server).   run.py autocad [year]    e.g.  run.py autocad 2014  (UNVERIFIED version)"""
from .adapter import AutoCadApp, set_instance


def create(variant=None):
    app = AutoCadApp(year=str(variant) if variant else None)
    set_instance(app)
    return app
