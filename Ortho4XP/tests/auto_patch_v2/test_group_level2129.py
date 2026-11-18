"""RULINGS 2026-11-18h (#2129, owner: "Why is the building tilted?  It
should be flat"): a body of a BUILDING GROUP is never seat-tilted.  A
hall carrying a roof shares its frame with it (§16a), so the fit that
would rotate the hall over a 1.5 % grade leaves it LEVEL, its seat marked
``levelled`` for the touch pass, and the roof rides it level — whatever
order the members are cut in (#2060 r3's T1 cycle, the retired
14p (1) frame tilt's case).
"""
from __future__ import annotations

import os
import re

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import obj8_grade as OG
from auto_patch_v2.airport import placement_plan as PP

LAT, LON = 40.0, -3.0
ML, MO = AR._m_per_deg(LAT)
GRADE = 0.015                       # 0.86 deg, under both caps
Z0 = 100.0


def _surface(la: float, lo: float) -> float:
    return Z0 + GRADE * ((lo - LON) * MO)


def _box(x0, z0, y0, sx, sz, h):
    v = [(x0, y0, z0), (x0 + sx, y0, z0), (x0 + sx, y0, z0 + sz),
         (x0, y0, z0 + sz), (x0, y0 + h, z0), (x0 + sx, y0 + h, z0),
         (x0 + sx, y0 + h, z0 + sz), (x0, y0 + h, z0 + sz)]
    t = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
         (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return v, t


def _obj(path, boxes):
    v: list = []
    t: list = []
    for b in boxes:
        bv, bt = _box(*b)
        t += [(p + len(v), q + len(v), r + len(v)) for p, q, r in bt]
        v += bv
    idx = [i for tri in t for i in tri]
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(v)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t0.0 0.0" for x, y, z in v]
    out.append("")
    for i in range(0, len(idx) - len(idx) % 10, 10):
        out.append("IDX10\t" + " ".join(str(q) for q in idx[i:i + 10]))
    out += [f"IDX\t{q}" for q in idx[len(idx) - len(idx) % 10:]]
    out += ["", "ATTR_no_blend", f"TRIS\t0 {len(idx)}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _part(pid, comp, box, footed):
    """``box`` = (x0, z0, y0, sx, sz, h) in the unit's authored frame."""
    from auto_patch_v2.model.rebake import Part
    x0, z0, y0, sx, sz, _h = box
    la0, la1 = LAT - (z0 + sz) / ML, LAT - z0 / ML
    lo0, lo1 = LON + x0 / MO, LON + (x0 + sx) / MO
    feet = (tuple((la, lo, y0) for la in (la0, 0.5 * (la0 + la1), la1)
                  for lo in (lo0, 0.5 * (lo0 + lo1), lo1)) if footed else ())
    return Part(pid=pid, comp=comp, lat=0.5 * (la0 + la1), lon=0.5 * (lo0 + lo1),
                base_y=y0, area_m2=sx * sz, box=(la0, lo0, la1, lo1), feet=feet)


def _hall(x0):
    """a footed 60 m hall (+-0.45 m about its anchor: over the foot tolerance)"""
    return (x0, 0.0, 0.0, 60.0, 20.0, 3.0)


def _roof(x0):
    """a roof slab resting on the hall at ``x0``"""
    return (x0 + 2.0, 2.0, 3.0, 16.0, 16.0, 0.3)


def _plan(tmp_path, spec):
    """``spec``: ``(name, own hall x0, x0 of the hall its roof rests on)``."""
    from auto_patch_v2.model.rebake import Member, RebakePlan, Unit
    mem = []
    pid = 0
    for name, hall_x, roof_x in spec:
        hall, roof = _hall(hall_x), _roof(roof_x)
        # the reader numbers the components west to east
        boxes = sorted([hall, roof])
        p = _obj(tmp_path / f"{name}.obj", boxes)
        parts = (_part(pid, boxes.index(hall), hall, True),
                 _part(pid + 1, boxes.index(roof), roof, False))
        pid += 2
        mem.append(Member(id=f"dsf:{name}", resource=f"objects/{name}.obj",
                          authored_path=p, live_path=p, heading_deg=0.0,
                          parts=parts, base_profile={"verdict": OG.FEET}))
    return RebakePlan(icao="TEST", pack_name="pack", pack_root=str(tmp_path),
                      units=(Unit("u0", (LAT, LON), 0.0, tuple(mem)),),
                      skipped=(), counts={}, contacts=())


def _build(tmp_path, spec):
    return PP.build_splits(_plan(tmp_path, spec), _surface, write=False,
                           split_tol_m=0.3, elevated_base_m=0.5, foot_band_m=1.0,
                           bind_ground_m=0.5, seat_tilt_max_deg=1.5)


def _bodies(ss):
    """``{(resource basename, body id): body}`` of every written body."""
    return {(os.path.basename(s.resource), b.body_id): b
            for s in ss.splits for b in s.bodies}


CYCLE = [("a", 0.0, 80.0), ("b", 80.0, 0.0)]


def _carriers_level(ss, alone=()):
    """every hall that carries a roof is written level, its seat marked;
    a hall carrying nothing (``alone``) keeps 10-01k Q1's tilt"""
    bodies = _bodies(ss)
    carried = {re.sub(r"_[0-9a-f]{8}\.obj$", ".obj", b.merged_into)
               for b in bodies.values() if b.merged_into}
    assert carried, "no rider"
    for (res, _k), b in bodies.items():
        if not b.feet:
            assert b.seat is None or not b.seat.applied, res
        elif res in alone:
            assert b.seat.applied and not b.seat.levelled, res
        else:
            assert f"objects/{res[:-4]}__b0.obj" in carried, res
            assert not b.seat.applied and b.seat.levelled, res


def test_a_carried_frame_is_written_level_in_either_order(tmp_path):
    (tmp_path / "ab").mkdir()
    (tmp_path / "ba").mkdir()
    for ss in (_build(tmp_path / "ab", CYCLE), _build(tmp_path / "ba", CYCLE[::-1])):
        _carriers_level(ss)
        assert ss.counts.get("seat_tilt_applied", 0) == 0


def test_a_hall_carrying_nothing_keeps_its_tilt_the_shelters_case(tmp_path):
    ss = _build(tmp_path, [("c", 160.0, 0.0)] + CYCLE)
    _carriers_level(ss, alone=("c.obj",))
    assert ss.counts["seat_tilt_applied"] == 1
