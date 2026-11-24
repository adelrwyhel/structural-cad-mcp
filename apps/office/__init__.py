"""Microsoft Office plugin.   run.py office excel|word|powerpoint"""
from .adapter import VARIANTS, OfficeApp, set_instance


def create(variant=None):
    variant = (variant or "excel").lower()
    if variant not in VARIANTS:
        raise SystemExit(f"unknown office variant '{variant}'; use one of {list(VARIANTS)}")
    app = OfficeApp(variant)
    set_instance(app)
    return app
