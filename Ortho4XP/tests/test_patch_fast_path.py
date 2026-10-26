"""Twins of the height-edit fast path (#1323, spec
``docs/specs/incremental-patch-edit-spec.md`` §3A, §9 E2' / E3).

E2': the z-provenance replay of a height-only patch edit writes the SAME
``.node`` bytes as a second full vector step on the edited patch, through
the real ``include_patches``, crossings, grid encoding, 9-dp snap and
noding.  Then the fast path end to end through ``O4_Step_Reuse``, and its
refusals (§3A.4), each in its own words.

Headless: synthetic patches and a stand-in DEM in ``tmp_path``.
"""
from __future__ import annotations

import os
import shutil
import sys

import numpy
import pytest
from shapely import geometry

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Cfg_Vars as CFGVARS  # noqa: E402
import O4_Edit_Cache as EDITCACHE  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Patch_Fast_Path as FASTPATH  # noqa: E402
import O4_Step_Reuse as REUSE  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
import O4_Vector_Utils as VECT  # noqa: E402
import O4_ZProv as ZPROV  # noqa: E402

LAT, LON = 30, 30


class _DEM:
    """A sloped stand-in DEM, so every crossing interpolates real values;
    float32 like a raster, so the patch's altitude array is float32 too."""

    def alt_vec(self, way):
        way = numpy.asarray(way, dtype=float)
        z = 100.0 + 37.31 * way[:, 0] + 11.17 * way[:, 1]
        return z.astype(numpy.float32).reshape((len(way), 1))


class _Tile:
    def __init__(self, build_dir):
        self.lat, self.lon, self.build_dir = LAT, LON, str(build_dir)
        for name in CFGVARS.list_tile_vars:
            setattr(self, name, CFGVARS.cfg_vars[name]["default"])
        self.iterate = 0
        self.auto_patch = "All"
        self.custom_build_dir = ""
        self.dem = _DEM()


# Tile-relative coordinates; patch files carry them absolute.
RING = [(0.10, 0.10), (0.30, 0.10), (0.30, 0.30), (0.10, 0.30)]
INNER = [(0.10, 0.10), (0.25, 0.21)]                 # shares a ring node
CROSSING_RUN = [(0.05, 0.20), (0.35, 0.27)]         # DUMMY run, crosses ring
OTHER_RING = [(0.26, 0.26), (0.40, 0.26), (0.40, 0.40), (0.26, 0.40)]


def _patch_text(ways, alts, moved=None, extra_tag=None):
    """``ways``: [(points, closed, way tags)]; ``alts``: {point: alt_abs
    text}.  ``moved``: {point: new point}; ``extra_tag``: (point, k, v)."""
    moved = moved or {}
    ids, lines = {}, ["<?xml version='1.0' encoding='UTF-8'?>",
                      "<osm version='0.6' upload='false' generator='test'>"]
    for points, _closed, _tags in ways:
        for p in points:
            if p in ids:
                continue
            ids[p] = -1 - len(ids)
            (x, y) = moved.get(p, p)
            lines.append("  <node id='%d' action='modify' visible='true' "
                         "lat='%.11f' lon='%.11f'>" % (ids[p], LAT + y, LON + x))
            if p in alts:
                lines.append("    <tag k='alt_abs' v='%s' />" % alts[p])
            if extra_tag and extra_tag[0] == p:
                lines.append("    <tag k='%s' v='%s' />" % extra_tag[1:])
            lines.append("  </node>")
    for k, (points, closed, tags) in enumerate(ways):
        lines.append("  <way id='%d' action='modify' visible='true'>" % (-100 - k))
        for p in points + (points[:1] if closed else []):
            lines.append("    <nd ref='%d' />" % ids[p])
        for key, value in tags:
            lines.append("    <tag k='%s' v='%s' />" % (key, value))
        lines.append("  </way>")
    lines.append("</osm>")
    return "\n".join(lines) + "\n"


BASE_ALTS = {RING[0]: "112.5", RING[1]: "112.75", RING[2]: "113.25",
             RING[3]: "112.5", INNER[1]: "114.1", CROSSING_RUN[0]: "111.9",
             CROSSING_RUN[1]: "113.33"}
MAIN_WAYS = [(RING, True, [("role", "apron")]), (INNER, False, []),
             (CROSSING_RUN, False, [])]
OTHER_ALTS = {p: "120.6" for p in OTHER_RING}


def _write_patches(patch_dir, alts=BASE_ALTS, **kwargs):
    (patch_dir / "TEST_edited.patch.osm").write_text(
        _patch_text(MAIN_WAYS, alts, **kwargs), encoding="utf-8", newline="\n")
    (patch_dir / "TSTB.patch.osm").write_text(
        _patch_text([(OTHER_RING, True, [])], OTHER_ALTS),
        encoding="utf-8", newline="\n")


def _vector_step(tile):
    """The vector step's z-writing passes in build order: the patches,
    a DEM road crossing them, the ortho grid, the snap, the noding; then
    the files (``build_poly_file``'s own writers)."""
    vector_map = VECT.Vector_Map()
    VMAP.include_patches(vector_map, tile)
    road = numpy.array([[0.12, 0.02], [0.27, 0.38], [0.45, 0.33]])
    vector_map.insert_way(numpy.hstack(
        [road, tile.dem.alt_vec(road).astype(float)]), "DUMMY", check=True)
    grid = geometry.MultiLineString(
        [[(x, 0.0), (x, 1.0)] for x in (0.0, 0.17, 0.2713, 1.0)]
        + [[(0.0, y), (1.0, y)] for y in (0.0, 0.2311, 0.33, 1.0)])
    vector_map.encode_MultiLineString(grid, tile.dem.alt_vec, "DUMMY",
                                      check=True, skip_cut=True)
    vector_map.snap_to_grid(9)
    vector_map.node_vertices_on_edges(vector_map.split_spacing_m, tile.lat)
    os.makedirs(tile.build_dir, exist_ok=True)
    node_file = FNAMES.input_node_file(tile)
    vector_map.write_node_file(node_file)
    vector_map.zprov.write(ZPROV.zprov_file(node_file))
    vector_map.write_poly_file(FNAMES.input_poly_file(tile))
    for path in (FNAMES.alt_file(tile), FNAMES.apt_file(tile)):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("raster")
    return vector_map


@pytest.fixture
def tile(tmp_path, monkeypatch):
    for name in ("osm", "patches", "insets", "masks"):
        (tmp_path / name).mkdir()
    monkeypatch.setattr(FNAMES, "osm_dir", lambda lat, lon: str(tmp_path / "osm"))
    monkeypatch.setattr(FNAMES, "patch_dir",
                        lambda lat, lon: str(tmp_path / "patches"))
    monkeypatch.setattr(FNAMES, "mask_dir", lambda lat, lon: str(tmp_path / "masks"))
    monkeypatch.setattr(FNAMES, "airport_inset_directory",
                        lambda lat, lon: str(tmp_path / "insets"))
    monkeypatch.delenv("O4_STEP_REUSE", raising=False)
    (tmp_path / "osm" / "+30+030_airports.osm.bz2").write_bytes(b"osm")
    return _Tile(tmp_path / "build")


def _full_build(tile):
    """A full vector step, recorded as the session records one."""
    REUSE.forget_from(tile, "vector")
    _vector_step(tile)
    REUSE.record(tile, "vector")
    FASTPATH.after_step_recorded(tile, "vector")


def _node_bytes(tile):
    with open(FNAMES.input_node_file(tile), "rb") as handle:
        return handle.read()


EDITED_ALTS = {**BASE_ALTS, RING[1]: "113.41", CROSSING_RUN[0]: "110.07"}


def test_e2prime_replay_equals_a_full_vector_step(tile, tmp_path):
    """Arm A: a second full vector step on the edited patch.  Arm B: the
    replay.  The ``.node`` bytes are identical, and the edit reached more
    nodes than the two it touched (the crossings carried it)."""
    patches = tmp_path / "patches"
    _write_patches(patches)
    _full_build(tile)
    before = _node_bytes(tile)
    events = ZPROV.read_events(ZPROV.zprov_file(FNAMES.input_node_file(tile)))
    assert any(e[0] == "l" for e in events), "the fixture crosses nothing"

    _write_patches(patches, EDITED_ALTS)
    arm_b = FASTPATH.try_height_edit(tile)
    assert arm_b.applied, arm_b.why
    assert arm_b.heights_changed == 2
    assert arm_b.nodes_rewritten > 2
    replayed = _node_bytes(tile)
    log = ZPROV.zprov_file(FNAMES.input_node_file(tile))
    with open(log, "rb") as handle:
        replayed_log = handle.read()

    shutil.rmtree(tile.build_dir)
    _vector_step(tile)
    assert _node_bytes(tile) == replayed
    assert replayed != before
    # the log written back is the full step's too: a later edit replays
    # from it, and the vector record's output rows stay the full step's
    with open(log, "rb") as handle:
        assert handle.read() == replayed_log


def test_after_the_fast_path_every_step_record_is_current(tile, tmp_path):
    _write_patches(tmp_path / "patches")
    _full_build(tile)
    _write_patches(tmp_path / "patches", EDITED_ALTS)
    assert REUSE.stale_reason(tile, "vector") is not None
    assert FASTPATH.step_decision(tile, "vector")[0] == "updated"
    assert REUSE.stale_reason(tile, "vector") is None
    # the copy as built is now the edited patch: a second edit diffs from it
    prev = os.path.join(FASTPATH.prev_dir(tile), "TEST_edited.patch.osm")
    with open(prev, encoding="utf-8") as handle:
        assert "113.41" in handle.read()


@pytest.mark.parametrize("edit, words", [
    ({"moved": {RING[2]: (0.3001, 0.30)}}, "a patch node moved"),
    ({"alts": {**BASE_ALTS, RING[0]: None}}, "added or removed"),
    ({"extra_tag": (RING[0], "role", "x")}, "added or removed"),
])
def test_a_non_height_edit_takes_the_full_vector_step(tile, tmp_path, edit,
                                                      words):
    _write_patches(tmp_path / "patches")
    _full_build(tile)
    alts = edit.pop("alts", BASE_ALTS)
    alts = {p: v for p, v in alts.items() if v is not None}
    _write_patches(tmp_path / "patches", alts, **edit)
    result = FASTPATH.try_height_edit(tile)
    assert not result.applied and result.relevant
    assert words in result.why


def test_a_cleared_edit_cache_takes_the_full_vector_step(tile, tmp_path):
    _write_patches(tmp_path / "patches")
    _full_build(tile)
    shutil.rmtree(EDITCACHE.cache_dir(tile.build_dir))
    _write_patches(tmp_path / "patches", EDITED_ALTS)
    result = FASTPATH.try_height_edit(tile)
    assert not result.applied and "keep_edit_cache" in result.why


def test_a_missing_log_takes_the_full_vector_step(tile, tmp_path):
    _write_patches(tmp_path / "patches")
    _full_build(tile)
    os.remove(ZPROV.zprov_file(FNAMES.input_node_file(tile)))
    _write_patches(tmp_path / "patches", EDITED_ALTS)
    result = FASTPATH.try_height_edit(tile)
    assert not result.applied
    assert "a vector output other than a patch changed" in result.why


@pytest.mark.parametrize("change, words", [
    ("setting", "setting changed"),
    ("reuse_off", "O4_STEP_REUSE=0"),
    ("added", "an airport's apt.dat, CIFP or pack changed"),
])
def test_any_other_change_takes_the_full_vector_step(tile, tmp_path,
                                                     monkeypatch, change,
                                                     words):
    _write_patches(tmp_path / "patches")
    _full_build(tile)
    _write_patches(tmp_path / "patches", EDITED_ALTS)
    if change == "setting":
        tile.road_level = 3
    elif change == "reuse_off":
        monkeypatch.setenv("O4_STEP_REUSE", "0")
    else:
        (tmp_path / "patches" / "TSTC.patch.osm").write_text(
            _patch_text([(OTHER_RING, True, [])], OTHER_ALTS),
            encoding="utf-8")
    result = FASTPATH.try_height_edit(tile)
    assert not result.applied and not result.relevant
    assert words in result.why
    assert FASTPATH.step_decision(tile, "vector")[0] == "run"


def test_keep_edit_cache_is_a_tile_setting_no_step_reads():
    """Q148: per tile (with its global default), and toggling it stales
    no step (spec §8.1 item 2)."""
    assert "keep_edit_cache" in CFGVARS.list_tile_vars
    assert "global_keep_edit_cache" in CFGVARS.list_global_tile_vars
    assert CFGVARS.cfg_vars["keep_edit_cache"]["default"] is False
    for step in REUSE.REUSABLE_STEPS:
        assert "keep_edit_cache" not in REUSE._step_settings(step)


def _session_entry(tmp_path, name, keep):
    folder = tmp_path / name / EDITCACHE.CACHE_DIR_NAME
    (folder / "prev").mkdir(parents=True)
    tile = _Tile(tmp_path / name)
    tile.keep_edit_cache = keep
    return tile, folder


def test_the_session_clears_the_caches_of_tiles_that_do_not_keep_them(
        tmp_path, monkeypatch):
    """Q148: cleared when the session ends unless the tile keeps its own;
    a child process (inherited list) never clears."""
    dropped, dropped_dir = _session_entry(tmp_path, "a", False)
    kept, kept_dir = _session_entry(tmp_path, "b", True)
    keeps = {str(dropped_dir): False, str(kept_dir): True}
    monkeypatch.setattr(EDITCACHE, "_tile_keeps",
                        lambda entry: keeps[entry["dir"]])
    EDITCACHE.begin_session(frontend_pid=os.getpid() + 1)
    EDITCACHE.register(dropped)
    EDITCACHE.register(kept)
    listed = os.environ[EDITCACHE.LIST_ENV]
    owned = dict(EDITCACHE._owned)
    EDITCACHE._owned.clear()              # a child: inherits, never owns
    assert EDITCACHE.end_session() == 0 and dropped_dir.is_dir()
    EDITCACHE._owned.update(owned)
    assert EDITCACHE.end_session() == 1
    assert not dropped_dir.exists() and kept_dir.is_dir()
    assert not os.path.exists(listed)


def test_a_crashed_front_ends_list_is_swept_by_the_next_session(
        tmp_path, monkeypatch):
    import O4_Process_Liveness as PROC
    dropped, dropped_dir = _session_entry(tmp_path, "a", False)
    monkeypatch.setattr(EDITCACHE, "_tile_keeps", lambda entry: False)
    EDITCACHE.begin_session(frontend_pid=999999)
    EDITCACHE.register(dropped)
    EDITCACHE._owned.clear()
    monkeypatch.delenv(EDITCACHE.LIST_ENV)
    monkeypatch.setattr(PROC, "pid_is_alive", lambda pid: pid != 999999)
    EDITCACHE.begin_session(frontend_pid=os.getpid() + 2)
    assert not dropped_dir.exists()


def test_the_session_takes_the_fast_path_and_says_so(monkeypatch, tmp_path):
    """Q150: "Rebuild tile" takes it by itself — through the session's real
    step loop the vector step is not called, its row reads "updated for a
    height edit", and every later step runs."""
    from o4_engine import events as EV
    from o4_engine.session import EngineSession
    from test_engine_session import install_stub_pipeline, run_build

    calls = []
    install_stub_pipeline(monkeypatch, hooks={
        step: (lambda s: lambda tile: calls.append(s))(step)
        for step in ("vector", "mesh", "masks", "imagery")})
    stub = sys.modules["O4_Config_Utils"]

    class _ConfiguredTile(stub.Tile):
        iterate = 0

    monkeypatch.setattr(stub, "Tile", _ConfiguredTile)

    def decision(tile, step):
        if step == "vector":
            return "updated", FASTPATH.FastPathResult(applied=True)
        return "run", "the step before it changed its files or inputs"

    monkeypatch.setattr(FASTPATH, "step_decision", decision)
    events = run_build(EngineSession(), [(10, 20)], tmp_path)
    assert calls == ["mesh", "masks", "imagery"]
    labels = {e.step_key: e.label for e in events
              if isinstance(e, EV.StepProgress)}
    assert labels["vector"] == "vector data · updated for a height edit"
    assert [e.ok for e in events if isinstance(e, EV.BuildDone)] == [True]
