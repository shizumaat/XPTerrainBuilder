"""THE APRON WITHIN-SHAPE POPULATION — the movement surfaces at the STRICT
cap, the interior at the FAN-RAMP cap (owner rulings ``docs/RULINGS.md``
2026-08-21b answer "ii" and 2026-08-21c; spec
``docs/specs/apron-within-shape-population-spec.md`` + AMENDMENT A1).

AMENDED 2026-08-21c: the interior is NOT removed from the law.  Every apron
pair stays in the domain; what the movement-surface predicate now decides is
the pair's CAP — strict for a frontage chord and for the ring-adjacent
branch, ``APRON_INTERIOR_CAP`` (5 %) for the interior.  The removal half of
2026-08-21b was measured on lane/compose and REVERSED: with the interior
unpriced the transect rows moved the rings by metres and the frontage chords
absorbed it (SPJC 189 -> 551 airside).

The five twins the spec pre-registers (§8), all on ONE synthetic airport:
an apron, TWO building pads on its back edge, and ONE taxi corridor
running through it.

  (a) a generic apron pair is KEPT AT 5 % and a frontage chord is kept at
      the STRICT cap, and P1 (both endpoints frontage vertices of one pad)
      takes the pre-existing ring-adjacent branch — its verdict is identical
      with the rule on and off;
  (b) the CENSUS (``check_grade.iter_shape_grade_constraints``, reading
      an emitted ring by node id) and the BAKE
      (``grade_graph.shape_constraints`` under the solver's context)
      enumerate the IDENTICAL apron pair set AND THE IDENTICAL CAP PER
      PAIR — the lockstep the ruling requires ("ONE predicate, both
      readers");
  (c) junction / runway / building within-shape pair sets are BYTE-
      IDENTICAL to the rule-off arm (ruling clause 4);
  (d) the sidecar's ``pair_caps`` FAMILY TAG round-trips, and a legacy
      three-element row still reads exactly as before;
  (e) an apron with NO building frontage is FULLY POPULATED at the 5 %
      interior cap (A1 §5a: the interior law IS the interior's constraint,
      superseding §5's "carrier keeps the smoothing").

Everything here is headless: synthetic rings, no DEM, no X-Plane data,
no network.
"""
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from shapely.geometry import LineString, Polygon

from auto_patch import grade_graph as GG
from auto_patch import grade_law as GL
from auto_patch import verification as V
from auto_patch.apt_dat_reader import TaxiCenterline
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.config import BUILDING_REACH_CORRIDOR_M
from auto_patch.layout import BuiltShape, PavementLayout

import check_grade as cg


# ── THE SYNTHETIC AIRPORT ────────────────────────────────────────────
# One corridor along y = 0.  The apron straddles it, so the apron RING
# carries two vertices ON the spine — (-100, 0) and (300, 0) — which is
# where a frontage chord lands.  Two pads sit on the back edge (y = 120),
# each sharing a whole EDGE with the apron ring (the production frontage
# predicate: ``anchors._frontage_box``, both endpoints shared).
SPINE = [(-200.0, 0.0), (400.0, 0.0)]

#: open apron ring, CCW from the bottom-left corner.
APRON_RING = [
    (-100.0, -40.0),      # 0  generic
    (300.0, -40.0),       # 1  generic
    (300.0, 0.0),         # 2  ON THE SPINE (in the corridor cover)
    (300.0, 120.0),       # 3  generic
    (240.0, 120.0),       # 4  pad2 frontage
    (200.0, 120.0),       # 5  pad2 frontage
    (60.0, 120.0),        # 6  pad1 frontage
    (20.0, 120.0),        # 7  pad1 frontage
    (-100.0, 120.0),      # 8  generic
    (-100.0, 0.0),        # 9  ON THE SPINE (in the corridor cover)
]
PAD1 = [(20.0, 120.0), (60.0, 120.0), (60.0, 160.0), (20.0, 160.0)]
PAD2 = [(200.0, 120.0), (240.0, 120.0), (240.0, 160.0), (200.0, 160.0)]

FRONTAGE_XY = {(20.0, 120.0), (60.0, 120.0),
               (200.0, 120.0), (240.0, 120.0)}
SPINE_XY = {(300.0, 0.0), (-100.0, 0.0)}

#: the anchor + metre↔lat/lon pair BOTH readers use, so the census's
#: emitted-node frame is the layout's own frame.
#: OFF the integer graticule on purpose — a node at an integer
#: lat/lon is a TILE SEAM pin and the law exempts along-seam pairs.
ANCHOR = (30.5, 31.5)
_MPD_LAT = 111320.0
_MPD_LON = 96000.0


def _m_to_ll(x, y):
    return (ANCHOR[0] + y / _MPD_LAT, ANCHOR[1] + x / _MPD_LON)


def _ll_to_m(lat, lon):
    return ((lon - ANCHOR[1]) * _MPD_LON, (lat - ANCHOR[0]) * _MPD_LAT)


def _closed(ring):
    return list(ring) + [ring[0]]


def _layout(with_pads=True, apron_ring=None, extra_shapes=()):
    """The synthetic layout the SOLVER's ``build_context`` reads."""
    lay = PavementLayout(icao="ZZZZ", anchor=ANCHOR)
    lay.shapes.append(BuiltShape(
        polygon=Polygon(_closed(apron_ring or APRON_RING)),
        role="apron", ref="apron1"))
    if with_pads:
        lay.shapes.append(BuiltShape(polygon=Polygon(_closed(PAD1)),
                                     role="building", ref="pad1"))
        lay.shapes.append(BuiltShape(polygon=Polygon(_closed(PAD2)),
                                     role="building", ref="pad2"))
    lay.shapes.extend(extra_shapes)
    lay.apt_taxi_centerlines = [
        TaxiCenterline(line=LineString(SPINE), seg_sizes=["C"])]
    return lay


def _solver_ctx(lay):
    return GG.build_context(lay)


def _apron_shape(lay, apron_ring=None):
    """The apron as the solver builds it — keys are the ring COORDINATES
    (``build_context(layout)`` with no ``bucket_to_idx`` keys buildings by
    rounded coordinate, and this is that same space)."""
    ring = list(apron_ring or APRON_RING)
    return GG.GradeShape(role="apron", ring=ring,
                         keys=[(round(x, 3), round(y, 3)) for (x, y) in ring])


def _pairs_xy(sc, shape):
    """``{frozenset((xa, ya), (xb, yb))}`` — the pair SET, frame-neutral."""
    by_key = {k: p for k, p in zip(shape.keys, shape.ring)}
    return {frozenset((by_key[a], by_key[b])) for (a, b, _c) in sc.edges}


def _caps_xy(sc, shape):
    """``{frozenset(pair): cap}`` — the pair set WITH the cap that priced
    each one.  Under RULINGS 2026-08-21c the cap IS the law's answer, so
    every twin below asserts on this rather than on membership alone."""
    by_key = {k: p for k, p in zip(shape.keys, shape.ring)}
    return {frozenset((by_key[a], by_key[b])): c.flat_cap()
            for (a, b, c) in sc.edges}


def _edges_xy(lay, apron_ring=None):
    gs = _apron_shape(lay, apron_ring)
    return _pairs_xy(GG.shape_constraints(gs, _solver_ctx(lay)), gs)


def _edge_caps_xy(lay, apron_ring=None):
    gs = _apron_shape(lay, apron_ring)
    return _caps_xy(GG.shape_constraints(gs, _solver_ctx(lay)), gs)


@pytest.fixture
def rule_off(monkeypatch):
    """The kill switch ``O4_APRON_INTERIOR_RAMP_CAP=0`` — every apron pair
    at the STRICT body cap, i.e. the 2026-08-21 battery.  (The flag was
    renamed from ``O4_APRON_WITHIN_SHAPE_FRONTAGE_ONLY`` with 2026-08-21c:
    nothing is dropped any more, only the interior CAP changes.)  The
    module constant is read at import, so the twin drives THAT (the same
    shape every other gate in this engine is tested through)."""
    monkeypatch.setattr(GL, "APRON_INTERIOR_RAMP_CAP", False)


# ── (a) generic skipped, frontage chord kept, P1 unchanged ───────────

def _caps_rule_off(lay, apron_ring=None):
    """The same pair set priced with the rule OFF — i.e. today's
    all-strict behaviour, the 2026-08-21 battery.  Every twin below states
    the law as a DELTA against this arm, because "the strict cap" is
    whatever the existing chain (spine / blend / body) already returned:
    A1 raises exactly one class and touches nothing else."""
    saved = GL.APRON_INTERIOR_RAMP_CAP
    try:
        GL.APRON_INTERIOR_RAMP_CAP = False
        return _edge_caps_xy(lay, apron_ring)
    finally:
        GL.APRON_INTERIOR_RAMP_CAP = saved


def test_the_domain_is_unchanged_only_the_interior_cap_moves():
    """A1 §2a: both readers enumerate the same pair set as today's bake
    MINUS NOTHING; only the CAP changes, and only on the interior class,
    and only upward ("relax only")."""
    lay = _layout()
    on, off = _edge_caps_xy(lay), _caps_rule_off(lay)
    assert set(on) == set(off), (
        f"the DOMAIN moved: on-only {sorted(set(on) - set(off))} / "
        f"off-only {sorted(set(off) - set(on))}")
    assert on, "the fixture must produce pairs"
    raised = {k for k in on if on[k] != off[k]}
    assert raised, "no interior pair was raised — the amendment is inert"
    for k in on:
        assert on[k] >= off[k] - 1e-12, f"{k} was TIGHTENED, not relaxed"
    # every raised pair landed exactly on the ramp cap, and every raised
    # pair is one the law calls interior.
    for k in raised:
        assert abs(on[k] - GL.APRON_INTERIOR_CAP) < 1e-9
        assert off[k] < GL.APRON_INTERIOR_CAP


def test_frontage_chord_keeps_the_strict_cap_interior_takes_the_ramp_cap():
    """The movement surface is priced as it was; the interior is not."""
    lay = _layout()
    on, off = _edge_caps_xy(lay), _caps_rule_off(lay)
    for pad_xy, spine_xy in (((20.0, 120.0), (-100.0, 0.0)),
                             ((200.0, 120.0), (300.0, 0.0)),
                             ((240.0, 120.0), (300.0, 0.0))):
        assert math.dist(pad_xy, spine_xy) <= BUILDING_REACH_CORRIDOR_M
        pair = frozenset((pad_xy, spine_xy))
        assert pair in on, f"frontage chord {pad_xy}->{spine_xy} was dropped"
        assert on[pair] == off[pair], (
            f"frontage chord re-priced {off[pair]} -> {on[pair]}")
        assert on[pair] < GL.APRON_INTERIOR_CAP, (
            "a frontage chord must stay STRICTER than the interior")
    # the back edge is interior: neither endpoint fronts a pad here.
    back = frozenset(((300.0, 120.0), (-100.0, 120.0)))
    if back in on:                      # (subject to the 60 m body gate)
        assert abs(on[back] - GL.APRON_INTERIOR_CAP) < 1e-9


def test_the_ring_adjacent_branch_is_not_raised():
    """A1 §1a: the ring-adjacent branch keeps its behaviour — a ring edge
    is a physical stretch of pavement, and R19-5 exists to catch the
    148 %-class edge it would otherwise leave unpriced.  Reported count is
    asserted to be non-zero so the branch cannot silently empty."""
    lay = _layout()
    on, off = _edge_caps_xy(lay), _caps_rule_off(lay)
    ring_adj = [frozenset((APRON_RING[i], APRON_RING[(i + 1) % len(APRON_RING)]))
                for i in range(len(APRON_RING))]
    present = [k for k in ring_adj if k in on]
    assert present, "no ring edge survived — R19-5's own class is empty"
    for k in present:
        assert on[k] == off[k], f"ring edge {k} was re-priced to {on[k]}"


def test_the_cap_verdicts_are_the_ones_the_amendment_names():
    """A1's own acceptance sentence: a generic pair at 3 % PASSES and at
    6 % FAILS; a frontage chord at 3 % FAILS.  Both pairs are inside the
    60 m body gate so the gate is not what decides them."""
    base = dict(role="apron", dist=50.0, ring_adjacent=False,
                a_seam=False, b_seam=False, a_building=False,
                b_building=False, spine_caps=(), body_cap=GL.APRON_MAX_GRADE)
    generic = GL.classify_pair(GL.PairContext(
        **base, a_frontage=False, b_corridor=False))
    chord = GL.classify_pair(GL.PairContext(
        **{**base, "dist": 20.0}, a_frontage=True, b_corridor=True))
    assert generic is not None, "the interior pair must stay in the law"
    assert chord is not None
    g_cap, c_cap = generic.flat_cap(), chord.flat_cap()
    assert g_cap >= 0.03, "a generic interior pair at 3 % must PASS"
    assert g_cap < 0.06, "a generic interior pair at 6 % must FAIL"
    assert c_cap < 0.03, "a frontage chord at 3 % must FAIL"


def test_the_sixty_metre_body_gate_still_removes_long_interior_chords():
    """A1 §1a keeps ``APRON_BODY_CHORD_MAX_M``: a 680 m chord at 5 % is
    still 34 m of fall, so the gate that predates this ruling still runs."""
    long_pair = dict(role="apron", dist=200.0, ring_adjacent=False,
                     a_seam=False, b_seam=False, a_building=False,
                     b_building=False, spine_caps=(),
                     body_cap=GL.APRON_MAX_GRADE,
                     a_frontage=False, b_corridor=False)
    assert math.isfinite(GL.APRON_BODY_CHORD_MAX_M)
    assert 200.0 > GL.APRON_BODY_CHORD_MAX_M
    assert GL.classify_pair(GL.PairContext(**long_pair)) is GL.SKIP


def test_over_reach_frontage_chord_is_interior_not_dropped():
    """Beyond ``BUILDING_REACH_CORRIDOR_M`` the seat does not reach the
    spine, so the pair is not a MOVEMENT SURFACE — but under A1 it is
    still law, at the interior cap, rather than dropped (when the 60 m
    body gate lets it through)."""
    far_ctx = GL.PairContext(
        role="apron", dist=BUILDING_REACH_CORRIDOR_M + 5.0,
        ring_adjacent=False, a_seam=False, b_seam=False,
        a_building=False, b_building=False, spine_caps=(),
        body_cap=GL.APRON_MAX_GRADE, a_frontage=True, b_corridor=True)
    assert not GL.is_frontage_chord(far_ctx)
    if far_ctx.dist <= GL.APRON_BODY_CHORD_MAX_M:
        got = GL.classify_pair(far_ctx)
        assert got is not None
        assert abs(got.flat_cap() - GL.APRON_INTERIOR_CAP) < 1e-9


def test_p1_takes_the_existing_ring_adjacent_branch():
    """P1 — both endpoints frontage vertices of ONE pad — keeps exactly
    the verdict it has today (the inter-pad ``a_building and b_building``
    skip, which sits BEFORE the apron rule).  Reported count: 0 rows."""
    p1 = GL.PairContext(
        role="apron", dist=40.0, ring_adjacent=True,
        a_seam=False, b_seam=False, a_building=True, b_building=True,
        spine_caps=(), body_cap=0.01,
        a_frontage=True, b_frontage=True)
    with_rule = GL.classify_pair(p1)
    saved = GL.APRON_INTERIOR_RAMP_CAP
    try:
        GL.APRON_INTERIOR_RAMP_CAP = False
        without_rule = GL.classify_pair(p1)
    finally:
        GL.APRON_INTERIOR_RAMP_CAP = saved
    assert with_rule == without_rule
    # And the P1 pair is not in the emitted population at all.
    assert frozenset(((20.0, 120.0), (60.0, 120.0))) not in _edges_xy(_layout())


def test_the_predicate_lives_only_in_classify_pair():
    """``is_frontage_chord`` decides from the PairContext alone — the
    readers only supply per-vertex membership (spec §1)."""
    base = dict(role="apron", dist=100.0, ring_adjacent=False,
                a_seam=False, b_seam=False, a_building=True,
                b_building=False, spine_caps=(), body_cap=0.01)
    assert GL.is_frontage_chord(GL.PairContext(
        **base, a_frontage=True, b_corridor=True))
    assert GL.is_frontage_chord(GL.PairContext(
        **{**base, "a_building": False, "b_building": True},
        b_frontage=True, a_corridor=True))
    # far endpoint off the corridor ⇒ not a movement surface
    assert not GL.is_frontage_chord(GL.PairContext(**base, a_frontage=True))
    # neither endpoint a frontage vertex ⇒ generic
    assert not GL.is_frontage_chord(GL.PairContext(
        **base, a_corridor=True, b_corridor=True))
    # beyond the reach
    assert not GL.is_frontage_chord(GL.PairContext(
        **{**base, "dist": BUILDING_REACH_CORRIDOR_M + 1.0},
        a_frontage=True, b_corridor=True))


def test_rule_off_restores_the_all_pair_population(rule_off):
    kept = _edges_xy(_layout())
    assert frozenset(((-100.0, -40.0), (300.0, -40.0))) in kept
    assert len(kept) > 20


# ── (b) census and bake enumerate the same apron pair set ────────────

def _osm_ways_nodes(with_pads=True, apron_ring=None):
    """The same airport as an EMITTED patch: ``check_grade.Way`` rings on
    shared node ids (the identity join a real weld produces)."""
    nodes = {}
    nid_of = {}

    def _nid(x, y):
        k = (round(x, 3), round(y, 3))
        if k not in nid_of:
            nid_of[k] = f"-{len(nid_of) + 1}"
            nodes[nid_of[k]] = _m_to_ll(x, y)
        return nid_of[k]

    ways = []

    def _way(wid, role, ring):
        nids = [_nid(x, y) for (x, y) in ring]
        nids.append(nids[0])
        ways.append(cg.Way(wid=wid, role=role, ref=wid, aeroway="",
                           nids=nids, elevs=[100.0] * len(nids),
                           tags={"role": role}))

    _way("-900", "apron", apron_ring or APRON_RING)
    if with_pads:
        _way("-901", "building", PAD1)
        _way("-902", "building", PAD2)
    return ways, nodes, nid_of


def _census_caps_xy(with_pads=True, apron_ring=None):
    """``{frozenset(pair): cap}`` from the CENSUS reader."""
    ways, nodes, nid_of = _osm_ways_nodes(with_pads, apron_ring)
    xy_of = {nid: xy for xy, nid in nid_of.items()}
    axes = [(list(SPINE), 0.015, 0.015, -1, False)]
    out = {}
    for c in cg.iter_shape_grade_constraints(
            ways, nodes, _ll_to_m, 0.015, taxi_axes=axes):
        if c.way.tags.get("role") != "apron":
            continue
        out[frozenset((xy_of[c.nid_a], xy_of[c.nid_b]))] = c.cap
    return out


def _census_pairs_xy(with_pads=True, apron_ring=None):
    return set(_census_caps_xy(with_pads, apron_ring))


def test_census_and_bake_enumerate_the_same_apron_pairs():
    """THE LOCKSTEP (spec §2 / §8(b)).  A mismatch here is a STOP: the
    fix is the predicate, never the count."""
    bake = _edges_xy(_layout())
    census = _census_pairs_xy()
    assert census == bake, (
        f"census-only {sorted(census - bake)} / bake-only {sorted(bake - census)}")
    assert bake, "the fixture must produce at least one frontage chord"


def test_census_and_bake_agree_on_the_CAP_of_every_apron_pair():
    """THE LOCKSTEP EXTENDED TO THE CAP (RULINGS 2026-08-21c / A1 §2a).
    With two caps in play, agreeing on the pair SET is no longer enough:
    a census that priced an interior pair at the strict cap while the bake
    built it at 5 % would mint a whole class of phantom rows and the pair
    sets would still match.  Both readers call ``classify_pair``, so this
    is an identity — and it is the twin that keeps it one."""
    lay = _layout()

    def _drift():
        bake, census = _edge_caps_xy(lay), _census_caps_xy()
        assert set(census) == set(bake)
        return ({k: (bake[k], census[k]) for k in bake
                 if abs(bake[k] - census[k]) > 1e-9}, bake)

    on_drift, bake = _drift()
    saved = GL.APRON_INTERIOR_RAMP_CAP
    try:
        GL.APRON_INTERIOR_RAMP_CAP = False
        off_drift, _ = _drift()
    finally:
        GL.APRON_INTERIOR_RAMP_CAP = saved

    # THIS RULING INTRODUCES NO CAP DRIFT.  The comparison is on-vs-off, not
    # against zero, because ONE drifting pair PRE-DATES it: the bottom ring
    # edge reads the BLEND branch's 0.015 in the bake and the plain body cap
    # in the census, identically with the flag on and off.  That is the
    # blend-credit reader gap (docketed, not this lane's to fix); asserting
    # "no new drift" keeps the guard live for anything A1 might add without
    # silently adopting a defect it did not cause.
    assert set(on_drift) == set(off_drift), (
        f"NEW cap drift introduced by the interior rule: "
        f"{ {k: on_drift[k] for k in set(on_drift) - set(off_drift)} }")
    for k in on_drift:
        assert on_drift[k] == off_drift[k], (
            f"the interior rule CHANGED a pre-existing drift at {k}: "
            f"{off_drift[k]} -> {on_drift[k]}")
    # and both caps really are exercised on this fixture
    assert any(abs(c - GL.APRON_INTERIOR_CAP) < 1e-9 for c in bake.values())
    assert any(c < GL.APRON_INTERIOR_CAP for c in bake.values())


def test_census_and_bake_agree_with_the_rule_off_too(rule_off):
    assert _census_pairs_xy() == _edges_xy(_layout())


# ── (c) junction / runway / building are UNCHANGED ───────────────────

def test_junction_and_plane_pair_sets_are_byte_identical(monkeypatch):
    """Ruling clause 4: only the APRON population changes."""
    lay = _layout()
    ctx = _solver_ctx(lay)
    ring = list(APRON_RING)
    keys = [(round(x, 3), round(y, 3)) for (x, y) in ring]

    def _sets():
        jn = GG.shape_constraints(
            GG.GradeShape(role="junction", ring=ring, keys=keys), ctx)
        rw = GG.plane_constraints(
            GG.GradeShape(role="runway", ring=ring, keys=keys), ctx, 0.015)
        return ({(a, b) for (a, b, _c) in jn.edges},
                {(a, b) for (a, b, _c) in rw.edges})

    on = _sets()
    monkeypatch.setattr(GL, "APRON_INTERIOR_RAMP_CAP", False)
    ctx = _solver_ctx(_layout())
    off = _sets()
    assert on == off
    assert on[0] and on[1]


def test_building_pair_verdicts_are_unchanged():
    """A building↔building pair is the inter-pad step in BOTH arms."""
    p = GL.PairContext(role="building", dist=40.0, ring_adjacent=True,
                       a_seam=False, b_seam=False,
                       a_building=True, b_building=True,
                       spine_caps=(), body_cap=0.01)
    saved = GL.APRON_INTERIOR_RAMP_CAP
    try:
        GL.APRON_INTERIOR_RAMP_CAP = False
        off = GL.classify_pair(p)
    finally:
        GL.APRON_INTERIOR_RAMP_CAP = saved
    assert GL.classify_pair(p) == off


# ── (d) the sidecar family tag round-trips ───────────────────────────

class _BakeLayout:
    """The minimum surface ``verification.lockstep_pair_caps_ll`` reads."""

    def __init__(self, ring, baked_edges, spine, role="apron"):
        self.canonical_points = CanonicalPointRegistry()
        for (x, y) in ring:
            self.canonical_points.get_or_add(x, y)
        signature = tuple((round(x, 6), round(y, 6)) for (x, y) in ring)
        self._lockstep_shape_bake = {
            1: (role, signature, baked_edges, spine)}

    def m_to_ll(self, x, y):
        return _m_to_ll(x, y)


def test_pair_caps_rows_carry_the_edge_family():
    flat = GL.Allowance.flat(0.01)
    lay = _BakeLayout(APRON_RING, [(7, 9, flat), (2, 3, flat)], {(2, 3)})
    rows = V.lockstep_pair_caps_ll(lay)
    assert rows and all(len(r) == 4 for r in rows)
    fams = sorted(r[3] for r in rows)
    assert fams == ["unified:apron", "unified:apron:spine"]
    # ONE speller, shared with the certificate's ``edge_family``.
    assert GG.edge_family_name("apron", False) == "unified:apron"
    assert GG.edge_family_name("apron", True) == "unified:apron:spine"


def test_legacy_three_element_pair_caps_rows_still_read():
    """A patch built before 2026-08-21 has no family tag; every reader
    takes the row POSITIONALLY, so it is consumed exactly as before."""
    ways, nodes, nid_of = _osm_ways_nodes()
    a = nid_of[(20.0, 120.0)]
    b = nid_of[(-100.0, 0.0)]
    row3 = [list(nodes[a]), list(nodes[b]), 1.7]
    row4 = row3 + ["unified:apron"]
    axes = [(list(SPINE), 0.015, 0.015, -1, False)]

    def _run(rows):
        return {(c.nid_a, c.nid_b, round(c.allowance, 9))
                for c in cg.iter_shape_grade_constraints(
                    ways, nodes, _ll_to_m, 0.015, taxi_axes=axes,
                    pair_caps_ll=[rows])
                if c.way.tags.get("role") == "apron"}

    assert _run(row3) == _run(row4)
    assert _run(row3)

    from auto_patch.emit_snap import snap_pairs_from_axes_ll
    ll = {nid: nodes[nid] for nid in (a, b)}
    assert (snap_pairs_from_axes_ll([row3], ll, None)
            == snap_pairs_from_axes_ll([row4], ll, None))


# ── (e) a zero-building apron is FULLY POPULATED at the interior cap ──

def test_zero_building_apron_is_fully_populated_at_the_interior_cap():
    """AMENDED by RULINGS 2026-08-21c (A1 §5a).  Spec §8(e) used to require
    ZERO law edges here and to lean on the warm-start carrier for the
    smoothing.  The owner reversed that: an apron with no frontage at all
    is entirely interior, so it is entirely law at ``APRON_INTERIOR_CAP``.
    The measured reason is on this lane — an unpriced apron interior let
    the transect rows move the rings by metres (SPJC 189 -> 551 airside)."""
    lay = _layout(with_pads=False)
    caps = _edge_caps_xy(lay)
    off = _caps_rule_off(lay, None)
    assert caps, "a pad-less apron must still carry its interior law"
    # The DOMAIN is identical to the strict arm — nothing is dropped.
    assert set(caps) == set(off)
    # Every pair that is NOT a ring edge (nor spine/blend-credited above the
    # ramp cap) is interior and takes the ramp cap; the ring-adjacent branch
    # keeps its own, which is what A1 section 1a reserves for it.
    raised = {k for k in caps if caps[k] != off[k]}
    assert raised, "a frontage-less apron must have an interior class"
    assert all(abs(caps[k] - GL.APRON_INTERIOR_CAP) < 1e-9 for k in raised)
    assert all(caps[k] == off[k] for k in set(caps) - raised)
    # THE LOCKSTEP HOLDS ON THIS FIXTURE TOO (spec §8(b)).
    assert _census_pairs_xy(with_pads=False) == set(caps)
    # The shape still registers its spine chain — the global spine, the
    # reach band and the carrier all keep their connectivity.
    gs = _apron_shape(lay)
    sc = GG.shape_constraints(gs, _solver_ctx(lay))
    assert sc.edges
    assert sc.spine_chains == GG.shape_constraints(
        gs, _solver_ctx(lay)).spine_chains


def test_zero_building_apron_is_the_same_population_with_the_rule_off(rule_off):
    """The DOMAIN is the fixture's, the CAP is the rule's: with the kill
    switch off the same pad-less apron carries the same pairs, priced
    strictly instead (the remaining skips are the pre-existing body-chord
    and spine-crossing ones)."""
    off = _edge_caps_xy(_layout(with_pads=False))
    assert len(off) >= 10
    assert all(c < GL.APRON_INTERIOR_CAP for c in off.values())


# ── the READ instrument (tools/frontage_split --apron-population) ────

_POP_OSM = """<?xml version='1.0' encoding='UTF-8'?>
<osm version='0.6' generator='apronpop-twin'>
%(nodes)s
%(ways)s
</osm>
"""


def _pop_fixture(tmp_path):
    """A one-apron / one-pad / one-corridor patch with a STEEP frontage
    chord and a STEEP generic chord — so the census emits one of each and
    the read has something to partition."""
    ring = [(-100.0, -40.0), (300.0, -40.0), (300.0, 0.0), (300.0, 120.0),
            (60.0, 120.0), (20.0, 120.0), (-100.0, 120.0), (-100.0, 0.0)]
    #    the SPINE node (-100, 0) is 3 m below the pad-shared node
    #    (20, 120): a 169.7 m frontage chord at 1.77 % (apron cap 1 %).
    alt = {(-100.0, 0.0): 97.0, (20.0, 120.0): 100.0}
    nid, nodes_xml, nid_of = 0, [], {}
    for (x, y) in ring + PAD1[2:]:
        nid -= 1
        lat, lon = _m_to_ll(x, y)
        nid_of[(x, y)] = str(nid)
        nodes_xml.append(
            f"  <node id='{nid}' lat='{lat:.11f}' lon='{lon:.11f}'>"
            f"<tag k='alt_abs' v='{alt.get((x, y), 100.0):.2f}' /></node>")

    def _way(wid, role, pts):
        refs = "".join(f"<nd ref='{nid_of[p]}' />" for p in pts)
        return (f"  <way id='{wid}'>{refs}<nd ref='{nid_of[pts[0]]}' />"
                f"<tag k='role' v='{role}' />"
                f"<tag k='shapeID' v='{wid}' /></way>")

    ways_xml = [_way("-10", "apron", ring),
                _way("-11", "building", PAD1)]
    osm = tmp_path / "apronpop.osm"
    osm.write_text(_POP_OSM % {"nodes": "\n".join(nodes_xml),
                               "ways": "\n".join(ways_xml)})
    (tmp_path / "apronpop.osm.axes.json").write_text(__import__("json").dumps({
        "anchor": list(ANCHOR),
        "axes": [[[list(_m_to_ll(*p)) for p in SPINE], 0.015, 0.015, -1]],
    }))
    return osm


def test_the_read_partitions_the_population_through_the_law_itself(tmp_path):
    """The ``--apron-population`` axis is a READ, not a second law: its
    verdict IS ``grade_law.is_frontage_chord`` and its partition is
    exhaustive (rows == P1 + CHORD + GENERIC)."""
    import frontage_split as FS
    rep = FS.apron_population(_pop_fixture(tmp_path))
    ap = rep["per_role"].get("apron")
    assert ap is not None, rep
    assert ap["rows"] == ap["P1"] + ap["chord"] + ap["generic"]
    assert ap["chord"] >= 1, ap
    assert rep["corridor_cover_radius_m"] == pytest.approx(13.5)
    assert rep["frontage_vertices"] == 2


# ── the corridor cover is the EXISTING constant pair ─────────────────

def test_corridor_cover_radius_is_the_existing_terrace_constants():
    from auto_patch.config import (APRON_TERRACE_CORRIDOR_HALF_WIDTH_M,
                                   APRON_TERRACE_JOINT_CLEARANCE_M)
    from auto_patch.elevation_per_surface.route_profile import apron_terrace
    assert apron_terrace.corridor_cover_radius_m() == pytest.approx(
        APRON_TERRACE_CORRIDOR_HALF_WIDTH_M + APRON_TERRACE_JOINT_CLEARANCE_M)
    # and the SPINE cover carries the spines ALONE — never the pads (a
    # cover containing them would make every building pair "in the
    # corridor", which is not the ruled population).
    cover = apron_terrace.spine_corridor_cover([LineString(SPINE)])
    from shapely.geometry import Point
    assert cover.contains(Point(0.0, 0.0))
    assert not cover.contains(Point(40.0, 140.0))
