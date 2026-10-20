"""Twins for #581 — ONE PLAN-TRIANGLE ADMISSION, and the unions of pack
triangles under §51 Law B.

#559 dropped the faces seen edge-on (``obj8_clip._edge_on``) where
``_bulk_polys`` turns triangles into plan polygons, and unioned
``skirt._plan_union`` through ``frame_entry.union``.  Five more sites kept
their own area-only floor, and three unions of pack triangles stayed bare.
Every site now admits through ``obj8_clip._plan_admitted``; these twins
pin the rule on degenerate and sliver triangles, placed and authored, and
the routing of each site.
"""
from __future__ import annotations

import ast
import math
import pathlib

import numpy as np
import pytest
import shapely
from auto_patch_v2.airport import below_zero, obj8_clip, wall_geometry
from auto_patch_v2.airport import frame_entry as fe
from auto_patch_v2.airport.obj8_clip import _bulk_polys, _plan_admitted
from shapely.errors import GEOSException

REACH = 200.0
STEP = float(np.spacing(np.float32(REACH)))     # the float32 step there: 15 um

NEEDLE = ((REACH, 0.0), (REACH, 10.0), (REACH - STEP, 5.0))      # a wall, edge-on
PLATE = ((REACH - 20.0, 0.0), (REACH, 0.0), (REACH, 10.0))       # 100 m2 of roof
FIN = ((REACH, 0.0), (REACH, 10.0), (REACH - 1e-3, 5.0))         # a 1 mm fin: real
LINE = ((0.0, 0.0), (5.0, 0.0), (10.0, 0.0))                     # collinear: no area
POINT = ((3.0, 3.0), (3.0, 3.0), (3.0, 3.0))                     # all three coincide


def _admit(*tris, floor: float = 1e-9) -> list[bool]:
    pts = np.asarray(tris, dtype=float)
    return _plan_admitted(pts, shapely.polygons(pts), floor).tolist()


def test_the_admission_keeps_plates_and_fins_and_drops_needles_and_degenerates():
    assert _admit(PLATE, FIN, NEEDLE, LINE, POINT) == [True, True, False, False, False]


def test_the_needle_passes_the_old_area_floor():
    """What the five sites let through before: area alone admits it."""
    assert shapely.area(shapely.polygons(np.asarray([NEEDLE])))[0] > 1e-9


def test_the_floor_is_the_sites_own():
    """A site that snaps its frame to a grid passes its derived floor."""
    assert _admit(PLATE, floor=99.0) == [True]
    assert _admit(PLATE, floor=101.0) == [False]


def _placed(tris: np.ndarray, heading_deg: float, dx: float, dy: float) -> np.ndarray:
    c, s = math.cos(math.radians(heading_deg)), math.sin(math.radians(heading_deg))
    x, z = tris[..., 0], tris[..., 1]
    return np.stack([c * x - s * z + dx, s * x + c * z + dy], axis=-1)


def test_a_placed_needle_is_judged_on_its_authored_coordinates():
    """Placed 3 km out and turned 37 deg the needle's frame polygon is
    a valid sliver with area — the admission reads the AUTHORED triangle,
    the file's resolution, so it is dropped all the same; the plate is
    kept."""
    authored = np.asarray([NEEDLE, PLATE], dtype=float)
    frame = shapely.polygons(_placed(authored, 37.0, 3000.0, -2500.0))
    assert shapely.is_valid(frame).all()
    assert (shapely.area(frame) > 1e-9).all()
    assert _plan_admitted(authored, frame).tolist() == [False, True]


def _v_tris(*tris) -> tuple[np.ndarray, np.ndarray]:
    """Authored ``(x, y, z)`` vertices (y = 4 m) and their index triangles."""
    pts = np.asarray(tris, dtype=float).reshape(-1, 2)
    v = np.zeros((pts.shape[0], 3))
    v[:, 0], v[:, 1], v[:, 2] = pts[:, 0], 4.0, pts[:, 1]
    return v, np.arange(pts.shape[0]).reshape(-1, 3)


IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def test_below_zero_reads_an_edge_on_face_as_its_segment():
    """``below_zero._plan_parts``: the needle is a vertical face, so it
    draws its ground segment, never a polygon."""
    v, tris = _v_tris(PLATE, NEEDLE)
    parts = below_zero._plan_parts(v, tris, IDENT)
    kinds = sorted(p.geom_type for p in parts)
    assert kinds == ["LineString", "Polygon"]
    seg = next(p for p in parts if p.geom_type == "LineString")
    assert seg.length == pytest.approx(10.0)


def test_wall_geometry_drops_the_needle_snapped_or_not():
    v, tris = _v_tris(PLATE, NEEDLE, LINE)
    for q in (0.0, 1e-6):
        got = wall_geometry._plan_polys(v, tris, IDENT, q)
        assert len(got) == 1 and got[0].area == pytest.approx(100.0)


def test_bulk_polys_is_the_same_admission():
    v, tris = _v_tris(PLATE, FIN, NEEDLE, LINE, POINT)
    assert len(_bulk_polys(v, tris)) == 2


class _Comp:
    def __init__(self, tris):
        self.tris = tris


def test_the_clips_union_under_law_b(monkeypatch):
    """``_clip_component`` and ``_clip_both`` union their triangles through
    ``frame_entry.union``: an exact overlay that refuses falls to the
    ladder, counted against the site, and the tile is not aborted."""
    v, tris = _v_tris(PLATE, ((REACH - 20.0, 0.0), (REACH, 10.0), (REACH - 20.0, 10.0)))
    calls = {"n": 0}
    real = fe.unary_union

    def refuse_first(parts):
        calls["n"] += 1
        if calls["n"] == 1:
            raise GEOSException("TopologyException: Ring edge missing (twin)")
        return real(parts)

    fe.reset_rung_counts()
    monkeypatch.setattr(fe, "unary_union", refuse_first)
    got = obj8_clip._clip_component(v, _Comp(tris), 10.0, True)
    assert got is not None and got.area == pytest.approx(200.0)
    assert fe.rung_counts()["obj8_clip._clip_component"][0] == 1

    calls["n"] = 0
    lines, polys = obj8_clip._clip_both(v, _Comp(tris), 0.0)
    assert lines is not None and polys.area == pytest.approx(200.0)
    assert fe.rung_counts()["obj8_clip._clip_both.lines"][0] == 1
    fe.reset_rung_counts()


#: The sites that turn pack triangles into plan polygons (#559, #581):
#: each admits through ``_plan_admitted`` (or ``_bulk_polys``, which does).
_ADMISSION_SITES = {
    ("obj8_clip.py", "_bulk_polys"),
    ("below_zero.py", "_plan_parts"),
    ("sunken_roads.py", "_faces_below"),
    ("wall_geometry.py", "_plan_polys"),
    ("object_cut.py", "shell_reading"),
    ("object_cut.py", "_cover_plate"),
    ("basin_witness.py", "ramp_decks"),
}

_AIRPORT = pathlib.Path(obj8_clip.__file__).parent


def test_every_plan_triangle_site_admits_through_the_one_rule():
    seen, bad = set(), []
    for name in sorted({f for f, _ in _ADMISSION_SITES}):
        tree = ast.parse((_AIRPORT / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or (name, node.name) not in _ADMISSION_SITES:
                continue
            seen.add((name, node.name))
            called = {c.func.id for c in ast.walk(node)
                      if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
            if not called & {"_plan_admitted", "_bulk_polys"}:
                bad.append(f"{name}:{node.name}")
    assert seen == _ADMISSION_SITES, _ADMISSION_SITES - seen
    assert not bad, bad
