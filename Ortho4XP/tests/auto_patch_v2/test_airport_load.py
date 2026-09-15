"""M1 loader twins: the CYXY fixtures (the custom pack's apt.dat block,
its CIFP RWY records, cropped OSM feeds, the cropped DSFTool dump, a
synthetic DEM + inset) round-trip through ``airport.load``; the record
grammars, the bezier flattening, the DEM composite and the pack
selection are checked in isolation."""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

from auto_patch_v2.airport import apt_dat as A
from auto_patch_v2.airport import cifp as C
from auto_patch_v2.airport import dem as D
from auto_patch_v2.airport import dsf as S
from auto_patch_v2.airport import osm as O
from auto_patch_v2.airport import pack as P
from auto_patch_v2.airport.load import (Inputs, load_with_report,
                                        normalise_surface, runway_code_letter,
                                        runway_code_number)
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Surface
from auto_patch_v2.model.frame import Frame

FIX = Path(__file__).resolve().parent / "fixtures" / "CYXY"


def fixture_inputs() -> Inputs:
    return Inputs(xplane_root=str(FIX), cifp_dir=str(FIX / "CIFP"),
                  osm_root=str(FIX / "OSM_data"),
                  elevation_root=str(FIX / "Elevation_data"), dem_frame="authored",
                  mod_cache_root=str(FIX / "Airport_mod_cache"))


@pytest.fixture(scope="module")
def cyxy():
    return load_with_report("CYXY", fixture_inputs(), Law.for_airport("CYXY"))


# ── fixtures stay small ──────────────────────────────────────────────────

def test_fixture_budget_200kb():
    total = sum(p.stat().st_size for p in FIX.rglob("*") if p.is_file())
    assert total <= 200 * 1024, total


# ── apt.dat ──────────────────────────────────────────────────────────────

def test_pack_selection_prefers_custom_pack_with_pavement():
    sel = P.select_pack(str(FIX), "CYXY")
    assert sel is not None and sel.name == "CYXY Fixture" and sel.custom
    assert A.find_apt_dat(str(FIX), "ZZZZ") is None


def test_block_grammar(cyxy):
    a, rep = cyxy
    assert a.icao == "CYXY" and a.name.startswith("Whitehorse")
    assert [r.id for r in a.runways] == ["14R/32L", "14L/32R", "02/20"]
    r = a.runways[0]
    assert r.width_m == pytest.approx(45.72) and r.surface == Surface.ASPHALT
    assert 2890 < r.length_m < 2905 and r.code_number == 4 and r.code_letter == "E"
    assert a.runways[2].code_number == 1               # 428 m: code 1
    assert a.runways[2].ends[1].overrun_m == pytest.approx(120.0)
    assert rep.helipads == ("H1", "H2", "H3", "H4", "H5", "H6")   # reported, not graded
    assert len([p for p in a.pavements if p.id.startswith("pav")]) == 31
    assert sum(len(p.holes) for p in a.pavements) >= 3
    assert len(a.linear_features) == 72 and len(a.boundaries) == 1
    assert len(a.taxi_nodes) == 188 and len(a.taxi_edges) == 105
    assert len(a.ground_routes) == 86 and len(a.startups) == 20
    assert {e.width_class for e in a.taxi_edges if not e.is_runway} == \
        {"A", "B", "C", "D", "E"}
    assert sum(1 for e in a.taxi_edges if e.is_runway) == 18
    assert a.frame.origin == pytest.approx((60.710278, -135.067778))
    assert a.frame.identity_dp == 11
    assert a.elevation_m == pytest.approx(2314 * 0.3048)


def test_surface_normalisation():
    assert normalise_surface(23) == Surface.ASPHALT
    assert normalise_surface(53) == Surface.CONCRETE
    assert normalise_surface(2) == Surface.CONCRETE
    assert normalise_surface(13) == Surface.WATER
    assert runway_code_number(799) == 1 and runway_code_number(1800) == 4
    assert runway_code_letter(30.48) == "D" and runway_code_letter(45.72) == "E"


def test_bezier_flattening_bounds():
    """A 40 m quadratic bezier span tessellates to a few vertices, each
    within the sagitta bound of the exact curve (and the straight-chord
    rule leaves a 1 m corner-softening bezier alone)."""
    lat = 60.71
    m = 1.0 / 111320.0
    lonm = m / math.cos(math.radians(lat))

    def node(rt, x, y, cx=None, cy=None):
        r = [rt, f"{lat + y * m:.10f}", f"{-135.0 + x * lonm:.10f}"]
        if cx is not None:
            r += [f"{lat + cy * m:.10f}", f"{-135.0 + cx * lonm:.10f}"]
        return r

    rows = [["110", "1", "0.00", "0.0"], node("112", 0, 40, 30, 40),
            node("111", 40, 0), node("113", 0, 0)]
    pv = A._pavement(rows[0], rows[1:], 0)
    assert pv is not None
    ring = pv.rings[0]
    assert 5 <= len(ring) <= 30
    exact = [((1 - t) ** 2 * 0 + 2 * (1 - t) * t * 30 + t * t * 40,
              (1 - t) ** 2 * 40 + 2 * (1 - t) * t * 40 + t * t * 0)
             for t in [i / 400 for i in range(401)]]
    for lon, la in ring:
        x, y = (lon + 135.0) / lonm, (la - lat) / m
        if 0.5 < x < 39.5:
            assert min(math.hypot(x - ex, y - ey) for ex, ey in exact) < 0.5, (x, y)
    soft = [["110", "1", "0.00", "0.0"], node("112", 0, 40, 0.3, 40.3),
            node("111", 40, 0), node("113", 0, 0)]
    assert len(A._pavement(soft[0], soft[1:], 0).rings[0]) == 3


def test_dsf_facade_control_point_is_the_last_two_columns():
    """A facade winding at cpp 5 is ``lon lat wall ctrl_lon ctrl_lat``:
    the control point is the LAST two columns, never columns 2-3
    (measured SPJC M3b: one Cargo_Terminal.fac winding read ``wall``
    as ``ctrl_lon`` and flattened 2,000 km wide; its union swallowed
    128 of 135 pads)."""
    pts5 = [["-77.1203", "-12.0046", "4.0", "-77.1203", "-12.0046"],
            ["-77.1203", "-12.0047", "4.0", "-77.1203", "-12.0047"],
            ["-77.1202", "-12.0047", "4.0", "-77.1202", "-12.0047"],
            ["-77.1202", "-12.0046", "4.0", "-77.1202", "-12.0046"]]
    ring5 = S._flatten(pts5, 5)
    assert len(ring5) == 4
    assert all(-77.2 < lon < -77.0 and -12.1 < lat < -11.9 for lon, lat in ring5)
    # cpp 3 (lon lat wall) has no control point at all
    ring3 = S._flatten([p[:3] for p in pts5], 3)
    assert ring3 == ring5
    # a real cpp-5 bezier (control off the node) still tessellates
    bez = [list(p) for p in pts5]
    bez[0][3], bez[0][4] = "-77.12035", "-12.00465"
    assert len(S._flatten(bez, 5)) > 4


def test_block_sha_is_stable():
    block = A.read_airport_block(str(FIX / "Custom Scenery" / "CYXY Fixture"
                                     / "Earth nav data" / "apt.dat"), "CYXY")
    assert block and A.block_sha256(block) == A.block_sha256(list(block))


# ── CIFP ─────────────────────────────────────────────────────────────────

def test_cifp_join(cyxy):
    a, rep = cyxy
    assert C.parse_lat("N60431814") == pytest.approx(60.7217, abs=1e-4)
    assert C.parse_lon("W135043590") == pytest.approx(-135.0766, abs=1e-4)
    recs = C.read_cifp_runways(str(FIX / "CIFP" / "CYXY.dat"))
    assert set(recs) == {"02", "14L", "14R", "20", "32L", "32R"}
    assert rep.cifp_missing_ends == ()
    ends = {e.name: e.threshold_elev_m for r in a.runways for e in r.ends}
    assert ends["14R"] == pytest.approx(2277 * 0.3048)
    assert ends["32L"] == pytest.approx(2317 * 0.3048)
    assert C.match_designator("2", recs) is recs["02"]
    assert C.match_designator("99", recs) is None


# ── OSM ──────────────────────────────────────────────────────────────────

def test_osm_feeds(cyxy):
    a, rep = cyxy
    assert len(rep.osm_sources) == 3
    kinds = {w.kind for w in a.osm_ways}
    assert kinds == {"airports", "airport_small_roads", "big_roads"}
    assert any(w.tags.get("aeroway") == "taxiway" for w in a.osm_ways)
    assert any(w.tags.get("bridge") for w in a.osm_ways)
    assert set(O.TAGS_OF_INTEREST) >= {"highway", "bridge", "tunnel", "layer"}
    assert O.feed_path(str(FIX / "OSM_data"), 60, -136, "airports").endswith(
        "+60-140/+60-136/+60-136_airports.osm.bz2")
    assert rep.buildings_by_source["osm"] == 4


# ── DSF ──────────────────────────────────────────────────────────────────

def test_dsf_dump(cyxy):
    a, rep = cyxy
    assert rep.dsf_dump_path and rep.dsf_dump_path.endswith("+60-136.dsf.fixture.text")
    assert rep.buildings_by_source["dsf:fac"] >= 60
    assert rep.buildings_by_source["dsf:object"] == 2       # the cached OBJ8 footprints
    assert rep.dsf_pavements >= 40                          # stock .pol pages
    assert any(p.id.startswith("dsf:pol") and p.surface == Surface.CONCRETE
               for p in a.pavements)
    assert len(a.dsf_objects) == 30 and rep.unresolved_objects == 30
    assert S.building_role_for_def("lib/airport/Modern_Airports/Terminal_kit/term_building_Ground_01.fac") == "terminal"
    assert S.building_role_for_def("lib/g10/global_objects/wall_res_stucco.fac") is None
    assert S.is_pavement_def("lib/airport/pavement/asphalt_5L.pol")
    assert not S.is_pavement_def("lib/airport/lines/20_road_edge.lin")
    assert not S.is_pavement_def("lib/airport/markings/DrapedDirSigns.pol")


# ── DEM ──────────────────────────────────────────────────────────────────

def test_dem_composite_and_feather(cyxy):
    a, rep = cyxy
    assert "inset" in rep.dem_provenance and rep.dem_provenance["inset_provider"] == "FIXTURE"
    dem = a.dem
    base = D.HgtRaster.read(str(FIX / "Elevation_data" / "+60-140" / "N60W136.hgt"), 60, -136)
    ins = dem.inset
    assert ins is not None
    # inside the inset core (> feather from its edge) the composite IS the inset
    lat, lon = 60.7103, -135.0678
    x, y = _xy(dem, lat, lon)
    zi = float(ins.sample(np.array([lat]), np.array([lon]))[0])
    assert dem.z(x, y) == pytest.approx(zi, abs=1e-6)
    assert zi > float(base.sample(np.array([lat]), np.array([lon]))[0])
    # far outside the inset the composite is the base
    lat2, lon2 = 60.60, -135.20
    zb2 = float(base.sample(np.array([lat2]), np.array([lon2]))[0])
    assert dem.z(*_xy(dem, lat2, lon2)) == pytest.approx(zb2, abs=1e-6)
    # across the feather the weight ramps 0 -> 1 from the inset edge: an
    # in-memory 1 m inset (base + 10 m) beside the fixture base
    lat_n, lon_w = 60.72, -135.10
    dlat = 1.0 / 111320.0
    dlon = dlat / math.cos(math.radians(60.71))
    rr = np.arange(400)[:, None]
    cc = np.arange(400)[None, :]
    lat_c = lat_n - (rr + 0.5) * dlat
    lon_c = lon_w + (cc + 0.5) * dlon
    data = base.sample(np.broadcast_to(lat_c, (400, 400)).copy(),
                       np.broadcast_to(lon_c, (400, 400)).copy()).astype(np.float32) + 10.0
    hi_ins = D.GeoTiffRaster("mem", lon_w, lat_n, dlon, dlat, data, None)
    dem2 = D.DemSampler(a.frame, str(FIX / "Elevation_data"), hi_ins, 60.0, {})
    mid = lat_n - 200 * dlat
    for d, lo, hi in ((1.0, 0.0, 0.05), (30.0, 0.45, 0.55), (90.0, 0.98, 1.02)):
        lon_d = lon_w + d * dlon
        zb = float(base.sample(np.array([mid]), np.array([lon_d]))[0])
        z = dem2.z(*_xy(dem2, mid, lon_d))
        frac = (z - zb) / 10.0
        assert lo - 0.02 <= frac <= hi + 0.02, (d, frac)
    assert not math.isnan(dem.z(0.0, 0.0))
    xmin, ymin, xmax, ymax = dem.bounds()
    assert xmin < 0 < xmax and ymin < 0 < ymax


def _xy(dem, lat, lon):
    from pyproj import Transformer
    fwd = Transformer.from_crs("EPSG:4326", dem.frame.crs, always_xy=True)
    x, y = fwd.transform(lon, lat)
    return float(x), float(y)


def test_hgt_conventions(tmp_path):
    n = 5
    data = np.arange(n * n, dtype=">i2").reshape(n, n)
    p = tmp_path / "N10E020.hgt"
    data.tofile(p)
    r = D.HgtRaster.read(str(p), 10, 20)
    assert r.n == 5
    assert r.sample(np.array([11.0]), np.array([20.0]))[0] == 0.0     # NW corner = row 0
    assert r.sample(np.array([10.0]), np.array([21.0]))[0] == 24.0    # SE corner
    assert math.isnan(r.sample(np.array([12.0]), np.array([20.0]))[0])
    assert D.hgt_name(-13, -78) == "S13W078"
    hgt, tif, js = D.resolve_dem_files(str(FIX / "Elevation_data"), 60.71, -135.07, "CYXY")
    assert hgt.endswith("N60W136.hgt") and tif and tif.endswith("CYXY_fixture.tif") and js


# ── pack signature ───────────────────────────────────────────────────────

def test_pack_signature(cyxy):
    a, rep = cyxy
    assert a.pack.name == "CYXY Fixture"
    assert len(a.pack.apt_dat_sha256) == 64
    assert a.pack.dsf_paths == () and a.pack.dsf_sha256 == ()   # fixture pack has no DSF
    assert a.ruleset_key == "icao"


def test_no_dem_root_is_reported():
    inp = Inputs(xplane_root=str(FIX), cifp_dir="", osm_root="", elevation_root="",
                 mod_cache_root="")
    a, rep = load_with_report("CYXY", inp)
    assert rep.notes and math.isnan(a.dem.z(0.0, 0.0))
    assert rep.cifp_missing_ends == ("14R", "32L", "14L", "32R", "02", "20")
    assert a.osm_ways == () and a.dsf_objects == ()


def test_frame_key_is_identity_precision():
    fr = Frame("X", (60.0, -135.0), 11)
    assert fr.key(60.123456789012, -135.0) == (60.12345678901, -135.0)
    assert os.path.basename(A.__file__) == "apt_dat.py"


def test_dem_fixture_is_the_generator_output():
    """The committed synthetic rasters ARE what
    ``fixtures/make_dem_fixture.py`` writes (M3a fixture repair: the M1
    rasters were never committed — ``.gitignore`` ate the corpus-named
    directories — so the generator, not a lost file, is the record)."""
    sys.path.insert(0, str(FIX.parent))
    import make_dem_fixture as G
    assert G.check() == []


# ── the DSF text dump is chosen by the DSF's identity, never by name order
# (OTHH 2026-09-04: the legacy ``+25+051.dsf.text`` of 07-30 out-sorted the
# fresh ``+25+051.dsf.e9df4ffc.text`` and no v2 build saw the pack's new
# tunnel wall objects) ────────────────────────────────────────────────────

def test_text_dump_tag_is_the_engine_cache_tag(tmp_path):
    from auto_patch import dsf_reader as v1
    dsf = tmp_path / "pack" / "Earth nav data" / "+20+050" / "+25+051.dsf"
    dsf.parent.mkdir(parents=True)
    dsf.write_bytes(b"XPLNEDSF")
    v1_name = os.path.basename(v1._default_pack_text_cache_path(str(tmp_path), str(dsf)))
    assert v1_name == f"+25+051.dsf.{S.text_dump_tag(str(dsf))}.text"
    assert S.dsf_path_in_pack(str(tmp_path / "pack"), 25, 51) == str(dsf)
    assert S.dsf_path_in_pack("/p", -13, -78).endswith("/Earth nav data/-20-080/-13-078.dsf")


def test_find_text_dump_prefers_the_keyed_fresh_dump_and_refuses_stale(tmp_path):
    import time
    pack = tmp_path / "xp" / "Custom Scenery" / "OTHH Pack"
    dsf = pack / "Earth nav data" / "+20+050" / "+25+051.dsf"
    dsf.parent.mkdir(parents=True)
    root = tmp_path / "mod_cache"
    d = root / "OTHH Pack"
    d.mkdir(parents=True)
    legacy = d / "+25+051.dsf.text"
    legacy.write_text("OBJECT_DEF old\n")
    t0 = time.time() - 3600
    os.utime(legacy, (t0, t0))                       # 07-30
    dsf.write_bytes(b"XPLNEDSF")
    os.utime(dsf, (t0 + 600, t0 + 600))              # the pack changed later
    # every dump older than the DSF: refused, not the legacy one by name
    assert S.find_text_dump(str(root), "OTHH Pack", 25, 51, dsf_path=str(dsf)) is None
    keyed = d / f"+25+051.dsf.{S.text_dump_tag(str(dsf))}.text"
    keyed.write_text("OBJECT_DEF Objects/tunnels/tunnel1.obj\n")
    os.utime(keyed, (t0 + 1200, t0 + 1200))
    assert S.find_text_dump(str(root), "OTHH Pack", 25, 51, dsf_path=str(dsf)) == str(keyed)
    # a fixture dir with no DSF path: the newest by mtime, never by name
    assert S.find_text_dump(str(root), "OTHH Pack", 25, 51) == str(keyed)


def test_uv_mapped_pol_columns_are_texture_coordinates(tmp_path):
    """``BEGIN_POLYGON idx 65535 4``: lon lat u v — a 4-point junction
    marking stays a 4-point quad (RULINGS 2026-09-06a: read as beziers it
    spanned 23° and LEGT sampled a cold tile 1,300 km away)."""
    text = "\n".join([
        "POLYGON_DEF lib/airport/ground/roads/asphalt/junctions.pol",
        "BEGIN_POLYGON 0 65535 4", "BEGIN_WINDING",
        "POLYGON_POINT -3.883824960 40.521518082 0.015594720 0.406286717",
        "POLYGON_POINT -3.883962768 40.521478504 0.578088045 0.406286717",
        "POLYGON_POINT -3.883932250 40.521416037 0.578088045 0.609399557",
        "POLYGON_POINT -3.883794442 40.521455615 0.015594720 0.609399557",
        "END_WINDING", "END_POLYGON",
        "BEGIN_POLYGON 0 0 4", "BEGIN_WINDING",       # a heading-param polygon: columns 2-3 ARE a control point
        "POLYGON_POINT -3.8838 40.5215 -3.8839 40.5216",
        "POLYGON_POINT -3.8840 40.5215 -3.8840 40.5215",
        "POLYGON_POINT -3.8840 40.5213 -3.8840 40.5213",
        "END_WINDING", "END_POLYGON", ""])
    p = tmp_path / "t.dsf.text"
    p.write_text(text)
    d = S.read_dump(str(p))
    uv, bez = d.polygons[0], d.polygons[1]
    lons = [pt[0] for pt in uv.windings[0]]; lats = [pt[1] for pt in uv.windings[0]]
    assert len(uv.windings[0]) == 4
    assert max(lons) - min(lons) < 0.001 and max(lats) - min(lats) < 0.001
    assert len(bez.windings[0]) > 3                    # the bezier polygon still flattens
    blons = [pt[0] for pt in bez.windings[0]]
    assert max(blons) - min(blons) < 0.01


def test_find_text_dump_never_crosses_the_live_and_pristine_names(tmp_path):
    """RULINGS 2026-09-11m: ``+40-004.dsf`` and ``+40-004.dsf.anchor_bak``
    BOTH start ``+40-004.dsf.`` in the cache, and the write makes the live
    file's dump the NEWEST — so the old tile-wide freshness fallback could
    serve the WRITTEN dump for a plan read of the PRISTINE file (LEMD:
    3,934 placements against a 3,021-row frame).  The candidate set is the
    dumps named for the file asked about."""
    import time
    pack = tmp_path / "xp" / "Custom Scenery" / "LEMD Pack"
    dsf = pack / "Earth nav data" / "+40-010" / "+40-004.dsf"
    dsf.parent.mkdir(parents=True)
    bak = dsf.parent / "+40-004.dsf.anchor_bak"
    root = tmp_path / "mod_cache"
    d = root / "LEMD Pack"
    d.mkdir(parents=True)

    t0 = time.time() - 3600
    bak.write_bytes(b"XPLNEDSF pristine")
    os.utime(bak, (t0, t0))
    pristine_dump = d / f"+40-004.dsf.anchor_bak.{S.text_dump_tag(str(bak))}.text"
    pristine_dump.write_text("OBJECT_DEF objects/a.obj\n")
    os.utime(pristine_dump, (t0 + 60, t0 + 60))

    dsf.write_bytes(b"XPLNEDSF written with 913 body placements")
    os.utime(dsf, (t0 + 600, t0 + 600))
    written_dump = d / f"+40-004.dsf.{S.text_dump_tag(str(dsf))}.text"
    written_dump.write_text("OBJECT_DEF objects/a__b0.obj\n")   # the NEWEST
    os.utime(written_dump, (t0 + 700, t0 + 700))

    # the pristine frame gets the pristine dump, never the newer one
    assert S.find_text_dump(str(root), "LEMD Pack", 40, -4,
                            dsf_path=str(bak)) == str(pristine_dump)
    # and a live-file lookup never gets the backup's dump
    assert S.find_text_dump(str(root), "LEMD Pack", 40, -4,
                            dsf_path=str(dsf)) == str(written_dump)
    written_dump.unlink()
    assert S.find_text_dump(str(root), "LEMD Pack", 40, -4,
                            dsf_path=str(dsf)) is None


# ── §44 THE PAVEMENT BORROW (owner RULINGS 2026-09-15f) ──────────────────
#
# A custom pack whose apt.dat row-110 union covers less than
# ``structures.load.pavement_borrow_coverage_max`` of the Global Airports
# block's borrows Global's pavement, and its row-130 boundary when the pack
# authored none — FlyTampa LGAV: two runway strips, 1.3 % of Global's 63,
# graded with ZERO taxiways and ZERO aprons before §44.

import dataclasses as _dcx

from auto_patch_v2.airport import borrow as B

_BORROW_ICAO = "ZZQQ"
#: the fixture's frame origin, and the corner every square is placed from
_LA, _LO = 37.90, 23.90


def _sq(la: float, lo: float, d: float) -> str:
    """One row-110 square of side ``d`` degrees with its corner at
    ``(la, lo)`` — four node rows, the last closing the contour."""
    return ("110 1 0.25 0 pav\n"
            f"111 {la:.6f} {lo:.6f}\n"
            f"111 {la:.6f} {lo + d:.6f}\n"
            f"111 {la + d:.6f} {lo + d:.6f}\n"
            f"113 {la + d:.6f} {lo:.6f}\n")


def _bnd(la: float, lo: float, d: float) -> str:
    return ("130 boundary\n"
            f"111 {la:.6f} {lo:.6f}\n"
            f"111 {la:.6f} {lo + d:.6f}\n"
            f"111 {la + d:.6f} {lo + d:.6f}\n"
            f"113 {la + d:.6f} {lo:.6f}\n")


def _apt_file(path: Path, body: str) -> None:
    """One airport block for ``_BORROW_ICAO`` with a single runway (the
    frame's reference point) and ``body``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rw = (f"100 45.00 1 0 0.25 0 0 0 09 {_LA:.6f} {_LO:.6f} 0 0 3 0 0 0 "
          f"27 {_LA + 0.01:.6f} {_LO + 0.01:.6f} 0 0 3 0 0 0\n")
    path.write_text("I\n1100 Generated\n"
                    f"1 100 0 0 {_BORROW_ICAO} Borrow Fixture\n"
                    + rw + body + "99\n")


def _borrow_root(tmp_path: Path, custom_body: str,
                 global_body: str | None) -> Path:
    root = tmp_path / "XP"
    _apt_file(root / "Custom Scenery" / "AAA Pack" / "Earth nav data" / "apt.dat",
              custom_body)
    if global_body is not None:
        _apt_file(root / "Global Scenery" / "Global Airports" / "Earth nav data"
                  / "apt.dat", global_body)
    return root


def _borrow_law(coverage_max: float | None = None):
    law = Law.for_airport(_BORROW_ICAO)
    if coverage_max is None:
        return law
    t = law.tables
    st = _dcx.replace(t.structures, load=_dcx.replace(
        t.structures.load, pavement_borrow_coverage_max=coverage_max))
    return _dcx.replace(law, tables=_dcx.replace(t, structures=st))


def _borrow_inputs(root: Path) -> Inputs:
    return Inputs(xplane_root=str(root), cifp_dir="", osm_root="",
                  elevation_root="", mod_cache_root="")


#: TWO runway strips, 1.3 % of Global's — the LGAV shape
_CUSTOM_THIN = _sq(_LA, _LO, 0.0005) + _sq(_LA + 0.002, _LO, 0.0005)
#: FOUR Global squares, an order of magnitude bigger
_GLOBAL_FOUR = "".join(_sq(_LA + 0.004 * k, _LO, 0.004) for k in range(4)) \
    + _bnd(_LA - 0.001, _LO - 0.001, 0.02)


def test_borrow_fires_under_the_coverage_key(tmp_path):
    """(a) coverage < 25 %: pavement + boundary borrowed, the pack kept."""
    root = _borrow_root(tmp_path, _CUSTOM_THIN, _GLOBAL_FOUR)
    law = _borrow_law()
    sel = P.select_pack(str(root), _BORROW_ICAO, law)
    assert sel is not None and sel.name == "AAA Pack" and sel.custom
    assert sel.borrow_reason == "coverage"
    assert sel.borrowed_apt_dat_path.endswith("Global Airports/Earth nav data/apt.dat")
    assert 0.0 <= sel.borrow.coverage < 0.25

    a, rep = load_with_report(_BORROW_ICAO, _borrow_inputs(root), law)
    ps = rep.pavement_source
    assert ps["pack"] == "AAA Pack"
    assert ps["borrowed_from"] == sel.borrowed_apt_dat_path
    assert (ps["custom_pavements"], ps["borrowed_pavements"]) == (2, 4)
    assert ps["borrowed_boundary"] is True and ps["coverage"] < 0.25
    # borrowing ADDS, never removes: the pack's own two strips stand
    apt_pav = [p for p in a.pavements if p.id.startswith("pav")]
    assert len(apt_pav) == 6
    assert [p.source for p in apt_pav] == [""] * 2 + ["global_airports"] * 4
    assert [p.id for p in apt_pav] == [f"pav{i}" for i in range(6)]
    assert len(a.boundaries) == 1 and a.boundaries[0].source == "global_airports"
    # the taxi network, runways and the pack root stay the CUSTOM pack's
    assert len(a.runways) == 1 and sel.root.endswith("AAA Pack")
    # §44 (4): the signature and the partition key carry the borrowed sha
    assert a.pack.borrowed_apt_dat_path == sel.borrowed_apt_dat_path
    assert len(a.pack.borrowed_block_sha256) == 64
    assert rep.pavement_borrow_line.startswith(
        f"{_BORROW_ICAO}: the pack's apt.dat carries 2 pavement(s) covering ")
    assert "pavement + boundary BORROWED from" in rep.pavement_borrow_line


def test_borrow_sha_is_in_the_partition_key(tmp_path):
    """§44 (4) C5: a Global Airports update invalidates the cache."""
    from auto_patch_v2.airport import partition_cache as PC
    root = _borrow_root(tmp_path, _CUSTOM_THIN, _GLOBAL_FOUR)
    a, _ = load_with_report(_BORROW_ICAO, _borrow_inputs(root), _borrow_law())
    dump = tmp_path / "dump.text"
    dump.write_text("OBJECT_DEF objects/a.obj\n")
    (Path(a.pack.apt_dat_path).parent.parent / "x.obj").write_text("A\n800\nOBJ\n")
    law = _borrow_law()
    fp = PC.fingerprint(a, law, dump_path=str(dump), radius_deg=0.05)
    other = _dcx.replace(a.pack, borrowed_block_sha256="0" * 64)
    fp2 = PC.fingerprint(_dcx.replace(a, pack=other), law,
                         dump_path=str(dump), radius_deg=0.05)
    assert fp and fp2 and fp != fp2


def test_borrow_holds_at_or_above_the_coverage_key(tmp_path):
    """(b) coverage >= 25 %: nothing borrowed, the pack's pavement stands."""
    body = "".join(_sq(_LA + 0.004 * k, _LO, 0.004) for k in range(2))
    root = _borrow_root(tmp_path, body, _GLOBAL_FOUR)
    law = _borrow_law()
    sel = P.select_pack(str(root), _BORROW_ICAO, law)
    assert sel is not None and sel.borrowed_apt_dat_path == ""
    assert sel.borrow.coverage >= 0.25
    a, rep = load_with_report(_BORROW_ICAO, _borrow_inputs(root), law)
    assert len([p for p in a.pavements if p.id.startswith("pav")]) == 2
    assert rep.pavement_source["borrowed_from"] is None
    assert rep.pavement_source["borrowed_pavements"] == 0
    assert rep.pavement_borrow_line == ""
    assert a.boundaries == () and a.pack.borrowed_block_sha256 == ""


def test_borrow_without_a_global_block(tmp_path):
    """(c) no Global Airports file: nothing borrowed, no exception."""
    root = _borrow_root(tmp_path, _CUSTOM_THIN, None)
    law = _borrow_law()
    sel = P.select_pack(str(root), _BORROW_ICAO, law)
    assert sel is not None and sel.borrowed_apt_dat_path == ""
    assert sel.borrow_reason == "no Global Airports block"
    a, rep = load_with_report(_BORROW_ICAO, _borrow_inputs(root), law)
    assert len(a.pavements) == 2 and rep.pavement_source["borrowed_from"] is None


def test_borrow_keeps_the_packs_own_boundary(tmp_path):
    """(d) the pack authored a row-130: the boundary is NOT borrowed."""
    root = _borrow_root(tmp_path, _CUSTOM_THIN + _bnd(_LA, _LO, 0.001),
                        _GLOBAL_FOUR)
    law = _borrow_law()
    a, rep = load_with_report(_BORROW_ICAO, _borrow_inputs(root), law)
    assert rep.pavement_source["borrowed_pavements"] == 4
    assert rep.pavement_source["borrowed_boundary"] is False
    assert len(a.boundaries) == 1 and a.boundaries[0].source == ""
    assert "pavement BORROWED from" in rep.pavement_borrow_line


def test_borrow_key_at_zero_never_borrows(tmp_path):
    """(e) the key at 0 is the borrow switched OFF."""
    root = _borrow_root(tmp_path, _CUSTOM_THIN, _GLOBAL_FOUR)
    law = _borrow_law(0.0)
    sel = P.select_pack(str(root), _BORROW_ICAO, law)
    assert sel is not None and sel.borrowed_apt_dat_path == ""
    a, _ = load_with_report(_BORROW_ICAO, _borrow_inputs(root), law)
    assert len(a.pavements) == 2


def test_borrow_key_is_a_coverage_fraction():
    """The key is law, validated 0 <= x <= 1 (§44 (2))."""
    from auto_patch_v2.law import model as LM
    law = _borrow_law()
    assert law.tables.structures.load.pavement_borrow_coverage_max == 0.25
    with pytest.raises(LM.LawError):
        LM._check_cross_refs(_borrow_law(1.5).tables)


def test_pavement_less_custom_pack_is_still_the_pack(tmp_path):
    """§44 (1): the 'last resort' tail is DELETED — a custom pack with NO
    row-110 wins the selection (and borrows everything)."""
    root = _borrow_root(tmp_path, "", _GLOBAL_FOUR)
    law = _borrow_law()
    assert A.find_apt_dat(str(root), _BORROW_ICAO) == str(
        root / "Custom Scenery" / "AAA Pack" / "Earth nav data" / "apt.dat")
    a, rep = load_with_report(_BORROW_ICAO, _borrow_inputs(root), law)
    assert rep.pack_name == "AAA Pack"
    assert rep.pavement_source["coverage"] == 0.0
    assert rep.pavement_source["custom_pavements"] == 0
    assert len([p for p in a.pavements if p.id.startswith("pav")]) == 4
