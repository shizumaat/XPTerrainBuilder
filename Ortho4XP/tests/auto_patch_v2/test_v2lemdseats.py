"""RULINGS 2026-09-09q (1): a structure the terrain adapted to (a wall
corridor / basin / tunnel member) excludes THAT MEMBER from the re-seat,
never its ANCHOR FAMILY.

The measured failure: Aerosoft anchors the whole LEMD terminal pack at
two origin points, so the 28 wall-corridor members' ids — expanded to
their anchor family by the deleted ``[rebake] structure_family_excluded``
— took 300 placements out of the re-seat and left them at their authored
y over 32 m of relief (worst +36.4 m sunk, −31.8 m floating).

Twins here, sharing ``test_m6a_rebake``'s synthetic pack:

1. a family of THREE at one anchor spelling, one member a corridor wall:
   the wall stays out, the other two seat (and stay ONE unit);
2. the law key is gone — nothing may re-introduce the expansion;
3. the excluded member is still excluded when named by PATH (the basin
   records' spelling), and still only itself.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.rebake_plan import plan as _plan
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import read_objects

from test_m6a_rebake import _airport, _box_obj, law, pack   # noqa: F401


@pytest.fixture(scope="module")
def family(pack, law):                                      # noqa: F811
    """Three resources at ONE anchor spelling (0, 0), heading apart —
    ``family_key`` is the anchor position, so all three share it."""
    d = pack / "objects"
    for name in ("wall", "sib1", "sib2"):
        _box_obj(d / f"{name}.obj", 7.0, 5.0, 2.0)
    a = _airport(pack, law, [
        ("wall", (0.0, 0.0), 0.0, 0.0),
        ("sib1", (0.0, 0.0), 90.0, 0.0),
        ("sib2", (0.0, 0.0), 180.0, 0.0),
    ])
    objs, _ = read_objects(a, law)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    for o in objs:
        if o.resolved:
            cache.geometry(o.resolved)
    return a, objs, cache


def _plan_excluding(family, law, exclude):                  # noqa: F811
    a, objs, cache = family
    return _plan(a, objs, cache, law, exclude=exclude)


def _wall_id(family):
    _a, objs, _c = family
    return next(o.id for o in objs if o.path.endswith("wall.obj"))


def test_the_family_is_one_unit_when_nothing_is_excluded(family, law):  # noqa: F811
    pl = _plan_excluding(family, law, ())
    assert pl.counts["terrain_adapted"] == 0
    assert pl.counts["units"] == 1 and pl.counts["members"] == 3


def test_a_corridor_wall_excludes_only_itself(family, law):  # noqa: F811
    """The ruling: the wall stays out; its two anchor siblings seat."""
    pl = _plan_excluding(family, law, (_wall_id(family),))
    assert pl.counts["terrain_adapted"] == 1
    seated = {m.resource for u in pl.units for m in u.members}
    assert seated == {"objects/sib1.obj", "objects/sib2.obj"}
    assert "objects/wall.obj" in dict(pl.skipped)
    # ...and the survivors are still ONE body at the shared anchor (09d)
    assert pl.counts["units"] == 1 and pl.counts["members"] == 2


def test_the_exclusion_also_takes_the_resource_PATH_spelling(family, law):  # noqa: F811
    pl = _plan_excluding(family, law, ("objects/wall.obj",))
    assert pl.counts["terrain_adapted"] == 1
    assert {m.resource for u in pl.units for m in u.members} == {
        "objects/sib1.obj", "objects/sib2.obj"}


def test_the_family_expansion_key_is_deleted():
    """No caller may switch the expansion back on (RULINGS 09q (1))."""
    rb = Law.for_airport("ZZZZ").tables.structures.rebake
    assert not hasattr(rb, "structure_family_excluded")
