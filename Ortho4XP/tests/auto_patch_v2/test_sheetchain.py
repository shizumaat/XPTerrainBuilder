"""§16g (10) (4) AMENDED — A SPANNING SHEET CHAINS (owner RULINGS
2026-09-27a (1), issue #69, Q-69 (b)).

Parts of one pack terminal joined by a continuous roof / floor SHEET that
overlaps BOTH bodies' footprints are ONE §16g unit (one pad); a canopy
over ONE body links nothing (14ah holds for it).  ONE derivation
(``airport/sheet_chain``) asked by both chain sites — the design
surface's ``plan_clusters`` and the object stage's
``plan_units_and_connectors`` — so the two populations cannot drift."""
from __future__ import annotations

from auto_patch_v2.airport.footprint_unit import plan_units_and_connectors
from auto_patch_v2.airport.placement_family import plan_clusters
from auto_patch_v2.airport.sheet_chain import merge_by_sheets
from auto_patch_v2.law import Law

from test_v2connector import _lat, _PMember  # noqa: E402
from test_v2padcluster import TOUCH, _part, _plan  # noqa: E402

FRAC = 0.3


def _terminal(with_canopy=False, sheet_lat=(20, 80), deck=False,
              footed=False):
    """Two walled boxes 20 m apart (lat 0-40 and 60-100 m) — clear space
    between them — and a thin sheet over ``sheet_lat``."""
    a = _PMember("objects/a.obj", [_part(1, _lat(0), _lat(40), height=8.0)])
    b = _PMember("objects/b.obj", [_part(3, _lat(60), _lat(100), height=9.0)])
    sheet = _PMember("objects/roof.obj",
                     [_part(2, _lat(sheet_lat[0]), _lat(sheet_lat[1]),
                            height=0.3, base_y=0.0 if footed else 12.0,
                            footed=footed)])
    if deck:
        sheet.deck_kind = "signature"
    ms = [a, sheet, b]
    if with_canopy:
        # over a's north end only; never reaches b (60 m)
        ms.append(_PMember("objects/canopy.obj",
                           [_part(4, _lat(-10), _lat(10), height=0.2,
                                  base_y=5.0, footed=False)]))
    return _plan(ms)


def _sizes(cl):
    return sorted(q.bodies for q in cl)


def test_27a_a_sheet_over_two_walled_bodies_makes_ONE_cluster():
    plan = _terminal()
    # disarmed: 14ah — the sheet is a leaf, the two buildings apart
    off = plan_clusters(plan, TOUCH, chain_min_height_m=2.5)
    assert _sizes(off) == [1, 1, 1], [(q.id, q.bodies) for q in off]
    c: dict = {}
    on = plan_clusters(plan, TOUCH, chain_min_height_m=2.5, counts=c,
                       sheet_chain_min_fraction=FRAC)
    assert _sizes(on) == [3], [(q.id, q.bodies, q.walled) for q in on]
    assert on[0].walled == 2
    assert c["cluster_sheet_links"] == 1
    assert c["cluster_leaf_bodies"] == 0


def test_27a_a_canopy_over_ONE_body_links_nothing():
    plan = _terminal(with_canopy=True)
    on = plan_clusters(plan, TOUCH, chain_min_height_m=2.5,
                       sheet_chain_min_fraction=FRAC)
    # the terminal (a + roof + b) and the canopy a leaf of its own
    assert _sizes(on) == [1, 3], [(q.id, q.bodies) for q in on]
    # and with no spanning roof the canopy alone never joins a to b
    solo = _terminal(with_canopy=True, sheet_lat=(-30, -20))
    got = plan_clusters(solo, TOUCH, chain_min_height_m=2.5,
                        sheet_chain_min_fraction=FRAC)
    assert _sizes(got) == [1, 1, 1, 1], [(q.id, q.bodies) for q in got]


def test_27a_a_slab_TOUCHING_two_bodies_is_still_a_leaf():
    """14ah's own fixture: a slab between two buildings that touches both
    at an edge but covers neither — the ruling is about a sheet that
    OVERLAPS both footprints, not one resting against them."""
    plan = _terminal(sheet_lat=(40, 60))
    got = plan_clusters(plan, TOUCH, chain_min_height_m=2.5,
                        sheet_chain_min_fraction=FRAC)
    assert _sizes(got) == [1, 1, 1], [(q.id, q.bodies) for q in got]


def test_27a_a_small_overlap_under_the_fraction_links_nothing():
    # 1 m into each 40 m body: 1/40 of the smaller footprint
    plan = _terminal(sheet_lat=(39, 61))
    got = plan_clusters(plan, TOUCH, chain_min_height_m=2.5,
                        sheet_chain_min_fraction=FRAC)
    assert _sizes(got) == [1, 1, 1], [(q.id, q.bodies) for q in got]


def test_27a_a_DECK_spanning_two_bodies_links_nothing():
    """A deck keeps its own datum law (§16e) and the welded-deck shade
    (#14): it is never a sheet link."""
    plan = _terminal(deck=True)
    got = plan_clusters(plan, TOUCH, chain_min_height_m=2.5,
                        sheet_chain_min_fraction=FRAC)
    assert _sizes(got) == [1, 1, 1], [(q.id, q.bodies) for q in got]


def test_27a_a_GROUND_slab_under_two_bodies_links_nothing():
    """A footed leaf — a paving slab two buildings stand on — leaves them
    separated by clear space (18t); it is the class 14ah measured
    over-chaining HECA's T3 district."""
    plan = _terminal(footed=True)
    c: dict = {}
    got = plan_clusters(plan, TOUCH, chain_min_height_m=2.5,
                        sheet_chain_min_fraction=FRAC)
    assert _sizes(got) == [1, 1, 1], [(q.id, q.bodies) for q in got]
    un, _c = plan_units_and_connectors(plan, TOUCH, 0.0, c,
                                       chain_min_height_m=2.5,
                                       sheet_chain_min_fraction=FRAC)
    assert un == [] and c["unit_sheet_refused_footed"] == 1


def test_27a_the_object_stage_UNIT_reads_the_same_link():
    """§16g (9) ONE POPULATION: the unit chain asks the same question."""
    plan = _terminal(with_canopy=True)
    off, _c = plan_units_and_connectors(plan, TOUCH, 0.0, {},
                                        chain_min_height_m=2.5)
    assert off == [], [u.bodies for u in off]
    c: dict = {}
    on, _c = plan_units_and_connectors(plan, TOUCH, 0.0, c,
                                       chain_min_height_m=2.5,
                                       sheet_chain_min_fraction=FRAC)
    assert len(on) == 1, [u.bodies for u in on]
    res = sorted(on[0].members)
    assert res == ["objects/a.obj", "objects/b.obj", "objects/roof.obj"], res
    assert c["unit_sheet_links"] == 1 and c["unit_sheet_over_one_body"] == 1


def test_27a_merge_by_sheets_joins_chains_and_singletons():
    adj: dict = {}
    got = merge_by_sheets([[0, 1], [2]], [(5, (1, 2)), (6, (3, 4))], adj)
    assert got == [[0, 1, 2, 5], [3, 4, 6]]
    assert adj[5] == {1, 2} and adj[3] == {6}


def test_27a_the_law_key_is_armed():
    st = Law.for_airport("OTHH").tables.structures.placement
    assert 0.0 < float(st.sheet_chain_min_fraction) <= 1.0
