"""A face hole the neighbouring faces already fill is NOT written as a
``gap_interior_ring`` way (owner, OTHH 2026-09-04: junction 718's hole is
apron 730 exactly — the coincident ring read as "gap_interior_ring" in the
sim).  A hole no face covers (a pocket of raw terrain) still ships its ring
so the mesh constrains it."""
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


def _surface(covered: bool) -> GradedSurface:
    # outer square 0..10, inner square 4..6
    pts = [(0, 0), (10, 0), (10, 10), (0, 10), (4, 4), (6, 4), (6, 6), (4, 6)]
    verts = tuple(SurfaceVertex(i, (60.0 + y * 1e-5, -135.0 + x * 1e-5), 100.0)
                  for i, (x, y) in enumerate(pts))
    faces = [SurfaceFace(1, "apron", "pav1", (0, 1, 2, 3), ((4, 5, 6, 7),), "airside")]
    if covered:
        faces.append(SurfaceFace(2, "junction", "pav2", (4, 5, 6, 7), (), "airside"))
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
