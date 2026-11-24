"""SAFE plugin (its own MCP server).   run.py safe"""
from apps.csi_common import make_app

VERIFIED = ("21.",)


def create(variant=None):
    return make_app("safe", extra_modules=("apps.safe.tools_safe",), verified=VERIFIED)
