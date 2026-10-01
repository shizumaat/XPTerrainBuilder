"""Tests for the approach-graded elevation rings.

Covers ``src/O4_Elevation_Level.py``'s ring half
(``docs/specs/approach-graded-elevation-rings-spec.md``; owner RULINGS
2026-10-01g/h): the ONE grading function behind both approach ladders,
the feather-is-postings-of-the-coarser-side rule, the plan (its airport
admission, the exact ring unions measured from the aerodrome BOUNDARY,
the cell grading, the collapse rule, the ``elevation_level``
precedence), the per-class layer bake with its region mask, the cold
predicate, and the ``rings`` refresh scope.

All headless and corpus-free: synthetic rasters and synthetic boundary
polygons in ``tmp_path``, the provider registry mocked, no network (the
suite's socket guard would fail any test that reached one) and no
shared data repo.  The bake tests require the GDAL python bindings and
skip cleanly without them.
"""

from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace

import numpy
import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
)
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)),
                    "tools", "harness")
)

import O4_Elevation_Level as ELEVATION_LEVEL
import O4_File_Names as FNAMES

try:
    from osgeo import gdal

    HAS_GDAL = True
except Exception:
    HAS_GDAL = False

NODATA = -32768.0


# ═════════════════════════════════════════════════════════════════════
# THE ONE GRADING FUNCTION (spec §3.1, consumer census row 5)
# ═════════════════════════════════════════════════════════════════════
def _ring_class_m(index):
    return ELEVATION_LEVEL.approach_rung_resolution_m(
        ELEVATION_LEVEL.APPROACH_RING_LADDER[index - 1][1])


@pytest.mark.parametrize("distance_m,expected_ring", [
    (0.0, 1),
    (1.0, 1),
    (9_999.0, 1),
    (10_000.0, 1),          # the reach is INCLUSIVE, as the band's was
    (10_000.1, 2),
    (19_999.0, 2),
    (20_000.0, 2),
    (20_000.1, None),       # beyond the ladder: the base DEM stands
    (float("inf"), None),
])
def test_approach_class_ring_ladder(distance_m, expected_ring):
    resolution_m, ring = ELEVATION_LEVEL.approach_class(
        distance_m, ELEVATION_LEVEL.APPROACH_RING_LADDER)
    assert ring == expected_ring
    if expected_ring is None:
        assert resolution_m is None
    else:
        assert resolution_m == _ring_class_m(expected_ring)


def test_ring_ladder_is_the_owner_s_radii():
    # Owner RULINGS 2026-10-01g, CONFIRMED: 10 km and 20 km, measured
    # from the aerodrome boundary.  A ladder edit shows up here.
    assert [reach for reach, _r in ELEVATION_LEVEL.APPROACH_RING_LADDER] \
        == [10_000.0, 20_000.0]
    assert _ring_class_m(1) == round(
        ELEVATION_LEVEL.grid_posting_metres(3), 2)      # 1/3 arc-second
    assert _ring_class_m(2) == round(
        ELEVATION_LEVEL.grid_posting_metres(1), 2)      # 1 arc-second


def test_coastline_ladder_values_are_unchanged():
    """The band's table read through the SHARED function must produce
    exactly the three resolutions its own literals produced (spec
    question Q2: keep both tables, one function, until a coastline-mode
    sim read).  This is the twin that would catch a Q2 answer landing
    by accident."""
    ladder = ELEVATION_LEVEL.COASTLINE_APPROACH_LADDER
    near = ELEVATION_LEVEL.approach_class(0.0, ladder)
    mid = ELEVATION_LEVEL.approach_class(
        ELEVATION_LEVEL.COASTLINE_NEAR_AIRPORT_KM * 1000.0 + 1.0, ladder)
    far = ELEVATION_LEVEL.approach_class(
        ELEVATION_LEVEL.COASTLINE_MID_AIRPORT_KM * 1000.0 + 1.0, ladder)
    assert near == (round(ELEVATION_LEVEL.grid_posting_metres(3), 2), 1)
    assert mid == (float(ELEVATION_LEVEL.COASTLINE_MID_RESOLUTION_M), 2)
    assert far == (round(ELEVATION_LEVEL.grid_posting_metres(1), 2), 3)
    # A tile with NO airport grades every cell "far" -- the band's own
    # behaviour, which only an infinite last reach preserves.
    assert ELEVATION_LEVEL.approach_class(float("inf"), ladder) == far


def test_coastline_and_ring_ladders_are_separate_tables():
    assert ELEVATION_LEVEL.COASTLINE_APPROACH_LADDER \
        != ELEVATION_LEVEL.APPROACH_RING_LADDER


@pytest.mark.parametrize("rung,expected", [
    (3, round(ELEVATION_LEVEL.grid_posting_metres(3), 2)),
    (1, round(ELEVATION_LEVEL.grid_posting_metres(1), 2)),
    (20.0, 20.0),
])
def test_rung_resolution_reads_factors_and_metres(rung, expected):
    assert ELEVATION_LEVEL.approach_rung_resolution_m(rung) == expected


def test_rung_resolution_rejects_a_bool():
    # ``True`` is an int in Python, and a bool rung would silently read
    # as the 1 arc-second factor.
    with pytest.raises(TypeError):
        ELEVATION_LEVEL.approach_rung_resolution_m(True)


# ═════════════════════════════════════════════════════════════════════
# THE FEATHER RULE (spec §1: postings of the COARSER side)
# ═════════════════════════════════════════════════════════════════════
def test_feathers_are_the_ruled_300_m_and_900_m():
    assert ELEVATION_LEVEL._approach_ring_layer_feather_m(1) == 300.0
    assert ELEVATION_LEVEL._approach_ring_layer_feather_m(2) == 900.0


def test_feather_is_ten_postings_of_the_coarser_side():
    assert ELEVATION_LEVEL.APPROACH_RING_FEATHER_POSTINGS == 10
    for coarser_m in (10.0, 20.0, 31.0, 92.0):
        feather_m = ELEVATION_LEVEL.approach_ring_feather_m(coarser_m)
        raw_m = ELEVATION_LEVEL.APPROACH_RING_FEATHER_POSTINGS * coarser_m
        assert abs(feather_m - raw_m) <= \
            ELEVATION_RING_ROUNDING / 2.0 + 1e-9


ELEVATION_RING_ROUNDING = ELEVATION_LEVEL.APPROACH_RING_FEATHER_ROUNDING_M


def test_feather_below_one_rounding_step_is_kept():
    # A 1 m coarser side gives 10 m, which must not round to zero.
    assert ELEVATION_LEVEL.approach_ring_feather_m(1.0) == 10.0


def test_transition_grades_are_under_the_bank_and_the_taxi_cap():
    """Spec §8 (3) in closed form: the MEASURED worst steps (fact 2 --
    9.32 m across the 10 m/30 m seam, 33.2 m across 30 m/base) over the
    ruled feathers must stay far under ``emit.design.bank_slope`` and
    the p95 under ``ruleset.taxi.transverse``.  No law literal is used:
    both come from the shipped tables."""
    bank_slope, taxi_transverse = _law_bank_and_taxi()
    ring1_grade = 9.32 / ELEVATION_LEVEL._approach_ring_layer_feather_m(1)
    ring2_grade = 33.2 / ELEVATION_LEVEL._approach_ring_layer_feather_m(2)
    assert ring1_grade < bank_slope
    assert ring2_grade < bank_slope
    # And the p95 figures the spec quotes (1.68 m / 7.46 m).
    assert 1.68 / ELEVATION_LEVEL._approach_ring_layer_feather_m(1) \
        < taxi_transverse
    assert 7.46 / ELEVATION_LEVEL._approach_ring_layer_feather_m(2) \
        < taxi_transverse


def _law_bank_and_taxi():
    """``emit.design.bank_slope`` and ``ruleset.taxi.transverse`` READ
    FROM THE SHIPPED LAW TABLES, never copied: this test asserts a
    relation between the ring feathers and the law, so a law edit must
    reach it (CLAUDE.md: named constants, no law literals)."""
    import tomllib

    law_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "src", "auto_patch_v2", "law")
    with open(os.path.join(law_dir, "emit.toml"), "rb") as handle:
        bank = tomllib.load(handle)["design"]["bank_slope"]
    with open(os.path.join(law_dir, "rulesets.toml"), "rb") as handle:
        rulesets = tomllib.load(handle)
    # The STRICTEST taxiway transverse cap across every ruleset and
    # letter: the target the spec quotes the p95 against.
    caps = []
    for ruleset in rulesets.values():
        taxi_table = ((ruleset.get("taxi") or {}).get("transverse")
                      if isinstance(ruleset, dict) else None)
        if not isinstance(taxi_table, dict):
            continue
        caps.extend(
            float(value)
            for value in (taxi_table.get("by_letter") or {}).values())
        if "default" in taxi_table:
            caps.append(float(taxi_table["default"]))
    assert caps, "no taxiway transverse cap found in rulesets.toml"
    taxi = min(caps)
    return float(bank), taxi


# ═════════════════════════════════════════════════════════════════════
# THE CONFIGURATION GATE (spec §7: ONE key, auto|off)
# ═════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("value,enabled", [
    ("auto", True), ("AUTO", True), (" auto ", True), ("", True),
    (None, True), ("garbage", True),       # a typo degrades to ON
    ("off", False), ("OFF", False), (" off ", False),
])
def test_approach_rings_enabled(value, enabled):
    tile = SimpleNamespace(approach_rings=value)
    assert ELEVATION_LEVEL.approach_rings_enabled(tile) is enabled


def test_approach_rings_key_is_registered_with_its_hint():
    import O4_Cfg_Vars as CFG_VARS

    row = CFG_VARS.cfg_vars["approach_rings"]
    assert row["default"] == "auto"
    assert row["values"] == ("auto", "off")
    assert row["hint"].strip()
    assert "approach_rings" in CFG_VARS.list_cfg_vars


def test_approach_rings_is_a_dem_frame_key():
    # A divergence between a lane cfg and the owner's app cfg must make
    # the harness refuse: the rings shape the surface the build grades.
    from build_airport import DEM_FRAME_KEYS

    assert "approach_rings" in DEM_FRAME_KEYS


# ═════════════════════════════════════════════════════════════════════
# THE REFRESH SCOPE (spec §5, consumer census row 16)
# ═════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("relpath,scope", [
    ("Elevation_data/+30-110/N39W107_approach_rings/"
     "cell_03_07_usgs3dep_10.31m.tif", "rings"),
    ("Elevation_data/+30-110/N39W107_approach_rings/index.json", "rings"),
    # A DEM refresh must NOT warm a ring, and a ring refresh writes
    # nothing else: the two neighbouring artefact classes keep their own
    # scopes although they share the ``Elevation_data`` prefix.
    ("Elevation_data/+30-110/N39W107_airport_insets/KASE_usgs3dep.tif",
     "dem"),
    ("Elevation_data/+30-110/N39W107.hgt", "dem"),
    ("Elevation_data/+30-110/N39W107_coastline_band/"
     "cell_03_07_usgs3dep_10.31m.tif", "dem"),
    ("Elevation_data/_las_tiles/x.laz", "las_tiles"),
])
def test_scope_of_names_the_rings_scope(relpath, scope):
    from shared_repo_guard import scope_of

    assert scope_of(relpath) == scope


def test_rings_scope_is_known_and_described():
    from shared_repo_guard import REFRESH_SCOPES, scope_description

    assert "rings" in {name for name, _p, _w in REFRESH_SCOPES}
    assert "ring" in scope_description("rings").lower()


def test_rings_scope_is_listed_before_dem():
    # ``scope_of`` takes the first matching prefix, so the order is law.
    from shared_repo_guard import REFRESH_SCOPES

    names = [name for name, _p, _w in REFRESH_SCOPES]
    assert names.index("rings") < names.index("dem")


# ═════════════════════════════════════════════════════════════════════
# THE SYNTHETIC 3-RING FIXTURE (spec §8 (4) and §10 step 1)
# ═════════════════════════════════════════════════════════════════════
LAT, LON = 39, -107

#: Mock registry: a 1 m lidar service, a 10 m one, a 30 m one, and a
#: 30 m SURFACE model that opts OUT of wide-area use (the question-Q1
#: shape).  Each carries a coverage box so a cell can be asked its own
#: coverage question.
def _definition(code, resolution_m, box, *, wide_area=True,
                ring_class=None):
    definition = {"code": code, "enabled": True,
                  "_resolution_m": resolution_m, "_box": box}
    if not wide_area:
        definition["supports_wide_area"] = "false"
    if ring_class is not None:
        definition[ELEVATION_LEVEL.APPROACH_RING_OPT_IN_KEY] = ring_class
    return definition


def _mock_registry(monkeypatch, definitions):
    """Point the ring plan's provider selection at a FAKE registry.

    The real ranking, the real coverage test and the real native-
    resolution admission all run; only the registry's contents and the
    two tiny accessors the admission uses are mocked, so a change to
    the admission rules reaches this twin.
    """
    import O4_Airport_Elevation_Insets as INSETS

    monkeypatch.setattr(
        INSETS, "elevation_providers_dict",
        {d["code"]: d for d in definitions}, raising=False)
    monkeypatch.setattr(
        INSETS, "initialize_elevation_providers_dict",
        lambda: {d["code"]: d for d in definitions}, raising=False)
    monkeypatch.setattr(
        INSETS, "_definition_resolution_m",
        lambda d: d.get("_resolution_m"), raising=False)
    monkeypatch.setattr(
        INSETS, "_coverage_bbox_intersects",
        lambda d, box: _boxes_overlap(d["_box"], box), raising=False)

    class _Strategy:
        supports_wide_area = True

    monkeypatch.setattr(
        INSETS, "ACCESS_STRATEGIES",
        {None: _Strategy, "mock": _Strategy}, raising=False)


def _boxes_overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _square(centre_lon, centre_lat, half_degrees):
    from shapely.geometry import box as _box

    return _box(centre_lon - half_degrees, centre_lat - half_degrees,
                centre_lon + half_degrees, centre_lat + half_degrees)


def _ring_tile(tmp_path, **overrides):
    """A tile stub whose data roots are LANE-LOCAL (``tmp_path``): the
    plan writes and reads nothing in any shared corpus."""
    tile = SimpleNamespace(
        lat=LAT, lon=LON,
        approach_rings="auto",
        elevation_level="auto",
        custom_dem="",
        airport_elevation_providers="auto",
        airport_elevation_insets="All",
        airport_elevation_inset_feather_m=60.0,
        dem=None,
    )
    for key, value in overrides.items():
        setattr(tile, key, value)
    return tile


@pytest.fixture
def ring_corpus(tmp_path, monkeypatch):
    """Re-point every elevation path at ``tmp_path`` for the duration.

    The suite's shared-repo write guard refuses a write to the real data
    repo; these tests do not need one at all, so they never see it.
    """
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "Elevation"),
                        raising=False)
    monkeypatch.setattr(FNAMES, "Tmp_dir", str(tmp_path / "tmp"),
                        raising=False)
    (tmp_path / "Elevation").mkdir(parents=True, exist_ok=True)
    (tmp_path / "tmp").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _plan_for(tile, boundaries, monkeypatch, *, insets_on_disk=None,
              neighbours=None, neighbours_unknown=()):
    """Derive a plan over SYNTHETIC boundary polygons.

    ``boundaries`` is ``{icao: shapely polygon}`` in absolute degrees.
    The admission's two disk reads (the inset cache and the neighbour
    layers) are the only things stubbed; the geometry, the grading, the
    collapse rule and the provider choice are the real code.
    """
    import O4_Airport_Elevation_Insets as INSETS

    on_disk = set(boundaries) if insets_on_disk is None \
        else set(insets_on_disk)
    monkeypatch.setattr(
        INSETS, "cached_inset_paths_for_icao",
        lambda lat, lon, icao, providers_config="auto":
            ([f"{icao}.tif"] if icao in on_disk else []), raising=False)
    monkeypatch.setattr(
        INSETS, "airport_boundary_polygons",
        lambda tile_, dico, only=None: {
            icao: geometry for icao, geometry in boundaries.items()
            if only is None or icao in set(only)}, raising=False)
    monkeypatch.setattr(
        ELEVATION_LEVEL, "_approach_ring_neighbour_polygons",
        lambda tile_, reach_m: (dict(neighbours or {}),
                                [list(c) for c in neighbours_unknown]))
    dico = {icao: {"boundary": None} for icao in boundaries}
    return ELEVATION_LEVEL.resolve_approach_ring_plan(tile, dico)


# --- the plan: cells, classes, regions -------------------------------
def test_plan_grades_cells_by_boundary_distance(ring_corpus, monkeypatch):
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus)
    # A small aerodrome boundary in the middle of the tile.
    plan = _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch)
    assert plan is not None
    classes = {cell["class_m"] for cell in plan["cells"]}
    assert classes == {_ring_class_m(1), _ring_class_m(2)}
    # The ring-1 cells are the ones the 10 km union touches, and they are
    # a STRICT SUBSET of the ring-2 cells' footprint: a 10 km and a 20 km
    # buffer of the same boundary cannot cover the same cell set.
    ring1 = {(c["column"], c["row"]) for c in plan["cells"]
             if c["class_m"] == _ring_class_m(1)}
    ring2 = {(c["column"], c["row"]) for c in plan["cells"]
             if c["class_m"] == _ring_class_m(2)}
    assert ring1 and ring2
    assert not (ring1 & ring2)          # each cell is planned ONCE
    # Measured from the BOUNDARY, so the plan never covers the whole
    # tile for one small aerodrome.
    assert len(plan["cells"]) < 100


def test_plan_is_measured_from_the_boundary_not_the_centroid(
        ring_corpus, monkeypatch):
    """A LONG boundary reaches further than a point at its centroid --
    the ruling's "from the AERODROME BOUNDARY, NOT the ARP, NOT the
    box"."""
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    from shapely.geometry import box as _box

    tile = _ring_tile(ring_corpus)
    point_like = _plan_for(
        tile, {"A": _square(LON + 0.5, LAT + 0.5, 0.002)}, monkeypatch)
    # A 0.3 degree runway strip through the same centroid.
    elongated = _plan_for(
        tile, {"A": _box(LON + 0.35, LAT + 0.498,
                         LON + 0.65, LAT + 0.502)}, monkeypatch)
    assert len(elongated["cells"]) > len(point_like["cells"])


def test_two_overlapping_airports_bake_one_union(ring_corpus, monkeypatch):
    """Spec §3 reason 1: per-airport rasters baked one after the other
    would feather airport A's ring-2 OUTER edge INSIDE airport B's
    ring 1.  The union is by construction, so each cell is planned once
    and a cell near BOTH boundaries carries the FINEST class."""
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus)
    plan = _plan_for(tile, {
        "A": _square(LON + 0.40, LAT + 0.50, 0.005),
        "B": _square(LON + 0.60, LAT + 0.50, 0.005),
    }, monkeypatch)
    keys = [(c["column"], c["row"]) for c in plan["cells"]]
    assert len(keys) == len(set(keys))          # ONE record per cell
    # Both airports' ring-1 unions are in ONE region, so the layer for
    # the finest class is baked once, over both.
    layers = {layer["class_m"]: layer for layer in plan["layers"]}
    assert set(layers) == {_ring_class_m(1), _ring_class_m(2)}
    # Coarsest FIRST -- the bake order that makes the finest class win.
    assert [layer["class_m"] for layer in plan["layers"]] == \
        sorted(layers, reverse=True)
    # The cell exactly between them is ring 1 for both: one record.
    single = _plan_for(tile, {"A": _square(LON + 0.40, LAT + 0.50, 0.005)},
                       monkeypatch)
    pair_ring1 = {(c["column"], c["row"]) for c in plan["cells"]
                  if c["class_m"] == _ring_class_m(1)}
    solo_ring1 = {(c["column"], c["row"]) for c in single["cells"]
                  if c["class_m"] == _ring_class_m(1)}
    assert solo_ring1 < pair_ring1


def test_plan_is_none_without_an_inset_holder(ring_corpus, monkeypatch):
    # Spec §1: a ring exists ONLY around an airport that HOLDS AN INSET.
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus)
    assert _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch, insets_on_disk=[]) is None


@pytest.mark.parametrize("key", ["off", "OFF"])
def test_plan_is_none_when_the_key_is_off(ring_corpus, monkeypatch, key):
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus, approach_rings=key)
    assert _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch) is None


def test_plan_is_none_with_custom_dem(ring_corpus, monkeypatch):
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus, custom_dem="/some/raster.tif")
    assert _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch) is None


def test_plan_is_none_without_gdal(ring_corpus, monkeypatch):
    monkeypatch.setattr(ELEVATION_LEVEL, "has_gdal", False)
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus)
    assert _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch) is None


# --- the collapse rule and the sources (spec §2) ---------------------
def test_ring_one_collapses_into_ring_two_without_a_fine_provider(
        ring_corpus, monkeypatch):
    _mock_registry(monkeypatch, [
        _definition("THIRTYM", 30.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus)
    plan = _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch)
    assert plan is not None
    assert {cell["class_m"] for cell in plan["cells"]} == {_ring_class_m(2)}
    collapsed = [cell for cell in plan["cells"] if cell["collapsed"]]
    assert collapsed, "the ring-1 cells must be recorded as COLLAPSED"
    assert all(cell["provider"] == "THIRTYM" for cell in plan["cells"])


def test_no_wide_area_provider_at_all_is_no_plan(ring_corpus, monkeypatch):
    _mock_registry(monkeypatch, [
        _definition("ELSEWHERE", 1.0, (LON + 50, LAT, LON + 51, LAT + 1)),
    ])
    tile = _ring_tile(ring_corpus)
    assert _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch) is None


def test_ring_two_prefers_the_ring_one_product(ring_corpus, monkeypatch):
    """Spec §2: one product, one datum, one vintage across the
    10 m -> 30 m seam, so the measured step is pure resolution."""
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
        _definition("THIRTYM", 30.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus)
    plan = _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch)
    assert {cell["provider"] for cell in plan["cells"]} == {"TENM"}


def test_a_sub_metre_service_is_read_at_the_ring_class(
        ring_corpus, monkeypatch):
    # The band's rule: a lidar service is read at the ring's posting,
    # never at native -- the cache stem carries the ring class.
    _mock_registry(monkeypatch, [
        _definition("ONEM", 1.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus)
    plan = _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch)
    for cell in plan["cells"]:
        assert cell["class_m"] in (_ring_class_m(1), _ring_class_m(2))
        assert str(cell["class_m"]).rstrip("0").rstrip(".") in cell["stem"]


def test_a_surface_model_serves_ring_two_only_by_opt_in(
        ring_corpus, monkeypatch):
    """Spec question Q1's door: a 30 m SURFACE model that opts out of
    tile-wide use may be named for ring 2 by declaring
    ``approach_ring_class``, and NEVER for ring 1.  No shipped
    definition declares it, so flipping one on is a later, measured
    act -- this test is the door's twin, not its use."""
    _mock_registry(monkeypatch, [
        _definition("GLO30", 30.0, (LON - 1, LAT - 1, LON + 2, LAT + 2),
                    wide_area=False, ring_class=30),
    ])
    tile = _ring_tile(ring_corpus)
    plan = _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch)
    assert plan is not None
    # Everything collapses to the ring-2 class: it may never serve ring 1.
    assert {cell["class_m"] for cell in plan["cells"]} == {_ring_class_m(2)}
    assert {cell["provider"] for cell in plan["cells"]} == {"GLO30"}


def test_a_surface_model_without_the_opt_in_is_barred(
        ring_corpus, monkeypatch):
    _mock_registry(monkeypatch, [
        _definition("GLO30", 30.0, (LON - 1, LAT - 1, LON + 2, LAT + 2),
                    wide_area=False),
    ])
    tile = _ring_tile(ring_corpus)
    assert _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch) is None


def test_no_shipped_definition_opts_into_a_ring_class():
    """STOP list item 8: Copernicus GLO-30 must not become a ring source
    without the owner's answer to Q1.  This asserts the SHIPPED registry
    carries no opt-in at all."""
    import O4_Airport_Elevation_Insets as INSETS

    registry = INSETS.initialize_elevation_providers_dict()
    opted_in = [code for code, definition in registry.items()
                if definition.get(ELEVATION_LEVEL.APPROACH_RING_OPT_IN_KEY)]
    assert opted_in == []


# --- neighbour-tile airports (spec §3.1, census row 22) --------------
def test_a_neighbour_tile_airport_is_in_the_plan(ring_corpus, monkeypatch):
    """The coastline band's recorded limit, closed where the data is
    there: an airport just over the border draws its ring INTO this
    tile."""
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 2, LAT - 2, LON + 3, LAT + 3)),
    ])
    tile = _ring_tile(ring_corpus)
    # 0.03 degrees (~2.6 km) the other side of the western border.
    neighbour = {(LAT, LON - 1, "KEGE"): _square(LON - 0.03, LAT + 0.5,
                                                 0.005)}
    with_neighbour = _plan_for(
        tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)}, monkeypatch,
        neighbours=neighbour)
    without = _plan_for(
        tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)}, monkeypatch)
    assert len(with_neighbour["cells"]) > len(without["cells"])
    assert any("KEGE" in entry for entry in with_neighbour["airports"])
    # The neighbour's ring is CLIPPED to this tile: its own tile bakes
    # its own half.
    from shapely import wkt as _wkt

    region = _wkt.loads(with_neighbour["regions"]["R1"])
    assert region.bounds[0] >= LON - 1e-9


def test_an_uncached_neighbour_is_recorded_never_refused(
        ring_corpus, monkeypatch):
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus)
    plan = _plan_for(
        tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)}, monkeypatch,
        neighbours_unknown=[(LAT, LON - 1), (LAT + 1, LON)])
    assert plan is not None                      # never a refusal
    assert plan["neighbours_unknown"] == [[LAT, LON - 1], [LAT + 1, LON]]


def test_the_neighbour_scan_reads_only_cached_layers(ring_corpus,
                                                     monkeypatch):
    """The real scan, with NO cached layer anywhere: every one of the 8
    neighbours is recorded unknown and nothing is loaded (a load would
    need the network, which the suite blocks)."""
    monkeypatch.setattr(FNAMES, "osm_cached",
                        lambda lat, lon, suffix: "/nonexistent.osm.bz2",
                        raising=False)
    tile = _ring_tile(ring_corpus)
    polygons, unknown = ELEVATION_LEVEL._approach_ring_neighbour_polygons(
        tile, ELEVATION_LEVEL.APPROACH_RING_REACH_M)
    assert polygons == {}
    assert len(unknown) == 8


# --- elevation_level precedence (spec §7) ---------------------------
@pytest.mark.parametrize("level,expected_classes", [
    ("auto", {1, 2}),
    ("90", {1, 2}),
    ("coastline", {1, 2}),
    ("30", {1}),            # the 1 arc-second overlay SUPERSEDES ring 2
    ("10", set()),          # a <= 10 m overlay supersedes both
    ("5", set()),
    ("1", set()),
])
def test_level_precedence_is_finest_class_per_cell(
        ring_corpus, monkeypatch, level, expected_classes):
    _mock_registry(monkeypatch, [
        _definition("TENM", 10.0, (LON - 1, LAT - 1, LON + 2, LAT + 2)),
    ])
    tile = _ring_tile(ring_corpus, elevation_level=level)
    plan = _plan_for(tile, {"KASE": _square(LON + 0.5, LAT + 0.5, 0.005)},
                     monkeypatch)
    if not expected_classes:
        assert plan is None
        return
    assert plan is not None
    assert {cell["class_m"] for cell in plan["cells"]} == \
        {_ring_class_m(index) for index in expected_classes}
    assert plan["superseded"] == [
        _ring_class_m(index) for index in (1, 2)
        if index not in expected_classes]


# ═════════════════════════════════════════════════════════════════════
# THE LAYER BAKE (spec §3.2 and §10 step 2)
# ═════════════════════════════════════════════════════════════════════
#: A small window of the tile so the postings are metres, not kilometres:
#: 0.05 degrees over 201 cells is a ~21 m posting, which resolves a
#: 300 m feather in ~14 cells.  Placed mid-tile so the tile-edge ramp
#: (the overlay's own 60 m constant) is at weight 1 everywhere.
BAKE_CELLS = 201
WINDOW_X0, WINDOW_X1 = 0.40, 0.45
WINDOW_Y0, WINDOW_Y1 = 0.40, 0.45

#: The MEASURED 10 m-vs-30 m step at KASE (spec §0 fact 2: max 9.32 m).
STEP_M = 9.3


def _write_layer(path, box, values):
    """Write a north-up EPSG:4326 float32 GeoTIFF over ``box``."""
    rows, columns = values.shape
    west, south, east, north = box
    dataset = gdal.GetDriverByName("GTiff").Create(
        str(path), columns, rows, 1, gdal.GDT_Float32)
    dataset.SetGeoTransform((west, (east - west) / columns, 0.0,
                             north, 0.0, -(north - south) / rows))
    dataset.SetProjection(
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,'
        '298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",'
        '0.0174532925199433],AUTHORITY["EPSG","4326"]]')
    band = dataset.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteArray(values.astype(numpy.float32))
    band.FlushCache()
    dataset = None


def _bake_tile(base_fill=0.0):
    alt = numpy.full((BAKE_CELLS, BAKE_CELLS), base_fill, dtype=numpy.float32)
    dem = SimpleNamespace(
        nxdem=BAKE_CELLS, nydem=BAKE_CELLS,
        x0=WINDOW_X0, x1=WINDOW_X1, y0=WINDOW_Y0, y1=WINDOW_Y1,
        nodata=NODATA, alt_dem=alt)
    return _ring_tile(None, dem=dem)


def _blur_margin(feather_m):
    """How deep the ZERO-PADDED validity blur's dip reaches in from the
    GRID border: one blur radius, i.e. the feather in cells.

    This is the strip bake's long-standing behaviour and is invisible in
    production, where the grid border IS the tile border and the
    tile-edge ramp has already taken the weight to zero there.  The
    synthetic grids here are a mid-tile WINDOW, so the dip is exposed and
    the assertions step past it rather than pretend it is not there.
    """
    return max(int(numpy.ceil(float(feather_m) / _posting_m())), 1) + 1


def _posting_m():
    import O4_Geo_Utils as GEO

    return (WINDOW_Y1 - WINDOW_Y0) / (BAKE_CELLS - 1) * GEO.lat_to_m


def _grid_degrees():
    x = WINDOW_X0 + numpy.arange(BAKE_CELLS) * (
        (WINDOW_X1 - WINDOW_X0) / (BAKE_CELLS - 1))
    y = WINDOW_Y1 - numpy.arange(BAKE_CELLS) * (
        (WINDOW_Y1 - WINDOW_Y0) / (BAKE_CELLS - 1))
    return LON + x, LAT + y


def _disc(centre_lon, centre_lat, radius_m):
    import O4_Airport_Elevation_Insets as INSETS
    from shapely.geometry import Point

    return INSETS._buffer_geometry_m(Point(centre_lon, centre_lat),
                                     radius_m)


@pytest.mark.skipif(not HAS_GDAL, reason="requires the GDAL bindings")
def test_layer_bake_region_is_exact_beyond_the_feather(tmp_path):
    """Spec §10 step 2: values inside the region, beyond the feather,
    equal the layer EXACTLY; outside it the base is untouched."""
    box = (LON + WINDOW_X0 - 0.01, LAT + WINDOW_Y0 - 0.01,
           LON + WINDOW_X1 + 0.01, LAT + WINDOW_Y1 + 0.01)
    layer_path = tmp_path / "fine.tif"
    _write_layer(layer_path, box,
                 numpy.full((400, 400), STEP_M, dtype=numpy.float32))
    tile = _bake_tile()
    centre_lon = LON + (WINDOW_X0 + WINDOW_X1) / 2.0
    centre_lat = LAT + (WINDOW_Y0 + WINDOW_Y1) / 2.0
    feather_m = ELEVATION_LEVEL._approach_ring_layer_feather_m(1)   # 300
    radius_m = 1500.0
    assert ELEVATION_LEVEL.bake_overlay_layer_into_alt_dem(
        tile, str(layer_path), feather_m=feather_m,
        region=_disc(centre_lon, centre_lat, radius_m), label="ring 1")

    grid_x, grid_y = _grid_degrees()
    import O4_Geo_Utils as GEO

    dx = (grid_x - centre_lon) * GEO.lon_to_m(centre_lat)
    dy = (grid_y - centre_lat) * GEO.lat_to_m
    distance_m = numpy.hypot(dx[None, :], dy[:, None])
    baked = tile.dem.alt_dem
    # Deep inside: the layer, exactly.
    deep = distance_m < radius_m - 2.0 * feather_m
    assert deep.any()
    assert numpy.allclose(baked[deep], STEP_M, atol=1e-5)
    # Well outside: the base, untouched.
    outside = distance_m > radius_m + 2.0 * _posting_m()
    assert outside.any()
    assert numpy.allclose(baked[outside], 0.0, atol=1e-6)


@pytest.mark.skipif(not HAS_GDAL, reason="requires the GDAL bindings")
def test_layer_bake_transition_grade_is_under_the_bank(tmp_path):
    """Spec §8 (3) measured on a synthetic seam: a 9.3 m step across the
    ruled 300 m feather must come out an order of magnitude under
    ``emit.design.bank_slope``, and the ramp's AVERAGE grade must be
    the ruled ``step / feather``."""
    bank_slope, _taxi = _law_bank_and_taxi()
    box = (LON + WINDOW_X0 - 0.01, LAT + WINDOW_Y0 - 0.01,
           LON + WINDOW_X1 + 0.01, LAT + WINDOW_Y1 + 0.01)
    layer_path = tmp_path / "fine.tif"
    _write_layer(layer_path, box,
                 numpy.full((400, 400), STEP_M, dtype=numpy.float32))
    tile = _bake_tile()
    centre_lon = LON + (WINDOW_X0 + WINDOW_X1) / 2.0
    centre_lat = LAT + (WINDOW_Y0 + WINDOW_Y1) / 2.0
    feather_m = ELEVATION_LEVEL._approach_ring_layer_feather_m(1)
    ELEVATION_LEVEL.bake_overlay_layer_into_alt_dem(
        tile, str(layer_path), feather_m=feather_m,
        region=_disc(centre_lon, centre_lat, 1500.0), label="ring 1")
    baked = tile.dem.alt_dem
    posting_m = _posting_m()
    worst_grade = max(
        float(numpy.abs(numpy.diff(baked, axis=0)).max()),
        float(numpy.abs(numpy.diff(baked, axis=1)).max()),
    ) / posting_m
    # The whole point of the mechanism: nothing on the transition reads
    # as a bank, let alone the 33 % the 60 m feather produced.
    assert worst_grade < bank_slope
    assert worst_grade < 0.05
    # And the ramp is the ruled width: the step spread over ~feather_m.
    ramp_cells = int(numpy.count_nonzero(
        (baked[BAKE_CELLS // 2] > 1e-4)
        & (baked[BAKE_CELLS // 2] < STEP_M - 1e-4)) / 2)
    assert 0.5 * feather_m <= ramp_cells * posting_m <= 2.0 * feather_m


@pytest.mark.skipif(not HAS_GDAL, reason="requires the GDAL bindings")
def test_layer_bake_coarsest_first_lets_the_finest_class_win(tmp_path):
    """Spec §3.2: a cell straddling BOTH regions ends at the finest
    class's value, because the coarse layer bakes first."""
    box = (LON + WINDOW_X0 - 0.01, LAT + WINDOW_Y0 - 0.01,
           LON + WINDOW_X1 + 0.01, LAT + WINDOW_Y1 + 0.01)
    coarse_path = tmp_path / "coarse.tif"
    fine_path = tmp_path / "fine.tif"
    _write_layer(coarse_path, box,
                 numpy.full((200, 200), 100.0, dtype=numpy.float32))
    _write_layer(fine_path, box,
                 numpy.full((400, 400), 100.0 + STEP_M,
                            dtype=numpy.float32))
    tile = _bake_tile()
    centre_lon = LON + (WINDOW_X0 + WINDOW_X1) / 2.0
    centre_lat = LAT + (WINDOW_Y0 + WINDOW_Y1) / 2.0
    # COARSEST FIRST, each with its own ruled feather.
    ELEVATION_LEVEL.bake_overlay_layer_into_alt_dem(
        tile, str(coarse_path),
        feather_m=ELEVATION_LEVEL._approach_ring_layer_feather_m(2),
        region=_disc(centre_lon, centre_lat, 2300.0), label="ring 2")
    ELEVATION_LEVEL.bake_overlay_layer_into_alt_dem(
        tile, str(fine_path),
        feather_m=ELEVATION_LEVEL._approach_ring_layer_feather_m(1),
        region=_disc(centre_lon, centre_lat, 1000.0), label="ring 1")
    centre = BAKE_CELLS // 2
    # The straddling centre reads the FINE layer, not the coarse one.
    assert tile.dem.alt_dem[centre, centre] == pytest.approx(
        100.0 + STEP_M, abs=1e-4)


@pytest.mark.skipif(not HAS_GDAL, reason="requires the GDAL bindings")
def test_region_none_bakes_the_whole_raster(tmp_path):
    """The tile-overlay caller passes no region, and must keep baking
    everywhere -- the byte-identity half of census row 4."""
    box = (LON + WINDOW_X0 - 0.01, LAT + WINDOW_Y0 - 0.01,
           LON + WINDOW_X1 + 0.01, LAT + WINDOW_Y1 + 0.01)
    layer_path = tmp_path / "overlay.tif"
    _write_layer(layer_path, box,
                 numpy.full((300, 300), 55.0, dtype=numpy.float32))
    tile = _bake_tile()
    assert ELEVATION_LEVEL.bake_overlay_layer_into_alt_dem(
        tile, str(layer_path), feather_m=60.0, region=None, label="overlay")
    margin = _blur_margin(60.0)
    assert numpy.allclose(
        tile.dem.alt_dem[margin:-margin, margin:-margin], 55.0, atol=1e-5)


@pytest.mark.skipif(not HAS_GDAL, reason="requires the GDAL bindings")
def test_the_tile_overlay_caller_is_unchanged(tmp_path, monkeypatch):
    """``bake_tile_overlay_into_alt_dem`` must bake exactly what it baked
    before the refactor: the whole raster, the overlay's own feather, and
    the same ``tile_overlay_provenance``."""
    box = (LON, LAT, LON + 1, LAT + 1)
    layer_path = tmp_path / "overlay.tif"
    _write_layer(layer_path, box,
                 numpy.full((300, 300), 77.0, dtype=numpy.float32))
    tile = _bake_tile()
    tile.elevation_level = "10"
    plan = {"definition": {"code": "TESTWIDE"}, "factor": 3,
            "target_resolution_m": 10.31, "path": str(layer_path)}
    monkeypatch.setattr(ELEVATION_LEVEL, "resolve_tile_overlay_plan",
                        lambda _tile: plan)
    assert ELEVATION_LEVEL.bake_tile_overlay_into_alt_dem(tile) is True
    margin = _blur_margin(tile.airport_elevation_inset_feather_m)
    assert numpy.allclose(
        tile.dem.alt_dem[margin:-margin, margin:-margin], 77.0, atol=1e-5)
    assert tile.dem.tile_overlay_provenance["provider"] == "TESTWIDE"
    assert tile.dem.tile_overlay_provenance["target_resolution_m"] == 10.31


@pytest.mark.skipif(not HAS_GDAL, reason="requires the GDAL bindings")
def test_region_mask_is_the_exact_polygon_not_the_cell_grid(tmp_path):
    """The mask is rasterised on the working-grid lattice, so a cell is
    in the region when its CENTRE is -- a half-tile region leaves
    exactly half the grid baked."""
    from shapely.geometry import box as _box

    box = (LON + WINDOW_X0 - 0.01, LAT + WINDOW_Y0 - 0.01,
           LON + WINDOW_X1 + 0.01, LAT + WINDOW_Y1 + 0.01)
    layer_path = tmp_path / "half.tif"
    _write_layer(layer_path, box,
                 numpy.full((300, 300), 10.0, dtype=numpy.float32))
    tile = _bake_tile()
    midpoint = LON + (WINDOW_X0 + WINDOW_X1) / 2.0
    region = _box(LON + WINDOW_X0 - 0.01, LAT + WINDOW_Y0 - 0.01,
                  midpoint, LAT + WINDOW_Y1 + 0.01)
    # A zero feather so the edge is a step, and the count is exact.
    ELEVATION_LEVEL.bake_overlay_layer_into_alt_dem(
        tile, str(layer_path), feather_m=0.0, region=region, label="half")
    baked = tile.dem.alt_dem
    row = baked[BAKE_CELLS // 2]
    # Past the zero-padded blur dip at the grid border.
    assert row[_blur_margin(0.0)] == pytest.approx(10.0, abs=1e-5)
    assert row[-1] == pytest.approx(0.0, abs=1e-6)
    # Half the columns, within one cell of the polygon edge.
    assert abs(int(numpy.count_nonzero(row > 5.0)) - BAKE_CELLS // 2) <= 2


# ═════════════════════════════════════════════════════════════════════
# THE COLD PREDICATE AND THE HARNESS REFUSAL (spec §5, census rows 7/14)
# ═════════════════════════════════════════════════════════════════════
def _simple_plan(tmp_path, stems=("cell_04_05_tenm_10.31m",)):
    """A minimal plan whose cells live under ``tmp_path``."""
    directory = os.path.join(
        str(tmp_path), "Elevation", "+30-110", "N39W107_approach_rings")
    return {
        "cells": [
            {"column": 4, "row": 5 + index, "class_m": 10.31,
             "reach_ring": 1, "collapsed": False, "provider": "TENM",
             "path": os.path.join(directory, stem + ".tif"),
             "stem": stem, "box": [LON + 0.4, LAT + 0.5,
                                   LON + 0.5, LAT + 0.6]}
            for index, stem in enumerate(stems)],
        "layers": [{"class_m": 10.31, "ring": 1, "region": "R1",
                    "feather_m": 300.0, "providers": ["TENM"],
                    "cells": list(stems)}],
        "regions": {"R1": "POLYGON EMPTY", "R2": "POLYGON EMPTY"},
        "airports": ["+039-107:KASE"], "neighbours_unknown": [],
        "feathers": {"ring1_m": 300.0, "ring2_m": 900.0},
        "superseded": [], "directory": directory, "stamp": "deadbeefdeadbeef",
    }


def test_cold_plan_names_the_rings_refresh(ring_corpus):
    plan = _simple_plan(ring_corpus)
    problem = ELEVATION_LEVEL.approach_ring_frame_problem(LAT, LON, plan)
    assert problem is not None
    assert problem["missing"] == ["cell_04_05_tenm_10.31m"]
    assert problem["on_disk"] == 0
    assert "--refresh-data rings" in problem["text"]
    assert "UNANSWERED" in problem["text"]


def test_a_cell_on_disk_is_a_warm_frame(ring_corpus):
    plan = _simple_plan(ring_corpus)
    path = plan["cells"][0]["path"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("not a real raster; only its existence is read here")
    assert ELEVATION_LEVEL.approach_ring_frame_problem(
        LAT, LON, plan) is None
    state = ELEVATION_LEVEL.approach_ring_state(LAT, LON, plan)
    assert state["on_disk"] == 1 and state["missing"] == []


def test_a_recorded_negative_is_a_warm_frame(ring_corpus):
    """A durable no-coverage negative ANSWERS a cell: the base DEM
    stands there and nothing would be fetched -- so it is not cold."""
    plan = _simple_plan(ring_corpus)
    index_path = FNAMES.approach_ring_index(LAT, LON)
    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    with open(index_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump({"cells": {"cell_04_05_tenm_10.31m":
                             ELEVATION_LEVEL.NO_RING_COVERAGE}},
                  handle, indent=2, sort_keys=True)
    assert ELEVATION_LEVEL.approach_ring_frame_problem(
        LAT, LON, plan) is None
    assert ELEVATION_LEVEL.approach_ring_state(
        LAT, LON, plan)["negatives"] == 1


def test_a_band_cell_of_the_same_stem_is_reused_by_reference(ring_corpus):
    """ONE CELL CACHE, TWO PLANS (spec §5): a cell the coastline band
    already fetched answers the ring plan where it lies -- nothing is
    copied, and the frame is warm."""
    plan = _simple_plan(ring_corpus)
    stem = plan["cells"][0]["stem"]
    band_path = os.path.join(
        FNAMES.coastline_band_directory(LAT, LON), stem + ".tif")
    os.makedirs(os.path.dirname(band_path), exist_ok=True)
    with open(band_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("the band's own cell")
    assert ELEVATION_LEVEL.approach_ring_cell_on_disk(
        LAT, LON, plan["cells"][0]) == band_path
    assert ELEVATION_LEVEL.approach_ring_frame_problem(
        LAT, LON, plan) is None
    # And the ring directory was NOT created to hold a copy.
    assert not os.path.isdir(plan["directory"])


def test_no_plan_is_never_a_problem():
    assert ELEVATION_LEVEL.approach_ring_frame_problem(LAT, LON, None) \
        is None
    assert ELEVATION_LEVEL.approach_ring_state(LAT, LON, None)["planned"] \
        == 0


def test_harness_refuses_a_cold_ring_frame(ring_corpus):
    from build_airport import require_dem_frame

    plan = _simple_plan(ring_corpus)
    problem = ELEVATION_LEVEL.approach_ring_frame_problem(LAT, LON, plan)
    warm = {"tile": [LAT, LON], "tile_stem": "N39W107", "base_raster": True,
            "airport_insets": True, "airports_layer": True,
            "tile_overlay": False}
    with pytest.raises(SystemExit) as refusal:
        require_dem_frame(warm, ring_problem=problem)
    assert "--refresh-data rings" in str(refusal.value)


def test_allow_degraded_dem_proceeds_without_rings(ring_corpus):
    """``--allow-degraded-dem`` accepts baking WITHOUT rings knowingly --
    and authorises no write (spec §5: it covers this class too)."""
    from build_airport import require_dem_frame

    plan = _simple_plan(ring_corpus)
    problem = ELEVATION_LEVEL.approach_ring_frame_problem(LAT, LON, plan)
    warm = {"tile": [LAT, LON], "tile_stem": "N39W107", "base_raster": True,
            "airport_insets": True, "airports_layer": True,
            "tile_overlay": False}
    require_dem_frame(warm, allow_degraded=True, ring_problem=problem)


def test_an_authorised_rings_refresh_defers_the_refusal(ring_corpus, capsys):
    """An authorised scope is NOT a refusal (the KDFW precedent): the
    problem is named as something this run will DERIVE."""
    from build_airport import require_dem_frame

    plan = _simple_plan(ring_corpus)
    problem = ELEVATION_LEVEL.approach_ring_frame_problem(LAT, LON, plan)
    warm = {"tile": [LAT, LON], "tile_stem": "N39W107", "base_raster": True,
            "airport_insets": True, "airports_layer": True,
            "tile_overlay": False}
    require_dem_frame(warm, requested={"rings"}, ring_problem=problem)
    assert "DERIVES it before the build" in capsys.readouterr().out


def test_a_dem_authorisation_does_not_cover_the_rings(ring_corpus):
    """``dem`` and ``rings`` are separate acts: authorising a DEM
    refresh must not defer a cold RING frame."""
    from build_airport import require_dem_frame

    plan = _simple_plan(ring_corpus)
    problem = ELEVATION_LEVEL.approach_ring_frame_problem(LAT, LON, plan)
    warm = {"tile": [LAT, LON], "tile_stem": "N39W107", "base_raster": True,
            "airport_insets": True, "airports_layer": True,
            "tile_overlay": False}
    with pytest.raises(SystemExit):
        require_dem_frame(warm, requested={"dem"}, ring_problem=problem)


def test_the_stamp_is_not_rewritten_when_it_did_not_change(ring_corpus):
    """Owner ruling e9daef5: a byte-identical stamp is never rewritten --
    an mtime-only write re-keys every stored arm through the corpus
    stamp's directory listing."""
    plan = _simple_plan(ring_corpus)
    outcomes = {"cell_04_05_tenm_10.31m": "ok"}
    ELEVATION_LEVEL._write_approach_ring_stamp(LAT, LON, plan, outcomes)
    stamp_path = FNAMES.approach_ring_index(LAT, LON)
    first = os.stat(stamp_path).st_mtime_ns
    ELEVATION_LEVEL._write_approach_ring_stamp(LAT, LON, plan, outcomes)
    assert os.stat(stamp_path).st_mtime_ns == first
    # A CHANGED stamp is written.
    ELEVATION_LEVEL._write_approach_ring_stamp(
        LAT, LON, plan, {"cell_04_05_tenm_10.31m":
                         ELEVATION_LEVEL.NO_RING_COVERAGE})
    with open(stamp_path, "r", encoding="utf-8") as handle:
        assert json.load(handle)["cells"]["cell_04_05_tenm_10.31m"] == \
            ELEVATION_LEVEL.NO_RING_COVERAGE


# ═════════════════════════════════════════════════════════════════════
# THE CORPUS STAMP AND THE DOWNLOAD-POLLUTION FLAG (spec §5)
# ═════════════════════════════════════════════════════════════════════
def test_corpus_stamp_carries_a_rings_dir_part(tmp_path):
    """Spec §5: the ring state does NOT enter ``dem_cache_state`` (its
    key set is frozen); the ledger's corpus stamp gains ONE part."""
    import artifact_ledger as AL

    frame = {"data_repo": str(tmp_path), "data_mounts": {},
             "dem_cache_before": {"tile_stem": "N39W107",
                                  "base_raster_files": [],
                                  "airports_layer_files": [],
                                  "airport_inset_dirs": []},
             "dem_frame_effective": {}}
    cold = AL.corpus_stamp(frame, root=tmp_path)
    assert "rings_dir" in cold["parts"]
    rings = tmp_path / "Elevation_data" / "+30-110" / "N39W107_approach_rings"
    rings.mkdir(parents=True)
    with open(rings / "cell_04_05_tenm_10.31m.tif", "w",
              encoding="utf-8", newline="\n") as handle:
        handle.write("a cell")
    warm = AL.corpus_stamp(frame, root=tmp_path)
    # A corpus that gained a ring cell is a DIFFERENT corpus: without
    # this a PRE-rings control would be served for a POST-rings build.
    assert warm["parts"]["rings_dir"] != cold["parts"]["rings_dir"]
    assert warm["sha256"] != cold["sha256"]


def test_dem_cache_state_key_set_is_unchanged():
    """STOP list item 3: no key was added to the frozen dict."""
    from build_airport import dem_cache_state

    state = dem_cache_state(
        os.path.join(os.path.dirname(os.path.dirname(__file__))), LAT, LON)
    assert set(state) == {
        "tile", "tile_stem", "base_raster", "base_raster_files",
        "airport_insets", "airport_inset_dirs", "tile_overlay",
        "airports_layer", "airports_layer_files"}


def test_rings_fetched_disqualifies_a_build_time_record(tmp_path):
    """A step-1 pass that FETCHED ring cells spent unbudgeted download
    wall time inside step 1, so its record is no baseline -- exactly the
    ``insets_fetched`` treatment (spec §5)."""
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "tools"))
    import check_build_time as CBT

    record = {"features": {"textures_missing": 0, "insets_fetched": 0,
                           "rings_fetched": 1},
              "step_seconds": {"1 vector": 10.0, "2 mesh": 20.0}}
    store = tmp_path / "store"
    store.mkdir()
    with open(store / "+39-107.json", "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump([record], handle)
    assert CBT.newest_tile_measurement("+39-107", str(store)) is None
    record["features"]["rings_fetched"] = 0
    with open(store / "+39-107.json", "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump([record], handle)
    assert CBT.newest_tile_measurement("+39-107", str(store)) is not None
