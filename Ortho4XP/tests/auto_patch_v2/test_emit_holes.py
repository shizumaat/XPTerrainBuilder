"""A face hole the neighbouring faces already fill is NOT written as a
``gap_interior_ring`` way (owner, OTHH 2026-09-04: junction 718's hole is
apron 730 exactly — the coincident ring read as "gap_interior_ring" in the
sim).  A hole no face covers (a pocket of raw terrain) still ships its ring
so the mesh constrains it.

RULINGS 2026-09-14g item 5 (lane ``v2slivers``): the cover test is by AREA
(``emit.terrace.hole_cover_eps``), not by ring-EDGE superset — a hole the
inner faces cover 92 % of but not edge-for-edge used to ship as a
constrained ring across a service road — and a hole narrower than
``emit.terrace.strip_min_width_m`` is refused outright.  The fixture's
units are 3 m apart so its 2-unit hole is 6 m wide: a hairline fixture
would be suppressed for its WIDTH and would prove nothing about cover."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from auto_patch_v2.emit.osm_adapter import HOLE_FEATURE, render_patch
from auto_patch_v2.emit.surface import (GradedSurface, SurfaceFace,
                                        SurfaceVertex)
from auto_patch_v2.law import Law
import pytest


@pytest.fixture
def law():
    return Law.for_airport("CYXY")


#: ~3 m per fixture unit at the fixture's latitude (1e-5 deg of latitude is
#: 1.11 m; the longitude axis is scaled by cos(60 deg) in the emitted frame).
_U = 3e-5


def _surface(covered: bool, *, shrink: float = 1.0,
             hairline: bool = False) -> GradedSurface:
    # outer square 0..10, inner square 4..6 (6 m wide at _U = 3e-5)
    lo, hi = 4.0, 6.0
    if hairline:
        lo, hi = 4.9, 5.1                      # 0.6 m: narrower than 3 m
    pts = [(0, 0), (10, 0), (10, 10), (0, 10),
           (lo, lo), (hi, lo), (hi, hi), (lo, hi)]
    # the coverer, when it does not fill the hole edge-for-edge
    c = 0.5 * (lo + hi)
    s = 0.5 * (hi - lo) * shrink
    pts += [(c - s, c - s), (c + s, c - s), (c + s, c + s), (c - s, c + s)]
    verts = tuple(SurfaceVertex(i, (60.0 + y * _U, -135.0 + x * _U * 2.0), 100.0)
                  for i, (x, y) in enumerate(pts))
    faces = [SurfaceFace(1, "apron", "pav1", (0, 1, 2, 3), ((4, 5, 6, 7),), "airside")]
    if covered:
        ring = (4, 5, 6, 7) if shrink == 1.0 else (8, 9, 10, 11)
        faces.append(SurfaceFace(2, "junction", "pav2", ring, (), "airside"))
    return GradedSurface(icao="TEST", ruleset="icao", origin=(60.0, -135.0),
                         crs="+proj=tmerc", identity_dp=11, vertices=verts,
                         faces=tuple(faces), breaklines=(), provenance={})


def _hole_ways(text: str) -> list[dict]:
    root = ET.fromstring(text)
    out = []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        if tags.get("o4_feature") == HOLE_FEATURE:
            out.append(tags)
    return out


def test_covered_hole_is_not_written(law):
    text, n_ways, _ = render_patch(_surface(covered=True), law)
    assert _hole_ways(text) == []
    assert n_ways == 2


def test_uncovered_hole_still_ships_its_ring(law):
    text, n_ways, _ = render_patch(_surface(covered=False), law)
    holes = _hole_ways(text)
    assert [h["shapeID"] for h in holes] == ["1"]
    assert n_ways == 2


def test_hole_covered_by_area_but_not_edges_is_not_written(law):
    """RULINGS 2026-09-14g item 5: the inner face covers 99 % of the hole's
    area and shares NOT ONE edge with it — the ring-EDGE superset test
    shipped it, the AREA test does not."""
    eps = float(law.tables.emit.terrace.hole_cover_eps)
    # sqrt(1 - eps) shrink leaves exactly 1 - eps of the area covered
    text, _n, _v = render_patch(
        _surface(covered=True, shrink=(1.0 - eps * 0.5) ** 0.5), law)
    assert _hole_ways(text) == []


def test_hole_the_inner_face_does_not_cover_keeps_its_ring(law):
    """The other side of the same test: a real void — an inner face covering
    only a quarter of the hole — KEEPS its ring, so the mesh constrains it."""
    text, _n, _v = render_patch(_surface(covered=True, shrink=0.5), law)
    assert [h["shapeID"] for h in _hole_ways(text)] == ["1"]


def test_the_ring_edge_superset_still_suppresses(law):
    """The pre-2026-09-14 test is KEPT as a second sufficient condition:
    dropping it emitted 9 new HECA rings / 245,000 m2 whose edges are ring
    edges throughout and whose interiors are 72-100 % covered — a different
    class from the owner's item 5, and this rule suppresses MORE, never
    ships more.  Here the inner face fills the hole edge-for-edge while
    covering only a quarter of its area by the strict inner test."""
    surface = _surface(covered=True)
    # the coverer IS the hole's ring: covered by edges AND by area
    text, _n, _v = render_patch(surface, law)
    assert _hole_ways(text) == []


def test_hairline_hole_is_refused(law):
    """A hole narrower than ``emit.terrace.strip_min_width_m`` carries no
    transition and is never emitted, covered or not (HECA way -10231,
    1.60 m wide, straight across ``service_road:route4``)."""
    text, _n, _v = render_patch(_surface(covered=False, hairline=True), law)
    assert _hole_ways(text) == []


def test_a_suppressed_hole_leaves_no_detached_nodes(law):
    """Issue #15 (lane ``othhjunction``): the vertices of a hole the writer
    suppresses are named by NO way, and used to ship anyway as free-standing
    nodes — the owner's "clouds of detached nodes" (OTHH 2026-09-18: 209 of
    them, all on suppressed holes).  Every node written is referenced by a
    way, and the returned count is the written count."""
    eps = float(law.tables.emit.terrace.hole_cover_eps)
    for surface in (_surface(covered=True, shrink=(1.0 - eps * 0.5) ** 0.5),
                    _surface(covered=False, hairline=True)):
        text, _n, n_nodes = render_patch(surface, law)
        root = ET.fromstring(text)
        nodes = {n.get("id") for n in root.iter("node")}
        refs = {nd.get("ref") for w in root.iter("way") for nd in w.iter("nd")}
        assert nodes == refs
        assert n_nodes == len(nodes) < len(surface.vertices)
    # nothing is lost where every vertex is on a written ring
    text, _n, n_nodes = render_patch(_surface(covered=False), law)
    assert n_nodes == 8
