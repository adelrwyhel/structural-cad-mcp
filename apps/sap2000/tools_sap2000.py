"""SAP2000-only tools."""
from mcpkit.core import tool

from apps.csi_common.adapter import A
from apps.csi_common.tools_tables import _result


@tool(unverified=True)
def legacy_api_status() -> dict:
    """Does this SAP2000 version lack the DatabaseTables API (older than v21)? If so the table/result tools use the
    legacy Results.* readers, which have NOT been tested on a real old installation."""
    m = A.sap()
    return {"version": m.GetVersion()[0], "has_database_tables": A.has_tables(m),
            "results_come_from": "DatabaseTables" if A.has_tables(m) else "legacy Results API (unverified)"}


@tool(unverified=True)
def area_forces(where: dict = None, max_rows: int = 200, offset: int = 0) -> dict:
    """Shell/area element forces (Element Forces - Area Shells)."""
    return _result("Element Forces - Area Shells", where, max_rows, offset)
