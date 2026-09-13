"""§39 (i) THE VECTOR MAP IS THE LAST SITE (owner RULINGS 2026-09-13bu).

KCLT: patch node −23317 of ``bank:51`` entered the vector map as n11592;
the tile's OSM WATER edge passed 2.7913 mm away; ``insert_edge``'s split
test is DIMENSIONLESS (``are_encroached``'s ``eps = 1e-8``), so it read
the crossing as interior, split the water edge and minted n849288 — a
2.7913 mm constrained WATER segment, and 481,602 triangles under 0.1 m^2
off it (723,015 at the second site, 0.2401 mm).

Two cures, twinned here: the split test becomes METRIC, and whatever
still lands inside the weld radius after ``snap_to_grid`` is WELDED onto
the SENIOR node (water / tile border first — "water is a datum").
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import O4_Geo_Utils as GEO                                    # noqa: E402
from O4_Vector_Utils import Vector_Map                        # noqa: E402

LAT = 35
M_LAT = GEO.lat_to_m
M_LON = GEO.lon_to_m(LAT + 0.5)


def _dlat(m):
    return m / M_LAT


def _dlon(m):
    return m / M_LON


def _map():
    vm = Vector_Map()
    vm.weld_spacing_m = 0.010
    return vm


def _insert(vm, p, q, marker):
    vm.insert_way(numpy.array([[p[0], p[1], 0.0], [q[0], q[1], 0.0]]),
                  marker, check=True)


def _shortest_segment_m(vm):
    out = []
    for (a, b) in vm.edges_dico.values():
        (xa, ya), (xb, yb) = vm.nodes_dico[a], vm.nodes_dico[b]
        out.append(math.hypot((xb - xa) * M_LON, (yb - ya) * M_LAT))
    return min(out) if out else None


def test_a_crossing_a_hair_from_an_endpoint_mints_no_node():
    """The KCLT cure at ``insert_edge``: the water edge crosses the patch
    node 2.7913 mm away, so the crossing IS that node."""
    vm = _map()
    # the patch chain, whose middle node is the one the water passes
    a = (0.0692, 0.2181530)
    b = (a[0] + _dlon(20.0), a[1])
    _insert(vm, a, b, "INTERP_ALT")
    n_before = len(vm.nodes_dico)
    # a water edge crossing 2.7913 mm from ``b``
    off = _dlon(0.0027913)
    _insert(vm, (b[0] - off, b[1] - _dlat(10.0)),
            (b[0] - off, b[1] + _dlat(10.0)), "WATER")
    assert len(vm.nodes_dico) == n_before + 2, (
        "the crossing must reuse the patch node, not mint a third")
    assert _shortest_segment_m(vm) > 0.01, (
        f"a {_shortest_segment_m(vm) * 1000:.4f} mm constrained segment "
        f"survived — that is KCLT's 481,602-sliver cascade")


def test_a_genuine_interior_crossing_still_splits():
    """The metric test narrows the split; it must not abolish it."""
    vm = _map()
    a = (0.0692, 0.2181530)
    b = (a[0] + _dlon(20.0), a[1])
    _insert(vm, a, b, "INTERP_ALT")
    n_before = len(vm.nodes_dico)
    mid = (a[0] + _dlon(10.0), a[1])
    _insert(vm, (mid[0], mid[1] - _dlat(10.0)), (mid[0], mid[1] + _dlat(10.0)),
            "WATER")
    assert len(vm.nodes_dico) == n_before + 3, (
        "a crossing in the true interior still mints its node")


def test_the_weld_moves_the_junior_node_onto_the_water():
    """"Water is a datum": the bank node welds onto the shore, never the
    shore onto the bank."""
    vm = _map()
    water_a = (0.0692, 0.2181530)
    water_b = (water_a[0] + _dlon(20.0), water_a[1])
    _insert(vm, water_a, water_b, "WATER")
    bank = (water_a[0] + _dlon(0.003), water_a[1] + _dlat(0.003))
    _insert(vm, bank, (bank[0] + _dlon(20.0), bank[1] + _dlat(20.0)),
            "INTERP_ALT")
    report = {}
    assert vm.weld_hairlines(0.010, LAT, report=report) == 1
    assert report["welded"] == 1
    coords = set(vm.nodes_dico.values())
    assert water_a in coords, "the SENIOR (water) node kept its coordinate"
    assert bank not in coords, "the junior (bank) node was welded away"


def test_the_weld_keeps_a_boundary_node_fixed():
    """Triangle4XP's ``-Y`` may not move an outer-boundary node at all, so
    it outranks even water."""
    vm = _map()
    border = (0.0, 0.20)
    _insert(vm, border, (0.0, 0.20 + _dlat(20.0)), "WATER")
    other = (border[0] + _dlon(0.004), border[1])
    _insert(vm, other, (other[0] + _dlon(20.0), other[1]), "WATER")
    vm.weld_hairlines(0.010, LAT)
    assert border in set(vm.nodes_dico.values())
    assert other not in set(vm.nodes_dico.values())


def test_the_weld_drops_the_degenerate_segment():
    vm = _map()
    a = (0.0692, 0.2181530)
    b = (a[0] + _dlon(0.002), a[1])
    _insert(vm, a, b, "WATER")
    _insert(vm, b, (b[0] + _dlon(20.0), b[1] + _dlat(5.0)), "WATER")
    before = len(vm.edges_dico)
    vm.weld_hairlines(0.010, LAT)
    assert len(vm.edges_dico) == before - 1
    assert _shortest_segment_m(vm) > 0.01


def test_the_weld_leaves_ordinary_geometry_alone():
    """KCLT carries 2,245 constrained segments under 0.5 m and only 28
    under 10 mm: the radius is the DEGENERATE floor, not the spacing."""
    vm = _map()
    a = (0.0692, 0.2181530)
    _insert(vm, a, (a[0] + _dlon(20.0), a[1]), "WATER")
    near = (a[0] + _dlon(0.30), a[1] + _dlat(0.30))
    _insert(vm, near, (near[0] + _dlon(20.0), near[1]), "INTERP_ALT")
    n_before = len(vm.nodes_dico)
    assert vm.weld_hairlines(0.010, LAT) == 0
    assert len(vm.nodes_dico) == n_before
