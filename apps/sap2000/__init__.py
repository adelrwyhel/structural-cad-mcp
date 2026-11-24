"""SAP2000 plugin (its own MCP server).   run.py sap2000"""
from apps.csi_common import make_app

from .legacy_results import KEYS, fetch

VERIFIED = ("26.",)


def create(variant=None):
    return make_app("sap2000", extra_modules=("apps.sap2000.tools_sap2000",), verified=VERIFIED,
                    legacy_fetch=fetch, legacy_keys=KEYS)
