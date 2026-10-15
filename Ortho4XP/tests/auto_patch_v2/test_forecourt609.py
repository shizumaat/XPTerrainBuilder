"""#609 (lane forecourt609, owner RULINGS 2026-10-14l (2)): a part-less
component with clear space to every part of its own placement — farther
than ``footprint_touch_m`` from each part box — is seated as its own
object (§15's carrier search), however near its placement's part HULL.

The witness: a terminal file's roof plate 82 m from both terminal wings
but inside their hull (gap 0).  Before the rule it joined the terminal's
group and was written at the terminal's zero (KCLT's toll-plaza roof,
+3.45 m over its canopy, app 1.0.392).

Red on main (no ``clear_m``; the plate joins the terminal), green here."""
from __future__ import annotations

import types

import numpy as np

from auto_patch_v2.airport import placement_orphan as PO

_O = (35.0, -80.0)
_D = 1.0 / 111_000.0        # ~1 m in latitude degrees


def _box(la0, lo0, la1, lo1):
    return (_O[0] + la0 * _D, _O[1] + lo0 * _D,
            _O[0] + la1 * _D, _O[1] + lo1 * _D)


# the terminal's two wings 200 m apart (the hull spans the gap); the roof
# plate in the middle, 82 m from each
WING_A = _box(0, 0, 20, 20)
WING_B = _box(0, 200, 20, 220)
ROOF = _box(4, 102, 16, 118)


def test_clear_of_every_own_part():
    st = types.SimpleNamespace(raw=[([1], ), ([1], )],
                               part_boxes=[[WING_A], [WING_B]])
    near = _box(0, 20.3, 20, 30)            # 0.3 m off wing A: touching
    assert PO._clear_of_parts(st, [ROOF, near], 0.5) == [True, False]
    assert PO._clear_of_parts(st, [ROOF, near], 0.0) == [False, False]


class _Cutter:
    """The two written components of the terminal's file: comp 0 is wing
    A's (owned), comp 1 the roof plate (no part names it)."""

    def __init__(self, roof=None):
        self._tris = np.array([[0, 1, 2]])
        self._roof = roof or ROOF

    def written_components(self):
        return [(0, self._tris, WING_A), (1, self._tris, self._roof)]

    def geom_points(self, _parts, _tris):
        c = ROOF
        return [(0.5 * (c[0] + c[2]), 0.5 * (c[1] + c[3]), 5.5)]

    def part_tops(self, raws):
        return [[5.5] for _ in raws]


def _staged(roof=None):
    part_a = types.SimpleNamespace(comp=0)
    part_b = types.SimpleNamespace(comp=2)
    raw = [([part_a], "other", None, (), False, (), (), 210.0),
           ([part_b], "other", None, (), False, (), (), 210.0)]
    return types.SimpleNamespace(
        cutter=_Cutter(roof), raw=raw, m=None, groups=[[0, 1]],
        part_boxes=[[WING_A], [WING_B]], boxes=[WING_A, WING_B],
        geom_boxes=[WING_A, WING_B], part_tops=[], elevated=frozenset())


def test_a_roof_clear_of_every_own_part_is_its_own_body():
    """82 m from both wings, inside their hull: its own object."""
    st = _staged()
    counts: dict = {}
    PO.place_orphans(st, 100.0, None, counts, clear_m=0.5)
    assert counts.get("orphan_clear_of_own_parts") == 1
    assert counts.get("orphan_components_own_body") == 1
    assert not counts.get("orphan_components_joined")
    assert len(st.raw) == 3 and 2 in st.elevated     # asks §15's search
    assert st.groups == [[0, 1]]                     # not the terminal's


def test_a_component_touching_its_own_part_still_joins():
    st = _staged(roof=_box(2, 20.3, 18, 30))         # 0.3 m off wing A
    counts: dict = {}
    PO.place_orphans(st, 100.0, None, counts, clear_m=0.5)
    assert not counts.get("orphan_clear_of_own_parts")
    assert counts.get("orphan_components_joined") == 1
    assert st.groups == [[0, 1, 2]]


def test_without_the_clearance_the_roof_joins_the_terminal():
    """The control (disarmed): the hull reach alone joins it (gap 0)."""
    st = _staged()
    counts: dict = {}
    PO.place_orphans(st, 100.0, None, counts)
    assert counts.get("orphan_components_joined") == 1
    assert st.groups == [[0, 1, 2]]
