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
        importlib.reload(C)
        importlib.reload(GL)
        importlib.reload(GG)


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
    for m in ("auto_patch.config", "auto_patch.grade_law",
              "auto_patch.grade_graph"):
        importlib.reload(sys.modules[m])
    cg2 = _load("xsec_twin_check_grade_off", ROOT / "tools" / "check_grade.py")
    try:
        assert cg2._ROAD_XSECTION_LAW is False
        fam: dict = {}
        cg2.run_checks(osm, top_n=0, quiet=True, family_out=fam)
        assert fam["road_cross_section"] == []
    finally:
        monkeypatch.delenv("O4_ROAD_CROSS_SECTION_LAW", raising=False)
        for m in ("auto_patch.config", "auto_patch.grade_law",
                  "auto_patch.grade_graph"):
            importlib.reload(sys.modules[m])


def test_the_family_is_registered_in_its_emission_position(cg):
    """``LAW_FAMILIES`` order IS the emission order (``test_harness.py``
    asserts the returned lists rebuild from it).  The cross-section rides
    the within-shape pair walk, so it is emitted directly after it."""
    keys = [k for k, _t, _b in cg.LAW_FAMILIES]
    assert keys.index("road_cross_section") == keys.index("within_shape") + 1
    bucket = next(b for k, _t, b in cg.LAW_FAMILIES
                  if k == "road_cross_section")
    assert bucket == "within"
