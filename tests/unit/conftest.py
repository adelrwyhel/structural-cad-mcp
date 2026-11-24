"""Point the servers' data folders at a temp dir BEFORE mcpkit is imported, so tests never touch real folders."""
import os
import pathlib
import sys
import tempfile

_tmp = tempfile.mkdtemp(prefix="cadmcp_test_")
os.environ["CSI_MCP_HOME"] = _tmp
os.environ.pop("CSI_MCP_ALLOW_EDIT_EXISTING", None)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
