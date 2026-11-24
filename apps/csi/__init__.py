"""CSI family plugin: ETABS, SAP2000, SAFE.   run.py csi etabs|sap2000|safe"""
from .adapter import CsiApp, VARIANTS, set_instance


def create(variant=None):
    variant = (variant or "sap2000").lower()
    if variant not in VARIANTS:
        raise SystemExit(f"unknown CSI variant '{variant}'; use one of {list(VARIANTS)}")
    app = CsiApp(variant)
    set_instance(app)
    return app
