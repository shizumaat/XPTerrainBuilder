"""THE ONE-GRAPH TWINS — groundside joins the route graph (cycle 8).

Owner rulings under test (docs/RULINGS.md, 2026-08-06):

* **"ONE graph: groundside joins the route graph"** — one route graph, no
  second groundside one; every connected groundside node's band derives
  from what its service-road routes reach; truly disconnected geometry is
  NOT SOLVED and mints nothing.
* **"Service-road mouths seat like apron-edge buildings"** — the mouth is
  the interface node, seated at a value where the AIRSIDE apron lawfully
  meets it, after which everything downstream grades per its own law.
* **"Frontage coupling ⇒ band seating"** — a coupled surface is seated
  FROM the band; the DEM chooses where inside it, never a bound.

Four families, one per ruled property, plus the census half of the
lockstep:

1. MOUTH SEATING — the mouth's interval IS the airside field's at that
   node (airside prices it; nothing is minted here).
2. BAND THROUGH ROADS — a node reachable only along service edges gets a
   band, and its width is the mouth's plus the road budget travelled.
3. DISCONNECTED MINTS NOTHING — the solve leaves it at DEM, marks it, the
   sidecar carries it and the census adjudicates its rows OUT OF SCOPE
   through the SAME answer (never a second predicate).
4. RECEIVER-ONLY DIRECTION — no groundside value can enter the airside
   field: the airside band is byte-identical with and without the whole
   groundside apparatus.

Every answer is hand-computed and stated before it is asserted.  No
build, no network, no X-Plane.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from auto_patch.elevation_per_surface import building_feasibility as BF  # noqa: E402


# ══════════════════════════════════════════════════════════════════════
# THE SYNTHETIC AIRPORT
#
#   node 0 ── node 1 ── node 2 ── node 3
#     |  taxi   |  taxi   | service | service
#
# Node 0 is a runway anchor at 100.0 m.  Edges 0-1 and 1-2 are TAXI spine
# edges with budget 1.0 m each; edges 2-3 and 3-4 are SERVICE edges with
# budget 4.0 m each (a road's 8 % over 50 m).  Node 2 is therefore THE
# MOUTH: a service edge touches it and the airside field reaches it.
#
# Hand-computed airside field (service-excluded, so it stops at node 2):
#   node 0: (100, 100)          node 1: (99, 101)      node 2: (98, 102)
# Mouth band at node 2 = (98, 102), width 4.
# Outward from the mouth along the road:
#   node 3: (98 − 4, 102 + 4) = (94, 106), width 12
#   node 4: (90, 110), width 20
# ══════════════════════════════════════════════════════════════════════

class _G:
    """The minimum ``UnifiedGraph`` surface the band reads."""

    def __init__(self):
        self.pos = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0),
                    3: (70.0, 0.0), 4: (120.0, 0.0)}
        self.runway_anchor = {0: 100.0}
        self.spine_adj = {
            0: [(1, 1.0)],
            1: [(0, 1.0), (2, 1.0)],
            2: [(1, 1.0), (3, 4.0)],
            3: [(2, 4.0), (4, 4.0)],
            4: [(3, 4.0)],
        }
        self.service_spine_pairs = {(2, 3), (3, 4)}


class _Layout:
    shapes = ()
    anchor = (0.0, 0.0)
    canonical_points = None


@pytest.fixture()
def graph():
    return _G()


@pytest.fixture()
def layout():
    return _Layout()


# ══════════════════════════════════════════════════════════════════════
# FAMILY 1 — THE MOUTH IS SEATED BY AIRSIDE
# ══════════════════════════════════════════════════════════════════════

def test_the_airside_field_stops_at_the_mouth(layout, graph):
    """KNOWN ANSWER.  ``spine_value_fields`` never rides a service edge,
    so it covers nodes 0-2 and NOT 3-4 — the standing exclusion this round
    inverts for groundside without touching it."""
    ceiling, floor = BF.spine_value_fields(layout, graph)
    assert set(ceiling) == {0, 1, 2}
    assert set(floor) == {0, 1, 2}
    assert ceiling[2] == pytest.approx(102.0)
    assert floor[2] == pytest.approx(98.0)


def test_the_mouth_carries_the_airside_interval_verbatim(layout, graph):
    """KNOWN ANSWER: node 2 is the only mouth, and its band is the AIRSIDE
    band there — (98, 102) — read, not minted.  "Airside always wins, and
    the mouth is seated where it's feasible for the airside apron to meet
    it."""
    mouths = BF.service_mouths(layout, graph)
    assert set(mouths) == {2}
    assert mouths[2] == (pytest.approx(98.0), pytest.approx(102.0))


def test_a_mouth_needs_BOTH_a_service_edge_and_an_airside_value(layout):
    """A service edge whose endpoints the airside field never reaches is
    not a mouth: there is no airside seat to hand it.  (Here the only
    anchor is removed, so nothing is reachable at all.)"""
    g = _G()
    g.runway_anchor = {}
    assert BF.service_mouths(layout, g) == {}


# ══════════════════════════════════════════════════════════════════════
# FAMILY 2 — THE BAND FLOWS THROUGH THE ROADS
# ══════════════════════════════════════════════════════════════════════

def test_the_band_reaches_a_node_only_service_edges_serve(layout, graph):
    """KNOWN ANSWER, hand-computed above: node 3 sits 4.0 m of road budget
    from the mouth, so its interval is (94, 106) — the mouth's, widened by
    what the ROAD's own law costs to travel.  Queried AT the node, the
    off-route leg is zero.

    Before this round that node had no band at all, which is why it kept
    its DEM seed and shipped 9,935 m from the pavement it welds to."""
    band = BF.groundside_reach_band(layout, graph)
    assert band is not None
    lo, hi = band(70.0, 0.0)
    assert lo == pytest.approx(94.0)
    assert hi == pytest.approx(106.0)


def test_the_band_widens_with_the_route_not_the_distance(layout, graph):
    """Node 4 is TWO road edges out: (90, 110).  The width grows with the
    ROUTE budget travelled (4 m per edge), which is the route metric, not
    the straight-line distance."""
    band = BF.groundside_reach_band(layout, graph)
    lo, hi = band(120.0, 0.0)
    assert lo == pytest.approx(90.0)
    assert hi == pytest.approx(110.0)


def test_an_off_route_point_pays_the_lot_cap_and_the_radius_ends_it(
        layout, graph):
    """A point 10 m off node 4 pays the GROUNDSIDE cap for the leg —
    5 % × 10 m = 0.5 m each way — and a point beyond the off-net radius
    has no coupling at all and reads ``None``, which is the ruling's
    "truly disconnected" answer."""
    from auto_patch.config import GROUNDSIDE_BAND_OFFNET_RADIUS_M
    band = BF.groundside_reach_band(layout, graph)
    lo, hi = band(120.0, 10.0)
    assert lo == pytest.approx(90.0 - 0.5)
    assert hi == pytest.approx(110.0 + 0.5)
    far = GROUNDSIDE_BAND_OFFNET_RADIUS_M + 50.0
    assert band(120.0, far) is None


def test_the_airside_interval_wins_where_both_fields_cover_a_node(
        layout, graph):
    """Node 2 is both an airside node and a mouth.  The AIRSIDE interval
    is the law there (airside is king), so the band answers (98, 102) and
    not something widened by the road it also touches."""
    band = BF.groundside_reach_band(layout, graph)
    lo, hi = band(20.0, 0.0)
    assert (lo, hi) == (pytest.approx(98.0), pytest.approx(102.0))


# ══════════════════════════════════════════════════════════════════════
# FAMILY 3 — DISCONNECTED MINTS NOTHING, AND THE CENSUS AGREES
# ══════════════════════════════════════════════════════════════════════

def test_a_ring_with_no_law_and_no_band_keeps_its_seed_and_is_marked():
    """KNOWN ANSWER.  A groundside ring with no weld, no prior field and
    no band comes back UNCHANGED (its DEM seed) and is marked
    disconnected — "it just gets left at DEM and doesn't need to be
    solved"."""
    from auto_patch.groundside import (_DISCONNECTED_ATTR,
                                       seat_groundside_on_law)
    from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
    from shapely.geometry import Polygon

    class _S:
        pass

    s = _S()
    s.role = ROLE_GROUNDSIDE_PAVEMENT
    ring = [(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)]
    s.polygon = Polygon(ring + [ring[0]])
    s.node_altitudes = None
    s.altitude = None

    class _L:
        anchor = (0.0, 0.0)
        shapes = [s]

    class _DEM:
        def alt(self, *a, **k):
            return -500.0
        alt_strict = alt

    layout = _L()
    n = seat_groundside_on_law(layout, _DEM(), 0, 0,
                               band_at=lambda x, y: None)
    assert n == 0
    assert getattr(s, _DISCONNECTED_ATTR, False) is True


def test_the_census_adjudicates_a_disconnected_ring_out_of_scope():
    """KNOWN ANSWER, the lockstep half.  Two rows: one whose BOTH points
    lie inside a declared disconnected ring, one that does not.  The first
    is stamped ``disconnected_ring`` and leaves the ADJUDICATED count; the
    second stays.  Both are still COUNTED — instruments report."""
    import check_grade as cg

    ring_m = cg._disconnected_rings_to_m(
        [[(0.0, 0.0), (0.0, 0.001), (0.001, 0.001), (0.001, 0.0)]],
        lambda la, lo: (lo * 1000.0, la * 1000.0))
    assert ring_m, "the reader must build the ring polygon"

    class _Row:
        def __init__(self, pa, pb):
            self.pt_a, self.pt_b = pa, pb
            self.out_of_scope = None
            self.way_a = self.way_b = None

    inside = _Row((0.2, 0.2), (0.6, 0.6))
    outside = _Row((5.0, 5.0), (0.2, 0.2))
    n = cg._mark_disconnected([inside, outside], [], ring_m)
    assert n == 1
    assert inside.out_of_scope == "disconnected_ring"
    assert outside.out_of_scope is None

    adj = cg.adjudication([("within_shape", inside),
                           ("within_shape", outside)])
    assert adj["out_of_scope_total"] == 1
    assert adj["out_of_scope_classes"]["disconnected_ring"]["n"] == 1
    assert adj["adjudicated_total"] == 1


def test_one_end_on_solved_geometry_is_NOT_out_of_scope():
    """A row with one end inside a disconnected ring and one end on the
    solved network is a statement about the COUPLING — if the two are that
    close the ring was not disconnected — so it stays adjudicated."""
    import check_grade as cg
    ring_m = cg._disconnected_rings_to_m(
        [[(0.0, 0.0), (0.0, 0.001), (0.001, 0.001), (0.001, 0.0)]],
        lambda la, lo: (lo * 1000.0, la * 1000.0))

    class _Row:
        def __init__(self, pa, pb):
            self.pt_a, self.pt_b = pa, pb
            self.out_of_scope = None

    straddle = _Row((0.2, 0.2), (40.0, 40.0))
    assert cg._mark_disconnected([straddle], [], ring_m) == 0
    assert straddle.out_of_scope is None


def test_the_sidecar_key_is_registered_for_every_reader():
    """The rings only work as a lockstep if the ONE sidecar reader knows
    the key — an unregistered key is a census that silently judges a
    different law (the terrace_joints precedent in CLAUDE.md)."""
    import check_grade as cg
    assert cg.SIDECAR_LAW_KEYS["disconnected_rings"] == "disconnected_rings_ll"


# ══════════════════════════════════════════════════════════════════════
# FAMILY 4 — RECEIVER-ONLY, STRUCTURALLY
# ══════════════════════════════════════════════════════════════════════

def test_the_airside_field_is_byte_identical_with_and_without_the_band(
        layout, graph):
    """THE DIRECTION TEST.  Building the groundside band cannot change the
    airside field by one float: no groundside value enters an airside
    constraint set, which is the Q4 debt's cure stated as an assertion.

    Hand-checkable: the airside field is computed, the band is built (its
    outward Dijkstra runs over the same graph), and the field is computed
    again — the two dicts must be equal, keys and values."""
    before = BF.spine_value_fields(layout, graph)
    BF.groundside_reach_band(layout, graph)
    after = BF.spine_value_fields(layout, graph)
    assert before[0] == after[0]
    assert before[1] == after[1]
    assert set(after[0]) == {0, 1, 2}, (
        "the airside field must still stop at the mouth — the groundside "
        "direction is an inversion for GROUNDSIDE reach, never a deletion "
        "of the airside exclusion")


def test_the_band_never_widens_an_airside_node_beyond_its_own_law(
        layout, graph):
    """Every node the airside field covers answers with the AIRSIDE
    interval, never the mouth-propagated one — so no groundside route can
    loosen an airside band."""
    ceiling, floor = BF.spine_value_fields(layout, graph)
    band = BF.groundside_reach_band(layout, graph)
    for i in ceiling:
        x, y = graph.pos[i]
        lo, hi = band(x, y)
        assert lo == pytest.approx(floor[i])
        assert hi == pytest.approx(ceiling[i])


# ══════════════════════════════════════════════════════════════════════
# FAMILY 4 — THE BETWEEN-RING WELD (finalarch item 1; weld-or-gap)
# ══════════════════════════════════════════════════════════════════════

def test_two_seated_rings_agree_at_their_shared_nodes():
    """S1f dossier item 2: each seat pass closed its ring WITHIN itself
    (``_grade_limit_ring``) but seated rings in ISOLATION — 894
    service_junction seatings at HECA seam 14, worst BETWEEN-ring step
    3.260 m.  Under weld-or-gap a shared-node disagreement is always a
    defect: a later ring must PIN its shared vertices to the value the
    earlier ring shipped and absorb the level change over its own run.

    Here junction B touches NO higher authority at all — only junction A
    does.  Before the weld book, B left the pass unseated (a law island
    beside a seated ring); with it, B welds to A's shipped values."""
    from shapely.geometry import Polygon
    from auto_patch.groundside import seat_service_pavement_on_law
    from auto_patch.layout import ROLE_APRON, ROLE_SERVICE_JUNCTION

    def _shape(role, x0, alts=None):
        class _S:
            pass
        s = _S()
        s.role = role
        ring = [(x0, 0.0), (x0 + 20.0, 0.0), (x0 + 20.0, 20.0),
                (x0, 20.0)]
        s.polygon = Polygon(ring + [ring[0]])
        s.node_altitudes = alts
        s.altitude = None
        s.ref = role
        return s

    apron = _shape(ROLE_APRON, 0.0, alts=[100.0] * 4)
    jct_a = _shape(ROLE_SERVICE_JUNCTION, 20.0)
    jct_b = _shape(ROLE_SERVICE_JUNCTION, 40.0)

    class _L:
        anchor = (0.0, 0.0)
        shapes = [apron, jct_a, jct_b]
        canonical_points = None

    class _DEM:
        def alt(self, *a, **k):
            return -500.0
        alt_strict = alt

    layout = _L()
    n = seat_service_pavement_on_law(layout, _DEM(), 0, 0)
    assert n == 2, (
        f"expected BOTH junctions seated (A from the apron weld, B from "
        f"the between-ring weld book); got {n}")
    a_alts = jct_a.node_altitudes
    b_alts = jct_b.node_altitudes
    assert a_alts is not None and b_alts is not None
    # The shared edge x=40: A's vertices 1,2 are B's vertices 0,3 (both
    # rings are CCW squares starting at their own x0).
    a_ring = list(jct_a.polygon.exterior.coords)[:-1]
    b_ring = list(jct_b.polygon.exterior.coords)[:-1]
    shared = {(40.0, 0.0), (40.0, 20.0)}
    a_at = {p: a_alts[i] for i, p in enumerate(a_ring) if p in shared}
    b_at = {p: b_alts[i] for i, p in enumerate(b_ring) if p in shared}
    assert a_at == b_at, (
        f"seated rings disagree at their shared nodes: {a_at} vs {b_at} "
        f"— the between-ring debt again")
    book = layout._gs_law_seat["post_solve_service_law_seat"]
    assert book.get("between_ring_weld_pins", 0) >= 2
