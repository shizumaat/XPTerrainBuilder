"""#1984 twin: a MOVING part (an ``ANIM`` block's geometry) is never a
ground reading.  KEGE's SAM jetways author their tunnel, cab and wheels
down to y = -5.47 inside ANIM blocks that draw them from y = 0 up; read
as parts they lifted the jetways 1.15-1.23 m off the apron.  The member's
ground comes from its STILL geometry (``pack_partition._still_parts``)
and so does its base profile (``obj8_grade.base_profile``)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from auto_patch_v2.airport import obj8, pack_partition  # noqa: E402
from auto_patch_v2.law.tables import load_default  # noqa: E402


def _box(x0, y0, z0, x1, y1, z1, base):
    """8 VT rows and 36 indices of an axis-aligned box."""
    vs = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
             (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    rows = [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vs]
    return rows, [base + i for f in faces for i in f]


def _write(path, animated_too=True):
    still, si = _box(-2, 0, -2, 2, 4, 2, 0)            # a rotunda on y = 0
    moving, mi = _box(-1, -5, -20, 1, -2, -4, 8)       # drawn 5 m higher
    rows = still + moving
    idx = si + mi
    lines = ["I", "800", "OBJ", "", f"POINT_COUNTS {len(rows)} 0 0 {len(idx)}"]
    lines += rows + [f"IDX {i}" for i in idx]
    if animated_too:
        lines += ["TRIS 0 36", "ANIM_begin", "ANIM_trans 0 5 0 0 5 0 0 0 none",
                  "TRIS 36 36", "ANIM_end"]
    else:
        lines += ["ANIM_begin", "ANIM_trans 0 5 0 0 5 0 0 0 none",
                  "TRIS 0 72", "ANIM_end"]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def _cache(law):
    return obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)


def test_moving_part_is_not_a_ground_part(tmp_path):
    law = load_default()
    p = str(tmp_path / "jetway.obj")
    _write(p)
    cache = _cache(law)
    comps = list(enumerate(cache.components(p)))
    assert sorted(c.animated for _i, c in comps) == [False, True]
    counts: dict = {}
    kept = pack_partition._still_parts(comps, counts)
    assert [c.animated for _i, c in kept] == [False]
    assert min(c.min_y for _i, c in kept) == 0.0
    assert counts["moving_parts_dropped"] == 1
    assert cache.base_profile(p, law).feet_y == 0.0


def test_all_moving_member_keeps_its_parts(tmp_path):
    law = load_default()
    p = str(tmp_path / "windsock.obj")
    _write(p, animated_too=False)
    cache = _cache(law)
    comps = list(enumerate(cache.components(p)))
    assert all(c.animated for _i, c in comps)
    counts: dict = {}
    assert pack_partition._still_parts(comps, counts) == comps
    assert counts == {}
    assert cache.base_profile(p, law).feet_y == -5.0
