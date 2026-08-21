"""THE APRON WITHIN-SHAPE POPULATION — the movement surfaces, never a
generic ring-vertex pair (owner ruling ``docs/RULINGS.md`` 2026-08-21b,
answer "ii"; spec ``docs/specs/apron-within-shape-population-spec.md``).

The five twins the spec pre-registers (§8), all on ONE synthetic airport:
an apron, TWO building pads on its back edge, and ONE taxi corridor
running through it.

  (a) a generic apron pair is SKIPPED and a frontage chord is KEPT, and
      P1 (both endpoints frontage vertices of one pad) takes the
      pre-existing ring-adjacent branch — its verdict is identical with
      the rule on and off;
  (b) the CENSUS (``check_grade.iter_shape_grade_constraints``, reading
      an emitted ring by node id) and the BAKE
      (``grade_graph.shape_constraints`` under the solver's context)
      enumerate the IDENTICAL apron pair set — the lockstep the ruling
      requires ("ONE predicate, both readers");
  (c) junction / runway / building within-shape pair sets are BYTE-
      IDENTICAL to the rule-off arm (ruling clause 4);
  (d) the sidecar's ``pair_caps`` FAMILY TAG round-trips, and a legacy
      three-element row still reads exactly as before;
  (e) an apron with NO building frontage yields ZERO within-shape law
      edges (the warm-start carrier keeps the smoothing — spec §5).

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


def _edges_xy(lay, apron_ring=None):
    gs = _apron_shape(lay, apron_ring)
    return _pairs_xy(GG.shape_constraints(gs, _solver_ctx(lay)), gs)


@pytest.fixture
def rule_off(monkeypatch):
    """The kill switch ``O4_APRON_WITHIN_SHAPE_FRONTAGE_ONLY=0`` — the
    pre-ruling all-pair population.  The module constant is read at
    import, so the twin drives THAT (the same shape every other gate in
    this engine is tested through)."""
    monkeypatch.setattr(GL, "APRON_WITHIN_SHAPE_FRONTAGE_ONLY", False)


# ── (a) generic skipped, frontage chord kept, P1 unchanged ───────────

def test_frontage_chord_kept_generic_apron_pair_skipped():
    kept = _edges_xy(_layout())
    # A FRONTAGE CHORD: one endpoint a frontage vertex, the other on the
    # spine, within the frontage band's own reach.
    for pad_xy, spine_xy in (((20.0, 120.0), (-100.0, 0.0)),
                             ((200.0, 120.0), (300.0, 0.0)),
                             ((240.0, 120.0), (300.0, 0.0))):
        assert math.dist(pad_xy, spine_xy) <= BUILDING_REACH_CORRIDOR_M
        assert frozenset((pad_xy, spine_xy)) in kept, (
            f"frontage chord {pad_xy}->{spine_xy} was dropped")
    # GENERIC pairs — including a RING-ADJACENT one, which the ruling
    # does not exempt: neither endpoint is a frontage vertex.
    for a, b in (((-100.0, -40.0), (300.0, -40.0)),      # ring-adjacent
                 ((-100.0, -40.0), (300.0, 120.0)),      # body diagonal
                 ((300.0, 120.0), (-100.0, 120.0))):     # back edge
        assert frozenset((a, b)) not in kept, f"generic pair {a}-{b} kept"
    # EVERY surviving pair is a frontage chord.
    for pair in kept:
        (pa, pb) = tuple(pair)
        assert ({pa, pb} & FRONTAGE_XY) and ({pa, pb} & SPINE_XY), (
            f"{pair} is not a frontage chord")


def test_over_reach_frontage_chord_is_not_law():
    """Beyond ``BUILDING_REACH_CORRIDOR_M`` the seat does not reach the
    spine — the frontage band's OWN reach, not a new constant."""
    far = frozenset(((20.0, 120.0), (300.0, 0.0)))
    assert math.dist((20.0, 120.0), (300.0, 0.0)) > BUILDING_REACH_CORRIDOR_M
    assert far not in _edges_xy(_layout())


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
    saved = GL.APRON_WITHIN_SHAPE_FRONTAGE_ONLY
    try:
        GL.APRON_WITHIN_SHAPE_FRONTAGE_ONLY = False
        without_rule = GL.classify_pair(p1)
    finally:
        GL.APRON_WITHIN_SHAPE_FRONTAGE_ONLY = saved
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


def _census_pairs_xy(with_pads=True, apron_ring=None):
    ways, nodes, nid_of = _osm_ways_nodes(with_pads, apron_ring)
    xy_of = {nid: xy for xy, nid in nid_of.items()}
    axes = [(list(SPINE), 0.015, 0.015, -1, False)]
    out = set()
    for c in cg.iter_shape_grade_constraints(
            ways, nodes, _ll_to_m, 0.015, taxi_axes=axes):
        if c.way.tags.get("role") != "apron":
            continue
        out.add(frozenset((xy_of[c.nid_a], xy_of[c.nid_b])))
    return out


def test_census_and_bake_enumerate_the_same_apron_pairs():
    """THE LOCKSTEP (spec §2 / §8(b)).  A mismatch here is a STOP: the
    fix is the predicate, never the count."""
    bake = _edges_xy(_layout())
    census = _census_pairs_xy()
    assert census == bake, (
        f"census-only {sorted(census - bake)} / bake-only {sorted(bake - census)}")
    assert bake, "the fixture must produce at least one frontage chord"


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
    monkeypatch.setattr(GL, "APRON_WITHIN_SHAPE_FRONTAGE_ONLY", False)
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
    saved = GL.APRON_WITHIN_SHAPE_FRONTAGE_ONLY
    try:
        GL.APRON_WITHIN_SHAPE_FRONTAGE_ONLY = False
        off = GL.classify_pair(p)
    finally:
        GL.APRON_WITHIN_SHAPE_FRONTAGE_ONLY = saved
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


# ── (e) a zero-building apron has no within-shape law edges ──────────

def test_zero_building_apron_yields_no_within_shape_law_edges():
    """Spec §8(e): the law goes silent and the CARRIER keeps the
    smoothing (RULINGS 2026-08-15, band carrier) — no replacement
    regulariser is added here."""
    lay = _layout(with_pads=False)
    assert _edges_xy(lay) == set()
    assert _census_pairs_xy(with_pads=False) == set()
    # The shape still registers its spine chain — the global spine, the
    # reach band and the carrier all keep their connectivity.
    gs = _apron_shape(lay)
    sc = GG.shape_constraints(gs, _solver_ctx(lay))
    assert sc.edges == []
    assert sc.spine_chains == GG.shape_constraints(
        gs, _solver_ctx(lay)).spine_chains


def test_zero_building_apron_is_fully_populated_with_the_rule_off(rule_off):
    """The (e) claim is the RULE's, not the fixture's: with the kill
    switch off the same pad-less apron carries its full pre-ruling
    population (the remaining skips are the pre-existing body-chord and
    spine-crossing ones)."""
    assert len(_edges_xy(_layout(with_pads=False))) >= 10


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
