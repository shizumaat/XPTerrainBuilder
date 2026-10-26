"""Owner RULINGS 2026-10-26d (Q142 "b", #1331): a pack HARD DECK over the
pack's own cut sits flush with the solved surface it carries — the
taxiway where it drives onto the deck, read one step outside the deck's
end lines (the trench is under its edges) — and is never left at the
pack's shared zero.  A deck over no pack cut is left as it was (22n (2)).
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import cut_deck_seat as CDS
from auto_patch_v2.airport.placement_record import Body, Split
from auto_patch_v2.model.frame import m_per_deg_exact

LAT, LON = 40.0, -3.0
ML, MO = m_per_deg_exact(LAT)
#: the deck slab: 40 m east-west, 30 m north-south, top y 0.0 (a taxiway
#: runs NORTH-SOUTH over it; the road in the trench under it EAST-WEST)
HALF_X, HALF_Z = 20.0, 15.0
N, S = LAT + HALF_Z / ML, LAT - HALF_Z / ML
TAXI_N, TAXI_S, TRENCH = 100.0, 100.2, 94.0


def _deck_obj(tmp_path, y=0.0):
    """An OBJ8 whose only geometry is one ATTR_hard_deck quad at ``y``."""
    v = [(-HALF_X, y, -HALF_Z), (HALF_X, y, -HALF_Z), (HALF_X, y, HALF_Z), (-HALF_X, y, HALF_Z)]
    tris = [v[0], v[2], v[1], v[0], v[3], v[2]]
    out = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(tris)} 0 0 {len(tris)}"]
    out += [f"VT {p[0]:.4f} {p[1]:.4f} {p[2]:.4f} 0 1 0 0 0" for p in tris]
    out += [f"IDX {i}" for i in range(len(tris))]
    out += ["ATTR_hard_deck concrete", f"TRIS 0 {len(tris)}"]
    path = tmp_path / "deck.obj"
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
    return str(path)


def _member(path):
    return types.SimpleNamespace(deck_kind="flag", deck_top_y=0.0, authored_path=path,
                                 heading_deg=0.0, resource="objects/deck.obj", zero_y=0.0,
                                 origin=(LAT, LON))


def _record(zero=77.0):
    """The deck body as the stack left it: riding a shared zero ``zero``."""
    a = AR.Anchor(AR.OTHER, LAT, LON, TRENCH - zero, "carried by the stack", TRENCH,
                  offset=(0.0, TRENCH - zero, 0.0))
    box = (S - 1e-6, LON - HALF_X / MO - 1e-6, N + 1e-6, LON + HALF_X / MO + 1e-6)
    b = Body(0, AR.OTHER, (), a, "objects/deck__b0.obj", merged_into="objects/shell__b0.obj",
             geom_box=box, plan_box=box)
    return Split(0, "dsf:obj0", "objects/deck.obj", "/x/deck.obj", LAT, LON, 0.0, (b,))


def _surface(n_role="cross_connector", ew_role="tunnel_trench"):
    """The taxiway north and south of the deck; the trench under it and
    its ramps east and west (``tunnel_trench`` is a STRUCTURE role the law
    registers airside — never the surface the deck carries)."""
    def surface(la, lo):
        if la > N + 1e-7:
            return TAXI_N
        if la < S - 1e-7:
            return TAXI_S
        return TRENCH

    class Roles:
        def roles_many(self, las, los):
            return [n_role if (a > N + 1e-7 or a < S - 1e-7) else ew_role for a in las]
    surface.roles = Roles()
    return surface


def _cut(pad_m=10.0):
    """The pack cut's footprint ring, ``pad_m`` beyond the deck."""
    dn, de = (HALF_Z + pad_m) / ML, (HALF_X + pad_m) / MO
    return ((LAT - dn, LON - de), (LAT - dn, LON + de), (LAT + dn, LON + de),
            (LAT + dn, LON - de))


def _seat(tmp_path, cuts, surface=None, counts=None):
    m = _member(_deck_obj(tmp_path))
    return CDS.seat_cut_decks(_record(), m, (LAT, LON), surface or _surface(), cuts, 2.0,
                              0.5, {} if counts is None else counts)


def _zero(b):
    return b.anchor.surface_z - b.anchor.y_zero


def test_a_deck_over_the_packs_cut_sits_flush_with_the_taxiway(tmp_path):
    """LGAV ``Trench_00`` over ``Trench_02``: the deck stood at the stack's
    zero; it now meets the taxiway at its two end lines (100.0 / 100.2),
    never the trench under its edges (94.0)."""
    counts: dict = {}
    rec = _seat(tmp_path, (_cut(),), counts=counts)
    b = rec.bodies[0]
    assert abs(_zero(b) - 0.5 * (TAXI_N + TAXI_S)) < 1e-6
    assert b.anchor.datum and not b.merged_into
    assert "RULINGS 2026-10-26d" in b.anchor.reason
    assert counts["cut_deck_bodies"] == 1
    # the offset the file bakes is the anchor's own (R1: renamed for it)
    assert b.anchor.offset[1] == b.anchor.y_zero
    assert b.new_resource != "objects/deck__b0.obj"


def test_a_deck_over_no_pack_cut_is_left_as_it_was(tmp_path):
    """22n (2): a deck over an OSM cut, or over nothing, keeps its seat."""
    rec0 = _record()
    m = _member(_deck_obj(tmp_path))
    assert CDS.seat_cut_decks(rec0, m, (LAT, LON), _surface(), (), 2.0, 0.5, {}) is rec0
    far = tuple((la + 0.01, lo) for la, lo in _cut())
    assert CDS.seat_cut_decks(rec0, m, (LAT, LON), _surface(), (far,), 2.0, 0.5, {}) is rec0


def test_a_road_deck_reads_the_road_when_no_taxiway_drives_onto_it(tmp_path):
    rec = _seat(tmp_path, (_cut(),), surface=_surface(n_role="service_road"))
    assert abs(_zero(rec.bodies[0]) - 0.5 * (TAXI_N + TAXI_S)) < 1e-6


def test_the_trench_is_never_the_carried_surface(tmp_path):
    """With nothing but the cut's own structure roles around it, the deck
    has no end lines and stays where it was (counted)."""
    counts: dict = {}
    rec0 = _record()
    m = _member(_deck_obj(tmp_path))
    got = CDS.seat_cut_decks(rec0, m, (LAT, LON), _surface(n_role="tunnel_ramp"),
                             (_cut(),), 2.0, 0.5, counts)
    assert got is rec0 and counts["cut_deck_no_end_lines"] == 1


def test_cut_rings_are_read_off_the_seat_records_once():
    ring = [[40.0, -3.0], [40.0, -2.999], [40.001, -2.999]]
    recs = [{"id": "a", CDS.CUT_RING: ring}, {"id": "b", CDS.CUT_RING: ring}, {"id": "c"}]
    assert CDS.cut_rings(recs) == (tuple((a, b) for a, b in ring),)


def test_the_planar_cut_is_stamped_on_its_objects_seat_record():
    """``pipeline/rebake_inputs`` publishes each OBJECT cut's footprint
    ring as ``[lat, lon]`` on its placements' seat records."""
    from auto_patch_v2.pipeline.rebake_inputs import _stamp_cut_rings
    tn = types.SimpleNamespace(source="object", objects=("dsf:obj1",), wall_path=(),
                               footprint=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)))
    osm = types.SimpleNamespace(source="osm", objects=(), footprint=((0.0, 0.0),) * 3,
                                wall_path=())
    frame = types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (40.0 + y, -3.0 + x)))
    seats = {"dsf:obj1": {"id": "dsf:obj1"}}
    _stamp_cut_rings(seats, types.SimpleNamespace(structures=(tn, osm)),
                     types.SimpleNamespace(frame=frame))
    assert seats["dsf:obj1"][CDS.CUT_RING] == [[40.0, -3.0], [40.0, 7.0], [50.0, 7.0]]
