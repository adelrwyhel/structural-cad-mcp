"""ETABS plugin (its own MCP server).   run.py etabs"""
from apps.csi_common import make_app

# version-string prefixes that passed the live suite; everything else is reported as UNVERIFIED by ping()
VERIFIED = ("21.", "22.")


def create(variant=None):
    return make_app("etabs", extra_modules=("apps.etabs.tools_etabs",), verified=VERIFIED)
