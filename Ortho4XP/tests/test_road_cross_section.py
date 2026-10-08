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
# SEAM S4 (v1 retirement round 1, 2026-09-17; RULINGS 2026-09-13aw ruling
# (d)): tools/check_grade.py may not import the v1 tree, so the CENSUS
# half of this law lives in tools/harness/law_support/grade_law.py and the
# v1 emitter half stays in auto_patch.grade_law.  Identity is asserted
# within each half below; tests/test_law_support.py holds the textual
# identity of the copy against its source while the v1 tree is on disk.
sys.path.insert(0, str(ROOT / "tools"))                       # noqa: E402


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


# ══════════════════════════════════════════════════════════════════════
# §2 THE SOLVE PRICES WHAT THE CENSUS PRICES
# ══════════════════════════════════════════════════════════════════════


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
        path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
        Path(str(path) + ".axes.json").write_text(json.dumps(
            {"anchor": list(ANCHOR), "ruleset": "icao"}), encoding="utf-8", newline="")
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
    running over its chord cap along its own axis is still a
    ``within_shape`` row."""
    p = _Patch(cg)
    # 120 m long, two points over the road cap ALONG the axis, laterally flat.
    top = 10.0 + (cg.SERVICE_ROAD_MAX_GRADE + 0.02) * 120.0
    p.ring([(0.0, 0.0, 10.0), (120.0, 0.0, top),
            (120.0, 6.0, top), (0.0, 6.0, 10.0)],
           {"role": "service_road", "shapeID": "R2"})
    osm = p.write(tmp_path / "LONG_auto.patch.osm")
    fam: dict = {}
    cg.run_checks(osm, top_n=0, quiet=True, family_out=fam)
    assert fam["within_shape"], "the over-cap longitudinal grade vanished"
    assert not fam["road_cross_section"], (
        "a laterally FLAT road minted cross-section rows")


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


def test_the_family_is_registered_in_its_emission_position(cg):
    """``LAW_FAMILIES`` order IS the emission order (``test_harness.py``
    asserts the returned lists rebuild from it).  The cross-section rides
    the within-shape pair walk, so it is emitted directly after it."""
    keys = [k for k, _t, _b in cg.LAW_FAMILIES]
    assert keys.index("road_cross_section") == keys.index("within_shape") + 1
    bucket = next(b for k, _t, b in cg.LAW_FAMILIES
                  if k == "road_cross_section")
    assert bucket == "within"
