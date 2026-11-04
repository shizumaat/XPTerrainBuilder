"""#1852 (owner 2026-11-04T14:53Z: "Typically terminals have two (or more)
levels with roads and/or rails serving both stacked on top of each other")
— a lot welded to a pad's rim where the pad's object has walls authored
below its zero is the building's LOWER level: the rim vertices it shares
leave the pad's plate (``constraints.pad_lower_frontage``); a floor-level
object keeps them (its door); with no object the ground decides.

MEASURED KIAH (station by Terminal D landside, pad ``building88``): the lot
``pav62#beyond1`` rode the pad's 28.04 m over DEM 24.9-26.3 m, held by the
pad's own level row; the station's walls reach y -3.93."""
from __future__ import annotations

import dataclasses as dc
from types import SimpleNamespace

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints.cluster_pad import plate_groups
from auto_patch_v2.constraints.pad_lower_frontage import released_vertices
from auto_patch_v2.constraints.pads import pad_frontage_level
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build

RUN_LEN, HALF_W = 1600.0, 22.5
PAD = ((-60.0, 200.0), (60.0, 200.0), (60.0, 250.0), (-60.0, 250.0))


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Dem:
    """The landside ground (north of the pad) stands 4 m under the apron."""
    provenance = {"synthetic": "landside low"}

    def z(self, x: float, y: float) -> float:
        return 696.0 if y >= 245.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    # the subject is the plain §20 plate: a held block is one HARD plane and
    # is never released (its lower level is ``planar/low_level``'s)
    from tests.auto_patch_v2._plate import plate_law
    return plate_law(Law.for_airport("ZZZZ"))


@pytest.fixture(scope="module")
def base(law):
    return _build(law)


def _build(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "f"),
            RunwayEnd("27", (RUN_LEN / 2, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "f"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    ap = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (), (), (), (),
                 (), (), (), SceneryPack("fixture", "apt.dat", "0", (), ()), _Dem(),
                 law.ruleset_key)
    cells = [Cell(0, "runway", "09/27", _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
                  (), 3, "D", "airside", "runway", {}),
             Cell(1, "apron", "apronA", _rect(-260.0, 140.0, 260.0, 200.0), (), None,
                  None, "airside", "apron", {}),
             Cell(2, "building", "padA", PAD, (), None, None, "airside", "pad", {}),
             Cell(3, "parking_lot", "lotA", _rect(-100.0, 250.0, 100.0, 300.0), (),
                  None, None, "groundside", "lot", {})]
    pm, _st = build(ap, Classification(tuple(cells), (), {}, ()), law)
    return ap, pm


def _with_part(ap, base_y):
    """``ap`` with one walled pack part over the pad, its base at ``base_y``."""
    _xy, to_ll = ap.frame.transformers()
    ring = tuple(to_ll(x, y) for x, y in ((-62, 198), (62, 198), (62, 252), (-62, 252)))
    part = SimpleNamespace(line=False, height_m=20.0, rings=(ring,), base_y=base_y)
    unit = SimpleNamespace(members=(SimpleNamespace(parts=(part,)),))
    return dc.replace(ap, partition=SimpleNamespace(units=(unit,)))


def _lot_rim(pm, law):
    """The pad's plate vertices (``pads._pad_groups``) the lot shares."""
    from auto_patch_v2.constraints.pads import _pad_groups
    lot = next(f for f in pm.faces.values() if f.role == "parking_lot")
    rim = {v for _f, _r, g in _pad_groups(pm, law) for v in g}
    return rim & {v for r in (lot.ring, *lot.holes) for v in pm.ring_vertices(r)}


def test_walls_below_zero_release_the_lot(law, base):
    ap, pm = base
    shared = _lot_rim(pm, law)
    assert shared, "the fixture lot must weld to the pad's rim"
    arm = _with_part(ap, -3.93)
    got = released_vertices(pm, law, arm)
    assert got == frozenset(shared)
    for _f, _r, g in plate_groups(pm, law, arm):
        assert not set(g) & shared
    for r in pad_frontage_level(pm, law, arm):
        assert not {v for v, _c in r.terms} & shared


def test_floor_level_object_keeps_its_door(law, base):
    ap, pm = base
    assert released_vertices(pm, law, _with_part(ap, -0.1)) == frozenset()


def test_no_object_the_ground_decides(law, base):
    ap, pm = base
    # the landside DEM is 4 m under the apron the pad is seated on
    assert released_vertices(pm, law, ap) == frozenset(_lot_rim(pm, law))




def test_a_held_block_is_never_released():
    held_law = Law.for_airport("ZZZZ")      # the flat-pad hold armed
    ap, pm = _build(held_law)
    assert released_vertices(pm, held_law, _with_part(ap, -3.93)) == frozenset()
