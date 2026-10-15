"""#609 (lane forecourt609): a part-less component standing on ANOTHER
file's footed structure, in the same authored frame, and touching no part
of its own placement, is not joined to its own placement by reach — it
becomes its own footless body and §15's search seats it on what it stands
on.

The witness is a shared-datum pack: the terminal's file holds a roof
plate that lies 40 m from every terminal part but inside the terminal's
part HULL, authored on top of a canopy that is another file placed at the
same origin.  Before the rule the plate joined the terminal's group and
was written at the terminal's zero (KCLT's toll-plaza roof, +3.45 m over
its canopy, 1.0.392).

Red on main (no ``foreign_feet``; the plate joins the terminal), green
here."""
from __future__ import annotations

import types

import numpy as np

from auto_patch_v2.airport import placement_orphan as PO

_O = (35.0, -80.0)          # one authored origin, both files
_D = 1.0 / 111_000.0        # ~1 m in latitude degrees


def _part(box, base, h, feet=True):
    return types.SimpleNamespace(box=box, feet=feet, line=False,
                                 base_y=base, height_m=h)


def _member(res, parts, origin=_O, heading=0.0):
    return types.SimpleNamespace(resource=res, origin=origin,
                                 heading_deg=heading, parts=parts)


def _box(la0, lo0, la1, lo1):
    return (_O[0] + la0 * _D, _O[1] + lo0 * _D,
            _O[0] + la1 * _D, _O[1] + lo1 * _D)


# the terminal's two wings 200 m apart (hull spans the gap); the canopy
# in the middle, 5.5 m tall; the roof plate on the canopy's top
WING_A = _box(0, 0, 20, 20)
WING_B = _box(0, 200, 20, 220)
CANOPY = _box(2, 100, 18, 120)
ROOF = _box(4, 102, 16, 118)


def _plan(canopy_origin=_O):
    terminal = _member("terminal.obj", [_part(WING_A, 0.0, 10.0),
                                        _part(WING_B, 0.0, 10.0)])
    canopy = _member("canopy.obj", [_part(CANOPY, 0.0, 5.5)],
                     origin=canopy_origin)
    return types.SimpleNamespace(
        units=[types.SimpleNamespace(members=[terminal, canopy])]), terminal


def test_foreign_feet_reads_the_structure_in_its_own_frame():
    plan, terminal = _plan()
    on = PO.foreign_feet(plan, 0.5, 0.3)
    assert on(ROOF, terminal, lambda: 5.5)          # rests on the canopy
    assert not on(ROOF, terminal, lambda: 9.0)      # above it
    assert not on(_box(4, 150, 16, 160), terminal, lambda: 5.5)  # over nothing
    # another frame: the canopy placed elsewhere says nothing about it
    plan2, terminal2 = _plan(canopy_origin=(35.1, -80.0))
    assert not PO.foreign_feet(plan2, 0.5, 0.3)(ROOF, terminal2, lambda: 5.5)
    # disarmed
    assert PO.foreign_feet(plan, 0.0, 0.3) is None


def test_clear_of_every_own_part():
    clear = PO._clear_of([WING_A, WING_B])
    assert clear(ROOF)
    assert not clear(_box(10, 10, 30, 30))
    assert PO._clear_of([])(ROOF)


class _Cutter:
    """The two written components of the terminal's file: comp 0 is wing
    A's (owned), comp 1 the roof plate (no part names it)."""

    def __init__(self):
        self._tris = np.array([[0, 1, 2]])

    def written_components(self):
        return [(0, self._tris, WING_A), (1, self._tris, ROOF)]

    def geom_points(self, _parts, _tris):
        c = ROOF
        return [(0.5 * (c[0] + c[2]), 0.5 * (c[1] + c[3]), 5.5)]

    def part_tops(self, raws):
        return [[5.5] for _ in raws]


def _staged(terminal):
    part_a = types.SimpleNamespace(comp=0)
    part_b = types.SimpleNamespace(comp=2)
    raw = [([part_a], "other", None, (), False, (), (), 210.0),
           ([part_b], "other", None, (), False, (), (), 210.0)]
    return types.SimpleNamespace(
        cutter=_Cutter(), raw=raw, m=terminal, groups=[[0, 1]],
        part_boxes=[[WING_A], [WING_B]], boxes=[WING_A, WING_B],
        geom_boxes=[WING_A, WING_B], part_tops=[], elevated=frozenset())


def test_a_roof_on_another_files_canopy_is_its_own_body():
    plan, terminal = _plan()
    st = _staged(terminal)
    counts: dict = {}
    PO.place_orphans(st, 100.0, None, counts,
                     over=PO.foreign_feet(plan, 0.5, 0.3))
    assert counts.get("orphan_on_foreign_feet") == 1
    assert counts.get("orphan_components_own_body") == 1
    assert not counts.get("orphan_components_joined")
    assert len(st.raw) == 3 and 2 in st.elevated     # asks §15's search
    assert st.groups == [[0, 1]]                     # not the terminal's


def test_without_the_witness_the_roof_joins_the_terminal():
    """The control: the hull reach alone joins it (gap 0 to the hull)."""
    _plan_, terminal = _plan()
    st = _staged(terminal)
    counts: dict = {}
    PO.place_orphans(st, 100.0, None, counts)
    assert counts.get("orphan_components_joined") == 1
    assert st.groups == [[0, 1, 2]]
