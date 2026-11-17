"""#2127 round 3 Part A (spec ``sim-review/2127-R3.md`` §3): a road leaving a
channel through its wall climbs on a RAMP PART of the floor
(``planar/channel_ramp``), stated by the pack's foot line where a member's
feet flank it (16s) and by the road ramp law otherwise; one function reads the
declared floor on the main floor and on a ramp (``geom/channel_declared``)."""
from __future__ import annotations

import types

import numpy as np
from auto_patch_v2.geom import channel_declared as DCL
from auto_patch_v2.planar import channel_ramp as CR
from auto_patch_v2.planar.channel_depth import FLOOR, LEDGE
from shapely.geometry import LineString
from test_hanging_objects1298 import LAW

GROUND = 77.0
FLOOR_Z = 70.0
#: the channel: axis along x 0..400, floor |y| <= 30, crest |y| <= 40
REGION = ((0.0, 30.0), (400.0, 30.0), (400.0, -30.0), (0.0, -30.0))
CREST = ((0.0, 40.0), (400.0, 40.0), (400.0, -40.0), (0.0, -40.0))
AXIS = LineString([(0.0, 0.0), (400.0, 0.0)])
PROFILE = ((0.0, FLOOR_Z), (400.0, FLOOR_Z))


def _airport(*ways):
    return types.SimpleNamespace(
        osm_ways=list(ways),
        dem=types.SimpleNamespace(z=lambda x, y: GROUND),
        frame=types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (y, x))))


def _road(i, pts):
    return types.SimpleNamespace(id=i, kind="small_roads", points=tuple(pts), closed=False,
                                 tags={"highway": "tertiary", "lanes": "2"})


def _exit_road(i=-14, start=60.0):
    """On the floor along the axis from ``start``, then out through the
    north wall at x ~ 240 and on into the field."""
    return _road(i, [(start, 0.0), (200.0, 0.0), (260.0, 60.0), (300.0, 160.0)])


def _vis(feet_rows):
    """A visible floor whose one station holds ``feet_rows`` ``(t, z, kind)``
    of member 0 along the exit road's diagonal, 5 m off it on the outside."""
    rows, kinds = [], []
    u = np.array([60.0, 60.0]) / np.hypot(60.0, 60.0)
    n = np.array([-u[1], u[0]])
    for t, z, _k in feet_rows:
        x, y = np.array([200.0, 0.0]) + u * t + n * 5.0
        rows.append((x, 0.0, z, 0.0, x, y))
        kinds.append(_k)
    return types.SimpleNamespace(feet=[np.array(rows)], kinds=[np.array(kinds, dtype=object)],
                                 level=np.array([FLOOR_Z]))


def _ramps(*ways, vis=None):
    return CR.exit_ramps(_airport(*ways), LAW, "channel:0", AXIS, (0.0, 400.0), PROFILE,
                         REGION, CREST, 6.0, vis)


def test_a_road_leaving_through_the_wall_climbs_at_the_road_ramp_law():
    ramps, rows, notes = _ramps(_exit_road())
    assert len(ramps) == 1 and not rows
    r = ramps[0]
    assert r.source == "law" and r.ref == "channel_floor:0#r0"
    zs = [z for _x, _y, z in r.stations]
    assert abs(zs[0] - FLOOR_Z) < 1e-6 and abs(zs[-1] - GROUND) < 0.1
    st = np.array(r.stations)
    run = np.hypot(np.diff(st[:, 0]), np.diff(st[:, 1]))
    assert (np.diff(st[:, 2]) / run).max() <= LAW.tables.structures.tunnel.ramp_max_grade + 1e-9
    assert any("exit ramp" in n for n in notes)


def test_a_member_foot_line_states_the_ramp():
    feet = [(-30.0, 70.1, FLOOR), (-10.0, 70.3, FLOOR), (5.0, 71.2, LEDGE),
            (15.0, 72.0, LEDGE), (25.0, 72.8, LEDGE)]
    ramps, rows, _notes = _ramps(_exit_road(), vis=_vis(feet))
    r = ramps[0]
    assert r.source == "pack"
    # from the last foot within visual_m of the floor (t -10) through the ledges
    assert rows == frozenset({(0, 1), (0, 2), (0, 3), (0, 4)})
    zs = [z for _x, _y, z in r.stations]
    assert abs(zs[0] - 70.3) < 1e-6 and abs(zs[-1] - GROUND) < 0.1


def test_a_short_run_on_the_floor_is_no_exit():
    ramps, _rows, notes = _ramps(_exit_road(start=195.0))   # 47 m on the floor
    assert ramps == () and any("no exit ramp" in n for n in notes)


def test_the_ramp_is_a_part_of_the_floor_the_crest_takes_in():
    from auto_patch_v2.model.structures import Channel
    from auto_patch_v2.planar.channel_claims import channel_cells
    ramps, _rows, _notes = _ramps(_exit_road())
    crest = CR.crest_with_ramps(CREST, ramps)
    c = Channel(id="channel:0", ways=(1,), axis=tuple(AXIS.coords), profile=PROFILE,
                region=REGION, crest_ring=crest, floor_ref="channel_floor:0",
                wall_ref="channel_wall:0", wall_band_m=6.0, ramps=ramps)
    cells, knives = channel_cells([c], LAW)
    refs = [ref for _role, ref, _p, _c in cells]
    assert "channel_floor:0#r0" in refs
    floor = next(p for _r, ref, p, _c in cells if ref == "channel_floor:0")
    ramp = next(p for _r, ref, p, _c in cells if ref == "channel_floor:0#r0")
    assert floor.distance(ramp) >= 6.0 - 1e-6          # the floor stands back a band
    assert knives[0].contains(ramp.buffer(-0.01))        # the knife covers the ramp


def test_one_function_reads_the_declared_floor():
    ramp = [(0.0, 0.0, 70.0), (10.0, 0.0, 71.0), (20.0, 0.0, 72.0)]
    main = lambda x, y: 69.0                                       # noqa: E731
    assert DCL.declared_floor_z("channel_floor:0#1", 5.0, 3.0, main, {0: ramp}) == 69.0
    assert abs(DCL.declared_floor_z("channel_floor:0#r0", 5.0, 3.0, main, {0: ramp})
               - 70.5) < 1e-9
    # the top line hands over to the road: not declared
    assert DCL.declared_floor_z("channel_floor:0#r0-1", 19.8, 0.0, main, {0: ramp}) is None
    assert DCL.ramp_index("channel_floor:0#r12-3") == 12 and DCL.ramp_index("x#3") is None


def test_a_road_that_ends_gets_a_ramp_that_meets_its_ground_before_it():
    """A dead-end exit road too short for the design grade: the ramp
    steepens (never over ramp_max_grade) to meet its ground by the road's
    end — MEASURED LGAV -1129: at 5 % it ran 7 m past the way's end and the
    unpinned top line stepped 1.56 m."""
    short = _road(-1129, [(60.0, 0.0), (200.0, 0.0), (260.0, 60.0), (290.0, 100.0)])
    ramps, _rows, _notes = _ramps(short)
    st = np.array(ramps[0].stations)
    assert abs(st[-1, 2] - GROUND) < 0.1
    run = np.hypot(np.diff(st[:, 0]), np.diff(st[:, 1]))
    g = np.diff(st[:, 2]) / run
    assert 0.05 < g.max() <= LAW.tables.structures.tunnel.ramp_max_grade + 1e-9
