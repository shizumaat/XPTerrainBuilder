"""Twins for §30 (4) THE CLUSTER PAD (owner RULINGS 2026-09-13bj item 1;
lane ``v2clusterpad``).

Owner, on KCLT 1.0.327: *"These large complex structures have to be
seated as a unit.  As long as it remains feasible with grade laws and
taxiways, etc. it's acceptable to flatten large apron areas around big
terminals if needed to accommodate a large terminal cluster."*

Two things the design surface owes the object stage's §16g:

1. ONE PLANE over the whole cluster — the emitted ``building`` faces its
   footprint union stands on are priced as ONE pad (one ``pad_flats``
   plate, one hard 1 % ceiling, one frontage fit), so a unit seated on
   "its pad" has one level to seat on however many faces the OSM drew.
2. THE APRON WITHIN THE REACH takes that plane, and the TAXIWAY does not:
   the reach's population excludes every vertex of a taxi- or
   runway-family face outright.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.cluster_pad import (CLUSTER_REACH_RULING,
                                                   cluster_apron_faces,
                                                   cluster_apron_level,
                                                   cluster_pad_faces,
                                                   cluster_reach_m,
                                                   plane_groups)
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design

RUN_LEN = 1600.0
HALF_W = 22.5
Y0, Y1 = 140.0, 300.0
#: the two pads of the "terminal", 40 m apart in x with the apron between
PAD_A = (-120.0, 200.0, -20.0, 280.0)
PAD_B = (20.0, 200.0, 120.0, 280.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    """Ground that FALLS 4 m from one pad to the other, so one plane over
    both is a thing the solve has to make rather than find."""

    provenance = {"synthetic": "tilt"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 4.0 * max(0.0, min(1.0, (x + 120.0) / 240.0))

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _airport(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, _Dem(), law.ruleset_key)


class _Cluster:
    """What ``planar/cluster.py`` puts on ``Airport.clusters``: the id and
    the PART BOXES of the footprint union, in lat/lon."""

    def __init__(self, airport, rects):
        _to_xy, to_ll = airport.frame.transformers()
        self.id = "unit:1#0"
        self.unit = "unit:1"
        self.members = ("objects/wall.obj", "objects/roof.obj")
        boxes = []
        for x0, y0, x1, y1 in rects:
            la0, lo0 = to_ll(x0, y0)
            la1, lo1 = to_ll(x1, y1)
            boxes.append((min(la0, la1), min(lo0, lo1),
                          max(la0, la1), max(lo0, lo1)))
        self.boxes = tuple(boxes)
        self.area_m2 = 20000.0
        self.hull = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                     max(b[2] for b in boxes), max(b[3] for b in boxes))


def _cells():
    """Two building pads inside one apron, and a TAXIWAY along the apron's
    north edge — the reach must stop at it."""
    return [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W,
                                             RUN_LEN / 2, HALF_W),
                 (), 3, "D", "airside", "runway", {}),
            Cell(1, "apron", "apronA",
                 _rect(-300.0, Y0, 300.0, Y1),
                 (_rect(*PAD_A), _rect(*PAD_B)),
                 None, None, "airside", "apron", {}),
            Cell(2, "building", "padA", _rect(*PAD_A), (), None, None,
                 "airside", "pad", {}),
            Cell(3, "building", "padB", _rect(*PAD_B), (), None, None,
                 "airside", "pad", {}),
            Cell(4, "primary_parallel", "twyA",
                 _rect(-300.0, 60.0, 300.0, 100.0), (), 3, "D",
                 "airside", "taxiway", {})]


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _arm(law, clustered: bool):
    airport = _airport(law)
    if clustered:
        airport = _dc.replace(airport,
                              clusters=(_Cluster(airport, (PAD_A, PAD_B)),))
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    cs, counts, _w = generate(pm, law, airport)
    sol, _rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.status
    return airport, pm, np.asarray(sol.z, float), counts


def _poly(pm, ref):
    from shapely.geometry import Polygon
    f = next(q for q in pm.faces.values() if q.ref == ref)
    return Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)])


def _pt(pm, v):
    from shapely.geometry import Point
    return Point(*pm.vertices[v].xy)


def _verts(pm, ref):
    f = next(q for q in pm.faces.values() if q.ref == ref)
    out = set(pm.ring_vertices(f.ring))
    for h in (f.holes or ()):
        out |= set(pm.ring_vertices(h))
    return out


def test_30_4_the_law_key_and_the_ruling_head_are_data(law):
    """The reach is a law value with ONE derivation site, and its ruling
    head is in NEITHER the pad-plane family nor the hard set — the row is
    a target at the law's weight, which is what makes the apron yield to
    its own caps and to the taxiways (the owner's feasibility clause)."""
    from auto_patch_v2.solve.design import (cluster_reach_rulings,
                                            hard_rulings, pad_flat_rulings)
    # RULINGS 2026-09-13ce: the reach ships DISARMED (0.0) until the cluster
    # pad MERGE does the work (round 4); the design value is 60.0.
    assert cluster_reach_m(law) == 0.0
    assert CLUSTER_REACH_RULING not in pad_flat_rulings(law)
    assert CLUSTER_REACH_RULING not in hard_rulings(law)
    # §30 (4) (13cc (ii)): the reach is priced at the APRON TREND's own
    # design-target weight, strictly BELOW the law's, so every taxi row
    # outranks it
    assert CLUSTER_REACH_RULING in cluster_reach_rulings(law)
    d = law.tables.emit.design
    assert d.apron_trend < d.law


def test_30_4_a_cluster_is_one_plane_over_every_pad_it_stands_on(law):
    """(1): the cluster's two ``building`` faces are ONE priced group, and
    the solved surface puts them at ONE level though the DEM falls 4 m
    between them.  Without the cluster they are two planes."""
    a0, pm0, z0, _c0 = _arm(law, False)
    a1, pm1, z1, _c1 = _arm(law, True)
    groups0 = plane_groups(pm0, law, a0)
    groups1 = plane_groups(pm1, law, a1)
    assert {r for _f, r, _g, _q in groups0 if r.startswith("cluster:")} == set()
    one = [q for q in groups1 if q[1].startswith("cluster:")]
    assert len(one) == 1 and len(one[0][3]) == 2, groups1
    assert cluster_pad_faces(pm1, law, a1) != {}

    def level(pm, z, ref):
        return float(np.mean(z[sorted(_verts(pm, ref))]))

    apart = abs(level(pm0, z0, "padA") - level(pm0, z0, "padB"))
    together = abs(level(pm1, z1, "padA") - level(pm1, z1, "padB"))
    assert together < apart and together <= 0.30, (apart, together)


def _with_reach(law, reach_m):
    """The reach re-armed for a twin (RULINGS 2026-09-13ce ships it at 0.0):
    the ONE derivation site is ``cluster_pad.cluster_reach_m``; the twin
    patches that reader rather than the frozen law tables."""
    import unittest.mock as _mock
    from auto_patch_v2.constraints import cluster_pad as _cp
    return _mock.patch.object(_cp, "cluster_reach_m", lambda _law: reach_m)


def test_30_4_the_reach_flattens_the_apron_and_stops_at_the_taxiway(law):
    """DISARMED on main (RULINGS 2026-09-13ce): the reach is 0.0 by law value
    until the cluster pad merge does the work; this twin arms it locally.

    (2): the apron vertices within ``cluster_apron_reach_m`` take the
    cluster's plane; the TAXIWAY family's own vertices are not in the
    population at all and are not moved."""
    with _with_reach(law, 60.0):
        airport, pm, z, counts = _arm(law, True)
        got = cluster_apron_faces(pm, law, airport)
        # the rows are ONE-WAY with the APRON as the follower
        rows = cluster_apron_level(pm, law, airport)
    assert got and sum(len(v) for v in got.values()) > 0
    taxi = _verts(pm, "twyA")
    assert not (set().union(*got.values()) & taxi)
    assert counts.get("cluster_apron_level", 0) > 0
    assert rows and all(r.follows for r in rows)
    # and the apron in the reach came out at the pads' level
    pad = float(np.mean(z[sorted(_verts(pm, "padA") | _verts(pm, "padB"))]))
    near = sorted(set().union(*got.values()))
    assert abs(float(np.mean(z[near])) - pad) <= 0.30

    # NO TAXI VERTEX IS EVER A FOLLOWER of a reach row — that is what
    # "the reach stops at any taxiway band" is, and it is exact.
    assert not (taxi & {v for r in rows for v in (r.follows or ())})
    # ... an apron vertex a taxi-family NO-STEP row couples to a taxi
    # vertex is struck too (13cc (i)): the reach stops ONE APRON CELL
    # short of any taxi face, not merely at the band
    from auto_patch_v2.constraints.no_step import no_step_edges
    pop = set().union(*got.values())
    for a, b, _c, _d in no_step_edges(pm, law, airport):
        assert not (a in taxi and b in pop), (a, b)
        assert not (b in taxi and a in pop), (a, b)
    # ... and an apron vertex nearer a taxi- or runway-family face than
    # the pad is not in the population either: the band's CATCHMENT is
    # the boundary, which is what "the reach stops at a taxiway band"
    # means for a vertex the band does not itself own.
    tpoly = _poly(pm, "twyA")
    upad = _poly(pm, "padA").union(_poly(pm, "padB"))
    for v in set().union(*got.values()):
        pt = _pt(pm, v)
        assert tpoly.distance(pt) >= upad.distance(pt), pm.vertices[v].key
    # WHAT THE TAXIWAY ITSELF DOES is the joint solve's arbitration and
    # is NOT asserted here: this fixture's taxi face carries no datum of
    # its own and swings metres between arms, which measures the fixture
    # and not the law.  The airport bar is KCLT's, in the MEASURED block.


def test_30_4_no_cluster_is_the_identity(law):
    """An airport with no cluster — CYXY's class — mints no reach row and
    prices every pad exactly as before."""
    airport, pm, _z, counts = _arm(law, False)
    assert cluster_pad_faces(pm, law, airport) == {}
    assert cluster_apron_faces(pm, law, airport) == {}
    assert cluster_apron_level(pm, law, airport) == []
    assert counts.get("cluster_apron_level", 0) == 0


def test_30_4_the_cluster_pads_are_published_in_the_sidecar(law):
    """The bar: the cluster pad is PUBLISHED (``cluster_pads``) so the
    object stage and the report read the plane the solve made, and it is
    read off the SAME derivations the rows were priced from."""
    from auto_patch_v2.pipeline.publication import cluster_pads
    airport, pm, z, _c = _arm(law, True)
    got = cluster_pads(pm, law, airport, z)
    assert len(got) == 1
    rec = got[0]
    assert sorted(rec["pads"]) == ["padA", "padB"]
    assert rec["level"] is not None and rec["rim_vertices"] > 0
    assert rec["apron_vertices_in_reach"] >= rec["apron_vertices_at_the_plane"]
    # an airport with no cluster publishes nothing
    a0, pm0, z0, _c0 = _arm(law, False)
    assert cluster_pads(pm0, law, a0, z0) == []
