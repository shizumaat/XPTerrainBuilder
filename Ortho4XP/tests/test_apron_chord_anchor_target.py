"""THE CHORD-TARGET LAW — an apron ring vertex's strict chord runs to its
NEAREST VISIBLE ANCHOR, pad or centerline, whichever is closer (owner
ruling ``docs/RULINGS.md`` 2026-08-25 first ruling; spec
``docs/specs/apron-chord-anchor-target-spec.md`` §1).

The ruling AMENDS A4.1(i) and the 2026-08-21d strict-chord clause: the
anchor set is the UNION of the taxi-centerline nodes and the building-pad
boundary vertices, and "the pad is a first-class chord target, not merely
an interceptor when it happens to lie in the path" (2026-08-21f, which
this supersedes).  BUILDING FRONTAGE CHORDS ARE UNCHANGED.

The spec's twins (§Twins), all on synthetic rings:

  (a) a vertex nearer a PAD vertex than any spine vertex gets ONE chord to
      the pad and it prices in the STAND class (1 %); a vertex nearer a
      SPINE vertex keeps today's chord and today's cap; equidistant ⇒ the
      lower ring index;
  (b) an anchor behind a re-entrant edge (across a gap / off the apron's
      own pavement) is NOT a candidate — the next-nearest VISIBLE anchor
      wins, through the ONE visibility predicate;
  (c) frontage chords are byte-identical before/after on a fixture with
      pads (``is_frontage_chord`` and its cap untouched);
  (d) ``O4_APRON_CHORD_ANCHOR_TARGET=0`` ⇒ the enumeration is
      byte-identical to the pre-ruling one (spine-only candidates, the
      2026-08-21f interception back in place, every kind ``spine``);
  (e) census/solve parity is STRUCTURAL — one enumeration, one kind per
      pair, and the kind reaches the law only through the reader's
      ``PairContext``.  ``tests/test_harness.py`` carries the register
      half of this twin; here it is asserted as "both readers call the
      same function and get the same mapping".

Headless: synthetic rings, no DEM, no X-Plane data, no network.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch import grade_graph as GG
from auto_patch import grade_law as GL
from auto_patch.config import TAXI_MAX_GRADE


class _Ctx:
    """A minimal grade context: one centerline through the given points,
    an optional pad-key set (``building_keys`` — the enumeration's own pad
    membership) and optional pad polygons (only the pre-ruling
    interception path reads those)."""

    def __init__(self, spine_pts, building_keys=(), pads=()):
        self.centerlines = [type("C", (), {"pts": list(spine_pts)})()]
        self.building_keys = frozenset(building_keys)
        self.building_polys = tuple(tuple(p) for p in pads)
        self._spine_nodes_built = False
        self._spine_nodes_m = []


def _apron_ctx(**kw):
    base = dict(role="apron", dist=30.0, ring_adjacent=False,
                a_seam=False, b_seam=False, a_building=False,
                b_building=False, spine_caps=(),
                body_cap=GL.APRON_MAX_GRADE,
                a_frontage=False, b_frontage=False,
                a_corridor=False, b_corridor=False)
    base.update(kw)
    return GL.PairContext(**base)


def _partner(pairs, k):
    """The single anchor chord of ring key ``k``: ``(other_key, kind)``."""
    hits = [(p, kind) for p, kind in pairs.items() if k in p]
    assert len(hits) == 1, f"exactly one chord per vertex; got {hits}"
    (p, kind) = hits[0]
    return ([x for x in p if x != k][0], kind)


# ── twin (a): whichever anchor is CLOSER wins ────────────────────────

def test_a_vertex_nearer_a_pad_chords_to_the_pad_at_one_percent():
    """Spec twin (a), first clause.  Vertex 0's nearest anchor is a PAD
    boundary vertex 20 m away; the centerline node is 100 m away.  The pad
    wins, the kind is ``pad``, and the law prices it in the STAND class —
    the 1 % the 2026-08-21d pad chord has always carried."""
    ring = [(0.0, 0.0), (20.0, 0.0), (100.0, 0.0), (100.0, 40.0),
            (0.0, 40.0)]
    keys = list(range(len(ring)))
    ctx = _Ctx([(100.0, 0.0)], building_keys=[1])
    got = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    partner, kind = _partner(got, 0)
    assert partner == 1, "the 20 m pad anchor must beat the 100 m spine node"
    assert kind == GG.ANCHOR_KIND_PAD

    p = _apron_ctx(dist=20.0, nearest_spine=True, nearest_anchor_pad=True,
                   corridor_connected=True)
    assert GL.apron_pair_class(p) == GL.APRON_CLASS_STAND
    allow = GL.classify_pair(p)
    assert allow is not None
    assert allow.flat_cap() == pytest.approx(GL.BUILDING_FRONTAGE_MAX_GRADE)


def test_a_vertex_nearer_a_spine_keeps_todays_chord_and_todays_cap():
    """Spec twin (a), second clause: with the spine node nearer, nothing
    about this vertex changes — same target, kind ``spine``, and the
    2026-08-24c reading (a NON-pad vertex's centerline chord is corridor
    travel at 1.5 %) is untouched."""
    ring = [(0.0, 0.0), (20.0, 0.0), (100.0, 0.0), (100.0, 40.0),
            (0.0, 40.0)]
    keys = list(range(len(ring)))
    # the spine node is now the 20 m vertex, the pad the 100 m one
    ctx = _Ctx([(20.0, 0.0)], building_keys=[2])
    got = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    partner, kind = _partner(got, 0)
    assert partner == 1 and kind == GG.ANCHOR_KIND_SPINE

    p = _apron_ctx(dist=20.0, nearest_spine=True, corridor_connected=True)
    assert GL.apron_pair_class(p) == GL.APRON_CLASS_CORRIDOR
    assert GL.classify_pair(p).flat_cap() == pytest.approx(TAXI_MAX_GRADE)
    # …and the same chord from a FRONTAGE vertex is still the stand class
    # (RULINGS 2026-08-24c, unchanged by this ruling).
    assert GL.apron_pair_class(
        _apron_ctx(dist=20.0, nearest_spine=True, a_frontage=True)
    ) == GL.APRON_CLASS_STAND


def test_equidistant_anchors_break_on_the_lower_ring_index():
    """Spec twin (a), third clause (A4.3(a) unchanged): a pad anchor and a
    spine anchor exactly 30 m away both reach vertex 0 — the LOWER ring
    index wins, whichever kind it is, so neither reader depends on
    iteration order."""
    ring = [(0.0, 0.0), (30.0, 0.0), (0.0, 30.0), (60.0, 60.0)]
    keys = list(range(len(ring)))
    # index 1 = pad, index 2 = spine, both 30 m from vertex 0
    got = GG.nearest_spine_pairs(
        ring, keys, _Ctx([(0.0, 30.0)], building_keys=[1]), vis=None)
    partner, kind = _partner(got, 0)
    assert partner == 1 and kind == GG.ANCHOR_KIND_PAD
    # …and with the two kinds swapped the answer flips with the index, not
    # with the kind.
    got2 = GG.nearest_spine_pairs(
        ring, keys, _Ctx([(30.0, 0.0)], building_keys=[2]), vis=None)
    partner2, kind2 = _partner(got2, 0)
    assert partner2 == 1 and kind2 == GG.ANCHOR_KIND_SPINE


def test_the_anchor_set_is_the_union_not_a_replacement():
    """The ruling widens the candidate set; it does not swap one for the
    other.  With pads present, a vertex whose only anchor in reach is a
    spine node still gets its spine chord."""
    ring = [(0.0, 0.0), (100.0, 0.0), (100.0, 40.0), (0.0, 40.0)]
    keys = list(range(len(ring)))
    ctx = _Ctx([(100.0, 0.0)], building_keys=[2])
    got = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    assert (0, 1) in got and got[(0, 1)] == GG.ANCHOR_KIND_SPINE
    # vertex 3's nearest anchor is the PAD vertex 2 (100 m) rather than the
    # spine node 1 (~107 m) — the union at work from the other end.
    partner, kind = _partner(got, 3)
    assert partner == 2 and kind == GG.ANCHOR_KIND_PAD


# ── twin (b): visibility ─────────────────────────────────────────────

def test_an_anchor_behind_a_gap_is_not_a_candidate():
    """Spec twin (b).  A C-shaped apron: the NEAREST pad anchor sits across
    the mouth, so the chord to it leaves the apron's own pavement.  It is
    not a candidate, and the next-nearest VISIBLE anchor wins — through the
    ONE visibility predicate, not a second notion."""
    ring = [(0.0, 0.0), (40.0, 0.0), (40.0, 10.0), (10.0, 10.0),
            (10.0, 30.0), (40.0, 30.0), (40.0, 40.0), (0.0, 40.0)]
    keys = list(range(len(ring)))
    vis = GG._visibility_predicate(ring)
    assert vis is not None
    # index 5 = (40, 30): the chord from (0,0) crosses the mouth.
    assert not vis(0.0, 0.0, *ring[5]), "the fixture must actually obstruct"
    ctx = _Ctx([(0.0, 40.0)], building_keys=[5])
    got = GG.nearest_spine_pairs(ring, keys, ctx, vis=vis)
    partner, kind = _partner(got, 0)
    assert ring[partner] == (0.0, 40.0), (
        f"the obstructed nearer PAD anchor must lose; got {ring[partner]}")
    assert kind == GG.ANCHOR_KIND_SPINE


def test_visibility_is_priced_over_the_aprons_own_ring():
    """The population the chord is walked over is THIS apron's ring — the
    spec's "apron-only pavement" clause.  With nothing in the way the
    verdicts are identical with and without the gate, which is what says
    the gate removes only chords that leave the pavement."""
    ring = [(0.0, 0.0), (30.0, 0.0), (30.0, 30.0), (0.0, 30.0)]
    keys = list(range(len(ring)))
    ctx = _Ctx([(30.0, 30.0)], building_keys=[1])
    with_vis = GG.nearest_spine_pairs(
        ring, keys, ctx, vis=GG._visibility_predicate(ring))
    without = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    assert with_vis == without


# ── twin (c): frontage chords untouched ──────────────────────────────

def test_frontage_chords_are_byte_identical_before_and_after():
    """Spec twin (c) / §1.3's unchanged-rules clause: ``is_frontage_chord``
    and the cap it earns do not move, with the ruling armed or disarmed and
    with a pad target flag set or not."""
    front = dict(dist=40.0, a_frontage=True, b_corridor=True)
    base = _apron_ctx(**front)
    assert GL.is_frontage_chord(base)
    assert GL.apron_pair_class(base) == GL.APRON_CLASS_STAND
    cap = GL.classify_pair(base).flat_cap()
    assert cap == pytest.approx(GL.BUILDING_FRONTAGE_MAX_GRADE)
    # a frontage chord that is ALSO an anchor chord, of either kind, is
    # still exactly the frontage chord — the frontage clause runs first.
    for kw in ({"nearest_spine": True},
               {"nearest_spine": True, "nearest_anchor_pad": True}):
        p = _apron_ctx(**{**front, **kw})
        assert GL.is_frontage_chord(p)
        assert GL.apron_pair_class(p) == GL.APRON_CLASS_STAND
        assert GL.classify_pair(p).flat_cap() == pytest.approx(cap)


def test_the_pad_target_flag_alone_never_reaches_a_non_anchor_pair():
    """The kind is a property OF the chord: without ``nearest_spine`` the
    pair is not an anchor chord at all and the flag must change nothing —
    the 2026-08-21d refutation of the blanket pad clamp (a 400 m pair that
    merely touches a pad is not a 1 % chord)."""
    for kw in ({}, {"nearest_anchor_pad": True}):
        p = _apron_ctx(dist=400.0, a_building=True, corridor_connected=True,
                       **kw)
        assert GL.apron_pair_class(p) == GL.APRON_CLASS_BACK_EDGE


# ── twin (d): the kill switch ────────────────────────────────────────

def test_flag_off_is_the_pre_ruling_enumeration(monkeypatch):
    """Spec twin (d).  With ``O4_APRON_CHORD_ANCHOR_TARGET=0`` the pad keys
    are not candidates, the 2026-08-21f interception is back, and every
    chord reports kind ``spine`` — the pre-ruling cap assignment exactly."""
    ring = [(0.0, 0.0), (20.0, 0.0), (100.0, 0.0), (100.0, 40.0),
            (0.0, 40.0)]
    keys = list(range(len(ring)))
    ctx = _Ctx([(100.0, 0.0)], building_keys=[1])
    monkeypatch.setattr(GG, "APRON_CHORD_ANCHOR_TARGET", False)
    got = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    partner, kind = _partner(got, 0)
    assert partner == 2, "flag off ⇒ the spine node is the only anchor"
    assert kind == GG.ANCHOR_KIND_SPINE
    assert set(got.values()) == {GG.ANCHOR_KIND_SPINE}


def test_flag_off_restores_the_pad_interception(monkeypatch):
    """The other half of twin (d): the pre-ruling law's pad INTERCEPTION
    (RULINGS 2026-08-21f) is kept whole behind the switch."""
    ring = [(0.0, 0.0), (40.0, 0.0), (60.0, 0.0), (100.0, 0.0),
            (100.0, 50.0), (0.0, 50.0)]
    keys = list(range(len(ring)))
    pad = [(40.0, -5.0), (60.0, -5.0), (60.0, 0.0), (40.0, 0.0)]
    ctx = _Ctx([(100.0, 0.0)], pads=[pad])
    monkeypatch.setattr(GG, "APRON_CHORD_ANCHOR_TARGET", False)
    got = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    partner, kind = _partner(got, 0)
    assert ring[partner] in ((40.0, 0.0), (60.0, 0.0))
    assert kind == GG.ANCHOR_KIND_SPINE, (
        "the pre-ruling law knows one kind — an intercepting pad only "
        "moved the far end of a centerline chord")


# ── twin (e): one enumeration, both readers ──────────────────────────

def test_the_kind_reaches_the_law_only_through_the_one_enumeration():
    """Spec twin (e) / §1.5.  ``PairContext.nearest_anchor_pad`` defaults
    to FALSE, so a reader that does not consume the enumeration sees the
    pre-ruling assignment; and the enumeration's mapping is the ONLY place
    the kind is minted.  (The register half of this twin —
    census/solve/fixture lockstep — is ``tests/test_harness.py``.)"""
    assert GL.PairContext(
        role="apron", dist=10.0, ring_adjacent=True, a_seam=False,
        b_seam=False, a_building=False, b_building=False, spine_caps=(),
        body_cap=GL.APRON_MAX_GRADE).nearest_anchor_pad is False
    ring = [(0.0, 0.0), (20.0, 0.0), (100.0, 0.0), (100.0, 40.0),
            (0.0, 40.0)]
    keys = list(range(len(ring)))
    ctx = _Ctx([(100.0, 0.0)], building_keys=[1])
    a = GG.nearest_spine_pairs(ring, keys, ctx, vis=None)
    b = GG.nearest_spine_pairs(
        ring, list(keys), _Ctx([(100.0, 0.0)], building_keys=[1]), vis=None)
    assert a == b, "the mapping must not depend on iteration order"
    assert set(a.values()) <= {GG.ANCHOR_KIND_SPINE, GG.ANCHOR_KIND_PAD}


def test_shape_constraints_records_the_kind_index_parallel():
    """``ShapeConstraints.edge_anchor_kind`` is index-parallel to
    ``edges`` by construction (the ``edge_interior`` precedent): a report
    that had to re-derive the target from a cap VALUE would be guessing,
    because both sub-populations price at 1 %."""
    ring = [(0.0, 0.0), (20.0, 0.0), (100.0, 0.0), (100.0, 40.0),
            (0.0, 40.0)]
    keys = list(range(len(ring)))
    shape = GG.GradeShape(role="apron", ring=ring, keys=keys)
    ctx = GG.GradeContext(centerlines=[
        GG.Centerline(pts=[(100.0, 0.0), (100.0, 40.0)],
                      seg_caps=[TAXI_MAX_GRADE])],
        building_keys=frozenset({1}))
    sc = GG.shape_constraints(shape, ctx)
    assert len(sc.edge_anchor_kind) == len(sc.edges)
    kinds = {k for k in sc.edge_anchor_kind if k}
    assert kinds <= {GG.ANCHOR_KIND_SPINE, GG.ANCHOR_KIND_PAD}
