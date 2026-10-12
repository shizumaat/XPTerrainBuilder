"""THE TILE-WIDE INSET PRE-FLIGHT and the ``dem`` refresh that completes
it -- issue #583.

MEASURED 2026-10-12.  (A) ``build_airport.py KBFI --tile 47 -123`` named
no pending inset work; the tile build's inset pass then re-fetched KGRF's
and KTCM's insets (a resolution-ladder rung listing new coverage) into
the shared corpus -- the per-airport verdict was asked for the one named
airport on an airport build and for NOBODY on a ``--tile`` build.
(B) ``KPDX --tile 45 -123 --refresh-data rings,dem --refresh-only``
answered "nothing to derive" and then refused on nine version-stale
inset negatives, naming the scope that had just run.

OFFLINE: the engine's predicates are stubbed at the engine's own names
(or run for real against a fake provider), on tmp directories.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"
sys.path.insert(0, str(ROOT / "src"))

from test_inset_resolution_ladder import (               # noqa: E402,F401
    BOX, requires_gdal, two_providers)

STATE = {"tile_stem": "N47W123", "airport_insets": True,
         "airports_layer": True, "base_raster": True}
BOXES = {"KBFI": (0.0, 0.0, 1.0, 1.0), "KGRF": (1.0, 1.0, 2.0, 2.0),
         "KTCM": (2.0, 2.0, 3.0, 3.0), "KXXX": (3.0, 3.0, 4.0, 4.0)}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def build_mod():
    return _load("harness_refetch583_build", HARNESS / "build_airport.py")


@pytest.fixture
def ipf(build_mod):
    return build_mod.IPF


class _Notes:
    def __init__(self):
        self.lines = []

    def note(self, msg):
        self.lines.append(msg)


def _stub_tile(monkeypatch, build_mod, verdicts, ladder=None):
    """A tile of four aerodromes, three of them selected; the engine's
    frame predicate answers from ``verdicts`` and the ladder re-check
    from ``ladder``."""
    import O4_Airport_Elevation_Insets as INSETS
    import O4_Config_Utils as CFG
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP

    asked = []
    monkeypatch.setattr(CFG, "Tile", lambda lat, lon, _s:
                        types.SimpleNamespace(lat=lat, lon=lon,
                                              read_from_config=lambda: None))
    monkeypatch.setattr(OSM, "OSM_layer", lambda: None)
    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer", lambda *a, **k: None)
    monkeypatch.setattr(VMAP, "build_airports_dico",
                        lambda _t, _l: {key: {} for key in BOXES})
    monkeypatch.setattr(INSETS, "insets_enabled_for_tile", lambda tile: True)
    monkeypatch.setattr(INSETS, "resolved_inset_mode", lambda tile: "ICAO")
    monkeypatch.setattr(INSETS, "inset_keys",
                        lambda dico, mode: {"KBFI", "KGRF", "KTCM"})
    monkeypatch.setattr(
        INSETS, "_airport_bounding_boxes",
        lambda tile, dico, only=None: {
            key: box for key, box in BOXES.items()
            if only is None or key in only})
    monkeypatch.setattr(
        INSETS, "airport_inset_frame_problem",
        lambda lat, lon, icao, required, *a, **k:
        asked.append((icao, required)) or verdicts.get(icao))
    monkeypatch.setattr(build_mod, "apply_xplane_install_paths_for_preflight",
                        lambda: asked.append("paths") or {})
    monkeypatch.setattr(
        build_mod, "_ladder_recheck_problem",
        lambda _insets, lat, lon, icao, required: (ladder or {}).get(icao))
    return asked


def test_a_tile_build_names_every_inset_its_pass_would_refetch(
        build_mod, monkeypatch):
    """(A) The engine's own verdicts, asked for every SELECTED aerodrome
    of the tile -- not for the airport the command happens to name."""
    asked = _stub_tile(
        monkeypatch, build_mod,
        verdicts={"KTCM": ("stale", "KTCM was cut for a smaller box"),
                  "KBFI": ("empty", "KBFI's raster is declared empty"),
                  "KXXX": ("stale", "not selected: never asked")},
        ladder={"KGRF": ("ladder", "LADDER-STALE … KGRF (--refresh-data "
                                   "dem; --warm-insets KGRF)")})
    rows = build_mod.tile_inset_refetch_rows(STATE, 47, -123)
    assert rows == [
        ("dem", "Elevation_data/**/N47W123_airport_insets/KGRF_*.tif "
                "[ladder]", "LADDER-STALE … KGRF (--refresh-data dem; "
                            "--warm-insets KGRF)"),
        ("dem", "Elevation_data/**/N47W123_airport_insets/KTCM_*.tif "
                "[stale]", "KTCM was cut for a smaller box")]
    # the owner's X-Plane paths are applied BEFORE the predicate runs
    assert asked[0] == "paths"
    assert [row[0] for row in asked[1:]] == ["KBFI", "KGRF", "KTCM"]
    # a tile already refused for its whole cache or its layer: no query
    for key in ("airport_insets", "airports_layer"):
        assert build_mod.tile_inset_refetch_rows(
            dict(STATE, **{key: False}), 47, -123) == []


def test_the_missing_artifact_list_carries_them_on_a_tile_build_only(
        build_mod, monkeypatch, tmp_path):
    """A ``--tile`` run passes no ICAO: the tile-wide rows join the list
    the refusal prints.  An airport build keeps its one-airport verdict."""
    row = ("dem", "Elevation_data/**/N47W123_airport_insets/KGRF_*.tif "
                  "[ladder]", "LADDER-STALE")
    monkeypatch.setattr(build_mod, "tile_inset_refetch_rows",
                        lambda state, lat, lon: [row])
    for name in ("unverified_inset_negatives", "schema_stale_osm_layers"):
        monkeypatch.setattr(build_mod, name, lambda *a, **k: [])
    monkeypatch.setattr(build_mod, "missing_pack_dsf_dumps",
                        lambda *a, **k: [])
    monkeypatch.setattr(build_mod, "this_airports_inset_problem",
                        lambda *a, **k: None)
    assert build_mod.missing_shared_artifacts(
        tmp_path, 47, -123, None, state=STATE) == [row]
    assert build_mod.missing_shared_artifacts(
        tmp_path, 47, -123, "KBFI", state=STATE) == []
    with pytest.raises(SystemExit) as refusal:
        build_mod.require_no_implicit_refresh([row], set())
    assert "KGRF_*.tif [ladder]" in str(refusal.value)
    assert "--refresh-data dem" in str(refusal.value)


@requires_gdal
def test_the_tile_wide_verdict_is_the_engines_ladder_recheck_for_real(
        build_mod, ipf, monkeypatch, two_providers):
    """No stub between the harness and the engine: a rung that did not
    answer makes the next build re-fetch, and the pre-flight says so; a
    rung DECLINED BY A CAP under the same listing does not (#583)."""
    import O4_Airport_Elevation_Insets as INSETS

    plan, _calls, chain, _other, _raise = two_providers
    monkeypatch.setattr(INSETS, "initialize_elevation_providers_dict",
                        lambda: INSETS.elevation_providers_dict)
    monkeypatch.setattr(ipf, "required_boxes",
                        lambda lat, lon, selected_only: {"KASE": BOX})
    state = dict(STATE, tile_stem="N39W107")
    plan.update({"FAKE3DEP:1": {"valid": None, "listing": []},
                 "FAKEPIT": {"transient": "index outage", "listing": ["T1"]},
                 "FAKE3DEP:10": {"valid": 1.0, "listing": ["n1"]}})
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    rows = build_mod.tile_inset_refetch_rows(state, 39, -107)
    assert [(scope, artifact) for (scope, artifact, _why) in rows] == [
        ("dem", "Elevation_data/**/N39W107_airport_insets/KASE_*.tif "
                "[ladder]")]
    assert "T1" in rows[0][2] and "--refresh-data dem" in rows[0][2]
    plan["FAKEPIT"] = {"cap": "2 tiles", "listing": ["T1", "T2", "T3"]}
    INSETS.ensure_airport_insets(39, -107, {"KASE": BOX}, [chain], None)
    build_mod.LADDER_RECHECKS.clear()
    assert build_mod.tile_inset_refetch_rows(state, 39, -107) == []


def _warm_tile_root(tmp_path, monkeypatch):
    import O4_File_Names as FNAMES

    root = tmp_path / "lane"
    elev = root / "Elevation_data" / "N40W130"
    (elev / "N45W123_airport_insets").mkdir(parents=True)
    (elev / "N45W123.hgt").write_bytes(b"raster")
    osm = root / "OSM_data"
    osm.mkdir()
    monkeypatch.setattr(FNAMES, "OSM_dir", str(osm))
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(root / "Elevation_data"))
    layer = Path(FNAMES.osm_cached(45, -123, "airports"))
    layer.parent.mkdir(parents=True, exist_ok=True)
    layer.write_bytes(b"layer")
    return root


def test_a_dem_refresh_reasks_the_stale_negatives_it_used_to_refuse_on(
        build_mod, ipf, monkeypatch, tmp_path):
    """(B) one command: the airports the pre-flight's own rows name are
    run through the production pass AS A BUILD WOULD (``refresh=False``),
    on an airport build and a tile build alike."""
    root = _warm_tile_root(tmp_path, monkeypatch)
    state = build_mod.dem_cache_state(root, 45, -123)
    assert state["base_raster"] and state["airport_insets"]
    assert state["airports_layer"]
    negative = ("dem", "Elevation_data/**/N45W123_airport_insets/index.json "
                       "[Lehman Field:USGS3DEP]", "version-stale negative")
    pending = {"negatives": [negative]}
    monkeypatch.setattr(build_mod, "unverified_inset_negatives",
                        lambda state, lat, lon: list(pending["negatives"]))
    monkeypatch.setattr(ipf, "stale_negative_airports",
                        lambda lat, lon: ["Lehman Field", "Gone Airpark"])
    monkeypatch.setattr(ipf, "tile_pending_refetches",
                        lambda *a, **k: [("KGRF", "ladder", "LADDER-STALE")])
    monkeypatch.setattr(ipf, "required_boxes",
                        lambda lat, lon, selected_only: {
                            "Lehman Field": BOX, "KGRF": BOX, "KPDX": BOX})
    monkeypatch.setattr(build_mod, "this_airports_inset_problem",
                        lambda *a, **k: None)
    monkeypatch.setattr(build_mod, "tile_inset_refetch_rows",
                        lambda state, lat, lon: [])
    warmed = []

    def _warm(icaos, _root, lat, lon, prog, *, refresh=True):
        warmed.append((list(icaos), refresh))
        pending["negatives"] = []
        return {}

    monkeypatch.setattr(build_mod, "warm_airport_insets", _warm)
    notes = _Notes()
    out = build_mod.refresh_tile_dem(root, 45, -123, notes)
    assert warmed == [(["KGRF", "Lehman Field"], False)]
    assert out["derived"] == [
        "Elevation_data/**/N45W123_airport_insets/ "
        "[completed: KGRF, Lehman Field]"]
    assert not any("nothing to derive" in line for line in notes.lines)
    # an AIRPORT build re-asks the negatives too (they refuse it as well)
    # and leaves the other aerodromes' pending re-fetches alone
    warmed.clear()
    pending["negatives"] = [negative]
    build_mod.refresh_tile_dem(root, 45, -123, _Notes(), icao="KPDX")
    assert warmed == [(["Lehman Field"], False)]
    # nothing pending: the old answer, and no pass
    warmed.clear()
    monkeypatch.setattr(ipf, "stale_negative_airports", lambda lat, lon: [])
    monkeypatch.setattr(ipf, "tile_pending_refetches", lambda *a, **k: [])
    notes = _Notes()
    assert build_mod.refresh_tile_dem(root, 45, -123, notes)["derived"] == []
    assert warmed == []
    assert any("nothing to derive" in line for line in notes.lines)


def test_a_dem_refresh_that_leaves_a_row_pending_refuses(
        build_mod, ipf, monkeypatch, tmp_path):
    """A provider that did not answer leaves its negative in place: the
    refresh says so itself, naming the row -- never exit 0."""
    root = _warm_tile_root(tmp_path, monkeypatch)
    negative = ("dem", "index.json [Lehman Field:USGS3DEP]", "still stale")
    monkeypatch.setattr(build_mod, "unverified_inset_negatives",
                        lambda state, lat, lon: [negative])
    monkeypatch.setattr(ipf, "stale_negative_airports",
                        lambda lat, lon: ["Lehman Field"])
    monkeypatch.setattr(ipf, "required_boxes",
                        lambda lat, lon, selected_only: {"Lehman Field": BOX})
    monkeypatch.setattr(build_mod, "this_airports_inset_problem",
                        lambda *a, **k: None)
    monkeypatch.setattr(build_mod, "warm_airport_insets",
                        lambda *a, **k: {})
    with pytest.raises(SystemExit) as refusal:
        build_mod.refresh_tile_dem(root, 45, -123, _Notes(), icao="KPDX")
    assert "STILL pending" in str(refusal.value)
    assert "Lehman Field:USGS3DEP" in str(refusal.value)


def test_the_warm_pass_hands_its_refresh_flag_to_the_engine(
        build_mod, monkeypatch, tmp_path):
    import O4_Airport_Elevation_Insets as INSETS
    import O4_OSM_Utils as OSM
    import O4_Vector_Map as VMAP

    root = _warm_tile_root(tmp_path, monkeypatch)
    seen = []
    monkeypatch.setattr(OSM, "OSM_queries_to_OSM_layer", lambda *a, **k: None)
    monkeypatch.setattr(VMAP, "build_airports_dico",
                        lambda tile, layer: {"KPDX": {}})
    monkeypatch.setattr(INSETS, "_airport_bounding_boxes",
                        lambda tile, dico: {key: BOX for key in dico})
    monkeypatch.setattr(INSETS, "select_provider_definitions",
                        lambda providers: [{"code": "STUB"}])
    monkeypatch.setattr(INSETS, "parse_airport_elevation_level",
                        lambda level: 1.0)
    monkeypatch.setattr(INSETS, "airport_boundary_polygons",
                        lambda tile, dico, only=None: None)
    monkeypatch.setattr(INSETS, "ensure_airport_insets",
                        lambda *a, **kw: seen.append(kw["refresh"]))
    build_mod.warm_airport_insets(["KPDX"], root, 45, -123, _Notes())
    build_mod.warm_airport_insets(["KPDX"], root, 45, -123, _Notes(),
                                  refresh=False)
    assert seen == [True, False]


# ── the guard: cleanup of a write it could not see ───────────────────

def _armed_corpus(build_mod, tmp_path):
    guard_mod = sys.modules["shared_repo_guard"]
    repo = tmp_path / "corpus"
    clips = repo / "OSM_data" / "_regional_extracts" / "clips"
    clips.mkdir(parents=True)
    guard = guard_mod.SharedRepoWriteGuard(set(), str(tmp_path / "lane"),
                                           repo=str(repo))
    return guard_mod, guard, clips


def test_the_guard_lets_a_run_remove_the_temporary_it_wrote_past_it(
        build_mod, tmp_path):
    """(d) A child or a C library wrote ``….tmp-<our pid>-…`` into the
    corpus after the guard armed; the Python ``os.remove`` is the first
    call the guard sees.  Refusing it is what LEFT the file there (#159,
    #583): it is let through, the corpus is clean again -- and the write
    is on the record, so the run still fails naming it."""
    import os

    guard_mod, guard, clips = _armed_corpus(build_mod, tmp_path)
    with guard:
        mine = clips / ("clip_ab.tmp-%d-7.osm.pbf" % os.getpid())
        other = clips / ("clip_cd.tmp-%d-7.osm.pbf" % (os.getpid() + 1))
        for path in (mine, other):
            # the unpatched open: past the guard, as GDAL or a child writes
            guard._saved["open"](str(path), "wb").close()
        os.remove(str(mine))
        with pytest.raises(guard_mod.SharedRepoWriteBlocked):
            os.remove(str(other))          # another process's: refused
        with pytest.raises(guard_mod.SharedRepoWriteBlocked):
            open(str(mine), "wb")          # a WRITE is still refused
    assert not mine.exists() and other.exists()
    assert [row["via"] for row in guard.blocked] == [
        guard_mod.UNSEEN_WRITE_VIA % "remove", "os.remove",
        "open for writing"]
    with pytest.raises(SystemExit) as failure:
        guard_mod.require_no_swallowed_write_block(guard.blocked[:1])
    assert mine.name in str(failure.value)


def test_the_guard_still_refuses_removing_a_temporary_older_than_itself(
        build_mod, tmp_path):
    import os

    guard_mod, guard, clips = _armed_corpus(build_mod, tmp_path)
    old = clips / ("clip_ab.tmp-%d-7.osm.pbf" % os.getpid())
    old.write_bytes(b"left by an earlier run that reused this pid")
    guard_mod_time = guard_mod.time.time
    with guard:
        guard.armed_at = guard_mod_time() + 60.0   # armed AFTER the file
        with pytest.raises(guard_mod.SharedRepoWriteBlocked):
            os.remove(str(old))
    assert old.exists()
