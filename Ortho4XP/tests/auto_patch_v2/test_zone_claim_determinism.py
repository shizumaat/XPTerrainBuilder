"""Issue #486 (and #637): the zone claim is DETERMINISTIC.

``planar/zones.zone_regions`` cut every band from one floating cascaded
union of all cells; adding any cell re-noded it, so a zone part beside a
runway edge kilometres away changed (HECA: a 0.8 mm hairline part; KCLT: a
runway vertex flipping 227.08 / 227.13 m).  The claim and the bands are now
fixed-precision overlays over a canonical order (``geom/fixed_overlay``):
a band near a point is a function of the cells near that point.
"""
from __future__ import annotations

import random

import shapely
from shapely import affinity
from shapely.geometry import Polygon, box

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.geom.fixed_overlay import (canonical_union, fixed_difference,
                                              is_hairline)
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_side
from auto_patch_v2.planar.zones import zone_regions

LAW = Law.for_airport("HECA")
_ANG = 23.7                       # off-axis, so every overlay node is inexact


def _rot(g):
    return affinity.rotate(g, _ANG, origin=(0, 0))


def _cell(i, role, ref, g, cn=None, cl=None):
    return Cell(i, role, ref, tuple(g.exterior.coords)[:-1], (), cn, cl,
                role_side(LAW, role), role, {})


def _field(seed=7):
    """A 3 km runway in four pieces, four connectors, a parallel and a
    random apron beyond it — the shape of a real field's claim."""
    rng = random.Random(seed)
    cuts = [0.0, 700.3333, 1311.77, 2222.2222, 3000.123456]
    cells = [_cell(j, "runway", "05/23", _rot(box(cuts[j], 0, cuts[j + 1], 45.0)), cn=4)
             for j in range(4)]
    i = 10
    for x in (300.3, 1100.7, 1900.11, 2700.9):
        cells.append(_cell(i, "junction", f"pav{i}", _rot(box(x, 45.0, x + 23.0, 300.0)),
                           cl="E"))
        i += 1
    cells.append(_cell(i, "junction", "pavP", _rot(box(0, 300.0, 3000.123456, 323.0)),
                       cl="E"))
    i += 1
    for _ in range(40):
        x0, y0 = rng.uniform(0, 2900), rng.uniform(330, 600)
        q = Polygon([(x0, y0), (x0 + rng.uniform(20, 80), y0 + rng.uniform(-3, 3)),
                     (x0 + rng.uniform(20, 80), y0 + rng.uniform(20, 60)),
                     (x0 + rng.uniform(-3, 3), y0 + rng.uniform(20, 60))])
        if q.is_valid:
            cells.append(_cell(i, "apron", f"ap{i}", _rot(q)))
            i += 1
    return cells, rng


def _near(cells, window):
    """The zone material inside ``window``, by band, exactly."""
    out = []
    for z in zone_regions(tuple(cells), LAW):
        if z.polygon.intersects(window):
            part = shapely.normalize(z.polygon.intersection(window))
            out.append((z.ref.split("#")[0], part.wkb_hex))
    return sorted(out)


def test_an_unrelated_cell_leaves_the_bands_at_the_far_end_of_the_runway():
    """A cell added inside the runway band 1.2 km away changes no zone
    vertex beside the runway's other end (old code: 30 of 30 moved)."""
    cells, rng = _field()
    window = _rot(box(0, -200, 800, 290))
    base = _near(cells, window)
    assert base
    for _ in range(12):
        x0, y0 = rng.uniform(1950, 2650), rng.uniform(70, 250)
        extra = _cell(999, "apron", "extra",
                      _rot(box(x0, y0, x0 + rng.uniform(5, 40), y0 + rng.uniform(5, 40))))
        assert _near(cells + [extra], window) == base


def test_the_bands_do_not_depend_on_the_order_of_the_cells():
    cells, _ = _field()
    want = [(z.ref, z.polygon.wkb_hex) for z in zone_regions(tuple(cells), LAW)]
    for seed in (1, 2):
        shuffled = list(cells)
        random.Random(seed).shuffle(shuffled)
        assert [(z.ref, z.polygon.wkb_hex)
                for z in zone_regions(tuple(shuffled), LAW)] == want


def test_the_lip_is_cut_by_every_connector():
    """The runway lip ring, cut by four connectors, is FOUR parts: the
    south side with both ends, and the three runs between connectors.  The
    floating claim kept a hairline along the shared pavement edge under a
    connector and joined two of them into one part (3 parts)."""
    cells, _ = _field()
    lips = [z.polygon for z in zone_regions(tuple(cells), LAW)
            if z.ref.startswith("adjacent_ground:runway:4:zone1")]
    assert len(lips) == 4
    for k in (Polygon(c.ring) for c in cells if c.role == "junction"):
        assert all(p.intersection(k).area < 1e-4 for p in lips)


def test_the_fixed_overlay_helpers():
    a, b = box(0, 0, 10, 10), box(5, 0, 15, 10)
    assert canonical_union([a, b]).equals(canonical_union([b, a]))
    assert canonical_union([a, b]).wkb == canonical_union([b, a]).wkb
    assert canonical_union([]).is_empty
    assert fixed_difference(a, None) is a
    assert abs(fixed_difference(a, b).area - 50.0) < 1e-9
    assert is_hairline(box(0, 0, 1000, 0.0015), 0.002)
    assert not is_hairline(box(0, 0, 1000, 0.003), 0.002)
    assert not is_hairline(box(0, 0, 1000, 0.0015), 0.0)
