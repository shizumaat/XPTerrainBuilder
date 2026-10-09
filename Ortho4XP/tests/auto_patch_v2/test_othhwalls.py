"""Twins of lane ``othhwalls`` (owner RULINGS 2026-10-07a / 07b; issues
#448 #449 #450): a corridor ramp's knees span its width, a retaining-wall
corridor's ramp runs the wall's length, a ramp that cannot top out is no
trench."""
from __future__ import annotations

import pytest
from shapely.geometry import LineString

from auto_patch_v2.classify.roles import CutLine
from auto_patch_v2.model.structures import profile_z
from auto_patch_v2.planar import structure_service as ss


# ── #449: every profile knee is a vertex on every edge that crosses it ──

#: a corridor ramp 10 m wide along +x: flat to the knee at s 27, climbing
#: to s 53 — the cross-chords the ring emits (§34 (7): mouth, knee, top)
_KNEES = (0.0, 27.0, 53.0)
_PROFILE = ((0.0, 2.07), (27.0, 2.07), (53.0, 3.77))


def _chords():
    return [LineString([(s, -5.0), (s, 5.0)]) for s in _KNEES]


def _level_along(points, s: float) -> float:
    """The level a mesh edge chain carries at station ``s``: each vertex
    at its own design level (``ramp_targets`` reads the profile at the
    vertex's projection), LINEAR between consecutive vertices."""
    xs = sorted(p[0] for p in points)
    for a, b in zip(xs[:-1], xs[1:]):
        if a <= s <= b:
            za, zb = profile_z(_PROFILE, a), profile_z(_PROFILE, b)
            return za + (zb - za) * (s - a) / ((b - a) or 1.0)
    raise AssertionError(s)


def test_a_centreline_through_a_ramp_takes_a_vertex_at_every_knee():
    """The road centreline splits the corridor ramp lengthwise.  Before:
    the shared edge ran mouth -> top with no vertex at the knee and stood
    0.88 m over both outer edges there.  After: the level is equal across
    the width at every station."""
    road = CutLine("road_centerline", "route7", ((0.0, 0.0), (53.0, 0.0)))
    edge = [(s, 5.0) for s in _KNEES]                 # an outer ring edge
    before = _level_along(road.points, 27.0) - _level_along(edge, 27.0)
    assert before == pytest.approx(0.866, abs=0.01)   # the #449 ridge
    out = ss.knee_nodes([road], _chords(), 0.5)
    assert len(out) == 1 and out[0].kind == "road_centerline" and out[0].ref == "route7"
    assert [p[0] for p in out[0].points] == pytest.approx(list(_KNEES))
    for s in (0.0, 5.0, 13.5, 27.0, 30.0, 40.0, 53.0):
        assert _level_along(out[0].points, s) == pytest.approx(_level_along(edge, s), abs=1e-9)


def test_knee_nodes_keeps_what_it_does_not_cross():
    """A line that misses every chord, a line that is no surface element
    and an oblique line: untouched / untouched / noded where it crosses,
    its own vertices kept in order (a vertex already at a knee is not
    doubled)."""
    far = CutLine("taxi_centerline", "A", ((0.0, 40.0), (53.0, 40.0)), "E")
    rw = CutLine("runway_profile", "16L", ((0.0, 0.0), (53.0, 0.0)))
    obl = CutLine("road_centerline", "r", ((-10.0, -2.0), (27.0, 0.0), (80.0, 3.0)))
    out = ss.knee_nodes([far, rw, obl], _chords(), 0.5)
    assert out[0] is far and out[1] is rw
    xs = [p[0] for p in out[2].points]
    assert xs == pytest.approx([-10.0, 0.0, 27.0, 53.0, 80.0])
    assert out[2].points[2] == (27.0, 0.0)
    assert ss.knee_nodes([obl], [], 0.5) == [obl]
