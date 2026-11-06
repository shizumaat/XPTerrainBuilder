"""Twin of ``tools/drawn_site.py`` (#1903): the drawn-mesh reader, the
loose-triangle sampler and the per-component readings, on synthetic
geometry -- no DSFTool, no installed scenery."""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

_TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools")
sys.path.insert(0, _TOOLS)

import drawn_site as DC  # noqa: E402
from auto_patch.mesh_sampler import MeshElevationSampler  # noqa: E402
from auto_patch_v2.airport.dsf_mesh import (  # noqa: E402
    expand_primitive,
    physical_triangles,
)
from auto_patch_v2.airport.obj8 import Component  # noqa: E402

LAT, LON = 40.0, 10.0


def _text(flags: int, ptype: int, verts) -> list[str]:
    lines = [f"BEGIN_PATCH 0 0.0 -1.0 {flags} 5", f"BEGIN_PRIMITIVE {ptype}"]
    lines += [f"PATCH_VERTEX {x} {y} {z} 0 0" for x, y, z in verts]
    return lines + ["END_PRIMITIVE", "END_PATCH"]


def test_physical_triangles_keeps_physical_patches_in_the_box():
    sq = [(10.0, 40.0, 5.0), (10.001, 40.0, 6.0), (10.0, 40.001, 7.0), (10.001, 40.001, 8.0)]
    text = (_text(1, 1, sq)                                       # strip: 2 triangles
            + _text(0, 0, sq[:3])                                 # overlay patch: not drawn ground
            + _text(1, 2, sq)                                     # fan: 2 triangles
            + _text(1, 0, [(11.0, 41.0, 1.0), (11.001, 41.0, 1.0),
                           (11.0, 41.001, 1.0)]))           # off the box
    got = physical_triangles(text, (9.99, 39.99, 10.01, 40.01))
    assert got.shape == (4, 3, 3)
    assert set(np.unique(got[:, :, 2])) == {5.0, 6.0, 7.0, 8.0}
    assert len(expand_primitive(0, sq[:3] + sq[:3])) == 2


def test_sampler_over_loose_triangles_interpolates_and_misses_outside():
    corners = np.array([[[0, 0, 0], [1, 0, 10], [0, 1, 20]],
                        [[1, 0, 10], [1, 1, 30], [0, 1, 20]]], float)
    smp = MeshElevationSampler.from_triangles(corners, (0, 0, 1, 1))
    assert smp.sample_at(0.25, 0.25).elevation_metres == pytest.approx(7.5)
    assert smp.sample_many([0.75, 2.0], [0.75, 2.0])[1] is None


class _Mesh:
    """A drawn surface given as ``f(east, north)`` in the site frame."""

    def __init__(self, frame: DC.Frame, f):
        self.frame, self.f = frame, f

    def z(self, lat, lon):
        lat, lon = np.asarray(lat, float).reshape(-1), np.asarray(lon, float).reshape(-1)
        e, n = self.frame.enter(lat, lon)
        return np.array([self.f(a, b) for a, b in zip(e, n, strict=True)], float)


def _trench(base: float):
    """An open-top trench 40 m east-west, 10 m wide: a floor 4 m down,
    walls on its north and south sides, both ends open."""
    V = np.array([[-20, -5, base - 4], [20, -5, base - 4], [20, 5, base - 4], [-20, 5, base - 4],
                  [-20, -5, base], [20, -5, base], [20, 5, base], [-20, 5, base]], float)
    tris = np.array([[0, 1, 2], [0, 2, 3],                   # floor
                     [0, 1, 5], [0, 5, 4], [3, 2, 6], [3, 6, 7]])  # south and north walls
    return V, Component(tris, -4.0, 0.0, 0.0, 0.0, False, np.arange(len(tris)))


def _no_others(e, n):
    return np.full(len(e), np.nan)


def test_trench_on_uncut_ground_reads_buried_with_terrain_over_its_ends():
    fr = DC.Frame(LAT, LON)
    V, comp = _trench(100.0)
    rec = DC.measure(V, comp, fr, _Mesh(fr, lambda e, n: 100.0), _no_others)
    assert rec["bottom_minus_mesh"]["p50"] == pytest.approx(-4.0, abs=0.01)
    assert rec["shape"]["class"] == "concave cut shell"
    ends = [q for q in rec["open_runs"] if q["length_m"] >= 8.0]
    assert len(ends) == 2 and all(q["step_m"] == pytest.approx(-4.0, abs=0.01) for q in ends)


def test_trench_in_its_cut_reads_on_the_mesh_and_flush_at_its_ends():
    fr = DC.Frame(LAT, LON)
    V, comp = _trench(100.0)
    cut = lambda e, n: 96.0 if abs(n) <= 5.5 else 100.0                # noqa: E731 (cut + ramps)
    rec = DC.measure(V, comp, fr, _Mesh(fr, cut), _no_others)
    assert abs(rec["bottom_minus_mesh"]["p50"]) <= DC.PAVEMENT_BAR_M
    ends = [q for q in rec["open_runs"] if q["length_m"] >= 8.0]
    assert len(ends) == 2 and all(abs(q["step_m"]) <= DC.PAVEMENT_BAR_M for q in ends)


def test_deck_ends_read_the_step_to_the_ground_beyond():
    fr = DC.Frame(LAT, LON)
    V = np.array([[-30, -6, 101.0], [30, -6, 101.0], [30, 6, 101.0], [-30, 6, 101.0]], float)
    comp = Component(np.array([[0, 1, 2], [0, 2, 3]]), 0.0, 0.0, 0.0, 0.0, True, np.arange(2))
    ground = lambda e, n: 100.3 if abs(e) > 30 else 95.0                # noqa: E731
    rec = DC.measure(V, comp, fr, _Mesh(fr, ground), _no_others)
    ends = sorted((q for q in rec["open_runs"] if q["length_m"] < 20.0), key=lambda q: q["at"][1])
    assert [q["step_m"] for q in ends] == [pytest.approx(0.7, abs=0.01)] * 2
    assert rec["shape"]["class"].startswith("flat plate")


def test_a_box_is_a_convex_body():
    fr = DC.Frame(LAT, LON)
    b = 100.0
    V = np.array([[-10, -10, b], [10, -10, b], [10, 10, b], [-10, 10, b],
                  [-10, -10, b + 8], [10, -10, b + 8], [10, 10, b + 8], [-10, 10, b + 8]], float)
    tris = np.array([[4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                     [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    rec = DC.measure(V, Component(tris, 0, 8, 0, 0, False, np.arange(len(tris))), fr,
                     _Mesh(fr, lambda e, n: b), _no_others)
    assert rec["shape"]["class"] == "convex body"
    feet = [sd["foot_minus_mesh"]["p50"] for sd in rec["outline_sides"]]
    assert feet and all(abs(f) <= DC.PAVEMENT_BAR_M for f in feet)


def test_the_surface_outside_is_the_higher_of_mesh_and_object():
    out, obj = DC.drawn_outside(np.array([10.0, 10.0, np.nan]), np.array([np.nan, 11.0, 9.0]))
    assert out.tolist() == [10.0, 11.0, 9.0] and obj.tolist() == [False, True, True]


def test_row_base_follows_the_row_kind():
    class P:
        kind, elevation = "OBJECT_MSL", 42.0
    assert DC.row_base(P, 7.0) == 42.0
    P.kind, P.elevation = "OBJECT_AGL", 1.5
    assert DC.row_base(P, 7.0) == 8.5
    P.kind, P.elevation = "OBJECT", None
    assert DC.row_base(P, 7.0) == 7.0


def test_placed_vertices_turn_by_heading():
    class G:
        vertices = np.array([[0.0, 0.0, -10.0]])        # 10 m north of the origin (z south)
    v = DC.placed_vertices(G, 0.0, 0.0, 90.0, 5.0)[0]
    assert v[0] == pytest.approx(10.0) and v[1] == pytest.approx(0.0, abs=1e-9) and v[2] == 5.0
    assert math.isclose(DC.Frame(LAT, LON).leave(*DC.Frame(LAT, LON).enter(LAT, LON))[0], LAT)
