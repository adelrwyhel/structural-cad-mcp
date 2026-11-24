"""AutoCAD plugin.   run.py autocad"""
from .adapter import AutoCadApp, set_instance


def create(variant=None):
    app = AutoCadApp()
    set_instance(app)
    return app
