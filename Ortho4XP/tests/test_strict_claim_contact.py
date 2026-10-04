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


# ══════════════════════════════════════════════════════════════════════
# §1 THE LAW — THE STRICTEST CLAIMANT'S CAP WINS AT A CARVE
# ══════════════════════════════════════════════════════════════════════


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


def test_gate_off_restores_the_census_reading(cg, tmp_path, monkeypatch):
    monkeypatch.setattr(C, "STRICT_CLAIM_CAP", False, raising=False)
    rows = _runway_rows(cg, _crossing_patch(cg, tmp_path))
    assert not rows, ("with the gate OFF the 3.3 % runway pair must be "
                      "invisible again — that is what BYTE-IDENTICAL "
                      "means for this arm")


def test_the_gate_is_default_on():
    assert C.STRICT_CLAIM_CAP is True
    assert C.STRICT_CLAIM_VALUE is True
