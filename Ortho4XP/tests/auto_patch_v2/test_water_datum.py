"""WATER IS A DATUM — the v2 twins (owner RULINGS 2026-09-09m (1)(3);
mechanism 09o (1); spec ``docs/specs/auto-patch-v2/water-datum-spec.md``).

A synthetic frame with a CANAL cut across the graded strip:

* every ground vertex over the canal is PINNED at the water level and is
  no longer an unknown of the sheet;
* every other row that would govern such a vertex is withdrawn;
* the flat-site datum region excludes the canal;
* a sampler with no water witness changes nothing (the pre-change arm).

The LEVEL rule is read directly off :class:`TileWater`: sea 0.0, an
inland body its own DEM median.
"""
from __future__ import annotations

import numpy as np
import pytest
from shapely.geometry import box

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate, water, water_exempt
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Diff, Linear, Pin, Source
from auto_patch_v2.planar.build import build
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
from tests.auto_patch_v2.test_v2smooth import RUN_LEN, _ValleyDem, _airport

#: The canal, in frame metres: a band across the strip's far side.
CANAL = box(-700.0, -100.0, 700.0, -60.0)
CANAL_LEVEL = 0.0


class _CanalDem(_ValleyDem):
    """The valley DEM plus a WATER WITNESS — the production frame's
    interface (``dem_production.ProductionDem.water_many`` /
    ``water_geometry``), nothing more."""

    provenance = {"synthetic": "V valley with a canal"}

    def water_many(self, xs, ys):
        xs = np.asarray(xs, float)
        ys = np.asarray(ys, float)
        wet = (xs >= -700.0) & (xs <= 700.0) & (ys >= -100.0) & (ys <= -60.0)
        level = np.where(wet, CANAL_LEVEL, np.nan)
        return wet, level

    def water_geometry(self, bounds=None):
        return CANAL if bounds is None else CANAL.intersection(box(*bounds))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _map(law, dem):
    airport, r = _airport(law, dem, ())
    cells = (
        Cell(0, "runway", "09/27",
             _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2, HALF_WIDTH),
             (), 3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -400.0, 60.0, 400.0, 83.0),
             (), None, "D", "airside", "taxi", {}),
    )
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    return pm, airport


@pytest.fixture(scope="module")
def canal(law):
    return _map(law, _CanalDem())


@pytest.fixture(scope="module")
def dry(law):
    return _map(law, _ValleyDem())


# ── (1) THE PIN ─────────────────────────────────────────────────────────

def test_ground_vertices_over_the_canal_are_pinned_at_the_water_level(canal, law):
    pm, airport = canal
    rows = water.water_pins(pm, law, airport)
    assert rows, "the canal crosses the graded strip: some ground stands on water"
    vw = view(pm, law)
    for r in rows:
        assert isinstance(r, Pin)
        assert r.z == pytest.approx(CANAL_LEVEL)
        x, y = vw.xy[r.v]
        assert CANAL.covers(box(x, y, x, y)), "a pin off the canal"
    # every candidate the canal covers is pinned, none of the dry ones
    wet = {r.v for r in rows}
    for v in vw.pavement_vertices:
        assert v not in wet, "pavement keeps its own law"


def test_no_water_witness_mints_nothing(dry, law):
    pm, airport = dry
    assert water.water_pins(pm, law, airport) == []


# ── (2) THE PIN IS THE VERTEX'S OWN LAW ─────────────────────────────────

def test_every_row_governing_a_pinned_vertex_is_withdrawn(canal, law):
    pm, airport = canal
    pins = water.water_pins(pm, law, airport)
    v = pins[0].v
    src = Source("fixture", "twin", ())
    band = Linear(((v, 1.0), (v + 1, -1.0)), -2.0, 0.0, src, None, None, v)
    both = Diff(v, pins[1].v, 0.05, 10.0, src)
    keep = Diff(v, 10 ** 6, 0.05, 10.0, src)       # one free end: the SHORE
    other_pin = Pin(v, 42.0, src)
    out, n = water_exempt(list(pins) + [band, both, keep, other_pin])
    assert n == 3
    assert keep in out and band not in out and both not in out
    assert other_pin not in out
    assert all(p in out for p in pins), "the water pins themselves survive"


def test_the_generator_is_registered_and_runs_before_the_seam(law, canal):
    from auto_patch_v2.constraints import GENERATORS
    names = [n for n, _fn in GENERATORS]
    assert "water_pins" in names
    assert names.index("water_pins") < names.index("seam_pins")
    pm, airport = canal
    cs, counts, _w = generate(pm, law, airport)
    assert counts["water_pins"] > 0
    assert counts["water_pin_row_withdrawn"] >= 0
    pinned = {p.v for p in cs.pins if p.source.generator == water.GEN}
    assert pinned, "the water pins reach the constraint set as PINS"
    for row in cs.linears:
        if getattr(row, "follows", None) in pinned:
            pytest.fail("a one-way row still governs a water-pinned vertex")


# ── (3) THE FLAT-SITE DATUM REGION ──────────────────────────────────────

def test_the_datum_region_excludes_the_canal():
    from auto_patch_v2.airport.flat_site import _cut_water
    region = box(-800.0, -400.0, 800.0, 400.0)
    cut, removed = _cut_water(_CanalDem(), region)
    assert removed == pytest.approx(CANAL.area, rel=1e-6)
    assert not cut.intersects(CANAL.buffer(-1.0))
    assert cut.covers(box(-100.0, 100.0, 100.0, 200.0))


def test_a_sampler_without_the_witness_leaves_the_region_alone():
    from auto_patch_v2.airport.flat_site import _cut_water
    region = box(-800.0, -400.0, 800.0, 400.0)
    cut, removed = _cut_water(_ValleyDem(), region)
    assert cut is region and removed is None


# ── the LEVEL rule ──────────────────────────────────────────────────────

def test_tile_water_levels_sea_zero_and_an_inland_body_its_dem_median():
    from auto_patch_v2.airport.dem_production import TileWater
    from shapely.geometry import MultiPolygon
    sea = MultiPolygon([box(0.0, 0.0, 0.1, 0.1)])
    lake = MultiPolygon([box(0.5, 0.5, 0.6, 0.6)])
    w = TileWater(25, 51, sea, lake)
    assert w.has_data and w.n_sea == 1 and w.n_inland == 1

    def sampler(lat, lon):
        return np.full(np.shape(lat), 12.5)

    lat = np.array([25.05, 25.55, 25.9])
    lon = np.array([51.05, 51.55, 51.9])
    idx = w.index_of(lat, lon)
    assert idx[0] >= 0 and idx[1] >= 0 and idx[2] == -1
    assert w.level_of(int(idx[0]), sampler) == 0.0          # SEA
    assert w.level_of(int(idx[1]), sampler) == pytest.approx(12.5)  # inland
    assert TileWater(25, 51, None, None).state()["has_data"] is False
