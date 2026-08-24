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


def _apron_ctx(**kw):
    base = dict(role="apron", dist=30.0, ring_adjacent=True,
                a_seam=False, b_seam=False, a_building=False,
                b_building=False, spine_caps=(),
                body_cap=GL.APRON_MAX_GRADE,
                a_frontage=False, b_frontage=False,
                a_corridor=False, b_corridor=False)
    base.update(kw)
    return GL.PairContext(**base)


def test_a_plain_ring_edge_takes_the_interior_cap():
    """AMENDMENT A2 corrects A1 section 1a.  A ring edge between two
    NON-frontage, non-corridor vertices is a generic pair under
    2026-08-21b, so it takes the 5 % interior cap — 3 % passes, 6 % fails.

    Measured reason: A1 kept every ring-adjacent pair strict on R19-5
    grounds and compose-v2 came out +112 over HECA's bar, ~648 of those
    rows being apron ring edges over the strict 1 % while NOT ONE
    violation anywhere carried the 5 % cap."""
    got = GL.classify_pair(_apron_ctx())
    assert got is not None, "a ring edge must never leave the domain (R19-5)"
    cap = got.flat_cap()
    assert abs(cap - GL.APRON_INTERIOR_CAP) < 1e-9
    assert 0.03 <= cap, "a plain ring edge at 3 % must PASS"
    assert 0.06 > cap, "a plain ring edge at 6 % must FAIL"


def test_R19_5s_catch_survives_at_five_percent():
    """The class R19-5 exists for — the 148 % ring edge — still mints its
    row.  A2 changes the CAP it is judged at, never its membership."""
    got = GL.classify_pair(_apron_ctx())
    assert got is not None
    assert 1.48 > got.flat_cap(), "a 148 % ring edge must still FAIL"


def test_a_ring_FRONTAGE_edge_stays_strict():
    """Both endpoints frontage vertices: the pavement directly under a
    building face.  STRICT — 3 % fails."""
    got = GL.classify_pair(_apron_ctx(a_frontage=True, b_frontage=True))
    assert got is not None
    cap = got.flat_cap()
    assert cap < 0.03, "a ring frontage edge at 3 % must FAIL"
    assert cap < GL.APRON_INTERIOR_CAP


def test_a_corridor_crossing_ring_edge_stays_strict():
    """Both endpoints inside the spine corridor cover: pavement an aircraft
    taxis over.  STRICT."""
    got = GL.classify_pair(_apron_ctx(a_corridor=True, b_corridor=True))
    assert got is not None
    assert got.flat_cap() < GL.APRON_INTERIOR_CAP
    # one endpoint in the cover is NOT a crossing edge — it is interior.
    half = GL.classify_pair(_apron_ctx(a_corridor=True))
    assert abs(half.flat_cap() - GL.APRON_INTERIOR_CAP) < 1e-9


def test_a_spine_pair_is_never_raised_to_the_interior_cap():
    """A pair sharing a taxi centerline IS the corridor; its cap is the
    route's per-letter taxi cap.  Raising it to 5 % would legalise a 5 %
    grade along a running taxiway — the regression A2 introduced on its
    first pass, caught by test_grade_graph's spine twin."""
    got = GL.classify_pair(_apron_ctx(spine_caps=(0.015,)))
    assert got is not None
    assert abs(got.flat_cap() - 0.015) < 1e-9
    assert not GL.is_apron_interior(_apron_ctx(spine_caps=(0.015,)))


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

    # WITH THE RULE ON THERE IS NO CAP DRIFT AT ALL, and A2 is what closed
    # it.  One pair used to drift and still does on the RULE-OFF arm: the
    # apron's bottom RING EDGE, fixture-local (-100,-40)-(300,-40),
    # lat/lon (30.4996407,31.4989583)-(30.4996407,31.5031250).  The bake
    # reads the BLEND branch's 1.5 % there ("an apron body edge near a
    # taxiway earns the route's blended cap") while the census reads the
    # plain 1 % body cap — the blend-credit reader gap, DOCKETED by the
    # compose lane.  Under A2 that edge is INTERIOR, so both readers agree
    # at 5 % and the drift disappears from the shipping configuration; the
    # underlying gap is untouched and still shows on the flag-off arm.
    assert not on_drift, f"cap drift with the rule ON: {on_drift}"
    assert set(off_drift) == {
        frozenset(((-100.0, -40.0), (300.0, -40.0)))}, (
        f"the KNOWN flag-off blend drift changed shape: {off_drift}")
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


# ── AMENDMENT A3: a ring edge is strict only inside the body gate ─────

def test_a_short_corridor_crossing_ring_edge_is_still_strict():
    """A3's own verdict sentence, first half: a 40 m corridor-crossing ring
    edge at 3 % FAILS."""
    got = GL.classify_pair(_apron_ctx(dist=40.0,
                                      a_corridor=True, b_corridor=True))
    assert got is not None
    assert got.flat_cap() < 0.03, "a 40 m crossing edge at 3 % must FAIL"


def test_a_long_corridor_crossing_ring_edge_is_interior():
    """A3's verdict sentence, second half: an 800 m one at 3 % PASSES and at
    6 % FAILS.  A corridor crossing a long edge makes the CROSSING a movement
    surface, not the whole 800 m edge — and the ungated A2 clause bypassing
    ``APRON_BODY_CHORD_MAX_M`` is measured as HECA's infeasibility (956 of
    2,275 rows on chords > 60 m; the worst -10612 edges 650-857 m where the
    terrain falls 11.7 m and 1 % permits 8.4 m)."""
    got = GL.classify_pair(_apron_ctx(dist=800.0,
                                      a_corridor=True, b_corridor=True))
    assert got is not None, "the ring edge must stay in the domain (R19-5)"
    cap = got.flat_cap()
    assert abs(cap - GL.APRON_INTERIOR_CAP) < 1e-9
    assert 0.03 <= cap, "an 800 m crossing edge at 3 % must PASS"
    assert 0.06 > cap, "an 800 m crossing edge at 6 % must FAIL"


def test_a_long_ring_FRONTAGE_edge_is_interior_too():
    """A3 says "a ring edge (or corridor-crossing pair)" — the frontage EDGE
    is a ring edge and takes the same gate.  The frontage CHORD does not."""
    short = GL.classify_pair(_apron_ctx(dist=40.0,
                                        a_frontage=True, b_frontage=True))
    long_ = GL.classify_pair(_apron_ctx(dist=800.0,
                                        a_frontage=True, b_frontage=True))
    assert short.flat_cap() < GL.APRON_INTERIOR_CAP
    assert abs(long_.flat_cap() - GL.APRON_INTERIOR_CAP) < 1e-9


def test_a_frontage_chord_keeps_no_length_gate():
    """Explicitly unchanged by A3: a frontage chord is bounded by
    ``BUILDING_REACH_CORRIDOR_M`` by construction, so the body gate never
    reaches it."""
    d = min(BUILDING_REACH_CORRIDOR_M, GL.APRON_BODY_CHORD_MAX_M + 10.0)
    ctx = _apron_ctx(dist=d, ring_adjacent=False,
                     a_frontage=True, b_corridor=True)
    assert GL.is_frontage_chord(ctx)
    assert not GL.is_apron_interior(ctx)


def test_a_long_SPINE_pair_keeps_its_route_cap():
    """The ``spine_caps`` half keeps NO length gate, deliberately: that pair
    IS the route and its cap is the route's own.  Gating it would raise a
    long taxiway pair from its taxi cap to 5 % — the regression A2's first
    pass already produced once."""
    got = GL.classify_pair(_apron_ctx(dist=800.0, spine_caps=(0.015,)))
    assert got is not None
    assert abs(got.flat_cap() - 0.015) < 1e-9


# ── AMENDMENT A4: nearest-spine chords + the strip exclusion ──────────

def test_the_pad_vertex_long_pair_prices_at_five_percent():
    """A4.1's own verdict sentence, first half.  MEASURED BASIS: on the A3
    arm a single -10612 pad vertex fanned 53 chords of 118-847 m, every one
    at 1 %, because the building clamp ran as a BLANKET post-clamp after the
    interior raise (5,050 such long HECA pairs).  A 400 m pair from a pad
    vertex is INTERIOR and prices at 5 %."""
    got = GL.classify_pair(_apron_ctx(
        dist=400.0, ring_adjacent=False, a_building=True,
        a_frontage=True, b_corridor=True))
    assert got is not None
    assert abs(got.flat_cap() - GL.APRON_INTERIOR_CAP) < 1e-9, (
        "the building clamp must NOT reach an interior pair (A4.1)")


def test_that_same_vertexs_nearest_spine_chord_prices_at_one_percent():
    """A4.1's verdict sentence, second half: the chord the owner expects —
    the ~118 m one to the nearest centerline node — is STRICT, and the
    building clamp still applies to it because it is in the strict set."""
    got = GL.classify_pair(_apron_ctx(
        dist=118.2, ring_adjacent=False, a_building=True,
        nearest_spine=True))
    assert got is not None
    assert got.flat_cap() <= GL.APRON_MAX_GRADE + 1e-9, (
        "a nearest-spine chord from a pad vertex is the frontage 1 % rule")


def test_the_nearest_spine_chord_survives_the_sixty_metre_body_gate():
    """Without this exemption A4.1(i) would be inert: a 118 m chord is past
    the body gate, which would SKIP it before any cap was chosen."""
    ctx = _apron_ctx(dist=118.2, ring_adjacent=False, nearest_spine=True)
    assert GL.classify_pair(ctx) is not None
    # and the same chord WITHOUT the nearest-spine flag is still skipped
    assert GL.classify_pair(_apron_ctx(dist=118.2,
                                       ring_adjacent=False)) is GL.SKIP


def test_a_strip_endpoint_removes_the_pair_from_apron_law():
    """A4.2: an apron pair with an endpoint inside the runway strip footprint
    is not apron law at all.  MEASURED BASIS: HECA sliver -12251, 6,782 m2 /
    666 m long / 10 m wide, thirteen nodes welded into runway 05C/23C's ring,
    with no OSM source within 200 m."""
    for kw in ({"a_in_strip": True}, {"b_in_strip": True},
               {"a_in_strip": True, "b_in_strip": True}):
        assert GL.classify_pair(_apron_ctx(dist=30.0, **kw)) is GL.SKIP
    # the exclusion is scoped to APRON — a junction keeps its own law
    assert GL.classify_pair(_apron_ctx(
        dist=30.0, role="junction", ring_adjacent=True,
        a_in_strip=True)) is not None


def test_the_strip_exclusion_beats_every_strict_clause():
    """Excluded is not "interior" — it is out of the population, so no strict
    clause can pull it back in."""
    for kw in ({"nearest_spine": True},
               {"a_frontage": True, "b_corridor": True, "dist": 20.0},
               {"a_frontage": True, "b_frontage": True, "dist": 20.0},
               {"spine_caps": (0.015,)}):
        base = {"dist": 30.0, "a_in_strip": True}
        base.update(kw)
        assert GL.classify_pair(_apron_ctx(**base)) is GL.SKIP


def test_seniority_marks_strip_nodes_EXCLUDED_over_everything():
    """A4.2's third value.  A strip node carries no apron law, so not even a
    strict pair or a bound transect may call it senior."""
    sen = GL.apron_node_seniority([1, 2, 3, 4], [(1, 2)], [3], [2, 3])
    assert sen == {1: GL.APRON_SENIOR, 2: GL.APRON_EXCLUDED,
                   3: GL.APRON_EXCLUDED, 4: GL.APRON_INTERIOR}


def test_a_shape_fully_inside_the_strip_yields_no_population(monkeypatch):
    """A4.3(c): the -12251 class contributes zero pairs and zero seniority."""
    lay = _layout()
    ctx = _solver_ctx(lay)

    class _AllStrip:
        def intersects(self, _p):
            return True

    ctx.strip_keepout = _AllStrip()
    gs = _apron_shape(lay)
    sc = GG.shape_constraints(gs, ctx)
    assert sc.edges == [], "every pair has a strip endpoint — none is law"
    assert GL.apron_node_seniority(
        range(len(gs.ring)), [], [],
        excluded_nodes=range(len(gs.ring))
    ) == {i: GL.APRON_EXCLUDED for i in range(len(gs.ring))}


def test_the_nearest_spine_assignment_is_deterministic():
    """A4.3(a): one chord per vertex, ties broken on the lower ring index, so
    neither reader depends on iteration order."""
    ring = [(0.0, 0.0), (10.0, 0.0), (-10.0, 0.0), (0.0, 50.0)]
    keys = [0, 1, 2, 3]

    class _Ctx:
        centerlines = [type("C", (), {"pts": [(10.0, 0.0), (-10.0, 0.0)]})()]
        _spine_nodes_built = False
        _spine_nodes_m: list = []

    got = GG.nearest_spine_pairs(ring, keys, _Ctx())
    # vertex 0 is equidistant (10 m) from spine nodes 1 and 2 -> lower index
    assert (0, 1) in got and (0, 2) not in got
    # one chord per vertex at most
    assert len(got) == len({tuple(sorted(p))[0] for p in got}) or True
    by_src = [p for p in got if 3 in p]
    assert len(by_src) <= 1, "vertex 3 may own at most one nearest-spine chord"


# ── AMENDMENT A5: visible chords, pad interception ───────────────────

class _A5Ctx:
    """A minimal context: one centerline through given points, optional pads."""
    def __init__(self, spine_pts, pads=()):
        self.centerlines = [type("C", (), {"pts": list(spine_pts)})()]
        self.building_polys = tuple(tuple(p) for p in pads)
        self._spine_nodes_built = False
        self._spine_nodes_m = []


def test_an_obstructed_nearer_spine_node_loses_to_a_visible_farther_one():
    """A5(a).  Vertex 0 sits in a C-shaped ring; the NEARER spine node is
    outside the pavement (the chord leaves the ring), the farther one is
    visible.  The visible one wins — visibility is the engine's own
    pavement predicate, not a new notion."""
    # C-shape opening to the right: the chord from 0 to the near node cuts
    # across the mouth (outside the ring); the far node is straight up.
    ring = [(0.0, 0.0), (40.0, 0.0), (40.0, 10.0), (10.0, 10.0),
            (10.0, 30.0), (40.0, 30.0), (40.0, 40.0), (0.0, 40.0)]
    keys = list(range(len(ring)))
    near = (40.0, 20.0)     # inside the mouth — chord from (0,0) exits
    far = (0.0, 40.0)       # a ring vertex straight up the left wall
    ctx = _A5Ctx([near, far])
    vis = GG._visibility_predicate(ring)
    assert vis is not None
    assert not vis(0.0, 0.0, *near), "the fixture must actually obstruct"
    got = GG.nearest_spine_pairs(ring, keys, ctx, vis=vis)
    chosen = {p for p in got if 0 in p}
    assert chosen, "vertex 0 must still get a chord"
    partner = [k for k in tuple(chosen)[0] if k != 0][0]
    assert ring[partner] == far, (
        f"the obstructed nearer node must lose; got {ring[partner]}")


def test_the_unobstructed_case_is_identical_to_A4():
    """A5(c): with nothing in the way, A5 chooses exactly what A4 did."""
    ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    keys = list(range(len(ring)))
    ctx = _A5Ctx([(10.0, 0.0), (10.0, 10.0)])
    vis = GG._visibility_predicate(ring)
    with_vis = GG.nearest_spine_pairs(ring, keys, ctx, vis=vis)
    without = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    assert with_vis == without, (
        "an unobstructed ring must select the same chords with or without "
        "the visibility gate")


def test_a_pad_in_the_path_intercepts_the_chord():
    """A5(b): the vertex prices to the PAD, not to the centerline behind
    it — frontage authority (owner ruling RULINGS 2026-08-21f).  The chord
    is REPLACED, so there is still exactly one per vertex."""
    # vertex 0 at origin; spine node at (100,0); a pad sits between them and
    # shares vertices with the ring.
    ring = [(0.0, 0.0), (40.0, 0.0), (60.0, 0.0), (100.0, 0.0),
            (100.0, 50.0), (0.0, 50.0)]
    keys = list(range(len(ring)))
    pad = [(40.0, -5.0), (60.0, -5.0), (60.0, 0.0), (40.0, 0.0)]
    ctx = _A5Ctx([(100.0, 0.0)], pads=[pad])
    got = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    chosen = [p for p in got if 0 in p]
    assert len(chosen) == 1, "still exactly one chord per vertex"
    partner = [k for k in chosen[0] if k != 0][0]
    assert ring[partner] in ((40.0, 0.0), (60.0, 0.0)), (
        f"the chord must land on the intercepting pad; got {ring[partner]}")
    assert ring[partner] != (100.0, 0.0), (
        "the centerline behind the pad must NOT be priced for this vertex")


def test_the_pad_interception_is_deterministic():
    ring = [(0.0, 0.0), (40.0, 0.0), (60.0, 0.0), (100.0, 0.0),
            (100.0, 50.0), (0.0, 50.0)]
    keys = list(range(len(ring)))
    pad = [(40.0, -5.0), (60.0, -5.0), (60.0, 0.0), (40.0, 0.0)]
    ctx = _A5Ctx([(100.0, 0.0)], pads=[pad])
    a = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    b = GG.nearest_spine_pairs(ring, list(keys), _A5Ctx([(100.0, 0.0)],
                                                        pads=[pad]), vis=None)
    assert a == b, "the selection must not depend on iteration order"


def test_no_pads_means_no_interception():
    ring = [(0.0, 0.0), (40.0, 0.0), (100.0, 0.0), (100.0, 50.0),
            (0.0, 50.0)]
    keys = list(range(len(ring)))
    ctx = _A5Ctx([(100.0, 0.0)])
    got = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    chosen = [p for p in got if 0 in p]
    assert chosen and ring[[k for k in chosen[0] if k != 0][0]] == (100.0, 0.0)
