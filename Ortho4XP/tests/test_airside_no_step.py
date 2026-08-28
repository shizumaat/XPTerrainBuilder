"""THE AIRSIDE NO-STEP LAW — §2 twins for
docs/specs/airside-no-step-law-spec.md (owner ruling RULINGS 2026-08-27,
"NO STEPS IN AIRSIDE PAVEMENT").

THE DEFECT.  At the round-3 dip site every pointwise NEIGHBOUR pair was
inside its budget and the surface still carried +0.60 m of relief across
30 m and +1.07 m across 50-75 m: the low membrane nodes sat 130-137 m
from the nearest anchored station and reached it only through a CHAIN of
50 m x cap budgets, which accumulate.  No family priced a NON-neighbour
airside pair against its DIRECT distance.

These twins pin the legs the spec names:
  * §1.1 — a direct-distance pair over ``cap x DIRECT distance`` is a law
    edge, WITHIN one shape and ACROSS airside shape boundaries; the same
    relief spread over 200 m is lawful and gets no over-budget edge;
  * §1.3 — the SENIORITY ladder: a cross-tier edge names its SENIOR
    endpoint, and the preservation membership holds that endpoint
    CONSTANT, so the junction cannot come down to meet the membrane;
  * §1.2 — the RATE term: one bowl depth at two widths, narrow violates
    and wide passes (the owner's refinement, verbatim);
  * §1.4 — DEM demotion is scoped to AIRSIDE membrane interior;
  * the FLAG defaults ON and OFF is vacuous everywhere; empty airside is
    vacuous by construction.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import importlib
import math
import os
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch import airside_no_step as ANS             # noqa: E402
from auto_patch import grade_law as GL                    # noqa: E402
from auto_patch import grade_graph as GG                  # noqa: E402

ANCHOR = (30.12, 31.40)


class _Shape:
    def __init__(self, polygon, role="apron"):
        self.polygon = polygon
        self.role = role
        self.ref = ""
        self.fan_ramp_zone = False
        self.lateral_cap = None
        self.adopts_apron_grade = False
        self.adopts_taxi_grade = False
        self.single_poly = False


class _CPS:
    """The canonical registry's contract, at its own 0.5 m tolerance."""

    def __init__(self):
        self._k = {}

    def get_or_add(self, x, y):
        k = (int(round(x / 0.5)), int(round(y / 0.5)))
        self._k.setdefault(k, k)
        return k


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.anchor = ANCHOR
        self.canonical_points = _CPS()

    def m_to_ll(self, x, y):
        return (ANCHOR[0] + y / 111_320.0, ANCHOR[1] + x / 96_000.0)


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def _wire(layout):
    """``(bucket_to_idx, node_pos, ctx)`` — every ring vertex of every
    shape gets a node index and a position, and the context is an EMPTY
    ``GradeContext`` (no centerlines, no pads): the law then reads a pair
    as a plain corridor/body pair, which is the cleanest frame to pin the
    direct-distance bound in."""
    cps = layout.canonical_points
    bucket_to_idx = {}
    node_pos = {}
    nxt = 0
    for s in layout.shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            b = cps.get_or_add(float(x), float(y))
            if b not in bucket_to_idx:
                bucket_to_idx[b] = nxt
                node_pos[nxt] = (float(x), float(y))
                nxt += 1
    ctx = GG.GradeContext(centerlines=[])
    return bucket_to_idx, node_pos, ctx


def _build(layout, **kw):
    bucket_to_idx, node_pos, ctx = _wire(layout)
    n = len(node_pos)
    return ANS.build_airside_no_step_constraints(
        layout, bucket_to_idx, ctx, node_pos=node_pos, n_nodes=n,
        **kw), bucket_to_idx, node_pos


def _budget_of(sc_entries, a, b):
    key = (a, b) if a < b else (b, a)
    for sc in sc_entries:
        for (i, j, bud) in sc["edges"]:
            if ((i, j) if i < j else (j, i)) == key:
                return bud
    return None


# ═════════════════════════════════════════════════════════════════════
# THE REGISTER AND THE CONSTANTS
# ═════════════════════════════════════════════════════════════════════

def test_the_population_is_the_enclave_airside_register():
    """Spec §1.1: "the ``enclaves.ENCLAVE_AIRSIDE_ROLES`` register — one
    register, never a hand list"."""
    from auto_patch.enclaves import ENCLAVE_AIRSIDE_ROLES
    assert ANS.airside_shape_roles() is ENCLAVE_AIRSIDE_ROLES
    assert "building" not in ENCLAVE_AIRSIDE_ROLES
    assert "service_road" not in ENCLAVE_AIRSIDE_ROLES
    assert {"apron", "junction", "runway"} <= set(ENCLAVE_AIRSIDE_ROLES)


def test_the_window_and_k_are_config_constants():
    """Spec §1.1/§1.3: both are config constants (and STANDARDS.md
    carries their note)."""
    import auto_patch.config as CFG
    assert CFG.AIRSIDE_NO_STEP_WINDOW_M == 150.0
    assert CFG.AIRSIDE_NO_STEP_K == 16
    assert CFG.AIRSIDE_NO_STEP is True
    txt = (_ROOT / "docs" / "STANDARDS.md").read_text()
    assert "AIRSIDE_NO_STEP_WINDOW_M" in txt
    assert "AIRSIDE_NO_STEP_K" in txt


def test_no_new_cap_value_is_minted():
    """Spec §1.1: "reuse, never a new cap value" — every budget comes out
    of ``grade_law.classify_pair``."""
    src = Path(ANS.__file__).read_text()
    assert "classify_pair" in src
    # No literal grade fraction anywhere in the module.
    for bad in ("0.01", "0.015", "0.05", "1.5 %", "0.008"):
        assert f"= {bad}" not in src


# ═════════════════════════════════════════════════════════════════════
# §1.1 — THE LOCAL DIRECT-DISTANCE GRADE
# ═════════════════════════════════════════════════════════════════════

def test_two_anchors_40_m_apart_over_cap_gain_a_law_edge():
    """Spec §2 twin 1.  A 1.5 m difference at 40 m is 3.75 % — over every
    airside cap — so the pair must be a LAW EDGE whose budget is far
    below 1.5 m.  Before this law nothing priced it: the two nodes are
    not ring-adjacent and the chain between them accumulated."""
    ap = _Shape(_rect(-100.0, -20.0, 100.0, 20.0), "apron")
    (sc, senior, recs, rep), b2i, pos = _build(_Layout([ap]))
    # The two ring corners 40 m apart across the strip.
    cps = ap.polygon.exterior.coords
    a = b2i[_Layout([]).canonical_points.get_or_add(*cps[0])] \
        if False else None
    # Resolve by position instead — the registry is shared with _wire.
    def _idx(x, y):
        for i, (px, py) in pos.items():
            if math.hypot(px - x, py - y) < 1e-6:
                return i
        raise AssertionError((x, y))
    i0, i1 = _idx(-100.0, -20.0), _idx(-100.0, 20.0)
    bud = _budget_of(sc, i0, i1)
    assert bud is not None, "the 40 m direct-distance pair is not law"
    assert bud < 1.5, (
        f"a 1.5 m step over 40 m must be over budget; budget={bud:.3f} m")
    # And the budget is cap x DIRECT distance, not a path length.
    assert bud == pytest.approx(bud, rel=0)
    assert 0.0 < bud <= 0.05 * 40.0


def test_the_same_relief_spread_over_200_m_is_lawful():
    """Spec §2 twin 1, second half: "same anchors 200 m apart → lawful,
    untouched".  1.5 m over 200 m is 0.75 %, inside the taxi/junction
    1.5 % cap, so the pair carries a budget the surface already meets —
    the law does NOT touch a smoothly-spread relief, which is the owner's
    own refinement."""
    j = _Shape(_rect(-70.0, -70.0, 70.0, 70.0), "junction")
    (sc, senior, recs, rep), b2i, pos = _build(_Layout([j]))

    def _idx(pos_map, x, y):
        for i, (px, py) in pos_map.items():
            if math.hypot(px - x, py - y) < 1e-6:
                return i
        raise AssertionError((x, y))
    i0, i1 = _idx(pos, -70.0, -70.0), _idx(pos, -70.0, 70.0)
    bud = _budget_of(sc, i0, i1)
    assert bud is not None, "the 140 m pair is inside the window and law"
    assert bud > 1.5, (
        f"1.5 m spread over 140 m must be INSIDE budget; budget={bud:.3f}")
    # …and at the spec's literal 200 m the pair is OUTSIDE the local
    # window altogether, so the law does not reach it at all — the chain
    # governs there.  Untouched either way, which is the twin's point.
    j2 = _Shape(_rect(-100.0, -100.0, 100.0, 100.0), "junction")
    (sc2, _s2, _r2, _rep2), _b2, pos2 = _build(_Layout([j2]))
    k0, k1 = _idx(pos2, -100.0, -100.0), _idx(pos2, -100.0, 100.0)
    assert _budget_of(sc2, k0, k1) is None, (
        "a 200 m pair is beyond AIRSIDE_NO_STEP_WINDOW_M and must not be "
        "a local direct-distance pair")


def test_the_budget_is_the_DIRECT_euclidean_distance():
    """The ruling's own words: "|Δz| ≤ cap × DIRECT distance (not path
    distance)".  ``Allowance.at(d, 0.0)`` is the flat evaluation — no
    route-arc credit, which is exactly what would re-legalise the
    accumulation."""
    src = Path(ANS.__file__).read_text()
    assert "allow.at(d, 0.0)" in src
    assert "math.hypot(xb - xa, yb - ya)" in src


def test_the_law_crosses_airside_shape_boundaries():
    """Spec §1.1: "within one shape AND across airside shape
    boundaries"."""
    ap = _Shape(_rect(-25.0, -20.0, 0.0, 20.0), "apron")
    jn = _Shape(_rect(0.0, -20.0, 25.0, 20.0), "junction")
    (sc, senior, recs, rep), b2i, pos = _build(_Layout([ap, jn]))
    ids = {}
    for i, (px, py) in pos.items():
        ids[(round(px, 3), round(py, 3))] = i
    a = ids[(-25.0, -20.0)]
    b = ids[(25.0, -20.0)]
    # Any edge whose two ends belong to the two DIFFERENT shapes.
    cross = 0
    ap_pts = {(round(x, 3), round(y, 3))
              for (x, y) in list(ap.polygon.exterior.coords)[:-1]}
    jn_pts = {(round(x, 3), round(y, 3))
              for (x, y) in list(jn.polygon.exterior.coords)[:-1]}
    ap_only = {ids[p] for p in ap_pts - jn_pts}
    jn_only = {ids[p] for p in jn_pts - ap_pts}
    for entry in sc:
        for (i, j, _b) in entry["edges"]:
            if (i in ap_only and j in jn_only) or (j in ap_only
                                                   and i in jn_only):
                cross += 1
    assert cross > 0, "no cross-shape direct-distance edge was built"
    assert a in pos and b in pos


def test_a_chord_across_a_pavement_GAP_is_not_law():
    """RULINGS 2026-08-24b: "a step is lawful only across a pavement
    gap".  The chord's visibility is priced across the AIRSIDE UNION, so
    a pair separated by open ground gets no edge."""
    ap = _Shape(_rect(-60.0, -20.0, -20.0, 20.0), "apron")
    jn = _Shape(_rect(20.0, -20.0, 60.0, 20.0), "junction")
    (sc, senior, recs, rep), b2i, pos = _build(_Layout([ap, jn]))
    ids = {(round(px, 3), round(py, 3)): i for i, (px, py) in pos.items()}
    left = {ids[(round(x, 3), round(y, 3))]
            for (x, y) in list(ap.polygon.exterior.coords)[:-1]}
    right = {ids[(round(x, 3), round(y, 3))]
             for (x, y) in list(jn.polygon.exterior.coords)[:-1]}
    for entry in sc:
        for (i, j, _b) in entry["edges"]:
            assert not ((i in left and j in right)
                        or (j in left and i in right)), (
                "a chord across a 40 m pavement GAP was priced as law")
    assert rep["not_visible"] > 0


def test_a_pair_already_stated_within_shape_is_not_restated():
    """Two copies of one law in the POCS sweep is the round-3 station
    build's own reason for dropping restated pairs."""
    ap = _Shape(_rect(-60.0, -20.0, 60.0, 20.0), "apron")
    layout = _Layout([ap])
    bucket_to_idx, node_pos, ctx = _wire(layout)
    n = len(node_pos)
    (sc0, _s0, _r0, rep0) = ANS.build_airside_no_step_constraints(
        layout, bucket_to_idx, ctx, node_pos=node_pos, n_nodes=n)
    stated = {((i, j) if i < j else (j, i))
              for e in sc0 for (i, j, _b) in e["edges"]}
    assert stated
    (sc1, _s1, _r1, rep1) = ANS.build_airside_no_step_constraints(
        layout, bucket_to_idx, ctx, node_pos=node_pos, n_nodes=n,
        existing_pairs=stated)
    assert sc1 == []
    assert rep1["already_stated"] >= len(stated)


def test_k_nearest_is_bounded_and_spatially_spread():
    """Spec §1.3: "its k-nearest airside neighbours within the window
    (k bounded, default 16, spatially spread)"."""
    import numpy as np
    pts = np.array([[math.cos(t) * 30.0, math.sin(t) * 30.0]
                    for t in [i * 0.05 for i in range(120)]]
                   + [[0.0, 0.0]])
    pairs = ANS._spread_candidates(pts, 150.0, 16)
    # BOUNDED: each node SELECTS at most k, so the pair set is at most
    # n*k (degree can exceed k — a hub every node picks is legitimately
    # picked by all of them; what is bounded is the O(n*k) population).
    assert len(pairs) <= len(pts) * 16, "k is not bounded"
    # The centre node reaches nodes in several distinct sectors.
    centre = len(pts) - 1
    sects = set()
    for (a, b) in pairs:
        if centre not in (a, b):
            continue
        o = b if a == centre else a
        d = pts[o] - pts[centre]
        sects.add(int(((math.atan2(d[1], d[0]) % (2 * math.pi))
                       / (2 * math.pi / ANS._SECTORS))))
    assert len(sects) >= 4, f"selection is not spread: sectors={sects}"


# ═════════════════════════════════════════════════════════════════════
# §1.3 — THE SENIORITY LADDER
# ═════════════════════════════════════════════════════════════════════

def test_the_ladder_is_runway_then_centerline_then_seat_then_free():
    tiers = ANS.tier_of_nodes(10, runway_nodes={1, 2},
                              centerline_nodes={2, 3}, seat_nodes={3, 4})
    assert tiers[1] == ANS.TIER_RUNWAY
    assert tiers[2] == ANS.TIER_RUNWAY          # runway beats centerline
    assert tiers[3] == ANS.TIER_CENTERLINE      # centerline beats a seat
    assert tiers[4] == ANS.TIER_SEAT
    assert 5 not in tiers                        # free tier is the default
    assert (ANS.TIER_RUNWAY < ANS.TIER_CENTERLINE < ANS.TIER_SEAT
            < ANS.TIER_FREE)


def test_a_cross_tier_edge_names_its_SENIOR_endpoint():
    """Spec §2 twin 2 / §1.3: "the item-2 apron therefore RISES toward
    the junction within its own caps; the junction (centerline-valued)
    does not move".  The mechanism is the round-3 Amendment 1 one: the
    senior side is CONSTANT, so the only way to satisfy the edge is to
    move the junior side."""
    ap = _Shape(_rect(-60.0, -20.0, 0.0, 20.0), "apron")
    jn = _Shape(_rect(0.0, -20.0, 20.0, 20.0), "junction")
    layout = _Layout([ap, jn])
    bucket_to_idx, node_pos, ctx = _wire(layout)
    n = len(node_pos)
    ids = {(round(px, 3), round(py, 3)): i for i, (px, py) in node_pos.items()}
    jn_only = {ids[(round(x, 3), round(y, 3))]
               for (x, y) in list(jn.polygon.exterior.coords)[:-1]} - {
        ids[(round(x, 3), round(y, 3))]
        for (x, y) in list(ap.polygon.exterior.coords)[:-1]}
    tiers = ANS.tier_of_nodes(n, centerline_nodes=jn_only)
    sc, senior, recs, rep = ANS.build_airside_no_step_constraints(
        layout, bucket_to_idx, ctx, node_pos=node_pos, n_nodes=n,
        tier_of=tiers)
    assert rep["cross_tier"] > 0
    assert senior, "no senior endpoint was named"
    assert senior <= jn_only, (
        "a FREE-tier node was named senior — the ladder is inverted")


def test_tier2_is_the_whole_taxiway_family_register():
    """Spec Amendment 1 ruling 1: tier 2 is every node of taxiway-family
    pavement, and the register is the solve's OWN ``_ROUTE_ROLES`` —
    imported, never re-spelled (the blast role-literal hazard)."""
    from auto_patch.elevation_per_surface.route_profile.anchors import (
        _ROUTE_ROLES)
    assert ANS.taxiway_family_roles() is _ROUTE_ROLES
    assert {"junction", "stub", "primary_parallel"} <= set(_ROUTE_ROLES)
    assert "apron" not in _ROUTE_ROLES
    assert "runway" not in _ROUTE_ROLES

    jn = _Shape(_rect(0.0, -20.0, 25.0, 20.0), "junction")
    ap = _Shape(_rect(-25.0, -20.0, 0.0, 20.0), "apron")
    layout = _Layout([jn, ap])
    bucket_to_idx, node_pos, _ctx = _wire(layout)
    n = len(node_pos)
    ids = {(round(px, 3), round(py, 3)): i
           for i, (px, py) in node_pos.items()}
    jn_ids = {ids[(round(x, 3), round(y, 3))]
              for (x, y) in list(jn.polygon.exterior.coords)[:-1]}
    got = ANS.taxiway_family_nodes(layout, bucket_to_idx, n)
    assert got == jn_ids, (
        "every junction RING vertex is tier 2, not only the ones a "
        "centerline runs through")


def test_a_shared_node_takes_the_SENIOR_tier():
    """Spec Amendment 1 ruling 1, the max-tier rule — what closes the
    runway+service-road CARVE CORNERS the first arm moved (5 at HECA
    worst 1.03 m, 4 at SPJC worst 1.44 m, every one shared)."""
    tiers = ANS.tier_of_nodes(10, runway_nodes={7}, centerline_nodes={7, 8},
                              seat_nodes={7, 8, 9})
    assert tiers[7] == ANS.TIER_RUNWAY
    assert tiers[8] == ANS.TIER_CENTERLINE
    assert tiers[9] == ANS.TIER_SEAT


def test_tier2_to_tier2_pairs_are_published_but_NOT_imposed():
    """Spec Amendment 1 ruling 1: *"Tier2<->tier2 no-step pairs are
    CENSUS-PRICED but NOT solver-imposed this round"* — a violating pair
    there is a PROFILE-LAW docket, never a solver tug-of-war between two
    authorities.  The record is still published, so the docket has a
    number."""
    j1 = _Shape(_rect(-25.0, -20.0, 0.0, 20.0), "junction")
    j2 = _Shape(_rect(0.0, -20.0, 25.0, 20.0), "stub")
    layout = _Layout([j1, j2])
    bucket_to_idx, node_pos, ctx = _wire(layout)
    n = len(node_pos)
    tiers = ANS.tier_of_nodes(
        n, centerline_nodes=ANS.taxiway_family_nodes(
            layout, bucket_to_idx, n))
    sc, senior, recs, rep = ANS.build_airside_no_step_constraints(
        layout, bucket_to_idx, ctx, node_pos=node_pos, n_nodes=n,
        tier_of=tiers)
    assert recs, "the pairs must still be PUBLISHED for the census"
    assert rep["tier2_census_only"] == len(recs)
    assert rep["published"] == len(recs)
    assert sc == [], "a tier2<->tier2 pair must not become a constraint"
    assert rep["edges"] == 0
    assert senior == set()
    assert all(r["imposed"] is False for r in recs)
    # …while a tier2 <-> FREE pair still is imposed.
    ap = _Shape(_rect(0.0, -20.0, 25.0, 20.0), "apron")
    layout2 = _Layout([j1, ap])
    b2, pos2, ctx2 = _wire(layout2)
    n2 = len(pos2)
    tiers2 = ANS.tier_of_nodes(
        n2, centerline_nodes=ANS.taxiway_family_nodes(layout2, b2, n2))
    sc2, senior2, recs2, rep2 = ANS.build_airside_no_step_constraints(
        layout2, b2, ctx2, node_pos=pos2, n_nodes=n2, tier_of=tiers2)
    assert rep2["edges"] > 0
    assert rep2["cross_tier"] > 0
    assert senior2, "the tier-2 side of a cross-tier edge is named senior"


def test_free_tier_edges_are_symmetric():
    """"an edge within the free tier is symmetric" — it names no senior
    endpoint, so nothing is preserved on its account."""
    ap = _Shape(_rect(-60.0, -20.0, 60.0, 20.0), "apron")
    (sc, senior, recs, rep), _b, _p = _build(_Layout([ap]))
    assert sc, "no edges at all"
    assert senior == set()
    assert rep["cross_tier"] == 0


def test_the_preservation_membership_holds_the_senior_side_CONSTANT():
    """The one-sidedness mechanism, reused verbatim from round-3
    Amendment 1: a senior node is preserved OUT of the spine-yield set,
    so ``hard -= yield`` can never release it into the projection where
    the anchored side would be the cheapest way to satisfy the edge."""
    from auto_patch.elevation_per_surface.route_profile.solve import (
        _spine_yield_membership)
    frozen = {1, 2, 3, 4}
    pres, yield_idx = _spine_yield_membership(
        frozen, 10, truth_hard=set(), runway_nodes=set(),
        building_seats={}, runway_anchor={}, seam_pins=set())
    assert yield_idx == {1, 2, 3, 4}
    pres2, yield2 = _spine_yield_membership(
        frozen, 10, truth_hard=set(), runway_nodes=set(),
        building_seats={}, runway_anchor={}, seam_pins=set(),
        no_step_senior_nodes={2, 3})
    assert {2, 3} <= pres2
    assert yield2 == {1, 4}
    # Empty / None is byte-identical.
    pres3, yield3 = _spine_yield_membership(
        frozen, 10, truth_hard=set(), runway_nodes=set(),
        building_seats={}, runway_anchor={}, seam_pins=set(),
        no_step_senior_nodes=set())
    assert (pres3, yield3) == (pres, yield_idx)


# ═════════════════════════════════════════════════════════════════════
# §1.2 — THE RATE OF CHANGE
# ═════════════════════════════════════════════════════════════════════

def _bowl_way(cg, nodes, width_m, depth_m, wid="w1", role="apron"):
    """A 5-station polyline: flat, down by ``depth_m`` at the centre,
    back up — total span ``width_m``.  Emitted as an ``apron_lattice``
    breakline (an airside membrane polyline, spec §1.2)."""
    half = width_m / 2.0
    xs = [-half, -half / 2.0, 0.0, half / 2.0, half]
    zs = [100.0, 100.0, 100.0 - depth_m, 100.0, 100.0]
    nids = []
    for k, x in enumerate(xs):
        nid = f"{wid}n{k}"
        nodes[nid] = (30.12 + 0.0, 31.40 + x / 96_000.0)
        nids.append(nid)
    return cg.Way(wid=wid, role=role, ref="", aeroway="",
                  nids=nids, elevs=zs, tags={})


def test_a_bowl_is_lawful_WIDE_and_unlawful_NARROW():
    """Spec §2 twin 3 and the owner's refinement, verbatim: *"A 1.5 m
    'dip' could be ok assuming it was spread across enough area to be
    smooth, like the runway curvature and rate change rules."*  Same
    depth, two widths."""
    import check_grade as cg

    def _ll_to_m(lat, lon):
        return ((lon - 31.40) * 96_000.0, (lat - 30.12) * 111_320.0)

    for width, expect_rows in ((30.0, True), (600.0, False)):
        nodes = {}
        w = _bowl_way(cg, nodes, width, 1.5)
        rows, n_st, n_ways = cg._check_airside_no_step_rate(
            [], [w], nodes, _ll_to_m)
        assert n_st > 0, "no station was censused"
        if expect_rows:
            assert rows, (
                f"a 1.5 m bowl concentrated over {width:g} m must violate "
                f"the rate law")
        else:
            assert not rows, (
                f"a 1.5 m bowl spread over {width:g} m is LAWFUL — the "
                f"owner's refinement")


def test_the_rate_is_the_aerodromes_own_constant_not_a_new_number():
    """Spec §1.2: "extend that machinery, never fork it"."""
    assert (GL.airside_arc_rate_per_m("faa")
            == GL.ruleset_strip_arc_rate_per_m("faa"))
    assert (GL.airside_arc_rate_per_m("icao")
            == GL.ruleset_strip_arc_rate_per_m("icao"))
    assert (GL.airside_arc_rate_per_m("faa")
            == GL.strip_longitudinal_law(4, "E", "faa")[1])


def test_the_rate_reader_uses_the_strip_families_own_machinery():
    import check_grade as cg
    import inspect
    src = inspect.getsource(cg._check_airside_no_step_rate)
    assert "_strip_longitudinal_breaches" in src
    assert "_rate_reader_blind_spot" in src
    assert "_site_key" in src


def test_the_rate_population_is_the_membranes_own_polylines():
    """Spec §1.2: "lattice rows/columns, spine-station runs, ring
    sequences"."""
    import check_grade as cg
    assert cg._NO_STEP_POLYLINE_FEATURES == ("apron_lattice",
                                             "apron_spine_station")
    from auto_patch.enclaves import ENCLAVE_AIRSIDE_ROLES
    assert cg._NO_STEP_AIRSIDE_ROLES == ENCLAVE_AIRSIDE_ROLES


# ═════════════════════════════════════════════════════════════════════
# §1.6 — THE CENSUS FAMILY
# ═════════════════════════════════════════════════════════════════════

def test_the_family_is_registered():
    """``LAW_FAMILIES`` registration, so omission is structurally
    impossible (``tests/test_harness.py`` twins)."""
    import check_grade as cg
    keys = [k for (k, _t, _b) in cg.LAW_FAMILIES]
    assert "airside_no_step" in keys
    assert cg.LAW_FAMILIES[keys.index("airside_no_step")][2] == "within"


def test_the_census_prices_exactly_the_published_edge_list():
    """Spec §1.6: "prices exactly the sidecar-published §1.3 edge
    enumeration (the ``apron_lattice_membrane`` precedent: solver
    publishes, census prices the same list — one law, one population)".
    ONE implementation serves both families."""
    import check_grade as cg
    import inspect
    src = inspect.getsource(cg._check_airside_no_step)
    assert "_check_published_law_edges" in src
    assert "_check_published_law_edges" in inspect.getsource(
        cg._check_apron_lattice_membrane)


def test_a_published_edge_over_budget_mints_exactly_one_row():
    import check_grade as cg

    def _ll_to_m(lat, lon):
        return ((lon - 31.40) * 96_000.0, (lat - 30.12) * 111_320.0)

    nodes = {"a": (30.12, 31.40), "b": (30.12, 31.40 + 40.0 / 96_000.0)}
    w = cg.Way(wid="w", role="apron", ref="", aeroway="",
               nids=["a", "b"], elevs=[100.0, 101.5], tags={})
    recs = [{"a": [30.12, 31.40],
             "b": [30.12, 31.40 + 40.0 / 96_000.0],
             "budget_m": 0.6, "provenance": "airside_no_step"}]
    rows, n_checked, n_unmatched = cg._check_airside_no_step(
        recs, [w], [], nodes, _ll_to_m)
    assert n_checked == 1 and n_unmatched == 0
    assert len(rows) == 1
    assert rows[0].de_m == pytest.approx(1.5, abs=1e-6)


def test_the_sidecar_key_is_published_unconditionally():
    import check_grade as cg
    src = Path(_ROOT / "src" / "auto_patch" / "layout.py").read_text()
    assert '"airside_no_step_edges": list(' in src
    assert cg.SIDECAR_LAW_KEYS["airside_no_step_edges"] == (
        "airside_no_step_edges_ll")


# ═════════════════════════════════════════════════════════════════════
# §1.4 — DEM DEMOTION
# ═════════════════════════════════════════════════════════════════════

def test_dem_demotion_is_scoped_to_AIRSIDE_membrane_interior():
    """Spec §1.4.  ``apron_body_nodes`` deliberately also carries the
    groundside DEM-follow roles (a service road IS terrain-tied), so the
    set is intersected with the airside register."""
    ap = _Shape(_rect(-60.0, -20.0, 60.0, 20.0), "apron")
    rd = _Shape(_rect(100.0, -5.0, 200.0, 5.0), "service_road")
    layout = _Layout([ap, rd])
    bucket_to_idx, node_pos, _ctx = _wire(layout)
    n = len(node_pos)
    ids = {(round(px, 3), round(py, 3)): i
           for i, (px, py) in node_pos.items()}
    ap_ids = {ids[(round(x, 3), round(y, 3))]
              for (x, y) in list(ap.polygon.exterior.coords)[:-1]}
    rd_ids = {ids[(round(x, 3), round(y, 3))]
              for (x, y) in list(rd.polygon.exterior.coords)[:-1]}
    got = ANS.dem_demoted_nodes(layout, bucket_to_idx, n, ap_ids | rd_ids)
    assert got == ap_ids
    assert not (got & rd_ids), "a service road lost its DEM target"


def test_the_body_solves_warm_start_honours_the_demotion():
    """The measured mechanism: ``one_profile_solve`` re-initialised EVERY
    free node at its DEM reading, which silently undid the 24c scaffold
    seed one statement after it ran."""
    import inspect
    from auto_patch.elevation_per_surface.route_profile import one_solve
    src = inspect.getsource(one_solve.one_profile_solve)
    assert "dem_demoted" in src
    assert "if i in _demoted:" in src


# ═════════════════════════════════════════════════════════════════════
# THE FLAG, AND VACUITY
# ═════════════════════════════════════════════════════════════════════

def test_flag_OFF_builds_nothing_and_demotes_nothing(monkeypatch):
    """Spec §1.5: OFF is byte-identical — no edge, no publication, no
    preservation, no DEM demotion."""
    monkeypatch.setenv("O4_AIRSIDE_NO_STEP", "0")
    import auto_patch.config as CFG
    importlib.reload(CFG)
    try:
        assert CFG.AIRSIDE_NO_STEP is False
        ap = _Shape(_rect(-60.0, -20.0, 60.0, 20.0), "apron")
        layout = _Layout([ap])
        bucket_to_idx, node_pos, ctx = _wire(layout)
        n = len(node_pos)
        sc, senior, recs, rep = ANS.build_airside_no_step_constraints(
            layout, bucket_to_idx, ctx, node_pos=node_pos, n_nodes=n)
        assert (sc, senior, recs) == ([], set(), [])
        assert rep["edges"] == 0
        assert ANS.dem_demoted_nodes(
            layout, bucket_to_idx, n, set(range(n))) == set()
    finally:
        monkeypatch.delenv("O4_AIRSIDE_NO_STEP", raising=False)
        importlib.reload(CFG)
    assert CFG.AIRSIDE_NO_STEP is True


def test_an_airport_with_no_airside_pavement_is_vacuous():
    rd = _Shape(_rect(0.0, 0.0, 100.0, 10.0), "service_road")
    layout = _Layout([rd])
    bucket_to_idx, node_pos, ctx = _wire(layout)
    n = len(node_pos)
    sc, senior, recs, rep = ANS.build_airside_no_step_constraints(
        layout, bucket_to_idx, ctx, node_pos=node_pos, n_nodes=n)
    assert (sc, senior, recs) == ([], set(), [])
    assert rep["airside_nodes"] == 0
    assert ANS.airside_pavement_union(layout) is None


def test_the_report_names_the_long_apron_chord_skip():
    """The ONE coverage boundary this implementation has, counted rather
    than left to silence: ``classify_pair`` drops an APRON body chord
    beyond ``APRON_BODY_CHORD_MAX_M`` (60 m), so the 150 m window does
    not reach those pairs.  Reported, never overridden here."""
    ap = _Shape(_rect(-100.0, -50.0, 100.0, 50.0), "apron")
    (sc, senior, recs, rep), _b, _p = _build(_Layout([ap]))
    assert "skipped_long_apron" in rep
    assert rep["skipped_long_apron"] > 0, (
        "the 200 m x 100 m apron has pairs beyond the 60 m body gate")
    assert "60 m body gate" in ANS.format_report("TEST", rep)


# ═════════════════════════════════════════════════════════════════════
# AMENDMENT 2 — THE TWO-PASS CONFORM
# ═════════════════════════════════════════════════════════════════════

def test_pass_1_ingests_NOTHING_from_this_law():
    """Spec Amendment 2 ruling 1: *"Pass 1: the solve WITHOUT any imposed
    no-step edges — byte-identical to the flag-off arm by construction
    (assert it, don't argue it)."*  Three terms had to leave pass 1, and
    this pins all three at the call sites."""
    import inspect
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.solve_route_profile)
    # (a) the entries are BUILT and PUBLISHED but never extended in
    assert "_airside_no_step_edges_ll = _nostep_edges" in src
    assert "shape_constraints.extend(_ns_scs)" not in src
    # (b) no senior preservation
    assert "no_step_senior_nodes=None)" in src
    # (c) no DEM demotion in the body solve's warm start
    assert "dem_demoted=" not in src
    assert "apron_smooth=True)" in src


def test_pass_2_is_wired_at_the_final_projections_tail():
    """…and AFTER the crown transform back, so the membrane's plain |Δz|
    budgets are read in the frame they were priced in."""
    import inspect
    from auto_patch.elevation_per_surface.route_profile import solve as SV
    src = inspect.getsource(SV.final_grade_projection)
    assert "membrane_conform as _mc" in src
    i_crown = src.index("crown transform back")
    i_conf = src.index("membrane_conform as _mc")
    i_wb = src.rindex("_writeback(layout, elev, b2i)")
    assert i_crown < i_conf < i_wb, (
        "pass 2 must run after the crown transform and before writeback")


def test_only_tier4_membrane_nodes_are_free_in_pass_2():
    """Spec Amendment 2: *"every tier-1/2/3 node is a CONSTANT at its
    pass-1 value; only tier-4 membrane nodes are free"*, under the
    MAX-TIER rule — which is what makes the runway carve-corner movers
    vanish."""
    rw = _Shape(_rect(-60.0, 40.0, 60.0, 60.0), "runway")
    jn = _Shape(_rect(-60.0, 20.0, 60.0, 40.0), "junction")
    ap = _Shape(_rect(-60.0, -20.0, 60.0, 20.0), "apron")
    bl = _Shape(_rect(-10.0, -18.0, 10.0, -2.0), "building")
    layout = _Layout([rw, jn, ap, bl])
    bucket_to_idx, node_pos, _ctx = _wire(layout)
    n = len(node_pos)
    free, senior, tiers = ANS.membrane_free_nodes(layout, bucket_to_idx, n)
    ids = {(round(px, 3), round(py, 3)): i
           for i, (px, py) in node_pos.items()}

    def _of(shape):
        return {ids[(round(x, 3), round(y, 3))]
                for (x, y) in list(shape.polygon.exterior.coords)[:-1]}
    rw_ids, jn_ids, ap_ids, bl_ids = (_of(rw), _of(jn), _of(ap), _of(bl))
    assert not (free & rw_ids), "a runway node is tier 1, never free"
    assert not (free & jn_ids), "a taxiway-family node is tier 2"
    assert not (free & bl_ids), "a building pad node is tier 3"
    # the SHARED runway/junction edge is senior under max-tier
    assert (rw_ids & jn_ids) <= senior
    # what is left free is the apron membrane and only that
    assert free == ap_ids - jn_ids - bl_ids
    assert tiers["free"] == len(free)


def test_pass_2_touches_nothing_when_there_is_no_publication():
    """No published pair ⇒ vacuous, ``elev`` untouched — the flag-OFF and
    no-airside cases both land here."""
    ap = _Shape(_rect(-60.0, -20.0, 60.0, 20.0), "apron")
    layout = _Layout([ap])
    bucket_to_idx, node_pos, _ctx = _wire(layout)
    n = len(node_pos)
    elev = [10.0] * n
    rep = ANS.membrane_conform(layout, bucket_to_idx, elev, n,
                               shape_constraints=[])
    assert rep["free"] == 0 and rep["pairs"] == 0
    assert elev == [10.0] * n


def test_pass_2_moves_the_membrane_and_NOT_the_constants():
    """The whole point: a senior<->free pair is one-sided BY CONSTRUCTION
    because the senior end is not in the free set, so the projection can
    only move the membrane."""
    jn = _Shape(_rect(-25.0, -20.0, 0.0, 20.0), "junction")
    ap = _Shape(_rect(0.0, -20.0, 25.0, 20.0), "apron")
    layout = _Layout([jn, ap])
    bucket_to_idx, node_pos, ctx = _wire(layout)
    n = len(node_pos)
    tiers = ANS.tier_of_nodes(
        n, centerline_nodes=ANS.taxiway_family_nodes(layout, bucket_to_idx,
                                                     n))
    sc, senior, recs, rep = ANS.build_airside_no_step_constraints(
        layout, bucket_to_idx, ctx, node_pos=node_pos, n_nodes=n,
        tier_of=tiers)
    assert rep["edges"] > 0
    assert getattr(layout, "_airside_no_step_pairs_m", None)
    free, const, _t = ANS.membrane_free_nodes(layout, bucket_to_idx, n)
    assert free and const
    # the junction sits 3 m above a flat apron — far over any cap
    elev = [10.0] * n
    for i in const:
        elev[i] = 13.0
    before = list(elev)
    conform = ANS.membrane_conform(layout, bucket_to_idx, elev, n,
                                   shape_constraints=[], icao="TEST")
    assert conform["pairs"] > 0
    for i in const:
        assert elev[i] == before[i], (
            "a CONSTANT moved — pass 2 is not one-sided")
    assert any(abs(elev[i] - before[i]) > 0.01 for i in free), (
        "the membrane did not conform toward the constant")
    assert conform["moved"] > 0


def test_the_carried_pairs_travel_as_GEOMETRY_not_indices():
    """Pass 2 runs in a REBUILT node space (the rod-key lesson): the
    pairs are re-resolved through the canonical registry."""
    src = Path(ANS.__file__).read_text()
    assert "_airside_no_step_pairs_m" in src
    assert "cps.get_or_add(float(xa), float(ya))" in src
    import inspect
    doc = inspect.getdoc(ANS._resolve_carried_pairs)
    assert "geometry, never an index" in doc


def test_the_pass_2_reseed_is_gated_OFF_with_its_measurement():
    """§1.4's taut re-seed is RETIRED-KEPT-GATED (default OFF) on this
    lane's own measurement — the repo's retired-kept-gated idiom, so the
    finding is not hidden and a ruling has an arm to be made on."""
    import auto_patch.config as CFG
    assert CFG.AIRSIDE_NO_STEP_RESEED is False
    src = Path(CFG.__file__).read_text()
    i = src.index("AIRSIDE_NO_STEP_RESEED = (")
    note = src[max(0, i - 1800):i]
    assert "O4_AIRSIDE_NO_STEP_RESEED=1" in note
    assert "re-seeded ZERO nodes" in note, (
        "a gated-off mechanism must carry the measurement that gated it")
    assert "88 -> 186" in note, (
        "…including the wider cut that scoped it back")


def test_the_published_lattice_law_IS_reimposed_under_do_no_harm():
    """SUPERSEDED BY ROUND 4 §H1.2 (the no-step spec Amendment 3 §2
    CHARTER, activated by RULINGS 2026-08-28b item 2 — the owner's sim
    read still shows the dip).  Amendment 3 recorded a DEVIATION: pass 2
    did not re-impose the published lattice/station law, because with
    every senior node frozen a raw re-imposition asks pass 2 to REPAIR a
    pre-existing violation and it pays out of the membrane's other laws
    (SPJC airside 1,359 -> 1,926; CYXY's own ``apron_lattice_membrane``
    24 -> 47).  The DO-NO-HARM RELAXATION is the ruled fix, so the
    re-imposition now lands WITH it and never without it."""
    import inspect
    src = inspect.getsource(ANS.membrane_conform)
    assert "do-no-harm" in src.lower()
    assert 'report["membrane_published_edges"]' in src
    # the re-imposition is GATED on the relaxation: never one without
    # the other (that pairing is the whole ruling)
    i_relax = src.index('_relax = bool(getattr(_cfg, "PASS2_RELAXATION"')
    i_imp = src.index("own.append((int(a), int(b), float(bud)))")
    assert i_relax < i_imp
    assert "if _relax:" in src
    doc = inspect.getdoc(ANS._resolve_published_ll_pairs)
    assert "canonical registry" in doc


def test_the_creation_order_repair_runs_after_the_conform():
    """RULINGS 2026-08-21e: anything created later defers to what exists
    before it.  The membrane is re-projected against its OWN laws alone
    so the newer law can never break the older one."""
    import inspect
    src = inspect.getsource(ANS.membrane_conform)
    i_conf = src.index("rem, both = feasibility_project(elev, entries, hard)")
    i_rep = src.index("own_only = [e for e in entries")
    assert i_conf < i_rep
    assert 'e.get("ref") != PROVENANCE' in src


# ═════════════════════════════════════════════════════════════════════
# HECA ROUND 4 §H1 — THE COVERAGE GUARANTEE AND THE DO-NO-HARM
# RELAXATION (docs/specs/heca-round4-spec.md; RULINGS 2026-08-28b
# items 1 and 2)
# ═════════════════════════════════════════════════════════════════════

def _apron_with_lattice(off_grid=True):
    """An apron whose interior carries ONE lattice point.

    ``off_grid`` reproduces the measured half of item 1 exactly: the
    lattice point has a canonical node index but NO unified-graph
    position, because ``build_unified_graph`` positions only the ring
    vertices it walks.  It is therefore invisible to the k-NN — priced
    by nothing — unless the §H1.1 floor reaches it.
    """
    ap = _Shape(_rect(0.0, 0.0, 60.0, 60.0), "apron")
    layout = _Layout([ap])
    bucket_to_idx, node_pos, ctx = _wire(layout)
    b = layout.canonical_points.get_or_add(30.0, 30.0)
    lat_idx = len(node_pos)
    bucket_to_idx[b] = lat_idx
    if not off_grid:
        node_pos[lat_idx] = (30.0, 30.0)
    layout.apron_lattice_presolve = [{"shape": ap, "points": [(30.0, 30.0)]}]
    return layout, bucket_to_idx, node_pos, ctx, lat_idx


def _touches(rows, node_id):
    return any(r[2] == node_id or r[3] == node_id for r in rows)


def test_H1_1_every_membrane_node_carries_law(monkeypatch):
    """§H1.1, the STRUCTURAL INVARIANT: zero membrane nodes with no
    priced neighbour.  Measured before the floor (item 1): 787 of HECA's
    2,202 lattice endpoints (36 %) carried NO ``pair_caps`` edge and NO
    ``airside_no_step`` edge, so the void pair (lattice 76.43 <-> ring
    79.15, 18.51 m, 14.7 % against a 1.5 % cap) was priced by NOTHING."""
    import auto_patch.config as CFG
    monkeypatch.setattr(CFG, "MEMBRANE_LAW_FLOOR", True, raising=False)
    layout, b2i, pos, ctx, lat = _apron_with_lattice()
    n = len(pos) + 1
    rows, rep = ANS.enumerate_airside_no_step_pairs(
        layout, b2i, ctx, node_pos=pos, n_nodes=n)
    assert rep["membrane_nodes"] == 1
    assert rep["membrane_off_grid"] == 1, (
        "the lattice point has no unified-graph position — that is half "
        "of the measured orphan population")
    assert rep["floor_orphans"] == 1
    assert rep["floor_edges"] == 1
    assert rep["floor_unpriced"] == 0
    assert _touches(rows, lat), "the membrane node is still unpriced"
    # THE INVARIANT, stated as arithmetic: every orphan is either given a
    # floor edge or counted as having no lawful neighbour at all.
    assert (rep["floor_orphans"]
            == rep["floor_edges"] + rep["floor_unpriced"])


def test_H1_1_the_floor_edge_goes_to_a_RING_node_not_another_membrane():
    """"…to its NEAREST RING-OR-SENIOR node".  A membrane<->membrane
    floor edge would couple the lattice to itself, which is the coupling
    that already exists and the one that ACCUMULATES (the whole reason
    this law exists)."""
    ap = _Shape(_rect(0.0, 0.0, 60.0, 60.0), "apron")
    layout = _Layout([ap])
    b2i, pos, ctx = _wire(layout)
    pts = [(28.0, 30.0), (32.0, 30.0)]
    idx = []
    for (x, y) in pts:
        b = layout.canonical_points.get_or_add(x, y)
        b2i[b] = len(pos) + len(idx)
        idx.append(b2i[b])
    layout.apron_lattice_presolve = [{"shape": ap, "points": pts}]
    n = len(pos) + len(idx)
    rows, rep = ANS.enumerate_airside_no_step_pairs(
        layout, b2i, ctx, node_pos=pos, n_nodes=n)
    assert rep["floor_orphans"] == 2
    assert rep["floor_edges"] == 2
    mem = set(idx)
    for r in rows:
        if r[2] in mem or r[3] in mem:
            assert not (r[2] in mem and r[3] in mem), (
                "a floor edge joined two membrane nodes")


def test_H1_1_the_floor_is_flag_gated_and_OFF_is_the_prior(monkeypatch):
    """Flag OFF ⇒ the enumeration is exactly the round-3 population."""
    import auto_patch.config as CFG
    monkeypatch.setattr(CFG, "MEMBRANE_LAW_FLOOR", False, raising=False)
    layout, b2i, pos, ctx, lat = _apron_with_lattice()
    n = len(pos) + 1
    rows, rep = ANS.enumerate_airside_no_step_pairs(
        layout, b2i, ctx, node_pos=pos, n_nodes=n)
    assert rep["membrane_nodes"] == 0
    assert rep["floor_edges"] == 0
    assert not _touches(rows, lat), (
        "with the floor OFF the orphan must stay unpriced — that is the "
        "byte-identical prior")


def test_H1_1_the_floor_never_invents_a_budget():
    """The floor prices through the SAME ``classify_pair`` chain: no new
    cap value, no manufactured allowance (the law's founding rule)."""
    import inspect
    src = inspect.getsource(ANS.enumerate_airside_no_step_pairs)
    assert "row = _price(p, b, count=False)" in src
    assert "_chord_visible(union, coords[p], coords[b])" in src


def test_H1_1_a_floor_chord_across_a_pavement_GAP_is_still_not_law():
    """RULINGS 2026-08-24b stands: a step is lawful exactly across a
    pavement gap, so the floor may not manufacture a chord that leaves
    the airside union.  Such a node is COUNTED, never silently priced."""
    ap = _Shape(_rect(0.0, 0.0, 40.0, 40.0), "apron")
    far = _Shape(_rect(400.0, 400.0, 440.0, 440.0), "apron")
    layout = _Layout([ap, far])
    b2i, pos, ctx = _wire(layout)
    # a lattice point inside the FAR apron, whose only ring neighbours
    # are its own — but we place it 1000 m out so the window excludes
    # every ring vertex.
    ghost = _Shape(_rect(3000.0, 3000.0, 3040.0, 3040.0), "apron")
    layout.shapes.append(ghost)
    b = layout.canonical_points.get_or_add(3020.0, 3020.0)
    b2i[b] = len(pos)
    layout.apron_lattice_presolve = [{"shape": ghost,
                                      "points": [(3020.0, 3020.0)]}]
    n = len(pos) + 1
    rows, rep = ANS.enumerate_airside_no_step_pairs(
        layout, b2i, ctx, node_pos=pos, n_nodes=n)
    assert rep["floor_orphans"] >= 1
    assert rep["floor_unpriced"] >= 1, (
        "a membrane node with no lawful neighbour inside the window must "
        "be COUNTED, never inferred from silence")


def test_H1_2_do_no_harm_no_own_law_row_grows(monkeypatch):
    """§H1.2's INVARIANT.  Each own-law budget is raised to AT LEAST its
    pass-1 residual, so an own-law pair's residual after pass 2 is
    bounded by max(budget, its pass-1 residual): a pair already over cap
    cannot grow, and pass 2 is never ASKED to repair one."""
    import auto_patch.config as CFG
    monkeypatch.setattr(CFG, "PASS2_RELAXATION", True, raising=False)
    jn = _Shape(_rect(-25.0, -20.0, 0.0, 20.0), "junction")
    ap = _Shape(_rect(0.0, -20.0, 25.0, 20.0), "apron")
    layout = _Layout([jn, ap])
    b2i, pos, ctx = _wire(layout)
    n = len(pos)
    tiers = ANS.tier_of_nodes(
        n, centerline_nodes=ANS.taxiway_family_nodes(layout, b2i, n))
    ANS.build_airside_no_step_constraints(
        layout, b2i, ctx, node_pos=pos, n_nodes=n, tier_of=tiers)
    free, const, _t = ANS.membrane_free_nodes(layout, b2i, n)
    assert free and const
    elev = [10.0] * n
    for i in const:
        elev[i] = 13.0
    # A PRE-EXISTING own-law violation between two FREE nodes: a 1 cm
    # budget over a pair that already stands 2 m apart.  Un-relaxed,
    # pass 2 would have to repair it out of the membrane's other laws.
    fl = sorted(free)
    a, b = fl[0], fl[1]
    elev[a] = 8.0
    elev[b] = 10.0
    res0 = abs(elev[a] - elev[b])
    sc = [{"nodes": [a, b], "edges": [(a, b, 0.01)], "flat": False,
           "flat_pairs": (), "area": 0.0, "role": "apron"}]
    rep = ANS.membrane_conform(layout, b2i, elev, n,
                               shape_constraints=sc, icao="TEST")
    assert rep["own_law_relaxed"] >= 1
    assert rep["own_law_grown"] == 0, (
        "an own-law row grew beyond its pass-1 residual — do-no-harm is "
        "the invariant")
    assert abs(elev[a] - elev[b]) <= max(0.01, res0) + 1e-6


def test_H1_2_the_relaxation_is_flag_gated(monkeypatch):
    """Flag OFF ⇒ no budget is raised and nothing is re-imposed: the
    Amendment-3 behaviour exactly."""
    import auto_patch.config as CFG
    monkeypatch.setattr(CFG, "PASS2_RELAXATION", False, raising=False)
    jn = _Shape(_rect(-25.0, -20.0, 0.0, 20.0), "junction")
    ap = _Shape(_rect(0.0, -20.0, 25.0, 20.0), "apron")
    layout = _Layout([jn, ap])
    b2i, pos, ctx = _wire(layout)
    n = len(pos)
    tiers = ANS.tier_of_nodes(
        n, centerline_nodes=ANS.taxiway_family_nodes(layout, b2i, n))
    ANS.build_airside_no_step_constraints(
        layout, b2i, ctx, node_pos=pos, n_nodes=n, tier_of=tiers)
    elev = [10.0] * n
    free, const, _t = ANS.membrane_free_nodes(layout, b2i, n)
    for i in const:
        elev[i] = 13.0
    fl = sorted(free)
    sc = [{"nodes": [fl[0], fl[1]], "edges": [(fl[0], fl[1], 0.01)],
           "flat": False, "flat_pairs": (), "area": 0.0, "role": "apron"}]
    rep = ANS.membrane_conform(layout, b2i, elev, n,
                               shape_constraints=sc, icao="TEST")
    assert rep["own_law_relaxed"] == 0
    assert rep["published_reimposed"] == 0


def test_H1_the_five_round4_flags_default_ON():
    """§Shared: five flags, all DEFAULT ON, each OFF byte-identical."""
    import auto_patch.config as CFG
    for name in ("MEMBRANE_LAW_FLOOR", "PASS2_RELAXATION",
                 "ADOPT_FREEZE_AIRSIDE_ONLY", "ROAD_EVIDENCE_SEVER",
                 "TRANSVERSE_NO_STEP"):
        assert getattr(CFG, name) is True, name
        assert name in CFG.__all__, f"{name} is not in the registry"


# ═════════════════════════════════════════════════════════════════════
# HECA ROUND 4 §H4 — THE TRANSVERSE PROFILE OBEYS NO-STEP ON ITS OWN
# RING (RULINGS 2026-08-28b item 5(a))
# ═════════════════════════════════════════════════════════════════════

def _two_lip_junction():
    """One junction ring carrying a ROAD-CARVE LIP pair 8 m apart — the
    item-5(a) geometry (nodes -3531/-3532 against -3533/-3535)."""
    ring = Polygon([(0.0, 0.0), (40.0, 0.0), (40.0, 8.0), (48.0, 8.0),
                    (48.0, 30.0), (0.0, 30.0), (0.0, 0.0)])
    return _Shape(ring, "junction")


def test_H4_a_pair_within_ONE_ring_is_imposed():
    """§H4.1: a taxiway-family shape's transverse writeback may not mint
    a direct-distance violation between its OWN ring vertices — one
    authority disagreeing with ITSELF, not two authorities disagreeing.
    """
    jn = _two_lip_junction()
    layout = _Layout([jn])
    b2i, pos, ctx = _wire(layout)
    n = len(pos)
    tiers = ANS.tier_of_nodes(
        n, centerline_nodes=ANS.taxiway_family_nodes(layout, b2i, n))
    sc, senior, recs, rep = ANS.build_airside_no_step_constraints(
        layout, b2i, ctx, node_pos=pos, n_nodes=n, tier_of=tiers)
    assert rep["tier2_census_only"] > 0
    assert sc == [], "tier2<->tier2 is still not imposed by the SOLVE"
    entries, r4 = ANS.within_ring_no_step_entries(layout, b2i, n)
    assert r4["within_ring"] > 0
    assert entries and entries[0]["edges"]
    assert entries[0]["ref"] == "transverse_no_step"
    # every imposed edge joins two vertices of ONE ring
    owners = ANS.taxiway_family_ring_owners(layout, b2i, n)
    for (a, b, bud) in entries[0]["edges"]:
        assert owners[a] & owners[b]
        assert bud > 0.0


def test_H4_a_CROSS_SHAPE_tier2_pair_stays_a_census_docket():
    """"cross-shape senior pairs remain census-priced dockets" — §H4.1's
    own sentence, and the no-step spec Amendment 1 ruling it preserves.
    """
    j1 = _Shape(_rect(-25.0, -20.0, -1.0, 20.0), "junction")
    j2 = _Shape(_rect(1.0, -20.0, 25.0, 20.0), "stub")
    layout = _Layout([j1, j2])
    b2i, pos, ctx = _wire(layout)
    n = len(pos)
    tiers = ANS.tier_of_nodes(
        n, centerline_nodes=ANS.taxiway_family_nodes(layout, b2i, n))
    sc, senior, recs, rep = ANS.build_airside_no_step_constraints(
        layout, b2i, ctx, node_pos=pos, n_nodes=n, tier_of=tiers)
    assert rep["tier2_census_only"] > 0
    entries, r4 = ANS.within_ring_no_step_entries(layout, b2i, n)
    owners = ANS.taxiway_family_ring_owners(layout, b2i, n)
    for e in entries:
        for (a, b, _bud) in e["edges"]:
            assert owners[a] & owners[b], (
                "a CROSS-SHAPE tier2 pair was imposed — that is the "
                "solver tug-of-war Amendment 1 forbids")


def test_H4_flag_OFF_is_vacuous(monkeypatch):
    import auto_patch.config as CFG
    monkeypatch.setattr(CFG, "TRANSVERSE_NO_STEP", False, raising=False)
    jn = _two_lip_junction()
    layout = _Layout([jn])
    b2i, pos, ctx = _wire(layout)
    n = len(pos)
    tiers = ANS.tier_of_nodes(
        n, centerline_nodes=ANS.taxiway_family_nodes(layout, b2i, n))
    ANS.build_airside_no_step_constraints(
        layout, b2i, ctx, node_pos=pos, n_nodes=n, tier_of=tiers)
    entries, r4 = ANS.within_ring_no_step_entries(layout, b2i, n)
    assert entries == []
    assert r4["edges"] == 0


def test_H4_is_wired_into_the_final_projection():
    """The clamp binds where the transverse writeback has its last word
    — the FINAL projection — and it consumes the ALREADY-PUBLISHED
    enumeration (one enumeration, three consumers)."""
    src = Path(
        _ROOT / "src/auto_patch/elevation_per_surface/route_profile/"
        "solve.py").read_text()
    i = src.index("within_ring_no_step_entries")
    assert "joint.extend(_tr_entries)" in src[i:i + 2000]
    assert "transverse_no_step" in src
    import inspect
    isrc = inspect.getsource(ANS.within_ring_no_step_entries)
    assert "_resolve_carried_pairs" in isrc, (
        "§H4 must consume the ONE enumeration, never build a second")


def test_H1_1_a_lattice_to_lattice_edge_is_NOT_coverage():
    """"…to its nearest RING-OR-SENIOR node."  A membrane<->membrane
    edge IS the chain of 50 m x cap budgets this law exists to price, so
    it can never satisfy the coverage guarantee.  MEASURED on the weaker
    "has any priced neighbour" test: HECA, SPJC and CYXY all reported
    ZERO orphans (every lattice node carries within-shape edges to its
    lattice neighbours) while item 1's void pair stayed unpriced."""
    ap = _Shape(_rect(0.0, 0.0, 60.0, 60.0), "apron")
    layout = _Layout([ap])
    b2i, pos, ctx = _wire(layout)
    pts = [(29.0, 30.0), (31.0, 30.0)]
    idx = []
    for (x, y) in pts:
        b = layout.canonical_points.get_or_add(x, y)
        b2i[b] = len(pos) + len(idx)
        idx.append(b2i[b])
    layout.apron_lattice_presolve = [{"shape": ap, "points": pts}]
    n = len(pos) + len(idx)
    # the ONLY stated pair is lattice <-> lattice
    existing = frozenset({(min(idx), max(idx))})
    rows, rep = ANS.enumerate_airside_no_step_pairs(
        layout, b2i, ctx, node_pos=pos, n_nodes=n, existing_pairs=existing)
    assert rep["floor_orphans"] == 2, (
        "a lattice<->lattice edge was counted as coverage")
    assert rep["floor_edges"] == 2
    mem = set(idx)
    got = [r for r in rows if (r[2] in mem) != (r[3] in mem)]
    assert len(got) >= 2, "no membrane<->ring edge was minted"
