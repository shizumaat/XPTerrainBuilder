"""#1718 B (spec ``docs/specs/1718-kbna-xb-r2-spec.md``): a pack hard deck no
mapped way carries, over a mapped road beneath — KBNA's crossing bridge — is
a KEPT candidate by its CROSSING at the pack stage
(``planar/free_bridge._overpass_witness``): the pack-stage half of the
road-overpass witness (``planar/overpass_deck.road_crossings``) and the stub
witnesses on its own axis (``bridge_witness.axis_witness``).  Its zero is the
overpass seat predicted on the DEM (``airport/bridge_stack._overpass_one``),
its axis ends graded to it; the overpass read still seats the deck
(``pipeline/rebake_inputs._kept_published`` never publishes it) and the
planar stage keeps its stack only where that read seats it.  Synthetic,
headless."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.airport import bridge_end_state as BES
from auto_patch_v2.airport import bridge_stack as BS
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.law import Law
from auto_patch_v2.model.deck_stack import KEPT, DeckStack, StackEnd
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.model.free_bridge import OVERPASS_PREFIX
from auto_patch_v2.planar import free_bridge as FB
from shapely.geometry import box as _sbox

LAW = Law.for_airport("")
BR = LAW.tables.structures.bridge
THICK = LAW.tables.structures.basin.min_solid_thickness_m
FRAME = Frame("ZZZZ", origin=(36.0, -86.0), identity_dp=11)
TO_XY, TO_LL = FRAME.transformers()


def _box(x, z, w, d, h, y0=0.0):
    x1, z1, y1 = x + w, z + d, y0 + h
    v = [(x, y0, z), (x1, y0, z), (x1, y0, z1), (x, y0, z1),
         (x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
             (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
             (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return [(v[a], v[b], v[c]) for a, b, c in faces]


def _write(path, top, roof=False):
    """A 16 x 50 m hard deck 0.3 m thick at ``top`` on two abutment blocks
    (``planar/overpass_deck`` twins' crossing), their feet 10 m under the
    zero (further under the deck than W4b reads); ``roof``: a canopy 2 m
    over the deck (the axis witness fails)."""
    comps = [_box(-8.0, -25.0, 16.0, 50.0, 0.3, y0=top - 0.3),
             _box(-8.0, -25.0, 16.0, 13.0, top + 10.0, y0=-10.0),
             _box(-8.0, 12.0, 16.0, 13.0, top + 10.0, y0=-10.0)]
    if roof:
        comps.append(_box(-8.0, -25.0, 16.0, 50.0, 0.3, y0=top + 2.0))
    verts = [p for comp in comps for tri in comp for p in tri]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
    out += [f"VT {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} 0 1 0 0 0" for v in verts]
    out += [f"IDX {i}" for i in range(len(verts))]
    n0 = 3 * len(comps[0])
    out += ["ATTR_hard_deck concrete", f"TRIS 0 {n0}", "ATTR_no_hard",
            f"TRIS {n0} {len(verts) - n0}"]
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _deck(tmp_path, top=7.5, roof=False):
    plan = _sbox(-8.0, -25.0, 8.0, 25.0)
    return types.SimpleNamespace(
        id="dsf:obj9", path="objects/crossing.obj",
        resolved=_write(tmp_path / f"c{top}{roof}.obj", top, roof), xy=(0.0, 0.0),
        heading_deg=0.0, kind="OBJECT", anchor_z=100.0, agl_m=0.0, deck_kind="flag",
        hard_deck=plan, deck_top_z=100.0 + top, plan_bbox=plan, footprint=None)


def _airport(road=True):
    ways = [types.SimpleNamespace(id=-7, points=[(-60.0, 1.0), (60.0, 1.0)],
                                  tags={"highway": "secondary"})] if road else []
    return types.SimpleNamespace(frame=FRAME, osm_ways=ways, dem=None, deck_stacks=())


def _candidate(tmp_path, **kw):
    road = kw.pop("road", True)
    o = _deck(tmp_path, **kw)
    cache = O.ResourceCache(THICK)
    rd = FB._Read(_airport(road), [o], cache, LAW)
    return o, cache, FB._overpass_witness([o], [o], [o], rd)


def test_a_routeless_deck_over_a_road_is_a_kept_candidate_by_its_crossing(tmp_path):
    """B1-B3: one KEPT candidate, its ends the axis's (the short sides, y
    -25 / +25), route ``AXIS_STUB``, ``under`` the road beneath's stations."""
    o, _c, (bridges, notes) = _candidate(tmp_path)
    (fb,) = bridges
    assert fb.id == OVERPASS_PREFIX + o.id and fb.members == (o.id,)
    (d,) = fb.decks
    assert d.stub_of == FB.AXIS_STUB + o.id and d.ways == ()
    assert d.under and all(abs(y - 1.0) < 1e-6 and -8.0 <= x <= 8.0 for x, y in d.under)
    assert sorted(round(e.stations[0][1]) for e in d.ends) == [-25, 25]
    assert all(e.land and abs(e.top - 7.5) < 1e-6 for e in d.ends)
    assert "a kept candidate by its crossing" in notes[0]


def test_the_crossing_must_stand_the_clearance_over_the_road(tmp_path):
    """B1: ``_crossing_top >= clearance_minimum_m`` — the plate's LOWEST face
    over the road (the 0.3 m slab's underside)."""
    clear = float(BR.clearance_minimum_m)
    assert _candidate(tmp_path, top=clear + 0.3 + 0.05)[2][0]
    assert _candidate(tmp_path, top=clear + 0.3 - 0.05)[2] == ([], [])
    assert _candidate(tmp_path, road=False)[2] == ([], [])


def test_a_deck_with_a_route_or_failing_its_axis_witness_is_no_candidate(tmp_path):
    # a deck that is not routeless (W1 held, or the join read took it)
    o = _deck(tmp_path)
    rd = FB._Read(_airport(), [o], O.ResourceCache(THICK), LAW)
    assert FB._overpass_witness([o], [], [o], rd) == ([], [])
    # a canopy 2 m over the deck: the stub witnesses on its own axis fail
    _o, _c, (bridges, notes) = _candidate(tmp_path, roof=True)
    assert bridges == [] and "not a kept candidate" in notes[0] and "own axis" in notes[0]


class _Obs:
    """A duck-typed ``bridge_end_state.Obstacles``: open ground."""

    def __init__(self):
        self.graph = BES._Graph(())
        self.dem = object()
        self.airside = types.SimpleNamespace(contains=lambda p: False)

    def z(self, xs, ys):
        return np.zeros(len(xs))

    def water(self, _box):
        return None

    def near(self, corridor, own):
        return [], []


def _cx(o, cache, road_z, end_z):
    """A duck-typed ``bridge_stack._Ctx``: the DEM ``road_z`` within 20 m of
    the deck's middle, ``end_z`` beyond."""
    def surface(lat, lon):
        _x, y = TO_XY(lon, lat)
        return road_z if abs(y) < 20.0 else end_z
    cx = types.SimpleNamespace(by_id={o.id: o}, cache=cache, to_ll=TO_LL, law=LAW,
                               out_m=float(BR.free_end_ground_out_m), obs=_Obs(),
                               step=float(BR.abutment_sample_step_m),
                               surface=lambda rings: surface)
    cx.ends = types.MethodType(BS._Ctx.ends, cx)
    return cx


def test_its_zero_is_the_overpass_seat_and_its_ends_grade_up_to_the_deck(tmp_path):
    """B3 / B4: zero = the road beneath (100.0, y 0); both ends 3 m under
    the deck top (107.5) are GRADED at the stub's grade, a KEPT stack whose
    bridge is the candidate's."""
    o, cache, ((fb,), _n) = _candidate(tmp_path)
    minted, every, notes = BS._overpass_one(fb, _cx(o, cache, 100.0, 104.5))
    (st,) = minted
    assert every == [st] and st.kind == KEPT and st.bridge == fb.id
    assert st.zero_z == pytest.approx(100.0)
    assert sorted(e.state for e in st.ends) == ["graded", "graded"]
    assert all(e.gap == pytest.approx(3.0) and e.run < 100.0 for e in st.ends)
    assert "kept by its crossing, predicted seat 100.000" in notes[0]


def test_flush_ends_or_a_run_past_the_reach_mint_nothing(tmp_path):
    o, cache, ((fb,), _n) = _candidate(tmp_path)
    minted, every, _notes = BS._overpass_one(fb, _cx(o, cache, 100.0, 107.5))
    assert minted == [] and [e.state for e in every[0].ends] == ["flush", "flush"]
    # a stub's run over ``fill_road_reach_m`` is LISTED, nothing built
    minted, every, _notes = BS._overpass_one(fb, _cx(o, cache, 100.0, 98.0))
    assert minted == [] and all("end_beyond_reach" in e.why for e in every[0].ends)


def _stack(bridge):
    end = StackEnd("D", "b", ((0.0, -4.0), (0.0, 4.0)), 7.5, (1.0, 0.0), 102.5, 5.0, "graded",
                   "", ((0.0, 0.0), (60.0, 0.0)), 50.0, 0.05)
    return DeckStack("stack:" + bridge, "", "", (("D", "d.obj"),), 100.0, 0.0, (), 0.0, 0.0,
                     (), (), (), (), (), kind=KEPT, ends=(end,), bridge=bridge)


def test_the_planar_stage_keeps_it_only_where_the_overpass_read_seats_it():
    st = _stack(OVERPASS_PREFIX + "D")
    assert FB.planar_stacks((st,), (), overpasses=("D",)) == ((st,), [])
    gone, notes = FB.planar_stacks((st,), ())
    assert gone == () and "reads no road overpass" in notes[0]
    # any other kept stack is untouched by the overpass read
    other = _stack("kept:D")
    assert FB.planar_stacks((other,), ())[0] == (other,)


def test_the_overpass_plate_seats_it_never_a_kept_record():
    from auto_patch_v2.pipeline.rebake_inputs import _kept_published
    st = _stack(OVERPASS_PREFIX + "D")
    fb = types.SimpleNamespace(id=OVERPASS_PREFIX + "D", deck_ids=lambda: ("D",))
    frame = types.SimpleNamespace(transformers=lambda: (None, TO_LL))
    ap = types.SimpleNamespace(kept_bridges=(fb,), deck_stacks=(st,), frame=frame)
    assert _kept_published(ap, types.SimpleNamespace(bridge_stacks=(st,))) == {}


def test_w4b_never_places_a_placement_its_reach_keeps_off_the_box(tmp_path):
    """``bridge_frame.Under``: a placement with no plan bounds is skipped by
    its geometry's plan reach (exact) — the faces returned are the same, the
    far placement is never placed (KBNA: 6,076 placements, 9 s)."""
    from auto_patch_v2.airport import bridge_frame as BF
    g = O.ResourceCache(THICK).geometry(_write(tmp_path / "u.obj", 7.5))
    placed = [("near", g, (0.0, 0.0), 0.0), ("far", g, (5000.0, 0.0), 0.0)]
    under = BF.Under(placed, lambda u: (0.0, True), float(BR.deck_plate_normal_y_min))
    got = under.for_unit("near", {"near"})((-10.0, -10.0, 10.0, 10.0))
    assert len(got) and 1 not in under._faces and 0 in under._faces
    every = BF.Under(placed, lambda u: (0.0, True), float(BR.deck_plate_normal_y_min))
    every._misses = lambda k, b: False
    assert np.array_equal(got, every.for_unit("near", {"near"})((-10.0, -10.0, 10.0, 10.0)))
