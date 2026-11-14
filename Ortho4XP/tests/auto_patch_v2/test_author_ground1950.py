"""Issue #1950 twins — BELOW GRADE IS READ AGAINST THE AUTHOR'S GROUND
(owner RULINGS 2026-11-07b (1); ``planar/basin_author_ground``,
``airport/shell_ground``).

KMCI is where it was found: a shared-datum pack hangs every object off one
datum, so a ground plate or a wall's footing reads "below grade" against
the placement's zero or the DEM while it stands on the pack's own ground.
The fixtures: a square of the author's ground plates at a known height
around a footprint, and the readings the basin pass and the shell reader
take against it.  Law values are read from the tables.
"""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import below_grade_witness as bgw
from auto_patch_v2.airport import shell_ground
from auto_patch_v2.geom.author_ground import AuthorGround
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basin_author_ground import author_ground_refusal
from shapely.geometry import box

FOOT = box(0.0, 0.0, 20.0, 40.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _ground(z: float):
    """The author's ground: one placement's plates over a 200 m square at
    ``z`` (the footprint's own faces are another placement's); the DEM 50 m
    under them, so a reading that falls back to it would show."""
    a, b = -100.0, 120.0
    faces = np.array([[(a, a, z), (b, a, z), (b, b, z)], [(a, a, z), (b, b, z), (a, b, z)]])
    return bgw._Ground(AuthorGround(faces, ["plates", "plates"]),
                       lambda xs, ys: np.full(np.size(xs), z - 50.0), {})


def _row(zero: float):
    return types.SimpleNamespace(id="shell", kind="OBJECT", anchor_z=zero, agl_m=0.0)


def test_a_pit_must_stand_under_the_authors_ground(law):
    bl = law.tables.structures.basin
    wit = [types.SimpleNamespace(z_min=100.0)]
    deep = author_ground_refusal("basin:0", FOOT, wit, {"pit"},
                                 _ground(100.0 + bl.admission_depth_m + 1.0), law, "x")
    assert deep is None
    shallow = author_ground_refusal("basin:0", FOOT, wit, {"pit"},
                                    _ground(100.0 + bl.admission_depth_m - 1.0), law, "x")
    assert shallow is not None and "admission_depth_m" in shallow and "its plates" in shallow


def test_a_shell_floor_must_stand_under_the_authors_ground(law):
    ob = law.tables.structures.tunnel.object
    floor_y = -(ob.shell_floor_min_m + 3.0)
    # the zero 100 states a floor 5 m down; the author's ground says how deep
    assert shell_ground.floor_under_ground(_row(100.0), floor_y, FOOT, {"shell"},
                                           _ground(100.0), law) is None
    why = shell_ground.floor_under_ground(_row(100.0), floor_y, FOOT, {"shell"},
                                          _ground(100.0 + floor_y + 0.5), law)
    assert why is not None and "shell_floor_min_m" in why


def _plate(x0, z0, x1, z1, y):
    return [[(x0, y, z0), (x1, y, z0), (x1, y, z1)], [(x0, y, z0), (x1, y, z1), (x0, y, z1)]]


def test_a_building_is_read_at_the_authors_ground_not_its_zero(law):
    """The shell's plates: a 5 m-deep storey over its whole outline and a
    12 m-deep floor under a corner.  Hung off a datum 5 m over the ground,
    the storey is the ground floor (a building); with the datum on the
    ground it is a trench's ramp level and the reading stands."""
    faces = np.array(_plate(0, 0, 20, 40, -5.0) + _plate(0, 0, 5, 5, -12.0))
    r = types.SimpleNamespace(floor_y=-12.0, floor_faces=faces, interior=FOOT)
    cov = types.SimpleNamespace(id="cover")
    on = shell_ground.placed_refusal(_row(100.0), r, cov, FOOT, 100.0, _ground(100.0), law)
    assert on is None
    hung = shell_ground.placed_refusal(_row(100.0), r, cov, FOOT, 100.0, _ground(95.0), law)
    assert hung is not None and "shell_at_zero_max_fraction" in hung


def test_no_plates_around_leaves_the_old_reading(law):
    """Where the author laid no plates around the footprint the readers
    abstain: rule 1 already read the DEM, and the zero is all a shell
    states."""
    g = _ground(100.0)
    bare = bgw._Ground(AuthorGround(np.zeros((0, 3, 3)), []), g.dem, {})
    wit = [types.SimpleNamespace(z_min=100.0)]
    assert author_ground_refusal("basin:0", FOOT, wit, {"pit"}, bare, law, "x") is None
    assert shell_ground.floor_under_ground(_row(100.0), -2.5, FOOT, {"shell"}, bare,
                                           law) is None
