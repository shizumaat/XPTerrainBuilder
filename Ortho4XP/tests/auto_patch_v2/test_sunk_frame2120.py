"""Twin of ``airport/sunk_frame`` (#2120): a frame its author drew DOWN from
his ground (``OBJECT_AGL`` < 0, its walls reaching from a buried footing up
to that ground) stands its author's ground on the ground -- its high side
where the ground steps across it -- and is no pad there.  KATL's 2026-11
pack: ``katl126_wall`` (y 0..20, AGL -19.81) floated its road plate 20 m
standing its walls' feet on the ground."""
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np
from auto_patch_v2.airport.sunk_frame import sunk_frames, sunk_shade
from auto_patch_v2.airport.wall_shade import wall_shade
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from tests.auto_patch_v2.test_wall_class_thick import FRAME, _StepDem

CFG = load_rules().service
LAW = Law.load()
_M_LAT = 1.0 / 111_320.0


def _airport(lift: float, base_y: float, height: float, step: float, width: float = 20.0):
    lat0, lon0 = 33.64, -84.42
    dlon = 100.0 / (111_320.0 * np.cos(np.radians(lat0)))
    ring = [(lat0, lon0), (lat0, lon0 + dlon), (lat0 + width * _M_LAT, lon0 + dlon),
            (lat0 + width * _M_LAT, lon0)]
    part = NS(rings=[ring], height_m=height, base_y=base_y, comp=0, line=False)
    m = NS(id="dsf:obj1", resource="objects/wall_000.obj", parts=[part])
    _x, y_axis = FRAME.entry()(lon0, lat0 + 0.5 * width * _M_LAT)
    unit = NS(id="unit:1", agl_m=lift, members=[m])
    return NS(partition=NS(units=[unit]), frame=FRAME,
              dem=_StepDem(y_axis, 300.0, 300.0 - step), sunken_ramps=None)


def test_a_block_sunk_to_its_top_stands_its_authored_ground_on_the_ground():
    got = sunk_frames(_airport(-19.81, 0.0, 20.0, 0.0), CFG, LAW)
    assert len(got) == 1
    f = got[0]
    assert not f.stepped and abs(f.plate_y - 19.81) < 1e-9
    assert f.ids == ("dsf:obj1",) and len(f.stations) >= 4
    assert sunk_shade(_airport(-19.81, 0.0, 20.0, 0.0), CFG, LAW) is None


def test_a_sunk_wall_between_two_levels_reads_its_high_side_and_is_no_pad():
    ap = _airport(-18.29, 0.0, 20.0, 12.0, width=1.0)
    (f,) = sunk_frames(ap, CFG, LAW)
    assert f.stepped and abs(f.plate_y - 18.29) < 1e-9
    z = ap.dem.z_many([p[0] for p in f.stations], [p[1] for p in f.stations])
    assert np.all(z == 300.0)                       # the upper level only
    shade = wall_shade(ap, CFG, comps=[])
    assert shade is not None and shade.area > 50.0


def test_a_frame_standing_on_its_authored_ground_is_not_sunk():
    # AGL 0, or a lift whose walls' feet are not buried floor_sunken_min_m
    assert sunk_frames(_airport(0.0, 0.0, 20.0, 12.0), CFG, LAW) == ()
    assert sunk_frames(_airport(-1.5, 0.0, 20.0, 12.0), CFG, LAW) == ()
    assert sunk_frames(_airport(+4.0, 0.0, 20.0, 12.0), CFG, LAW) == ()


def test_a_frame_buried_wholly_under_its_authored_ground_is_not_sunk():
    # its top stands more than authored_rim_tol_m under the author's ground
    assert sunk_frames(_airport(-6.0, 0.0, 3.0, 0.0), CFG, LAW) == ()


def test_a_retaining_plate_leads_only_a_unit_its_frame_dominates():
    """The plate's datum is its frame's y = 0: a terminal (AGL 0) dominating
    a §16g unit it shares with a sunk wall (AGL -19.81) must not take it --
    the closing build sank KATL's terminal F 19.4 m that way.  A runway-end
    WALLED plate still leads whatever it chains (#1977)."""
    from auto_patch_v2.airport.open_frame_seat import plate_leads_unit, walled_unit_zero
    wall = NS(plate_kind="retaining", plate_y=19.81, plate_stations=((33.64, -84.42),))
    term = NS(plate_kind="", plate_y=None, plate_stations=())
    frames = {1: ((33.64, -84.42), -19.81), 2: ((33.65, -84.41), 0.0),
              3: ((33.65, -84.41), 0.0), 4: ((33.64, -84.42), -19.81)}
    assert not plate_leads_unit([1, 2, 3], {1: wall, 2: term, 3: term}, frames)
    # the wall's frame dominates (a pole of another frame on its pad): it leads
    assert plate_leads_unit([1, 4, 2], {1: wall, 4: wall, 2: term}, frames)
    assert abs(walled_unit_zero([wall], lambda la, lo: 300.0) - 280.19) < 1e-9
    walled = NS(plate_kind="walled", plate_y=-9.9, plate_stations=((33.64, -84.42),))
    assert plate_leads_unit([1, 2, 3], {1: walled, 2: term, 3: term}, frames)
    assert not plate_leads_unit([2], {2: term}, frames)
