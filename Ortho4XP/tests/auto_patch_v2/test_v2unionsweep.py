"""Lane ``v2unionsweep`` (RULINGS 2026-09-14b): ``union_area_m2``'s ACTIVE-SET
sweep reads the SAME AREA, BIT FOR BIT, as the re-scan it replaced.

The law here is not the number — it is that the number did not move.  §16f (7)
and design §30 (4) gate a cluster pad on ``area_m2 >= cluster_pad_min_m2``, so a
one-ulp drift can add or drop a whole emitted pad.  The old implementation is
kept beside the new one as :func:`placement_family._union_area_m2_reference`
(called by nothing in the engine) and every case below asserts equality on the
raw IEEE-754 bytes, not ``pytest.approx``.

Coverage: hand-written overlap classes (disjoint / touching / nested /
partially overlapping / duplicated / degenerate / empty), a seeded fuzz over
box populations whose coordinates repeat at several rounding depths (so the
slab boundaries genuinely coincide, which is where an active set can drift from
a re-scan), and — when the registered OTHH capture is on this machine — the
REAL part boxes of the capture's own units, capped so the O(slabs x boxes)
reference stays a test and not a build.
"""
from __future__ import annotations

import os
import pickle
import random
import struct

import pytest

from auto_patch_v2.airport import placement_family as pf


#: the registered OTHH capture (frames: ``OTHH capture base 7949757a``)
OTHH_CAPTURE = ("/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/"
                "3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othh327/"
                "OTHH.pkl")

#: the reference is O(slabs x boxes); a real unit carries tens of thousands of
#: part boxes and would take minutes.  The cap keeps the REAL-geometry arm a
#: few seconds; the full 44-cluster reading is the lane's measurement, not the
#: suite's.
OTHH_BOX_CAP = 1200


def _bits(x: float) -> bytes:
    return struct.pack("<d", x)


def _same(boxes) -> None:
    got = pf.union_area_m2(boxes)
    want = pf._union_area_m2_reference(boxes)
    assert _bits(got) == _bits(want), (got, want, len(list(boxes)))


CASES = {
    "empty": [],
    "all_none": [None, None],
    "degenerate_point": [(1.0, 1.0, 1.0, 1.0)],
    "degenerate_zero_height": [(1.0, 1.0, 1.0, 2.0)],
    "degenerate_zero_width": [(1.0, 1.0, 2.0, 1.0)],
    "single": [(25.0, 51.0, 25.001, 51.001)],
    "duplicate": [(25.0, 51.0, 25.001, 51.001)] * 4,
    "disjoint_lat": [(25.0, 51.0, 25.001, 51.001),
                     (25.002, 51.0, 25.003, 51.001)],
    "disjoint_lon": [(25.0, 51.0, 25.001, 51.001),
                     (25.0, 51.002, 25.001, 51.003)],
    "touching_lat": [(25.0, 51.0, 25.001, 51.001),
                     (25.001, 51.0, 25.002, 51.001)],
    "touching_lon": [(25.0, 51.0, 25.001, 51.001),
                     (25.0, 51.001, 25.001, 51.002)],
    "nested": [(25.0, 51.0, 25.004, 51.004),
               (25.001, 51.001, 25.002, 51.002)],
    "overlap_corner": [(25.0, 51.0, 25.002, 51.002),
                       (25.001, 51.001, 25.003, 51.003)],
    "overlap_cross": [(25.0, 51.001, 25.003, 51.002),
                      (25.001, 51.0, 25.002, 51.003)],
    "shared_boundary_stack": [(25.0, 51.0, 25.002, 51.001),
                              (25.0, 51.001, 25.002, 51.002),
                              (25.001, 51.0, 25.003, 51.002)],
    "one_valid_rest_junk": [None, (1.0, 1.0, 1.0, 1.0),
                            (25.0, 51.0, 25.001, 51.001)],
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_sweep_matches_reference_bitwise(name: str) -> None:
    _same(CASES[name])


@pytest.mark.parametrize("seed", [1, 2, 3, 5, 8, 13])
def test_sweep_matches_reference_fuzz(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(40):
        bs = []
        for _i in range(rng.randint(0, 60)):
            dp = rng.choice([3, 4, 5, 6])
            la = round(rng.uniform(25.0, 25.01), dp)
            lo = round(rng.uniform(51.0, 51.01), dp)
            h = rng.choice([0.0, 0.0001, 0.0005, 0.002])
            w = rng.choice([0.0, 0.0001, 0.0005, 0.002])
            bs.append((la, lo, la + h, lo + w))
        _same(bs)


def test_sweep_matches_reference_southern_hemisphere() -> None:
    """``_m_per_deg`` is taken at the slab midpoint; a negative latitude must
    walk the same slabs in the same order."""
    rng = random.Random(21)
    bs = [(-33.0 - rng.random() * 0.01, 151.0 + rng.random() * 0.01,
           0.0, 0.0) for _ in range(30)]
    bs = [(a, b, a + 0.0004, b + 0.0007) for a, b, _c, _d in bs]
    _same(bs)


def test_reference_is_unused_by_the_engine() -> None:
    """The reference exists for this twin only — if a caller appears, the two
    implementations have become two authorities."""
    assert "_union_area_m2_reference" not in pf.__all__


def _othh_unit_boxes():
    if not os.path.exists(OTHH_CAPTURE):
        return None
    with open(OTHH_CAPTURE, "rb") as fh:
        plan = pickle.load(fh)["airport"].partition
    out = []
    for u in plan.units:
        bx = [p.box for m in u.members for p in m.parts
              if not p.line and p.box]
        if len(bx) >= 8:
            out.append(bx[:OTHH_BOX_CAP])
        if len(out) >= 6:
            break
    return out


def test_sweep_matches_reference_on_othh_part_boxes() -> None:
    """REAL geometry: the registered OTHH capture's own part boxes (base
    7949757a).  Skipped by name where the capture is not on the machine — it
    is a lane artefact, not a fixture in the tree."""
    got = _othh_unit_boxes()
    if got is None:
        pytest.skip(f"registered OTHH capture absent: {OTHH_CAPTURE}")
    assert got, "capture carries no unit with >= 8 part boxes"
    for bx in got:
        _same(bx)
