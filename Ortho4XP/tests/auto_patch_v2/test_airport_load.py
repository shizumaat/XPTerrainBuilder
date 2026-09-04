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
