"""Unit tests for the safety guard, path validation and output clipping (no CAD program required)."""
import os
import time

import pytest

from mcpkit import core


def test_sandbox_dirs_created_under_test_home():
    assert str(core.SANDBOX).startswith(os.environ["CSI_MCP_HOME"])
    assert core.SANDBOX.is_dir() and core.EXPORTS.is_dir()


# ---------------------------------------------------------------- safe_path
def test_relative_path_goes_to_sandbox():
    p = core.safe_path("model1.edb", (".edb",))
    assert p.startswith(str(core.SANDBOX))


@pytest.mark.parametrize("bad", ["", "..\\x.edb", "C:\\a\\..\\b.edb", "C:\\models\\nul.edb", "a<b.edb", "x.exe"])
def test_safe_path_rejects(bad):
    with pytest.raises(core.GuardError):
        core.safe_path(bad, (".edb",))


def test_overwrite_rules(tmp_path):
    inside = core.SANDBOX / "exists.edb"
    inside.write_text("x")
    with pytest.raises(core.GuardError):
        core.safe_path(str(inside), (".edb",), write=True)                       # exists, no overwrite flag
    assert core.safe_path(str(inside), (".edb",), write=True, overwrite=True)    # inside sandbox: allowed
    outside = tmp_path / "real.edb"
    outside.write_text("x")
    with pytest.raises(core.GuardError):
        core.safe_path(str(outside), (".edb",), write=True, overwrite=True)      # outside sandbox: never
    assert core.safe_path(str(tmp_path / "new.edb"), (".edb",), write=True)      # a NEW file anywhere is fine


# ---------------------------------------------------------------- guard
def test_untitled_rules():
    core.check_target("", empty=True, ours=False, action="t")      # empty untitled: fine
    core.check_target("", empty=False, ours=True, action="t")      # created by the tools: fine
    with pytest.raises(core.GuardError):
        core.check_target("", empty=False, ours=False, action="t")  # someone's unsaved work: blocked


def test_real_file_blocked_then_granted_then_revoked(tmp_path):
    f = tmp_path / "REAL.edb"
    f.write_text("model")
    with pytest.raises(core.GuardError) as e:
        core.check_target(str(f), empty=False, ours=False, action="add_frame")
    assert "allow_edit" in str(e.value)
    backup = core.grant_edit(str(f), 5)
    assert os.path.isfile(backup) and open(backup).read() == "model"
    core.check_target(str(f), empty=False, ours=False, action="add_frame")       # allowed now
    assert core.active_grants()[0]["minutes_left"] > 4
    assert core.revoke_edit(str(f)) == 1
    with pytest.raises(core.GuardError):
        core.check_target(str(f), empty=False, ours=False, action="add_frame")


def test_grant_expires(tmp_path):
    f = tmp_path / "REAL2.edb"
    f.write_text("m")
    core.grant_edit(str(f), 1)
    core._grants[core.norm(str(f))] = time.time() - 1                            # force expiry
    assert not core.is_granted(str(f))
    with pytest.raises(core.GuardError):
        core.check_target(str(f), empty=False, ours=False, action="x")


def test_sandbox_registry_marks_files_as_ours(tmp_path):
    f = tmp_path / "created_by_tools.edb"
    f.write_text("m")
    assert not core.is_sandbox(str(f))
    core.register_sandbox(str(f))
    assert core.is_sandbox(str(f))
    core.check_target(str(f), empty=False, ours=False, action="x")


# ---------------------------------------------------------------- clip / errors
def test_clip_rows():
    obj = {"columns": ["a"], "rows": [["x" * 100] for _ in range(1000)]}
    out = core.clip(obj, limit=5000)
    assert out["truncated"] and 0 < len(out["rows"]) < 1000


def test_clip_small_untouched():
    assert core.clip({"a": 1}) == {"a": 1}


def test_friendly_known_hresult():
    class E(Exception):
        hresult = -2147023174
    assert "closed" in core.friendly(E())
