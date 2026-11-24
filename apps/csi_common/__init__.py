"""Shared CSI library used by the ETABS, SAP2000 and SAFE plugins (not a plugin itself)."""
from .adapter import CsiApp, VARIANTS, set_instance


def make_app(prog, extra_modules=(), verified=(), legacy_fetch=None, legacy_keys=()):
    app = CsiApp(prog, extra_modules=extra_modules, verified=verified, legacy_fetch=legacy_fetch, legacy_keys=legacy_keys)
    set_instance(app)
    return app
