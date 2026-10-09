"""Spec §59 (owner RULINGS 2026-10-08c (6), 08g): a gap piece classed APRON
is a stage-1 ``apron`` cell, ref ``gapapron:<j>`` — the names, and the one
planar consumer that must not see it (the zone claim: "with the runway held
at zero")."""
from __future__ import annotations

from shapely.geometry import box

from auto_patch_v2.classify.roles import Cell, is_late_cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_side
from auto_patch_v2.model import planar as mp
from auto_patch_v2.planar.zones import zone_regions

LAW = Law.for_airport("HECA")


def _ring(b):
    return tuple(b.exterior.coords)[:-1]


def _cell(i, role, ref, b, code_number=None, code_letter=None):
    return Cell(i, role, ref, _ring(b), (), code_number, code_letter,
                role_side(LAW, role), role, {})


def test_a_gap_apron_ref_is_no_gap_piece_and_is_not_late():
    ref = f"{mp.GAP_APRON_PREFIX}:3"
    assert mp.is_gap_apron_ref(ref) and mp.is_gap_apron_ref(ref + "#1")
    assert not mp.is_gap_ref(ref) and not mp.is_late_ref(ref)
    assert not mp.is_gap_apron_ref("gap:3") and not mp.is_gap_apron_ref("pav3")
    assert not mp.is_gap_apron_ref(None)
    assert mp.gap_part_kind(ref) is None and not mp.gap_step_part(ref)
    # a stage-1 cell: never dropped from the ribbon-free / gap-free maps
    assert not is_late_cell(_cell(0, "apron", ref, box(0, 0, 1, 1)))


def _zones(cells):
    return [(z.ref, z.polygon.wkb_hex) for z in zone_regions(tuple(cells), LAW)]


def test_a_gap_apron_cell_is_not_in_the_zone_claim():
    """The zone bands are the STANDING cells' (§59, the runway's planar
    half): a gap-apron cell — minted outside every band's envelope — leaves
    every band byte-identical, however the claim's union would re-node."""
    runway = _cell(0, "runway", "05/23", box(0, 0, 3000, 60), code_number=4)
    taxi = _cell(1, "junction", "pav9", box(1000, 60, 1030, 400), code_letter="E")
    apron = _cell(2, "apron", "pav1", box(900, 400, 1200, 700))
    base = _zones([runway, taxi, apron])
    assert base                                           # there ARE bands here
    far = _cell(3, "apron", "gapapron:0", box(1200, 420, 1260, 480))
    assert _zones([runway, taxi, apron, far]) == base
    # the same polygon as a standing apron IS in the claim (today's rule)
    assert _zones([runway, taxi, apron,
                   _cell(3, "apron", "pav2", box(1035, 100, 1100, 160))]) != base


def test_a_gap_apron_cell_that_reaches_a_band_is_cut_out_of_that_band():
    """Planarity is kept where the stand-off did not hold: the band yields
    the cell's ground, and no other band moves."""
    runway = _cell(0, "runway", "05/23", box(0, 0, 3000, 60), code_number=4)
    taxi = _cell(1, "junction", "pav9", box(1000, 60, 1030, 400), code_letter="E")
    part = box(1035, 100, 1100, 160)
    got = zone_regions((runway, taxi, _cell(2, "apron", "gapapron:0", part)), LAW)
    assert got and all(z.polygon.intersection(part).area < 1e-6 for z in got)


# ── S2: the ONE road-evidence reader, two keywords (§59 (1)) ─────────────

def _ev(truck=(), roads=()):
    import types
    from shapely.geometry import LineString
    mk = lambda pts: types.SimpleNamespace(line=LineString(pts))  # noqa: E731
    return types.SimpleNamespace(truck_chains=[mk(p) for p in truck],
                                 road_chains=[mk(p) for p in roads])


def test_road_evidence_defaults_are_todays_reader():
    from auto_patch_v2.classify.roles import _road_evidence
    from auto_patch_v2.classify.rules import load_rules
    rules = load_rules()
    scored = [(box(0, 0, 50, 50), "apron"),                 # a route runs through
              (box(100, 0, 150, 50), "apron"),              # a lot touches it
              (box(150, 0, 200, 50), "parking_lot"),
              (box(300, 0, 350, 50), "apron"),              # 1.4 m off a service road
              (box(351.4, 0, 360, 50), "service_road"),
              (box(500, 0, 550, 50), "apron")]              # nothing
    ev = _ev(truck=[[(-10, 25), (60, 25)]])
    today = _road_evidence(scored, ev, rules)
    assert today == {0, 1, 2, 4}
    assert _road_evidence(scored, ev, rules, touch_tol_m=None,
                          touch_roles=("service_road", "parking_lot")) == today


def test_road_evidence_at_the_stand_off_and_over_the_road_family():
    """A gap piece stands ``standoff_m`` off every road face: evidenced at
    the stand-off, not at ``groundside.touch_tol_m``; ``touch_roles`` names
    the faces that count."""
    from auto_patch_v2.classify.gap_mint import standoff_m
    from auto_patch_v2.classify.roles import _road_evidence
    from auto_patch_v2.classify.rules import load_rules
    rules = load_rules()
    stand = standoff_m(LAW)
    piece = box(0, 0, 50, 50)
    scored = [(piece, "groundside_pavement"),
              (box(50 + stand, 0, 60 + stand, 50), "service_junction")]
    ev = _ev()
    assert _road_evidence(scored, ev, rules) == set()
    assert 0 not in _road_evidence(scored, ev, rules, touch_tol_m=stand + 1.0)
    assert 0 in _road_evidence(scored, ev, rules, touch_tol_m=stand + 1.0,
                               touch_roles=("service_road", "service_junction"))
    # an OSM road ON the piece (the sheet-union ``_osm_roads`` call's chains)
    assert 0 in _road_evidence(scored[:1], _ev(roads=[[(10, 10), (40, 40)]]), rules)


# ── S3: §27 with the road-by-evidence verdict handed in (§59 (2) 2) ──────

def _flip(final_extra, road_class=None, roads=()):
    from auto_patch_v2.classify.airside_edge import airside_edge_flip
    from auto_patch_v2.classify.rules import load_rules
    final = [list(t) + [str(t[4].get("kind", ""))] for t in final_extra]
    n, _rounds = airside_edge_flip(final, [], LAW, load_rules(), roads,
                                   road_class=road_class)
    return n, [f[0] for f in final], final


def test_road_class_none_is_the_born_role_read():
    apron = ("apron", "pav1", box(0, 0, 100, 100), None, {})
    lot = ("groundside_pavement", "gap:0", box(100, 0, 200, 12), None, {})
    assert _flip([apron, lot])[1] == ["apron", "apron"]             # 12 m lateral: a lot flips
    assert _flip([apron, lot], road_class=frozenset())[1] == ["apron", "apron"]


def test_a_road_class_piece_flips_by_share_a_lot_class_piece_by_edge():
    apron = ("apron", "pav1", box(0, 0, 100, 100), None, {})
    # 12 m of lateral apron edge on a 2 x (12 + 100) = 224 m perimeter: 5 %
    thin = ("groundside_pavement", "gap:0", box(100, 0, 200, 12), None, {})
    n, roles, _f = _flip([apron, thin], road_class=frozenset({1}))
    assert n == 0 and roles[1] == "groundside_pavement"             # a road that grazes
    # 60 m of lateral edge on a 2 x (60 + 20) = 160 m perimeter: 37.5 %
    along = ("groundside_pavement", "gap:1", box(100, 0, 120, 60), None, {})
    n, roles, final = _flip([apron, along], road_class=frozenset({1}))
    assert n == 1 and roles[1] == "apron"                           # a strip that SITS against it
    assert final[1][4]["airside_edge_m"] >= 60.0
    assert final[1][4]["airside_edge_was"] == "groundside_pavement"
