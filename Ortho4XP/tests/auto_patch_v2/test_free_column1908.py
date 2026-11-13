"""#1908 A FREE-STANDING COLUMN STANDS ON ITS OWN FOOT
(``airport/free_column``), and #972's wet seat never floats a foot over
the water it stands in (``anchor_rule._wet_body_anchor``).

ENTC's ``ALS.obj``: approach-light masts authored 4.44-6.06 m over the
placement's zero (the author's terrain profile), nothing under them —
they stood 4.4-11 m over the shore.  Synthetic and hermetic: one OBJ8
with a footed box at the origin and a 1 m mast 60 m north whose foot is
authored 4.44 m up, read through the engine's own parser."""
from __future__ import annotations

import math
import os

import pytest
from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import free_column as FC
from auto_patch_v2.airport import obj8
from auto_patch_v2.airport import placement_plan as PP
from auto_patch_v2.model.rebake import Member, Part, RebakePlan, Unit
from test_v2objsplit import _box, _write_obj  # noqa: E402

LAT, LON = 40.0, -3.0
LAW = FC._ColumnLaw(min_h_m=2.0, max_w_m=2.0, aspect=3.0, clear_m=0.5)
ARGS = dict(split_tol_m=0.3, elevated_base_m=0.5, bind_ground_m=0.5,
            coarsen_reach_m=100.0)


def _prism(x0, z0, w, y0, y1):
    """A closed box ``w`` wide from ``y0`` to ``y1``."""
    v, t = _box(x0, z0, side=w, h=1.0)
    return [(x, y0 + y * (y1 - y0), z) for x, y, z in v], t


def _obj(tmp_path, *, slab=False):
    shapes = [_prism(0.0, 0.0, 4.0, 0.0, 3.0),            # footed, at the origin
              _prism(0.0, -60.0, 1.0, 4.44, 11.27)]       # the mast, 60 m north
    if slab:                                             # a host under the mast
        shapes.append(_prism(-1.0, -61.0, 3.0, 0.0, 0.2))
    verts, tris = [], []
    for v, t in shapes:
        tris += [(a + len(verts), b + len(verts), c + len(verts)) for a, b, c in t]
        verts += v
    return _write_obj(tmp_path / "als.obj", verts, [("", tris)])


def _plan(path):
    """One member, one part per solid component (the plan's own fields)."""
    g = obj8.parse_obj8(str(path))
    ml, mo = AR._m_per_deg(LAT)
    parts = []
    for ci, c in enumerate(obj8.solid_components(g)):
        v = g.vertices[sorted({int(i) for i in c.tris.reshape(-1)})]
        x0, x1 = float(v[:, 0].min()), float(v[:, 0].max())
        z0, z1 = float(v[:, 2].min()), float(v[:, 2].max())
        y0, y1 = float(v[:, 1].min()), float(v[:, 1].max())
        box = (LAT - z1 / ml, LON + x0 / mo, LAT - z0 / ml, LON + x1 / mo)
        la, lo = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
        feet = ((la, lo, y0),) if y0 <= 0.5 else ()
        parts.append(Part(pid=ci, comp=ci, lat=la, lon=lo, base_y=y0,
                          area_m2=(x1 - x0) * (z1 - z0), box=box, feet=feet,
                          height_m=y1 - y0))
    m = Member(id="dsf:obj1", resource="objects/als.obj", authored_path=str(path),
               live_path=str(path), heading_deg=0.0, parts=tuple(parts))
    return RebakePlan(icao="TEST", pack_name="pack", pack_root=os.path.dirname(str(path)),
                      units=(Unit("u0", (LAT, LON), 0.0, (m,)),), skipped=(), counts={})


def _mast(ss):
    """The body holding the mast (the part whose base is 4.44)."""
    for s in ss.all:
        for b in s.bodies:
            if b.anchor.surface_z is not None and b.plan_box and b.plan_box[0] > LAT + 50 / 111000:
                return b
    raise AssertionError("no mast body")


def _slope(lat, lon):
    return 10.0 + (lat - LAT) * 111000.0 * 0.05        # 5 % up to the north


def test_column_of_reads_a_tall_thin_lowest_part():
    ml, mo = AR._m_per_deg(LAT)
    box = (LAT, LON, LAT + 1 / ml, LON + 1 / mo)
    mast = Part(pid=1, comp=1, lat=LAT, lon=LON, base_y=4.44, area_m2=1.0, box=box,
                height_m=6.83)
    bar = Part(pid=2, comp=2, lat=LAT, lon=LON, base_y=11.2, area_m2=8.0, box=box,
               height_m=0.1)
    assert FC._column_of([bar, mast], LAW) is mast
    wide = Part(pid=3, comp=3, lat=LAT, lon=LON, base_y=4.44, area_m2=36.0,
                box=(LAT, LON, LAT + 6 / ml, LON + 6 / mo), height_m=6.83)
    assert FC._column_of([wide], LAW) is None                  # a block, not a mast
    leg2 = Part(pid=4, comp=4, lat=LAT, lon=LON, base_y=4.6, area_m2=1.0, box=box,
                height_m=6.6)
    assert FC._column_of([mast, leg2], LAW) is None            # a gantry: two legs
    assert FC._column_of([Part(pid=5, comp=5, lat=LAT, lon=LON, base_y=4.4, area_m2=1.0,
                              box=box)], LAW) is None          # no height: a pre-field plan


def test_a_free_mast_stands_on_its_own_foot(tmp_path):
    plan = _plan(_obj(tmp_path))
    on = _mast(PP.build_splits(plan, _slope, write=False, free_column=LAW, **ARGS))
    assert FC.FREE_COLUMN in on.anchor.reason
    assert on.anchor.y_zero == pytest.approx(4.44, abs=1e-6)
    # the foot (authored y 4.44) lands ON the ground under the mast
    g = _slope(on.anchor.lat, on.anchor.lon)
    assert on.anchor.surface_z == pytest.approx(g, abs=0.05)
    assert on.anchor.offset[1] == pytest.approx(4.44, abs=1e-6)


def test_disarmed_the_mast_keeps_its_authored_lift(tmp_path):
    plan = _plan(_obj(tmp_path))
    ss = PP.build_splits(plan, _slope, write=False, **ARGS)
    assert not any(FC.FREE_COLUMN in b.anchor.reason
                   for s in ss.all for b in s.bodies)
    assert ss.counts.get("free_columns", 0) == 0


def test_a_mast_over_a_host_stays_with_its_group(tmp_path):
    """13r: any doubt — a slab of its own unit under its foot — and the
    mast is not free."""
    plan = _plan(_obj(tmp_path, slab=True))
    ss = PP.build_splits(plan, _slope, write=False, free_column=LAW, **ARGS)
    assert ss.counts.get("free_columns", 0) == 0
    assert not any(FC.FREE_COLUMN in b.anchor.reason
                   for s in ss.all for b in s.bodies)


def test_part_index_hosts_any_other_unit_overlap():
    ml, mo = AR._m_per_deg(LAT)
    box = (LAT, LON, LAT + 1 / ml, LON + 1 / mo)
    mast = Part(pid=0, comp=0, lat=LAT, lon=LON, base_y=4.44, area_m2=1.0, box=box,
                height_m=6.83)
    roof = Part(pid=7, comp=0, lat=LAT, lon=LON, base_y=20.0, area_m2=1.0, box=box,
                height_m=1.0)
    m0 = Member(id="a", resource="a.obj", authored_path="a", live_path="a",
                heading_deg=0.0, parts=(mast,))
    m1 = Member(id="b", resource="b.obj", authored_path="b", live_path="b",
                heading_deg=0.0, parts=(roof,))
    one = RebakePlan(icao="T", pack_name="p", pack_root="/", skipped=(), counts={},
                     units=(Unit("u0", (LAT, LON), 0.0, (m0, m1)),))
    two = RebakePlan(icao="T", pack_name="p", pack_root="/", skipped=(), counts={},
                     units=(Unit("u0", (LAT, LON), 0.0, (m0,)),
                            Unit("u1", (LAT, LON), 0.0, (m1,))))
    # same unit, ABOVE the foot: not a host; another unit: doubt
    assert not FC.PartIndex(one).hosts(mast, 0, {0}, 0.5)
    assert FC.PartIndex(two).hosts(mast, 0, {0}, 0.5)


def test_fallback_only():
    assert FC.fallback_only([(None, "nearest footed body of the unit (60 m)")])
    assert FC.fallback_only([(None, "the unit's largest footed body")])
    assert not FC.fallback_only([(None, "stands over 4 m2 of it in plan")])
    assert not FC.fallback_only([])


# ── #972 refined: the wet seat never floats a foot ────────────────────────

def _wet_surface():
    def surface(la, lo):
        return 0.0 if la >= 40.001 else 6.5
    surface.water = lambda la, lo: la >= 40.001
    return surface


def _wet_body(foot_y):
    feet = tuple((la, LON, foot_y) for la in (40.002, 40.003))
    return AR.BodyGeometry(((feet[0][0], LON, foot_y, feet),), LAT, LON)


def test_a_wet_seat_that_floats_its_feet_is_not_the_authors():
    """ALS.obj's sea masts: feet at y -0.2, origin on land at 6.5 — the
    'authored seat' (agl 0 at the origin) stood them 6.3 m over the sea."""
    a = AR.anchor_for(AR.OTHER, _wet_body(-0.2), _wet_surface(), tol_m=0.3,
                      authored_agl_m=0.0)
    assert not a.datum and "on water" not in a.reason
    assert a.surface_z - a.y_zero + (-0.2) == pytest.approx(0.0, abs=1e-6)


def test_a_wet_seat_under_the_water_line_is_kept():
    """#972's own seawall: the authored seat puts the feet under water."""
    a = AR.anchor_for(AR.OTHER, _wet_body(-23.5), _wet_surface(), tol_m=0.3,
                      authored_agl_m=-4.4)
    assert a.datum and "on water" in a.reason and a.y_zero == 4.4
    assert math.isclose(a.surface_z, 6.5)


def test_a_lone_mast_is_no_field_of_masts(tmp_path):
    """A lone post of a building stays with its group: the class is the
    placement whose elevated bodies are mostly free columns."""
    import dataclasses
    plan = _plan(_obj(tmp_path))
    law = dataclasses.replace(LAW, min_count=3, min_share=0.5)
    ss = PP.build_splits(plan, _slope, write=False, free_column=law, **ARGS)
    assert ss.counts.get("free_columns", 0) == 0
