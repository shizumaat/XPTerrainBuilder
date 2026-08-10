"""FLAT-SITE mode twins — docs/specs/flat-site-mode-spec.md §4.

Synthetic fixtures only: no X-Plane install, no CIFP, no network, no DEM
download, no build, no write anywhere.  Every raster here is an in-memory
array over a synthetic 1°x1° tile at (0, 0).

What the spec asks these to hold:

* constant plateau + a MONOTONE feather ring + the provenance entry;
* the degeneracy arms — ``not_flat`` / ``lidar_credible`` / ``no_data`` /
  gate-off leave DEM prep BYTE-IDENTICAL;
* the spread > 0 fixture — Z0 is the CIFP MEAN and the thresholds
  themselves are untouched (the runway profile keeps binding to them);
* a water row in the feather ring is unchanged.

WHAT IS NOT ASSERTED HERE, and why.  The runway profile's CIFP-absolute
binding (spec §3.2) is EXISTING law in
``pavement/runway_segments.generate_patch_osm``; this change adds no code
on that path and the twin below asserts the property this change owns —
that the mode reads the thresholds, derives Z0 from them, and mutates
nothing but ``alt_dem`` and the provenance attribute.
"""
from __future__ import annotations

import hashlib
import math
import os
import sys
import types

import numpy as np
import pytest
from shapely.geometry import Polygon

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (os.path.join(_ROOT, "src"), _ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
from auto_patch import config, flat_site, flat_site_mode, provenance  # noqa: E402

R_EARTH = 6378137.0
TILE_LAT, TILE_LON = 0, 0

#: A working grid at ~1 arc-second over the synthetic tile.  Small enough
#: to keep the twins instant, fine enough that a 60 m feather spans
#: several posts.
GRID_N = 1201
STEP_M = 111319.49 / (GRID_N - 1)          # ~92.8 m per post at the equator

#: The airport: a boundary polygon in DEGREES about (0.5, 0.5).
ANCHOR = (0.5, 0.5)
_HALF_LON = 0.010                          # ~1.1 km half-width
_HALF_LAT = 0.006
BOUNDARY = Polygon([
    (ANCHOR[1] - _HALF_LON, ANCHOR[0] - _HALF_LAT),
    (ANCHOR[1] + _HALF_LON, ANCHOR[0] - _HALF_LAT),
    (ANCHOR[1] + _HALF_LON, ANCHOR[0] + _HALF_LAT),
    (ANCHOR[1] - _HALF_LON, ANCHOR[0] + _HALF_LAT),
])

#: Four identical thresholds — the OTHH consensus shape (spread 0).
FLAT_THRESHOLDS = [3.96, 3.96, 3.96, 3.96]

FEATHER_M = 60.0


class FakeDEM:
    """The surface ``O4_DEM_Utils.DEM`` exposes to the bake and detector."""

    def __init__(self, elevation_fn=None, *, constant=None, n=GRID_N,
                 elevation_level="auto", nodata=-32768.0):
        self.lat, self.lon = TILE_LAT, TILE_LON
        self.nxdem = self.nydem = int(n)
        self.x0 = self.y0 = 0.0
        self.x1 = self.y1 = 1.0
        self.nodata = nodata
        self.elevation_level = elevation_level
        self.source_path = "<synthetic>"
        if constant is not None:
            # No meshgrid for a constant surface: the fine-grid fixture
            # would otherwise materialise three 13 M-cell float64 arrays.
            self.alt_dem = np.full((self.nydem, self.nxdem), float(constant),
                                   dtype=np.float32)
            return
        cos0 = math.cos(math.radians(ANCHOR[0]))
        lon_deg = TILE_LON + np.linspace(0.0, 1.0, self.nxdem)
        lat_deg = TILE_LAT + np.linspace(1.0, 0.0, self.nydem)
        x_m = np.radians(lon_deg - ANCHOR[1]) * R_EARTH * cos0
        y_m = np.radians(lat_deg - ANCHOR[0]) * R_EARTH
        grid_x, grid_y = np.meshgrid(x_m, y_m)
        self.alt_dem = np.asarray(elevation_fn(grid_x, grid_y),
                                  dtype=np.float32)


def make_tile(dem):
    return types.SimpleNamespace(
        lat=TILE_LAT, lon=TILE_LON, dem=dem,
        airport_elevation_inset_feather_m=FEATHER_M)


def flat_dem(value=0.0, n=GRID_N):
    return FakeDEM(constant=value, n=n)


def sloped_dem(slope_pct=2.0, n=GRID_N):
    """Real relief: a 2 % ramp — S2 fails on slope AND on the relief floor."""
    return FakeDEM(lambda x, y: x * (slope_pct / 100.0), n=n)


def fake_apt(boundary=BOUNDARY):
    return types.SimpleNamespace(runways=[], pavements=[], boundary=boundary)


def sha(array):
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def wire_airport(monkeypatch, thresholds=FLAT_THRESHOLDS, apt=None,
                 icaos=("TEST",)):
    """Point the decision function's three lookups at synthetic inputs.

    ``flat_site_substitutions`` resolves them at call time from their own
    modules, so patching the modules is enough — nothing here replaces a
    detector function, so every verdict below is the real detector's.
    """
    from auto_patch import apt_dat_reader, osm_load

    per_icao = (thresholds if isinstance(thresholds, dict)
                else {icao: thresholds for icao in icaos})
    # The install the DEM-prep call site resolves from the engine config;
    # there is none in a headless twin.
    monkeypatch.setattr(flat_site_mode, "_resolve_xplane_root",
                        lambda: "/synthetic/X-Plane")
    monkeypatch.setattr(
        flat_site, "cifp_threshold_elevations",
        lambda root, icao: list(per_icao.get(icao.upper(), [])))
    monkeypatch.setattr(
        osm_load, "_pick_best_apt_dat_against_osm",
        lambda root, icao: "/synthetic/apt.dat")
    monkeypatch.setattr(
        apt_dat_reader, "load_airport",
        lambda path, icao, **kwargs: (apt if apt is not None else fake_apt()))


def substitutions(tile, icaos=("TEST",)):
    return flat_site_mode.flat_site_substitutions(
        tile, dico_airports={icao: {"key_type": "icao"} for icao in icaos},
        xplane_root="/synthetic/X-Plane")


def dico(*icaos):
    return {icao: {"key_type": "icao"} for icao in (icaos or ("TEST",))}


# ──────────────────────────────────────────────────────────────────────
# Fixture 1 — the constant plateau and its monotone feather ring
# ──────────────────────────────────────────────────────────────────────
def test_synthetic_inset_is_a_constant_plateau_with_a_monotone_feather():
    """Z0 across the interior, a linear ramp to base over the feather.

    On the 1 arc-second grid (~31 m posts) a 60 m feather spans about two
    posts, so the ramp is visible as values STRICTLY between base and Z0 —
    the property that distinguishes a feather from a cliff.
    """
    dem = flat_dem(0.0, n=3601)
    tile = make_tile(dem)
    before = dem.alt_dem.copy()
    z0 = 3.96
    # A rect spanning many working-grid posts on each axis.
    x0, y0, x1, y1 = 0.480, 0.490, 0.520, 0.510
    inset = INSETS._ConstantInset(x0, y0, x1, y1, z0, label="TEST")
    INSETS._bake_one_inset(tile, None, FEATHER_M, inset=inset)

    step_deg = 1.0 / (dem.nxdem - 1)

    def column(x_deg):
        return int(round(x_deg / step_deg))

    def row(y_deg):
        return int(round((1.0 - y_deg) / step_deg))

    centre = dem.alt_dem[row((y0 + y1) / 2.0), column((x0 + x1) / 2.0)]
    assert centre == pytest.approx(z0, abs=1e-4)

    # OUTSIDE the rect: byte-identical.  The substitution's footprint is
    # exactly the rect it declares — nothing leaks past the data edge.
    outside_col = column(x0) - 2
    assert np.array_equal(dem.alt_dem[:, :outside_col + 1],
                          before[:, :outside_col + 1])

    # The FEATHER RING, read inward along a row through the middle: base
    # at the edge, Z0 by ``feather_m`` in, monotone non-decreasing between.
    middle_row = row((y0 + y1) / 2.0)
    ring = dem.alt_dem[middle_row, column(x0):column(x0) + 6]
    assert ring[0] == pytest.approx(0.0, abs=1e-4)      # weight 0 at the edge
    assert np.all(np.diff(ring) >= -1e-6)               # monotone inward
    assert ring[-1] == pytest.approx(z0, abs=1e-4)      # past the feather
    # ...and it is a RAMP, not a cliff: at least one post lands strictly
    # between the base surface and Z0.
    assert np.any((ring > 1e-3) & (ring < z0 - 1e-3))


def test_water_row_in_and_beyond_the_feather_ring_is_unchanged():
    """A sea row outside the synthetic rect keeps its own elevation.

    The DEM bake has no water machinery — none is added here (spec §2.4
    forbids inventing a mask).  What it DOES guarantee, and what the
    shoreline rests on at this layer, is that the substitution writes
    only inside its declared rect and contributes weight ZERO at the data
    edge, so water outside the extent is byte-identical and water at the
    edge keeps the base value exactly.  (Sea triangles are levelled later
    by ``O4_Mesh_Utils``' own sea/water pass, which reads the mesh's water
    classification and not this raster.)
    """
    dem = flat_dem(0.0, n=3601)
    tile = make_tile(dem)
    x0, y0, x1, y1 = 0.480, 0.490, 0.520, 0.510
    step_deg = 1.0 / (dem.nxdem - 1)
    # Two "lagoon" rows below sea level: one exactly ON the rect's south
    # data edge (inside the bake window, weight 0 — the feather ring's own
    # boundary) and one two posts beyond it.
    edge_row = int(round((1.0 - y0) / step_deg))
    beyond_row = edge_row + 2
    dem.alt_dem[edge_row, :] = -1.5
    dem.alt_dem[beyond_row, :] = -1.5
    before_edge = dem.alt_dem[edge_row].copy()
    before_beyond = dem.alt_dem[beyond_row].copy()

    INSETS._bake_one_inset(
        tile, None, FEATHER_M,
        inset=INSETS._ConstantInset(x0, y0, x1, y1, 3.96))

    assert np.array_equal(dem.alt_dem[edge_row], before_edge)
    assert np.array_equal(dem.alt_dem[beyond_row], before_beyond)


# ──────────────────────────────────────────────────────────────────────
# Fixture 2 — the decision: which airports get substituted
# ──────────────────────────────────────────────────────────────────────
def test_flat_candidate_yields_one_substitution_at_z0(monkeypatch):
    wire_airport(monkeypatch)
    tile = make_tile(flat_dem(0.0))

    got = substitutions(tile)

    assert len(got) == 1
    assert got[0]["icao"] == "TEST"
    assert got[0]["z0_m"] == pytest.approx(3.96)
    assert got[0]["record"]["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE
    x0, y0, x1, y1 = got[0]["extent_deg"]
    # The extent is the boundary bbox grown by FLAT_SITE_MARGIN_M, in
    # TILE-RELATIVE degrees (tile origin 0/0 here, so degrees outright).
    margin_deg = config.FLAT_SITE_MARGIN_M / 111319.49
    assert x0 == pytest.approx(ANCHOR[1] - _HALF_LON - margin_deg, abs=2e-4)
    assert x1 == pytest.approx(ANCHOR[1] + _HALF_LON + margin_deg, abs=2e-4)
    assert y0 == pytest.approx(ANCHOR[0] - _HALF_LAT - margin_deg, abs=2e-4)
    assert y1 == pytest.approx(ANCHOR[0] + _HALF_LAT + margin_deg, abs=2e-4)


def test_gate_off_substitutes_nothing_and_leaves_the_raster_identical(
        monkeypatch):
    """``O4_FLAT_SITE_MODE=0`` restores pre-change behaviour (spec §3.1)."""
    wire_airport(monkeypatch)
    monkeypatch.setattr(config, "FLAT_SITE_MODE", False)
    dem = flat_dem(0.0)
    tile = make_tile(dem)
    before = sha(dem.alt_dem)

    assert substitutions(tile) == []
    INSETS.overlay_flat_site_insets(tile, {"TEST": {"key_type": "icao"}})

    assert sha(dem.alt_dem) == before
    assert not hasattr(dem, "synthetic_flat_site_provenance")


def test_not_flat_substitutes_nothing_and_leaves_the_raster_identical(
        monkeypatch):
    wire_airport(monkeypatch)
    dem = sloped_dem(2.0)
    tile = make_tile(dem)
    before = sha(dem.alt_dem)

    got = substitutions(tile)

    assert got == []
    INSETS.overlay_flat_site_insets(tile, {"TEST": {"key_type": "icao"}})
    assert sha(dem.alt_dem) == before


def test_lidar_credible_substitutes_nothing(monkeypatch):
    """A metre-credible DEM is trustworthy — the normal path already works."""
    wire_airport(monkeypatch)
    dem = flat_dem(0.0)
    dem.airport_inset_provenance = [
        {"icao": "TEST", "provider": "LIDAR", "native_resolution_m": 1.0}]
    tile = make_tile(dem)
    before = sha(dem.alt_dem)

    got = substitutions(tile)

    assert got == []
    INSETS.overlay_flat_site_insets(tile, {"TEST": {"key_type": "icao"}})
    assert sha(dem.alt_dem) == before


def test_no_cifp_is_no_data_and_substitutes_nothing(monkeypatch):
    wire_airport(monkeypatch, thresholds=[])
    dem = flat_dem(0.0)
    tile = make_tile(dem)
    before = sha(dem.alt_dem)

    assert substitutions(tile) == []
    INSETS.overlay_flat_site_insets(tile, {"TEST": {"key_type": "icao"}})
    assert sha(dem.alt_dem) == before


def test_threshold_spread_beyond_the_cap_substitutes_nothing(monkeypatch):
    wire_airport(monkeypatch,
                 thresholds=[0.0, config.FLAT_SITE_THRESHOLD_SPREAD_M + 1.0])
    tile = make_tile(flat_dem(0.0))

    assert substitutions(tile) == []


def test_flat_declared_substitutes_exactly_like_flat_candidate(monkeypatch):
    """The owner-declaration verdict is EQUIVALENT to the measured one.

    Detector spec v3 adds ``flat_declared``; spec §1 makes the two the
    same event for this mode — same substitution, same Z0, and Z0 read
    from the record rather than recomputed, because a declaration may
    carry its own elevation there.
    """
    wire_airport(monkeypatch)
    dem = sloped_dem(2.0)                  # S2 would REFUSE this surface
    tile = make_tile(dem)
    real_classify = flat_site.classify_site
    declared = dict(z0_m=7.25, verdict=flat_site_mode.VERDICT_FLAT_DECLARED)
    monkeypatch.setattr(
        flat_site, "classify_site",
        lambda **kwargs: dict(real_classify(**kwargs), **declared))

    got = substitutions(tile)

    assert len(got) == 1
    assert got[0]["verdict"] == "flat_declared"
    assert got[0]["z0_m"] == pytest.approx(7.25)   # the RECORD's Z0

    INSETS.overlay_flat_site_insets(tile, {"TEST": {"key_type": "icao"}})
    entry = dem.synthetic_flat_site_provenance[0]
    assert entry["verdict"] == "flat_declared"
    assert entry["z0_m"] == pytest.approx(7.25)


def test_an_unknown_future_verdict_takes_the_normal_path(monkeypatch):
    """An allow-list, not a deny-list: unknown ⇒ real DEM, never a crash."""
    wire_airport(monkeypatch)
    dem = flat_dem(0.0)
    tile = make_tile(dem)
    before = sha(dem.alt_dem)
    real_classify = flat_site.classify_site
    monkeypatch.setattr(
        flat_site, "classify_site",
        lambda **kwargs: dict(real_classify(**kwargs),
                              verdict="flat_by_some_future_signal"))

    assert substitutions(tile) == []
    INSETS.overlay_flat_site_insets(tile, {"TEST": {"key_type": "icao"}})
    assert sha(dem.alt_dem) == before
    assert not hasattr(dem, "synthetic_flat_site_provenance")


def test_multi_airport_tile_substitutes_only_its_flat_candidates(monkeypatch):
    """Per airport (spec §2.1): one flat, one whose thresholds disagree."""
    wire_airport(monkeypatch, thresholds={
        "AAAA": FLAT_THRESHOLDS,
        "BBBB": [0.0, config.FLAT_SITE_THRESHOLD_SPREAD_M + 10.0],
    })
    tile = make_tile(flat_dem(0.0))

    got = substitutions(tile, icaos=("AAAA", "BBBB"))

    assert [entry["icao"] for entry in got] == ["AAAA"]


# ──────────────────────────────────────────────────────────────────────
# Fixture 3 — nonzero spread: Z0 is the CIFP MEAN, thresholds untouched
# ──────────────────────────────────────────────────────────────────────
def test_spread_within_the_cap_places_z0_at_the_cifp_mean(monkeypatch):
    """Thresholds 2 m apart: off-runway ground goes to their mean.

    The runways keep their CIFP-absolute profiles — those values are read
    from the CIFP file by ``runway_segments``, a path this change does not
    touch, and the twin asserts the mode neither rewrites nor rounds them.
    """
    thresholds = [12.0, 14.0]
    original = list(thresholds)
    wire_airport(monkeypatch, thresholds=thresholds)
    dem = flat_dem(0.0)
    tile = make_tile(dem)

    got = substitutions(tile)

    assert len(got) == 1
    assert got[0]["z0_m"] == pytest.approx(13.0)         # the MEAN, not an end
    assert got[0]["record"]["s1_spread_m"] == pytest.approx(2.0)
    assert thresholds == original                        # CIFP values untouched

    INSETS.overlay_flat_site_insets(tile, {"TEST": {"key_type": "icao"}})
    x0, y0, x1, y1 = got[0]["extent_deg"]
    step_deg = 1.0 / (dem.nxdem - 1)
    centre = dem.alt_dem[int(round((1.0 - (y0 + y1) / 2.0) / step_deg)),
                         int(round(((x0 + x1) / 2.0) / step_deg))]
    assert centre == pytest.approx(13.0, abs=1e-4)       # off-runway at Z0


# ──────────────────────────────────────────────────────────────────────
# THE TWO REGRESSIONS THE FIRST OTHH ACCEPTANCE BUILD FOUND (2026-08-09)
#
# That build substituted NOTHING while stamping a flat_candidate verdict.
# Neither fixture above could see it, because both hand the decision the
# things a real build has to FIND: an X-Plane root and a warm DEM.
# ──────────────────────────────────────────────────────────────────────
def test_a_warm_cache_shaped_dem_is_substituted_with_no_bake_at_all(
        monkeypatch):
    """WARM SHAPE: a prebaked raster, no cached inset, no bake invoked.

    The substitution hangs off DEM ASSEMBLY, not off the inset bake — on
    a warm corpus ``bake_airport_insets_into_alt_dem`` has nothing to do
    and returns early, and a mode that only fired alongside it would be
    a mode that never fires in production.  Here the bake is not called
    at ALL and the extent must still come out constant at Z0.
    """
    wire_airport(monkeypatch)
    dem = flat_dem(0.0)                      # a raster already "loaded"
    dem.airport_inset_provenance = []        # the bake ran and baked none
    tile = make_tile(dem)

    INSETS.overlay_flat_site_insets(tile, dico())

    entry = dem.synthetic_flat_site_provenance[0]
    assert entry["z0_m"] == pytest.approx(3.96)
    x0, y0, x1, y1 = entry["extent_tile_degrees"]
    step_deg = 1.0 / (dem.nxdem - 1)
    centre = dem.alt_dem[int(round((1.0 - (y0 + y1) / 2.0) / step_deg)),
                         int(round(((x0 + x1) / 2.0) / step_deg))]
    assert centre == pytest.approx(3.96, abs=1e-4)


def test_the_builds_own_xplane_root_is_used_when_the_caller_passes_none(
        monkeypatch):
    """DEM prep is entered from several call sites; only one had the root.

    ``elevation._compute_elevations`` composes the tile DEM BEFORE the
    per-surface solver does and passes no ``xplane_root``; ``_DEM_CACHE``
    then memoises whatever surface that first caller produced.  So the
    root has to be BUILD-scoped: with no argument and no engine config,
    the classification must still find the install
    ``build_airport_pavement`` was handed.
    """
    wire_airport(monkeypatch)
    # Undo the fixture's resolver patch: this test is about the real one.
    monkeypatch.undo()
    wire_airport(monkeypatch)
    monkeypatch.setattr(flat_site_mode, "_BUILD_XPLANE_ROOT", None)
    monkeypatch.setattr(flat_site_mode, "_resolve_xplane_root",
                        flat_site_mode._resolve_xplane_root)
    dem = flat_dem(0.0)
    tile = make_tile(dem)

    # No root anywhere: the mode must decline, loudly and harmlessly.
    monkeypatch.setattr(flat_site_mode, "_resolve_xplane_root",
                        lambda: None)
    assert flat_site_mode.flat_site_substitutions(tile, dico()) == []

    # The build recorded its root -> the SAME call now substitutes.
    monkeypatch.setattr(
        flat_site_mode, "_resolve_xplane_root",
        lambda: flat_site_mode.build_xplane_root())
    flat_site_mode.set_build_xplane_root("/synthetic/X-Plane")
    try:
        got = flat_site_mode.flat_site_substitutions(tile, dico())
    finally:
        flat_site_mode.set_build_xplane_root(None)

    assert [entry["icao"] for entry in got] == ["TEST"]


def test_the_bake_does_not_carry_the_substitution(monkeypatch):
    """The wiring is OUT of the bake: baking alone substitutes nothing.

    Locks the correction — if a later edit re-attaches the overlay to
    ``bake_airport_insets_into_alt_dem``, the mode silently becomes
    conditional on the inset feature again.
    """
    wire_airport(monkeypatch)
    dem = flat_dem(0.0)
    tile = make_tile(dem)
    tile.airport_elevation_insets = False        # the bake's own gate
    before = sha(dem.alt_dem)

    INSETS.bake_airport_insets_into_alt_dem(tile)

    assert sha(dem.alt_dem) == before
    assert not hasattr(dem, "synthetic_flat_site_provenance")


# ──────────────────────────────────────────────────────────────────────
# Fixture 4 — the provenance entry
# ──────────────────────────────────────────────────────────────────────
def test_overlay_stamps_synthetic_flat_site_provenance(monkeypatch):
    wire_airport(monkeypatch)
    dem = flat_dem(0.0)
    tile = make_tile(dem)

    INSETS.overlay_flat_site_insets(tile, {"TEST": {"key_type": "icao"}})

    stamped = dem.synthetic_flat_site_provenance
    assert len(stamped) == 1
    entry = stamped[0]
    assert entry["icao"] == "TEST"
    assert entry["kind"] == "synthetic_flat_site"
    assert entry["z0_m"] == pytest.approx(3.96)
    assert entry["feather_m"] == FEATHER_M
    assert len(entry["extent_wgs84"]) == 4
    assert entry["record"]["verdict"] == flat_site.VERDICT_FLAT_CANDIDATE

    meta = provenance.dem_provenance_from_dem(dem, icao="TEST")
    assert meta["synthetic_flat_site"]["z0_m"] == pytest.approx(3.96)
    assert meta["raw"] is True            # no FETCHED inset baked here
    assert "FLAT_SITE(Z0=3.96 m)" in provenance.dem_label(meta)


def test_provenance_selects_this_airports_entry_on_a_multi_airport_dem():
    dem = flat_dem(0.0)
    dem.synthetic_flat_site_provenance = [
        {"icao": "AAAA", "kind": "synthetic_flat_site", "z0_m": 1.0},
        {"icao": "BBBB", "kind": "synthetic_flat_site", "z0_m": 2.0},
    ]

    assert provenance.dem_provenance_from_dem(
        dem, icao="BBBB")["synthetic_flat_site"]["z0_m"] == 2.0
    assert provenance.dem_provenance_from_dem(
        dem, icao="CCCC")["synthetic_flat_site"] is None


def test_provenance_without_a_substitution_reads_exactly_as_before():
    """The real-DEM frame is unchanged: a None key, and the old label."""
    dem = flat_dem(0.0)

    meta = provenance.dem_provenance_from_dem(dem, icao="TEST")

    assert meta["synthetic_flat_site"] is None
    assert meta["raw"] is True
    assert provenance.dem_label(meta) == "base RAW (no inset baked)"
