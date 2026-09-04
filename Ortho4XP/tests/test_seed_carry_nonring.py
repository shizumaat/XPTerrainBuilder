"""Twins for the NON-RING CARRIER WARM START (zero-airside R1 step 4,
lane r1backfill 2026-09-03; attribution `r1-pins-attribution-20260903.md`).

THE DEFECT.  ``_seed_elevations`` warm-starts RING vertices from their
shape's altitudes, but an apron spine STATION, an apron LATTICE point or
a gap-fill drainage SPINE node lies on no ring; re-read with no DEM (the
``solved_values`` mint, the final projection's entry seed) it fell to
branch 3 ``nearest_hard_backfill`` — the nearest CIFP runway corner —
while the solve had valued it and published that value in
``apron_spine_station_emit`` / ``apron_lattice_emit`` /
``gap_fill_presolve[*]["values"]``.  HECA: stations at 116.5 m over a
99.05 m surface, 977 of 1,362 pass-2 infeasible rows.

  (a) a station / lattice / gap-spine node's carried seed EQUALS the
      value the solve published for it (gate ON);
  (b) a node the solve never valued still takes the backfill, and the
      census reports it as such, per class;
  (c) gate OFF is byte-inert: the same read returns the backfill.
"""
import os

import auto_patch.pipeline                                    # noqa: F401
import pytest
from shapely.geometry import Polygon

from auto_patch.canonical_points import CanonicalPointRegistry

from auto_patch.elevation_per_surface import solver_primitives as SP
from auto_patch.layout import SHARED_VERTEX_TOL_M, BuiltShape, PavementLayout

ANCHOR = (30.10, 31.40)
RWY = 116.5          # the HECA 05C-end class: the backfill value
STATION_Z = 99.05    # what the solve published for the stations
LATTICE_Z = 98.6
SPINE_Z = 97.2


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def _fixture():
    layout = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
    layout.canonical_points = CanonicalPointRegistry(
        tol_m=SHARED_VERTEX_TOL_M)
    layout.shapes.append(BuiltShape(
        polygon=_rect(-1500.0, -22.0, 1500.0, 22.0),
        role="runway", ref="05/23",
        altitude_high=RWY, altitude_low=RWY))
    # an apron 600 m off the runway, with NO altitude on its ring (the
    # readonly re-read of an unsolved ring is not the class under test)
    layout.shapes.append(BuiltShape(
        polygon=_rect(400.0, 400.0, 700.0, 700.0), role="apron", ref="A1"))
    stations = [(450.0, 550.0), (510.0, 550.0), (570.0, 550.0)]
    lattice = [(500.0, 450.0), (550.0, 450.0), (600.0, 450.0)]
    spine = [(520.0, 650.0), (540.0, 650.0)]
    layout.apron_spine_presolve = [
        {"shape": layout.shapes[-1], "points": list(stations),
         "lines": [list(stations)]}]
    layout.apron_lattice_presolve = [
        {"shape": layout.shapes[-1], "points": list(lattice),
         "lines": [list(lattice)]}]
    layout.gap_fill_presolve = [
        {"spine": list(spine), "values": [SPINE_Z, None]}]
    # the solve's publication: the carriers, in ll, one alt per point.
    layout.apron_spine_station_emit = [
        ([layout.m_to_ll(x, y) for (x, y) in stations],
         [STATION_Z] * len(stations))]
    layout.apron_lattice_emit = [
        ([layout.m_to_ll(x, y) for (x, y) in lattice[:2]],
         [LATTICE_Z, LATTICE_Z + 0.2])]     # third lattice point UNVALUED
    # the solve interned every variable; a finished layout's registry
    # already holds the stations, so the readonly re-reads resolve them.
    SP._build_node_list(layout)
    return layout, stations, lattice, spine


def _seed(layout, gate):
    prev = os.environ.get(SP.SEED_CARRY_NONRING_ENV)
    if gate:
        os.environ[SP.SEED_CARRY_NONRING_ENV] = "1"
    else:
        os.environ.pop(SP.SEED_CARRY_NONRING_ENV, None)
    try:
        nodes, b2i = SP._build_node_list(layout)
        elev, is_hard, have = SP._seed_elevations(layout, nodes, b2i,
                                                  readonly=True)
    finally:
        if prev is None:
            os.environ.pop(SP.SEED_CARRY_NONRING_ENV, None)
        else:
            os.environ[SP.SEED_CARRY_NONRING_ENV] = prev
    cps = layout.canonical_points

    def at(x, y):
        return elev[b2i[cps.get(float(x), float(y))]]
    return at, elev, is_hard


def test_gate_off_carries_the_runway_corner_backfill():
    """(c) the standing (defective) read, so the fix's effect is
    measured against it and not assumed."""
    layout, stations, lattice, spine = _fixture()
    at, _, _ = _seed(layout, gate=False)
    for (x, y) in stations + lattice + spine:
        assert at(x, y) == pytest.approx(RWY), (x, y)


def test_gate_on_a_station_carries_its_solved_value():
    """(a) the R1.3 headline class: a station's carried seed IS the
    value the solve emitted for it, never the runway corner."""
    layout, stations, lattice, spine = _fixture()
    at, _, is_hard = _seed(layout, gate=True)
    for (x, y) in stations:
        assert at(x, y) == pytest.approx(STATION_Z), (x, y)
    assert at(*lattice[0]) == pytest.approx(LATTICE_Z)
    assert at(*lattice[1]) == pytest.approx(LATTICE_Z + 0.2)
    assert at(*spine[0]) == pytest.approx(SPINE_Z)
    # the runway is untouched: hard, at its own value
    assert at(-1500.0, -22.0) == pytest.approx(RWY)
    counts = layout._seed_carry_nonring_counts
    assert counts["station"] == 3 and counts["lattice"] == 2
    assert counts["gap_spine"] == 1


def test_gate_on_an_unvalued_node_still_backfills_and_is_reported():
    """(b) the backfill remains ONLY for nodes the solve never valued,
    and the census names them by class."""
    layout, stations, lattice, spine = _fixture()
    at, _, _ = _seed(layout, gate=True)
    assert at(*lattice[2]) == pytest.approx(RWY)      # no carrier alt
    assert at(*spine[1]) == pytest.approx(RWY)        # value None
    os.environ[SP.SEED_CARRY_NONRING_ENV] = "1"
    try:
        census = SP.seed_branch_census(layout)
    finally:
        os.environ.pop(SP.SEED_CARRY_NONRING_ENV, None)
    c = census["classes"]
    assert c["station"]["branches"] == {"carrier_warm_start_station": 3}
    assert c["station"]["carrier"]["n_disagree"] == 0
    assert c["lattice"]["branches"] == {
        "carrier_warm_start_lattice": 2, "nearest_hard_backfill": 1}
    assert c["gap_spine"]["branches"] == {
        "carrier_warm_start_gap_spine": 1, "nearest_hard_backfill": 1}
    # the census restores the seeder's published attributes and gate
    assert "O4_SEED_BRANCH_ATTRIB" not in os.environ
    assert not hasattr(layout, "_seed_branch_attrib")


def test_census_off_gate_reports_the_defect_it_measures():
    layout, *_ = _fixture()
    census = SP.seed_branch_census(layout)
    c = census["classes"]
    assert c["station"]["branches"] == {"nearest_hard_backfill": 3}
    assert c["station"]["carrier"]["n_disagree"] == 3
    assert c["station"]["carrier"]["max_abs_diff_m"] == pytest.approx(
        RWY - STATION_Z, abs=1e-6)
