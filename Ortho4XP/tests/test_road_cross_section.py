"""THE ROAD CROSS-SECTION IS LAW — owner ruling RULINGS 2026-08-25g.

Spec: ``docs/specs/road-surface-quality-spec.md`` §1.  The owner's in-sim
read of 1.0.259 was "roads improved but still have a lot of bumps and
laterally not flat"; the ruling resolves the KAFW N-1 open question of
2026-08-20 by putting the road CROSS-SECTION limit into the law.

WHAT ACTUALLY WAS WRONG, and why each twin here exists.  The 2 %
transverse cap was already GENERATION-BINDING — ``grade_graph.
_bake_one_route`` has resolved ``cT`` for road pairs since 2026-08-08 —
and it did not HOLD.  Two measured reasons, one twin each:

* §1 THE CENSUS COULD NOT REACH IT.  Every within-shape allowance is
  ``max(baked, cap_l · dist)``, deliberately "never TIGHTER than the flat
  cap" so a curve's arc credit can only relax.  On a pair running ACROSS
  a road the 8 % longitudinal term therefore always won, and a road could
  tilt 2-8 % laterally with nothing able to price it — 164 rows at KAFW,
  254 at KDFW, all invisible.
* §2 THE SOLVE LEFT AN OFF-NETWORK ROAD ISOTROPIC.  ``_bake_edge``'s last
  branch returns the pair unchanged when neither endpoint finds a route,
  i.e. at the 8 % cap in every direction.

* §3 ONE IMPLEMENTATION.  The classifier ("is this pair the road's
  cross-section?") and the road's own axis are single functions in
  ``grade_law``; the solver's pair builder, the census and the
  lateral-contiguity station walk all reach THEM.  Two copies of a
  classifier drifting is this repo's census-wrapper defect class, and
  here it would mean the surface we build and the surface we census
  disagree about which pairs are lateral.
* §4 THE FAMILY.  ``road_cross_section`` is registered in
  ``LAW_FAMILIES`` and a pair lands in exactly ONE family — the ruling
  prices the cross-section AT the cross-section limit, *not* at the
  chord cap, so counting it under both would price one pair twice.
  (The register/census/partition parity itself is twinned in
  ``tests/test_harness.py`` §1, which this file does not duplicate.)
* §5 THE GATE.  ``O4_ROAD_CROSS_SECTION_LAW=0`` restores the pre-ruling
  reading on BOTH readers together — they are one law and land together.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from auto_patch import config as C                          # noqa: E402
from auto_patch import grade_law as GL                      # noqa: E402
from auto_patch import grade_graph as GG                    # noqa: E402
from auto_patch import lateral_contiguity as LC             # noqa: E402


#: EVERY module that captures a law object at IMPORT, in dependency order.
#: The gate tests below reload the law under a changed environment, and a
#: reload REBINDS the function objects — so a module that imported
#: ``grade_law.pair_is_transverse`` by value (``grade_graph``,
#: ``groundside``, ``lateral_contiguity``) is left holding the PREVIOUS
#: one unless it is reloaded too.  Restoring only three of the five left
#: ``groundside._long_axis_of_points is grade_law.long_axis_of_points``
#: false for whatever ran next in the same xdist worker: a test-isolation
#: leak that reads exactly like the two-copies defect the identity twin
#: exists to catch.  Reload the whole set, always, in this order.
_LAW_MODULES = ("auto_patch.config", "auto_patch.grade_law",
                "auto_patch.grade_graph", "auto_patch.lateral_contiguity",
                "auto_patch.groundside")


def _reload_the_law():
    """Re-read every law module, in dependency order.  A module absent
    from ``sys.modules`` was never imported in this worker and has no
    stale binding to restore."""
    import auto_patch.groundside            # noqa: F401  (force the import)
    for name in _LAW_MODULES:
        mod = sys.modules.get(name)
        if mod is not None:
            importlib.reload(mod)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cg():
    return _load("xsec_twin_check_grade", ROOT / "tools" / "check_grade.py")


# ══════════════════════════════════════════════════════════════════════
# §3 ONE IMPLEMENTATION
# ══════════════════════════════════════════════════════════════════════

def test_the_road_family_has_one_spelling(cg):
    """Four readers, one role set.  ``lateral_contiguity`` walks these
    rings' stations, ``grade_graph`` flags their pairs and the census
    censuses them; a fourth hand-written list is the census-wrapper
    defect that cost this repo a whole law family once already."""
    assert LC.ROAD_ROLES is GL.ROAD_ROLES
    assert set(cg._ROAD_FAMILY_ROLES) == set(GL.ROAD_ROLES)
    # ``groundside_pavement`` is deliberately NOT a road: the ruling
    # names the road, and a car park has no cross-section.
    assert "groundside_pavement" not in GL.ROAD_ROLES


def test_the_axis_reader_is_one_function(cg):
    """The station walk and the pair classifier must not each have their
    own idea of which way a road runs — the law would then price one set
    of pairs while the walk described another."""
    from shapely.geometry import Polygon
    ring = [(0.0, 0.0), (100.0, 0.0), (100.0, 6.0), (0.0, 6.0)]
    assert LC.long_axis(Polygon(ring)) == GL.long_axis_of_points(ring)
    # The census reaches the SAME function object, not a copy of it.
    assert cg._long_axis_of_points is GL.long_axis_of_points
    assert cg._pair_is_transverse is GL.pair_is_transverse
    assert cg._road_xsection_cap is GL.road_cross_section_cap


def test_the_classifier_partitions_at_45_degrees():
    """Every pair is on one side of the partition, so no pair falls
    between the two laws."""
    axis = GL.long_axis_of_points(
        [(0.0, 0.0), (100.0, 0.0), (100.0, 6.0), (0.0, 6.0)])[0]
    assert axis == pytest.approx((1.0, 0.0))
    assert not GL.pair_is_transverse(axis, 10.0, 0.0)     # along
    assert GL.pair_is_transverse(axis, 0.0, 6.0)          # across
    # The boundary itself is TRANSVERSE — the ruling says "≥ 45 °".
    assert GL.pair_is_transverse(axis, 6.0, 6.0)
    assert not GL.pair_is_transverse(axis, 6.0, 5.9)
    # Sign-free: a chord and its reverse are the same chord.
    assert (GL.pair_is_transverse(axis, 3.0, 9.0)
            is GL.pair_is_transverse(axis, -3.0, -9.0))
    # An unreadable axis prices NOTHING new (never a cap asserted on
    # geometry we could not measure).
    assert GL.pair_is_transverse(None, 0.0, 6.0) is False
    assert GL.long_axis_of_points([(0.0, 0.0), (1.0, 1.0)]) is None


def test_the_cap_is_the_config_constant_and_only_tightens():
    """"the existing config cross-section constant for roads; never a
    literal" — the spec's own words."""
    assert (GL.road_cross_section_cap(C.SERVICE_ROAD_MAX_GRADE)
            == C.SERVICE_ROAD_MAX_TRANSVERSE)
    # Never LOOSER than what came in: a pair the rest of the chain
    # already tightened (a building frontage at 1 %) is untouched.
    for cap in (0.01, 0.015, 0.005):
        assert GL.road_cross_section_cap(cap) <= cap
    assert C.ROAD_TRANSVERSE_AXIS_MIN_DEG == 45.0


# ══════════════════════════════════════════════════════════════════════
# §2 THE SOLVE PRICES WHAT THE CENSUS PRICES
# ══════════════════════════════════════════════════════════════════════

def _road_shape(width=6.0, length=120.0, role="service_road"):
    ring = [(0.0, 0.0), (length, 0.0), (length, width), (0.0, width)]
    return GG.GradeShape(role=role, ring=ring,
                         keys=[f"n{i}" for i in range(len(ring))])


def _bare_ctx():
    return GG.GradeContext(centerlines=[], routes=[])


def test_the_solve_prices_the_cross_section_at_the_transverse_cap():
    """§1.3: "the road ring's transverse pairs enter the grade graph at
    the cross-section cap".  An OFF-NETWORK road (no routes at all) is
    the population ``_bake_edge`` used to leave isotropic at 8 %."""
    sc = GG.shape_constraints(_road_shape(), _bare_ctx())
    assert sc.edges, "a road ring must produce within-shape law edges"
    assert len(sc.edge_transverse_road) == len(sc.edges)
    seen = {}
    for (ka, kb, allow), tv in zip(sc.edges, sc.edge_transverse_road):
        seen.setdefault(tv, set()).add(round(allow.flat_cap(), 6))
    assert True in seen, "a 6 x 120 m road ring has cross-section pairs"
    assert seen[True] == {round(C.SERVICE_ROAD_MAX_TRANSVERSE, 6)}, (
        f"cross-section pairs priced at {seen[True]}, not the road's "
        f"transverse cap")
    # ...and the ALONG pairs keep their longitudinal cap: this is a
    # partition, not a blanket tightening of the road family.
    assert seen[False] == {round(C.SERVICE_ROAD_MAX_GRADE, 6)}


def test_the_gate_off_restores_the_pre_ruling_solve(monkeypatch):
    """ONE kill switch, both readers.  OFF ⇒ every road pair prices at
    its longitudinal cap, exactly as before 25g."""
    monkeypatch.setenv("O4_ROAD_CROSS_SECTION_LAW", "0")
    importlib.reload(C)
    importlib.reload(GL)
    importlib.reload(GG)
    try:
        sc = GG.shape_constraints(_road_shape(), _bare_ctx())
        assert not any(sc.edge_transverse_road)
        caps = {round(a.flat_cap(), 6) for (_x, _y, a) in sc.edges}
        assert caps == {round(C.SERVICE_ROAD_MAX_GRADE, 6)}
    finally:
        monkeypatch.delenv("O4_ROAD_CROSS_SECTION_LAW", raising=False)
        _reload_the_law()


def test_a_taxiway_ring_is_untouched_by_the_road_law():
    """The ruling names the ROAD.  A taxiway/apron ring's transverse law
    is the ROUTE-frame one the bake already applies; this must not have
    quietly become a shape-axis law for every soft shape."""
    sc = GG.shape_constraints(_road_shape(role="apron"), _bare_ctx())
    assert not any(sc.edge_transverse_road)


# ══════════════════════════════════════════════════════════════════════
# §1 + §4 THE CENSUS PRICES IT, IN ITS OWN FAMILY
# ══════════════════════════════════════════════════════════════════════

ANCHOR = (1.5, 1.5)     # never an integer degree: those nodes are
                        # seam-anchored and their pairs drop out.


class _Patch:
    """Metres in, one ``.patch.osm`` + ``.axes.json`` out — the same
    equirectangular formula ``check_grade._ll_to_m_factory`` inverts."""

    def __init__(self, cg):
        self._r = cg.R_EARTH
        self._cos0 = math.cos(math.radians(ANCHOR[0]))
        self.nodes: list = []
        self.ways: list = []
        self._next = 0

    def ll(self, x, y):
        return (ANCHOR[0] + math.degrees(y / self._r),
                ANCHOR[1] + math.degrees(x / (self._r * self._cos0)))

    def _id(self):
        self._next -= 1
        return str(self._next)

    def ring(self, pts, tags):
        ns = []
        for (x, y, alt) in pts:
            nid = self._id()
            lat, lon = self.ll(x, y)
            self.nodes.append((nid, lat, lon, alt))
            ns.append(nid)
        self.ways.append((self._id(), ns + [ns[0]], dict(tags)))

    def write(self, path: Path):
        out = ["<?xml version='1.0' encoding='UTF-8'?>",
               "<osm version='0.6' generator='xsec-twin'>"]
        for nid, lat, lon, alt in self.nodes:
            out.append(f"  <node id='{nid}' lat='{lat:.11f}' "
                       f"lon='{lon:.11f}'><tag k='alt_abs' "
                       f"v='{alt:.2f}' /></node>")
        for wid, nids, tags in self.ways:
            out.append(f"  <way id='{wid}'>")
            out += [f"    <nd ref='{n}' />" for n in nids]
            out += [f"    <tag k='{k}' v='{v}' />" for k, v in tags.items()]
            out.append("  </way>")
        out.append("</osm>")
        path.write_text("\n".join(out) + "\n")
        Path(str(path) + ".axes.json").write_text(json.dumps(
            {"anchor": list(ANCHOR), "ruleset": "icao"}))
        return path


#: The N-1 CLASS, minimally: a 6 m wide, 120 m long road whose two flanks
#: sit 0.30 m apart — 5.0 % ACROSS the road, and 0.25 % along it.  Under
#: the 8 % chord cap (so ``within_shape`` says nothing) and well over the
#: 2 % cross-section limit.  This is the population the owner sees as "not
#: laterally flat", and before 25g it censused ZERO.
def _n1_patch(cg, tmp_path: Path) -> Path:
    p = _Patch(cg)
    p.ring([(0.0, 0.0, 10.00), (120.0, 0.0, 10.30),
            (120.0, 6.0, 10.60), (0.0, 6.0, 10.30)],
           {"role": "service_road", "shapeID": "R1"})
    return p.write(tmp_path / "XSEC_auto.patch.osm")


def test_the_n1_class_censuses_in_the_road_cross_section_family(cg,
                                                                tmp_path):
    fam: dict = {}
    cg.run_checks(_n1_patch(cg, tmp_path), top_n=0, quiet=True,
                  family_out=fam)
    rows = fam["road_cross_section"]
    assert rows, ("the 5 % lateral tilt censused NOTHING — this is the "
                  "KAFW N-1 defect the ruling resolves")
    worst = max(r.grade_pct for r in rows)
    assert worst > C.SERVICE_ROAD_MAX_TRANSVERSE * 100
    assert all(r.cap_pct == pytest.approx(
        C.SERVICE_ROAD_MAX_TRANSVERSE * 100) for r in rows), (
        "a cross-section row must report the cross-section cap it was "
        "priced at, not the chord cap")


def test_a_row_lands_in_exactly_one_family(cg, tmp_path):
    """The ruling prices the cross-section AT the cross-section limit,
    NOT at the chord cap.  A row in both families is one pair priced
    twice, and would inflate every count that sums them."""
    fam: dict = {}
    cg.run_checks(_n1_patch(cg, tmp_path), top_n=0, quiet=True,
                  family_out=fam)

    def _key(r):
        return (round(r.pt_a[0], 3), round(r.pt_a[1], 3),
                round(r.pt_b[0], 3), round(r.pt_b[1], 3))
    xs = {_key(r) for r in fam["road_cross_section"]}
    ws = {_key(r) for r in fam["within_shape"]}
    assert xs and not (xs & ws)


def test_the_along_road_grade_still_censuses_as_within_shape(cg, tmp_path):
    """The partition must not have eaten the LONGITUDINAL law: a road
    running over its 8 % chord cap along its own axis is still a
    ``within_shape`` row."""
    p = _Patch(cg)
    # 120 m long, 12 m of rise = 10 % ALONG the axis, laterally flat.
    p.ring([(0.0, 0.0, 10.0), (120.0, 0.0, 22.0),
            (120.0, 6.0, 22.0), (0.0, 6.0, 10.0)],
           {"role": "service_road", "shapeID": "R2"})
    osm = p.write(tmp_path / "LONG_auto.patch.osm")
    fam: dict = {}
    cg.run_checks(osm, top_n=0, quiet=True, family_out=fam)
    assert fam["within_shape"], "the 10 % longitudinal grade vanished"
    assert not fam["road_cross_section"], (
        "a laterally FLAT road minted cross-section rows")


def test_the_gate_off_empties_the_family(cg, tmp_path, monkeypatch):
    """OFF ⇒ the pre-ruling frame exactly: the family censuses zero and
    the tilt is not re-priced anywhere else either."""
    osm = _n1_patch(cg, tmp_path)
    monkeypatch.setenv("O4_ROAD_CROSS_SECTION_LAW", "0")
    # The gate is read at IMPORT, so the law modules the fresh census
    # binds to have to be re-read under it too — otherwise this would
    # test a census wired to an already-armed law and pass for the wrong
    # reason.
    _reload_the_law()
    cg2 = _load("xsec_twin_check_grade_off", ROOT / "tools" / "check_grade.py")
    try:
        assert cg2._ROAD_XSECTION_LAW is False
        fam: dict = {}
        cg2.run_checks(osm, top_n=0, quiet=True, family_out=fam)
        assert fam["road_cross_section"] == []
    finally:
        monkeypatch.delenv("O4_ROAD_CROSS_SECTION_LAW", raising=False)
        _reload_the_law()


# ══════════════════════════════════════════════════════════════════════
# §6 THE LAW RUN LATE — the chord limiter knows the cross-section
# ══════════════════════════════════════════════════════════════════════
# Spec ``road-surface-quality-spec.md`` §2.2, remedy shape (a): "the road
# chord+cross-section law re-clamps road nodes AFTER pass 20 (a final
# road conformance pass reusing the SAME law objects — one law, run
# late)".  ``groundside._grade_limit_groundside_chords`` IS that late
# pass; its band was ISOTROPIC at the role cap, so it permitted — and
# re-created — any lateral tilt under 8 %.
#
# MEASURED (this lane, CYXY, the seam ledger, with the solve already
# enforcing §1): the limiter's two runs were the two seams that MINTED
# lateral defects back — +8 lateral pairs over the 2 % limit at
# ``14_groundside_separation`` and +10 at
# ``20_post_projection_conformance``, on a final population of 171.

def _tilted_road_ring():
    """6 m x 120 m, 0.30 m across = 5.0 % LATERAL, 0.25 % along.  Under
    the 8 % chord cap and well over the 2 % cross-section limit — the
    N-1 class, as a ring the limiter can clamp."""
    return ([(0.0, 0.0), (120.0, 0.0), (120.0, 6.0), (0.0, 6.0)],
            [10.00, 10.30, 10.60, 10.30])


def _lateral_pct(ring, vals):
    from auto_patch import groundside as G
    ax = G._long_axis_of_points(ring)[0]
    worst = 0.0
    n = len(ring)
    for i in range(n):
        for j in range(i + 1, n):
            dx = ring[j][0] - ring[i][0]
            dy = ring[j][1] - ring[i][1]
            if not GL.pair_is_transverse(ax, dx, dy):
                continue
            d = math.hypot(dx, dy)
            worst = max(worst, abs(vals[j] - vals[i]) / d)
    return worst * 100.0


def test_the_late_limiter_clamps_the_cross_section():
    from auto_patch import groundside as G
    ring, vals = _tilted_road_ring()
    axis = G._long_axis_of_points(ring)[0]
    live = free = list(range(len(ring)))
    aware = list(vals)
    G._chord_cut_and_fill(ring, aware, live, free,
                          C.SERVICE_ROAD_MAX_GRADE, axis=axis)
    assert _lateral_pct(ring, aware) <= (
        C.SERVICE_ROAD_MAX_TRANSVERSE * 100.0 + 1e-6)


def test_without_the_axis_the_late_limiter_is_byte_identical():
    """The pre-ruling arithmetic, for every non-road ring and for the
    whole pass with the gate off: the isotropic band permits the tilt,
    so the values come back untouched."""
    from auto_patch import groundside as G
    ring, vals = _tilted_road_ring()
    live = free = list(range(len(ring)))
    iso = list(vals)
    G._chord_cut_and_fill(ring, iso, live, free, C.SERVICE_ROAD_MAX_GRADE)
    assert iso == vals
    assert _lateral_pct(ring, iso) == pytest.approx(5.0, abs=1e-6)


def test_the_late_limiter_reaches_the_laws_own_objects():
    """One law, run late — not a second copy of a 45 deg test living in
    the limiter (which would be two laws over two populations)."""
    from auto_patch import groundside as G
    assert G._long_axis_of_points is GL.long_axis_of_points
    assert G._pair_is_transverse is GL.pair_is_transverse
    assert G._road_cross_section_cap is GL.road_cross_section_cap
    assert G._LAW_ROAD_ROLES is GL.ROAD_ROLES


def test_the_late_limiter_never_loosens_a_longitudinal_budget():
    """The cross-section term may only TIGHTEN.  A road that is steep
    ALONG its axis is still clamped by the longitudinal cap — the axis
    must not have become a licence for the along direction."""
    from auto_patch import groundside as G
    ring = [(0.0, 0.0), (120.0, 0.0), (120.0, 6.0), (0.0, 6.0)]
    vals = [10.0, 40.0, 40.0, 10.0]        # 25 % ALONG, laterally flat
    axis = G._long_axis_of_points(ring)[0]
    live = free = list(range(4))
    out = list(vals)
    G._chord_cut_and_fill(ring, out, live, free, C.SERVICE_ROAD_MAX_GRADE,
                          axis=axis)
    worst = max(abs(out[1] - out[0]), abs(out[2] - out[3])) / 120.0
    assert worst <= C.SERVICE_ROAD_MAX_GRADE + 1e-6


def test_the_cross_section_never_loosens_a_pair_the_chain_tightened(cg,
                                                                    tmp_path):
    """A pair whose LONGITUDINAL cap is already stricter than 2 % — a
    building frontage chord inside a road ring — must keep it.  The
    cross-section cap is a pure function OF the cap the chain settled
    on, and it is ``min``-shaped; re-reading the ROLE cap here instead
    would hand such a pair a 2 % licence it never had."""
    for cap in (0.01, 0.015, 0.005, C.SERVICE_ROAD_MAX_TRANSVERSE):
        assert GL.road_cross_section_cap(cap) == pytest.approx(cap)
    # And the census's own branch is wired to the pair's cap, not the
    # role's: every emitted cross-section row reports a cap no looser
    # than its family's limit.
    fam: dict = {}
    cg.run_checks(_n1_patch(cg, tmp_path), top_n=0, quiet=True,
                  family_out=fam)
    assert all(r.cap_pct <= C.SERVICE_ROAD_MAX_TRANSVERSE * 100 + 1e-9
               for r in fam["road_cross_section"])


# ══════════════════════════════════════════════════════════════════════
# §7 BUILDINGS ARE THE HEAVIEST CONSTRAINT — the frontage exemption
# ══════════════════════════════════════════════════════════════════════
# Owner ruling in the 25g round, applying the standing 2026-07-03 law:
# the 2 % band may NEVER pull a road node off its pad.
#
# THE MEASUREMENT THAT SHAPED THIS (HECA site B, both arms).  The pad END
# already held — 5 of 5 pad-claimed road nodes moved 0.000 m, because
# ``building`` is not in ``GROUNDSIDE_ROLES`` and the limiter's airside
# pin therefore already covers it.  What moved was the ROAD end of the
# same frontage chord (29 of 38 pad-less road nodes, worst 3.21 m), and
# the chord the law prices at BUILDING_FRONTAGE_MAX_GRADE blew out to
# 6.04 m at 10.66 %.  So the defect was never a missing pin: it was that
# the cross-section was applied to a FRONTAGE pair at all.

def _pad_ring():
    """A 6 m x 120 m road at 5 % lateral whose vertex 0 is a PAD weld."""
    ring = [(0.0, 0.0), (120.0, 0.0), (120.0, 6.0), (0.0, 6.0)]
    return ring, [10.00, 10.30, 10.60, 10.30]


def test_the_band_never_pulls_a_road_node_off_its_pad():
    from auto_patch import groundside as G
    ring, base = _pad_ring()
    axis = G._long_axis_of_points(ring)[0]
    live = list(range(4))
    pad = [True, False, False, False]        # v0 is the pad weld
    free = [1, 2, 3]                         # ...and is therefore pinned
    vals = list(base)
    G._chord_cut_and_fill(ring, vals, live, free, C.SERVICE_ROAD_MAX_GRADE,
                          axis=axis, pad=pad)
    assert vals[0] == pytest.approx(base[0]), "the pad node must not move"
    # v0-v3 is the frontage chord: it keeps the value it had, so the
    # chord the law prices at 1 % is not blown open by the 2 % band.
    assert vals[3] == pytest.approx(base[3]), (
        "the 2 % band pulled the road end of a frontage chord away from "
        "its pad — the exact HECA site-B regression this exempts")


def test_without_a_pad_the_same_ring_still_clamps():
    """The exemption must be scoped to the frontage pair, not a licence
    for the ring: the identical geometry with no pad claim still clamps
    to the cross-section limit."""
    from auto_patch import groundside as G
    ring, base = _pad_ring()
    axis = G._long_axis_of_points(ring)[0]
    live = free = list(range(4))
    vals = list(base)
    G._chord_cut_and_fill(ring, vals, live, free, C.SERVICE_ROAD_MAX_GRADE,
                          axis=axis, pad=None)
    assert _lateral_pct(ring, vals) <= (
        C.SERVICE_ROAD_MAX_TRANSVERSE * 100.0 + 1e-6)


def test_a_pad_pair_still_holds_the_road_longitudinal_cap():
    """RELAXING ONLY relative to the CROSS-SECTION.  A frontage pair
    reverts to its pre-25g longitudinal reading — never to no law at
    all."""
    from auto_patch import groundside as G
    ring = [(0.0, 0.0), (120.0, 0.0), (120.0, 6.0), (0.0, 6.0)]
    vals = [10.0, 40.0, 40.0, 10.0]          # 25 % ALONG the axis
    axis = G._long_axis_of_points(ring)[0]
    live = free = list(range(4))
    pad = [True, True, True, True]           # every vertex a pad weld
    out = list(vals)
    G._chord_cut_and_fill(ring, out, live, free, C.SERVICE_ROAD_MAX_GRADE,
                          axis=axis, pad=pad)
    worst = max(abs(out[1] - out[0]), abs(out[2] - out[3])) / 120.0
    assert worst <= C.SERVICE_ROAD_MAX_GRADE + 1e-6


def test_the_late_pass_uses_THE_LAWS_claim_set_not_a_ring_walk():
    """THE LAW'S CLAIM SET IS THE PIN SET (owner ruling).

    ``ctx.building_keys`` has TWO populations and both are the claim: a
    building RING VERTEX, and an ON-EDGE node within
    ``SHARED_VERTEX_TOL_M`` of a pad BOUNDARY that is not a ring vertex
    (the pad only acquires the shared vertex later, at the nid weld).

    THE MISS THIS PINS.  The first implementation re-derived the claim
    from ring vertices alone, so the exemption no-op'd exactly where the
    regression was — HECA site B's frontage pairs are population (2) and
    15 rows held at 6.04 m / 37.6 % across a whole verification build.
    """
    from auto_patch import groundside as G
    from auto_patch import grade_graph as GG
    import inspect
    # The limiter DELEGATES to the law's claim; it does not walk rings.
    assert "building_claim" in inspect.getsource(G._pad_claim)
    # ...and build_context uses the very same object, so the law's claim
    # set and the pin set are one population by construction.
    assert "BuildingClaim(" in inspect.getsource(GG.build_context)


def test_a_proximity_zone_road_node_holds_under_the_late_pass():
    """THE POPULATION THAT WAS MISSED, end to end through the real pass.

    A road ring whose vertex is NOT a pad ring vertex but lies within
    ``SHARED_VERTEX_TOL_M`` of a pad boundary.  Under the ring-walk
    implementation this node was not claimed and the 2 % band pulled it;
    with the law's own claim set it holds.
    """
    from shapely.geometry import Polygon
    from auto_patch import groundside as G
    from auto_patch.layout import SHARED_VERTEX_TOL_M as TOL

    class _S:
        def __init__(self, role, polygon):
            self.role, self.polygon = role, polygon

    class _L:
        canonical_points = None

        def __init__(self, shapes):
            self.shapes = shapes

    # A pad whose BOUNDARY runs along y = 0; the road ring's v0 sits
    # 0.4*tol away from it and is NOT one of the pad's ring vertices.
    pad = Polygon([(-50.0, -20.0), (200.0, -20.0), (200.0, 0.0),
                   (-50.0, 0.0)])
    layout = _L([_S("building", pad)])
    claim = G._pad_claim(layout)
    ring = [(0.0, TOL * 0.4), (120.0, 0.0), (120.0, 6.0), (0.0, 6.0)]
    flags = [claim.contains(x, y) for (x, y) in ring]
    assert flags[0], ("the proximity-zone node was not claimed — this is "
                      "exactly the HECA site-B population the ring walk "
                      "missed")
    assert not flags[2] and not flags[3]

    axis = G._long_axis_of_points(ring)[0]
    base = [10.00, 10.30, 10.60, 10.30]
    vals = list(base)
    G._chord_cut_and_fill(ring, vals, list(range(4)), [1, 2, 3],
                          C.SERVICE_ROAD_MAX_GRADE, axis=axis, pad=flags)
    assert vals[0] == pytest.approx(base[0])
    assert vals[3] == pytest.approx(base[3]), (
        "the 2 % band pulled the road end of a frontage chord whose pad "
        "contact is an ON-EDGE claim")


def test_the_claim_covers_BOTH_populations():
    from auto_patch.grade_graph import BuildingClaim
    from auto_patch.layout import SHARED_VERTEX_TOL_M as TOL
    from shapely.geometry import Polygon
    claim = BuildingClaim([Polygon([(0, 0), (20, 0), (20, 20), (0, 20)])],
                          TOL)
    assert claim
    assert claim.contains(0.0, 0.0)          # (1) a ring VERTEX
    assert claim.contains(10.0, 0.0)         # (2) ON-EDGE, not a vertex
    assert claim.contains(10.0, TOL * 0.4)   # (2) within the weld tolerance
    assert not claim.contains(10.0, -5.0)    # plainly off the pad
    assert not claim.contains(10.0, 10.0)    # pad INTERIOR is not a claim


def test_the_pad_is_already_pinned_by_the_airside_set():
    """The measured fact this whole exemption rests on: a pad node is
    ALREADY pinned, because ``building`` is not a groundside role.  If
    that ever changes, the exemption alone would stop being enough and
    this twin says so."""
    from auto_patch.layout import (GROUNDSIDE_ROLES, ROLE_BUILDING,
                                   ROLE_OBJECT_PAD)
    assert ROLE_BUILDING not in GROUNDSIDE_ROLES
    assert ROLE_OBJECT_PAD not in GROUNDSIDE_ROLES


def test_a_spine_pair_is_never_a_cross_section():
    """THE CENTERLINE OUTRANKS THE BOUNDING BOX.

    A spine pair IS the road's travel path — that is what a centerline
    is — while the ring's minimum-area axis is only a PROXY for that
    direction, and ``long_axis_of_points`` says so itself ("a blobby
    service JUNCTION has no natural axis ... a shared convention").  A
    shared convention is not an authority.

    MEASURED (CYXY ``test_cyxy_spine_zero``, a zero-tolerance gate that
    passes on main): without this clause the classifier priced 8
    service_junction SPINE edges as cross-sections — the through-route
    of a junction whose bounding box is wider than it is long — and the
    solve then could not meet even the road's own LONGITUDINAL cap
    there (two edges at 14.6 % against cap 8.0).
    """
    common = dict(role="service_road", dist=6.0, ring_adjacent=True,
                  a_seam=False, b_seam=False,
                  a_building=False, b_building=False,
                  body_cap=C.SERVICE_ROAD_MAX_GRADE,
                  transverse_road=True)
    body = GL.classify_pair(GL.PairContext(spine_caps=(), **common))
    spine = GL.classify_pair(GL.PairContext(
        spine_caps=(C.SERVICE_ROAD_MAX_GRADE,), **common))
    assert body.flat_cap() == pytest.approx(C.SERVICE_ROAD_MAX_TRANSVERSE)
    assert spine.flat_cap() == pytest.approx(C.SERVICE_ROAD_MAX_GRADE), (
        "a road's own travel direction was capped at its cross-section "
        "rate — the bounding-box proxy overriding the centerline")


def test_the_family_is_registered_in_its_emission_position(cg):
    """``LAW_FAMILIES`` order IS the emission order (``test_harness.py``
    asserts the returned lists rebuild from it).  The cross-section rides
    the within-shape pair walk, so it is emitted directly after it."""
    keys = [k for k, _t, _b in cg.LAW_FAMILIES]
    assert keys.index("road_cross_section") == keys.index("within_shape") + 1
    bucket = next(b for k, _t, b in cg.LAW_FAMILIES
                  if k == "road_cross_section")
    assert bucket == "within"
