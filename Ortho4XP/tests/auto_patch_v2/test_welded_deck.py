"""Twins for THE WELDED DECK (issue #14; ``docs/specs/welded-deck-spec.md``
§1-§2, §6 (a)-(g)) — lane ``weldeddeck``.

A hard deck welded into a unit of buildings is a DECK when what stands
under its plate — the section halfway between the unit's zero and the
plate, each member's trace hole-filled ALONE — covers at most
``[bridge] deck_pier_footprint_max`` of its ring; its SHADE (ring minus
that section) leaves every cluster outline at the one outline site, and a
welded deck lends no datum.  Synthetic OBJ8 files under ``tmp_path``; law
values are read from the tables, never retyped.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import Polygon, box

from auto_patch_v2.airport import deck_signature as ds
from auto_patch_v2.airport import obj8
from auto_patch_v2.geom import cluster_outlines, deck_shades
from auto_patch_v2.law import Law
from auto_patch_v2.model.rebake import Member, RebakePlan, Unit

LAW = Law.for_airport("ZZZZ")
BR = LAW.tables.structures.bridge


# ── synthetic OBJ8 ──────────────────────────────────────────────────────

def _quad(vt, tris, a, b, c, d):
    i = len(vt)
    vt.extend((a, b, c, d))
    tris.extend(((i, i + 1, i + 2), (i, i + 2, i + 3)))


def _wall(vt, tris, x0, z0, x1, z1, y0, y1):
    _quad(vt, tris, (x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0))


def _slab(vt, tris, x0, z0, x1, z1, y):
    _quad(vt, tris, (x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1))


def _box(vt, tris, x0, z0, x1, z1, y0, y1, walls=(0, 1, 2, 3)):
    sides = [(x0, z0, x1, z0), (x1, z0, x1, z1), (x1, z1, x0, z1), (x0, z1, x0, z0)]
    for k in walls:
        _wall(vt, tris, *sides[k], y0, y1)


def _write(path, vt, tris, hard=()):
    """An OBJ8 of ``tris`` over ``vt``; the triangles at indices ``hard``
    are emitted under ``ATTR_hard_deck`` (the flag signature)."""
    soft = [t for k, t in enumerate(tris) if k not in set(hard)]
    deck = [t for k, t in enumerate(tris) if k in set(hard)]
    idx = [i for t in soft + deck for i in t]
    lines = ["A", "800", "OBJ", "", "TEXTURE none",
             f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
    lines += [f"VT {x:.3f} {y:.3f} {z:.3f} 0 1 0 0 0" for x, y, z in vt]
    lines += ["IDX " + " ".join(str(i) for i in idx[k:k + 10]) for k in range(0, len(idx), 10)]
    if soft:
        lines.append(f"TRIS 0 {3 * len(soft)}")
    if deck:
        lines.append("ATTR_hard_deck concrete")
        lines.append(f"TRIS {3 * len(soft)} {3 * len(deck)}")
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def _placed(oid, path, deck_ring=None, xy=(0.0, 0.0), anchor_z=100.0, agl=0.0):
    """A placement at heading 0: authored ``(x, z)`` -> frame ``(x, -z)``
    (OBJ8 ``z`` points south)."""
    return obj8.PlacedObject(oid, path, path, xy, 0.0, agl, "OBJECT", anchor_z,
                             None, None, None, None, deck_ring,
                             None if deck_ring is None else anchor_z + agl,
                             (), "flag" if deck_ring is not None else "")


def _cache():
    return obj8.ResourceCache(LAW.tables.structures.basin.min_solid_thickness_m)


def _deck_obj(tmp_path, name, y, columns=True, x0=40.0, x1=70.0, z0=0.0, z1=30.0):
    """A 30 x 30 m slab at ``y`` (a hard-deck plate, both faces), on four
    1 x 1 m columns at its corners when ``columns``."""
    vt, tris = [], []
    _slab(vt, tris, x0, z0, x1, z1, y)
    _slab(vt, tris, x0, z0, x1, z1, y - 0.5)
    hard = range(len(tris))
    if columns:
        for cx, cz in ((x0 + 2, z0 + 2), (x1 - 3, z0 + 2), (x0 + 2, z1 - 3), (x1 - 3, z1 - 3)):
            _box(vt, tris, cx, cz, cx + 1.0, cz + 1.0, 0.0, y - 0.5)
    return _write(tmp_path / name, vt, tris, hard=list(hard))


def _building_obj(tmp_path, name, x0=0.0, x1=40.0, z0=0.0, z1=30.0, h=20.0, walls=(0, 1, 2, 3)):
    vt, tris = [], []
    _box(vt, tris, x0, z0, x1, z1, 0.0, h, walls)
    return _write(tmp_path / name, vt, tris)


def _ring(x0=40.0, z0=0.0, x1=70.0, z1=30.0):
    """The frame ring of the authored plan box ``x0..x1 × z0..z1``."""
    return box(x0, -z1, x1, -z0)


# ── (a)-(d): the pier reading ───────────────────────────────────────────

def test_a_a_slab_on_four_columns_welded_to_a_building_is_a_DECK(tmp_path):
    """(a) a box building and a slab on four columns WELDED to its wall:
    the section under the plate is the four columns and the building's
    one wall on the ring's edge — a DECK, its shade the ring minus the
    column blobs."""
    c = _cache()
    b = _placed("b", _building_obj(tmp_path, "b.obj"))
    d = _placed("d", _deck_obj(tmp_path, "d.obj", 8.0), deck_ring=_ring())
    r = ds.welded_deck(c, [b, d], d, LAW)
    assert r is not None and r.deck, r
    assert r.ratio < BR.deck_pier_footprint_max
    assert r.plate_y == pytest.approx(8.0)
    D = _ring()
    assert r.shade is not None and r.shade.within(D.buffer(1e-6))
    # the columns (4 m2) leave the shade, nothing else of D does beyond
    # the cell quantum along the welded wall and round each column
    lost = D.area - r.shade.area
    assert 4.0 <= lost <= BR.deck_pier_footprint_max * D.area, lost
    for cx, cz in ((42.5, 2.5), (67.5, 2.5), (42.5, 27.5), (67.5, 27.5)):
        assert not r.shade.contains(Polygon.from_bounds(cx - 0.4, -cz - 0.4, cx + 0.4, -cz + 0.4))
    assert r.shade.contains(Polygon.from_bounds(50, -20, 60, -10))


def test_b_the_same_slab_on_a_walled_box_casts_no_shade(tmp_path):
    """(b) the same slab standing on its OWN four walls: the section fills
    the ring — WALLED, no shade (a road inside walls under a deck, OTHH
    02_000 / 03_000)."""
    c = _cache()
    vt, tris = [], []
    _slab(vt, tris, 40, 0, 70, 30, 8.0)
    n = len(tris)
    _box(vt, tris, 40, 0, 70, 30, 0.0, 7.5)
    d = _placed("d", _write(tmp_path / "w.obj", vt, tris, hard=list(range(n))), deck_ring=_ring())
    r = ds.welded_deck(c, [d], d, LAW)
    assert r is not None and not r.deck and r.shade is None
    assert r.ratio > 0.9


def test_c_walls_that_only_JOINTLY_enclose_the_section_are_filled_per_member(tmp_path):
    """(c) two members whose walls close a loop round the ring only
    TOGETHER (each an L): per-member fill reads each L as a trace, not an
    enclosure — still a DECK.  The joint fill is refuted (spec §1 (2):
    HECA's parapet + façade read 0.683 jointly against 0.093)."""
    c = _cache()
    a = _placed("a", _building_obj(tmp_path, "a.obj", 40, 70, 0, 30, h=12.0, walls=(0, 3)))
    b = _placed("b", _building_obj(tmp_path, "b.obj", 40, 70, 0, 30, h=12.0, walls=(1, 2)))
    d = _placed("d", _deck_obj(tmp_path, "d.obj", 8.0, columns=False), deck_ring=_ring())
    r = ds.welded_deck(c, [a, b, d], d, LAW)
    assert r is not None and r.deck, r
    assert r.ratio < BR.deck_pier_footprint_max
    # ...while ONE member carrying all four walls is walled
    w = _placed("w", _building_obj(tmp_path, "w.obj", 40, 70, 0, 30, h=12.0))
    assert not ds.welded_deck(c, [w, d], d, LAW).deck


def test_d_a_plate_under_H_casts_no_shade(tmp_path):
    """(d) a plate under ``deck_min_elevation_m`` over the unit's zero is
    a slab on the ground: the rule does not apply."""
    c = _cache()
    y = BR.deck_min_elevation_m - 0.5
    d = _placed("d", _deck_obj(tmp_path, "d.obj", y), deck_ring=_ring())
    r = ds.welded_deck(c, [d], d, LAW)
    assert r is not None and not r.deck and r.shade is None
    assert "slab on the ground" in r.note


def test_the_plate_is_read_over_the_UNIT_zero_not_the_resource_floor(tmp_path):
    """§1 (1): a deck authored as a slab alone at y 10.75-12.64 (OTHH
    01_001: no column of its own, ``elevated_deck`` False) reads its plate
    over y = 0 — the unit's zero — and the section at half that height
    through a neighbour's columns."""
    c = _cache()
    vt, tris = [], []
    _slab(vt, tris, 40, 0, 70, 30, 12.5)
    _slab(vt, tris, 40, 0, 70, 30, 10.75)
    d = _placed("d", _write(tmp_path / "s.obj", vt, tris, hard=list(range(len(tris)))),
                deck_ring=_ring())
    vt2, tris2 = [], []
    for cx in (45.0, 60.0):
        _box(vt2, tris2, cx, 10.0, cx + 1.0, 11.0, -2.2, 10.75)
    cols = _placed("cols", _write(tmp_path / "c.obj", vt2, tris2))
    r = ds.welded_deck(c, [cols, d], d, LAW)
    assert r.plate_y == pytest.approx(12.5)
    assert r.deck and r.ratio < 0.05
    assert not ds.elevated_deck(c, d.resolved, LAW).deck


# ── (e): the region rule at the one outline site ────────────────────────

class _Cl:
    def __init__(self, cid, rings):
        self.id = cid
        self.rings = tuple(rings)
        self.area_m2 = 20000.0
        self.floors = (0.0,)
        self.walled = 1


def _sq(x0, y0, x1, y1):
    return ((y0, x0), (y0, x1), (y1, x1), (y1, x0))


class _Part:
    def __init__(self, units):
        self.units = units


def _ident(lon, lat):
    return (float(lon), float(lat))


def _shaded_member(poly):
    ext = tuple((y, x) for x, y in poly.exterior.coords[:-1])
    return Member("d", "d.obj", "d", "d", 0.0, deck_kind="flag",
                  deck_shade_ring=((ext,),), deck_pier_ratio=0.03)


def test_e_rule_6_subtracts_the_shade_AFTER_the_close(tmp_path):
    """(e) ``cluster_outlines`` subtracts the shade after rule 2's close:
    a shade narrower than the close (0.6 m at touch 0.5) still cuts the
    outline — subtracted before the close, the dilate/erode refilled it."""
    touch = 0.5
    shade = Polygon.from_bounds(49.7, -1.0, 50.3, 41.0)
    part = _Part([Unit("unit:0", (0.0, 0.0), 0.0, (_shaded_member(shade),))])
    sh = deck_shades(part, _ident)
    assert sh is not None and sh.area == pytest.approx(shade.area)
    cl = [_Cl("c", [_sq(0, 0, 100, 40)])]
    base, _ = cluster_outlines(cl, _ident, touch)
    got, counts = cluster_outlines(cl, _ident, touch, shades=sh)
    assert len(base) == 1 and base[0][2].area == pytest.approx(4000.0)
    assert len(got) == 2 and counts["deck_trimmed"] == 1
    assert sum(g.area for _i, _c, g in got) == pytest.approx(4000.0 - 0.6 * 40.0)
    assert not any(g.intersects(Polygon.from_bounds(49.8, 1, 50.2, 39)) for _i, _c, g in got)
    # a cluster wholly under a shade mints nothing, counted
    got2, c2 = cluster_outlines([_Cl("u", [_sq(49.8, 5, 50.2, 30)])], _ident, 0.0, shades=sh)
    assert got2 == [] and c2["under_deck"] == 1
    # no shade: identity
    assert cluster_outlines(cl, _ident, touch, shades=None)[0][0][2].equals(base[0][2])


def test_e_a_fallback_footprint_over_the_shade_is_trimmed():
    """(e) §2 (2): a FALLBACK footprint (OSM / ``dsf:fac`` / ``dsf:object``)
    is trimmed by the shades before the cover test — a deck never
    re-enters as a v1 footprint or an OSM ``building=roof``."""
    from auto_patch_v2.classify.evidence import _pads

    class _R:
        class buildings:
            sources = ("osm",)

    class _B:
        source = "osm"
        holes = ()

        def __init__(self, outer):
            self.outer = outer

    class _Frame:
        def entry(self):
            return _ident

    shade = Polygon.from_bounds(40.0, 0.0, 70.0, 30.0)

    class _AP:
        frame = _Frame()
        clusters = ()
        dsf_objects = ()
        partition = _Part([Unit("unit:0", (0.0, 0.0), 0.0, (_shaded_member(shade),))])
        buildings = (_B(((0.0, 0.0), (0.0, 30.0), (70.0, 30.0), (70.0, 0.0))),)

    gate = Polygon.from_bounds(-500, -500, 500, 500)
    empty = Polygon()
    pads, _d, _s = _pads(_AP(), _R, 100.0, gate, empty, empty, law=LAW)
    assert len(pads) == 1
    assert pads[0][1].area == pytest.approx(40.0 * 30.0)
    assert not pads[0][1].intersects(shade.buffer(-0.01))


# ── (f): the plan version ───────────────────────────────────────────────

def test_f_a_v9_plan_loads_with_no_shade_and_v10_round_trips():
    """(f) a plan written at version 9 loads with ``deck_shade_ring`` /
    ``deck_pier_ratio`` None (and so mints as before); version 10 round-
    trips them exactly."""
    ring = (((25.0, 51.0), (25.0, 51.001), (25.001, 51.001), (25.001, 51.0)),
            ((25.0004, 51.0004), (25.0004, 51.0005), (25.0005, 51.0005)))
    m = Member("dsf:obj1", "d.obj", "/a/d.obj", "/a/d.obj", 0.0, deck_kind="flag",
               deck_shade_ring=(ring,), deck_pier_ratio=0.033)
    plan = RebakePlan("ZZZZ", "pack", "/a", (Unit("unit:0", (25.0, 51.0), 0.0, (m,)),),
                      (), {})
    d = plan.to_dict()
    assert d["version"] == 10
    back = RebakePlan.from_dict(d).units[0].members[0]
    assert back.deck_shade_ring == (ring,) and back.deck_pier_ratio == pytest.approx(0.033)
    d9 = dict(d, version=9)
    for u in d9["units"]:
        for mm in u["members"]:
            mm.pop("deck_shade_ring"); mm.pop("deck_pier_ratio")
    old = RebakePlan.from_dict(d9).units[0].members[0]
    assert old.deck_shade_ring is None and old.deck_pier_ratio is None
    assert deck_shades(_Part(RebakePlan.from_dict(d9).units), _ident) is None


# ── (g): a welded deck lends no datum ───────────────────────────────────

def test_g_a_welded_deck_lends_nothing_while_a_bridge_still_lends():
    """(g) §2 (5): a DECK by §1 inside a unit holding a walled non-deck
    body standing outside its ring — a building — lends no datum
    (``deck_datum_lent_to`` 0); a bridge whose walled members are its own
    piers, under its ring, still lends its deck's."""
    from auto_patch_v2.airport import footprint_unit as fu
    from test_v2connector import _PMember, _PPlan, _PUnit, _lat

    lo0, lo1 = -3.0, -2.9996                 # ~34 m of longitude at 41 N
    deck_ring = ((_lat(0), lo0), (_lat(0), lo1), (_lat(30), lo1), (_lat(30), lo0))

    def _mem(name, dz=None, shade=False):
        m = _PMember(name, (), deck_datum_z=dz)
        m.deck_kind = "flag" if dz is not None else ""
        m.deck_ring = deck_ring if dz is not None else None
        m.deck_shade_ring = ((deck_ring,),) if shade else None
        return m

    def _shim(seq, ui, mi, rings, walled=True):
        la = [p[0] for r in rings for p in r]
        lo = [p[1] for r in rings for p in r]
        return fu._PShim(seq, (ui, mi, 0), [(min(la), min(lo), max(la), max(lo))],
                         frozenset({seq}), f"m{mi}", tuple(rings), walled)

    pier = ((_lat(10), -2.9998), (_lat(10), -2.99978), (_lat(12), -2.99978), (_lat(12), -2.9998))
    bldg = ((_lat(-60), lo0), (_lat(-60), lo1), (_lat(0.2), lo1), (_lat(0.2), lo0))
    for shade in (False, True):
        plan = _PPlan([_PUnit("unit:0", [_mem("deck", 9.0, shade), _mem("pier")])])
        shims = [_shim(0, 0, 0, [deck_ring], walled=True), _shim(1, 0, 1, [pier])]
        counts: dict = {}
        pids, deck = fu._deck_lending([0, 1], shims, plan, 0.5, 0.0, counts)
        assert deck is not None and deck[0] == 9.0 and 1 in pids, (shade, counts)
    plan = _PPlan([_PUnit("unit:0", [_mem("deck", 9.0, True), _mem("bldg")])])
    shims = [_shim(0, 0, 0, [deck_ring]), _shim(1, 0, 1, [bldg])]
    counts = {}
    pids, deck = fu._deck_lending([0, 1], shims, plan, 0.5, 0.0, counts)
    assert deck is None and pids == frozenset()
    assert counts.get("deck_datum_lent_to", 0) == 0
    assert counts["deck_lender_refused_welded"] == 1
    # the same unit with a deck the §1 reading did NOT shade lends as before
    plan = _PPlan([_PUnit("unit:0", [_mem("deck", 9.0, False), _mem("bldg")])])
    counts = {}
    pids, deck = fu._deck_lending([0, 1], shims, plan, 0.5, 0.0, counts)
    assert deck is not None and counts["deck_datum_lent_to"] == 2


# ── the law: no new number, the dead key gone ───────────────────────────

def test_the_gate_and_H_are_the_existing_bridge_keys_and_the_dead_key_is_gone():
    assert BR.deck_pier_footprint_max == pytest.approx(0.20)
    assert BR.deck_min_elevation_m == pytest.approx(2.0)
    assert not hasattr(LAW.tables.structures.rebake, "abutment_deck_share_min")
    assert "abutment_deck_share_min" not in {f.name for f in _dc.fields(
        type(LAW.tables.structures.rebake))}
