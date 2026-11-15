"""TWINS for the refresh-lock release (lane llocks, 2026-11-14).

``build_airport.py`` held every ``--refresh-data`` scope's lock for the
WHOLE build (LFLL 1 h 45 min, then KBNA and OTHH back to back), refusing
every other lane's capture and refresh while those builds only computed.

* the data-prep scopes' locks are released when the prep ends, except a
  scope a pre-flight still owes the build; build-written scopes stay held;
* the consistency guarantee holds: a write into a released scope after
  the release is audited (CONTAMINATED in scope) and the ledger stamps the
  run's own refresh from the prep window only;
* the refusal names the holder (pid, lane, tag, start, phase, expected
  release) and ``--wait-lock N`` is an explicit, bounded wait;
* ``lane_worktree.sh down`` matches holder paths by WHOLE component
  (``l2090`` no longer matches ``l2090d``'s processes and locks).
"""
from __future__ import annotations

import importlib
import inspect
import json
import os
import subprocess
import sys
import threading
import time

import pytest

if sys.platform == "win32":                                # pragma: no cover
    pytest.skip("tools/harness is a POSIX-only lane instrument",
                allow_module_level=True)

from test_harness import (_ritual, _tiny_repo, build_mod,  # noqa: E402,F401
                          guard_mod)


@pytest.fixture
def PR(guard_mod):
    return importlib.import_module("prep_release")


class _Lock:
    def __init__(self, scope):
        self.scope, self.held, self.phases = scope, True, []

    def release(self):
        self.held = False

    def set_phase(self, phase, expected):
        self.phases.append((phase, expected))


class _Guard:
    def __init__(self, requested):
        self.requested = set(requested)


class _P:
    def __init__(self):
        self.notes = []

    def note(self, m):
        self.notes.append(m)


DEM = "Elevation_data/+30+030/N30E031.hgt"
OSM = "OSM_data/+30+030/+30+031/+30+031_airports.osm.bz2"
PACK = "Custom Scenery/zPack/Earth nav data/+30+030/+30+031.dsf"


def test_prep_scopes_release_and_build_scopes_stay_held(PR):
    locks = [_Lock(s) for s in ("dem", "osm_layers", "pack_rebake", "rings")]
    guard = _Guard(["dem", "osm_layers", "pack_rebake", "rings"])
    snaps = iter([{"mid": (1, 1)}])
    prep = PR.PrepRelease(locks, guard, lambda: next(snaps), _P())
    assert prep.release(owed={"rings"}) == ["dem", "osm_layers"]
    held = {lk.scope: lk.held for lk in locks}
    assert held == {"dem": False, "osm_layers": False,
                    "pack_rebake": True, "rings": True}
    assert guard.requested == {"pack_rebake", "rings"}
    assert prep.kept_owed == ["rings"]
    assert locks[2].phases and locks[2].phases[0][0] == "build"
    assert "PREP DONE" in prep.prog.notes[0]
    # idempotent: released once, whichever path calls it
    assert prep.release() == ["dem", "osm_layers"]
    rec = prep.record({"mid": (1, 1)})
    assert rec["released_after_prep"] == ["dem", "osm_layers"]
    assert rec["held_through_build"] == ["pack_rebake", "rings"]


def test_nothing_to_release_keeps_the_whole_window_audit(PR):
    prep = PR.PrepRelease([_Lock("pack_rebake")], _Guard(["pack_rebake"]),
                          lambda: pytest.fail("no snapshot owed"))
    assert prep.release() == []
    changes, scopes = prep.audit_changes({}, {PACK: (1, 1)}, {"pack_rebake"})
    assert changes["added"] == [PACK] and scopes == {"pack_rebake"}


def test_a_write_under_the_build_after_release_is_audited(PR, guard_mod):
    """The guarantee: this run's prep write is authorised and ledgered from
    the prep window; ANOTHER lane's write into the same released scope
    after the release CONTAMINATES the run (it is in the input set)."""
    before = {DEM: (1, 1)}
    mid = {DEM: (2, 2), OSM: (1, 1)}                   # this run's prep
    after = {DEM: (3, 3), OSM: (1, 1)}                 # moved under the build
    prep = PR.PrepRelease([_Lock("dem"), _Lock("osm_layers")],
                          _Guard(["dem", "osm_layers"]), lambda: dict(mid))
    prep.release()
    changes, scopes = prep.audit_changes(before, after, {"dem", "osm_layers"})
    assert scopes == set()
    assert changes["modified"] == [DEM] and changes["added"] == []
    # the ledger record is the PREP window's
    assert prep.scope_changes("osm_layers", before, after)["added"] == [OSM]
    assert prep.scope_changes("dem", before, after)["modified"] == [DEM]
    scope = guard_mod.BuildInputScope(tiles=[(30, 31)], icaos=["HECA"])
    off = guard_mod.report_unauthorised_writes(
        changes, scopes, _P(), input_scope=scope, redirected=())
    assert [o["path"] for o in guard_mod.contaminating_writes(off)] == [DEM]
    assert prep.record(after)["build_window_writes"]["modified"] == [DEM]


def test_main_releases_at_the_end_of_the_prep(build_mod):
    """Source twins: the release sits after the re-judge and before the
    build on the patch path; on the tile path ``build_tile`` calls it after
    the bathymetry band admission, carrying the band's owed scopes."""
    src = inspect.getsource(build_mod.main)
    i_judge = src.index("owed = require_refreshed_frame(")
    i_rel = src.index("prep.release(owed_scopes)")
    assert i_judge < i_rel < src.index("result = build_patch_v2(", i_rel)
    assert "on_prep_done=lambda band: prep.release(" in src
    assert "prep.audit_changes(before, after, requested)" in src
    assert "report_unauthorised_writes(audit, audit_scopes" in src
    tile = inspect.getsource(build_mod.build_tile)
    assert (tile.index("require_no_implicit_refresh(band_missing")
            < tile.index("on_prep_done({sc for sc, _a, _w in band_missing})"))
    assert '"--wait-lock"' in inspect.getsource(build_mod)


def test_the_refusal_names_the_holder_and_its_expected_release(
        build_mod, guard_mod, tmp_path, monkeypatch):
    monkeypatch.setattr(guard_mod, "LOCK_DIR", tmp_path / "locks")
    first = build_mod.RefreshLock("dem", lane="/w/lfll/Ortho4XP",
                                  tag="LFLL_t1").acquire()
    try:
        first.set_phase("build", "at the end of the build")
        with pytest.raises(SystemExit) as exc:
            build_mod.RefreshLock("dem", lane="me").acquire()
        msg = str(exc.value)
        for must in ("tag='LFLL_t1'", f"pid={os.getpid()}", "ALIVE",
                     "phase:  build", "at the end of the build",
                     "--wait-lock", "held 0 min"):
            assert must in msg, (must, msg)
        assert "TIMED_OUT" not in msg
    finally:
        first.release()


def test_wait_lock_is_bounded_and_takes_a_released_lock(
        build_mod, guard_mod, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(guard_mod, "LOCK_DIR", tmp_path / "locks")
    monkeypatch.setattr(guard_mod.RefreshLock, "POLL_S", 0.05)
    first = build_mod.RefreshLock("rings", lane="A", tag="a").acquire()
    try:
        t0 = time.time()
        with pytest.raises(SystemExit) as exc:
            build_mod.RefreshLock("rings", lane="B",
                                  wait_minutes=0.005).acquire()   # 0.3 s
        assert "TIMED_OUT" in str(exc.value)
        assert time.time() - t0 < 5
        assert "WAITING up to" in capsys.readouterr().out
        threading.Timer(0.2, first.release).start()
        got = build_mod.RefreshLock("rings", lane="B", tag="b",
                                    wait_minutes=1).acquire()
        assert json.loads(got.path.read_text())["tag"] == "b"
        got.release()
    finally:
        first.release()


def test_down_matches_whole_path_components(tmp_path):
    """``down l2090`` refused on ``l2090d``'s python and lock."""
    main, data, env, _old = _tiny_repo(tmp_path)
    for name in ("l2090", "l2090d"):
        up = _ritual(env, "up", name, "HEAD")
        assert up.returncode == 0, up.stdout + up.stderr
    other = main / ".claude" / "worktrees" / "l2090d"
    (data / ".harness" / "locks").mkdir(parents=True)
    (data / ".harness" / "locks" / "dem.lock").write_text(json.dumps(
        {"scope": "dem", "lane": str(other / "Ortho4XP"), "pid": 1}),
        encoding="utf-8", newline="")
    holder = subprocess.Popen([sys.executable, "-c",
                               "import time; time.sleep(60)",
                               str(other / "Ortho4XP" / "x")])
    try:
        time.sleep(0.3)
        held = _ritual(env, "down", "l2090d")
        assert held.returncode == 2, held.stdout + held.stderr
        down = _ritual(env, "down", "l2090")
        assert down.returncode == 0, down.stdout + down.stderr
        assert not (main / ".claude" / "worktrees" / "l2090").exists()
    finally:
        holder.kill()
        holder.wait()
