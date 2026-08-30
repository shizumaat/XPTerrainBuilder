"""A FACADE CLUSTER'S BIG INTERIOR HOLE IS GROUND, NOT PAD.

HECA round 6 item 1 (spec ``docs/specs/heca-round6-groundside-\
classification-spec.md`` Family B).  The owner reads ``building79``
(way -10079, shapeID 78) as ONE flat ring at 97.85 spanning ~530 x 490 m
that encompasses FIVE buildings and the pavement around them.

MEASURED on the 1.50.1713 patch: the pad is 100,888 m², 531 x 494 m,
hull-ratio 0.857, with ZERO interior rings and ZERO other building pads
inside it — nothing survived under it to be a building of its own.

MECHANISM: the source's own holes reach the clusterer intact —
``pipeline._admit_dsf_building_footprint`` builds each admitted facade
``Polygon(outer, holes)`` — and the ``+gap/-gap`` merge close only
erases holes narrower than ``DSF_FACADE_MERGE_GAP_M``.  What destroyed
them is ``_cluster_dsf_building_facades``' ``Polygon(g.exterior)``,
written for the sub-metre snap/panel-grid artifacts but applied to every
hole, so an ENCLOSING facade run swallows everything it surrounds.

THE LAW: a building pad is ONE building's footprint; the pavement
between buildings is scored as pavement, split per the source's own
outlines.  A hole is filled only when it is too small to BE ground.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch import config as C                          # noqa: E402
from auto_patch import terminals as T                       # noqa: E402


def _ring_wall(outer_half: float, thickness: float) -> Polygon:
    """A square compound WALL facade — the enclosing run that swallowed
    building79's five buildings."""
    o = outer_half
    i = outer_half - thickness
    return Polygon(
        [(-o, -o), (o, -o), (o, o), (-o, o)],
        [[(-i, -i), (i, -i), (i, i), (-i, i)]],
    )


def test_a_compound_wall_no_longer_swallows_what_it_encloses():
    wall = _ring_wall(100.0, 3.0)          # 200 x 200 m, 3 m wall
    hole_area = (2 * 97.0) ** 2            # 37,636 m² of enclosed ground
    assert wall.area == pytest.approx(200.0 ** 2 - hole_area)

    out = T._cluster_dsf_building_facades([wall])
    assert len(out) == 1
    pad = out[0]
    assert len(pad.interiors) == 1, "the enclosed ground must stay open"
    # The pad is the WALL's own footprint, not the whole compound.
    assert pad.area < 0.25 * 200.0 ** 2
    # And the enclosed ground is not claimed by it.
    assert not pad.contains(Polygon(
        [(-50, -50), (50, -50), (50, 50), (-50, 50)]).centroid)


def test_an_artifact_hole_is_still_filled():
    """The class the fill exists for: a hole below the tiny-pad floor
    cannot hold anything of building scale, so it stays filled and the
    pad stays solid."""
    h = 0.45 * C.DSF_CLUSTER_HOLE_FILL_MAX_M2 ** 0.5   # < the floor
    small = Polygon(
        [(-60, -60), (60, -60), (60, 60), (-60, 60)],
        [[(-h, -h), (h, -h), (h, h), (-h, h)]],
    )
    assert (2 * h) ** 2 < C.DSF_CLUSTER_HOLE_FILL_MAX_M2
    out = T._cluster_dsf_building_facades([small])
    assert len(out) == 1
    assert out[0].interiors[:] == []
    assert out[0].area == pytest.approx(120.0 ** 2, rel=1e-3)


def test_the_threshold_is_the_owners_tiny_pad_floor():
    """One value, not a second copy (RULINGS 2026-08-24)."""
    assert C.DSF_CLUSTER_HOLE_FILL_MAX_M2 == C.PAD_MIN_AREA_M2


def test_a_solid_facade_cluster_is_unchanged():
    """No hole, no change: the ordinary building keeps its old answer."""
    solid = Polygon([(0, 0), (40, 0), (40, 25), (0, 25)])
    out = T._cluster_dsf_building_facades([solid])
    assert len(out) == 1
    assert out[0].interiors[:] == []
    # (the snap-buffer round trip rounds the corners — that is the
    # pre-existing arithmetic, untouched here)
    assert out[0].area == pytest.approx(1000.0, rel=5e-3)
