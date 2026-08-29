"""STRICT CLAIM AT A SHARED NODE — owner ruling RULINGS 2026-08-29c.

Spec: ``docs/specs/runway-crossing-strict-claim-spec.md``.  Verbatim
owner intent: "a service corridor joining an apron should not be any
different than a runway: it should exactly match the airside elevation —
why would it need to be re-capped?"  A CONTACT IS A VALUE QUESTION,
NEVER A CAP QUESTION.

WHAT WAS MEASURED, and why each twin here exists.  On the owner's own
HECA patch (engine 1.50.1710, built 2026-08-29 10:27) the service
corridor -12136 crosses runway 05C/23C's ring -12210.  Two separate
leaks, one twin family each:

* §1 THE CAP LEAK.  ``grade_law.classify_pair``'s road-carve relaxation
  raised the cap to ``SERVICE_ROAD_MAX_GRADE`` for ANY host whose pair
  had both endpoints in the road-carve zone — with no guard on the
  host's own role.  Ring -12210 therefore carried THREE
  ``within_shape runway|runway`` rows priced at cap 8.0 (101.53 %,
  85.19 %, 59.26 %) while the same ring's rows 22-30 m away carried the
  lawful 1.5.  A runway|runway row at a foreign cap is structurally
  impossible under the ruling — that is what §2 asserts, on the census
  itself, so it cannot come back through a different reader.

* §3 THE GATE.  ``O4_STRICT_CLAIM_CAP=0`` restores the unguarded
  relaxation byte for byte, so the ON arm is attributable on its own.

The rank is NOT re-derived here: ``layout.AUTHORITY_PRECEDENCE`` is
already the ruling's order (runway > taxi family > apron > building >
road > groundside) and is what ``to_osm`` uses to pick the one author of
a shared node.  A second rank table is this campaign's two-instruments
defect class.

These twins are hermetic: no X-Plane install, no airport build.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from auto_patch import config as C                          # noqa: E402
from auto_patch import grade_law as GL                      # noqa: E402
from auto_patch import layout as L                          # noqa: E402

# The emitted-patch builder and the harness-library loader are REUSED,
# never re-spelled: a second almost-identical fixture writer is the
# census-wrapper defect class.
from test_road_cross_section import _Patch, _load           # noqa: E402


@pytest.fixture(scope="module")
def cg():
    return _load("strictclaim_twin_check_grade",
                 ROOT / "tools" / "check_grade.py")


RUNWAY_CAP = C.ROLE_GRADE_LIMITS["runway"]
ROAD_CAP = C.SERVICE_ROAD_MAX_GRADE


def _pair(role: str, *, body_cap: float, both_road: bool = True,
          dist: float = 3.0) -> float:
    """The cap ``classify_pair`` settles on for one carve pair."""
    allow = GL.classify_pair(GL.PairContext(
        role=role, dist=dist, ring_adjacent=True,
        a_seam=False, b_seam=False, a_building=False, b_building=False,
        spine_caps=(), body_cap=body_cap, both_road=both_road))
    assert allow is not None
    return allow.flat_cap()


# ══════════════════════════════════════════════════════════════════════
# §1 THE LAW — THE STRICTEST CLAIMANT'S CAP WINS AT A CARVE
# ══════════════════════════════════════════════════════════════════════

def test_a_road_carve_may_not_reprice_a_runway_pair():
    """The measured HECA leak, at the law: cap 8.0 on a runway pair."""
    assert _pair("runway", body_cap=RUNWAY_CAP) == pytest.approx(
        RUNWAY_CAP), (
        "a service-road carve re-priced a RUNWAY pair at the road class "
        "— HECA ring -12210 carried runway|runway rows at cap 8.0")


@pytest.mark.parametrize("role", [
    "runway", "runway_crossing",
    "primary_parallel", "secondary_parallel", "stub",
    "cross_connector", "junction",
    "apron",
])
def test_no_airside_host_is_repriced_by_a_road_carve(role):
    """Generalised (ruling: runway > taxi family > apron > road).  The
    owner's words: a corridor joining an APRON is not different from one
    joining a runway."""
    body = C.ROLE_GRADE_LIMITS.get(role, RUNWAY_CAP)
    assert _pair(role, body_cap=body) <= body + 1e-12, (
        f"the road carve relaxed {role} above its own law")


@pytest.mark.parametrize("role", ["service_road", "service_junction"])
def test_the_carved_road_itself_still_grades_at_the_road_class(role):
    """The relaxation's ONE legitimate job survives: the carved feature's
    own ring descends at the road class between contacts.  Losing this
    would re-price every free road at the host's cap — the round-5
    scoping defect, inverted."""
    assert _pair(role, body_cap=0.010) == pytest.approx(ROAD_CAP)


def test_a_cross_shape_pair_is_claimed_by_rank_not_by_the_smaller_cap():
    """THE SECOND READER.  ``airside_no_step`` prices a CROSS-SHAPE pair
    under whichever side carries the smaller body cap — a cap question,
    which says nothing about who claims the contact.  A
    ``runway|service_junction`` pair therefore took the road carve's 8 %
    even with the within-shape guard on (measured at HECA: 1 surviving
    row).  ``claim_role`` carries the rank answer."""
    assert GL.strictest_claim_role("service_junction", "runway") == "runway"
    assert GL.strictest_claim_role("apron", "service_road") == "apron"
    assert GL.strictest_claim_role("junction", "apron") == "junction"

    # priced under the service junction's tighter body cap, claimed by
    # the runway: the road relaxation must not fire
    allow = GL.classify_pair(GL.PairContext(
        role="service_junction", dist=6.0, ring_adjacent=False,
        a_seam=False, b_seam=False, a_building=False, b_building=False,
        spine_caps=(), body_cap=0.010, both_road=True,
        claim_role=GL.strictest_claim_role("service_junction", "runway")))
    assert allow.flat_cap() == pytest.approx(0.010), (
        "a runway-claimed contact took the 8 % road relaxation")


def test_a_pure_road_cross_shape_pair_still_relaxes():
    """The claim only ever TIGHTENS: two road shapes meeting still grade
    at the road class."""
    allow = GL.classify_pair(GL.PairContext(
        role="service_junction", dist=6.0, ring_adjacent=False,
        a_seam=False, b_seam=False, a_building=False, b_building=False,
        spine_caps=(), body_cap=0.010, both_road=True,
        claim_role=GL.strictest_claim_role("service_junction",
                                           "service_road")))
    assert allow.flat_cap() == pytest.approx(ROAD_CAP)


def test_the_rank_is_the_emit_authority_order_not_a_second_table():
    """One rank table.  If ``AUTHORITY_PRECEDENCE`` is ever reordered,
    this law follows it — that is the point of reading it."""
    assert (L.authority_rank("runway")
            < L.authority_rank("junction")
            < L.authority_rank("apron")
            < L.authority_rank("service_road")
            <= L.authority_rank("service_junction")
            < L.authority_rank("groundside_pavement"))
    assert GL._road_carve_outranked_by_host("runway") is True
    assert GL._road_carve_outranked_by_host("service_road") is False


# ══════════════════════════════════════════════════════════════════════
# §2 THE CENSUS — A runway|runway ROW AT A FOREIGN CAP IS IMPOSSIBLE
# ══════════════════════════════════════════════════════════════════════

#: THE HECA CROSSING, minimally.  A runway ring with three closely
#: spaced edge vertices where a service corridor pierces it, the middle
#: one sitting 0.10 m low — 3.3 % over 3 m.  That is OVER the runway's
#: 1.5 % and UNDER the road's 8 %, so before the ruling it censused
#: ZERO, exactly as HECA's real rows censused at the wrong cap.  The
#: road ring's 3 m carve buffer covers all three vertices.
def _crossing_patch(cg, tmp_path: Path) -> Path:
    p = _Patch(cg)
    p.ring([(0.0, 0.0, 100.00), (95.0, 0.0, 100.00),
            (98.0, 0.0, 99.90), (101.0, 0.0, 100.00),
            (200.0, 0.0, 100.00),
            (200.0, 45.0, 100.00), (0.0, 45.0, 100.00)],
           {"role": "runway", "aeroway": "runway", "ref": "09/27",
            "shapeID": "2210"})
    p.ring([(94.0, -20.0, 96.00), (102.0, -20.0, 96.00),
            (102.0, 20.0, 99.90), (94.0, 20.0, 99.90)],
           {"role": "service_junction", "aeroway": "taxiway",
            "ref": "service", "shapeID": "2136"})
    return p.write(tmp_path / "XING_auto.patch.osm")


def _runway_rows(cg, path):
    fam: dict = {}
    cg.run_checks(path, top_n=0, quiet=True, family_out=fam)
    return [r for r in fam["within_shape"]
            if cg.row_roles(r) == ("runway", "runway")]


def test_the_crossing_pair_censuses_at_the_runway_cap(cg, tmp_path):
    rows = _runway_rows(cg, _crossing_patch(cg, tmp_path))
    assert rows, ("the 3.3 % runway pair inside the road carve censused "
                  "NOTHING — this is the HECA cap leak")
    assert all(r.cap_pct == pytest.approx(RUNWAY_CAP * 100)
               for r in rows), (
        "a runway|runway row carried a cap other than the runway's: "
        + repr(sorted({r.cap_pct for r in rows})))


def test_no_runway_row_anywhere_carries_a_foreign_cap(cg, tmp_path):
    """The acceptance clause, as an invariant over EVERY family that
    prices a per-pair cap — not just the one the defect surfaced in."""
    fam: dict = {}
    cg.run_checks(_crossing_patch(cg, tmp_path), top_n=0, quiet=True,
                  family_out=fam)
    bad = []
    for key, rows in fam.items():
        for r in (rows or ()):
            cap = getattr(r, "cap_pct", None)
            if cap is None:
                continue
            if cg.row_roles(r) == ("runway", "runway") and cap > (
                    RUNWAY_CAP * 100 + 1e-9):
                bad.append((key, cg.row_roles(r), cap))
    assert not bad, f"runway rows at a foreign cap: {bad}"


# ══════════════════════════════════════════════════════════════════════
# §3 THE GATE — OFF IS THE PRE-RULING LAW
# ══════════════════════════════════════════════════════════════════════

def test_gate_off_restores_the_unguarded_relaxation(monkeypatch):
    monkeypatch.setattr(C, "STRICT_CLAIM_CAP", False, raising=False)
    assert _pair("runway", body_cap=RUNWAY_CAP) == pytest.approx(
        ROAD_CAP), "OFF must reproduce the pre-ruling cap 8.0"


def test_gate_off_restores_the_census_reading(cg, tmp_path, monkeypatch):
    monkeypatch.setattr(C, "STRICT_CLAIM_CAP", False, raising=False)
    rows = _runway_rows(cg, _crossing_patch(cg, tmp_path))
    assert not rows, ("with the gate OFF the 3.3 % runway pair must be "
                      "invisible again — that is what BYTE-IDENTICAL "
                      "means for this arm")


def test_the_gate_is_default_on():
    assert C.STRICT_CLAIM_CAP is True
    assert C.STRICT_CLAIM_VALUE is True
