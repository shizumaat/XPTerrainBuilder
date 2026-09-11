"""Lane v2othhseat twins (RULINGS 2026-09-08d; spec
``docs/specs/auto-patch-v2/othh-seat-artefacts-spec.md``): the flat-site
datum reaches the seat — (a) the anchor on water / on the plane, (b) the
deck ring's abutment relief, (c) the plate stations outside the wall's
outer face, (d) a structure seat under the threshold stays, (e) the datum
under every footprint.  Hermetic: synthetic plans and samplers."""
from __future__ import annotations

import dataclasses as _dc
import json
import types

import pytest
from shapely.geometry import Point, Polygon

from auto_patch_v2.emit import rebake as R
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.build import _plate_seats, plate_stations

Z0 = 10.0
#: the datum region: a square 0.005° around the origin (``(lat, lon)``)
SQUARE = ((-0.005, -0.005), (-0.005, 0.005), (0.005, 0.005), (0.005, -0.005))
FLAT = R.FlatDatum("flat_candidate", Z0, "cifp", ((SQUARE, ()),))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _part(pid: int, lat: float, lon: float = 0.0, base_y: float = 0.0) -> R.Part:
    return R.Part(pid, 0, lat, lon, base_y, 100.0, (lat - 1e-5, lon - 1e-5, lat + 1e-5, lon + 1e-5))


def _member(name: str, parts=(), **deck) -> R.Member:
    return R.Member(name, f"objects/{name}.obj", name, name, 0.0, tuple(parts), **deck)


def _plan(units, contacts=(), flat=FLAT) -> R.RebakePlan:
    return R.RebakePlan("ZZZZ", "p", "/p", tuple(units), (), {}, tuple(contacts), flat)


def _by_lat(table, water=()):
    """``{lat: z}`` by rounded latitude; latitudes in ``water`` sample as water."""
    def f(lat, lon):
        k = round(lat, 6)
        return (table.get(k, table[0.0]), k in water)
    return f


# ── (a) the anchor ───────────────────────────────────────────────────────

def test_anchor_on_water_takes_the_datum_on_a_flat_site(law):
    """OTHH Bridges Bus (08d): the anchor over the canal samples water at
    0.00; on the flat site Z0 founds the base, the ground parts at Z0
    read delta 0 — nothing is written.  Without a datum the unit is HELD."""
    m = _member("bridge", [_part(0, 0.001)])
    pl = _plan([R.Unit("u", (0.0, 0.0), 0.0, (m,))])
    res = R.seat(pl, _by_lat({0.0: 0.0, 0.001: Z0}, water=(0.0,)), law)
    u = res.units[0]
    assert not u.held and u.anchor_ground_m == Z0
    assert not u.bakes and u.skip_reason.startswith("below_threshold")
    assert any("anchor on water" in f and "Z0" in f for f in u.findings)
    held = R.seat(_dc.replace(pl, flat=None), _by_lat({0.0: 0.0, 0.001: Z0}, water=(0.0,)), law)
    assert held.units[0].held and "anchor on water" in held.units[0].skip_reason
    assert law.tables.structures.rebake.anchor_water_founds_seat is False


def test_anchor_on_the_plane_takes_the_datum_but_a_cut_keeps_the_mesh(law):
    """A land anchor within the band of Z0 takes Z0 (the plane's own
    residual is the datum's); an anchor on a pit floor 13 m under Z0
    (OTHH Dewatering_01) keeps the mesh — the plate seat's +13 is the cut
    compensation the sim needs."""
    band = law.tables.structures.basin.contact_band_m
    plate = _member("pit", [_part(0, 0.001, base_y=-13.0)], plate_y=-13.0,
                    plate_stations=((0.001, 0.0), (0.0012, 0.0)))
    pl = _plan([R.Unit("u", (0.0, 0.0), 0.0, (plate,))])
    # the anchor on the floor at −3 (13 under Z0), the floor stations at −3
    res = R.seat(pl, _by_lat({0.0: Z0 - 13.0, 0.001: -3.0, 0.0012: -3.0}), law)
    u = res.units[0]
    assert u.anchor_ground_m == pytest.approx(Z0 - 13.0)
    assert u.datum == R.DATUM_PLATE and u.bakes and u.delta_m == pytest.approx(13.0)
    assert any("in a cut" in f for f in u.findings)
    # the anchor 0.4 m off the plane: Z0 founds it
    res = R.seat(pl, _by_lat({0.0: Z0 + 0.4, 0.001: -3.0, 0.0012: -3.0}), law)
    assert res.units[0].anchor_ground_m == Z0 and 0.4 <= band
    # not a flat site: the mesh founds every anchor
    res = R.seat(_dc.replace(pl, flat=None), _by_lat({0.0: Z0 + 0.4, 0.001: -3.0, 0.0012: -3.0}), law)
    assert res.units[0].anchor_ground_m == pytest.approx(Z0 + 0.4)


# ── (b) the deck ring ────────────────────────────────────────────────────

def test_a_ring_without_abutment_relief_is_not_a_bridge(law):
    """OTHH TerminalRoads (08d): a flag deck 10 m over a plane whose ring
    samples flat was seated at ground (−10.87); a ring with no water and a
    land spread under the band stands the deck seat down; a ring over a
    cut (water, or relief) seats the deck top."""
    band = law.tables.structures.basin.contact_band_m
    ring = ((0.001, 0.0), (0.001, 0.0002), (0.0012, 0.0002), (0.0012, 0.0))
    deck = _member("deck", deck_ring=ring, deck_top_y=10.0, deck_kind="flag")
    pl = _plan([R.Unit("u", (0.0, 0.0), 0.0, (deck,))], flat=None)
    flat = R.seat(pl, _by_lat({0.0: 5.0, 0.001: 5.0, 0.0012: 5.0 + band / 2.0}), law).units[0]
    assert flat.datum == R.DATUM_CLUSTER and flat.delta_m is None
    assert any("ring samples flat" in m.note for m in flat.members)
    over_water = R.seat(pl, _by_lat({0.0: 5.0, 0.001: 5.0, 0.0012: 5.0}, water=(0.0012,)), law).units[0]
    assert over_water.datum == R.DATUM_DECK_TOP and over_water.delta_m == pytest.approx(-10.0)
    relief = R.seat(pl, _by_lat({0.0: 5.0, 0.001: 5.0, 0.0012: 5.0 + 2.0 * band}), law).units[0]
    assert relief.datum == R.DATUM_DECK_TOP and relief.bakes


# ── (c) the plate stations ───────────────────────────────────────────────

def test_plate_stations_stand_outside_the_outer_face(law):
    """The stations are the object's footprint grown by the identity
    spacing, sampled every abutment step — off the outer face, never on
    the trench rim, whichever side of the face the rim stands."""
    grid = law.tables.emit.identity.min_distinct_spacing_m
    step = law.tables.structures.bridge.abutment_sample_step_m
    rect = ((0.0, 0.0), (40.0, 0.0), (40.0, 12.0), (0.0, 12.0))
    pts = plate_stations(rect, grid, step)
    poly = Polygon(rect)
    assert len(pts) >= (2 * (40.0 + 12.0)) / step
    assert all(not poly.contains(Point(p)) for p in pts)
    # the stand-off: the spacing off the faces, up to spacing × √2 at a mitred corner
    assert all(grid - 1e-6 <= poly.exterior.distance(Point(p)) <= grid * 2 ** 0.5 + 1e-6 for p in pts)
    assert plate_stations((), grid, step) == []

    def pm_with(rim):
        tn = types.SimpleNamespace(source="object", objects=("dsf:obj0",), plate_y_m=5.0,
                                   depth_m=5.0, footprint=rect, wall_path=rim,
                                   wall_length_m=40.0, top_s=40.0, axis=((0.0, 6.0), (40.0, 6.0)))
        return types.SimpleNamespace(structures=[tn], basins=[])
    # RULINGS 2026-09-08o (rule (c) restated): the stations stand OUTSIDE
    # the EMITTED rim ring, whichever side of the outer face it is on — a
    # rim inside the wall leaves them at the footprint's stand-off; a rim
    # the arrangement pushed 0.3 m OUTSIDE the outer face pushes them out
    # with it (none inside the ring, all the stand-off off it)
    rim_out = Polygon(rect).buffer(0.3, join_style="mitre")
    outside = _plate_seats(pm_with(tuple(rim_out.exterior.coords)), law)
    inside = _plate_seats(pm_with(tuple(Polygon(rect).buffer(-0.5).exterior.coords)), law)
    assert inside["dsf:obj0"] == (5.0, pts)
    assert outside["dsf:obj0"][0] == 5.0
    o_pts = outside["dsf:obj0"][1]
    assert o_pts and all(not rim_out.contains(Point(p)) for p in o_pts)
    assert all(rim_out.exterior.distance(Point(p)) >= grid - 1e-6 for p in o_pts)


# ── (d) the threshold ────────────────────────────────────────────────────

def test_structure_seat_under_the_threshold_stays(law):
    """OTHH Drainage_06 was written +0.001 m under the exemption: a plate
    seat under ``min_delta_m`` STAYS, its members keep their authored y
    and are never handed to the cluster law; the decision lists them as
    skipped (v1's reversion pass puts an earlier bake back)."""
    from auto_patch.engine_v2 import _decision_from_seats
    rb = law.tables.structures.rebake
    assert rb.structure_seat_threshold_exempt is False
    plate = _member("drain", [_part(0, 0.001, base_y=-4.2)], plate_y=-4.2,
                    plate_stations=((0.001, 0.0),))
    pl = _plan([R.Unit("u", (0.0, 0.0), 0.0, (plate,))], flat=None)
    res = R.seat(pl, _by_lat({0.0: Z0, 0.001: Z0 - 4.2 + 0.001}), law)
    u = res.units[0]
    assert u.datum == R.DATUM_PLATE and u.delta_m is None and not u.bakes
    assert u.skip_reason.startswith("below_threshold") and not u.held
    assert all(not m.bakes for m in u.members)
    dec = _decision_from_seats(pl, res, measure_only=False)
    assert "objects/drain.obj" not in dec.delta_by_resource_and_vertex
    assert any(r == "objects/drain.obj" and "below_threshold" in why for r, why in dec.skipped)
    # at the threshold the plate bakes
    res = R.seat(pl, _by_lat({0.0: Z0, 0.001: Z0 - 4.2 + rb.min_delta_m}), law)
    assert res.units[0].bakes and res.units[0].delta_m == pytest.approx(rb.min_delta_m)


def test_a_plate_seat_writes_at_its_own_smaller_threshold(law):
    """RULINGS 2026-09-08u (1): OTHH's deep bore computed +0.492 m and the
    1.0 m ``min_delta_m`` declined it — a wall crest half a metre under
    grade is visible.  A PLATE-datum seat writes any |delta| ≥
    ``plate_seat_min_delta_m`` 0.05; below it the unit still stays (08d
    (d) unchanged), and an ORDINARY (deck) seat keeps the 1.0 m bar."""
    rb = law.tables.structures.rebake
    band = law.tables.structures.basin.contact_band_m
    assert 0.0 < rb.plate_seat_min_delta_m < rb.min_delta_m
    plate = _member("wall", [_part(0, 0.001, base_y=2.0)], plate_y=2.0,
                    plate_stations=((0.001, 0.0),))
    pl = _plan([R.Unit("u", (0.0, 0.0), 0.0, (plate,))], flat=None)
    # the deep bore's own number: the ground at the wall band 0.492 over the
    # rendered crest — written, whole, at the plate datum
    hit = R.seat(pl, _by_lat({0.0: Z0, 0.001: Z0 + 2.0 + 0.492}), law).units[0]
    assert hit.datum == R.DATUM_PLATE and hit.bakes
    assert hit.delta_m == pytest.approx(0.492)
    # +0.03 is under the plate bar: the structure stays at its authored y
    miss = R.seat(pl, _by_lat({0.0: Z0, 0.001: Z0 + 2.0 + 0.03}), law).units[0]
    assert not miss.bakes and miss.delta_m is None
    assert miss.skip_reason.startswith("below_threshold") and \
        f"{rb.plate_seat_min_delta_m}" in miss.skip_reason
    # an ORDINARY unit (a deck seat) at the same +0.49 stays: its bar is 1.0 m
    ring = ((0.001, 0.0), (0.0012, 0.0), (0.0013, 0.0))
    deck = _member("deck", deck_ring=ring, deck_top_y=0.0, deck_kind="flag")
    dpl = _plan([R.Unit("d", (0.0, 0.0), 0.0, (deck,))], flat=None)
    d = R.seat(dpl, _by_lat({0.0: Z0 - 0.49, 0.001: Z0, 0.0012: Z0,
                             0.0013: Z0 + 2.0 * band}), law).units[0]
    assert d.datum == R.DATUM_DECK_TOP and not d.bakes and d.delta_m is None
    assert d.skip_reason.startswith("below_threshold") and \
        f"{rb.min_delta_m}" in d.skip_reason


# ── (e) the datum under the footprint ────────────────────────────────────

def test_the_datum_extends_under_every_footprint_inside_the_region(law):
    """OTHH Emiri / Terminal_Parking_VCN (08d): ground parts reading the
    canal bank or the raw inset DEM (2 m under Z0) read their AUTHORED
    foot — the pack's seat, delta 0 — over the WHOLE footprint of an object
    anchored inside the region (VCN's bank parts beyond the region's edge
    included), an AGL-offset unit (Bridge_05 at −3.5) too; a part of an
    object anchored OUTSIDE the region reads the mesh; a flat-site DECK
    unit keeps its authored deck."""
    inside = _member("emiri", [_part(0, 0.001), _part(4, 0.02)])   # a part on the bank, beyond the region
    low = _member("bridge", [_part(2, 0.002)])
    outside = _member("far", [_part(1, 0.02)])
    ring = ((0.003, 0.0), (0.003, 0.0002), (0.0032, 0.0002), (0.0032, 0.0))
    deck = _member("deck", [_part(3, 0.003)], deck_ring=ring, deck_top_y=1.1, deck_kind="flag")
    pl = _plan([R.Unit("a", (0.0, 0.0), 0.0, (inside,)), R.Unit("b", (0.021, 0.0), 0.0, (outside,)),
                R.Unit("c", (0.0, 0.0), -3.5, (low,)), R.Unit("d", (0.0, 0.0), -3.5, (deck,))])
    table = {0.0: Z0, 0.001: Z0 - 2.0, 0.021: Z0, 0.02: Z0 - 2.0, 0.002: Z0, 0.003: Z0 - 2.0, 0.0032: Z0}
    res = R.seat(pl, _by_lat(table), law)
    a, b, c, d = res.units
    assert not a.bakes and a.skip_reason.startswith("below_threshold")
    assert a.members[0].ground_m == pytest.approx(Z0)
    # the WHOLE footprint of an object anchored inside the region reads the
    # authored plane (OTHH Terminal_Parking_VCN: two parts on the canal bank
    # beyond the region's edge read 2.07 and wrote −1.89)
    assert all(d is None for _, _, d in a.members[0].part_deltas)
    assert b.anchor_ground_m == pytest.approx(Z0)            # outside the region: the mesh
    assert b.members[0].ground_m == pytest.approx(Z0 - 2.0) and b.bakes
    assert not c.bakes and c.members[0].ground_m == pytest.approx(Z0 - 3.5)   # −agl is no lift
    assert not d.bakes and d.datum == R.DATUM_DECK_TOP
    assert d.skip_reason.startswith("below_threshold: flat site") and not d.held
    # the key off: the bank is read
    off = _dc.replace(law, tables=_dc.replace(law.tables, structures=_dc.replace(
        law.tables.structures, rebake=_dc.replace(law.tables.structures.rebake,
                                                  flat_site_ground_datum=False))))
    a2 = R.seat(pl, _by_lat({0.0: Z0, 0.001: Z0 - 2.0, 0.02: Z0 - 2.0}), off).units[0]
    assert a2.bakes and a2.members[0].part_deltas[0][2] == pytest.approx(-2.0)


def test_plan_carries_the_datum(law):
    pl = _plan([R.Unit("a", (0.0, 0.0), 0.0, (_member("x", [_part(0, 0.001)]),))])
    d = json.loads(pl.to_json())
    assert d["version"] == R.PLAN_VERSION == 7 and d["flat"]["z0_m"] == Z0
    assert R.RebakePlan.from_json(pl.to_json()) == pl
    d["version"] = 4
    with pytest.raises(ValueError):
        R.RebakePlan.from_dict(d)
