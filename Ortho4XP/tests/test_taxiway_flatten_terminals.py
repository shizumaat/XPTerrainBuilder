"""#2278: the legacy taxiway flatten keeps clear of a mapped terminal.

An unpatched airport's OSM taxiways are flattened along a fitted profile
(``O4_Airport_Utils.encode_runways_taxiways_and_aprons``): the ring of
the buffered taxiway area carries the profile's altitude, which can sit a
metre off the ground.  The area was cut back from hangars only, so where a
taxiway runs beside the terminal its ring ran under the terminal building
and draped the ground there; a pack's ``TILTED`` terminal then tilted with
the mesh (measured on the owner's 1.0.580 mesh: the triangle under the
building's origin pitched 8-14 deg, the ground under its footprint
92.31-93.50 m over a 93.30-93.55 m lidar slab).  A terminal is a building
like a hangar: the area keeps the hangar's clearance from it.
"""
from __future__ import annotations

import types
from math import cos, pi

from shapely import geometry

import O4_Airport_Utils as APT
import O4_Vector_Utils as VECT

LAT, LON = 22, -160
M = 1.0 / 111320.0  # one metre of latitude, in degrees


def _layer(terminal_rel: bool = False):
    """A synthetic airports layer: one closed terminal way (or relation)
    20 x 20 m centred at (0.5, 0.5) of the tile, one open service way."""
    x0, y0 = LON + 0.5, LAT + 0.5
    d = 10 * M
    nodes = {1: (x0 - d, y0 - d), 2: (x0 + d, y0 - d), 3: (x0 + d, y0 + d),
             4: (x0 - d, y0 + d), 5: (x0, y0), 6: (x0 + d, y0)}
    ways = {10: [1, 2, 3, 4, 1], 11: [5, 6]}
    tags = {"w": {11: {"aeroway": "taxiway"}}, "r": {}}
    rels = {}
    if terminal_rel:
        rels[20] = {"outer": [ways[10]], "inner": []}
        tags["r"][20] = {"aeroway": "terminal"}
    else:
        tags["w"][10] = {"aeroway": "terminal", "building": "yes"}
    return types.SimpleNamespace(dicosmn=nodes, dicosmw=ways, dicosmr=rels,
                                 dicosmtags=tags)


def _tile():
    VECT.scalx = cos((LAT + 0.5) * pi / 180)
    return types.SimpleNamespace(lat=LAT, lon=LON)


def _apt():
    """A taxiway area (a 60 m wide strip from over the terminal to 200 m
    east of it), no runway, no hangar."""
    d = 30 * M
    taxi = geometry.box(0.5 - d, 0.5 - d, 0.5 + 200 * M, 0.5 + d)
    return {"taxiway": (geometry.MultiPolygon([taxi]), []),
            "runway": (geometry.MultiPolygon(), [], []),
            "hangar": geometry.MultiPolygon()}


def test_terminal_area_reads_ways_and_relations():
    for rel in (False, True):
        area = APT._terminal_area(_tile(), _layer(terminal_rel=rel))
        assert len(area.geoms) == 1
        # grown as a hangar's is (2 m), never the open service way
        assert area.contains(geometry.Point(0.5 + 11 * M, 0.5))
        assert not area.contains(geometry.Point(0.5 + 13 * M, 0.5))


def test_flatten_area_keeps_clear_of_the_terminal():
    tile, apt = _tile(), _apt()
    building = geometry.box(0.5 - 10 * M, 0.5 - 10 * M, 0.5 + 10 * M, 0.5 + 10 * M)
    before = APT._taxiway_flatten_area(apt, geometry.MultiPolygon())
    assert before.intersection(building).area > 0.99 * building.area
    after = APT._taxiway_flatten_area(apt, APT._terminal_area(tile, _layer()))
    assert not after.is_empty and after.intersection(building).is_empty
    # the hangar clearance (20 m past the 2 m growth): no ring within ~20 m
    assert after.distance(building) > 19 * M


def test_no_terminal_leaves_the_area_unchanged():
    tile, apt = _tile(), _apt()
    a = APT._taxiway_flatten_area(apt, geometry.MultiPolygon())
    layer = _layer()
    layer.dicosmtags["w"].pop(10)
    b = APT._taxiway_flatten_area(apt, APT._terminal_area(tile, layer))
    assert a.equals_exact(b, 0.0)
