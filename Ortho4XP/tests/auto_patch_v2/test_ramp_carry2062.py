"""#2062 spec R4 / R5: the front wall (C), the one lateral fit (C′ + F), a
stop carried over a ramp only by a deck with a bridge read (E′1), the kept
stack over the floor (E′2, E′4, E′5) and the airside run-out of its road
(master ruling 2026-11-15).  Synthetic: no pack, no airport."""
from __future__ import annotations

import dataclasses as dc
import types

import numpy as np
import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.deck_stack import KEPT, DeckStack, StackDeck, StackEnd
from auto_patch_v2.planar.front_band import _fit_halves as fit_halves
from auto_patch_v2.planar.front_band import halves_fn
from auto_patch_v2.planar.ramp_carry import carry_of
from shapely.geometry import LineString, Polygon, box

LAW = Law.for_airport("")
BR = LAW.tables.structures.bridge
FLUSH = float(BR.deck_flush_m)
STEP = float(BR.abutment_sample_step_m)


# ── C: the front wall ───────────────────────────────────────────────────

def _wall(x0, x1, y0, y1, zz=0.0):
    v = [(x0, y0, zz), (x1, y0, zz), (x1, y1, zz), (x0, y1, zz)]
    return v, [(0, 1, 2), (0, 2, 3)]


def _geometry(*quads):
    vs, ts = [], []
    for v, t in quads:
        k = len(vs)
        vs += v
        ts += [tuple(k + i for i in tri) for tri in t]
    return types.SimpleNamespace(vertices=np.array(vs, float), solid=np.array(ts, int))


def test_the_front_wall_is_the_full_height_wings_never_the_lintel_or_the_back_plug():
    from auto_patch_v2.airport.entrance_front import front_of
    o = types.SimpleNamespace(xy=(0.0, 0.0), heading_deg=0.0)
    g = _geometry(_wall(-30, -5, -6, 0), _wall(5, 30, -6, 0), _wall(-5, 5, -1, 0),
                  _wall(-5, 5, -6, 0, zz=3.0))
    into = (0.0, -1.0)
    w, _ends = front_of(o, g, (0.0, 0.0), into, 10.0, LAW, ((-5.0, 0.0), (5.0, 0.0)), -6.0, 0.0)
    assert w == pytest.approx(60.0, abs=1.0)
    g2 = _geometry(_wall(-30, -10, -6, 0), _wall(-1, 0, -6, 0), _wall(9, 30, -6, 0))
    w2, _e = front_of(o, g2, (-5.0, 0.0), into, 10.0, LAW, ((-10.0, 0.0), (-1.0, 0.0)),
                      -6.0, 0.0, others=[((0.0, 0.0), (9.0, 0.0))])
    assert w2 == pytest.approx(60.0, abs=1.0)


# ── C′ + F: the one lateral fit ─────────────────────────────────────────

AXIS = LineString([(0.0, 0.0), (0.0, -100.0)])        # mouth first, running south


def _axis_fn(s):
    return (0.0, -s)


RIM, GAP, GRID, SPACING = 1.6, 0.6, 0.5, 12.0
SS = [0.0, 5.0, 12.0, 24.0, 36.0, 48.0, 60.0]


def _ring(hfn):
    left = [(hfn(s)[0] + RIM, -s) for s in SS]
    right = [(-(hfn(s)[1] + RIM), -s) for s in SS]
    return Polygon(left + right[::-1])


def _fit(stops, target=(15.0, 15.0), minimum=(5.0, 5.0)):
    """The fit on a ring offset ``half + RIM`` each side (left = +x)."""
    def hit_of(pr):
        return next((r for p, r in stops if p.distance(pr) < GAP - 1e-9), None)

    def part_of(ref, pr):
        return next(p for p, r in stops if r == ref).intersection(pr.buffer(GAP))
    return fit_halves(SS, lambda s: target, lambda s: minimum, _ring, hit_of, part_of,
                      _axis_fn, AXIS, RIM, GAP, GRID, SPACING, (8.0, 8.0))


def test_no_stop_in_reach_leaves_the_targets():
    table, notes = _fit([(box(40, -60, 50, -20), "far")])
    assert all(table[s] == (15.0, 15.0) for s in SS) and notes == []


def test_a_stop_inside_the_stand_off_cuts_its_side_only_and_clears():
    stops = [(box(16.0, -40.0, 30.0, -20.0), "apron")]
    table, notes = _fit(stops)
    assert 5.0 <= table[24.0][0] < 15.0 and table[24.0][1] == 15.0
    assert table[60.0] == (15.0, 15.0)
    assert stops[0][0].distance(_ring(halves_fn(table))) >= GAP - 1e-9
    assert notes and "left side" in notes[0]


def test_a_stop_across_the_floor_is_left_to_the_clip_loop():
    table, notes = _fit([(box(6.0, -40.0, 30.0, -20.0), "road")])
    assert all(table[s] == (15.0, 15.0) for s in SS)
    assert "across the floor" in notes[-1]


def test_the_halves_table_is_exact_at_stations_and_linear_between():
    fn = halves_fn({0.0: (10.0, 10.0), 10.0: (20.0, 0.0)})
    assert fn(0.0) == (10.0, 10.0) and fn(5.0) == pytest.approx((15.0, 5.0))
    assert fn(-1.0) == (10.0, 10.0) and fn(30.0) == (20.0, 0.0)


# ── E′1: carried only by a deck with a bridge read and the clearance ───

class _Reads:
    def __init__(self, tops):
        self.tops = tops

    def top(self, oid):
        return self.tops.get(oid)


DECK = box(-20.0, -31.0, 20.0, -14.0)
ROAD = box(-4.0, -40.0, 4.0, -5.0)
IVALS = [("D", 14.0, 31.0, DECK, 33.6)]


def _carry(tops, floor=25.14):
    probe = box(-16.0, -31.0, 16.0, -14.0)       # the corridor's part under the deck
    return carry_of("road", probe, [(ROAD, "road")], IVALS, GAP,
                    lambda s0, s1: floor, float(BR.clearance_m), _Reads(tops))


def test_a_stop_is_carried_only_by_a_deck_with_a_bridge_read_and_the_clearance():
    clearance = float(BR.clearance_m)
    assert _carry({"D": 25.14 + clearance + 0.01}) == (("D",), "")
    by, why = _carry({"D": 25.14 + clearance - 0.1})
    assert by == () and "deck_too_low" in why
    by, why = _carry({})
    assert by == () and "deck_without_bridge_read" in why
    far = carry_of("road", box(-16.0, -60.0, 16.0, -45.0), [(ROAD, "road")], IVALS, GAP,
                   lambda s0, s1: 0.0, clearance, _Reads({"D": 99.0}))
    assert far == ((), "")


# ── E′2 / E′4 / E′5: the kept stack over the floor ─────────────────────

def _deck():
    ring = ((-40.0, -4.0), (0.0, -4.0), (0.0, 4.0), (-40.0, 4.0))
    plate = (((-40.0, -4.0, 0.0), (0.0, -4.0, 0.0), (0.0, 4.0, 0.0)),
             ((-40.0, -4.0, 0.0), (0.0, 4.0, 0.0), (-40.0, 4.0, 0.0)))
    return StackDeck("D", "d.obj", 0, ring, 1, (7,), (), ((-40.0, -4.0), (-40.0, 4.0)),
                     ((0.0, -4.0), (0.0, 4.0)), -0.3, -0.3, plate)


def _end(side, line, out, state="flush"):
    return StackEnd("D", side, line, -0.3, out, 10.0, 0.0, state, "", (), 0.0, 0.0)


def _kept(**kw):
    ends = (_end("a", ((-40.0, -4.0), (-40.0, 4.0)), (-1.0, 0.0)),
            _end("b", ((0.0, -4.0), (0.0, 4.0)), (1.0, 0.0)))
    base = dict(id="stack:kept:D", walls_id="", walls_resource="", members=(("D", ""),),
                zero_z=10.3, zero_spread_m=0.0, end_zeros=(), feet_y=0.0, crest_y=0.0,
                floor=(), rim=(), runouts=(), under_ways=(), decks=(_deck(),), kind=KEPT,
                ends=ends, bridge="kept:D")
    base.update(kw)
    return DeckStack(**base)


def test_a_candidate_carried_over_a_floor_is_kept_with_both_flush_ends_rowed():
    from auto_patch_v2.planar.free_bridge import planar_stacks
    cand = _kept()
    assert cand.rowed_ends() == ()
    got, notes = planar_stacks((), (), (), (cand,), {"D": ("tunnel:x@0",)})
    (st,) = got
    assert st.over_floor == ("tunnel:x@0",) and [e.side for e in st.rowed_ends()] == ["a", "b"]
    assert "over the floor" in notes[0]
    assert planar_stacks((), (), (), (cand,), {})[0] == ()
    graded = _kept(ends=(dc.replace(cand.ends[0], state="graded"), cand.ends[1]))
    assert planar_stacks((graded,), (), (), (), {})[0] == (graded,)


def _map():
    verts, faces = {}, {}

    def face(role, ref, pts):
        ids = []
        for p in pts:
            verts[len(verts)] = types.SimpleNamespace(xy=tuple(p), incident_faces=[len(faces)],
                                                      dem_z=0.0)
            ids.append(len(verts) - 1)
        faces[len(faces)] = types.SimpleNamespace(role=role, ref=ref, ring=tuple(ids), holes=())
    face("graded_strip", "stack_ground:x", [(1.0, -2.0), (1.0, 2.0), (3.0, 0.0)])
    face("graded_strip", "ground", [(-20.0, -1.0), (-20.0, 1.0), (-19.0, 0.0)])
    face("tunnel_ramp", "ramp", [(-30.0, -1.0), (-30.0, 1.0), (-29.0, 0.0)])
    return verts, faces


def test_the_over_floor_stack_rows_its_flush_ends_and_ceils_the_ground_not_the_floor():
    from auto_patch_v2.constraints.deck_stack import deck_stack_rows
    st = dc.replace(_kept(), over_floor=("tunnel:x@0",))
    verts, faces = _map()
    pm = types.SimpleNamespace(faces=faces, vertices=verts, ring_vertices=lambda r: list(r),
                               bridge_stacks=(st,))
    rows = deck_stack_rows(pm, LAW, types.SimpleNamespace(deck_stacks=(st,)))
    slab = [r for r in rows if r.source.inputs[2].endswith("end b")]
    assert slab and all(r.hi == pytest.approx(10.3) for r in slab)
    ceil = [r for r in rows if "under the deck" in r.source.inputs[2]]
    on = {r.v for r in ceil}
    ramp = {v for f in faces.values() if f.role == "tunnel_ramp" for v in f.ring}
    under = {v for f in faces.values() if f.ref == "ground" for v in f.ring}
    assert under <= on and not (on & ramp)
    plain = _kept()
    pm.bridge_stacks = (plain,)
    rp = deck_stack_rows(pm, LAW, types.SimpleNamespace(deck_stacks=(plain,)))
    assert not [r for r in rp if "under the deck" in r.source.inputs[2]]
    assert not [r for r in rp if r.source.inputs[2].endswith("end b")]


def test_the_over_floor_stack_publishes_both_ends_and_its_zero():
    from auto_patch_v2.pipeline.rebake_inputs import _kept_published
    st = dc.replace(_kept(), over_floor=("tunnel:x@0",))
    ap = types.SimpleNamespace(
        kept_bridges=(types.SimpleNamespace(id="kept:D", deck_ids=lambda: ("D",)),),
        deck_stacks=(st,), agp_groups=(),
        frame=types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (y, x))))
    rec = _kept_published(ap, types.SimpleNamespace(bridge_stacks=(st,), agp_groups=()))["D"]
    assert len(rec["route_mids"]) == 2 and len(rec["graded"]) == 2
    assert rec["zero"] == pytest.approx(10.3) and not rec.get("joined")


# ── the airside run-out ──────────────────────────────────────────────

@dc.dataclass(frozen=True)
class _CS:
    bands: tuple

def test_the_run_out_holds_the_profile_until_it_meets_the_airside_then_the_airside():
    from auto_patch_v2.constraints.deck_runout import runout_rewrite, runout_rows
    from auto_patch_v2.model.constraints import Band, Source
    end = StackEnd("D", "b", ((0.0, -4.0), (0.0, 4.0)), -0.3, (1.0, 0.0), 10.0, 0.0, "flush",
                   "", ((0.0, 0.0), (40.0, 0.0)), 40.0, 0.05, airside_run=40.0)
    st = dc.replace(_kept(), ends=(end,), over_floor=("t",))
    verts = {}
    for i, x in enumerate((3.0, 10.0, 20.0, 30.0)):          # on the run-out's axis
        verts[i] = types.SimpleNamespace(xy=(x, 0.0), dem_z=11.0)
    for j, x in enumerate((10.0, 20.0, 30.0)):                # the apron beside it
        verts[10 + j] = types.SimpleNamespace(xy=(x, 9.0), dem_z=11.0)
        verts[20 + j] = types.SimpleNamespace(xy=(x, -9.0), dem_z=11.0)
    pm = types.SimpleNamespace(vertices=verts)
    rows = runout_rows(pm, LAW, st, "deck_stack", "rigid", set())
    by_v = {r.v: r for r in rows}
    assert 0 not in by_v                                     # the slab: R1's
    p10 = 10.3 - 0.3 - 0.05 * (10.0 - STEP)
    assert by_v[1].hi == pytest.approx(p10) and by_v[1].lo == pytest.approx(p10 - FLUSH)
    levels = {10 + j: 9.5 for j in range(3)} | {20 + j: 9.5 for j in range(3)}
    cs = _CS(tuple(rows) + (Band(99, 0.0, 1.0, Source("x", "y", ("a", "b", "c"))),))
    out, rep = runout_rewrite(pm, LAW, cs, levels)
    got = {r.v: r for r in out.bands if r.v in by_v}
    assert got[1].hi == pytest.approx(p10)                   # over the apron: the road
    assert got[2].hi == pytest.approx(9.5) and got[3].hi == pytest.approx(9.5)
    (rec,) = rep["ends"].values()
    assert rec["on_airside"] == 2
    assert [r for r in out.bands if r.v == 99][0].hi == 1.0       # another row: as it was


def test_the_driven_layer_is_read_never_the_underside_or_a_far_plane():
    from auto_patch_v2.geom.plate_heights import driven_y_at
    sq = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], [(0.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

    def layer(y):
        return [[(x, yy, y) for x, yy in t] for t in sq]
    plate = np.asarray(layer(-1.0) + layer(-0.3) + layer(0.5), float)
    got = driven_y_at(plate, [5.0], [5.0], -0.3, 0.0)
    assert got[0] == pytest.approx(-0.3)
    # a steep face read off its edge lands metres off the top: no driven layer
    wall = np.asarray([[(10.0, 0.0, -6.0), (10.0, 10.0, -6.0), (10.1, 5.0, 0.5)]], float)
    assert np.isnan(driven_y_at(wall, [14.0], [5.0], -0.3, 5.0)[0])


def test_the_end_inner_strip_runs_past_the_end_lines_ends():
    from auto_patch_v2.geom.deck_ground import end_inner_strip
    end = StackEnd("D", "b", ((0.0, -4.0), (0.0, 4.0)), -0.3, (1.0, 0.0), 10.0, 0.0, "flush",
                   "", (), 0.0, 0.0)
    ring = Polygon(_deck().ring)
    strip = end_inner_strip(end, 2.0, ring)
    minx, miny, maxx, maxy = strip.bounds
    assert minx == pytest.approx(-2.0) and maxx == pytest.approx(0.0)
    assert miny == pytest.approx(-6.0) and maxy == pytest.approx(6.0)
