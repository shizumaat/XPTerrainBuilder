"""#1777 twins: a wall-slope piece takes the side of the ground it grades.

The role stays ``graded_strip`` (every constraint and the law's own gate key
on it); the face's side moves, the sidecar publishes it (``face_sides``)
and the census report sides the row by it (``check_grade.row_side``).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

from auto_patch_v2.emit.osm_adapter import face_sides
from auto_patch_v2.law import Law
from auto_patch_v2.model.planar import Face
from auto_patch_v2.model.wall_reach import WALL_SLOPE_REF_PREFIX
from auto_patch_v2.planar.wall_slope import slope_sides

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import check_grade as cg  # noqa: E402


def _face(fid, role, ref, side="airside"):
    return Face(fid, role, ref, (), (), None, None, side)


def _map():
    """0 an airside zone band; 1 a road; 2 a piece welded to the band,
    3 a piece welded only to piece 2, 4 a piece welded only to the road,
    5 a piece welded to nothing."""
    s = WALL_SLOPE_REF_PREFIX
    faces = {0: _face(0, "graded_strip", "adjacent_ground:taxi:A:zone1"),
             1: _face(1, "service_road", "small_roads:-1", "groundside"),
             2: _face(2, "graded_strip", f"{s}w.obj#0"),
             3: _face(3, "graded_strip", f"{s}w.obj#1"),
             4: _face(4, "graded_strip", f"{s}v.obj#2"),
             5: _face(5, "graded_strip", f"{s}u.obj#3")}
    incident = {10: {0, 2}, 11: {2, 3}, 12: {3}, 13: {1, 4}, 14: {5}, 15: {0}}
    return faces, incident


def test_a_piece_takes_the_side_of_the_ground_it_welds_to():
    faces, incident = _map()
    out = slope_sides(faces, incident)
    assert {f: out[f].side for f in out} == {
        0: "airside", 1: "groundside", 2: "airside", 3: "airside",
        4: "groundside", 5: "groundside"}
    assert all(out[f].role == faces[f].role for f in faces)


def test_no_piece_no_change():
    faces, _ = _map()
    keep = {k: faces[k] for k in (0, 1)}
    assert slope_sides(keep, {10: {0, 1}}) == keep


def test_the_sidecar_names_only_a_side_that_is_not_the_role_s():
    faces, incident = _map()
    out = slope_sides(faces, incident)
    surface = types.SimpleNamespace(faces=tuple(out.values()))
    assert face_sides(surface, Law.load()) == {"4": "groundside", "5": "groundside"}


def test_the_census_report_sides_by_the_face_and_the_gate_by_the_role():
    def way(wid, role, sid):
        return cg.Way(wid, role, "r", "apron", ["1", "2", "3", "1"], [0.0] * 4,
                      {"role": role, "shapeID": sid})
    piece, zone = way("w1", "graded_strip", "4"), way("w2", "graded_strip", "0")
    cg.tag_face_sides([piece, zone], {"4": "groundside"})
    one = types.SimpleNamespace(way_a=piece, way_b=None)
    mixed = types.SimpleNamespace(way_a=piece, way_b=zone)
    assert cg.row_side(one) == "groundside"
    assert cg.row_side(mixed) == "mixed"
    assert not cg._is_groundside(piece)          # the law's gate is the role's
    cg.tag_face_sides([zone], None)
    assert cg.row_side(types.SimpleNamespace(way_a=zone, way_b=None)) == "airside"
