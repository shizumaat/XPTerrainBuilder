"""Twins for issue #150 (flat-pad spec v2 §3 / §7 A9: "any airside vertex
minted / deleted outside ``plateau_rings``" is a STOP).

1. THE PLATEAU MEETS THE APRON RING ONLY AT THE RING'S OWN COORDINATES: a
   stand zone whose disc crosses the apron/collar edge between two ring
   stations cuts its plateau WITHOUT minting a vertex on that edge — the
   pad's collar on the other side of it (the HECA ``building4/b*#collar``
   class) keeps every vertex it had, no face but the cut apron and its
   plateau gains or loses one, and the plateau keeps the run of frontage
   it reached (its crossings go to the station BEYOND, never collapse).
2. A SLIVER ZONE BORDERING TWO HOSTS BY THE SAME LENGTH dissolves into the
   same host whatever order the faces arrive in (HECA ``zone1#44``:
   ``dsf:objpav85`` vs ``route21`` flipped by a plateau cut 300 m away).
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Startup
from auto_patch_v2.model.planar import PLATEAU_MARK
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.overlay import Region, dissolve_sliver_zones

from test_flatpad128v3 import _airport, _cells  # noqa: E402

#: the gate stands 15 m inside the apron/pad edge (y = 180), so its 30 m
#: stand disc crosses that edge at x = ±25.98 — between the edge's ring
#: stations, which is where the pre-#150 cut minted a vertex on the pad
GATE_XY = (0.0, 165.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def arms(law):
    gate = Startup("G1", GATE_XY, 180.0, "gate")
    cl = Classification(tuple(_cells()), (), {}, ())
    pm1, _s1 = build(_airport(law, startups=(gate,)), cl, law)
    from auto_patch_v2.model.platform import PLATEAUS
    plateaus = dict(PLATEAUS)
    pm0, _s0 = build(_airport(law), cl, law)
    return pm1, pm0, plateaus


def _keys_by_ref(pm) -> dict[str, set]:
    out: dict[str, set] = {}
    for f in pm.faces.values():
        out.setdefault(str(f.ref), set()).update(
            pm.vertices[v].key for r in (f.ring, *f.holes)
            for v in pm.ring_vertices(r))
    return out


def test_the_disc_reaches_the_pad_edge(arms):
    pm1, _pm0, plateaus = arms
    assert "padA" in plateaus, "the fixture's stand cuts a plateau"
    faces = [f for f in pm1.faces.values() if PLATEAU_MARK in str(f.ref)]
    pad = _keys_by_ref(pm1)["padA"]              # the pad face fronts the apron
    ring = {pm1.vertices[v].key for f in faces for r in (f.ring, *f.holes)
            for v in pm1.ring_vertices(r)}
    assert len(ring & pad) >= 2, "the plateau runs along the pad edge (the crossing case)"


def test_the_pad_across_the_edge_keeps_its_identity(arms):
    pm1, pm0, _p = arms
    k1, k0 = _keys_by_ref(pm1), _keys_by_ref(pm0)
    c = "padA"
    assert k1[c] == k0[c], (
        "the plateau cut minted/deleted a vertex on the pad it fronts: "
        f"+{len(k1[c] - k0[c])} -{len(k0[c] - k1[c])}")
    # every face other than the cut apron and its plateau is untouched
    for ref, ks in k0.items():
        if ref == "apronA":
            continue
        assert k1.get(ref) == ks, ref


def test_the_cut_apron_ring_keeps_every_station(arms):
    """No vertex of the uncut apron is deleted, and every vertex the cut
    adds stands on the plateau ring, never on the uncut apron's own
    boundary between two of its stations."""
    pm1, pm0, _p = arms
    from shapely.geometry import Point
    a0 = [f for f in pm0.faces.values() if f.ref == "apronA"]
    assert a0
    k0 = _keys_by_ref(pm0)["apronA"]
    k1 = set().union(*(ks for ref, ks in _keys_by_ref(pm1).items()
                       if ref == "apronA" or ref.startswith("apronA" + PLATEAU_MARK)))
    assert not (k0 - k1), "the cut deleted an apron vertex"
    outline = Polygon([pm0.vertices[v].xy for v in pm0.ring_vertices(a0[0].ring)])
    by_key = {vx.key: vx.xy for vx in pm1.vertices.values()}
    for k in k1 - k0:
        assert outline.exterior.distance(Point(by_key[k])) > 1e-6, (
            "a vertex minted on the apron's own ring", k)



def test_no_apron_face_under_the_identity_spacing_area_is_emitted(arms, law):
    """The REST of a cut apron is never a scrap face (issue #150's §7
    criterion, ``pad_cut._dissolve_rest_slivers``): ``region - piece``
    pinches off scallops where the quantised piece chords a ring station
    the ring stands past, and each one emitted is 4-5 airside vertices
    minted outside every plateau ring.  Read on the whole arrangement: no
    arm may carry a rolled-on face under the law's identity-spacing area
    that the arm WITHOUT the plateau does not carry too."""
    from auto_patch_v2.planar.pad_cut import _identity_sliver_m2
    pm1, pm0, _p = arms
    bar = _identity_sliver_m2(law)

    def _small(pm) -> set:
        out = set()
        for f in pm.faces.values():
            if f.role != "apron":
                continue
            poly = Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)])
            if poly.area < bar:
                out.add((str(f.ref), round(poly.area, 3)))
        return out

    assert not (_small(pm1) - _small(pm0)), (
        "the plateau cut emitted a sub-identity-spacing apron face")

# ── 2. the sliver-dissolve tie ───────────────────────────────────────────

def _region(role, ref, poly, source="cell"):
    if source == "zone":
        return (poly, Region(role, ref, poly, None, None, "groundside", "zone", 1))
    return (poly, Region(role, ref, poly, None, None, "airside", "cell"))


def _r(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def test_a_tied_sliver_dissolves_into_the_same_host_in_any_order(law):
    # a 2 m x 2 m zone sliver bordered by two aprons along 2 m each
    a = _region("apron", "route21", _r(-40.0, 0.0, 0.0, 2.0))
    b = _region("apron", "dsf:objpav85", _r(2.0, 0.0, 40.0, 2.0))
    s = _region("graded_strip", "adjacent_ground:taxi:E:zone1#44",
                _r(0.0, 0.0, 2.0, 2.0), "zone")
    hosts = ("apron", "junction", "cross_connector")
    won = set()
    for faces in ([a, b, s], [b, a, s], [s, b, a], [s, a, b]):
        _f, n, _d, _ar, rows = dissolve_sliver_zones(
            list(faces), law.tables.emit.terrace.strip_min_m2,
            law.tables.emit.terrace.strip_min_width_m, hosts)
        assert n == 1
        won.add(rows[0][3])
    # the tie is broken by the two candidates alone (role, then ref) —
    # never by the STRtree's packing, which put the WEST host first here
    assert won == {"apron:dsf:objpav85"}, won
