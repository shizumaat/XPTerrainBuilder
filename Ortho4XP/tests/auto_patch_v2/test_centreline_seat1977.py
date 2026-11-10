"""Owner RULINGS 2026-11-10i (#1977 item 2): an origin-built ``OBJECT_MSL``
set whose origin stands on a runway's extended centreline beyond its end,
heading along it, is seated with its origin (the light plane) at the
solved runway-end elevation, not draped at its origin.  Synthetic packs
in ``tmp_path``; no airport, no corpus."""
from __future__ import annotations

import math
import types

from auto_patch_v2.airport import centreline_seat as CS
from auto_patch_v2.airport import placement_write as PW

END_Z = 271.85          # the design surface at the runway end
VALLEY_Z = 260.48       # ... and in the valley under the approach lights
#: one runway end on an axis bearing 47° outward, 45.72 m wide
LAT0, LON0 = 38.0, -81.0
_ML, _MO = 111_000.0, 111_000.0 * math.cos(math.radians(LAT0))


def _at(s, t=0.0, bearing=47.0):
    """``(lat, lon)`` ``s`` m beyond the end along the outward axis, ``t``
    m to its right."""
    b = math.radians(bearing)
    e = s * math.sin(b) + t * math.cos(b)
    n = s * math.cos(b) - t * math.sin(b)
    return LAT0 + n / _ML, LON0 + e / _MO


FAR = _at(-2500.0)
END = {"runway": "05/23", "end": "23", "lat": LAT0, "lon": LON0,
       "far_lat": FAR[0], "far_lon": FAR[1], "half_width_m": 22.86}


def _obj(tmp_path, name, y0, y1):
    vt = [(0, y0, 0), (5, y0, 0), (0, y1, 5), (5, y1, 5)]
    body = ["I", "800", "OBJ", "POINT_COUNTS 4 0 0 6"]
    body += [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in vt]
    body += [f"IDX {i}" for i in (0, 1, 2, 1, 3, 2)] + ["TRIS 0 6"]
    (tmp_path / "objects").mkdir(exist_ok=True)
    (tmp_path / "objects" / name).write_text("\n".join(body) + "\n", encoding="utf-8",
                                             newline="\n")
    return "objects/" + name


def _row(path, lat, lon, heading=46.99):
    return types.SimpleNamespace(def_path=path, lat=lat, lon=lon, heading_deg=heading,
                                 kind="OBJECT_MSL", elevation=271.0)


def _surface(la, lo):
    return END_Z if (la, lo) == (LAT0, LON0) else VALLEY_Z


def _rows(dump, tmp_path, ends=(END,), reach=900.0):
    plan = types.SimpleNamespace(units=(), contacts=(), flat=None, authored_seats=())
    ss = types.SimpleNamespace(unit_seats=())
    return PW.dump_rows(dump, plan, ss, (), _surface, str(tmp_path), tol_m=0.02,
                        runway_ends=ends, approach_reach_m=reach,
                        approach_heading_deg=5.0)


def _lights(tmp_path, lat, lon, heading=46.99):
    pier = _obj(tmp_path, "pier.obj", -93.3, 0.5)       # piers into the valley
    bar = _obj(tmp_path, "bar.obj", -2.7, 0.4)
    return types.SimpleNamespace(placements=[_row(pier, lat, lon, heading),
                                             _row(bar, lat, lon, heading)])


def test_an_approach_light_set_is_seated_at_the_runway_end(tmp_path):
    """KCRW 23: the set 21 m past the end, its piers 93 m below its origin.
    Draped it sat at the valley's 260.48; its origin now stands at the
    runway end's solved elevation, both rows at one elevation."""
    dump = _lights(tmp_path, *_at(20.9, 0.4))
    conv, msl, _r, counts = _rows(dump, tmp_path)
    assert not conv
    assert sorted(m.index for m in msl) == [0, 1]
    assert {m.why for m in msl} == {CS.CENTRELINE_END}
    assert all(abs(m.elevation - END_Z) < 1e-9 for m in msl)
    assert counts["centreline_end_sets"] == 1 and counts["centreline_end_seated"] == 2


def test_the_reciprocal_heading_reads_along_the_axis(tmp_path):
    dump = _lights(tmp_path, *_at(300.0), heading=226.99)
    _c, msl, _r, _n = _rows(dump, tmp_path)
    assert len(msl) == 2


def test_off_the_centreline_or_across_it_or_short_of_the_end_it_drapes(tmp_path):
    """Each witness alone withholds the seat: the origin off the axis by
    more than the half width, a heading across it, on the runway side of
    the end, or past the approach reach — the set keeps Q54's conversion."""
    for where, heading in ((_at(50.0, 30.0), 46.99), (_at(50.0), 90.0),
                           (_at(-50.0), 46.99), (_at(950.0), 46.99)):
        dump = _lights(tmp_path, *where, heading=heading)
        conv, msl, _r, _n = _rows(dump, tmp_path)
        assert not [m for m in msl if m.why == CS.CENTRELINE_END], (where, heading)
        assert len(conv) == 2


def test_a_set_standing_on_its_origin_is_msl_feet_s(tmp_path):
    """A set NOT built around its origin is read by its feet (owner answer
    48), never by this rule."""
    mast = _obj(tmp_path, "mast.obj", 0.0, 8.0)
    lat, lon = _at(60.0)
    dump = types.SimpleNamespace(placements=[_row(mast, lat, lon)])
    conv, msl, _r, counts = _rows(dump, tmp_path)
    assert not msl and len(conv) == 1             # its feet ARE the drape
    assert counts["msl_feet_left_to_the_drape"] == 1
    assert counts["centreline_end_seated"] == 0


def test_no_runway_ends_or_no_reach_disarms(tmp_path):
    dump = _lights(tmp_path, *_at(20.9))
    for ends, reach in (((), 900.0), ((END,), 0.0)):
        conv, msl, _r, _n = _rows(dump, tmp_path, ends=ends, reach=reach)
        assert not msl and len(conv) == 2


def test_runway_ends_ll_names_both_ends_with_the_axis():
    e = lambda n, ll: types.SimpleNamespace(name=n, ll=ll)  # noqa: E731
    rw = types.SimpleNamespace(id="05/23", width_m=45.72,
                               ends=(e("05", (38.0, -81.0)), e("23", (38.01, -80.99))))
    a, b = CS.runway_ends_ll(types.SimpleNamespace(runways=(rw,)))
    assert (a["end"], a["far_lat"], b["end"], b["far_lat"]) == ("05", 38.01, "23", 38.0)
    assert a["half_width_m"] == b["half_width_m"] == 22.86
