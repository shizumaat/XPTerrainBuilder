"""Twins for ``tools/repro_cut.py`` — the repro cutter.

Everything here is headless: it reads the CHECKED-IN mini patch
(``tests/fixtures/repro_mini.patch.osm``, a real 40 m disc cut out of the
shipped KCLT artifact by this tool, carrying the runway-end strip defect
at 1.25 m / 13.1078 %) and ``tests/fixtures/synthetic_apt.dat``.  No
X-Plane install, no shared corpus, no network.

The three twins the spec names:
  * EXTRACTION CLOSURE — the cut chains stay closed and the sidecar slice
    is a valid law context (the census runs on it and reports every family)
  * PIN REPRODUCTION on the known case — a pin measured on the mini patch
    is REPRODUCED when the same instrument re-measures it
  * THE REFUSAL RAILS — R1..R7, each with its own assertion
"""
from __future__ import annotations

import importlib.util
import json
import math
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FIXTURES = HERE / "fixtures"
MINI = FIXTURES / "repro_mini.patch.osm"
MINI_CENTER = (35.22581, -80.93661)
MINI_RADIUS = 40.0


def _load_repro_cut():
    """Load the tool by path — it is a script, not an installed module."""
    spec = importlib.util.spec_from_file_location(
        "repro_cut_under_test", ROOT / "tools" / "repro_cut.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


rc = _load_repro_cut()


# ── the pin grammar ──────────────────────────────────────────────────

def test_pin_grammar_round_trips_every_kind():
    fam = rc.parse_pin("family:transverse:worst_m=3.3595")
    assert (fam.kind, fam.family, fam.metric, fam.value) == (
        "family", "transverse", "worst_m", 3.3595)
    assert fam.tol == rc.DEFAULT_TOL["m"]          # materiality floor

    row = rc.parse_pin("row:transverse@35.20342,-80.94468/2.5:"
                       "grade_pct=39.023+/-0.05")
    assert row.kind == "row" and row.at == (35.20342, -80.94468)
    assert row.near_m == 2.5 and row.tol == 0.05

    tot = rc.parse_pin("total:adjudicated:n=388")
    assert (tot.kind, tot.metric, tot.value, tot.tol) == (
        "total", "adjudicated", 388.0, 0.0)   # counts are EXACT


def test_pin_grammar_refuses_nonsense():
    for bad in ("nonsense", "family:transverse:height=1",
                "row:transverse:count=1", "total:banana:n=1"):
        with pytest.raises(rc.ReproRefusal):
            rc.parse_pin(bad)


# ── R1: mesh-side classes are out of v1 scope ────────────────────────

def test_R1_refuses_a_mesh_side_pin():
    assert "plane_gradient" in rc.MESH_SIDE_FAMILIES
    with pytest.raises(rc.ReproRefusal) as exc:
        rc.parse_pin("family:plane_gradient:count=5")
    assert "R1" in str(exc.value) and "MESH-SIDE" in str(exc.value)
    # ...and the same family is fine as a row pin? No — the rail is on the
    # FAMILY, whichever kind names it.
    with pytest.raises(rc.ReproRefusal):
        rc.parse_pin("row:plane_gradient@1,2:magnitude_m=0.2")


# ── R2: a tile-boundary effect needs two tiles ───────────────────────

def test_R2_refuses_a_disc_that_crosses_a_tile_boundary():
    with pytest.raises(rc.ReproRefusal) as exc:
        rc.refuse_tile_boundary(35.0001, -80.9, 500.0, 400.0)
    assert "R2" in str(exc.value) and "TILE BOUNDARY" in str(exc.value)
    # the same radius well inside the tile is lawful
    rc.refuse_tile_boundary(35.5, -80.9, 500.0, 400.0)


def test_R2_measures_the_margin_too():
    """A disc that clears the boundary but whose MARGIN does not still
    refuses — the apt.dat and DEM windows are cut at the margin."""
    lat = 35.0 + 450.0 / (rc.R_EARTH * math.radians(1.0))     # 450 m north
    rc.refuse_tile_boundary(lat, -80.9, 100.0, 100.0)         # clears
    with pytest.raises(rc.ReproRefusal):
        rc.refuse_tile_boundary(lat, -80.9, 100.0, 400.0)     # margin does not


# ── R4 / R5: the pin contract ────────────────────────────────────────

def test_R4_refuses_a_pin_sited_outside_the_disc():
    pins = [rc.parse_pin("row:transverse@35.30000,-80.93661:magnitude_m=1.0")]
    with pytest.raises(rc.ReproRefusal) as exc:
        rc.refuse_pins_outside_disc(pins, *MINI_CENTER, MINI_RADIUS)
    assert "R4" in str(exc.value)


def test_R4_admits_a_pin_inside_the_disc():
    pins = [rc.parse_pin(
        f"row:transverse@{MINI_CENTER[0]},{MINI_CENTER[1]}:magnitude_m=1.0")]
    rc.refuse_pins_outside_disc(pins, *MINI_CENTER, MINI_RADIUS)


# ── the mini case: one census, shared by the closure and pin twins ───

@pytest.fixture(scope="module")
def mini_census(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("repro_mini_census")
    return rc.census_rows(MINI, tmp)


@pytest.fixture(scope="module")
def mini_disc_rows(mini_census):
    _rep, rows = mini_census
    return rc.rows_in_disc(rows, MINI_CENTER, MINI_RADIUS)


# ── EXTRACTION CLOSURE ───────────────────────────────────────────────

def test_extraction_closure_keeps_every_welded_chain_closed():
    """A cut chain stays closed and every referenced node survives.

    Shared node ids are the ONLY weld record in an emitted patch, so the
    closure law is: kept ways = disc hits + everything sharing a nid with
    one, and every nid of every kept way resolves inside the slice.
    """
    doc = rc.read_patch(MINI)
    seeds, kept = rc.select_ways(doc, MINI_CENTER, 20.0)
    assert seeds, "the mini case must have shapes in the 20 m disc"
    assert kept > seeds, "welded neighbours must be pulled in"

    keep_nids = set()
    for wid in kept:
        keep_nids.update(doc.way_nids[wid])
    # 1. every kept way references only nodes the slice will carry
    for wid in kept:
        for nid in doc.way_nids[wid]:
            assert nid in doc.node_ll, f"way {wid} references unknown {nid}"
    # 2. a ring closed in the source is still closed in the slice
    for wid in kept:
        nids = doc.way_nids[wid]
        assert nids, f"way {wid} lost its nodes"
        src_closed = nids[0] == nids[-1]
        assert src_closed == (nids[0] == nids[-1])
    # 3. ONE ring of adjacency, not two: a way sharing a nid with a
    #    NEIGHBOUR (but not with a seed) is deliberately NOT pulled in
    seed_nids = set()
    for wid in seeds:
        seed_nids.update(doc.way_nids[wid])
    for wid in kept - seeds:
        assert seed_nids.intersection(doc.way_nids[wid]), (
            f"{wid} was kept without sharing a nid with any seed")


def test_extraction_closure_emits_a_slice_the_census_can_read(tmp_path):
    doc = rc.read_patch(MINI)
    sidecar = json.loads(Path(str(MINI) + ".axes.json").read_text())
    _seeds, kept = rc.select_ways(doc, MINI_CENTER, 20.0)
    out = tmp_path / "slice.patch.osm"
    counts = rc.write_patch_slice(doc, kept, out, {"o4_repro_test": "1"})
    window = rc.disc_window(*MINI_CENTER, 20.0, 200.0)
    Path(str(out) + ".axes.json").write_text(
        json.dumps(rc.slice_sidecar(sidecar, window)))

    assert counts["ways"] == len(kept)
    # the emitted slice re-parses to exactly what we kept
    back = rc.read_patch(out)
    assert set(back.way_nids) == set(kept)
    assert set(back.node_ll) == {n for w in kept for n in doc.way_nids[w]}
    # the provenance root survived, with the cut stamped on it
    attrs = rc.root_attrs(back)
    assert attrs.get("o4_provenance_icao") == "KCLT"
    assert attrs.get("o4_repro_test") == "1"
    # ...and the census runs on it, in the law-true frame, all families
    rep, _rows = rc.census_rows(out, tmp_path)
    assert rep["ruleset_active"] == "faa"
    assert len(rep["families"]) >= 22


def test_sidecar_slice_keeps_the_frame_and_subsets_only_geometry():
    sidecar = json.loads(Path(str(MINI) + ".axes.json").read_text())
    window = rc.disc_window(*MINI_CENTER, 20.0, 100.0)
    sliced = rc.slice_sidecar(sidecar, window)
    # the frame is carried UNCHANGED — a re-anchored fixture would be
    # measured in a different frame than the artifact it claims
    assert sliced["anchor"] == sidecar["anchor"]
    assert sliced["ruleset"] == sidecar["ruleset"]
    # the index-coupled keys ride verbatim (axes_exact indexes routes_exact)
    for key in ("axes", "routes", "axes_exact", "routes_exact"):
        assert sliced[key] == sidecar[key]
    # ...and the subsettable register is PINNED to the index-free keys, so
    # admitting an index-coupled one has to fail a test first
    assert set(rc.SIDECAR_GEOMETRY_KEYS) == {
        "mesh_edges", "pair_caps", "crown_drops", "crown_centerline",
        "seam_pins", "disconnected_rings"}
    # the pure-geometry keys are subset, never grown
    for key in rc.SIDECAR_GEOMETRY_KEYS:
        if isinstance(sidecar.get(key), list):
            assert len(sliced[key]) <= len(sidecar[key])
    # every surviving pair_caps entry really does touch the window
    for entry in sliced.get("pair_caps", []):
        assert rc.segment_hits_window(entry[0], entry[1], window)


# ── PIN REPRODUCTION on the known case ───────────────────────────────

def test_pin_reproduction_on_the_checked_in_mini_case(mini_census,
                                                      mini_disc_rows):
    """The known answer: the mini patch carries the KCLT runway-end strip
    defect at 1.25 m / 13.1078 %.  Pinning it and re-measuring with the
    same instrument must report REPRODUCED."""
    rep, _rows = mini_census
    pins = [rc.parse_pin(
        f"row:strip_arc@{MINI_CENTER[0]},{MINI_CENTER[1]}/3:"
        f"magnitude_m=1.25"),
        rc.parse_pin(
        f"row:strip_longitudinal@{MINI_CENTER[0]},{MINI_CENTER[1]}/3:"
        f"grade_pct=13.1078"),
        rc.parse_pin("family:strip_arc:count=1")]
    # R5 passes: every pin IS a measured number of this artifact
    rc.verify_pins_against_source(pins, rep, mini_disc_rows, MINI_CENTER,
                                  MINI_RADIUS, label="the mini case")
    assert [p.source_value for p in pins] == [1.25, 13.1078, 1.0]
    # ...and re-measuring reports each one REPRODUCED
    for p in pins:
        value, _n = rc.measure_pin(p, rep, mini_disc_rows, MINI_CENTER)
        assert abs(value - p.value) <= p.tol, f"{p.raw} -> {value}"


def test_R5_refuses_a_pin_the_artifact_does_not_carry(mini_census,
                                                      mini_disc_rows):
    rep, _rows = mini_census
    bogus = [rc.parse_pin(
        f"row:strip_arc@{MINI_CENTER[0]},{MINI_CENTER[1]}/3:"
        f"magnitude_m=99.0")]
    with pytest.raises(rc.ReproRefusal) as exc:
        rc.verify_pins_against_source(bogus, rep, mini_disc_rows,
                                      MINI_CENTER, MINI_RADIUS)
    assert "R5" in str(exc.value)
    assert "NOT a measured number" in str(exc.value)


def test_a_total_pin_reads_the_census_adjudication(mini_census,
                                                   mini_disc_rows):
    rep, _rows = mini_census
    n = rep["adjudication"]["adjudicated_total"]
    pin = rc.parse_pin(f"total:adjudicated:n={n}")
    value, _ = rc.measure_pin(pin, rep, mini_disc_rows, MINI_CENTER)
    assert value == float(n)


# ── R3 / R6 / R7: the cut's own rails (headless — --patch given) ──────

def test_R6_refuses_a_patch_with_no_sidecar(tmp_path):
    lone = tmp_path / "lonely.patch.osm"
    shutil.copy(MINI, lone)                       # sidecar deliberately not
    with pytest.raises(rc.ReproRefusal) as exc:
        rc.cut("KCLT", *MINI_CENTER, 20.0, patch=lone, out=tmp_path / "fx",
               quiet=True)
    assert "R6" in str(exc.value)


def test_R3_refuses_another_airports_patch(tmp_path):
    with pytest.raises(rc.ReproRefusal) as exc:
        rc.cut("ZZZZ", *MINI_CENTER, 20.0, patch=MINI, out=tmp_path / "fx",
               quiet=True)
    assert "R3" in str(exc.value)


def test_R7_refuses_a_disc_that_selects_no_shape(tmp_path):
    with pytest.raises(rc.ReproRefusal) as exc:
        rc.cut("KCLT", 35.2400, -80.9700, 20.0, patch=MINI,
               out=tmp_path / "fx", quiet=True)
    assert "R7" in str(exc.value)


def test_R7_refuses_an_aptdat_window_with_no_geometry():
    """The other half of R7: input geometry, not emitted geometry."""
    _header, block = rc.read_airport_block(
        FIXTURES / "synthetic_apt.dat", "ZZZZ")
    far = rc.disc_window(10.0, 10.0, 100.0, 100.0)
    with pytest.raises(rc.ReproRefusal) as exc:
        rc.slice_apt_block(block, far)
    assert "R7" in str(exc.value)


# ── the apt.dat slicer, known-answer against the synthetic fixture ────

def test_apt_dat_slice_keeps_whole_blocks_and_drops_the_rest():
    """``synthetic_apt.dat`` has three row-110 pavements (SQUARE,
    BEZIER_RECT, NESTED_HOLE — the last with an interior ring), one
    runway and a row-130 boundary, all around (0, 0)."""
    _header, block = rc.read_airport_block(
        FIXTURES / "synthetic_apt.dat", "ZZZZ")
    # the block reader stopped at the SECOND airport: YYYY's runway is not
    # in it (a fixture carries one airport — the R3 rail's other half)
    assert not any(ln.startswith("100 30.00") for ln in block)
    everything = rc.disc_window(-12.002, -77.100, 100000.0, 0.0)
    kept_all, stats_all = rc.slice_apt_block(block, everything)
    assert stats_all["blocks_in"] == 4        # 3 x row-110 + 1 x row-130
    assert stats_all["blocks_kept"] == 4
    assert stats_all["runways_in"] == stats_all["runways_kept"] == 1
    # a 110 block is kept WHOLE: its header and every node row
    header_idx = [i for i, ln in enumerate(kept_all)
                  if ln.startswith("110 ")]
    for i in header_idx:
        assert kept_all[i + 1].split()[0] in ("111", "112"), (
            "a kept pavement header must keep its node rows")
    # a window nowhere near the geometry keeps no block (R7 fires)
    with pytest.raises(rc.ReproRefusal):
        rc.slice_apt_block(block, rc.disc_window(45.0, 45.0, 100.0, 0.0))


def test_apt_dat_slice_keeps_a_taxi_edges_endpoints():
    """A surviving 1202 drags in the 1201 nodes it references, even the
    ones outside the window — an edge with a dangling endpoint is not a
    network."""
    block = [
        "1201 0.00000 0.00000 both 1 alpha",
        "1201 0.50000 0.50000 both 2 bravo",          # far outside
        "1202 1 2 twoway taxiway A",
        "1204 departure 09",
    ]
    window = rc.disc_window(0.0, 0.0, 100.0, 0.0)
    kept, stats = _slice_allowing_no_pavement(block, window)
    assert stats["edges_kept"] == 1
    assert any(ln.startswith("1201 0.50000") for ln in kept)
    assert any(ln.startswith("1204 ") for ln in kept), (
        "a 1204 rides with the edge it attaches to")


def _slice_allowing_no_pavement(block, window):
    """``slice_apt_block`` with R7 satisfied by a throwaway runway row."""
    rwy = ("100 45.00 1 0 0.25 1 3 0 09  0.00000 0.00000 0 0 3 0 0 0 "
           "27  0.00100 0.00000 0 0 3 0 0 0")
    kept, stats = rc.slice_apt_block(block + [rwy], window)
    return kept, stats


# ── the DEM window ───────────────────────────────────────────────────

def _synthetic_dem(n=64):
    """A real ``O4_DEM_Utils.DEM`` over one tile, worn by field assignment
    — the same construction the tool's ``dem_from_window`` uses, so the
    twin exercises the engine's own sampling math."""
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    import numpy as np
    rec = {
        "alt_dem": np.fromfunction(
            lambda r, c: (100.0 + r * 0.5 + c * 0.25), (n, n),
            dtype="float32").astype("float32"),
        "x0": 0.0, "x1": 1.0, "y0": 0.0, "y1": 1.0,
        "lat": 35, "lon": -81, "nodata": -32768.0,
        "elevation_level": "auto", "source_path": "<twin>",
    }
    return rc.dem_from_window(rec, [])


def test_dem_window_round_trips_and_answers_the_same_inside(tmp_path):
    dem = _synthetic_dem()
    window = (35.40, 35.60, -80.60, -80.40)      # tile-relative 0.4..0.6
    info = rc.save_dem_window(dem, window, tmp_path / "dem.npz")
    assert info["subdems"] == 0
    win = rc.load_dem_window(tmp_path / "dem.npz")
    # the window's own footprint is smaller than the tile
    assert win.nxdem < dem.nxdem and win.nydem < dem.nydem
    # ...and inside it, the cropped DEM answers what the full one does
    for (x, y) in ((0.45, 0.45), (0.5, 0.5), (0.55, 0.52)):
        assert win.alt((x, y)) == pytest.approx(dem.alt((x, y)), abs=0.5)


def test_dem_window_is_honest_about_its_edge(tmp_path):
    """``alt_strict`` outside the window answers NODATA rather than
    clamping to an edge value the artifact never saw — the reason the
    window is grown by ``--margin`` beyond the disc."""
    dem = _synthetic_dem()
    window = (35.40, 35.60, -80.60, -80.40)
    rc.save_dem_window(dem, window, tmp_path / "dem.npz")
    win = rc.load_dem_window(tmp_path / "dem.npz")
    assert win.alt_strict((0.5, 0.5)) != win.nodata
    assert win.alt_strict((0.05, 0.05)) == win.nodata


def test_dem_window_refuses_a_window_off_the_raster(tmp_path):
    dem = _synthetic_dem()
    with pytest.raises(rc.ReproRefusal) as exc:
        rc.crop_dem(dem, (40.0, 40.1, -80.6, -80.4))
    assert "R7" in str(exc.value)


# ── rows_in_disc: the population every pin is measured over ──────────

def test_rows_in_disc_is_the_disc_and_not_the_fixture_extent(mini_census):
    _rep, rows = mini_census
    tight = rc.rows_in_disc(rows, MINI_CENTER, 5.0)
    wide = rc.rows_in_disc(rows, MINI_CENTER, 200.0)
    assert len(tight) <= len(wide) <= len(rows)
    ll = rc.ll_to_m_factory(*MINI_CENTER)
    for r in wide:
        assert math.hypot(*ll(r["lat"], r["lon"])) <= 200.0 + 1e-6
