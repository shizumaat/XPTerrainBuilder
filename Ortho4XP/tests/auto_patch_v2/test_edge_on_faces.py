"""Twins for #559 — A FACE SEEN EDGE-ON IS NOT PLAN AREA.

The defect (found on a 94,000-triangle terminal object, 1,255
components): OBJ8 vertices are single precision, so a wall authored
vertical stands off its own plan line by a float32 step — 15 um at 200 m
from the object's origin.  Its plan projection is a needle metres long
and one step wide; its AREA passes the standing ``1e-9`` floor, every
needle is a valid polygon, and 11,074 of them through one exact overlay
made GEOS refuse the union (``TopologyException: Ring edge missing``),
which aborted the tile.

The rule (``obj8_clip._edge_on``): a plan triangle whose WIDTH is at or
below the float32 spacing of its own largest coordinate is a line, and is
dropped where triangles become plan polygons (``_bulk_polys``).  The
bound is the file's own resolution, so it scales with the object.

``fixtures/edge_on_needles_559.npz`` is the refusing input reduced by
delta-minimisation to 2,321 of its 85,253 plan triangles (80 of 1,255
components), as integers of 1e-8 m — the file's own 8-decimal print, so
the doubles are the ones the reader parsed.  The remaining twins pin the
RULE on constructed geometry; the union's Law B at the site is G2's
(``test_v2witnessvalid._UNION_FUNCTIONS``).
"""
from __future__ import annotations

import pathlib

import numpy as np
import pytest
import shapely
from shapely.errors import GEOSException
from shapely.ops import unary_union

from auto_patch_v2.airport import skirt
from auto_patch_v2.airport.obj8_clip import _bulk_polys, _edge_on

REACH = 200.0                                   # metres from the object's origin
STEP = float(np.spacing(np.float32(REACH)))     # the float32 step there: 15 um


def _tri(*pts) -> np.ndarray:
    return np.asarray([pts], dtype=float)


def test_a_wall_one_float32_step_off_its_line_is_edge_on():
    """10 m long, one step wide: 7.6e-5 m2 — two orders above the area
    floor, and a line."""
    t = _tri((REACH, 0.0), (REACH, 10.0), (REACH - STEP, 5.0))
    assert shapely.area(shapely.polygons(t))[0] > 1e-9
    assert _edge_on(t).tolist() == [True]


def test_a_thin_real_plate_is_not_edge_on():
    """A 1 mm fin at the same reach is 65 steps wide: geometry, kept."""
    t = _tri((REACH, 0.0), (REACH, 10.0), (REACH - 1e-3, 5.0))
    assert _edge_on(t).tolist() == [False]


def test_the_bound_is_the_coordinates_own_resolution():
    """The same 15 um width is 128 steps wide on an object 1 m across —
    a small part of a small object, kept.  No fixed width decides it."""
    near = _tri((1.0, 0.0), (1.0, 0.5), (1.0 - STEP, 0.25))
    assert STEP > 100 * float(np.spacing(np.float32(1.0)))
    assert _edge_on(near).tolist() == [False]


def test_the_reach_is_the_larger_axis():
    """A wall along x far out in z reads the z reach."""
    t = _tri((0.0, REACH), (10.0, REACH), (5.0, REACH - STEP))
    assert _edge_on(t).tolist() == [True]


def test_bulk_polys_drops_the_needle_and_keeps_the_plate():
    v = np.asarray([
        (REACH, 0.0, 0.0), (REACH, 8.0, 10.0), (REACH - STEP, 4.0, 5.0),   # the wall
        (REACH - 20.0, 8.0, 0.0), (REACH, 8.0, 0.0), (REACH, 8.0, 10.0),   # the roof
    ])
    tris = np.asarray([(0, 1, 2), (3, 4, 5)])
    got = _bulk_polys(v, tris)
    assert len(got) == 1
    assert got[0].area == pytest.approx(100.0)


_NEEDLES = pathlib.Path(__file__).parent / "fixtures" / "edge_on_needles_559.npz"


def _needle_soup() -> np.ndarray:
    """The reduced refusing input as ``(n, 3, 2)`` authored ``(x, z)``."""
    return np.load(_NEEDLES)["xz_1e8"] / 1e8


def test_the_soup_is_all_valid_triangles_with_area():
    """What the area floor let through: every operand valid, every area
    above ``1e-9``.  Whether the exact overlay then REFUSES the union is
    the platform's: shapely 2.1.2's macOS arm64 wheel (GEOS 3.13.1) raises
    ``Ring edge missing``; the same shapely on Linux and Windows x86_64
    returns.  Either is lawful here — a refusal must be GEOS's own, and an
    answer must be the fixed-precision union's area."""
    polys = shapely.polygons(_needle_soup())
    assert shapely.is_valid(polys).all()
    assert (shapely.area(polys) > 1e-9).all()
    try:
        u = unary_union(polys.tolist())
    except GEOSException:
        return
    whole = shapely.union_all(polys, grid_size=1e-6)
    assert u.area == pytest.approx(whole.area, abs=1e-4)


def test_the_soup_unions_exactly_without_its_edge_on_faces():
    """Through ``_bulk_polys`` the same triangles union on the EXACT
    overlay — no ladder rung — and nothing but lines was lost: against
    the fixed-precision union of the WHOLE soup the area falls by no more
    than the dropped needles' own (12 cm2 in 303 m2)."""
    c = _needle_soup()
    v = np.zeros((c.shape[0] * 3, 3))
    v[:, [0, 2]] = c.reshape(-1, 2)
    tris = np.arange(c.shape[0] * 3).reshape(-1, 3)
    kept = _bulk_polys(v, tris)
    thin = _edge_on(c)
    assert int(thin.sum()) == c.shape[0] - len(kept) > 0
    u = unary_union(kept)
    assert u.is_valid
    whole = shapely.union_all(shapely.polygons(c), grid_size=1e-6)
    shed = whole.area - u.area
    assert -1e-6 <= shed <= float(shapely.area(shapely.polygons(c[thin])).sum())
    assert shed < 0.01


class _Geometry:
    def __init__(self, vertices, solid):
        self.vertices, self.solid = vertices, solid


class _Component:
    def __init__(self, tris):
        self.tris = tris


class _Cache:
    """What ``skirt.footprint`` reads of a ``ResourceCache``."""

    def __init__(self, vertices, comps):
        self._g = _Geometry(vertices, np.concatenate(comps))
        self._c = [_Component(t) for t in comps]

    def geometry(self, path):
        return self._g

    def genuine(self, path):
        return self._c

    def components(self, path):
        return self._c


def _leaning_box(x0: float, lean: float):
    """A 30 x 20 m roof at 8 m over four walls whose FEET stand ``lean``
    outside the roof's edge — the single-precision rounding of a vertical
    wall.  Roof and walls are separate components, as authored shells are."""
    x1, z0, z1 = x0 + 30.0, -10.0, 10.0
    top = [(x0, 8.0, z0), (x1, 8.0, z0), (x1, 8.0, z1), (x0, 8.0, z1)]
    foot = [(x0 - lean, 0.0, z0 - lean), (x1 + lean, 0.0, z0 - lean),
            (x1 + lean, 0.0, z1 + lean), (x0 - lean, 0.0, z1 + lean)]
    v = np.asarray(top + foot, dtype=float)
    roof = np.asarray([(0, 1, 2), (0, 2, 3)])
    walls = []
    for k in range(4):
        j = (k + 1) % 4
        walls += [(k, j, 4 + j), (k, 4 + j, 4 + k)]
    return v, [roof, np.asarray(walls)]


def test_the_footprint_is_the_roof_not_the_rounded_walls():
    """Every wall triangle here passes the area floor (0.2 mm2 and up)
    and is one float32 step wide: the footprint is the roof plate,
    exactly, with no needle on its boundary."""
    v, comps = _leaning_box(REACH - 30.0, STEP)
    wall_polys = shapely.polygons(v[comps[1]][:, :, [0, 2]])
    assert (shapely.area(wall_polys) > 1e-9).all()
    fp = skirt.footprint(_Cache(v, comps), "leaning.obj")
    assert fp.geom_type == "Polygon"
    assert fp.area == pytest.approx(600.0, abs=1e-9)
    assert len(fp.exterior.coords) == 5


def test_a_shell_of_walls_alone_still_reads_its_hull():
    """With no plate at all the convex hull of the solid points stands in
    — the standing fallback, reached now for rounded walls too."""
    v, comps = _leaning_box(REACH - 30.0, STEP)
    fp = skirt.footprint(_Cache(v, comps[1:]), "walls.obj")
    assert fp is not None
    assert fp.area == pytest.approx(600.0, rel=1e-4)

