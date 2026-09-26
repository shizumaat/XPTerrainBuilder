"""#28 / spec ``pack-read-once-fast-spec.md`` §B.3 (slice S3): the three
bulk-GEOS sites return EXACTLY what their scalar loops returned.

The scalar loops are kept HERE as the references (``_ref_*``), verbatim
from the shipped code they replaced.  Two populations:

* synthetic twins that always run (U-kerbs, a portal ring, a skirt at the
  tolerance, stations exactly AT ``probe_m``);
* the REAL inputs harvested off the registered TNCM capture (lane
  ``packperf``: ``read_objects -> partition_pack -> planar build`` with the
  three helpers wrapped, ``frames.py list TNCM``), compared ordered-output
  identical.  The harvest is a data-repo artefact; the test SKIPS BY NAME
  when it is absent (``O4_PACKBULK_HARVEST`` overrides the path).
"""
from __future__ import annotations

import gzip
import math
import os
import pickle
from pathlib import Path

import numpy as np
import pytest
import shapely
from shapely.geometry import LineString, Point, Polygon, box

from auto_patch_v2.airport import bulk_geos, object_cut, skirt, wall_geometry


# ── the scalar references (the shipped loops, verbatim) ─────────────────

def _ref_straight_runs(segs, parallel_deg, t_max):
    from auto_patch_v2.airport import frame_entry as _fe
    clusters = []
    for k, (seg, _t) in enumerate(segs):
        b = wall_geometry._bearing(seg)
        for cl in clusters:
            if wall_geometry._angle_diff(b, cl[0]) <= parallel_deg:
                cl[1].append(k)
                break
        else:
            clusters.append((b, [k]))
    runs = []
    for _b, idx in clusters:
        merged = _fe.union([segs[k][0].buffer(t_max / 2.0, cap_style="flat",
                                              **wall_geometry._MITRE) for k in idx],
                           "wall_geometry.runs")
        for part in shapely.get_parts(merged):
            members = [k for k in idx if segs[k][0].intersects(part)]
            if members:
                runs.append(members)
    return runs


def _ref_open_edges(ring, wall, probe_m):
    n = len(ring)
    opens = []
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        e = LineString([a, b])
        k = max(2, int(e.length / 2.0))
        hit = sum(1 for j in range(k + 1)
                  if wall.distance(e.interpolate(j / k, normalized=True)) <= probe_m)
        if hit / (k + 1) < 0.5:
            opens.append(i)
    return opens


def _ref_rim_hits(below, exteriors, tol):
    return [any(e.distance(g) <= tol for e in exteriors) for g in below]


# ── synthetic twins ──────────────────────────────────────────────────────

def _u_kerb(ox=0.0, oy=0.0, w=6.0, d=4.0, t=0.2):
    """The faces of a welded U-shaped kerb: two side walls and an end wall,
    each with its two faces (plan segments)."""
    segs = []
    for x in (ox, ox + t, ox + w - t, ox + w):
        segs.append(LineString([(x, oy), (x, oy + d)]))
    for y in (oy + d - t, oy + d):
        segs.append(LineString([(ox, y), (ox + w, y)]))
    return [(s, k) for k, s in enumerate(segs)]


@pytest.mark.parametrize("n", [1, 2, 5])
def test_straight_runs_equal_on_u_kerbs(n):
    segs = []
    for i in range(n):
        segs += _u_kerb(ox=15.0 * i, oy=3.0 * i)
    segs = [(s, k) for k, (s, _k) in enumerate(segs)]
    got = wall_geometry._straight_runs(segs, 10.0, 0.5)
    assert got == _ref_straight_runs(segs, 10.0, 0.5)
    assert len(got) >= 2 * n              # the side walls and the end wall apart


def test_straight_runs_equal_on_random_segments():
    rng = np.random.default_rng(28)
    for _trial in range(20):
        pts = rng.uniform(0, 60, size=(int(rng.integers(2, 80)), 2))
        ang = rng.choice([0.0, 0.3, 1.57, 2.9], size=len(pts))
        ln = rng.uniform(0.5, 12.0, size=len(pts))
        segs = [(LineString([(x, y), (x + l * math.cos(a), y + l * math.sin(a))]), k)
                for k, ((x, y), a, l) in enumerate(zip(pts, ang, ln))]
        assert wall_geometry._straight_runs(segs, 8.0, 0.6) == \
            _ref_straight_runs(segs, 8.0, 0.6)


def test_open_edges_equal_on_a_portal_ring():
    ring = [(0.0, 0.0), (40.0, 0.0), (40.0, 8.0), (0.0, 8.0)]
    # walls on three sides, the east end (a portal) open
    wall = shapely.union_all([LineString([(0, -0.3), (40, -0.3)]),
                              LineString([(0, 8.3), (40, 8.3)]),
                              LineString([(-0.3, 0), (-0.3, 8)])])
    for probe in (0.1, 0.3, 0.30000000000000004, 0.5, 1.0):
        assert object_cut._open_edges(ring, wall, probe) == _ref_open_edges(ring, wall, probe)
    assert object_cut._open_edges(ring, wall, 0.5) == [1]


def test_open_edges_station_exactly_at_the_tolerance():
    """A station whose distance to the wall IS ``probe_m`` reads as the
    scalar loop read it — the bracket hands it to the scalar distance."""
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    wall = LineString([(0.0, -0.25), (10.0, -0.25)])
    for probe in (0.25, np.nextafter(0.25, 0.0), np.nextafter(0.25, 1.0)):
        assert object_cut._open_edges(ring, wall, float(probe)) == \
            _ref_open_edges(ring, wall, float(probe))


def test_rim_hits_equal_including_at_tolerance():
    fp = box(0, 0, 20, 10)
    ext = skirt._exteriors(fp)
    below = [box(0.5, 0.5, 3, 3), box(5, 5, 6, 6), box(19.0, 2, 19.75, 3),
             Polygon([(0, -1), (1, -1), (1, -0.5)]), box(8, 4.5, 9, 5.5)]
    for tol in (0.25, 0.5, 1.0, 4.0):
        assert skirt._rim_hits(below, ext, tol) == _ref_rim_hits(below, ext, tol)
    assert skirt._rim_hits([], ext, 0.5) == []


def test_within_distance_leaves_the_geometry_unprepared():
    g = LineString([(0, 0), (10, 0)])
    assert not shapely.is_prepared(g)
    got = bulk_geos.within_distance(g, [Point(1, 0.5), Point(1, 2.0)], 1.0)
    assert got.tolist() == [True, False]
    assert not shapely.is_prepared(g)


def test_intersecting_pairs_order():
    a = [box(0, 0, 1, 1), box(5, 5, 6, 6), box(0.5, 0.5, 5.5, 5.5)]
    b = [box(5.2, 5.2, 7, 7), box(-1, -1, 0.2, 0.2)]
    qi, ti = bulk_geos.intersecting_pairs(a, b)
    want = [(i, j) for j in range(len(b)) for i in range(len(a)) if a[i].intersects(b[j])]
    assert list(zip(qi.tolist(), ti.tolist())) == want


# ── the REAL inputs (registered TNCM capture harvest) ────────────────────

_HARVEST = Path(os.environ.get(
    "O4_PACKBULK_HARVEST",
    "/Users/noah/XPTerrainBuilderData/.harness/frames/packperf/harvest_TNCM.pkl.gz"))


@pytest.fixture(scope="module")
def harvest():
    if not _HARVEST.is_file():
        pytest.skip(f"real-input harvest absent: {_HARVEST} (lane packperf, "
                    "tools/harness/frames.py list TNCM)")
    with gzip.open(_HARVEST, "rb") as fh:
        return pickle.load(fh)


def test_real_straight_runs_identical(harvest):
    calls = harvest["straight_runs"]
    assert calls
    for segs_wkb, pd, tm, want in calls:
        segs = [(shapely.from_wkb(w), k) for w, k in segs_wkb]
        assert wall_geometry._straight_runs(segs, pd, tm) == want


def test_real_open_edges_identical(harvest):
    calls = harvest["open_edges"]
    if not calls:
        pytest.skip("the TNCM capture reads no shell (no _ring_ends call)")
    for ring, wall_wkb, pm, want in calls:
        assert object_cut._open_edges(ring, shapely.from_wkb(wall_wkb), pm) == want


def test_real_rim_hits_identical(harvest):
    calls = harvest["rim_hits"]
    if not calls:
        pytest.skip("the TNCM capture reads no below-zero piece (no _rim_hits call)")
    for below_wkb, ext_wkb, tol, want in calls:
        got = skirt._rim_hits([shapely.from_wkb(w) for w in below_wkb],
                              [shapely.from_wkb(w) for w in ext_wkb], tol)
        assert got == want
