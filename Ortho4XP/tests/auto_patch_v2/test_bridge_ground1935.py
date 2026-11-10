"""Twin of ``airport/bridge_ground`` (issue #1935): the ground under a
mapped bridge is the ground BESIDE it.

Synthetic: a flat 40 m field, a highway bridge way (``bridge=yes``,
``width=8``) mapped along the y axis from y = -100 to +100, and a DEM that
carries its deck (a ridge |x| <= 4.5 m standing ``deck`` over the field)."""
from __future__ import annotations

import types

import numpy as np

from auto_patch_v2.airport import bridge_ground as BG
from auto_patch_v2.law import load_default
from auto_patch_v2.model.airport import OsmWay

LAW = load_default()
BRIDGE = {"highway": "primary", "bridge": "yes", "width": "8"}


class _Dem:
    def __init__(self, deck=6.0, left=0.0, gap=None, extend=0.0):
        self.deck, self.left, self.gap, self.extend = deck, left, gap, extend

    def posting_m(self):
        return 1.0

    def z_many(self, xs, ys):
        xs, ys = np.asarray(xs, float), np.asarray(ys, float)
        z = np.where(xs > 4.5, 40.0 + self.left, 40.0)
        ridge = (np.abs(xs) <= 4.5) & (ys >= -100.0) & (ys <= 100.0 + self.extend)
        if self.gap is not None:
            ridge &= ~((ys > self.gap[0]) & (ys < self.gap[1]))
        return np.where(ridge, 40.0 + self.deck, z)

    def z(self, x, y):
        return float(self.z_many([x], [y])[0])


def _airport(dem, *extra):
    way = OsmWay(-7, "small_roads", ((0.0, -100.0), (0.0, 100.0)), False, dict(BRIDGE))
    return types.SimpleNamespace(dem=dem, osm_ways=(way, *extra))


def _lower(dem, xs, ys, *extra, airside=frozenset()):
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    runs = BG.bridge_runs(_airport(dem, *extra), LAW)
    z, rep = BG.bridge_ground(runs, xs, ys, dem.z_many(xs, ys), airside)
    return runs, z, rep


def test_a_deck_the_dem_carries_reads_the_ground_beside_it():
    runs, z, rep = _lower(_Dem(6.0), [0.0, 2.0, -3.0], [0.0, 50.0, -60.0])
    assert len(runs) == 1 and rep.ways == [-7]
    assert np.allclose(z, 40.0) and rep.vertices_lowered == 3
    assert abs(rep.max_lower_m - 6.0) < 1e-6
    # the road profile's sampler reads the same ground
    s = BG.bridge_sampler(_Dem(6.0).z_many, runs)
    assert np.allclose(s(np.array([0.0]), np.array([0.0])), 40.0)


def test_bare_earth_under_the_clearance_is_byte_identical():
    dem = _Dem(3.0)                                # a 3 m rise is no deck
    xs, ys = np.array([0.0, 1.0]), np.array([0.0, 10.0])
    runs, z, rep = _lower(dem, xs, ys)
    assert not runs and rep.vertices_lowered == 0
    assert z.tobytes() == dem.z_many(xs, ys).tobytes()
    sample = dem.z_many
    assert BG.bridge_sampler(sample, runs) is sample


def test_an_airside_vertex_keeps_its_dem_and_is_counted():
    _runs, z, rep = _lower(_Dem(6.0), [0.0, 0.0], [0.0, 20.0], airside={0})
    assert z[0] == 46.0 and z[1] == 40.0
    assert rep.airside_inside == 1 and rep.vertices_lowered == 1


def test_lower_only_and_a_side_above_the_deck_is_no_witness():
    # a ditch under the deck (38 m) is lower than the ground beside: kept
    runs = BG.bridge_runs(_airport(_Dem(6.0)), LAW)
    z, _rep = BG.bridge_ground(runs, np.array([0.0]), np.array([0.0]), np.array([38.0]),
                               frozenset())
    assert z[0] == 38.0
    # one side standing above the deck: the deck is not over the ground there
    runs, z, _rep = _lower(_Dem(6.0, left=7.0), [0.0], [0.0])
    assert not runs and z[0] == 46.0


def test_a_gap_in_the_run_is_not_bridged():
    # the DEM sees no deck over y in (-20, 20): two runs, and a point in
    # the gap standing over the ground beside keeps its height (no
    # interpolation spans the gap)
    runs = BG.bridge_runs(_airport(_Dem(6.0, gap=(-20.0, 20.0))), LAW)
    assert len(runs) == 2
    z, rep = BG.bridge_ground(runs, np.array([0.0, 0.0, 0.0]), np.array([0.0, -60.0, 60.0]),
                              np.array([45.0, 46.0, 46.0]), frozenset())
    assert z[0] == 45.0 and np.allclose(z[1:], 40.0) and rep.vertices_lowered == 2


def test_the_road_a_bridge_leaves_from_reads_the_ground_beside_it():
    # EFHK's terminal kerb (#1935): a road that ends where a bridge leaves
    # it, inside that bridge's ribbon, is the bridge's ground (DEVIATION
    # from the round-3 spec's approach exclusion, awaiting its ruling)
    kerb = OsmWay(-8, "small_roads", ((0.0, 100.0), (0.0, 200.0)), False,
                  {"highway": "primary", "width": "8"})
    runs, z, _rep = _lower(_Dem(6.0, extend=40.0), [0.0, 0.0], [99.0, 0.0], kerb)
    assert runs and z[0] == 40.0 and z[1] == 40.0
