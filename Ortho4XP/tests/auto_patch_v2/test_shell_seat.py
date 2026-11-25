"""#2272 round 3 (owner 2026-11-25T04:29Z): a kept small terrain shell is
ONE rigid body seated by its skirt on our ground (``shell_seat``): the
offset closest to 0 that leaves no gap under its land rim, water stations
not read, bounded by the skirt's depth and REPORTED past it; our ground is
never cut.  Synthetic OBJ8s and a synthetic drawn surface, no corpus."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from auto_patch_v2.airport import shell_seat as SS  # noqa: E402
from auto_patch_v2.airport import terrain_cut as TC  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.model.frame import Frame  # noqa: E402

import test_terrain_model as TTM  # noqa: E402

LAT, LON = 17.9, -62.85
HALF = 30.0
#: the author's datum (the ground near it is land, over the sea datum)
Z0 = 20.0


def _mesa(x, z):
    """A 60 m square rock, its skirt rising 5 m in its outer 5 m: 0.5 m at
    the centre of an outline cell (1 m), 4.5 m under the body."""
    edge = HALF - max(abs(x), abs(z))
    return 5.0 * min(1.0, max(0.0, edge) / 5.0)


def _rec(path, oid="dsf:obj0", lat=LAT, lon=LON, z0=Z0):
    return {"id": oid, "model": oid, "resource": "rock.obj", "seat": TM.SEAT,
            "elevation": z0, "shell": {"file": path, "lat": lat, "lon": lon, "heading": 0.0}}


def _surface(ground, lat=LAT, lon=LON):
    """Our drawn ground ``ground(x, y)`` (metres east / north of the
    anchor) as the placement write's surface."""
    to_xy, _ = TC.projector(lat, lon)

    def many(lats, lons):
        x, y = to_xy(np.asarray(lons, float), np.asarray(lats, float))
        return [float(ground(a, b)) for a, b in zip(x, y, strict=True)]

    def one(la, lo):
        return many([la], [lo])[0]
    one.many = many
    return one


@pytest.fixture()
def rock(tmp_path):
    return TTM._write(tmp_path, "rock.obj", _mesa, half=HALF, step=1.0, hard=False)


def test_a_rim_already_under_our_ground_keeps_the_authors_height(rock):
    recs, reps = SS.seat_shells([_rec(rock)], _surface(lambda x, y: Z0 + 1.0))
    (rep,) = reps
    assert rep["dz"] == 0.0 and rep["gap_before_m"] == 0.0 and rep["fixed"]
    assert rep["headroom_m"] == pytest.approx(0.5, abs=0.05)
    assert rep["depth_m"] == pytest.approx(4.5, abs=0.05)
    assert recs[0]["elevation"] == Z0


def test_the_seat_is_rigid_and_closest_to_zero(rock):
    """Our ground 2.5 m under the rim on the east half: the whole body goes
    down by the largest gap -- no more -- and every row of its set with it;
    another record stays."""
    rider = {"id": "dsf:obj1", "model": "dsf:obj0", "resource": "hut.obj", "seat": TM.SEAT,
             "elevation": 4.0}
    other = {"id": "dsf:obj2", "resource": "x.obj", "seat": TM.SEAT, "elevation": 9.0}
    recs, (rep,) = SS.seat_shells([_rec(rock), rider, other],
                                  _surface(lambda x, y: Z0 - 2.0 if x > 0 else Z0 + 1.0))
    assert rep["dz"] == pytest.approx(-2.5, abs=0.05)
    assert rep["gap_before_m"] == pytest.approx(2.5, abs=0.05) and rep["gap_after_m"] == 0.0
    assert recs[0]["elevation"] == pytest.approx(Z0 + rep["dz"], abs=1e-3)
    assert recs[1]["elevation"] == pytest.approx(4.0 + rep["dz"], abs=1e-3)
    assert recs[2] == other
    assert "dz -2.50" in SS.log_line(rep)


def test_a_rim_over_water_is_not_read(rock):
    """RULINGS 2026-11-25a (3): the east half of the rim stands at the sea
    datum (the water's): its 3 m "gap" is the shell running under the
    water, and the land rim alone seats it."""
    surf = _surface(lambda x, y: 0.0 if x > 0 else 4.0)
    _recs, (rep,) = SS.seat_shells([_rec(rock, z0=3.0)], surf)
    assert rep["wet"] > 0 and rep["land"] > 0
    assert rep["dz"] == 0.0 and rep["fixed"]


def test_a_gap_deeper_than_the_skirt_is_reported(rock):
    """Our ground 8.5 m under the whole rim, the skirt 4.5 m deep: the seat
    goes down the skirt's depth and no further, and the shell is
    REPORTED with the 4 m left."""
    _recs, (rep,) = SS.seat_shells([_rec(rock)], _surface(lambda x, y: Z0 - 8.0))
    assert not rep["fixed"]
    assert rep["dz"] == pytest.approx(-rep["depth_m"], abs=1e-9)
    assert rep["gap_after_m"] == pytest.approx(4.0, abs=0.05)
    assert "REPORTED" in SS.log_line(rep)


def test_a_rim_under_another_kept_shell_is_that_shells(tmp_path, rock):
    """Two rocks overlapping by 10 m: the stations inside the other's plan
    are not read (it covers them), so the low ground hidden under the
    overlap seats neither."""
    to_xy, to_ll = TC.projector(LAT, LON)
    lon2, lat2 = (float(v[0]) for v in to_ll(np.array([50.0]), np.array([0.0])))

    def ground(x, y):
        return Z0 - 6.0 if 18.0 < x < 32.0 and abs(y) < 28.0 else Z0 + 1.0
    recs = [_rec(rock), _rec(rock, "dsf:obj9", lat2, lon2)]
    _out, reps = SS.seat_shells(recs, _surface(ground))
    assert all(r["shared"] > 0 for r in reps)
    assert [r["dz"] for r in reps] == [0.0, 0.0]


def test_seat_offset_is_the_one_rule():
    assert SS._seat_offset(np.array([0.5, 2.0]), 4.0)["dz"] == 0.0
    r = SS._seat_offset(np.array([-1.5, 2.0]), 4.0)
    assert r["dz"] == -1.5 and r["fixed"] and r["gap_after_m"] == 0.0
    r = SS._seat_offset(np.array([-6.0, 2.0]), 4.0)
    assert r["dz"] == -4.0 and not r["fixed"] and r["gap_after_m"] == 2.0
    assert SS._seat_offset(np.array([]), 4.0)["dz"] == 0.0


def test_a_small_shell_record_carries_its_plan_and_no_cut(tmp_path):
    """``terrain_model.seat_records``: a small shell's own row carries its
    plan as ``shell`` (the tile build cuts nothing under it) and every row
    of its set names it as ``model``; a model's own row keeps its ``cut``."""
    path = TTM._write(tmp_path, "rock.obj", _mesa, half=HALF, step=5.0, hard=False)
    m = TM.TerrainModel("dsf:obj0", "rock.obj", (0.0, 0.0), 0.0, 2.0, 0.9, 0.1, 0.0,
                        3600.0, 5.0, file=path, datum=2.0, fill=True, small=True)

    class _A:
        terrain_models = (("dsf:obj0", "rock.obj", m, 0.0), ("dsf:obj1", "hut.obj", m, 1.0))
        frame = Frame("TEST", (LAT, LON), 11)
    recs = TM.seat_records(_A())
    assert "cut" not in recs[0] and "cut" not in recs[1]
    assert recs[0]["shell"] == {"file": path, "lat": LAT, "lon": LON, "heading": 0.0}
    assert [r.get("model") for r in recs] == ["dsf:obj0", "dsf:obj0"]
    assert "shell" not in recs[1]
    assert TM.model_paths(recs) == ("rock.obj",)
