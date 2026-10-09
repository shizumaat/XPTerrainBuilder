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


# ── S4: the mint — evidence -> class -> spelling -> rim closure (§59 (2)) ─

def _mint(sheets, cells, truck=()):
    from test_gap_mint import _airport, _mint as mint, _evidence
    return mint(_airport(*sheets), cells, _evidence(truck))


APRON = box(0, 0, 100, 50)


def test_a_touching_piece_with_no_road_is_the_apron():
    out, stats, notes = _mint([box(0, 50, 12, 150)], [_cell(0, "apron", "pav1", APRON)])
    (role, ref, part, kind, ev), = out
    assert (role, ref, kind) == ("apron", "gapapron:0", "gap_apron")
    assert ev["gap_ref"] == "gap:0" and ev["road_evidence"] == 0.0
    assert ev["gap_apron"] == 1.0 and ev["airside_edge_m"] >= 12.0
    assert ev["area_m2"] == part.area and "gap_piece" not in ev
    assert (stats["gap_pieces"], stats["gap_pieces_apron"], stats["gap_pieces_road"]) == (1, 1, 0)
    assert any("gapapron:0" in n and "apron — no road evidence" in n for n in notes)


def test_a_road_at_the_stand_off_keeps_a_grazing_piece_a_road():
    """12 m of a 224 m perimeter: a road that touches the apron and leaves."""
    from auto_patch_v2.classify.gap_mint import ROLE, KIND
    road = _cell(1, "service_road", "route3", box(12, 60, 20, 150))
    out, stats, _n = _mint([box(0, 50, 20, 150)], [_cell(0, "apron", "pav1", APRON), road])
    (role, ref, _part, kind, ev), = out
    assert (role, ref, kind) == (ROLE, "gap:0", KIND)
    assert ev["road_evidence"] == 1.0 and ev["touches_apron"] == 1.0 and ev["gap_piece"] == 1.0
    assert (stats["gap_pieces_apron"], stats["gap_pieces_road"]) == (0, 1)
    # a 1206 route through the piece is road evidence too (the reader's own)
    out, _s, _n = _mint([box(0, 50, 12, 150)], [_cell(0, "apron", "pav1", APRON)],
                        truck=[[(6, 60), (6, 140)]])
    assert out[0][1] == "gap:0" and out[0][4]["road_evidence"] == 1.0


def test_a_road_evidenced_strip_that_sits_against_the_apron_is_the_apron():
    """A ribbon flush along it AND 100 m of a 240 m perimeter on the apron:
    §37 (2)'s share — the free-road ruling."""
    ribbon = _cell(1, "service_road", "small_roads:-1", box(0, 70, 100, 76))
    out, stats, notes = _mint([box(0, 50, 100, 76)],
                              [_cell(0, "apron", "pav1", APRON), ribbon])
    (role, ref, _part, _kind, ev), = out
    assert (role, ref) == ("apron", "gapapron:0") and ev["road_evidence"] == 1.0
    assert ev["airside_edge_m"] >= 100.0
    assert any("lateral airside edge (§37 (2))" in n for n in notes)


def test_the_two_counters_run_in_the_mints_part_order():
    """``gap:<k>`` is the part's ordinal among ALL minted parts (a road
    piece keeps the ref it has today), ``gapapron:<j>`` among the apron's."""
    road = _cell(1, "service_road", "route3", box(212, 60, 220, 400))
    sheets = [box(200, 50, 220, 400),                  # largest: road (grazes)
              box(0, 50, 12, 150),                     # apron, no evidence
              box(60, 50, 72, 100)]                    # apron, no evidence
    cells = [_cell(0, "apron", "pav1", box(0, 0, 300, 50)), road]
    out, _s, _n = _mint(sheets, cells)
    assert [(ref, ev.get("gap_ref")) for _r, ref, _p, _k, ev in out] == [
        ("gap:0", None), ("gapapron:0", "gap:1"), ("gapapron:1", "gap:2")]


def test_no_road_evidence_is_apron_even_where_section_27_would_not_flip():
    """THE RULING'S WORDS (08c (6)): §27's sliver floor never flips a face
    this thin; a touching piece with no road evidence is the apron all the
    same.  (Flagged for the spec author: §59 (2) 2 reads 'a part the pass
    leaves groundside is ROAD'.)"""
    from shapely.ops import unary_union
    from auto_patch_v2.classify import airside_edge as ae
    body = unary_union([box(0, 50, 15, 65), box(15, 57, 615, 57.5)])
    assert body.area / body.length < ae._LOT_SLIVER_RADIUS_M
    out, _s, _n = _mint([body], [_cell(0, "apron", "pav1", APRON)])
    assert out and out[0][0] == "apron" and out[0][4]["road_evidence"] == 0.0


def _unwelded_m2(part, apron, weld_m, keep_out=None):
    """Ground BETWEEN a part and an apron whose rims face each other within
    the weld spacing without coinciding: the bodies of the closing of the
    two (less both, less ``keep_out``) that reach both rims."""
    def off(g, d):
        return g.buffer(d, join_style="mitre", mitre_limit=2.0)
    both = part.union(apron)
    gap = off(off(both, weld_m), -weld_m).difference(both)
    if keep_out is not None:
        gap = gap.difference(keep_out)
    return sum(g.area for g in getattr(gap, "geoms", [gap])
               if not g.is_empty and g.distance(part) <= 1e-3 and g.distance(apron) <= 1e-3)


def test_an_apron_parts_rim_is_closed_onto_the_apron_ring():
    """§59 (2) 4: the sheet's edge runs 0.5 m off the apron's (within the
    weld spacing, not coincident) — the apron part's rim IS the apron's
    afterwards; a ROAD part keeps today's rim."""
    weld = LAW.tables.emit.identity.weld_spacing_m
    sheet = box(0, 50.5, 100, 90)
    out, _s, _n = _mint([sheet], [_cell(0, "apron", "pav1", APRON)])
    part = out[0][2]
    assert out[0][1] == "gapapron:0"
    assert _unwelded_m2(sheet, APRON, weld) == 50.0          # before: the 0.5 m strip
    assert _unwelded_m2(part, APRON, weld) == 0.0
    assert part.bounds == (0.0, 50.0, 100.0, 90.0)           # no ear past the contact's ends
    assert part.intersection(APRON).area == 0.0
    assert part.boundary.intersection(APRON.boundary).length == 100.0
    assert out[0][4]["area_m2"] == part.area == 4000.0
    # the closure never crosses a standing cell's stand-off
    road = _cell(1, "service_road", "route3", box(40, 50.2, 60, 50.4))
    out, _s, _n = _mint([sheet], [_cell(0, "apron", "pav1", APRON), road])
    from auto_patch_v2.classify.gap_mint import standoff_m
    assert all(o[2].distance(box(40, 50.2, 60, 50.4)) >= standoff_m(LAW) - 0.02 for o in out)
    # a road-class part is not closed
    grazing = box(0, 50.5, 12, 150)
    road = _cell(1, "service_road", "route3", box(12 + 1.45, 60, 20, 150))
    out, _s, _n = _mint([grazing], [_cell(0, "apron", "pav1", APRON), road])
    assert out[0][1] == "gap:0" and out[0][2].bounds[1] == 50.5


def test_a_sheet_free_airport_never_reaches_the_readers(monkeypatch):
    """§59 (5) NO-OP: the mint returns before the class on no sheet; and a
    piece that touches no apron is not judged."""
    from auto_patch_v2.classify import gap_mint as gm

    def boom(*a, **k):
        raise AssertionError("the §59 class was read")
    monkeypatch.setattr(gm, "judge", boom)
    monkeypatch.setattr(gm, "close_rim", boom)
    assert _mint([], [_cell(0, "apron", "pav1", APRON)])[0] == []
    out, _s, _n = _mint([box(300, 0, 340, 40)], [_cell(0, "apron", "pav1", APRON)])
    assert [o[1] for o in out] == ["gap:0"] and "road_evidence" not in out[0][4]


# ── the HECA frame twin: the class table (§59 (5)) ───────────────────────

import pathlib  # noqa: E402

import pytest  # noqa: E402

FRAME = pathlib.Path("/Users/noah/XPTerrainBuilderData/.harness/frames/gapapron3/HECA.pkl")


@pytest.mark.skipif(not FRAME.exists(), reason="frames gapapron3 (the capture) not mounted")
def test_the_class_table_read_on_a_real_map():
    """A change in this table is a change in the rule.  AS RE-DERIVED on the
    fresh capture (lane gapapron3 S0): 38 pieces, 19 apron-touching."""
    import dataclasses as dc
    import pickle

    from auto_patch_v2.airport import frame_entry as fe
    from auto_patch_v2.airport.obj8 import ResourceCache
    from auto_patch_v2.classify import classify
    from auto_patch_v2.classify.rules import load_rules
    from auto_patch_v2.planar.cluster import clusters
    from shapely.geometry import Point, Polygon
    with open(FRAME, "rb") as fh:
        airport = pickle.load(fh)["airport"]
    law = Law.for_airport(airport.icao)
    airport = dc.replace(airport, clusters=clusters(airport, law))
    cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m, fe.quantum(law))
    cl = classify(airport, law, load_rules(), cache=cache)
    pieces = [c for c in cl.cells if mp.is_gap_ref(c.ref)]
    aprons = [c for c in cl.cells if mp.is_gap_apron_ref(c.ref)]
    assert len(pieces) + len(aprons) == 38 == cl.stats["gap_pieces"]
    road = sorted(int(c.ref.split(":")[1]) for c in pieces
                  if c.evidence.get("touches_apron") == 1.0)
    assert road == [0, 2, 4, 7, 11, 12, 28, 29]
    assert all(c.evidence["road_evidence"] == 1.0 for c in pieces
               if c.evidence.get("touches_apron") == 1.0)
    by = {False: [], True: []}
    for c in aprons:
        assert c.role == "apron" and c.side == "airside" and c.kind == "gap_apron"
        by[c.evidence["road_evidence"] == 1.0].append(int(c.evidence["gap_ref"].split(":")[1]))
    assert sorted(by[False]) == [22, 24, 35]                       # no road evidence
    assert sorted(by[True]) == [13, 15, 16, 17, 20, 30, 33, 36]    # §37 (2)'s share
    assert [c.ref for c in aprons] == [f"gapapron:{j}" for j in range(11)]
    assert (cl.stats["gap_pieces_apron"], cl.stats["gap_pieces_road"]) == (11, 8)
    # the owner's sites stand in ROAD pieces (#430 / #292: gap:7; #358: gap:0)
    to_xy = airport.frame.transformers()[0]
    for (lat, lon), ref in {(30.1154841, 31.4105884): "gap:7", (30.1159784, 31.4106264): "gap:7",
                            (30.1193169, 31.4085087): "gap:0"}.items():
        pt = Point(*to_xy(lon, lat))
        assert [c.ref for c in pieces if Polygon(c.ring, c.holes).contains(pt)] == [ref]
    # THE RIM CLOSURE (§59 (2) 4): no apron|apron rim pair of a gap-apron face
    # stands within the weld spacing unwelded — but where §53 (12) keeps the
    # piece out (a standing cell's stand-off, the runway / taxi band envelope).
    # Under 1 m2 is the snap grid's hairline (0.6 m2 over 523 m at gapapron:0).
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    from auto_patch_v2.classify.gap_mint import standoff_m
    from auto_patch_v2.classify.ribbon_mint import ribbon_extent
    weld, stand = law.tables.emit.identity.weld_spacing_m, standoff_m(law)

    def off(g):
        return g.buffer(stand, join_style="mitre", mitre_limit=2.0)
    standing = [Polygon(c.ring, c.holes) for c in cl.cells
                if c.role == "apron" and not mp.is_gap_apron_ref(c.ref)]
    apart = [Polygon(c.ring, c.holes) for c in cl.cells
             if c.role != "apron" and not mp.is_osm_ribbon_ref(c.ref)
             and not mp.is_gap_ref(c.ref)]
    flush = [Polygon(c.ring, c.holes) for c in cl.cells
             if mp.is_osm_ribbon_ref(c.ref) or mp.is_gap_ref(c.ref)]
    bands = off(ribbon_extent(list(cl.cells), law, Polygon()))
    tree, atree, ftree = STRtree(standing), STRtree(apart), STRtree(flush)
    grew = 0
    for c in aprons:
        part = Polygon(c.ring, c.holes)
        reach = part.buffer(2 * weld + 2 * stand)
        near = unary_union([standing[int(j)] for j in tree.query(reach, predicate="intersects")])
        keep = unary_union([bands.intersection(reach)]
                           + [off(apart[int(j)]) for j in atree.query(reach, predicate="intersects")]
                           + [flush[int(j)] for j in ftree.query(reach, predicate="intersects")])
        assert _unwelded_m2(part, near, weld, keep) < 1.0, c.ref
        grew += part.area > c.evidence["area_m2"] - 1e-6 and part.is_valid
    assert grew == 11
    # the spec's sliver site (the census's apron|apron step, gap:30 | pav39)
    # is inside the part now
    site = Point(*to_xy(31.4046286, 30.1278259))
    assert Polygon(aprons[7].ring, aprons[7].holes).contains(site)


# ── S5: the sidecar's ``gap_pieces`` carries both kinds (§59 (4) row 17) ──

def test_gap_pieces_publishes_the_apron_parts_beside_the_cut_parts():
    from auto_patch_v2.pipeline.publication import gap_pieces
    out, _s, _n = _mint([box(0, 50, 12, 150)], [_cell(0, "apron", "pav1", APRON)])
    cells = [_cell(0, "apron", "pav1", APRON),
             Cell(1, out[0][0], out[0][1], _ring(out[0][2]), (), None, None,
                  "airside", out[0][3], out[0][4])]
    cut = {"pieces": [{"ref": "gap:1", "groups": 1, "knives": 0, "stations": {"road": 2},
                       "conflicts_merged": [],
                       "parts": [{"ref": "gap:1/lot", "kind": "lot", "m2": 310.0}]}]}
    got = gap_pieces(cut, cells)
    assert [(r["ref"], r["kind"]) for r in got] == [("gap:1/lot", "lot"), ("gapapron:0", "apron")]
    assert got[1] == {"ref": "gapapron:0", "kind": "apron", "m2": 1200.0, "gap_ref": "gap:0",
                      "apron_shared_m": 14.0, "airside_edge_m": 14.0, "road_evidence": False}
    # no last stage ran (every touching piece is apron): the apron records alone
    assert gap_pieces(None, cells) == got[1:]
    assert gap_pieces(cut) == got[:1] and gap_pieces(None, cells[:1]) == []
