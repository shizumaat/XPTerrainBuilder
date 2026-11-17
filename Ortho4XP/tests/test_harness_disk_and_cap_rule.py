"""Owner HARD RULE 2026-11-06: no raising the lane cap, no build on a full disk."""
import collections
import pathlib
import shutil
import sys

import pytest

HARNESS = pathlib.Path(__file__).resolve().parents[1] / "tools" / "harness"
sys.path.insert(0, str(HARNESS))
import build_airport as ba  # noqa: E402


def test_lane_cap_override_cannot_raise():
    src = (HARNESS / "lane_worktree.sh").read_text(encoding="utf-8")
    assert 'cannot raise the cap above $LANE_CAP' in src
    assert "LANE_CAP=16" in src


@pytest.mark.parametrize("tile,free_gb,refused", [
    (True, 29, True), (True, 31, False), (False, 4, True), (False, 6, False)])
def test_disk_floor_gate(monkeypatch, tmp_path, tile, free_gb, refused):
    usage = collections.namedtuple("u", "total used free")
    monkeypatch.setattr(shutil, "disk_usage",
                        lambda _p: usage(0, 0, free_gb * 1e9))
    if refused:
        with pytest.raises(SystemExit, match="HARD RULE"):
            ba.disk_floor_gate(tmp_path, tile=tile)
    else:
        ba.disk_floor_gate(tmp_path, tile=tile)


def test_a_harness_build_is_a_lane_on_the_machine_memory_ledger(
        monkeypatch, tmp_path):
    """Incident 2026-11-17: concurrency is the machine memory ledger's, not
    a build count; a harness build joins it as a lane named by worktree,
    and a role an ancestor claimed (the app's engine) stands."""
    import O4_Machine_Memory as MEMORY
    root = tmp_path / ".claude" / "worktrees" / "lfoo" / "Ortho4XP"
    root.mkdir(parents=True)
    ba.claim_lane_memory(root)
    assert MEMORY.role() == "lane"
    assert MEMORY._label() == "lane lfoo"
    monkeypatch.setenv(MEMORY.ENV_ROLE, "app")
    ba.claim_lane_memory(root)
    assert MEMORY.role() == "app"
    src = (HARNESS / "build_airport.py").read_text(encoding="utf-8")
    assert "at most 4" not in src
