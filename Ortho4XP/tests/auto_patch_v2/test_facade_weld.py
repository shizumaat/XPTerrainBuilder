"""Issue #127 (flat-pad spec §7; HECA T3 30.1110593, 31.404281): a body
§15's carrier search leaves with NO carrier rides the carrier of the body
it is WELDED to — never the ground under its own footprint while its
wall is written at another zero.

At HECA T3 eleven single-pane ``glass_blue_2`` / ``metal_dark`` bodies
were welded only to ``T2_Brick`` b4, itself CARRIED by ``door`` b27.  The
search offers FOOTED candidates only, so the panes found nothing, fell to
§16 (3)'s own ground (103.6-103.9) and stepped 1.1-1.44 m against the
brick wall written at 102.48 — the site's 11 STOP pairs.
"""
from __future__ import annotations

import os

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import placement_carrier as _PC
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.airport.placement_targets import welded_carriers


# ── the pure rule ───────────────────────────────────────────────────────

def _c(member, feet=4, group=0):
    a = AR.Anchor(AR.BUILDING, 40.0, -3.0, 0.0, "r", 100.0 + member)
    return _PC.Candidate(member, f"objects/m{member}.obj", a,
                         frozenset({1000 + member}), feet,
                         (40.0, -3.0, 40.0, -3.0), group=group,
                         body_class=AR.BUILDING, fill=1.0, ground_off=0.0)


def test_a_pane_welded_to_a_carried_wall_takes_the_walls_carrier():
    door = _c(0)
    # pid 1 is the carried brick wall (on the door); pid 2 the pane
    got = welded_carriers([{2}], {1: door}, [(1, 2)])
    assert got[0][0] is door
    assert "welded" in got[0][1]


def test_two_facades_welded_to_each_other_share_one_carrier():
    door = _c(0)
    # pane 20 touches the wall, pane 30 touches only pane 20
    got = welded_carriers([{30}, {20}], {1: door}, [(1, 20), (20, 30)])
    assert got[0][0] is door and got[1][0] is door
    assert "hop 2" in got[0][1] and "hop 1" in got[1][1]


def test_the_most_welds_win_and_the_order_never_decides():
    a, b = _c(0), _c(1)
    placed = {1: a, 2: b, 3: b}
    contacts = [(1, 9), (2, 9), (3, 9)]
    assert welded_carriers([{9}], placed, contacts)[0][0] is b
    # a tie goes to the carrier with the most feet, whatever the order
    big = _c(2, feet=40)
    for pl in ({1: a, 4: big}, {4: big, 1: a}):
        assert welded_carriers([{9}], pl, [(1, 9), (4, 9)])[0][0] is big


def test_a_body_welded_to_nothing_placed_keeps_its_own_ground():
    assert welded_carriers([{5}, {6}], {1: _c(0)}, [(5, 6)]) == {}
    assert welded_carriers([{5}], {}, []) == {}


# ── the plan stage, end to end ──────────────────────────────────────────

def _box(x0, z0, y0, side=4.0, h=3.0):
    v = [(x0, y0, z0), (x0 + side, y0, z0), (x0 + side, y0, z0 + side),
         (x0, y0, z0 + side), (x0, y0 + h, z0), (x0 + side, y0 + h, z0),
         (x0 + side, y0 + h, z0 + side), (x0, y0 + h, z0 + side)]
    t = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6), (0, 4, 5), (0, 5, 1),
         (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0)]
    return v, t


def _obj(path, x0, z0, y0):
    v, t = _box(x0, z0, y0)
    idx = [i for tri in t for i in tri]
    out = ["I", "800", "OBJ", "", "TEXTURE\ttest.dds",
           f"POINT_COUNTS\t{len(v)} 0 0 {len(idx)}", ""]
    out += [f"VT\t{x:.3f} {y:.3f} {z:.3f}\t0.0 1.0 0.0\t0.0 0.0"
            for x, y, z in v]
    out.append("")
    for i in range(0, len(idx) - len(idx) % 10, 10):
        out.append("IDX10\t" + " ".join(str(q) for q in idx[i:i + 10]))
    out += [f"IDX\t{q}" for q in idx[len(idx) - len(idx) % 10:]]
    out += ["", "ATTR_no_blend", f"TRIS\t0 {len(idx)}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _plan(tmp_path, weld=True):
    """Three members of one unit at 40N 3W: a WALL on the ground, a BRICK
    band resting on it (carried, no feet), and a PANE 30 m north at the
    brick's height, welded to the brick only and standing over nothing."""
    from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit

    lat, lon = 40.0, -3.0
    ml, mo = AR._m_per_deg(lat)
    spec = [("wall", 0.0, 0.0, 0.0, True),
            ("brick", 0.0, 0.0, 3.0, False),
            ("pane", 0.0, -30.0, 3.0, False)]
    mem = []
    for pid, (name, x0, z0, y0, footed) in enumerate(spec):
        p = _obj(tmp_path / f"{name}.obj", x0, z0, y0)
        la0, la1 = lat - (z0 + 4.0) / ml, lat - z0 / ml
        lo0, lo1 = lon + x0 / mo, lon + (x0 + 4.0) / mo
        cl, co = 0.5 * (la0 + la1), 0.5 * (lo0 + lo1)
        feet = tuple((la, lo, 0.0) for la in (la0, la1) for lo in (lo0, lo1)) \
            if footed else ()
        mem.append(Member(id=f"dsf:obj{pid}",
                          resource=f"objects/{name}.obj",
                          authored_path=p, live_path=p, heading_deg=0.0,
                          parts=(Part(pid=pid, comp=0, lat=cl, lon=co,
                                      base_y=y0, area_m2=16.0,
                                      box=(la0, lo0, la1, lo1), feet=feet),)))
    return RebakePlan(icao="TEST", pack_name="pack", pack_root=str(tmp_path),
                      units=(Unit("u0", (lat, lon), 0.0, tuple(mem)),),
                      skipped=(), counts={},
                      contacts=((1, 2),) if weld else ())


def _surface(lat, lon):
    # the pane's own ground stands 1.5 m over the wall's
    return 101.5 if lat > 40.0 + 10.0 / AR._m_per_deg(40.0)[0] else 100.0


def _zero_of(ss, name):
    for s in ss.all:
        if os.path.basename(s.resource) == f"{name}.obj":
            b = s.bodies[0]
            return float(b.anchor.surface_z) - float(b.anchor.y_zero), b
        for b in s.bodies:
            if any(os.path.basename(str(q)).startswith(name)
                   for q in (getattr(b, "new_resource", ""),)):
                return (float(b.anchor.surface_z) - float(b.anchor.y_zero), b)
    raise AssertionError(name)


def _args():
    return dict(split_tol_m=0.3, elevated_base_m=0.5, bind_ground_m=0.5)


def test_the_welded_pane_rides_the_bricks_carrier_end_to_end(tmp_path):
    ss = PP.build_splits(_plan(tmp_path), _surface, write=False, **_args())
    assert ss.counts.get("footless_rides_weld") == 1
    assert ss.counts.get("footless_own_ground", 0) == 0
    zb, _ = _zero_of(ss, "brick")
    zp, bp = _zero_of(ss, "pane")
    assert abs(zb - zp) < 1e-6, (zb, zp)
    assert "welded" in bp.anchor.reason


def test_without_the_weld_the_pane_keeps_its_own_ground(tmp_path):
    ss = PP.build_splits(_plan(tmp_path, weld=False), _surface, write=False,
                         **_args())
    assert not ss.counts.get("footless_rides_weld")
    assert ss.counts.get("footless_own_ground") == 1
    zp, bp = _zero_of(ss, "pane")
    assert abs(zp - 101.5) < 1e-6
