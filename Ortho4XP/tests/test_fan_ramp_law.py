"""THE FAN-RAMP LAW — the generation-binding twins.

Owner ruling ``docs/RULINGS.md`` 2026-08-05 (commit 21f0980), all four
clarifications answered:

  1. RAMP CAP: 5 % — the groundside-pavement class; no new constant.
  2. FORM PRECEDENCE: ramps FIRST; a declared wall/step is the FALLBACK
     only where 5 % cannot span the demand within the zone.
  3. ZONE: bounded by adjacent buildings' frontage chords, the back apron
     edge, and standard clearance from every spine corridor.
  4. SCOPE: GENERAL — every apron with building frontage.

And the composition clause: "aircraft-movement surfaces (spine corridors
+ frontage chords + stand entries) hold the strict apron cap, always …
no ramp, joint, or wall may touch any movement surface."

The twins drive the REAL zone builder and the REAL cap rewriters on
synthetic layouts — the same discipline the terrace twins keep — and the
last one asserts the LOCKSTEP: the solver's predicate and
``check_grade``'s predicate are the same question asked of the same
geometry, which is the only thing that stops a lawful ramp being
censused as a violation (the named precedent in this repo's CLAUDE.md).
"""
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch.config import APRON_MAX_GRADE, GROUNDSIDE_MAX_GRADE

# ── FAN ZONES ARE RETIRED (W2, 2026-08-08) — THIS FILE IS THE OFF ARM ─
# Owner, verbatim (RULINGS 2026-08-08 THE FABRIC MODEL, scope answer 1):
# "Fan zones RETIRE OUTRIGHT (they compensated for dense emission)";
# reg-set §5.1 T1.  On a default build no plan is created and the split
# refuses at its own entry, which is the successor behaviour, twinned in
# ``tests/test_fabric_phase_b.py``.  This whole file is the FAN LAW as
# it was, kept because it is what certifies the OFF arm of
# ``O4_FABRIC_W2_RETIRE_FANS`` — a retired family whose machinery still
# has to behave when the flag reverts it.
@pytest.fixture(autouse=True)
def _pre_w2_fan_zones(monkeypatch):
    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_FANS", "0")


class _Centerline:
    def __init__(self, pts):
        self.line = LineString(pts)


class _Layout:
    def __init__(self, shapes, centerlines=()):
        self.shapes = list(shapes)
        self.apt_taxi_centerlines = [_Centerline(p) for p in centerlines]
        self.anchor = (0.0, 0.0)

    def m_to_ll(self, x, y):
        return (30.0 + y / 111320.0, 31.0 + x / 96000.0)


# ── 1. THE ZONE ─────────────────────────────────────────────────────


# ── 2. THE CAP, AND WHO KEEPS THE STRICT ONE ────────────────────────


# ── 3. PRECEDENCE: ramps first, wall fallback ───────────────────────

def _pinned(z_fn):
    def _env(x, y):
        z = z_fn(x, y)
        return None if z is None else (float(z), float(z))
    return _env


# ── 4. THE LOCKSTEP — one declaration, two readers ──────────────────


def test_the_new_sidecar_key_is_registered_with_a_reader():
    """Every emitted sidecar key must be law input or declared evidence —
    ``tests/test_harness.py`` twin-asserts it, and this names the one
    this law adds so a future reader cannot silently ignore it."""
    import check_grade as CG
    assert CG.SIDECAR_LAW_KEYS["fan_ramp_zones"] == "fan_ramp_zones_ll"


def test_a_patch_predating_the_law_is_judged_exactly_as_before():
    import check_grade as CG
    assert CG._fan_ramp_zones_to_m(None, lambda a, b: (a, b)) == []
    assert CG._fan_ramp_pair_cap([], 0.0, 0.0, 1.0, 1.0) is None


# ── 5. ACTIVATION — the zone is a SHAPE, not a region in one ────────
#
# The law above is correct and was INERT.  Measured on HECA's plateau
# build: 808 declared zones, 295 526 m² of movement-clear apron, and 170
# within-apron edges raised.  The cause is structural — the chord
# predicate can only raise a pair that EXISTS, an apron's solve variables
# are its RING vertices, and a fan-ramp zone is interior ground.  Of
# 10 255 within-apron census rows, 9 739 had neither endpoint in any zone
# and 9 were blocked by the whole-chord test.
#
# These twins bind the fix: the zone is CUT OUT before the solve, so it
# has ring vertices of its own and its interior pairs are its own
# all-pairs at 5 %.


def test_the_emitted_tag_and_the_solver_read_ONE_law():
    """THE LOCKSTEP, in its shipped form.  The build stamps
    ``o4_grade_law='fan_ramp'``; the census turns that tag back into the
    same ``GradeShape`` field the solver set, so both sides reach the cap
    through ``config.fan_ramp_law_cap`` and cannot drift."""
    import check_grade as CG
    from auto_patch.config import FAN_RAMP_LAW, fan_ramp_law_cap

    assert fan_ramp_law_cap(FAN_RAMP_LAW) == pytest.approx(
        GROUNDSIDE_MAX_GRADE)
    assert fan_ramp_law_cap("apron") is None
    assert fan_ramp_law_cap(None) is None

    class _W:
        tags = {"role": "apron", "o4_grade_law": FAN_RAMP_LAW}

    class _P:
        tags = {"role": "apron"}

    assert CG._role_grade_limit(_W(), APRON_MAX_GRADE) == pytest.approx(
        GROUNDSIDE_MAX_GRADE)
    assert CG._role_grade_limit(_P(), APRON_MAX_GRADE) == pytest.approx(
        APRON_MAX_GRADE)


# ── THE LATTICE-COARSE SUPERSET COVER (cycle-5 node-identity RULING
#    2026-08-06) ────────────────────────────────────────────────────────
# The zone is CUT against a coarsened SUPERSET of the true movement
# cover, because the true cover is a ``buffer()`` whose arc vertices are
# spaced at about the canonical weld tolerance — cutting against it borns
# the zone with vertex pairs the canonical registry interns onto ONE
# solve node, and the ramp piece and the remainder panel then price that
# node's pairs under two different caps (CYXY: 0 such pairs on aprons
# before the cut, 884 after; 193 solver/validator budget mismatches).
# The ruling's two properties are twinned here.


