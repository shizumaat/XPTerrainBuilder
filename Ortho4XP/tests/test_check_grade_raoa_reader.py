"""The RAOA reader prices profiles ALONG the approach (ICAO Annex 14
§3.8.4): a hop between two strip vertices whose lateral separation exceeds
their along-axis separation is a cross-width neighbour, not a profile
station.  Adjudicated 2026-09-04 (auto-patch-v2 M3a): every over-cap
triple the reader had minted at CYXY (28/28) and SPLP (6/6) was such a
hop — laterally separated vertices centimetres apart in station priced
as one profile; zero along-approach violations.

Two synthetic strips inside a code-4 ICAO RAOA rectangle, both with the
same lawful 1 % profile along the approach and a 0.5 m lateral relief:
the OLD reading (sorted by station, no lateral test) reports the
zig-zag; the reader now reports nothing there and still reports a REAL
along-approach kink."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools" / "harness"))
sys.path.insert(0, str(ROOT / "src"))

cg = pytest.importorskip("check_grade")


def _way(wid, role, pts, elevs, tags=None):
    nids = [f"{wid}_{k}" for k in range(len(pts))]
    return (cg.Way(wid, role, "strip", "graded_strip", nids + [nids[0]],
                   elevs + [elevs[0]], tags or {}), dict(zip(nids, pts)))


def _runway(length=2400.0, width=45.0):
    """A runway ring along +x from the origin; ll_to_m is the identity
    (the reader takes points in metres)."""
    pts = [(0.0, -width / 2), (length, -width / 2), (length, width / 2),
           (0.0, width / 2)]
    elevs = [0.0, 0.0, 0.0, 0.0]
    w, nodes = _way("rwy", "runway", pts, elevs, {"o4_single_poly": "1"})
    return w, nodes


def _strip(name, stations, lateral, z_of):
    """A thin ring: the line at ``lateral`` and its return 3 m across
    with stations shifted by half a spacing (so no two ring vertices
    share a station and the reader walks 10 m hops along the ring)."""
    back = [s + 10.0 for s in stations]
    pts = [(s, lateral) for s in stations] + [(s, lateral + 3.0) for s in reversed(back)]
    elevs = [z_of(s) for s in stations] + [z_of(s) for s in reversed(back)]
    return _way(name, "graded_strip", pts, elevs)


def _run(ways, nodes):
    cg._ACTIVE_RULESET = "icao"
    return cg._check_raoa_rate(ways, nodes, lambda lat, lon: (lat, lon))


@pytest.mark.skipif(cg._raoa_footprint_ring is None, reason="grade_law absent")
def test_laterally_separated_vertices_are_not_a_profile():
    rw, nodes = _runway()
    ways = [rw]
    # stations before threshold 02 (x <= 0), inside the 300 x 120 m RAOA:
    # two strips 40 m apart laterally, both a lawful 1 % plane along x,
    # offset 0.5 m from each other — station-interleaved by 0.2 m
    st_a = [-280.0 + 20.0 * k for k in range(14)]
    st_b = [s + 0.2 for s in st_a]
    # ONE ring carrying both lines (v1's zone rings do): sorted by station
    # the walk alternates lines every 0.2 m — the old reading priced the
    # 0.5 m lateral relief as a 250 % grade change per 0.2 m
    both_pts = [(s, -55.0) for s in st_a] + [(s, -15.0) for s in reversed(st_b)]
    both_z = [0.01 * s for s in st_a] + [0.01 * s + 0.5 for s in reversed(st_b)]
    wc, nc = _way("sc", "graded_strip", both_pts, both_z)
    ways.append(wc)
    nodes.update(nc)
    rows, n_st, n_ways = _run(ways, nodes)
    assert n_st > 0
    assert rows == [], [(r.grade_pct, r.distance_m) for r in rows[:5]]


@pytest.mark.skipif(cg._raoa_footprint_ring is None, reason="grade_law absent")
def test_a_real_along_approach_kink_is_still_read():
    rw, nodes = _runway()
    st = [-280.0 + 20.0 * k for k in range(14)]
    # 2 % then -2 % at station -140: a 4 % change over 10 m (cap 2 % / 30 m)
    wa, na = _strip("sa", st, -30.0,
                    lambda s: 0.02 * s if s <= -140.0 else -0.02 * s - 5.6)
    nodes.update(na)
    rows, _n, _w = _run([rw, wa], nodes)
    assert rows and max(r.grade_pct for r in rows) > 1.0
