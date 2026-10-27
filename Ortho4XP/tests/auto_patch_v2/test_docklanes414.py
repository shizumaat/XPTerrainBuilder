"""#414 — PACK DOCK LANES: THE WALLS FRAME THE RAMP (owner RULINGS
2026-10-28h, Q218–Q220).

* (1) a pack floor plate authored OPPOSITE to the lane its walls frame —
  at grade against the face that closes the lane, deepest at the open end
  — is read as THE BAY those walls frame (``airport/plate_frame``,
  ``planar/plate_bays``): deep at the closed end, rising over the walls'
  length.  Twin: two MIRRORED lanes of one object, one framed by walls
  alone (a Law C bay), one carrying such a plate, come out as mirrored,
  EQUAL ramps.
* (2) a bay's floor is the SHALLOWER wall's bottom
  (``wall_corridors._floor_profile``).
* (3) side-by-side bays sharing a wall are all built
  (``planar/structure_overlap.resolve_overlaps``).

Synthetic geometry only; no airport is named by the code under test.
"""
from __future__ import annotations

import types

import numpy as np
import pytest
from shapely.geometry import LineString, Polygon

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.sunken_roads import read_sunken_roads
from auto_patch_v2.airport.wall_corridors import CLASS_BAY, WallBand, _floor_profile
from auto_patch_v2.airport.wall_family import read_wall_corridors
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.structures import profile_z
from auto_patch_v2.planar import structure_overlap
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.door_ramps import sunken_groups
from auto_patch_v2.planar.plate_bays import plate_bays
from auto_patch_v2.planar.structures import build_structures
from auto_patch_v2.planar.wall_corridor_ramps import KIND as WALL_KIND, wall_corridor_groups
from test_tunnel_objects import _airport, _rect, _slab, _write
from test_v2wallcorridor import _vwall

#: the dock row's authored geometry (object frame: x across, z along the
#: lanes, the closing face at z = 0, the lanes open at z = LANE_M)
LANE_M = 18.0
LANE_W = 12.0
WALL_T = 0.3
DEPTH = 1.2
CANOPY_Y = 5.0


def _plate(vt, tris, x0, x1, z0, z1, y0, y1):
    """A floor sheet whose top runs from ``y0`` at ``z0`` to ``y1`` at
    ``z1`` — its top faces alone, as a pack draws a ramp's surface."""
    b = len(vt)
    vt += [(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)]
    tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]


def _dock_row(path):
    """Two lanes side by side sharing the wall at x = 0: lane W (x < 0)
    framed by walls alone, ``DEPTH`` deep; lane P (x > 0), its mirror,
    beside the shared wall alone (its floor plate is another member of the
    family, :func:`_dock_plate`); one face closing both lanes at z = 0, a
    canopy over their inner half."""
    vt: list = []
    tris: list = []
    h = WALL_T / 2.0
    _vwall(vt, tris, -h - LANE_W - WALL_T, -h - LANE_W, 0.0, LANE_M, -DEPTH, -DEPTH, 0.5)
    _vwall(vt, tris, -h, h, 0.0, LANE_M, -DEPTH, -DEPTH, 0.5)
    _vwall(vt, tris, -h - LANE_W - WALL_T, h + LANE_W, -WALL_T, 0.0, -DEPTH, -DEPTH, 2.5)
    _slab(vt, tris, -h - LANE_W - WALL_T, h + LANE_W, 0.0, LANE_M * 0.55, CANOPY_Y, CANOPY_Y + 0.3)
    return _write(path, vt, tris)


def _dock_plate(path):
    """Lane P's floor plate, authored the OTHER way: at grade against the
    closing face, ``DEPTH`` under at the open end."""
    vt: list = []
    tris: list = []
    h = WALL_T / 2.0
    _plate(vt, tris, h, h + LANE_W, 0.0, LANE_M, 0.0, -DEPTH)
    return _write(path, vt, tris)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory):
    d = tmp_path_factory.mktemp("pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    return {"dir": d, "dock": _dock_row(d / "dock.obj"), "plate": _dock_plate(d / "plate.obj")}


def _read(objs, law, names=("dock", "plate")):
    airport = _airport(objs, law, [(n, (0.0, 0.0), 0.0, None, "OBJECT") for n in names])
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    objects, _rep = read_objects(airport, law, cache)
    return airport, cache, objects


def _cells():
    return [Cell(0, "runway", "09/27", _rect(-600, 500, 600, 545), (), 3, "D", "airside",
                 "runway", {})]


def test_mirrored_lanes_get_mirrored_equal_ramps(objs, law):
    """(1) + (3): the walled lane is a Law C bay; its mirror, carrying a
    plate authored the other way, is the SAME bay mirrored — and both are
    built though they share a wall."""
    airport, cache, objects = _read(objs, law)
    walls, wst = read_wall_corridors(airport, objects, cache, law)
    roads, rst = read_sunken_roads(airport, objects, cache, law)
    assert [w.cls for w in walls] == [CLASS_BAY], (wst.refused, wst.admission)
    assert len(roads) == 1 and roads[0].framed is not None, rst.refused
    f = roads[0].framed
    assert f.wall_length_m == pytest.approx(LANE_M, abs=0.05)
    assert f.closed_cover >= law.tables.structures.cutout.wall_corridor.end_cap_cover_min
    kept, bays = plate_bays(roads, walls, law, airport.dem.z)
    assert not kept and len(bays) == 1 and bays[0].cls == CLASS_BAY
    w, b = walls[0], bays[0]
    # mirrored plans: s = 0 on the closing face, the axes mirror across x = 0
    assert b.axis[0][0] == pytest.approx(-w.axis[0][0], abs=0.3)
    assert b.axis[0][1] == pytest.approx(w.axis[0][1], abs=0.3)
    assert b.axis[-1][1] == pytest.approx(w.axis[-1][1], abs=0.3)
    assert b.length_m == pytest.approx(w.length_m, abs=0.3)
    assert b.width_m == pytest.approx(w.width_m, abs=0.3)
    # both deep at the closed end, by the same depth
    assert w.grounds[0] - w.floors[0] == pytest.approx(DEPTH, abs=0.05)
    assert b.grounds[0] - b.floors[0] == pytest.approx(DEPTH, abs=0.05)
    groups = wall_corridor_groups(list(walls) + bays, law) + sunken_groups(kept, law)
    cl = Classification(tuple(_cells()), (), {}, ())
    _cl2, tunnels, sst = build_structures(airport, cl, law, objects, (), groups)
    assert len(tunnels) == 2 and all(t.source == WALL_KIND for t in tunnels), sst.refused
    tw, tp = sorted(tunnels, key=lambda t: t.axis[0][0])
    assert tp.top_s == pytest.approx(tw.top_s, abs=0.3)
    assert tp.design_grade == pytest.approx(tw.design_grade, abs=0.005)
    for t in (tw, tp):
        assert profile_z(t.profile, 0.0) == pytest.approx(t.mouth_dem_z - DEPTH, abs=0.08)
        assert profile_z(t.profile, t.top_s) == pytest.approx(t.mouth_dem_z, abs=0.08)
        assert not t.clipped_by


def test_a_plate_with_no_closing_face_stays_law_b(tmp_path, law):
    """(1) is a test of witnesses: without the face closing the lane at
    the plate's grade end, the plate is read as Law B reads it."""
    vt: list = []
    tris: list = []
    _vwall(vt, tris, -WALL_T, 0.0, 0.0, LANE_M, -DEPTH, -DEPTH, 0.5)
    _plate(vt, tris, 0.0, LANE_W, 0.0, LANE_M, 0.0, -DEPTH)
    _slab(vt, tris, -WALL_T, LANE_W, 0.0, LANE_M * 0.55, CANOPY_Y, CANOPY_Y + 0.3)
    d = tmp_path / "objects"
    d.mkdir()
    (tmp_path / "Earth nav data").mkdir()
    (tmp_path / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    walls = _write(d / "walls.obj", vt[:8], tris[:8])
    vt, tris = vt[8:], [tuple(i - 8 for i in t) for t in tris[8:]]
    objs = {"dir": d, "walls": walls, "open": _write(d / "open.obj", vt, tris)}
    airport, cache, objects = _read(objs, law, ("walls", "open"))
    roads, rst = read_sunken_roads(airport, objects, cache, law)
    assert len(roads) == 1 and roads[0].framed is None, rst.refused
    kept, bays = plate_bays(roads, (), law, airport.dem.z)
    assert kept == roads and not bays


def _band(z_bottom: float, x: float, y_auth: float) -> WallBand:
    zs = np.linspace(0.0, LANE_M, 10)
    pts = np.array([(x, z, z_bottom, y_auth) for z in zs])
    poly = LineString([(x, 0.0), (x, LANE_M)]).buffer(0.15, cap_style="flat")
    return WallBand("o", "r", 0, poly, 0.3, LineString([(x, 0.0), (x, LANE_M)]), LANE_M, 0.0,
                    pts, 0.5, z_bottom)


def test_the_floor_is_the_shallower_walls_bottom():
    """(2): one wall 1.2 m deep, a block beside it 12 m deep — the floor
    is the shallower wall's bottom, per station."""
    axis = LineString([(6.0, 0.0), (6.0, LANE_M)])
    ss = [0.0, 6.0, 12.0, LANE_M]
    floors, floors_y = _floor_profile((_band(698.8, 0.0, -1.2), _band(688.0, 12.0, -12.0)),
                                      axis, ss, 0.5)
    assert floors_y == pytest.approx([-1.2] * 4)
    assert floors == pytest.approx([698.8] * 4)


def test_bays_sharing_a_wall_are_all_built(monkeypatch):
    """(3): two wall corridors whose footprints overlap in the wall they
    share are both kept; a wall corridor overlapping any OTHER structure
    still drops the smaller (the pair test is unchanged)."""
    monkeypatch.setattr(structure_overlap, "overlap_yield", lambda *a, **k: ({}, {}))
    a = Polygon(_rect(-12.3, 0.0, 0.15, 18.0))
    b = Polygon(_rect(-0.15, 0.0, 12.3, 18.0))
    walls = [types.SimpleNamespace(id="w1", source=WALL_KIND),
             types.SimpleNamespace(id="w2", source=WALL_KIND)]
    keep, refused = [True, True], []
    structure_overlap.resolve_overlaps(walls, [a, b], keep, {}, {}, {}, {}, None, 0.1, 0.5,
                                       False, refused)
    assert keep == [True, True] and not refused
    mixed = [walls[0], types.SimpleNamespace(id="t1", source="object")]
    keep, refused = [True, True], []
    structure_overlap.resolve_overlaps(mixed, [a, b], keep, {}, {}, {}, {}, None, 0.1, 0.5,
                                       False, refused)
    assert keep.count(True) == 1 and refused


# ── 2026-10-28l (2): the shared wall hides the step between two bays ─────

def _bay_tunnel(tid, x0, x1, floor, ground=700.0):
    """A Law C bay's Tunnel as the publication reads it: the lane between
    x0 and x1 (y 0..18), its two walls 0.3 m thick outside it."""
    from auto_patch_v2.model.structures import Tunnel
    return Tunnel(tid, (), (((x0 + x1) / 2.0, 0.0), ((x0 + x1) / 2.0, LANE_M)), (x1 - x0) / 2.0,
                  ground, floor, LANE_M, 0.0, (), "", (), source=WALL_KIND,
                  profile=((0.0, floor), (LANE_M, ground)),
                  footprint=tuple(_rect(x0 - WALL_T, 0.0, x1 + WALL_T, LANE_M)))


def _pair(shared_bottom):
    """Two bays, floors 1.2 m and 0.8 m down, sharing the wall at
    x 0..0.3 whose bottom stands at ``shared_bottom``."""
    import dataclasses as dc
    a = _bay_tunnel("bayA", -LANE_W, 0.0, 698.8)
    b = _bay_tunnel("bayB", WALL_T, WALL_T + LANE_W, 699.2)
    ring = lambda xa: ((xa, 0.0), (xa + WALL_T, 0.0), (xa + WALL_T, LANE_M), (xa, LANE_M))  # noqa: E731
    a = dc.replace(a, wall_bands=((ring(-LANE_W - WALL_T), 698.6), (ring(0.0), shared_bottom)))
    b = dc.replace(b, wall_bands=((ring(0.0), shared_bottom), (ring(WALL_T + LANE_W), 698.6)))
    return a, b


def _planar(tunnels, ramps=None):
    """The planar map's things the publication reads: the structures,
    vertex keys for the plan -> lat/lon fit, and the faces the emitted
    ramps stand on (``ramps``: ref -> plan ring; none by default)."""
    xys = [(-50.0, -50.0), (50.0, -50.0), (0.0, 60.0), (40.0, 40.0)]
    faces = {}
    for ref, ring in (ramps or {}).items():
        faces[ref] = types.SimpleNamespace(ref=ref, role="", holes=(),
                                           ring=tuple(range(len(xys), len(xys) + len(ring))))
        xys += list(ring)
    vs = {i: types.SimpleNamespace(xy=(x, y), key=(60.5 + y / 111320.0, -135.5 + x / 55000.0))
          for i, (x, y) in enumerate(xys)}
    return types.SimpleNamespace(structures=tuple(tunnels), vertices=vs, faces=faces,
                                 ring_vertices=lambda ring: ring)


def test_a_deep_shared_wall_declares_the_step_between_two_bays(law):
    """(2) of 28l: a shared wall reaching under BOTH floors is declared
    along its own axis; a chord crossing it is forgiven up to its reach,
    a chord beside it is not."""
    import tools.check_grade as cg
    from auto_patch_v2.pipeline.shared_wall_steps import LABEL, shared_wall_joints
    joints = shared_wall_joints(_planar(_pair(698.5)), law)
    assert len(joints) == 1 and joints[0]["kind"] == cg.WALL_TERRACE_JOINT_KIND
    assert joints[0]["shapes"][0] == LABEL
    assert joints[0]["declared_step_m"] == pytest.approx(700.0 - 698.5 + 0.01)
    ll_to_m = lambda la, lo: ((lo + 135.5) * 55000.0, (la - 60.5) * 111320.0)  # noqa: E731
    walls = cg.DeclaredWallSteps(joints, ll_to_m)
    assert walls.allowance(-0.2, 9.0, 0.5, 9.0) == pytest.approx(1.51)    # across the wall
    assert walls.allowance(-3.0, 9.0, -1.0, 9.0) == 0.0                   # beside it, in bay A
    assert walls.allowance(0.15, -3.0, 0.15, -1.0) == 0.0                 # beyond the bays


def test_a_shallow_shared_wall_declares_nothing(law):
    """A shared wall standing ABOVE a floor hides nothing: the step reports."""
    from auto_patch_v2.pipeline.shared_wall_steps import shared_wall_joints
    assert shared_wall_joints(_planar(_pair(699.0)), law) == []


def test_the_step_is_declared_between_the_ramps_as_emitted(law):
    """The rings stand on the identity lattice, not on a 0.3 m wall: here
    both emitted ramps end LEFT of the authored band's axis (x = 0.15).
    The declared line is their midline (x = -0.75), so the chord between
    the two rings is forgiven; a chord that crosses only the authored
    axis, inside bay B's ramp, is not under the shared wall and still
    reports in full, as does a step inside bay A."""
    import dataclasses as dc

    import tools.check_grade as cg
    from auto_patch_v2.pipeline.shared_wall_steps import shared_wall_joints
    a, b = _pair(698.5)
    a, b = dc.replace(a, ramp_refs=("rampA",)), dc.replace(b, ramp_refs=("rampB",))
    ramps = {"rampA": _rect(-LANE_W, 0.0, -1.0, LANE_M),
             "rampB": _rect(-0.5, 0.0, WALL_T + LANE_W, LANE_M)}
    joints = shared_wall_joints(_planar((a, b), ramps), law)
    assert len(joints) == 1
    ll_to_m = lambda la, lo: ((lo + 135.5) * 55000.0, (la - 60.5) * 111320.0)  # noqa: E731
    walls = cg.DeclaredWallSteps(joints, ll_to_m)
    assert walls.allowance(-1.0, 9.0, -0.5, 9.0) == pytest.approx(1.51)   # ring to ring
    assert walls.allowance(-0.4, 9.0, 1.0, 9.0) == 0.0                    # off the wall, in B
    assert walls.allowance(-3.0, 9.0, -1.5, 9.0) == 0.0                   # off the wall, in A
