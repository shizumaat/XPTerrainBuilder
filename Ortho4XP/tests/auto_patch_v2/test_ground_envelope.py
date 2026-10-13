"""THE GROUND ENVELOPE and the lake that runs off the tile (issue #623).

The owner's read of a mountain-lake airport: "massive spikes right next to
the runway, hundreds of feet tall".  Measured: 15 vertices of the runway's
outer strip stood at exactly 1,798.00 m beside a 535 m runway, the solve
was ``optimal`` and the patch shipped.  The strip vertices stand in a lake;
the lake's outline runs on into the next two tiles; its level was the
median of the tile's raster over posts across the WHOLE outline, and the
raster answers a post beyond its edge with the edge cell — a mountainside.

Four twins, one per layer:

* THE CAUSE — a body is levelled from the posts inside it AND inside the
  tile, and a body with no sample has NO level (never 0.0);
* THE SOLVE GUARD — ``solve/ground_band``: a solved vertex outside every
  level the map's ground holds is named, whatever row put it there;
* THE SHIP GUARD — ``sentinel_elevation`` reads BOTH sides, against the
  published envelope when the patch carries it, on both instruments;
* THE FAILURE — a named catalogue entry, and the verify gate.
"""
from __future__ import annotations

import math
import sys
import types
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_v2parity186 as P                                 # noqa: E402
from test_v2parity186 import cg                              # noqa: E402,F401

from auto_patch_v2.law import Law                            # noqa: E402
from auto_patch_v2.solve.ground_band import (ground_envelope,  # noqa: E402
                                             outside_envelope)
from auto_patch_v2.verify import pins                        # noqa: E402
from auto_patch_v2.verify.census import DEFECT_KEYS, defect_gate  # noqa: E402

_RUNWAY_M = 535.0
_LAKE_M = 532.0
_EDGE_M = 1798.0


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("HECA")


# ── THE CAUSE ───────────────────────────────────────────────────────────

def _tile_with_a_mountain_edge():
    """A 1° raster: the lake's level everywhere, a mountainside on the
    east column and the north row — what a clipped post reads."""
    from auto_patch_v2.airport.dem_production import _BakedTile
    alt = np.full((101, 101), _LAKE_M)
    alt[:, -1] = _EDGE_M
    alt[0, :] = _EDGE_M
    return _BakedTile(49, -118, alt, 0.0, 1.0, 0.0, 1.0)


def test_a_lake_running_off_the_tile_is_levelled_inside_the_tile():
    from shapely.geometry import MultiPolygon, box
    from auto_patch_v2.airport.dem_production import TileWater
    # the outline: a third of it in this tile, the rest east and north
    lake = MultiPolygon([box(0.70, 0.40, 1.60, 1.50)])
    w = TileWater(49, -118, None, lake)
    idx = w.index_of(np.array([49.5]), np.array([-117.2]))
    assert idx[0] >= 0
    level = w.level_of(int(idx[0]), _tile_with_a_mountain_edge().sample)
    assert level == pytest.approx(_LAKE_M, abs=0.5), \
        "the level is the lake's own, not the tile edge's mountainside"


def test_a_body_with_no_sample_has_no_level_never_sea_level():
    from shapely.geometry import MultiPolygon, box
    from auto_patch_v2.airport.dem_production import TileWater
    w = TileWater(49, -118, None, MultiPolygon([box(0.2, 0.2, 0.3, 0.3)]))

    def void(lat, lon):
        return np.full(np.shape(lat), np.nan)

    assert math.isnan(w.level_of(0, void))
    # ... and a body wholly beyond the tile's own cell has no post at all
    far = TileWater(49, -118, None, MultiPolygon([box(1.2, 0.2, 1.3, 0.3)]))
    assert math.isnan(far.level_of(0, _tile_with_a_mountain_edge().sample))


# ── THE SOLVE GUARD ─────────────────────────────────────────────────────

def _map(dem_by_vertex):
    verts = {v: types.SimpleNamespace(id=v, key=(49.0 + v * 1e-4, -117.0),
                                      dem_z=d)
             for v, d in dem_by_vertex.items()}
    return types.SimpleNamespace(vertices=verts)


def test_the_envelope_is_the_dem_hull_widened_by_the_laws_drop(law):
    drop = float(law.tables.emit.cockpit.sentinel_drop_m)
    pm = _map({0: 531.0, 1: 545.0, 2: None, 3: float("nan")})
    assert ground_envelope(pm, law) == (531.0 - drop, 545.0 + drop)
    assert ground_envelope(_map({0: None}), law) is None


def test_a_vertex_pinned_off_the_ground_is_named(law):
    pm = _map({v: 531.0 + 0.1 * v for v in range(40)})
    env = ground_envelope(pm, law)
    z = {v: _RUNWAY_M for v in range(40)}
    assert outside_envelope(pm, z, env) == []
    z[7] = _EDGE_M                      # the lake's wrong level, held exactly
    z[9] = 0.0                          # the crater class, same guard
    z[11] = float("nan")
    got = outside_envelope(pm, z, env)
    assert [r["vertex"] for r in got] == [11, 7, 9]
    assert got[1]["outside_m"] == pytest.approx(_EDGE_M - env[1])
    assert got[1]["dem_m"] == pytest.approx(531.7)
    assert outside_envelope(pm, z, None) == []


def test_a_far_structure_on_its_own_ground_is_inside_the_envelope(law):
    """A road tunnel up the valley stands 300 m over the runway on ITS OWN
    ground (measured on 11 built airports): the hull holds it."""
    dem = {v: 2750.0 for v in range(40)}
    dem.update({v: 3105.0 for v in range(40, 48)})
    pm = _map(dem)
    z = {v: d - 8.0 if v >= 40 else d for v, d in dem.items()}
    assert outside_envelope(pm, z, ground_envelope(pm, law)) == []


# ── THE SHIP GUARD, both instruments ────────────────────────────────────

def _spiked(*, envelope):
    """The parity layout's lawful twin with ONE strip vertex at the wrong
    lake level, and (optionally) the published envelope."""
    rings, side = P._layout(clean=True)
    role, ref, ring, cn, cl = rings[2]
    assert role == "graded_strip"
    la, lo, _z = ring[0]
    rings[2] = (role, ref, [(la, lo, _EDGE_M), *ring[1:]], cn, cl)
    if envelope:
        side = dict(side, ground_envelope=[P._BASE_Z_M - 60.0,
                                           P._BASE_Z_M + 60.0])
    return rings, side


@pytest.mark.parametrize("envelope", [False, True])
def test_a_vertex_far_above_the_band_is_a_sentinel_on_both_readers(
        cg, tmp_path, envelope):
    rings, side = _spiked(envelope=envelope)
    v2 = pins.sentinel_elevation(P._patch(rings, side))
    v1 = P._oracle(cg, tmp_path, "spiked", rings, side)["sentinel_elevation"]
    assert len(v2) == len(v1) == 1
    assert v2[0]["magnitude_m"] == pytest.approx(v1[0].de_m, abs=0.01)
    assert v2[0]["magnitude_m"] > 1500.0
    assert v2[0]["way_a"].startswith("adjacent_ground")


def test_the_published_envelope_outranks_the_patchs_own_percentiles(
        cg, tmp_path):
    """A lawful vertex far outside the patch's own band but inside the
    ground envelope (a tunnel mouth down the bluff) prices nothing; one
    outside the envelope prices whatever the percentiles say."""
    rings, side = P._layout(clean=True)
    role, ref, ring, cn, cl = rings[-1]
    la, lo, _z = ring[0]
    rings[-1] = (role, ref, [(la, lo, P._BASE_Z_M - 110.0), *ring[1:]], cn, cl)
    wide = dict(side, ground_envelope=[P._BASE_Z_M - 200.0, P._BASE_Z_M + 60.0])
    assert pins.sentinel_elevation(P._patch(rings, wide)) == []
    assert P._oracle(cg, tmp_path, "wide", rings, wide)["sentinel_elevation"] == []
    assert len(pins.sentinel_elevation(P._patch(rings, side))) == 1
    assert len(P._oracle(cg, tmp_path, "own", rings, side)
               ["sentinel_elevation"]) == 1


# ── THE FAILURE ─────────────────────────────────────────────────────────

def test_a_sentinel_row_fails_the_airport_at_verify(law):
    assert "sentinel_elevation" in DEFECT_KEYS
    rings, side = _spiked(envelope=True)
    rows = pins.sentinel_elevation(P._patch(rings, side))
    defects, _under = defect_gate(law, {"sentinel_elevation": rows})
    assert defects == {"sentinel_elevation": 1}


def test_the_solve_guard_has_its_own_catalogue_entry():
    import O4_Tile_Failures as FAIL
    code = "airport_surface_off_ground"
    assert code in FAIL.CATALOGUE
    assert FAIL.code_for_stage("solve", code) == code
    text = FAIL.render(FAIL.fold([FAIL.record(code, airport="ZZZZ")],
                                 "+49-118", built=True)[0])
    assert "ZZZZ" in text and "impossible height" in text


def test_the_pipeline_and_the_sidecar_read_the_one_derivation():
    import inspect
    from auto_patch_v2.emit import osm_adapter
    from auto_patch_v2.pipeline import build as B, publication as PUB
    assert "outside_envelope(pm, sol.z, _envelope)" in inspect.getsource(B)
    assert '"ground_envelope"' in inspect.getsource(PUB.publication)
    assert '"ground_envelope"' in inspect.getsource(osm_adapter)
