"""Tests for cross-tile build coordination
(docs/specs/parallel-tile-builds.md §3.7–3.8): the parent-side
OpenStreetMap cache warmer, the assignment gate that keeps a warming
tile off the workers, and the phase-aware orchestrator's resource-class
limits.

Headless, no network: the warmer's download modules are stubbed through
``sys.modules`` (the warmer imports them lazily inside its thread), and
the suite-wide ``O4_DISABLE_OSM_WARMER`` guard from ``conftest.py`` is
lifted only inside the tests that exercise the warmer itself.  Worker
children are the stub protocol speaker from
``tests/fixtures/stub_engine_worker.py``, which writes per-step
``stepstart_/stepend_`` marker files so class-concurrency claims can be
proven from wall-clock intervals.
"""

from __future__ import annotations

import os
import sys
import time
import types
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from o4_engine import parallel
from o4_engine.events import RunDone
from o4_engine.session import EngineSession

STUB_WORKER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures",
    "stub_engine_worker.py",
)


@pytest.fixture
def stub_worker_command(monkeypatch):
    monkeypatch.setattr(
        parallel, "tile_worker_command",
        lambda: [sys.executable, STUB_WORKER],
    )


@pytest.fixture
def collector():
    return []


def _run_build(session, events, tiles, slots, timeout=25.0,
               do_imagery=False):
    done = []

    def collect(event):
        events.append(event)
        if isinstance(event, RunDone):
            done.append(event)

    session.subscribe(collect)
    assert session.build(
        tiles, "STUBPROVIDER", 16, "", do_vector=True,
        do_imagery=do_imagery, slots=slots,
    )
    deadline = time.time() + timeout
    while not done and time.time() < deadline:
        time.sleep(0.02)
    assert done, "RunDone never arrived"
    return done[0]


def _install_warm_stubs(monkeypatch, warm_log, layer_seconds=0.02):
    """Stub the warmer's lazily imported modules through sys.modules."""

    def fake_queries_to_layer(queries, layer, lat, lon, tags,
                              cached_suffix="", node_tags_of_interest=[],
                              cache_schema=""):
        time.sleep(layer_seconds)
        warm_log.append(((lat, lon), cached_suffix, time.time()))
        return 1

    fake_osm = types.ModuleType("O4_OSM_Utils")
    fake_osm.OSM_layer = lambda: object()
    fake_osm.OSM_queries_to_OSM_layer = fake_queries_to_layer

    fake_vmap = types.ModuleType("O4_Vector_Map")
    fake_vmap.osm_layer_warm_specifications = lambda tile: [
        ("airports", ["q"], ["all"], [], ""),
        ("coastline", ["q"], [], [], ""),
    ]

    fake_cfg = types.ModuleType("O4_Config_Utils")

    class _Tile:
        def __init__(self, lat, lon, build_dir):
            self.lat, self.lon = lat, lon

        def read_from_config(self):
            return 1

    fake_cfg.Tile = _Tile
    monkeypatch.setitem(sys.modules, "O4_OSM_Utils", fake_osm)
    monkeypatch.setitem(sys.modules, "O4_Vector_Map", fake_vmap)
    monkeypatch.setitem(sys.modules, "O4_Config_Utils", fake_cfg)


def _step_interval(tmp_path, tile, step):
    start = tmp_path / ("stepstart_%d_%d_%s" % (tile[0], tile[1], step))
    end = tmp_path / ("stepend_%d_%d_%s" % (tile[0], tile[1], step))
    assert start.exists() and end.exists(), (
        "missing markers for %s %s" % (tile, step))
    return float(start.read_text()), float(end.read_text())


def _max_concurrency(intervals):
    """Peak overlap count over a list of (start, end) intervals."""
    boundary_events = sorted(
        [(start, 1) for start, _ in intervals]
        + [(end, -1) for _, end in intervals]
    )
    active = peak = 0
    for _, delta in boundary_events:
        active += delta
        peak = max(peak, active)
    return peak


# ---------------------------------------------------------------------
# The dispatcher gates (unit level)
# ---------------------------------------------------------------------
class _FakeChild:
    def __init__(self):
        self.tile = None
        self.running_step = None
        # Set by the dispatcher: the resource class actually occupied
        # (the vector step swaps it mid-flight for the auto-patch solve).
        self.step_class = None
        self.autopatch_pending = None
        self.step_failed = False
        self.cancelling = False
        self.retired = False
        self.started = []

    def start_step(self, step_key, build_arguments):
        self.running_step = step_key
        self.started.append((self.tile, step_key))
        return True

    def send(self, payload):
        return True


def _bare_run(tiles, slots):
    return parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        tiles, "P", 16, "", (True, False, False), slots,
    )


def test_new_tile_skips_the_tile_being_warmed():
    run = _bare_run([(10, 10), (11, 11)], 2)
    child = _FakeChild()
    run._warming_tile = (10, 10)
    with run._lock:
        assert run._start_new_tile_locked(child) is True
    assert child.tile == (11, 11), "must skip the warming tile"
    # Only the warming tile left: nothing assignable.
    other = _FakeChild()
    with run._lock:
        assert run._start_new_tile_locked(other) is False
    assert (10, 10) in run._queue, "the warming tile stays queued"


def test_step_dispatch_respects_class_capacity():
    tiles = [(10, index) for index in range(5)]
    run = _bare_run(tiles, 5)
    # program = [vector, mesh, masks]; the osm cap is 4 (owner ruling
    # 2026-07-30, "4 OSM + 4 imagery").
    children = [_FakeChild() for _ in tiles]
    with run._lock:
        for child in children[:4]:
            assert run._start_new_tile_locked(child) is True
        # The fifth tile's first step is osm-class and the cap is 4.
        assert run._start_new_tile_locked(children[4]) is False
    assert children[4].tile is None
    assert run._class_active["osm"] == 4


def test_blocked_children_dispatch_finish_first():
    run = _bare_run([(10, 10), (11, 11)], 2)
    ahead, behind = _FakeChild(), _FakeChild()
    ahead.tile, behind.tile = (10, 10), (11, 11)
    run._children = [behind, ahead]
    run._next_step_index = {(10, 10): 2, (11, 11): 1}  # masks vs mesh
    run._queue.clear()
    # Compute capacity of exactly one (slots=2): only the LATER step
    # (ahead, masks) may start.
    run._class_limits = {"osm": 2, "imagery": 2, "compute": 1}
    with run._lock:
        run._dispatch_locked()
    assert ahead.running_step == "masks"
    assert behind.running_step is None


def test_osm_and_imagery_budgets_are_independent():
    """A full imagery class must not block a tile's vector step — the
    two classes exhaust SEPARATE servers (spec §3.8, makespan goal)."""
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        [(10, 10), (11, 11), (12, 12)], "P", 16, "",
        (True, True, False), 4,
    )
    # program = [vector, mesh, masks, imagery]
    imagery_one, imagery_two, fresh = (
        _FakeChild(), _FakeChild(), _FakeChild())
    imagery_one.tile, imagery_two.tile = (10, 10), (11, 11)
    run._children = [imagery_one, imagery_two, fresh]
    run._next_step_index = {(10, 10): 3, (11, 11): 3}
    run._queue.clear()
    run._queue.append((12, 12))
    with run._lock:
        assert run._try_start_step_locked(imagery_one) is True
        assert run._try_start_step_locked(imagery_two) is True
        assert run._class_active["imagery"] == 2
        # Imagery is saturated, yet a NEW tile's vector step starts.
        assert run._start_new_tile_locked(fresh) is True
    assert fresh.running_step == "vector"


def test_mesh_memory_admission_gate():
    run = _bare_run([(10, 10), (11, 11)], 3)
    big, other = _FakeChild(), _FakeChild()
    big.tile, other.tile = (10, 10), (11, 11)
    run._children = [big, other]
    run._queue.clear()
    run._next_step_index = {(10, 10): 1, (11, 11): 1}  # both at mesh
    run._mesh_memory_estimates = {(10, 10): 10.0, (11, 11): 10.0}
    run._memory_budget = 12.0
    with run._lock:
        assert run._try_start_step_locked(big) is True
        # Two 10 GB meshes exceed the 12 GB budget: the second waits.
        assert run._try_start_step_locked(other) is False
        assert run._memory_in_use == 10.0
        # Releasing the first admits the second.
        run._release_step_resources_locked(big)
        assert run._try_start_step_locked(other) is True
        assert run._memory_in_use == 10.0


def test_mesh_memory_gate_always_admits_one():
    """A single tile must never deadlock, however big its raster."""
    run = _bare_run([(10, 10)], 2)
    child = _FakeChild()
    child.tile = (10, 10)
    run._children = [child]
    run._queue.clear()
    run._next_step_index = {(10, 10): 1}
    run._mesh_memory_estimates = {(10, 10): 50.0}
    run._memory_budget = 8.0
    with run._lock:
        assert run._try_start_step_locked(child) is True


# ---------------------------------------------------------------------
# Compute admission: cores, bounded by the projected-memory ceiling
# (docs/specs/apron-string-and-scheduling-spec.md §A.2)
# ---------------------------------------------------------------------
def test_compute_class_limit_is_the_core_count(monkeypatch):
    import O4_Parallel_Utils as PARALLEL_UTILS

    monkeypatch.delenv("O4_CACHE_AWARE_ADMISSION", raising=False)
    monkeypatch.setattr(PARALLEL_UTILS, "machine_core_count", lambda: 18)
    # Cores, not slots: a run of 4 children on an 18-core machine may
    # still grow to 18 compute tiles as its pool grows.
    assert parallel.compute_class_limit(4) == 18
    assert parallel.class_limits(4)["compute"] == 18
    # Gate off: the pre-2026-07-30 rule, the slot count.
    monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", "0")
    assert parallel.compute_class_limit(4) == 4


def test_memory_budget_is_eighty_percent_of_available(monkeypatch):
    import O4_Parallel_Utils as PARALLEL_UTILS

    monkeypatch.delenv("O4_CACHE_AWARE_ADMISSION", raising=False)
    monkeypatch.setattr(
        PARALLEL_UTILS, "machine_available_memory_gigabytes", lambda: 40.0)
    assert parallel.step_memory_budget_gigabytes() == pytest.approx(32.0)
    # Floored at one default estimate: a single tile never deadlocks.
    monkeypatch.setattr(
        PARALLEL_UTILS, "machine_available_memory_gigabytes", lambda: 0.5)
    assert parallel.step_memory_budget_gigabytes() == pytest.approx(
        parallel.MESH_MEMORY_DEFAULT_GB)


def test_memory_projection_covers_non_mesh_steps():
    """The projection is no longer mesh-only: a compute-class step with
    an estimate is admitted against the same ceiling (spec §A.2)."""
    tiles = [(10, 10), (11, 11), (12, 12)]
    run = _bare_run(tiles, 3)
    run._queue.clear()
    children = [_FakeChild() for _ in tiles]
    for child, tile in zip(children, tiles):
        child.tile = tile
    run._children = list(children)
    run._next_step_index = {tile: 2 for tile in tiles}      # all at masks
    run._memory_budget = 2.5                                 # 1.0 GB each
    with run._lock:
        assert run._try_start_step_locked(children[0]) is True
        assert run._try_start_step_locked(children[1]) is True
        assert run._memory_in_use == pytest.approx(2.0)
        # A third 1 GB masks step would exceed 2.5 GB.
        assert run._try_start_step_locked(children[2]) is False
        run._release_step_resources_locked(children[0])
        assert run._memory_in_use == pytest.approx(1.0)
        assert run._try_start_step_locked(children[2]) is True


def test_memory_projection_is_mesh_only_when_gated_off(monkeypatch):
    monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", "0")
    tiles = [(10, 10), (11, 11), (12, 12)]
    run = _bare_run(tiles, 3)
    run._queue.clear()
    children = [_FakeChild() for _ in tiles]
    for child, tile in zip(children, tiles):
        child.tile = tile
    run._children = list(children)
    run._next_step_index = {tile: 2 for tile in tiles}      # all at masks
    run._memory_budget = 0.1
    with run._lock:
        for child in children:
            assert run._try_start_step_locked(child) is True
        assert run._memory_in_use == 0.0


def test_mesh_memory_estimates_follow_elevation_level():
    assert parallel.mesh_memory_estimate_gigabytes("1") == 18.0
    assert parallel.mesh_memory_estimate_gigabytes("5") == 8.0
    assert parallel.mesh_memory_estimate_gigabytes("auto") == 2.0
    assert parallel.mesh_memory_estimate_gigabytes(None) == 2.0
    assert parallel.mesh_memory_estimate_gigabytes("garbage") == 2.0


# ---------------------------------------------------------------------
# The vector step's class split: fetch holds the osm token, the
# auto-patch solve does not (docs/specs/vector-step-class-split-spec.md
# §2).  These are the token-accounting tests of its §4.
# ---------------------------------------------------------------------
def _autopatch_begin(run, child, airports=("ICAO",)):
    run._on_child_event(child, {
        "event": "AutoPatchBegin", "airports": list(airports),
        "lat": child.tile[0], "lon": child.tile[1]})


def _autopatch_terminal(run, child, airport="ICAO", status="done"):
    run._on_child_event(child, {
        "event": "AutoPatchProgress", "airport": airport, "done": 1.0,
        "total": 1.0, "label": "Done", "status": status,
        "lat": child.tile[0], "lon": child.tile[1]})


def _fetching_run(tiles, slots):
    """A run with every child started on its tile's vector step."""
    run = _bare_run(tiles, slots)
    children = [_FakeChild() for _ in tiles]
    run._children = list(children)
    with run._lock:
        for child in children:
            run._start_new_tile_locked(child)
    return run, children


def test_solve_phase_releases_the_osm_token_at_once():
    """The token freed by a tile entering the solve is handed to a
    QUEUED tile immediately — that is the whole point of the split."""
    tiles = [(10, index) for index in range(5)]
    run, children = _fetching_run(tiles, 5)
    first = children[0]
    spare = children[4]
    # Only four tiles fetch (osm cap 4); the fifth child stayed idle.
    assert run._class_active["osm"] == 4
    assert spare.tile is None
    _autopatch_begin(run, first)
    assert first.step_class == "compute", "the solve is compute-class"
    assert first.running_step == "vector", "still the same step"
    assert run._class_active["compute"] == 1
    # The fifth tile started FETCHING on the freed token, same instant.
    assert spare.tile == (10, 4)
    assert spare.running_step == "vector"
    assert run._class_active["osm"] == 4


def test_many_tiles_solve_concurrently_past_the_osm_cap(monkeypatch):
    """Four tiles in the solve at once with an osm cap of two.

    Each release lets the next queued tile fetch, which then reaches its
    own solve — so the steady state is every worker solving.
    """
    monkeypatch.setenv("O4_OSM_CLASS_LIMIT", "2")
    tiles = [(10, i) for i in range(4)]
    run, children = _fetching_run(tiles, 4)
    for child in children:
        if child.tile is not None and child.step_class == "osm":
            _autopatch_begin(run, child)
    solving = [c for c in children if c.step_class == "compute"]
    assert len(solving) == 4, (
        "the solve must not be bounded by the osm cap, got %d"
        % len(solving))
    assert run._class_active["osm"] == 0
    assert run._class_active["compute"] == 4


def test_vector_tail_takes_the_osm_token_back():
    """The step's remainder can still touch the network, so the tile
    re-enters the osm class when its LAST airport finishes."""
    run, (child,) = _fetching_run([(10, 10)], 2)
    _autopatch_begin(run, child, ("AAAA", "BBBB"))
    assert run._class_active["osm"] == 0
    _autopatch_terminal(run, child, "AAAA")
    assert child.step_class == "compute", "one airport is still solving"
    _autopatch_terminal(run, child, "BBBB", status="fail")
    assert child.step_class == "osm"
    assert run._class_active["osm"] == 1
    assert run._class_active["compute"] == 0


def test_returning_tails_hold_the_osm_class_shut(monkeypatch):
    """Tiles that came back for their vector tail occupy the osm class,
    so no NEW tile is dispatched into it while they drain.

    Re-acquiring may over-subscribe the cap (the child is already
    running; the parent cannot refuse it) — every gate compares ``>=``,
    so the effect is to shut the class rather than to let the tails run
    ALONGSIDE a full complement of new fetchers, which is what simply
    never re-acquiring would do.
    """
    monkeypatch.setenv("O4_OSM_CLASS_LIMIT", "2")
    tiles = [(10, i) for i in range(4)]
    run, children = _fetching_run(tiles, 4)
    fetching = [c for c in children if c.running_step == "vector"]
    assert len(fetching) == 2
    for child in fetching:                      # both enter the solve
        _autopatch_begin(run, child)
    for child in fetching:                      # ...and come back out
        _autopatch_terminal(run, child)
    holders = [c for c in children if c.step_class == "osm"]
    assert len(holders) == 4
    assert run._class_active["osm"] == 4
    idle = _FakeChild()
    run._children.append(idle)
    run._queue.append((10, 99))
    run._programs[(10, 99)] = ["vector", "mesh", "masks"]
    run._tile_arguments[(10, 99)] = {}
    with run._lock:
        assert run._start_new_tile_locked(idle) is False, (
            "a full osm class must still refuse new fetch work")


def test_child_killed_in_the_solve_leaks_no_token():
    """The pool's reaping path releases whatever class the child held."""
    run, (child,) = _fetching_run([(10, 10)], 2)
    _autopatch_begin(run, child)
    assert run._class_active["compute"] == 1
    run._on_child_exit(child)                   # crash mid-solve
    assert run._class_active == {"osm": 0, "imagery": 0, "compute": 0}
    assert child.step_class is None
    assert child.autopatch_pending is None


def test_step_end_during_the_solve_releases_the_solve_class():
    """A vector step that ends while still in the solve (no terminal
    auto-patch event ever arrives) releases compute, not osm."""
    run, (child,) = _fetching_run([(10, 10)], 2)
    _autopatch_begin(run, child)
    with run._lock:
        run._release_step_resources_locked(child)
    assert run._class_active == {"osm": 0, "imagery": 0, "compute": 0}


def test_a_tile_without_airports_keeps_its_osm_token():
    """No auto-patch, no split: an AutoPatchBegin with no airports (and
    a tile that never emits one at all) changes nothing."""
    run, (child,) = _fetching_run([(10, 10)], 2)
    _autopatch_begin(run, child, ())
    assert child.step_class == "osm"
    assert run._class_active["osm"] == 1


def test_solve_class_constant_restores_the_old_behaviour(monkeypatch):
    """The before/after arm of the acceptance measurement: pinning the
    solve class back to "osm" reproduces the pre-split scheduling."""
    monkeypatch.setattr(parallel, "VECTOR_SOLVE_CLASS", "osm")
    tiles = [(10, index) for index in range(5)]
    run, children = _fetching_run(tiles, 5)
    _autopatch_begin(run, children[0])
    assert children[0].step_class == "osm"
    assert run._class_active["osm"] == 4
    assert children[4].tile is None, (
        "the token is not released before the fix")


# ---------------------------------------------------------------------
# The imagery step's class split: downloads hold the imagery token, the
# DDS conversion tail does not (spec §A.2, the hybrid-step release)
# ---------------------------------------------------------------------
def _imagery_run(tiles, slots):
    """A run with every child started on its tile's IMAGERY step."""
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        tiles, "P", 16, "", (True, True, False), slots,
    )
    run._queue.clear()
    children = [_FakeChild() for _ in tiles]
    for child, tile in zip(children, tiles):
        child.tile = tile
        run._next_step_index[tile] = 3          # the imagery step
    run._children = list(children)
    with run._lock:
        for child in children:
            run._try_start_step_locked(child)
    return run, children


def _downloads_done(run, child):
    run._on_child_event(child, {
        "event": "ImageryDownloadsDone", "lat": child.tile[0],
        "lon": child.tile[1], "downloaded": 4, "failed": 0})


def test_imagery_tail_releases_the_imagery_token():
    """A tile whose download queue drained converts under compute, so a
    queued tile may start downloading in the same lock hold."""
    tiles = [(20, index) for index in range(5)]
    run, children = _imagery_run(tiles, 5)
    assert run._class_active["imagery"] == 4, "the imagery cap is 4"
    assert children[4].running_step is None
    _downloads_done(run, children[0])
    assert children[0].step_class == "compute", "the tail is compute-class"
    assert children[0].running_step == "imagery", "still the same step"
    # Promotion in the SAME lock hold (spec §A.2): the fifth tile started
    # DOWNLOADING on the freed token the instant it was released.
    assert children[4].running_step == "imagery"
    assert children[4].step_class == "imagery"
    assert run._class_active["imagery"] == 4
    assert run._class_active["compute"] == 1


def test_imagery_tail_release_is_idempotent():
    """A duplicate or late drain signal must not double-release."""
    run, (child,) = _imagery_run([(20, 20)], 2)
    _downloads_done(run, child)
    _downloads_done(run, child)
    assert run._class_active["imagery"] == 0
    assert run._class_active["compute"] == 1


def test_child_killed_in_the_imagery_tail_leaks_no_token():
    """The pool's reaping path releases whatever class the child holds —
    the same one path that covers a crash mid auto-patch solve."""
    run, (child,) = _imagery_run([(20, 20)], 2)
    _downloads_done(run, child)
    assert run._class_active["compute"] == 1
    run._on_child_exit(child)
    assert run._class_active == {"osm": 0, "imagery": 0, "compute": 0}
    assert child.step_class is None


def test_imagery_tail_release_is_gated(monkeypatch):
    """Gate off: the pre-2026-07-30 behaviour, token held to step end."""
    monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", "0")
    run, (child,) = _imagery_run([(20, 20)], 2)
    _downloads_done(run, child)
    assert child.step_class == "imagery"
    assert run._class_active["imagery"] == 1


# ---------------------------------------------------------------------
# Cache-aware admission: a tile whose inputs are on disk never waits for
# a fetch token (spec §A.2)
# ---------------------------------------------------------------------
def _stub_predicates(monkeypatch, cached_tiles, step="vector"):
    """Register fake per-subsystem predicates for the tiles named."""
    cached = set(cached_tiles)

    def predicate(tile_configuration):
        return (tile_configuration.lat,
                tile_configuration.lon) in cached

    registry = {
        name: predicate
        for names in parallel.STEP_FETCH_SUBSYSTEMS.values()
        for name in names
    }
    monkeypatch.setattr(parallel, "_PREDICATES", registry)

    class _StubTile:
        def __init__(self, lat, lon, build_dir):
            self.lat, self.lon = lat, lon

        def read_from_config(self):
            return 1

    fake_cfg = types.ModuleType("O4_Config_Utils")
    fake_cfg.Tile = _StubTile
    monkeypatch.setitem(sys.modules, "O4_Config_Utils", fake_cfg)


def test_a_cached_tile_never_waits_for_a_fetch_token(monkeypatch):
    """Six tiles, an osm cap of four, and the last two fully cached: the
    cached ones are admitted under COMPUTE and start immediately."""
    tiles = [(10, index) for index in range(6)]
    _stub_predicates(monkeypatch, cached_tiles=tiles[4:])
    run = _bare_run(tiles, 6)
    children = [_FakeChild() for _ in tiles]
    run._children = list(children)
    with run._lock:
        for child in children:
            run._start_new_tile_locked(child)
    assert run._class_active["osm"] == 4, "cold tiles fill the fetch cap"
    assert run._class_active["compute"] == 2, "cached tiles bypass it"
    assert all(child.tile is not None for child in children), (
        "every tile started: the cached ones did not queue for a token")
    for child in children:
        if child.tile in tiles[4:]:
            assert child.step_class == "compute"
        else:
            assert child.step_class == "osm"


def test_a_cached_tile_takes_a_token_when_gated_off(monkeypatch):
    monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", "0")
    tiles = [(10, index) for index in range(6)]
    _stub_predicates(monkeypatch, cached_tiles=tiles)
    run = _bare_run(tiles, 6)
    children = [_FakeChild() for _ in tiles]
    run._children = list(children)
    with run._lock:
        for child in children:
            run._start_new_tile_locked(child)
    assert run._class_active["osm"] == 2, "the legacy cap, no bypass"
    assert run._class_active["compute"] == 0


def test_cache_verdicts_are_asked_once_per_tile_and_step(monkeypatch):
    """The predicates are cheap but not free, and the first step of a
    queued tile is re-evaluated on every dispatch sweep."""
    calls = []

    def counting(tile_configuration):
        calls.append((tile_configuration.lat, tile_configuration.lon))
        return True

    _stub_predicates(monkeypatch, cached_tiles=[])
    monkeypatch.setattr(parallel, "_PREDICATES", {
        name: counting
        for names in parallel.STEP_FETCH_SUBSYSTEMS.values()
        for name in names
    })
    run = _bare_run([(10, 10)], 2)
    with run._lock:
        for _ in range(5):
            run._fetch_is_cached_locked((10, 10), "vector")
    subsystems = len(parallel.STEP_FETCH_SUBSYSTEMS["vector"])
    assert len(calls) == subsystems, (
        "one pass over the subsystems, memoised after that; got %d"
        % len(calls))


def test_an_unavailable_subsystem_reads_as_not_cached(monkeypatch):
    """Unknown means NOT cached — and is not memoised, so the answer can
    still change once the preload thread finishes importing."""
    _stub_predicates(monkeypatch, cached_tiles=[(10, 10)])
    monkeypatch.setattr(parallel, "_PREDICATES", {})
    run = _bare_run([(10, 10)], 2)
    with run._lock:
        assert run._fetch_is_cached_locked((10, 10), "vector") is False
        assert ((10, 10), "vector") not in run._cache_state
    _stub_predicates(monkeypatch, cached_tiles=[(10, 10)])
    with run._lock:
        assert run._fetch_is_cached_locked((10, 10), "vector") is True


def test_a_raising_predicate_reads_as_not_cached(monkeypatch):
    def exploding(tile_configuration):
        raise RuntimeError("filesystem said no")

    _stub_predicates(monkeypatch, cached_tiles=[(10, 10)])
    monkeypatch.setattr(parallel, "_PREDICATES", {
        name: exploding
        for names in parallel.STEP_FETCH_SUBSYSTEMS.values()
        for name in names
    })
    run = _bare_run([(10, 10)], 2)
    with run._lock:
        assert run._fetch_is_cached_locked((10, 10), "vector") is False


def test_a_completed_step_re_asks_the_cache_predicates(monkeypatch):
    """A step that just ran may have landed the next step's inputs."""
    _stub_predicates(monkeypatch, cached_tiles=[])
    run = _bare_run([(10, 10), (11, 11)], 2)
    child = _FakeChild()
    child.tile = (10, 10)
    child.running_step = "vector"
    run._children = [child]
    run._queue.clear()
    run._next_step_index[(10, 10)] = 0
    run._cache_state[((10, 10), "vector")] = False
    run._child_step_done(child)
    assert ((10, 10), "vector") not in run._cache_state


# ---------------------------------------------------------------------
# The parent-side warmer is a FETCHER and takes an osm token (spec §A.3)
# ---------------------------------------------------------------------
def test_warmer_takes_and_returns_an_osm_token():
    tiles = [(10, index) for index in range(6)]
    run = _bare_run(tiles, 6)
    with run._lock:
        assert run._acquire_warm_token_locked() is True
        assert run._class_active["osm"] == 1
        # Idempotent: the warmer holds at most one token.
        assert run._acquire_warm_token_locked() is True
        assert run._class_active["osm"] == 1
        assert run._release_warm_token_locked() is True
        assert run._class_active["osm"] == 0
        assert run._release_warm_token_locked() is False


def test_warmer_is_refused_when_the_osm_class_is_full():
    """The binding invariant of spec §A.3: the warmer cannot push
    concurrent OpenStreetMap conversations past the class cap."""
    tiles = [(10, index) for index in range(5)]
    run = _bare_run(tiles, 5)
    children = [_FakeChild() for _ in tiles]
    run._children = list(children)
    with run._lock:
        for child in children:
            run._start_new_tile_locked(child)
        assert run._class_active["osm"] == 4
        assert run._acquire_warm_token_locked() is False
        assert run._class_active["osm"] == 4, "no over-subscription"


def test_warmer_token_is_released_when_its_thread_dies(monkeypatch):
    """Crash-safe release: a warmer that raises anywhere must not leak
    its token (the warmer's half of the pool's child-reaping path)."""
    run = _bare_run([(10, 10)], 2)

    def exploding():
        with run._lock:
            run._acquire_warm_token_locked()
        raise RuntimeError("warm blew up")

    monkeypatch.setattr(run, "_warm_queued_tiles", exploding)
    with pytest.raises(RuntimeError):
        run._osm_cache_warmer()
    assert run._class_active["osm"] == 0
    assert run._warm_token_held is False
    assert run._warmer_running is False


def test_class_limits_take_environment_overrides(monkeypatch):
    monkeypatch.setenv("O4_OSM_CLASS_LIMIT", "5")
    monkeypatch.setenv("O4_IMAGERY_CLASS_LIMIT", "3")
    limits = parallel.class_limits(8)
    assert (limits["osm"], limits["imagery"]) == (5, 3)
    # Never above the run's own slot count.
    limits = parallel.class_limits(2)
    assert (limits["osm"], limits["imagery"]) == (2, 2)
    # Garbage and non-positive values fall back to the defaults.
    monkeypatch.setenv("O4_OSM_CLASS_LIMIT", "not-a-number")
    monkeypatch.setenv("O4_IMAGERY_CLASS_LIMIT", "0")
    assert parallel.class_limits(8)["osm"] == 4
    assert parallel.class_limits(8)["imagery"] == 4


def test_class_limits_default_to_the_module_constants(monkeypatch):
    monkeypatch.delenv("O4_OSM_CLASS_LIMIT", raising=False)
    monkeypatch.delenv("O4_IMAGERY_CLASS_LIMIT", raising=False)
    monkeypatch.delenv("O4_CACHE_AWARE_ADMISSION", raising=False)
    assert parallel.osm_class_limit() == parallel.OSM_CLASS_LIMIT == 4
    assert parallel.imagery_class_limit() == parallel.IMAGERY_CLASS_LIMIT == 4
    # Gate off restores the pre-2026-07-30 caps exactly.
    monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", "0")
    assert parallel.osm_class_limit() == parallel.LEGACY_OSM_CLASS_LIMIT == 2
    assert parallel.imagery_class_limit() == 2


# ---------------------------------------------------------------------
# Class limits end to end (wall-clock proof via per-step markers)
# ---------------------------------------------------------------------
def test_compute_steps_run_concurrently(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    """Compute steps are uncapped (2026-07-17 ruling: the operating
    system arbitrates processor contention) — two sleeper tiles' mesh
    steps overlap in wall-clock time; only the memory admission gate
    and the network classes ever hold a step back."""
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    session = EngineSession()
    # Sleeper tiles (lat 60) sleep ~0.6 s inside EVERY step, so their
    # mesh intervals overlap solidly when dispatched concurrently.
    tiles = [(60, -100), (60, -101)]
    result = _run_build(session, collector, tiles, slots=2)
    assert (result.done_count, result.error_count) == (2, 0)
    mesh_intervals = [
        _step_interval(tmp_path, tile, "mesh") for tile in tiles
    ]
    assert _max_concurrency(mesh_intervals) == 2, (
        "uncapped compute steps must run concurrently"
    )


def test_network_class_capped_with_more_slots_than_the_cap(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    monkeypatch.setenv("O4_OSM_CLASS_LIMIT", "2")
    session = EngineSession()
    tiles = [(40, -100), (41, -100), (42, -100)]
    result = _run_build(session, collector, tiles, slots=3)
    assert result.done_count == 3
    vector_intervals = [
        _step_interval(tmp_path, tile, "vector") for tile in tiles
    ]
    assert _max_concurrency(vector_intervals) <= 2, (
        "at most two tiles may occupy the network class"
    )


def _phase_interval(tmp_path, tile, kind_start, kind_end):
    start = tmp_path / ("%s_%d_%d" % (kind_start, tile[0], tile[1]))
    end = tmp_path / ("%s_%d_%d" % (kind_end, tile[0], tile[1]))
    assert start.exists() and end.exists(), (
        "missing %s/%s markers for %s" % (kind_start, kind_end, tile))
    return float(start.read_text()), float(end.read_text())


def test_auto_patch_solves_run_at_full_width(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    """The behavioural acceptance check (spec §4), synthetically: four
    tiles whose vector steps hand off to a processor-burning auto-patch
    solve overlap FOUR ways, while their remote-fetch phases never
    exceed the osm cap of two."""
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    monkeypatch.setenv("O4_OSM_CLASS_LIMIT", "2")
    session = EngineSession()
    tiles = [(63, -100), (63, -101), (63, -102), (63, -103)]
    result = _run_build(session, collector, tiles, slots=4)
    assert (result.done_count, result.error_count) == (4, 0)
    solves = [
        _phase_interval(tmp_path, tile, "solvestart", "solveend")
        for tile in tiles
    ]
    fetches = [
        (_step_interval(tmp_path, tile, "vector")[0],
         float((tmp_path / ("fetchend_%d_%d" % tile)).read_text()))
        for tile in tiles
    ]
    assert _max_concurrency(solves) == 4, (
        "the auto-patch solve must run at full slot width, saw %d"
        % _max_concurrency(solves))
    assert _max_concurrency(fetches) <= 2, (
        "remote fetch concurrency must be unchanged, saw %d"
        % _max_concurrency(fetches))


def test_auto_patch_solves_serialise_without_the_split(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    """The BEFORE arm of the same measurement: with the solve pinned to
    the osm class (the pre-2026-07-30 behaviour) the same four tiles
    never get more than two solves running at once."""
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    monkeypatch.setenv("O4_OSM_CLASS_LIMIT", "2")
    monkeypatch.setattr(parallel, "VECTOR_SOLVE_CLASS", "osm")
    session = EngineSession()
    tiles = [(63, -100), (63, -101), (63, -102), (63, -103)]
    result = _run_build(session, collector, tiles, slots=4)
    assert (result.done_count, result.error_count) == (4, 0)
    solves = [
        _phase_interval(tmp_path, tile, "solvestart", "solveend")
        for tile in tiles
    ]
    assert _max_concurrency(solves) <= 2, (
        "the osm cap throttled the solve before the split, saw %d"
        % _max_concurrency(solves))


def test_imagery_conversion_tails_run_at_full_width(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    """The imagery half of the behavioural acceptance check (spec §A.2),
    synthetically: six tiles whose imagery steps hand off to a
    processor-burning DDS conversion tail overlap SIX ways, while their
    download phases never exceed the imagery cap of four."""
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    session = EngineSession()
    tiles = [(64, -100 - index) for index in range(6)]
    result = _run_build(session, collector, tiles, slots=6, timeout=60.0,
                        do_imagery=True)
    assert (result.done_count, result.error_count) == (6, 0)
    converts = [
        _phase_interval(tmp_path, tile, "convertstart", "convertend")
        for tile in tiles
    ]
    downloads = [
        (_step_interval(tmp_path, tile, "imagery")[0],
         float((tmp_path / ("downloadend_%d_%d" % tile)).read_text()))
        for tile in tiles
    ]
    assert _max_concurrency(converts) == 6, (
        "the DDS conversion tail must run at full slot width, saw %d"
        % _max_concurrency(converts))
    assert _max_concurrency(downloads) <= 4, (
        "imagery download concurrency must stay within the class cap,"
        " saw %d" % _max_concurrency(downloads))


def test_imagery_tails_serialise_when_gated_off(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    """The BEFORE arm: with cache-aware admission off, the imagery token
    is held to step end and the 2-tile legacy cap binds the tails."""
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", "0")
    session = EngineSession()
    tiles = [(64, -100 - index) for index in range(6)]
    result = _run_build(session, collector, tiles, slots=6, timeout=60.0,
                        do_imagery=True)
    assert (result.done_count, result.error_count) == (6, 0)
    converts = [
        _phase_interval(tmp_path, tile, "convertstart", "convertend")
        for tile in tiles
    ]
    assert _max_concurrency(converts) <= 2, (
        "the legacy imagery cap throttled the tails, saw %d"
        % _max_concurrency(converts))


def test_cached_tiles_reach_full_width_past_the_fetch_cap(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    """The headline acceptance measurement of spec §A (concurrency by
    SAMPLING intervals, never wall time): with N tiles whose inputs are
    all cached, N workers are simultaneously in their processor-burning
    phase even though the osm fetch cap is four."""
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    tiles = [(63, -100 - index) for index in range(6)]
    _stub_predicates(monkeypatch, cached_tiles=tiles)
    session = EngineSession()
    result = _run_build(session, collector, tiles, slots=6, timeout=60.0)
    assert (result.done_count, result.error_count) == (6, 0)
    solves = [
        _phase_interval(tmp_path, tile, "solvestart", "solveend")
        for tile in tiles
    ]
    assert _max_concurrency(solves) == 6, (
        "cached tiles must reach full slot width, saw %d"
        % _max_concurrency(solves))
    # And the vector steps themselves overlapped six ways, which the
    # 4-tile fetch cap would have forbidden had they taken tokens.
    vectors = [_step_interval(tmp_path, tile, "vector") for tile in tiles]
    assert _max_concurrency(vectors) == 6


def _recorded_build_commands(monkeypatch, tmp_path, collector, solve_class):
    """Every ``build`` command the parent sent to a worker, per tile."""
    monkeypatch.setattr(parallel, "VECTOR_SOLVE_CLASS", solve_class)
    sent = []
    original_send = parallel._WorkerChild.send

    def recording_send(self, command):
        if command.get("cmd") == "build":
            sent.append(dict(command))
        return original_send(self, command)

    monkeypatch.setattr(parallel._WorkerChild, "send", recording_send)
    session = EngineSession()
    tiles = [(63, -100), (63, -101), (63, -102)]
    result = _run_build(session, collector, tiles, slots=3)
    assert (result.done_count, result.error_count) == (3, 0)
    per_tile = {}
    for command in sent:
        # "id" is a per-child counter — an artefact of which worker
        # happened to take the tile, never of the work requested.
        command.pop("id", None)
        tile = tuple(command["tiles"][0])
        per_tile.setdefault(tile, []).append(command)
    return per_tile


def test_the_split_changes_nothing_a_worker_is_asked_to_do(
    monkeypatch, tmp_path, stub_worker_command
):
    """Output identity (spec §4): the split is SCHEDULING only.

    A worker child's whole input is the build command it receives plus
    the files on disk, so identical per-tile command sequences before
    and after prove the emitted artefacts cannot differ — the change
    moves WHEN a step is dispatched, never what the step is asked to do.
    """
    before = _recorded_build_commands(monkeypatch, tmp_path, [], "osm")
    after = _recorded_build_commands(monkeypatch, tmp_path, [], "compute")
    assert set(before) == set(after)
    for tile in before:
        assert before[tile] == after[tile], (
            "tile %s was asked for different work: %s vs %s"
            % (tile, before[tile], after[tile]))
        assert [c["steps"] for c in after[tile]] == [
            ["vector"], ["mesh"], ["masks"]], (
            "the step programme itself must be untouched")


def _recorded_commands_under_gate(monkeypatch, tmp_path, gate, tiles,
                                  cached_tiles=()):
    """Every ``build`` command the parent sent, per tile, under a gate
    setting — the accepted output-identity proof (a worker child's whole
    input is its build command plus the files on disk)."""
    monkeypatch.setenv("O4_CACHE_AWARE_ADMISSION", gate)
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    _stub_predicates(monkeypatch, cached_tiles=cached_tiles)
    sent = []
    original_send = parallel._WorkerChild.send

    def recording_send(self, command):
        if command.get("cmd") == "build":
            sent.append(dict(command))
        return original_send(self, command)

    monkeypatch.setattr(parallel._WorkerChild, "send", recording_send)
    session = EngineSession()
    result = _run_build(session, [], tiles, slots=len(tiles), timeout=60.0,
                        do_imagery=True)
    assert (result.done_count, result.error_count) == (len(tiles), 0)
    per_tile = {}
    for command in sent:
        # "id" is a per-child counter — an artefact of which worker
        # happened to take the tile, never of the work requested.
        command.pop("id", None)
        per_tile.setdefault(tuple(command["tiles"][0]), []).append(command)
    return per_tile


def test_cache_aware_admission_changes_nothing_a_worker_is_asked_to_do(
    monkeypatch, tmp_path, stub_worker_command
):
    """Output identity (spec §A acceptance): Part A is SCHEDULING only.

    Identical per-tile command sequences with the gate on (every tile
    reported cached, so every fetch token is bypassed) and off prove the
    emitted artefacts cannot differ — the change moves WHEN a step is
    dispatched, never what the step is asked to do.
    """
    tiles = [(40, -100), (41, -100), (42, -100)]
    off = _recorded_commands_under_gate(
        monkeypatch, tmp_path, "0", tiles)
    on = _recorded_commands_under_gate(
        monkeypatch, tmp_path, "1", tiles, cached_tiles=tiles)
    assert set(off) == set(on)
    for tile in off:
        assert off[tile] == on[tile], (
            "tile %s was asked for different work: %s vs %s"
            % (tile, off[tile], on[tile]))
        assert [c["steps"] for c in on[tile]] == [
            ["vector"], ["mesh"], ["masks"], ["imagery"]], (
            "the step programme itself must be untouched")


def test_percent_remaps_into_the_full_plan_window(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    session = EngineSession()
    tiles = [(40, -100), (41, -100)]
    result = _run_build(session, collector, tiles, slots=2)
    assert result.done_count == 2
    # The stub emits 50% inside each single-step build; after remapping,
    # a masks-step 50% must land above where a vector-step 100% would
    # (percent never restarts across steps).
    from o4_engine.events import StepProgress

    per_tile = {}
    for event in collector:
        if isinstance(event, StepProgress):
            per_tile.setdefault((event.lat, event.lon), []).append(
                event.percent)
    for tile, percents in per_tile.items():
        assert percents == sorted(percents), (
            "whole-tile percent must be monotonic, got %s for %s"
            % (percents, tile))
        assert max(percents) <= 100.0


# ---------------------------------------------------------------------
# Warmer end to end: queued tiles warm before their builds start
# ---------------------------------------------------------------------
def test_warmer_warms_queued_tiles_before_their_builds(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    monkeypatch.delenv("O4_DISABLE_OSM_WARMER", raising=False)
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    warm_log = []
    _install_warm_stubs(monkeypatch, warm_log)

    session = EngineSession()
    tiles = [(40, -100), (41, -100), (42, -100), (43, -100)]
    result = _run_build(session, collector, tiles, slots=2)
    assert (result.done_count, result.error_count) == (4, 0)

    warmed = {entry[0] for entry in warm_log}
    # Only tiles that were QUEUED (not first-wave assigned) get warmed;
    # with two slots the first two tiles start immediately.
    assert warmed <= {(42, -100), (43, -100)}
    # Every warmed tile finished warming BEFORE its build started (the
    # no-race guarantee: assignment skips the tile being warmed).
    for tile in warmed:
        last_warm = max(t for (w, _s, t) in warm_log if w == tile)
        marker = tmp_path / ("start_%d_%d" % tile)
        assert marker.exists()
        build_start = float(marker.read_text())
        assert last_warm <= build_start + 1e-3


def test_warmer_skips_tiles_covered_by_local_extracts(
    monkeypatch, tmp_path, stub_worker_command, collector
):
    """The warmer exists to spare OVERPASS; a tile fully covered by
    local regional extracts never touches Overpass, and warming it
    would run country-sized pbf scans inside the front-end process,
    starving the interface through the interpreter lock (live
    "build appears hung", 2026-07-17)."""
    monkeypatch.delenv("O4_DISABLE_OSM_WARMER", raising=False)
    monkeypatch.setenv("STUB_WORKER_MARK_DIR", str(tmp_path))
    warm_log = []
    _install_warm_stubs(monkeypatch, warm_log)
    fake_extracts = types.ModuleType("O4_OSM_Extracts")
    fake_extracts.local_extracts_cover = lambda bounding_box: True
    monkeypatch.setitem(sys.modules, "O4_OSM_Extracts", fake_extracts)

    session = EngineSession()
    tiles = [(40, -100), (41, -100), (42, -100), (43, -100)]
    result = _run_build(session, collector, tiles, slots=2)
    assert (result.done_count, result.error_count) == (4, 0)
    assert warm_log == [], (
        "locally covered tiles must not be warmed in the front-end "
        "process")


def test_warmer_disabled_by_environment(
    monkeypatch, stub_worker_command, collector
):
    # conftest sets O4_DISABLE_OSM_WARMER=1 suite-wide; leave it in place.
    warm_log = []
    _install_warm_stubs(monkeypatch, warm_log)
    session = EngineSession()
    tiles = [(40, -100), (41, -100), (42, -100)]
    result = _run_build(session, collector, tiles, slots=2)
    assert result.done_count == 3
    assert warm_log == [], "disabled warmer must never download"


def test_step_progress_never_slides_backward():
    """The legacy in-step bars oscillate (they refill per OpenStreetMap
    layer, per download phase); the forwarder ratchets so a per-tile bar
    only ever advances — the 2026-07-16 "bars jump around" report."""
    emitted = []
    run = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=emitted.append, _run_finished=lambda: None),
        [(10, 10)], "P", 16, "", (True, True, False), 2,
    )
    child = _FakeChild()
    child.tile = (10, 10)
    run._next_step_index[(10, 10)] = 3  # imagery, window 36.8..100
    for oscillating in (10.0, 80.0, 20.0, 90.0, 60.0):
        run._on_child_event(child, {
            "event": "StepProgress", "lat": 10, "lon": 10,
            "step_key": "imagery", "label": "imagery & DSF",
            "percent": oscillating, "indeterminate": False,
        })
    percents = [e.percent for e in emitted]
    assert percents == sorted(percents), (
        "ratcheted percent must be monotonic, got %s" % percents)
    assert len(set(percents)) >= 2, "the bar must still advance"
    # A later, genuinely higher value still moves the bar.
    assert percents[-1] >= percents[1]


def test_sibling_count_broadcast_when_a_tile_finishes():
    """When a child runs out of work, survivors get a "siblings"
    message so their Auto slot resolutions stop sharing the machine
    with ghosts (live case: one tile's imagery fully cached and done
    in seconds, the other throttled to half download throughput for
    its entire 17-minute cold download)."""
    run = _bare_run([(10, 10), (11, 11)], 2)

    class _SendingChild(_FakeChild):
        def __init__(self):
            super().__init__()
            self.sent = []

        def send(self, payload):
            self.sent.append(payload)
            return True

    finished, survivor = _SendingChild(), _SendingChild()
    finished.tile, survivor.tile = (10, 10), (11, 11)
    run._children = [finished, survivor]
    run._queue.clear()
    # The finished child's tile is on its last step.
    program = run._programs[(10, 10)]
    run._next_step_index[(10, 10)] = len(program) - 1
    run._next_step_index[(11, 11)] = 0
    finished.running_step = program[-1]
    run._child_step_done(finished)
    assert finished.tile is None
    assert {"cmd": "siblings", "count": 1} in survivor.sent
    assert not finished.sent
    # No further change: no duplicate broadcast.
    survivor.sent.clear()
    run._broadcast_sibling_count()
    assert survivor.sent == []


def test_sibling_count_ignores_queued_tiles():
    """Queued tiles consume nothing until a child picks them up, so
    they must NOT count as siblings: the pre-2026-07-17 formula told
    every child in a 2-slot 6-tile run that six siblings shared the
    machine, throttling each to a sixth of it for the whole run."""
    run = _bare_run([(10, 10), (11, 11), (12, 12), (13, 13),
                     (14, 14), (15, 15)], 2)

    class _SendingChild(_FakeChild):
        def __init__(self):
            super().__init__()
            self.sent = []

        def send(self, payload):
            self.sent.append(payload)
            return True

    first, second = _SendingChild(), _SendingChild()
    first.tile, second.tile = (10, 10), (11, 11)
    run._children = [first, second]
    for tile in [(10, 10), (11, 11)]:
        run._queue.remove(tile)
        run._next_step_index[tile] = 0
    # Four tiles still queued; two children hold tiles.  The broadcast
    # baseline is the slot count (2) — holders match it, so nothing is
    # sent, and above all nothing says "6".
    run._broadcast_sibling_count()
    assert first.sent == [] and second.sent == []
    assert run._sibling_broadcast == 2


def test_enqueue_admits_new_tiles_and_skips_running_ones():
    """enqueue() on a live run admits fresh tiles (per-batch build
    arguments) and refuses duplicates of queued or active tiles."""
    run = _bare_run([(10, 10), (11, 11)], 2)
    # No real worker processes in this unit test.
    run._spawn_child = lambda: None
    child = _FakeChild()
    child.tile = (10, 10)
    run._children = [child]
    run._queue.remove((10, 10))
    run._next_step_index[(10, 10)] = 1

    admitted = run.enqueue([(10, 10), (11, 11), (12, 12)],
                           "OTHERPROVIDER", 17, "/elsewhere/",
                           (True, True, True))
    assert admitted == 1
    assert (12, 12) in run._queue
    assert run._total == 3
    # The new batch keeps its own build arguments and step program.
    assert run._tile_arguments[(12, 12)]["provider"] == "OTHERPROVIDER"
    assert run._tile_arguments[(12, 12)]["zoomlevel"] == 17
    assert run._programs[(12, 12)] == [
        "vector", "mesh", "masks", "imagery", "overlays"]
    # The original batch is untouched.
    assert run._tile_arguments[(11, 11)]["provider"] == "P"
    assert run._programs[(11, 11)] == ["vector", "mesh", "masks"]


def test_enqueue_refused_once_run_finished():
    run = _bare_run([(10, 10)], 2)
    run._finished = True
    assert run.enqueue([(11, 11)], "P", 16, "", (True, False, False)) == 0
