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
PAD_B = (-20.0, 200.0, 80.0, 280.0)
#: §30 (4) (5): a pad the cluster's footprint union touches by a BOX
#: artefact but that stands far from every member — KCLT's `building91`,
#: 65.81 m from the terminal — YIELDS and keeps its own plane
PAD_FAR = (170.0, 200.0, 210.0, 240.0)


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
    """What ``planar/cluster.py`` puts on ``Airport.clusters``: the id, the
    PART BOXES of the footprint union, and — since §16g (7) (1) / (10) —
    the true footprint RINGS, which are what every reader uses.  The two
    are given APART here on purpose: the boxes are the coarse superset
    that once reached a pad 66 m outside the terminal (13ci), the rings
    are the footprint, and (10) reads the rings."""

    def __init__(self, airport, rects, rings=None, floors=(0.0, 0.0),
                 cid="unit:1#0"):
        _to_xy, to_ll = airport.frame.transformers()
        self.id = cid
        self.unit = cid.split("#", 1)[0]
        self.members = ("objects/wall.obj", "objects/roof.obj")
        boxes = []
        for x0, y0, x1, y1 in rects:
            la0, lo0 = to_ll(x0, y0)
            la1, lo1 = to_ll(x1, y1)
            boxes.append((min(la0, la1), min(lo0, lo1),
                          max(la0, la1), max(lo0, lo1)))
        self.boxes = tuple(boxes)
        self.rings = tuple(
            tuple(to_ll(x, y) for x, y in _rect(*r))
            for r in (rings if rings is not None else rects))
        self.floors = tuple(floors)
        self.bodies = len(self.floors)
        self.footed = len(self.floors)
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
                 (_rect(*PAD_A), _rect(*PAD_B), _rect(*PAD_FAR)),
                 None, None, "airside", "apron", {}),
            Cell(2, "building", "padA", _rect(*PAD_A), (), None, None,
                 "airside", "pad", {}),
            Cell(3, "building", "padB", _rect(*PAD_B), (), None, None,
                 "airside", "pad", {}),
            Cell(5, "building", "padFar", _rect(*PAD_FAR), (), None, None,
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
        # the union covers the FAR pad too — the box artefact the gate
        # is for; padA and padB touch and are the cluster's real plane
        # the BOX union covers the FAR pad too — the artefact 13ci built
        # a whole yield gate for — while the true OUTLINE is padA+padB.
        # (10) reads the outline, so padFar is simply not in the cluster.
        airport = _dc.replace(airport, clusters=(
            _Cluster(airport, (PAD_A, PAD_B, PAD_FAR),
                     rings=(PAD_A, PAD_B)),))
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

    together = abs(level(pm1, z1, "padA") - level(pm1, z1, "padB"))
    assert together <= 0.30, together
    # the two faces are ONE priced group — which is the claim; on this
    # fixture they also TOUCH, so 09-01g's weld already holds them close
    # without the cluster and the levels alone do not discriminate (the
    # discriminating case is the airport's: KCLT's `building91`, and the
    # yielding twin below)
    assert len(one[0][2]) == len(_verts(pm1, "padA") | _verts(pm1, "padB"))


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


def test_30_4_a_cluster_is_priced_per_face_complete_plus_cross_links(law):
    """§30 (4) round 4 (RULINGS 13ce): each member face of a cluster keeps
    EXACTLY the pairs it would have alone, and the faces are tied by
    explicit CROSS-LINKS — never by handing ``_pairs`` the concatenated
    rim, which was measured inert (KCLT's 865 + 18 group priced 1,624
    pairs with 40 crossing while ``building91``'s own plate fell 153 →
    17, and the PAD-ONLY arm came out byte-identical to DISARM)."""
    import math
    import types

    from auto_patch_v2.constraints.cluster_pad import cluster_pairs
    from auto_patch_v2.constraints.pads import _pairs

    class _PM:
        def __init__(self, n_big, n_small):
            self.vertices = {}
            for i in range(n_big):
                a = 2 * math.pi * i / n_big
                self.vertices[i] = types.SimpleNamespace(
                    xy=(400 * math.cos(a), 300 * math.sin(a)))
            for j in range(n_small):
                a = 2 * math.pi * j / n_small
                self.vertices[1000 + j] = types.SimpleNamespace(
                    xy=(12 * math.cos(a) + 50, 10 * math.sin(a) + 20))

    big, small = list(range(865)), list(range(1000, 1018))
    prs, n_cross = cluster_pairs(_PM(865, 18), [big, small])
    sm = set(small)
    inside = [q for q in prs if q[0] in sm and q[1] in sm]
    cross = [q for q in prs if (q[0] in sm) != (q[1] in sm)]
    # the small face keeps its WHOLE plate — the round-3 defect, closed
    assert len(inside) == len(_pairs(small)) == 153
    # ... and every one of its vertices is tied to the senior rim
    assert len(cross) == n_cross == 18
    assert {v for q in cross for v in q if v in sm} == sm
    # the senior face keeps its own pairs unchanged
    assert len([q for q in prs if q[0] not in sm and q[1] not in sm]) \
        == len(_pairs(big))
    # one face is not a cluster and gets exactly its own pairs, no links
    solo, k = cluster_pairs(_PM(865, 18), [big])
    assert k == 0 and len(solo) == len(_pairs(big))


def test_30_4_two_clusters_on_one_pad_are_ONE_plane(law):
    """Measured, round 4: KCLT's two terminal rows BOTH stand on
    `building80`, and ``setdefault`` gave the face to whichever cluster
    came first — the other was left holding `building91`'s 18 vertices
    alone, a "cluster" of one face with nothing to cross-link to.  That,
    not the `_pairs` decimation, is why PAD-ONLY came out byte-identical
    to DISARM twice.  Clusters sharing a face are now UNIONED."""
    import dataclasses as _d

    airport = _airport(law)
    a = _Cluster(airport, (PAD_A, PAD_B))
    b = _Cluster(airport, (PAD_A,), cid="unit:2#0")
    airport = _d.replace(airport, clusters=(a, b))
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    groups = [q for q in plane_groups(pm, law, airport)
              if q[1].startswith("cluster:")]
    assert len(groups) == 1, groups          # ONE plane, not two partials
    assert len(groups[0][3]) == 2            # holding BOTH faces
    verts = set(groups[0][2])
    assert verts >= _verts(pm, "padA") and verts >= _verts(pm, "padB")


def test_16g_10_a_pad_the_OUTLINE_does_not_reach_is_not_the_clusters(law):
    """§16g (10) (2) (owner RULINGS 2026-09-14x, 14z) REPLACES 13ci's
    touching-component YIELD GATE.

    13ci's gate existed because the cluster's union was a union of PART
    BOXES, which reached KCLT's `building91` 65.81 m outside the
    terminal's footprint; the gate then kept the connected component
    holding the largest face, and MEASURED at HECA it kept ONE face of 22
    and ONE of 73 — it starved the merge it was guarding.  Under §16g (7)
    (1) the union is the true OUTLINE, so the far pad is not in the
    cluster to begin with: no gate, nothing yielded, and the pad keeps
    its own plane by simply never having been claimed.

    This fixture states it exactly: the cluster's BOXES cover padFar, its
    RINGS do not."""
    from auto_patch_v2.constraints.cluster_pad import YIELDED
    airport, pm, z, _c = _arm(law, True)
    faces = cluster_pad_faces(pm, law, airport)
    kept = {pm.faces[q].ref for v in faces.values() for q in v}
    assert kept == {"padA", "padB"}, kept
    # nothing YIELDS: the outline never reached padFar
    yielded = {pm.faces[q].ref for v in YIELDED.values() for q in v}
    assert yielded == set(), yielded
    # ... and the yielding pad is NOT dragged onto the cluster's level
    far = float(np.mean(z[sorted(_verts(pm, "padFar"))]))
    one = float(np.mean(z[sorted(_verts(pm, "padA") | _verts(pm, "padB"))]))
    assert abs(far - one) > 0.30, (far, one)


def test_16g_10_the_steps_between_touching_clusters_are_DECLARED(law):
    """§16g (8) AS NARROWED BY (10) (owner RULINGS 2026-09-14x): 14u's
    derived pads WITHIN a cluster are withdrawn — a touching body at a
    different authored floor is now a different CLUSTER with its own pad
    — and what is left is the STEP between two touching clusters' pads,
    a declared terrace joint (§23) and never a priced row."""
    import dataclasses as _d

    from auto_patch_v2.constraints.cluster_pad import (TOUCHING_STEPS,
                                                       cluster_offsets)
    airport = _airport(law)
    a = _Cluster(airport, (PAD_A,), floors=(0.0,), cid="unit:1#0")
    b = _Cluster(airport, (PAD_B,), floors=(3.0,), cid="unit:1#1")
    airport = _d.replace(airport, clusters=(a, b))
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    # it mints NO row — the step is the ground law's, not the pad's
    assert cluster_offsets(pm, law, airport) == {}
    assert TOUCHING_STEPS == {("unit:1#0", "unit:1#1"): 3.0}, TOUCHING_STEPS
    # ... and two clusters that do NOT touch declare no step
    far = _Cluster(airport, (PAD_FAR,), floors=(3.0,), cid="unit:1#1")
    cluster_offsets(pm, law, _d.replace(airport, clusters=(a, far)))
    assert TOUCHING_STEPS == {}


def test_16g_10_3_pad_cluster_mismatch_names_a_cluster_spanning_two_pads(law):
    """§16g (10) (3) (owner RULINGS 2026-09-14x): CRITICAL — "no
    building, or cluster can span multiple pads ... they should match
    exactly".

    The fixture's cluster is more than half of BOTH ``padA`` and
    ``padB``, which is exactly the shape the owner refuses: it is
    reported, named and placed.  A cluster that is one pad reports
    nothing, which is the bar."""
    import dataclasses as _d

    from auto_patch_v2.constraints.cluster_pad import pad_cluster_mismatch
    airport, pm, _z, _c = _arm(law, True)
    got = pad_cluster_mismatch(pm, law, airport)
    assert len(got) == 1, got
    assert got[0]["kind"] == "cluster_spans_pads"
    assert got[0]["ref"] == "unit:1#0"
    assert sorted(got[0]["others"]) == ["padA", "padB"]
    assert got[0]["lat"] is not None and got[0]["lon"] is not None

    # THE BAR: one pad per cluster reports nothing
    one = _dc.replace(airport, clusters=(
        _Cluster(airport, (PAD_A,), rings=(PAD_A,), cid="unit:1#0"),
        _Cluster(airport, (PAD_B,), rings=(PAD_B,), cid="unit:1#1")))
    assert pad_cluster_mismatch(pm, law, one) == []

    # ... and TWO clusters over the SAME ground are not two pads: the
    # GROUND FLOOR owns it (``geom.cluster_outlines`` rule 3, the answer
    # to HECA's 519 overlapping pairs), so the upper one mints no pad,
    # claims nothing, and there is no mismatch to report
    from auto_patch_v2.constraints.cluster_pad import cluster_polys
    stacked = _dc.replace(airport, clusters=(
        _Cluster(airport, (PAD_A,), rings=(PAD_A,), floors=(0.0,),
                 cid="unit:1#0"),
        _Cluster(airport, (PAD_A,), rings=(PAD_A,), floors=(4.0,),
                 cid="unit:2#0")))
    got = cluster_polys(stacked, 0.0, 0.5)
    assert [c.id for c, _g in got] == ["unit:1#0"], got
    assert pad_cluster_mismatch(pm, law, stacked) == []


def test_16g_10_2_a_cluster_with_no_OUTLINE_gets_no_cluster_pad(law):
    """§16g (10) (2): a plan written before §16g (7) (1)'s ring field
    carries no footprint outline, and a PART-BOX union is not a
    footprint — so such a cluster gets NO cluster pad at all and the
    airport keeps the pre-14x derivation.

    This is the KCLT control's own mechanism.  13ci measured what
    pricing a box union costs there (`building91`, a separate building
    65.81 m from the terminal, lifted 3.63 m and 2,406 taxi-family
    vertices moved, worst 2.07 m) and answered it with a gate; (10)
    answers it by never reading a box as a footprint.  The registered
    KCLT frame's plan carries no rings on any of its 355 clusters, so
    this path is exactly what that control exercises."""
    import dataclasses as _d

    from auto_patch_v2.constraints.cluster_pad import (NO_OUTLINE,
                                                       cluster_polys)
    airport = _airport(law)
    stale = _Cluster(airport, (PAD_A, PAD_B, PAD_FAR))
    stale.rings = ()                       # a pre-14o plan
    airport = _d.replace(airport, clusters=(stale,))
    pm, _st = build(airport, Classification(tuple(_cells()), (), {}, ()), law)
    assert cluster_polys(airport) == []
    assert NO_OUTLINE == ["unit:1#0"]
    assert cluster_pad_faces(pm, law, airport) == {}
    assert [q for q in plane_groups(pm, law, airport)
            if q[1].startswith("cluster:")] == []
