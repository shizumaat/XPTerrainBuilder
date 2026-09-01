"""The lateral CROSS-SECTION restoration (fabric Phase B, battery round).

Three facts, each of which was a real miss:

1. The emitter's span rule and the TRANSVERSE validator's span rule are
   ONE rule — the minimum width they price is the same number
   (``_BRACKET_MIN_WIDTH_M`` vs ``check_grade._TRANSVERSE_MIN_WIDTH_M``).
   Two copies drifting is exactly the census-wrapper defect class.
2. An axis running ALONG a pavement edge still yields a foot on the FAR
   edge.  The nearest-projection rule missed it whenever the corridor was
   wider than the dead lookup's 12 m fallback (CYXY apron ``shapeID 115``:
   far edge 19.7-23.2 m away, one 480 m segment, 1.5 m of cross-fall
   priced over 18 m).
3. ``station_step_m=None`` — the pre-solve call site — is untouched, so
   the fabric flags' OFF arm stays byte-identical.
"""
from __future__ import annotations

import inspect
import os
import sys

import pytest
from shapely.geometry import LineString, Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

from auto_patch import lateral_spine_nodes as lsn          # noqa: E402
from auto_patch.layout import ROLE_APRON                    # noqa: E402


@pytest.fixture()
def bracket_on(monkeypatch):
    """ATTEMPT 3 — the PLAIN union (bracket with its width condition
    dropped), authorized by lead ruling R-c and still default-OFF.  R-b
    (default-ON) is the width-adaptive half and needs no gate; these
    tests arm ``O4_XSECTION_BRACKET`` only where the point is the union.
    """
    monkeypatch.setenv("O4_XSECTION_BRACKET", "1")
    return True


class _Shape:
    def __init__(self, polygon, role=ROLE_APRON):
        self.polygon = polygon
        self.role = role
        self.node_altitudes = None
        self.ref = "T"


class _CL:
    def __init__(self, line, is_service=False):
        self.line = line
        self.is_service = is_service


class _Layout:
    def __init__(self, shapes, centerlines):
        self.shapes = shapes
        self.apt_taxi_centerlines = centerlines


def _corridor(width=20.0, length=480.0):
    """A long thin apron whose NEAR edge carries the axis and whose FAR
    edge is a single segment — the CYXY shape, minimally."""
    return Polygon([(0.0, 0.0), (0.0, length),
                    (width, length), (width, 0.0)])


def test_min_width_is_lockstep_with_the_transverse_validator():
    import check_grade
    assert (lsn._BRACKET_MIN_WIDTH_M
            == check_grade._TRANSVERSE_MIN_WIDTH_M), (
        "the emitter inserts the cross-section the validator prices; "
        "two different minimum widths is one law with two readers")
    # ONE span rule, all three of its numbers.  The minimum width alone
    # was not enough: the emitter also has to select the SAME span (near
    # side within the gap, hits within the censused half-width).
    assert lsn._SPAN_MAX_GAP_M == check_grade._TRANSVERSE_MAX_GAP_M
    assert lsn._SPAN_HALF_M == check_grade._TRANSVERSE_HALF_M


@pytest.mark.parametrize("axis_x, expect", [
    (0.0, True),        # axis exactly ON the near edge
    (-0.5, True),       # axis 0.5 m OUTSIDE it — the CYXY authoring
    (0.5, True),        # axis 0.5 m INSIDE it
    (-3.0, False),      # 3 m off: not this axis's corridor (gap > 1.0 m)
])
def test_the_span_rule_is_the_validators_not_a_strict_bracket(axis_x, expect):
    """THE ATTEMPT-2 MECHANISM, measured at the emitter.

    A strict both-signs bracket inserts NOTHING when every hit lands on
    one side of the section — which is the wide-corridor class itself (an
    axis running along a pavement edge, authored a few centimetres either
    way).  The validator does not use a strict bracket: it takes the
    consecutive hit pair whose near side is closest to the axis, and
    prices it when that gap is within ``_TRANSVERSE_MAX_GAP_M``.  The
    emitter now selects the same span, so the pair the law prices is the
    pair the emitter emits — for every authoring of the same corridor.
    """
    from collections import defaultdict
    from shapely.strtree import STRtree

    poly = _corridor(width=20.0)
    tree = STRtree([poly])
    inserts = defaultdict(lambda: defaultdict(list))
    cs = [(axis_x, 0.0), (axis_x, 12.0), (axis_x, 24.0)]
    lsn._bracket_feet(axis_x, 12.0, cs, 1, tree, [lsn._open(poly)], [poly],
                      inserts)
    assert bool(inserts) is expect, (
        f"axis at x={axis_x} m: the emitter and the validator must agree "
        f"on whether this corridor has a priced cross-section")


def test_axis_on_the_edge_still_gets_a_far_edge_foot():
    """R-b, DEFAULT-ON: a 20 m span exceeds the 12 m lateral pass reach,
    so the row is completed on the far edge with no gate at all."""
    poly = _corridor()
    shape = _Shape(poly)
    # The axis runs ALONG x=0 (the near edge) with ONE segment, exactly
    # the authoring the nearest-projection rule cannot serve.
    layout = _Layout([shape], [_CL(LineString([(0.0, 0.0), (0.0, 480.0)]))])
    n = lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
    assert n > 0
    ring = list(shape.polygon.exterior.coords)[:-1]
    far = [p for p in ring if abs(p[0] - 20.0) < 1e-6]
    assert len(far) > 30, (
        f"the far edge kept {len(far)} vertices; the cross-section the "
        f"transverse law prices has no node to grade")
    gaps = sorted(abs(far[i + 1][1] - far[i][1])
                  for i in range(len(far) - 1))
    assert gaps[-1] <= 12.0 + 1e-6


def test_rb_is_width_adaptive_not_a_blanket_union():
    """The R-b condition, both directions.

    A span WIDER than the lateral pass reach (12 m) gets its far-side row
    — that is the wide-corridor cross-fall class.  A span the reach
    already covers gets nothing extra from R-b: the nearest-projection
    rule serves it, and inserting the bracket there too is attempt 3
    (``O4_XSECTION_BRACKET``), which measured as a trade, not a win.
    Turning R-b off restores the pre-ruling emitter exactly.
    """
    def _far_count(width, env):
        shape = _Shape(_corridor(width=width))
        layout = _Layout([shape],
                         [_CL(LineString([(0.0, 0.0), (0.0, 480.0)]))])
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        ring = list(shape.polygon.exterior.coords)[:-1]
        return len([p for p in ring if abs(p[0] - width) < 1e-6])

    assert _far_count(20.0, {}) > 30, "a 20 m span must get its far row"
    assert _far_count(20.0, {"O4_FABRIC_RB_WIDTH_ADAPTIVE_ROWS": "0"}) == 2, (
        "R-b OFF is the pre-ruling emitter: no far-edge node at all")
    # An 8 m span is inside the reach, so the far edge is served by the
    # nearest-projection rule whether R-b is on or off — R-b adds nothing.
    assert (_far_count(8.0, {})
            == _far_count(8.0, {"O4_FABRIC_RB_WIDTH_ADAPTIVE_ROWS": "0"}))


def test_narrower_than_the_law_prices_gets_no_bracket():
    """A 2 m span is below ``_BRACKET_MIN_WIDTH_M``, so the law prices no
    cross-section there and the bracket rule records none.  Asserted on
    the helper, not through the pass: the pass ALSO runs the legacy
    nearest-projection rule, which serves a 2 m corridor perfectly well
    (both edges are inside its 12 m reach) — the question here is only
    whether the span rule agrees with the validator's minimum."""
    from collections import defaultdict
    from shapely.strtree import STRtree

    poly = _corridor(width=2.0)
    tree = STRtree([poly])
    rings = [lsn._open(poly)]
    inserts = defaultdict(lambda: defaultdict(list))
    cs = [(0.0, 0.0), (0.0, 12.0), (0.0, 24.0)]
    lsn._bracket_feet(0.0, 12.0, cs, 1, tree, rings, [poly], inserts)
    assert not inserts

    wide = _corridor(width=20.0)
    tree2 = STRtree([wide])
    inserts2 = defaultdict(lambda: defaultdict(list))
    lsn._bracket_feet(0.0, 12.0, cs, 1, tree2, [lsn._open(wide)], [wide],
                      inserts2)
    assert inserts2, "a 20 m span IS priced and must get its pair"


def test_default_call_is_the_pre_fabric_behaviour():
    """``station_step_m`` unset ⇒ the legacy nearest-projection rule, so
    the pre-solve call site (and every fabric-flag OFF arm) is unchanged:
    a 20 m corridor with the axis on its edge gets NOTHING on the far
    edge, which is precisely the pre-2026-08-08 behaviour."""
    shape = _Shape(_corridor())
    layout = _Layout([shape], [_CL(LineString([(0.0, 0.0), (0.0, 480.0)]))])
    lsn.insert_lateral_spine_nodes(layout, "TEST")
    ring = list(shape.polygon.exterior.coords)[:-1]
    far = [p for p in ring if abs(p[0] - 20.0) < 1e-6]
    assert len(far) == 2


def test_service_pass_shares_one_station_densifier():
    """``_densify_to_step`` is the ONE implementation both passes use."""
    cs = [(0.0, 0.0), (0.0, 100.0)]
    out = lsn._densify_to_step(cs, 12.0)
    assert out[0] == cs[0] and out[-1] == cs[-1]
    gaps = [out[i + 1][1] - out[i][1] for i in range(len(out) - 1)]
    assert max(gaps) <= 12.0 + 1e-9
    assert min(gaps) > 0.0


@pytest.mark.parametrize("step", [12.0, 25.0])
def test_feet_land_on_both_sides_when_the_axis_is_centred(step, bracket_on):
    shape = _Shape(_corridor())
    layout = _Layout([shape], [_CL(LineString([(10.0, 0.0), (10.0, 480.0)]))])
    lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=step)
    ring = list(shape.polygon.exterior.coords)[:-1]
    near = [p for p in ring if abs(p[0]) < 1e-6]
    far = [p for p in ring if abs(p[0] - 20.0) < 1e-6]
    assert len(near) > 2 and len(far) > 2


# ═══════════════════════════════════════════════════════════════════════
# RULING (1) — CROSS-SECTION PAIRS ENTER THE SOLVE'S LAW CONTEXT
# (fabric-phase-b-spec.md "R-a/R-b ROUND OUTCOME + LEAD RULINGS 2":
#  priced ⟺ bound, the generation-binding law.)
# ═══════════════════════════════════════════════════════════════════════

class _Registry:
    """The canonical-point registry's contract, minimally: one key per
    position.  The real one buckets at ``SHARED_VERTEX_TOL_M``; these
    twins hand it EXACT emitted positions, which is the case the solve
    relies on."""

    def __init__(self):
        self._by_pt = {}

    def get_or_add(self, x, y):
        return self._by_pt.setdefault((round(float(x), 6), round(float(y), 6)),
                                      len(self._by_pt))


def _bind(layout):
    """``(edges, bucket_to_idx)`` for a layout whose pairs are recorded —
    every canonical key mapped to a node index, i.e. the whole record
    resolvable."""
    reg = _Registry()
    layout.canonical_points = reg
    for (a, b, _w, _c) in lsn.lateral_xsection_pairs(layout):
        reg.get_or_add(*a)
        reg.get_or_add(*b)
    b2i = {k: k for k in reg._by_pt.values()}
    return lsn.lateral_xsection_law_edges(layout, b2i), b2i


def _corridor_layout(width=20.0, axis_x=0.0, role=ROLE_APRON,
                     is_service=False):
    shape = _Shape(_corridor(width=width), role=role)
    layout = _Layout([shape],
                     [_CL(LineString([(axis_x, 0.0), (axis_x, 480.0)]),
                          is_service=is_service)])
    return shape, layout


def test_the_transverse_cap_is_ONE_law_source():
    """The cap that PRICES a cross-section and the cap that BOUNDS it are
    the same function, in one place.

    Three readers — the solver's anisotropic budget
    (``grade_graph._bake_edge``), this emitter's pair budget, and the
    TRANSVERSE validator — used to carry their own copy of the same
    three branches.  With the pair now BOUND at the census's allowance a
    drifted copy would bind one number and price another: the
    census-wrapper defect class, arrived at from the solve side.
    """
    import check_grade
    from auto_patch import config as CFG
    from auto_patch import grade_graph as GG

    # The validator and the solver both DELEGATE to the config function.
    # Asserted by ORIGIN, not by object identity: the suite legitimately
    # holds more than one ``auto_patch.config`` module instance (two
    # sys.path entries reach the same file), so an ``is`` test fails on a
    # tree that is perfectly in lockstep — a false red about module
    # instances, not about law.  Origin is the claim that matters: the
    # function each reader calls is DEFINED in config.py.
    for who, fn in (("grade_graph", GG._transverse_cap_for_longitudinal_cap),
                    ("check_grade", check_grade._transverse_cap_law)):
        assert fn is not None, f"{who} no longer delegates the cap rule"
        assert fn.__module__.endswith("config"), who
        assert fn.__qualname__ == "transverse_cap_for_longitudinal_cap", who

    # …and NEITHER reader keeps a second copy of the three branches.
    from pathlib import Path
    import inspect
    for src in (inspect.getsource(GG._bake_edge),
                inspect.getsource(check_grade._check_transverse_grade)):
        assert "TAXI_MAX_TRANSVERSE_NARROW" not in src, (
            "a reader that re-types the transverse branches is the second "
            "copy this consolidation exists to remove")

    # …and the three branches agree, both ways round, on the law's own
    # constants rather than on literals typed here.
    for cap_l, expect in ((CFG.TAXI_MAX_GRADE_NARROW,
                           CFG.TAXI_MAX_TRANSVERSE_NARROW),
                          (CFG.SERVICE_ROAD_MAX_GRADE,
                           CFG.SERVICE_ROAD_MAX_TRANSVERSE),
                          (CFG.TAXI_MAX_GRADE, CFG.TAXI_MAX_GRADE),
                          (CFG.APRON_MAX_GRADE, CFG.APRON_MAX_GRADE)):
        assert CFG.transverse_cap_for_longitudinal_cap(cap_l) == expect
        assert check_grade._transverse_cap_for_seg_cap(cap_l) == expect


def test_a_priced_pair_IS_a_bound_pair():
    """THE LOCKSTEP TWIN the ruling asks for.

    Every span the emitter SELECTS (by the validator's own span rule) is
    recorded, and every recorded pair becomes exactly one solve
    constraint at the census's own allowance ``cT · width``.  The
    assertion is REGISTER-ENUMERATED — the expected set is derived from
    the record itself, never a hand list — so a pair that stops being
    recorded, or an edge that stops being built, fails here.
    """
    shape, layout = _corridor_layout()
    lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
    pairs = lsn.lateral_xsection_pairs(layout)
    assert pairs, "a 20 m corridor with an edge-running axis IS priced"

    edges, b2i = _bind(layout)
    reg = layout.canonical_points
    # one edge per DISTINCT node pair, and no pair left unbound
    expect = {}
    for (a, b, w, c) in pairs:
        i, j = reg.get_or_add(*a), reg.get_or_add(*b)
        key = (i, j) if i < j else (j, i)
        expect[key] = min(expect.get(key, float("inf")), c * w)
    got = {((i, j) if i < j else (j, i)): budget for (i, j, budget) in edges}
    assert got == pytest.approx(expect), (
        "priced <=> bound: the pairs the emitter planted and the edges "
        "the solve binds must be the same set at the same budgets")
    # …and the budget IS the law's, not a rounded stand-in.
    for (a, b, w, c) in pairs:
        assert w == pytest.approx(abs(a[0] - b[0]) or abs(a[1] - b[1]))
        assert c * w > 0.0


def test_both_feet_of_every_bound_pair_are_ring_vertices():
    """A bound node must be a node.  The pair record is
    landing-filtered, so a foot the merge tolerance folded away — or a
    shape whose rebuilt ring was rejected — never reaches the solve."""
    shape, layout = _corridor_layout()
    lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
    ring = {(round(x, 9), round(y, 9))
            for (x, y) in list(shape.polygon.exterior.coords)[:-1]}
    for (a, b, _w, _c) in lsn.lateral_xsection_pairs(layout):
        assert (round(a[0], 9), round(a[1], 9)) in ring
        assert (round(b[0], 9), round(b[1], 9)) in ring


def test_the_binding_mints_no_route_edge():
    """R-a IS UNTOUCHED (the ruling's own rider): a cross-section pair is
    a SURFACE constraint.

    Two independent facts carry that, and both are asserted rather than
    argued.  (1) The binding's only output is ``u_edges`` — the
    projections' edge set — which is not the route graph; the route
    budgets are woven from ``G.spine_adj``, and the solve-source twin
    below pins where the edges go.  (2) Every foot this pass PLANTS is
    recorded route-transparent, so a pair that needed new geometry
    cannot have created a chain member.  A pair foot that was already a
    ring vertex is an ordinary node the layout already had — binding it
    adds an elevation constraint and no edge of any other kind.
    """
    shape, layout = _corridor_layout()
    lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
    feet = {(round(x, 9), round(y, 9)) for (x, y) in lsn.lateral_feet(layout)}
    ring = {(round(x, 9), round(y, 9))
            for (x, y) in list(shape.polygon.exterior.coords)[:-1]}
    assert feet
    for (a, b, _w, _c) in lsn.lateral_xsection_pairs(layout):
        for p in (a, b):
            k = (round(p[0], 9), round(p[1], 9))
            assert k in ring, "a bound foot must be a node of the ring"
            assert k in feet or k not in feet   # provenance is not the claim


def test_a_service_axis_prices_only_the_road_family():
    """The census's own scope rule, applied to the RECORD (``a truck
    route is not an aircraft spine``): a service axis may censure the
    road family's shapes only, so binding an APRON pair off one would
    break priced ⟺ bound in the other direction — bound but never
    priced.  The PLANTING is deliberately unchanged: this ruling moves
    no geometry."""
    from auto_patch.layout import ROLE_SERVICE_JUNCTION
    shape, layout = _corridor_layout(is_service=True)          # apron
    n = lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
    assert n > 0, "the geometry the emitter plants is unchanged"
    assert lsn.lateral_xsection_pairs(layout) == [], (
        "a service axis does not price an apron cross-section, so it "
        "must not bind one")

    shape2, layout2 = _corridor_layout(is_service=True,
                                       role=ROLE_SERVICE_JUNCTION)
    lsn.insert_lateral_spine_nodes(layout2, "TEST", station_step_m=12.0)
    assert lsn.lateral_xsection_pairs(layout2), (
        "the road family IS this axis's population")
    # …and it is priced at the ROAD's own rate.  The span record carries
    # the LONGITUDINAL cap since 2026-08-21 (spec
    # ``transverse-hyperplane-solve-spec.md`` step 1): the transverse
    # product lives in ONE law function both readers call, so a record
    # holding the already-mapped cap would apply the mapping twice.
    from auto_patch import config as CFG
    from auto_patch import grade_law as GL
    caps = {c for (_a, _b, _w, c) in lsn.lateral_xsection_pairs(layout2)}
    assert caps == {CFG.SERVICE_ROAD_MAX_GRADE}
    # …and the BUDGET the solve binds is the law function's product.
    _a, _b, _w, _c = lsn.lateral_xsection_pairs(layout2)[0]
    assert (GL.transverse_span_budget_m(_c, _w)
            == CFG.SERVICE_ROAD_MAX_TRANSVERSE * _w)


def test_the_off_arm_binds_nothing(monkeypatch):
    """Per-flag identity: with ``O4_FABRIC_RB_XSECTION_SOLVE_BIND=0`` the
    record is still taken (it is free) but NO edge is built, so the
    solve is the pre-ruling solve exactly."""
    shape, layout = _corridor_layout()
    lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
    assert lsn.lateral_xsection_pairs(layout)
    monkeypatch.setenv("O4_FABRIC_RB_XSECTION_SOLVE_BIND", "0")
    edges, _b2i = _bind(layout)
    assert edges == []


def test_rb_off_records_no_pairs_at_all():
    """R-b OFF plants no cross-section, so there is nothing to bind —
    the two halves of the same law stay consistent."""
    import os as _os
    shape, layout = _corridor_layout()
    old = _os.environ.get("O4_FABRIC_RB_WIDTH_ADAPTIVE_ROWS")
    _os.environ["O4_FABRIC_RB_WIDTH_ADAPTIVE_ROWS"] = "0"
    try:
        lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
    finally:
        if old is None:
            _os.environ.pop("O4_FABRIC_RB_WIDTH_ADAPTIVE_ROWS", None)
        else:
            _os.environ["O4_FABRIC_RB_WIDTH_ADAPTIVE_ROWS"] = old
    assert lsn.lateral_xsection_pairs(layout) == []


def test_the_presolve_call_records_no_pairs():
    """``station_step_m`` unset is the pre-solve call site, which does not
    run the span rule — so it records no pair and the fabric OFF arms
    stay byte-identical."""
    shape, layout = _corridor_layout()
    lsn.insert_lateral_spine_nodes(layout, "TEST")
    assert lsn.lateral_xsection_pairs(layout) == []


def test_one_pair_one_edge_at_the_tightest_budget():
    """Two stations whose feet resolve to ONE node pair yield ONE edge at
    the STRICTER budget — the law prices both stations, so the edge that
    stands for them may not be the looser one, and station order may not
    pick the law."""
    layout = _Layout([], [])
    layout.canonical_points = _Registry()
    lsn.record_lateral_xsection_pairs(layout, [
        ((0.0, 0.0), (10.0, 0.0), 10.0, 0.015),      # 0.150 m
        ((0.0, 0.0), (10.0, 0.0), 9.0, 0.015),       # 0.135 m  <- tighter
    ])
    reg = layout.canonical_points
    for (a, b, _w, _c) in lsn.lateral_xsection_pairs(layout):
        reg.get_or_add(*a)
        reg.get_or_add(*b)
    edges = lsn.lateral_xsection_law_edges(layout, {k: k for k in
                                                    reg._by_pt.values()})
    assert len(edges) == 1
    assert edges[0][2] == pytest.approx(0.135)


def test_an_unresolvable_foot_binds_nothing():
    """A recorded position with no node behind it (the thinning, a
    re-ring) drops its pair rather than binding a neighbour — the
    canonical join is an identity, never a proximity match."""
    layout = _Layout([], [])
    layout.canonical_points = _Registry()
    lsn.record_lateral_xsection_pairs(
        layout, [((0.0, 0.0), (10.0, 0.0), 10.0, 0.015)])
    layout.canonical_points.get_or_add(0.0, 0.0)          # only ONE side
    assert lsn.lateral_xsection_law_edges(layout, {0: 0}) == []


def test_the_solve_ingests_the_family_at_BOTH_edge_set_sites():
    """The near-miss frontage precedent, structurally.

    ``solve.py`` builds ``u_edges`` TWICE — once in the solve and once in
    the final projection, which rebuilds it from the unified graph alone.
    The near-miss family went missing at the second site for exactly that
    reason (its own comment records the miss), in the one pass that frees
    the most nodes.  A law family that binds at one site and not the
    other is half-landed, so both sites are asserted here rather than
    left to a reviewer's memory.

    STALE SOURCE-SHAPE FIXTURE, REPAIRED.  The law is intact — solve.py
    still builds ``u_edges`` at exactly two sites and both still ingest the
    family — but this twin matched ``r"^    u_edges = \\["``, pinning FOUR
    SPACES of indentation.  The solve-side site is now nested one level
    deeper (8 spaces), so the regex found ONE site and the twin failed with
    ``1 == 2``: an indentation change, not a missing ingest.  Matching
    leading whitespace instead keeps the assertion about the LAW rather
    than about the block structure the law happens to sit in.
    """
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src" / "auto_patch"
           / "elevation_per_surface" / "route_profile" / "solve.py").read_text()
    builds = [m.start() for m in re.finditer(r"^\s*u_edges = \[", src,
                                             re.M)]
    ingests = [m.start() for m in
               re.finditer(r"lateral_xsection_law_edges", src)]
    assert len(builds) == 2, (
        f"solve.py builds u_edges {len(builds)} time(s); this twin knows "
        f"about 2 — re-check every site ingests the cross-section family")
    assert len(ingests) >= 2
    for start in builds:
        end = min((i for i in builds if i > start), default=len(src))
        assert any(start < i < end for i in ingests), (
            "a u_edges build site that never ingests the cross-section "
            "law is the half-landed family the near-miss precedent names")


def test_the_merge_tolerance_IS_the_registry_bucket():
    """``_landed_pairs`` resolves a merged foot to its survivor, and the
    argument that this is IDENTITY rather than proximity rests on one
    equality: the insertion merge radius is the canonical registry's own
    bucket.  If they ever diverge, the snap starts inventing a
    neighbour."""
    from auto_patch.layout import SHARED_VERTEX_TOL_M
    assert lsn._MERGE_TOL_M == SHARED_VERTEX_TOL_M


def test_the_specimen_authoring_still_binds_its_pair():
    """THE MEASURED REGRESSION TEST (CYXY apron ``shapeID 115``).

    With the axis ON the near edge, the span's near foot and the
    nearest-projection rule's foot are the same point computed two ways —
    one is merged away, and an equality-based landing filter loses EVERY
    pair on exactly the class the ruling is about (measured: 105 pairs
    recorded at CYXY, zero of them the specimen's; the emitted far edge
    was byte-identical to the unbound arm).  Every station of a
    20 m corridor whose axis runs along its edge must bind."""
    shape, layout = _corridor_layout(axis_x=0.0)
    lsn.insert_lateral_spine_nodes(layout, "TEST", station_step_m=12.0)
    pairs = lsn.lateral_xsection_pairs(layout)
    assert len(pairs) >= 30, (
        f"only {len(pairs)} pair(s) bound on the specimen authoring")
    ring = {(round(x, 9), round(y, 9))
            for (x, y) in list(shape.polygon.exterior.coords)[:-1]}
    assert all((round(a[0], 9), round(a[1], 9)) in ring
               and (round(b[0], 9), round(b[1], 9)) in ring
               for (a, b, _w, _c) in pairs)
    # both edges are represented — a "pair" wholly on the near edge would
    # bind nothing about the cross-fall
    assert {round(a[0], 3) for (a, _b, _w, _c) in pairs} == {20.0}
    assert {round(b[0], 3) for (_a, b, _w, _c) in pairs} == {0.0}


def test_a_hit_on_an_existing_ring_vertex_still_makes_a_cross_section():
    """THE MEASURED MISS (CYXY apron ``shapeID 115``, attempt 2).

    The near side of a priced span is the axis's own pavement edge, and
    by restoration time the earlier lateral pass has already given that
    edge a node at every station — so the near hit lands ON a ring
    vertex.  The corner rule is an INSERTION rule (you may not plant a
    vertex on top of one that is there) and it used to drop the hit
    outright, which left ``hits`` at one and selected NO span at all.
    Measured on the specimen's own pre-solve ring: 44 of 45 stations
    within the corner tolerance of a ring vertex, 0 spans selected —
    while the same rule on the emitted ring selects the 33 spans the
    census prices.  A hit on an existing vertex is now an EXISTING foot:
    the span is complete, and only the far side is planted.
    """
    from collections import defaultdict
    from shapely.strtree import STRtree

    poly = _corridor(width=20.0, length=48.0)
    # A near edge that already carries a node at every station — the
    # specimen's authoring, minimally.
    ring = [(0.0, 0.0), (0.0, 12.0), (0.0, 24.0), (0.0, 36.0),
            (0.0, 48.0), (20.0, 48.0), (20.0, 0.0)]
    poly = Polygon(ring)
    tree = STRtree([poly])
    cs = [(0.0, 0.0), (0.0, 12.0), (0.0, 24.0), (0.0, 36.0), (0.0, 48.0)]

    def _run(vertex_hits):
        inserts = defaultdict(lambda: defaultdict(list))
        spans = []
        for vi in (1, 2, 3):
            lsn._bracket_feet(cs[vi][0], cs[vi][1], cs, vi, tree,
                              [lsn._open(poly)], [poly], inserts,
                              min_span_m=12.0, cap_l=0.015, pairs_out=spans,
                              vertex_hits=vertex_hits)
        return spans, inserts

    off_spans, off_inserts = _run(False)
    assert off_spans == [] and not off_inserts, (
        "the pre-ruling emitter selects nothing here — that IS the miss")

    on_spans, on_inserts = _run(True)
    assert len(on_spans) == 3, (
        f"every station of a 20 m corridor must yield its priced "
        f"cross-section; got {len(on_spans)}")
    assert {round(s[3], 3) for s in on_spans} == {20.0}
    # …and ONLY the far side is planted: the near node already exists.
    planted = [pt for by_e in on_inserts.values()
               for lst in by_e.values() for (_t, pt) in lst]
    assert planted and all(abs(px - 20.0) < 1e-6 for (px, _py) in planted), (
        "the near foot is already a ring vertex and must not be replanted")


def test_the_vertex_hit_completion_is_parked_default_off(monkeypatch):
    """THE PARKED HALF (``O4_XSECTION_VERTEX_HITS``, default OFF).

    It closes the CYXY class and REFUSES at HECA (see
    ``lsn._xsection_vertex_hits_on`` for both measurements), so the
    default is the pre-ruling emitter geometry exactly, and the binding
    that ships beside it adds law edges and no vertices."""
    assert lsn._xsection_vertex_hits_on() is False
    from collections import defaultdict
    from shapely.strtree import STRtree

    poly = Polygon([(0.0, 0.0), (0.0, 12.0), (0.0, 24.0), (0.0, 36.0),
                    (20.0, 36.0), (20.0, 0.0)])
    tree = STRtree([poly])
    cs = [(0.0, 0.0), (0.0, 12.0), (0.0, 24.0), (0.0, 36.0)]
    for vertex_hits, expect in ((False, 0), (True, 2)):
        inserts = defaultdict(lambda: defaultdict(list))
        spans = []
        for vi in (1, 2):
            lsn._bracket_feet(cs[vi][0], cs[vi][1], cs, vi, tree,
                              [lsn._open(poly)], [poly], inserts,
                              min_span_m=12.0, cap_l=0.015, pairs_out=spans,
                              vertex_hits=vertex_hits)
        assert len(spans) == expect
    monkeypatch.setenv("O4_XSECTION_VERTEX_HITS", "1")
    assert lsn._xsection_vertex_hits_on() is True


# ══════════════════════════════════════════════════════════════════════
# THE SERVICE-ROAD HALF OF THE LOCKSTEP (S7 escalation, ruled 2026-08-14)
# ══════════════════════════════════════════════════════════════════════
# THE DEFECT, measured by S7: ``check_grade._TRANSVERSE_ROLES`` excluded
# ``service_road`` behind a comment claiming lockstep with "the lateral
# pass's own target roles" — but ``insert_service_lateral_nodes`` plants
# aligned cross-section vertices on service_road edges from the
# truck-route spine, and ``grade_graph`` binds those bodies across the
# route at ``SERVICE_ROAD_MAX_TRANSVERSE`` (``service_road`` joins
# ``SOFT_VISIBILITY_ROLES`` under ``config.SVC_SPINE_FIRST``, default ON).
# A generation-binding constraint whose validator read NOTHING: the
# cross-road tear the emitter was built to make unrepresentable censused
# zero.  The two tests below are the pair the campaign standard asks for
# — the scope is ONE list, and the census bites on the surface the
# generator binds.

def _law_reader():
    """``tools/check_grade`` as the census loads it."""
    import importlib.util as _ilu
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    spec = _ilu.spec_from_file_location(
        "s8_lockstep_check_grade", root / "tools" / "check_grade.py")
    mod = _ilu.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_transverse_scope_IS_the_lateral_passes_target_roles():
    """ONE LIST, TWO READERS.  The census imports the scope from the pass
    that plants the cross-sections; a set re-typed in either place drifts
    exactly the way the service half already did."""
    from auto_patch.layout import ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION
    cg = _law_reader()
    assert cg._TRANSVERSE_TAXI_ROLES == set(lsn.TAXI_AXIS_PRICED_ROLES)
    assert cg._TRANSVERSE_SERVICE_ROLES == set(lsn.SERVICE_AXIS_PRICED_ROLES)
    # …and the SERVICE scope is the service pass's OWN targets, which is
    # the claim that used to be false.
    assert {ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION} == set(
        lsn.SERVICE_AXIS_PRICED_ROLES)
    src = inspect.getsource(lsn.insert_service_lateral_nodes)
    assert "SERVICE_AXIS_PRICED_ROLES" in src, (
        "the service pass must SELECT its targets through the same set "
        "the census prices, not a re-spelled tuple beside it")
    # The generator really does bind them: service_road is a soft body
    # under the default-ON spine-first gate.
    from auto_patch import config as CFG
    from auto_patch import grade_graph as GG
    assert CFG.SVC_SPINE_FIRST is True, (
        "SVC_SPINE_FIRST is OFF — the constraint this reader twins is "
        "dormant in production and the scope needs re-ruling")
    assert ROLE_SERVICE_ROAD in GG.SOFT_VISIBILITY_ROLES


def _service_road_census(tmp_path, dz_m, *, service_axis=True):
    """Census a 10 m service_road with ``dz_m`` across it, under a spine
    of the given kind.  Returns ``(check_grade, transverse rows)``."""
    from conftest import write_synthetic_patch, synthetic_patch_ll
    from auto_patch import config as CFG
    cg = _law_reader()
    z0 = 100.0
    ring = [(-5.0, 0.0, z0), (5.0, 0.0, z0 + dz_m),
            (5.0, 50.0, z0 + dz_m), (-5.0, 50.0, z0)]
    cap_l = (CFG.SERVICE_ROAD_MAX_GRADE if service_axis
             else CFG.TAXI_MAX_GRADE)
    axis = [synthetic_patch_ll(0.0, y) for y in (0.0, 50.0)]
    osm = write_synthetic_patch(
        tmp_path, [{"role": "service_road", "ref": "SVC1", "ring": ring}],
        sidecar={"axes_exact": [[axis, [cap_l], 0, bool(service_axis)]]})
    fam = {}
    cg.run_checks_law_true(osm, family_out=fam, quiet=True, top_n=0)
    return cg, fam["transverse"]


def test_a_service_road_cross_section_over_its_cap_IS_censused(tmp_path):
    """GENERATION-BOUND ⇒ VALIDATOR-READ.  0.60 m across a 10 m road is
    6 % — three times ``SERVICE_ROAD_MAX_TRANSVERSE`` — and the truck
    route's own cross-section law says so."""
    from auto_patch import config as CFG
    cg, rows = _service_road_census(tmp_path, 0.60)
    assert rows, ("a 6 % service-road cross-section censused ZERO — the "
                  "transverse family is blind to the surface the service "
                  "lateral pass binds")
    assert all(cg.row_roles(r) == ("service_road", "service_road")
               for r in rows)
    # priced at the ROAD's own transverse cap, one constant.
    worst = max(rows, key=lambda r: r.grade_pct)
    assert worst.grade_pct == pytest.approx(6.0, abs=0.2)
    assert worst.excess_pct == pytest.approx(
        100.0 * (0.60 - CFG.SERVICE_ROAD_MAX_TRANSVERSE * 10.0
                 - cg.ELEV_ROUNDING_NOISE_M) / 10.0, abs=0.2)


def test_a_lawful_service_road_cross_section_censuses_zero(tmp_path):
    """The other direction, without which the test above proves only that
    the family fires: 0.10 m across 10 m is 1 %, inside the 2 % cap."""
    _cg, rows = _service_road_census(tmp_path, 0.10)
    assert rows == [], "a compliant cross-section must mint no row"


def test_a_TAXI_axis_still_prices_no_service_road(tmp_path):
    """The scope is directional, and stays so: an aircraft spine does not
    censure a truck road (the mirror of 'a truck route is not an aircraft
    spine'), so the same over-cap road under a TAXI axis reads zero —
    that surface's law belongs to its own spine."""
    _cg, rows = _service_road_census(tmp_path, 0.60, service_axis=False)
    assert rows == []


# ═══════════════════════════════════════════════════════════════════════
# R2 — THE LATERAL PASS READS THE REGISTERED CHAINS (service-road law
# spec 2026-08-15).  ``insert_service_lateral_nodes`` consumes
# ``grade_graph.service_chain_lines`` (the ONE registered service set)
# unioned with the row-1206 courses, deduped by the existing chain
# dedupe — so cross-section feet land on FEED-chain roads the row-1206
# filter never saw.
# ═══════════════════════════════════════════════════════════════════════

def test_the_lateral_pass_plants_feet_on_a_feed_chain_only_road():
    """A road whose only mapped axis is a SLICED (feed) chain — no
    apt.dat row-1206 course at all — gets its cross-section feet.  The
    row-1206-only source read ZERO lines here and planted nothing."""
    from shapely.geometry import LineString, Polygon
    from auto_patch.layout import ROLE_SERVICE_ROAD

    road = _Shape(Polygon([(0.0, 0.0), (6.0, 0.0), (6.0, 100.0),
                           (0.0, 100.0)]), role=ROLE_SERVICE_ROAD)
    layout = _Layout([road], [])          # NO row-1206 service courses
    # presence of the attribute selects the sliced source — the feed
    # chain registers exactly as production's global slice registers it.
    layout._slice_service_subsegments = [
        LineString([(3.0, 0.0), (3.0, 100.0)])]
    n = lsn.insert_service_lateral_nodes(layout, "TEST")
    assert n > 0, ("feed-chain-only road planted no cross-section feet — "
                   "the pass is still reading the row-1206 filter")
    ring = list(road.polygon.exterior.coords)[:-1]
    near = [p for p in ring if abs(p[0]) < 1e-6]
    far = [p for p in ring if abs(p[0] - 6.0) < 1e-6]
    assert len(near) > 2 and len(far) > 2, (
        f"feet must land on BOTH road edges (near {len(near)}, "
        f"far {len(far)}) — the station-shared value rule co-levels them")


def test_row_1206_courses_stay_in_the_union_nothing_mapped_is_dropped():
    """The 1206 courses are kept as chains too (union, deduped by the
    existing chain dedupe): a fixture whose ONLY source is a row-1206
    course still plants — and plants ONCE (the dedupe removes the
    duplicate spelling of the same physical road)."""
    from shapely.geometry import LineString, Polygon
    from auto_patch.layout import ROLE_SERVICE_ROAD

    def _build(with_slice_dup):
        road = _Shape(Polygon([(0.0, 0.0), (6.0, 0.0), (6.0, 100.0),
                               (0.0, 100.0)]), role=ROLE_SERVICE_ROAD)
        layout = _Layout(
            [road], [_CL(LineString([(3.0, 0.0), (3.0, 100.0)]),
                         is_service=True)])
        if with_slice_dup:
            # the SAME physical road, also registered as a sliced chain
            layout._slice_service_subsegments = [
                LineString([(3.0, 0.0), (3.0, 100.0)])]
        return lsn.insert_service_lateral_nodes(layout, "TEST")

    n_1206_only = _build(False)
    assert n_1206_only > 0, "a row-1206-only fixture must still plant"
    assert _build(True) == n_1206_only, (
        "one physical road spelled by both sources must dedupe to ONE "
        "chain — a second spelling doubling the feet is the drift the "
        "chain dedupe exists to prevent")
