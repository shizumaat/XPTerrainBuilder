"""Issue #51 — a press's own tiles are never "a tile this build is not
building".

THE DEFECT (engine-stderr batch of 2026-09-21): tiles -13-078 and -13-077
were selected in ONE press; at build time each judged the other cold and
printed the tile-edge skip line naming it, so a class-S airport crossing
between them lost its patch although both tiles were being built in that
very run.  The preflight excluded the press's cells; the build-time
``is_cold`` in ``derive_auto_patch_selection`` did not.

Fixed at the single site: ONE predicate, ``VMAP.boundary_is_cold(batch)``
(wrapped by ``boundary_cold_predicate``),
shared by both call sites, fed by the press's tile set that
``EngineSession.build`` / ``enqueue_build`` land (and that ``parallel.py``
carries to each worker child beside the boundary policy).  Spec
``docs/specs/insets-follow-patch-set-spec.md`` rev 3 §C.2/§C.3, RULINGS
2026-09-18j.  Headless, ``tmp_path``, no network, no corpus.
"""
from __future__ import annotations

import inspect
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_Vector_Map as VMAP                                 # noqa: E402
from auto_patch import selection as SEL                      # noqa: E402

#: -13-077 (home) and -13-078 (its west neighbour): an apron 60 m east
#: of the lon -77 line is class S into -13-078 (test_boundary_airports b).
HOME = (-13, -77)
WEST = (-13, -78)
LAT = -12.15
M_PER_DEG_LON = 108800.0
M_PER_DEG_LAT = 111132.0


def _apron_apt(tmp_path):
    w = -77.0 + 60.0 / M_PER_DEG_LON
    e = -77.0 + 260.0 / M_PER_DEG_LON
    (s, n) = (LAT, LAT + 200.0 / M_PER_DEG_LAT)
    body = "\n".join(["110 1 0.25 0.0 PAV",
                      "111 %.7f %.7f" % (s, w), "111 %.7f %.7f" % (s, e),
                      "111 %.7f %.7f" % (n, e), "113 %.7f %.7f" % (n, w)])
    path = tmp_path / "apron.dat"
    path.write_text("A\n1000 Version\n\n1 10 0 0 ZZZZ Test\n%s\n99\n" % body,
                    encoding="utf-8")
    return str(path)


@pytest.fixture
def home_tile(monkeypatch, tmp_path):
    """-13-077 with one class-S airport crossing into a COLD -13-078, the
    REAL ``boundary_skipper`` and the unattended default (skip)."""
    apt = _apron_apt(tmp_path)
    monkeypatch.setattr(VMAP, "BOUNDARY_POLICY", None, raising=False)
    monkeypatch.setattr(VMAP, "BOUNDARY_BATCHES", {}, raising=False)
    monkeypatch.setattr(VMAP.CFG, "auto_patch_boundary", "Ask",
                        raising=False)
    monkeypatch.setattr(VMAP, "tile_frame_is_warm", lambda lat, lon: False)
    monkeypatch.setattr(VMAP, "resolve_cifp_dir_for_tile",
                        lambda tile: str(tmp_path))
    monkeypatch.setattr(VMAP, "resolved_auto_patch_mode",
                        lambda tile: "ICAO")
    monkeypatch.setattr(VMAP, "manual_patch_icaos", lambda tile: set())
    monkeypatch.setattr(SEL, "resolved_inset_mode", lambda tile: "None")
    candidate = SEL.PatchCandidate("ZZZZ", "x.dat", {}, "patch", "", apt)

    def select(tile, cifp, mode, manual_icaos=None, boundary=None):
        boundary("ZZZZ", {}, candidate)
        return []

    monkeypatch.setattr(SEL, "select_patch_airports", select)
    return SimpleNamespace(lat=HOME[0], lon=HOME[1])


def test_a_two_tile_press_prints_no_skip_line_for_its_sibling(
        home_tile, capsys):
    """THE DEFECT, pinned: both tiles in one press -> the sibling is not
    cold, nothing is skipped, no line."""
    VMAP.note_boundary_batch([HOME, WEST])

    VMAP.derive_auto_patch_selection(home_tile)

    out = capsys.readouterr().out
    assert "SKIPPED" not in out
    assert "-13-078" not in out
    assert home_tile.boundary_neighbours == []
    # ... but its cold frame is still warmed before this tile's patch
    # reads across the line (§D.2), under the unattended skip too.
    assert home_tile.boundary_siblings == [WEST]


def test_a_warm_sibling_needs_no_warming(home_tile, monkeypatch):
    monkeypatch.setattr(VMAP, "tile_frame_is_warm",
                        lambda lat, lon: (lat, lon) == WEST)
    VMAP.note_boundary_batch([HOME, WEST])

    VMAP.derive_auto_patch_selection(home_tile)

    assert home_tile.boundary_siblings == []


def test_a_one_tile_press_still_prints_the_skip_line(home_tile, capsys):
    """The control: the same airport, the neighbour NOT in the press ->
    the skip line names it, exactly as before."""
    VMAP.note_boundary_batch([HOME])

    VMAP.derive_auto_patch_selection(home_tile)

    out = capsys.readouterr().out
    assert "reach into 1 tile(s)" in out and "-13-078" in out
    assert home_tile.boundary_neighbours == [WEST]


def test_an_undeclared_tile_is_its_own_one_cell_batch(home_tile, capsys):
    """The harness ``--tile`` path declares no press: unchanged behaviour."""
    VMAP.derive_auto_patch_selection(home_tile)

    assert "-13-078" in capsys.readouterr().out


def test_a_later_one_tile_press_replaces_the_earlier_batch(home_tile,
                                                           capsys):
    VMAP.note_boundary_batch([HOME, WEST])
    VMAP.note_boundary_batch([HOME])

    VMAP.derive_auto_patch_selection(home_tile)

    assert "-13-078" in capsys.readouterr().out


# ── one spelling at both call sites ───────────────────────────────────
def test_the_preflight_and_the_build_time_check_share_one_is_cold():
    """No lambda re-spells ``is_cold`` at either call site."""
    from o4_engine import session

    preflight = inspect.getsource(session.EngineSession._boundary_preflight)
    build_time = inspect.getsource(VMAP.derive_auto_patch_selection)
    assert "VMAP.boundary_cold_predicate(" in preflight
    assert "boundary_cold_predicate(" in build_time
    for source in (preflight, build_time):
        assert "is_cold=lambda" not in source
    wrapper = inspect.getsource(VMAP.boundary_cold_predicate)
    assert "boundary_is_cold(batch)" in wrapper


def test_the_predicate_excludes_the_batch_and_reads_warmth(monkeypatch):
    monkeypatch.setattr(VMAP, "tile_frame_is_warm",
                        lambda lat, lon: (lat, lon) == (0, 1))
    is_cold = VMAP.boundary_is_cold([[0, 0], (0, 2)])   # JSON lists too
    assert not is_cold((0, 0))      # in the press
    assert not is_cold((0, 2))      # in the press
    assert not is_cold((0, 1))      # warm
    assert is_cold((0, 3))          # neither


# ── the batch reaches a worker child ──────────────────────────────────
def test_build_takes_the_batch_keyword():
    from o4_engine.session import EngineSession

    parameters = inspect.signature(EngineSession.build).parameters
    assert parameters["boundary_batch"].default is None


def test_the_batch_reaches_a_worker_childs_tile_arguments():
    from o4_engine import parallel

    class _Bare(parallel.ParallelBuildRun):
        def __getattr__(self, name):
            if name.startswith("_"):
                value = {} if name != "_queue" else []
                object.__setattr__(self, name, value)
                return value
            raise AttributeError(name)

    run = _Bare.__new__(_Bare)
    run._children = []
    run._queue = []
    run._total = 0
    parallel.ParallelBuildRun._admit_batch_locked(
        run, [HOME, WEST], "BI", 16, "", (True, False, False))
    for tile in (HOME, WEST):
        assert run._tile_arguments[tile]["boundary_batch"] == [
            list(HOME), list(WEST)]


def test_a_child_lands_the_json_batch(monkeypatch):
    """The child receives ``[[lat, lon], ...]`` over JSON; its one tile
    then sees its siblings."""
    monkeypatch.setattr(VMAP, "BOUNDARY_BATCHES", {}, raising=False)
    VMAP.note_boundary_batch([list(HOME), list(WEST)])
    assert VMAP.boundary_batch_of(*HOME) == frozenset({HOME, WEST})
    assert VMAP.boundary_batch_of(*WEST) == frozenset({HOME, WEST})
    assert VMAP.boundary_batch_of(1, 1) == frozenset({(1, 1)})


# ── which frames step 1 warms ─────────────────────────────────────────
def test_a_sibling_is_warmed_under_either_policy():
    for policy in ("skip", "neighbour"):
        tile = SimpleNamespace(lat=HOME[0], lon=HOME[1],
                               boundary_policy=policy,
                               boundary_neighbours=[],
                               boundary_siblings=[WEST])
        assert [c for (c, _r) in VMAP.boundary_cells_to_warm(tile)] == [WEST]


def test_an_outside_neighbour_is_warmed_only_on_build_adjacent():
    outside = (-14, -77)
    skip = SimpleNamespace(lat=HOME[0], lon=HOME[1], boundary_policy="skip",
                           boundary_neighbours=[outside],
                           boundary_siblings=[])
    assert VMAP.boundary_cells_to_warm(skip) == []
    adjacent = SimpleNamespace(lat=HOME[0], lon=HOME[1],
                               boundary_policy="neighbour",
                               boundary_neighbours=[outside],
                               boundary_siblings=[WEST])
    assert [c for (c, _r) in VMAP.boundary_cells_to_warm(adjacent)] == [
        outside, WEST]
