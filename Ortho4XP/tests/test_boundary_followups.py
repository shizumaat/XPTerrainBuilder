"""Issue #33 — the boundary-airports follow-ups owed by RULINGS 2026-09-18j.

Spec ``docs/specs/insets-follow-patch-set-spec.md`` rev 3:

* §D.3 — a NEIGHBOUR tile's airport-insets pass is named on the task
  meter (``"airport-insets +38-009"``) and in the step label the front
  ends render, so the activity view tells it from the home tile's pass;
* §D.2 — the vector step's fetch admission additionally requires
  ``INSETS.is_cached`` of each declared cold neighbour, so a tile with a
  neighbour fetch still holds a fetch token while it downloads;
* §E test 8 — "skip": the airport is absent from ``tasks`` and the
  manifest, the loud line is present, a stale on-disk auto patch is NOT
  applied, and no neighbour frame is fetched for it;
* §E test 10 — ``ensure_tile_frame``'s lock: two threads, one fetch.

Headless, ``tmp_path``, no network, no shared-corpus write.
"""
from __future__ import annotations

import contextlib
import os
import sys
import threading
import time
import types
from types import SimpleNamespace

import numpy
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

import O4_Vector_Map as VMAP                                 # noqa: E402
from auto_patch import selection as SEL                      # noqa: E402
from o4_engine import events as EV                           # noqa: E402

HOME = (38, -10)
WEST = (38, -11)


@pytest.fixture(autouse=True)
def clean_process_state(monkeypatch):
    monkeypatch.setattr(VMAP, "BOUNDARY_POLICY", None, raising=False)
    monkeypatch.setattr(VMAP, "BOUNDARY_BATCHES", {}, raising=False)
    monkeypatch.setattr(VMAP, "BOUNDARY_DECLARED", {}, raising=False)
    monkeypatch.setattr(VMAP.CFG, "auto_patch_boundary", "Ask",
                        raising=False)


# ======================================================================
# §D.3 — the neighbour pass is named
# ======================================================================
def _session_in_step(percent=12.0):
    from o4_engine.session import EngineSession

    session = EngineSession.__new__(EngineSession)
    emitted = []
    session._emit = emitted.append
    session._current_step = (HOME, "vector", 0.0, 0.3)
    session._autopatch_state = None
    session._step_detail = ""
    session._step_percent = percent
    return session, emitted


def test_the_step_label_names_a_neighbour_pass_and_clears():
    session, emitted = _session_in_step()

    session.step_detail("airport insets +38-011 (neighbour of +38-010)")
    session.step_detail("")

    assert [e.label for e in emitted] == [
        "vector data · airport insets +38-011 (neighbour of +38-010)",
        "vector data"]
    assert all(isinstance(e, EV.StepProgress) for e in emitted)
    assert all((e.lat, e.lon, e.step_key) == (38, -10, "vector")
               for e in emitted)
    # the bar does not move: the label changes, the percent is held
    assert [e.percent for e in emitted] == [12.0, 12.0]


def test_auto_patch_keeps_the_label_while_it_runs():
    session, emitted = _session_in_step()
    session._autopatch_state = {"total": 2, "finished": set(), "frac": {},
                                "current": ""}
    session.step_detail("airport insets +38-011")
    assert emitted == []


def test_the_ui_hook_reaches_the_session(monkeypatch):
    import O4_UI_Utils as UI

    seen = []
    monkeypatch.setattr(UI, "engine_session",
                        SimpleNamespace(step_detail=seen.append))
    UI.step_detail("x")
    assert seen == ["x"]
    monkeypatch.setattr(UI, "engine_session", None)
    UI.step_detail("never raises without a session")


@pytest.fixture
def frame_sandbox(monkeypatch, tmp_path):
    """``ensure_tile_frame`` with every fetch faked into ``tmp_path``:
    each fake fetches only when its cache marker is absent (as the real
    cache-aware fetches do) and counts what it fetched."""
    fetched = {"osm": 0, "insets": 0}
    meter_keys = []
    details = []

    class _Tile:
        def __init__(self, lat, lon, build_dir):
            (self.lat, self.lon) = (lat, lon)

        def read_from_config(self):
            return 1

    monkeypatch.setattr(VMAP.CFG, "Tile", _Tile)
    monkeypatch.setattr(VMAP.FNAMES, "osm_dir",
                        lambda lat, lon: str(tmp_path / "osm"))
    monkeypatch.setattr(VMAP.FNAMES, "airport_inset_directory",
                        lambda lat, lon: str(tmp_path / "insets"))
    monkeypatch.setattr(VMAP.OSM, "OSM_layer", lambda: object())

    def fake_osm(queries, layer, lat, lon, tags, cached_suffix=""):
        marker = tmp_path / "osm" / "airports.done"
        if not marker.exists():
            time.sleep(0.2)                  # a download takes a while
            fetched["osm"] += 1
            marker.write_text("x")

    def fake_insets(tile, dico, refresh=False, meter_key="airport-insets"):
        meter_keys.append(meter_key)
        marker = tmp_path / "insets" / "complete.json"
        if not marker.exists():
            time.sleep(0.2)
            fetched["insets"] += 1
            marker.write_text("{}")

    monkeypatch.setattr(VMAP.OSM, "OSM_queries_to_OSM_layer", fake_osm)
    monkeypatch.setattr(VMAP, "build_airports_dico", lambda tile, layer: {})
    monkeypatch.setattr(VMAP.INSETS, "ensure_insets_for_tile", fake_insets)
    monkeypatch.setattr(VMAP.UI, "step_detail", details.append)
    monkeypatch.setattr(VMAP, "tile_frame_is_warm", lambda lat, lon: True)
    return SimpleNamespace(fetched=fetched, meter_keys=meter_keys,
                           details=details)


def test_a_neighbour_pass_runs_under_its_own_meter_key_and_label(
        frame_sandbox):
    assert VMAP.ensure_tile_frame(38, -11, reason="neighbour of +38-010")

    assert frame_sandbox.meter_keys == ["airport-insets +38-011"]
    assert frame_sandbox.details == [
        "airport insets +38-011 (neighbour of +38-010)", ""]


def test_the_meter_key_reaches_ensure_airport_insets(monkeypatch):
    import O4_Airport_Elevation_Insets as INSETS

    calls = []
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda t: True)
    monkeypatch.setattr(INSETS, "select_provider_definitions",
                        lambda value: [{"code": "x"}])
    monkeypatch.setattr(INSETS, "resolved_inset_mode", lambda t: "ICAO")
    monkeypatch.setattr(INSETS, "inset_keys", lambda dico, mode: {"LPXX"})
    monkeypatch.setattr(INSETS, "_airport_bounding_boxes",
                        lambda tile, dico, only=None: {"LPXX": (0, 0, 1, 1)})
    monkeypatch.setattr(INSETS, "_write_inset_completion_stamp",
                        lambda tile: None)
    monkeypatch.setattr(
        INSETS, "ensure_airport_insets",
        lambda *a, **k: calls.append(k.get("meter_key", "airport-insets")))
    tile = SimpleNamespace(lat=38, lon=-11)

    INSETS.ensure_insets_for_tile(tile, {"LPXX": {}})
    INSETS.ensure_insets_for_tile(tile, {"LPXX": {}},
                                  meter_key="airport-insets +38-011")

    assert calls == ["airport-insets", "airport-insets +38-011"]


# ======================================================================
# §E test 10 — ensure_tile_frame's lock: two threads, one fetch
# ======================================================================
def _two_threads_warm(cell):
    barrier = threading.Barrier(2)
    errors = []

    def run():
        try:
            barrier.wait(timeout=10)
            VMAP.ensure_tile_frame(*cell, reason="test")
        except Exception as error:                   # pragma: no cover
            errors.append(error)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not errors and not any(t.is_alive() for t in threads)


def test_two_threads_warming_one_frame_fetch_once(frame_sandbox):
    _two_threads_warm(WEST)
    assert frame_sandbox.fetched == {"osm": 1, "insets": 1}


def test_without_the_lock_the_same_race_fetches_twice(frame_sandbox,
                                                      monkeypatch):
    """The control that gives the twin its teeth."""
    import O4_File_Lock as LOCK

    @contextlib.contextmanager
    def no_lock(path, timeout_seconds=900.0):
        yield True

    monkeypatch.setattr(LOCK, "hold_file_lock", no_lock)
    _two_threads_warm(WEST)
    assert frame_sandbox.fetched == {"osm": 2, "insets": 2}


# ======================================================================
# §D.2 — fetch admission requires the declared neighbours' frames
# ======================================================================
def test_an_undeclared_tile_has_no_neighbour_frame_to_fetch():
    assert VMAP.boundary_frames_are_cached(SimpleNamespace(lat=38, lon=-10))


def test_a_cold_declared_sibling_holds_the_fetch_token(monkeypatch):
    warm = set()
    monkeypatch.setattr(VMAP, "tile_frame_is_warm",
                        lambda lat, lon: (lat, lon) in warm)
    VMAP.declare_boundary_cells(HOME, siblings=[WEST])
    tile = SimpleNamespace(lat=HOME[0], lon=HOME[1])

    assert not VMAP.boundary_frames_are_cached(tile)
    warm.add(WEST)
    assert VMAP.boundary_frames_are_cached(tile)


@pytest.mark.parametrize("policy,cached", [("skip", True),
                                           ("neighbour", False)])
def test_an_outside_neighbour_counts_only_under_build_adjacent(
        monkeypatch, policy, cached):
    """Under skip the build never fetches it, so it must not pin the tile
    to the fetch class."""
    monkeypatch.setattr(VMAP, "tile_frame_is_warm", lambda lat, lon: False)
    VMAP.declare_boundary_cells(HOME, outside=[WEST])
    tile = SimpleNamespace(lat=HOME[0], lon=HOME[1], boundary_policy=policy)
    assert VMAP.boundary_frames_are_cached(tile) is cached


def test_the_predicate_is_registered_for_the_vector_step():
    from o4_engine import parallel

    name = "O4_Vector_Map:boundary_frames_are_cached"
    assert name in parallel.STEP_FETCH_SUBSYSTEMS["vector"]
    parallel.preload_cache_predicates()
    assert parallel._subsystem_is_cached(name) is \
        VMAP.boundary_frames_are_cached


def test_the_scheduler_hands_the_predicate_the_batch_policy(monkeypatch):
    from o4_engine import parallel

    class _StubTile:
        def __init__(self, lat, lon, build_dir):
            (self.lat, self.lon) = (lat, lon)

        def read_from_config(self):
            return 1

    fake_cfg = types.ModuleType("O4_Config_Utils")
    fake_cfg.Tile = _StubTile
    monkeypatch.setitem(sys.modules, "O4_Config_Utils", fake_cfg)
    run = parallel.ParallelBuildRun.__new__(parallel.ParallelBuildRun)
    run._tile_configurations = {}
    run._tile_arguments = {HOME: {"boundary_policy": "neighbour"}}
    assert run._tile_configuration(HOME).boundary_policy == "neighbour"


def _apron_candidate(tmp_path):
    """Class S into the WEST cell: an apron 60 m east of lon -10."""
    lat = 38.5
    m_per_deg_lon = 111320.0 * numpy.cos(numpy.radians(lat))
    w = -10.0 + 60.0 / m_per_deg_lon
    e = -10.0 + 260.0 / m_per_deg_lon
    (s, n) = (lat, lat + 200.0 / 111132.0)
    body = "\n".join(["110 1 0.25 0.0 PAV",
                      "111 %.7f %.7f" % (s, w), "111 %.7f %.7f" % (s, e),
                      "111 %.7f %.7f" % (n, e), "113 %.7f %.7f" % (n, w)])
    path = tmp_path / "apron.dat"
    path.write_text("A\n1000 Version\n\n1 10 0 0 LPXX Test\n%s\n99\n" % body,
                    encoding="utf-8")
    return SEL.PatchCandidate("LPXX", "x.dat", {}, "patch", "", str(path))


@pytest.mark.parametrize("cells,siblings,outside,add_tiles", [
    ([HOME, WEST], [WEST], [], []),          # the press builds both
    ([HOME], [], [WEST], [[38, -11]]),       # the neighbour is outside
])
def test_the_preflight_declares_what_step_1_may_warm(
        monkeypatch, tmp_path, cells, siblings, outside, add_tiles):
    import O4_Config_Utils as CFG
    import O4_Settings_Model as SETTINGS
    from o4_engine.session import EngineSession

    candidate = _apron_candidate(tmp_path)

    class _Tile:
        def __init__(self, lat, lon, build_dir):
            (self.lat, self.lon) = (lat, lon)

        def read_from_config(self):
            return 1

    monkeypatch.setattr(CFG, "Tile", _Tile)
    monkeypatch.setattr(SETTINGS, "resolve_cifp_dir",
                        lambda *a: str(tmp_path))
    monkeypatch.setattr(SEL, "resolved_auto_patch_mode", lambda t: "ICAO")
    monkeypatch.setattr(VMAP, "manual_patch_icaos", lambda t: set())
    monkeypatch.setattr(VMAP, "tile_frame_is_warm", lambda lat, lon: False)

    def select(tile, cifp, mode, manual_icaos=None, boundary=None):
        if (tile.lat, tile.lon) == HOME:
            boundary("LPXX", {}, candidate)
        return []

    monkeypatch.setattr(SEL, "select_patch_airports", select)
    session = EngineSession.__new__(EngineSession)

    ready = session._boundary_preflight(1, cells)

    assert ready.add_tiles == add_tiles
    assert VMAP.BOUNDARY_DECLARED[HOME] == (frozenset(siblings),
                                            frozenset(outside))


# ======================================================================
# §E test 8 — "skip"
# ======================================================================
def test_skip_fetches_no_neighbour_frame(monkeypatch, tmp_path):
    """Under skip the outside neighbour is named, never warmed."""
    candidate = _apron_candidate(tmp_path)
    monkeypatch.setattr(VMAP, "tile_frame_is_warm", lambda lat, lon: False)
    monkeypatch.setattr(VMAP, "resolve_cifp_dir_for_tile",
                        lambda tile: str(tmp_path))
    monkeypatch.setattr(VMAP, "resolved_auto_patch_mode", lambda t: "ICAO")
    monkeypatch.setattr(VMAP, "manual_patch_icaos", lambda t: set())
    monkeypatch.setattr(SEL, "resolved_inset_mode", lambda t: "None")

    def select(tile, cifp, mode, manual_icaos=None, boundary=None):
        reason = boundary("LPXX", {}, candidate)
        return [SEL.PatchCandidate("LPXX", "x", {}, "boundary_skipped",
                                   reason, candidate.apt_dat)]

    monkeypatch.setattr(SEL, "select_patch_airports", select)
    tile = SimpleNamespace(lat=HOME[0], lon=HOME[1])

    selection = VMAP.derive_auto_patch_selection(tile)

    assert [c.disposition for c in selection] == ["boundary_skipped"]
    assert tile.boundary_policy == "skip"
    assert tile.boundary_neighbours == [WEST]
    assert VMAP.boundary_cells_to_warm(tile) == []


def _auto_patch_file(patch_dir, icao, lat, lon):
    ring = [(lon + 0.001, lat + 0.001), (lon + 0.003, lat + 0.001),
            (lon + 0.003, lat + 0.003), (lon + 0.001, lat + 0.003)]
    lines = ["<?xml version='1.0' encoding='UTF-8'?>",
             "<osm version='0.6' upload='true' generator='test'>"]
    refs = []
    for (index, (x, y)) in enumerate(ring):
        node = -10 - 2 * index
        refs.append(node)
        lines.append("  <node id='%d' action='modify' visible='true' "
                     "lat='%.10f' lon='%.10f' />" % (node, y, x))
    lines.append("  <way id='-100' action='modify' visible='true'>")
    lines += ["    <nd ref='%d' />" % r for r in refs + [refs[0]]]
    lines += ["    <tag k='cst_alt_abs' v='75' />", "  </way>", "</osm>"]
    (patch_dir / ("%s_auto.patch.osm" % icao)).write_text("\n".join(lines))


def test_skip_never_applies_a_stale_on_disk_auto_patch(monkeypatch,
                                                       tmp_path):
    """§C.5: the file from an earlier build stays on disk (a later "build
    adjacent" run reuses it) but THIS build does not apply it."""
    import O4_Vector_Utils as VECT

    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    for icao in ("LPXX", "LPYY"):
        _auto_patch_file(patch_dir, icao, *HOME)
    monkeypatch.setattr(VMAP.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))

    class _DEM:
        def alt_vec(self, way):
            return numpy.zeros((len(way), 1))

    tile = SimpleNamespace(
        lat=HOME[0], lon=HOME[1], dem=_DEM(), auto_patch="All",
        auto_patch_selection=[
            SEL.PatchCandidate("LPXX", "x", {}, "boundary_skipped", "r"),
            SEL.PatchCandidate("LPYY", "x", {}, "patch", "")])

    (_area, patches_list, _graded) = VMAP.include_patches(
        VECT.Vector_Map(), tile)

    assert "LPYY" in patches_list
    assert "LPXX" not in patches_list and "LPXX_auto" not in patches_list
    assert (patch_dir / "LPXX_auto.patch.osm").exists()


def test_skip_is_absent_from_tasks_and_the_manifest(tmp_path, monkeypatch):
    """The driver: loud line, never queued, never built, never owed (the
    manifest check raises nothing and fails no airport)."""
    monkeypatch.delenv("O4_AUTO_PATCH_REBUILD", raising=False)
    import O4_UI_Utils as UI
    from auto_patch import build_support, driver
    from auto_patch import cifp_reader as _cifp
    from test_auto_patch_freshness import _make_apt_dat, _stub_the_engine

    failed = []
    monkeypatch.setattr(UI, "auto_patch_failed",
                        lambda icao, stage, error: failed.append(icao))
    lines = []
    monkeypatch.setattr(UI, "lvprint", lambda level, *parts: lines.append(
        " ".join(str(p) for p in parts)))
    apt = _make_apt_dat(tmp_path)
    patch_dir = tmp_path / "Patches"
    patch_dir.mkdir()
    rwy = {"lat": 40.1, "lon": -100.2}
    monkeypatch.setattr(driver.FNAMES, "patch_dir",
                        lambda lat, lon: str(patch_dir))
    for target in (driver, _cifp):
        monkeypatch.setattr(target, "discover_cifp_airports",
                            lambda path: {"KFAK": "a.dat", "KSKP": "b.dat"})
        monkeypatch.setattr(target, "parse_cifp_file",
                            lambda path: {"04": rwy, "22": rwy})
        monkeypatch.setattr(target, "airport_in_tile",
                            lambda runways, lat, lon: True)
        monkeypatch.setattr(target, "xplane_root_from_cifp_path",
                            lambda path: "xp_root")
    for target in (driver, build_support):
        monkeypatch.setattr(target, "pair_runways",
                            lambda runways: [("04", rwy, "22", rwy)])
    monkeypatch.setattr(build_support, "_pick_best_apt_dat_against_osm",
                        lambda xp_root, icao: str(apt))
    _stub_the_engine(tmp_path, monkeypatch)
    reason = ("crosses into tile +40-101 (not built) — patch SKIPPED by "
              "your boundary choice; build +40-101 with this tile to "
              "patch it")
    tile = SimpleNamespace(lat=40.0, lon=-100.0, dem=None)
    tile.auto_patch_selection = SEL.select_patch_airports(
        tile, str(tmp_path), "All", manual_icaos=(),
        boundary=lambda icao, rw, candidate=None:
        reason if icao == "KSKP" else None)
    stale = patch_dir / "KSKP_auto.patch.osm"
    stale.write_text("<osm version='0.6'></osm>\n")
    before = stale.read_bytes()

    auto_patched = driver.generate_auto_patches(
        tile, str(tmp_path), taxiway_data={}, building_data={},
        road_data=None, mode="All")

    assert auto_patched == ["KFAK"]
    assert failed == []
    assert any("KSKP" in line and "SKIPPED" in line for line in lines)
    assert stale.read_bytes() == before, "a skipped airport is never rebuilt"
