"""SAFE-only tools (slab / mat / punching results). Table based; UNVERIFIED on a model that has these results."""
from mcpkit.core import tool

from apps.csi_common.tools_tables import _result


@tool(unverified=True)
def slab_strip_forces(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Design-strip forces (needs strips defined and the model analyzed)."""
    return _result("Strip Forces", where, max_rows, offset)


@tool(unverified=True)
def punching_shear_checks(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Punching-shear design results (needs design run in the program)."""
    return _result("Concrete Slab Design 3 - Punching Shear Data", where, max_rows, offset)


@tool(unverified=True)
def soil_pressures(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Soil pressure results for mats/footings."""
    return _result("Soil Pressures", where, max_rows, offset)
