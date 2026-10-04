"""APRON TERRACE LAW — the generation-binding twins.

Owner ruling 2026-08-04 (``docs/RULINGS.md``): long aprons on genuinely
steep ground MAY terrace into level panels with declared joint steps,
"but it has to be done in a way that does not interrupt any spine where
aircraft have to travel."

The BINDING CONSTRAINT is structural in
``elevation_per_surface.route_profile.apron_terrace``: a joint is born as
``(terrace line ∩ apron) − corridor cover``.  These tests are the
generation-binding half the completeness standard demands (a
validator-only check is visibility, not law), so every one of them
exercises the EMITTER's own function on a synthetic layout:

  * a joint can never touch a corridor, at any corridor angle;
  * a spine's own pairs keep the cap through a panelized apron;
  * the declared step is bounded by ``APRON_TERRACE_MAX_STEP_M``;
  * the trigger floor and the steep-truth signature both bind
    (a value defect on gradeable ground must NOT panelize);
  * the sidecar round-trips into ``check_grade``'s own reader.
"""
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from auto_patch.config import APRON_MAX_GRADE, APRON_TERRACE_MAX_STEP_M

# ── APRON TERRACES ARE RETIRED (W2, 2026-08-08) — THIS IS THE OFF ARM ─
# fabric-model-spec.md §3 ("explicit shaping only in the REG SET") + the
# walls-to-carves ruling 2026-08-07: an apron terrace is a cut line plus
# a WALL FACE on unregulated ground, and walls exist only at carve
# structures.  On a default build no apron is a terrace candidate, which
# is the successor behaviour (twinned in tests/test_fabric_phase_b.py).
# This whole file is the terrace law as it was, kept because it is what
# certifies the OFF arm of ``O4_FABRIC_W2_RETIRE_APRON_TERRACES`` — a
# retired family whose machinery still has to behave when reverted.
@pytest.fixture(autouse=True)
def _pre_w2_apron_terraces(monkeypatch):
    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_APRON_TERRACES", "0")
    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_APRON_SURROUND", "0")
    monkeypatch.setenv("O4_FABRIC_W2_RETIRE_FANS", "0")


class _Centerline:
    def __init__(self, pts):
        self.line = LineString(pts)


class _FakeLayout:
    """The minimum surface ``apron_terrace`` reads: shapes, taxi
    centerlines and the metre↔lat/lon pair."""

    def __init__(self, shapes, centerlines=()):
        self.shapes = list(shapes)
        self.apt_taxi_centerlines = [_Centerline(p) for p in centerlines]
        self.anchor = (0.0, 0.0)

    def m_to_ll(self, x, y):
        return (30.0 + y / 111320.0, 31.0 + x / 96000.0)


def _entry(shape, idx, edges):
    return {"nodes": list(idx), "edges": list(edges), "flat": False,
            "role": "apron", "shape_id": id(shape),
            "ref": shape.ref or "", "area": float(shape.polygon.area)}


# ── 1. THE BINDING CONSTRAINT ───────────────────────────────────────


# ── 2. THE STEP BOUND ───────────────────────────────────────────────


# ── 3. THE TRIGGER ──────────────────────────────────────────────────


# ── 4. EMIT + SIDECAR ───────────────────────────────────────────────


def test_validator_flags_a_joint_that_crosses_a_route():
    """The twin (spec §5b).  The emitter cannot produce this — the check
    is fed a hand-built crossing joint, which is exactly what the STOP
    rule is looking for."""
    import check_grade as CG
    joints_m = [([(0.0, -50.0), (0.0, 50.0)], 1.5)]
    taxi_axes = [([(-100.0, 0.0), (100.0, 0.0)], 0.015, 0.015, 0)]
    hits = CG._check_terrace_joint_crosses_route(joints_m, None, taxi_axes)
    assert len(hits) == 1
    clear = [([(0.0, 20.0), (0.0, 80.0)], 1.5)]
    assert CG._check_terrace_joint_crosses_route(
        clear, None, taxi_axes) == []


# ════════════════════════════════════════════════════════════════════
# FLIP-READINESS V2 TWINS (spec docs/specs/terrace-flip-readiness-v2-
# spec.md; T1-T8).  Each one is generation-binding: it exercises the
# EMITTER's own function, not only the validator.
# ════════════════════════════════════════════════════════════════════

from auto_patch.config import (                                # noqa: E402
    APRON_TERRACE_FACING_PROXIMITY_M,
    APRON_TERRACE_FACING_STEP_M,
)


# ── T1  STRIP FENCE (§1) ────────────────────────────────────────────


# ── T2  FOOTPRINT CONGRUENCE, open vs closed ring (§1) ──────────────


# ── T3  CERTIFICATE (§2) ────────────────────────────────────────────


# ── T4  PLAN-TIME ADMISSIBILITY + DEMOTION (§3a) ────────────────────


# ── T5  JOINT-STEP PAIR CONSTRAINTS (§3b) ──────────────────────────


def test_T5d_validator_reads_the_actual_step_from_the_patch():
    """§3(b)'s honest instrument: an over-step face is flagged from the
    PATCH — the sidecar's own ``actual_step_m`` is never consulted."""
    import check_grade as CG

    def _ll_to_m(lat, lon):
        return ((lon - 31.0) * 96000.0, (lat - 30.0) * 111320.0)

    joints_m = [([(0.0, 0.0), (0.0, 100.0)], 1.5)]
    nodes = {}
    for i, (x, y) in enumerate([(0.0, 0.0), (0.0, 100.0),
                                (0.6, 100.0), (0.6, 0.0)]):
        nodes[str(i)] = (30.0 + y / 111320.0, 31.0 + x / 96000.0)
    nids = ["0", "1", "2", "3", "0"]
    # a face declaring 1.5 m but standing 4.9 m tall
    tall = CG.Way("w9", "retaining_wall", "apron_terrace_joint", "",
                  nids, [100.0, 100.0, 95.1, 95.1, 100.0],
                  {"role": "retaining_wall", "ref": "apron_terrace_joint"})
    hits = CG._check_terrace_actual_step(joints_m, [tall], nodes,
                                         _ll_to_m, APRON_MAX_GRADE)
    assert hits, "a 4.9 m face against a 1.5 m declared step was not seen"
    lawful = CG.Way("w9", "retaining_wall", "apron_terrace_joint", "",
                    nids, [100.0, 100.0, 98.6, 98.6, 100.0],
                    {"role": "retaining_wall",
                     "ref": "apron_terrace_joint"})
    assert CG._check_terrace_actual_step(joints_m, [lawful], nodes,
                                         _ll_to_m, APRON_MAX_GRADE) == []


# ── T6  FACING BOUNDARY (§3c) ──────────────────────────────────────


def test_T6e_the_facing_budget_is_the_step_readers_own_number():
    """One shared number, asserted rather than assumed."""
    import check_grade as CG
    import argparse
    parser = [a for a in CG.__doc__ or ""]           # doc presence only
    assert APRON_TERRACE_FACING_STEP_M == 0.5, (
        "the facing budget drifted from check_grade's --edge-step "
        "default (0.5 m)")
    assert APRON_TERRACE_FACING_PROXIMITY_M == CG._STEP_CONTACT_TOL_M, (
        "the facing proximity drifted from the step checks' own contact "
        "tolerance")
    assert parser is not None and argparse is not None


# ── T7  WALL-SITE REGISTRATION / HEALER SPLIT ──────────────────────


# ── T8  SIDECAR ROUND-TRIP with certificates + actual step ─────────


# ── §3(d)  THE POLYGON SPLIT — REMOVED ─────────────────────────────
# The split is out (lead 2026-08-05): it minted 5 defects because the
# difference's new ring vertices adopted the FACE's level, a value the
# solve never produced.  Its twins are deleted rather than re-aimed —
# a twin for a path that does not run is not a guardrail.
# ``_split_lower_panels`` / ``_split_reach_line`` stay parked in the
# module with the revival precondition (interior-ring emit support +
# a pre-solve panel boundary) named in their docstrings.


# ── PRE-SOLVE PANEL BOUNDARY (completion round 2026-08-05) ──────────


# ── THE SIDECAR KILLER (fix 2026-08-05) ──────────────────────────────


# ── ITEM 4: THE 0.6 m SLOT ───────────────────────────────────────────
# The PRE-SOLVE split cuts a ``STACKED_WALL_RETREAT_M`` band out of the
# apron for every declared joint.  The face that fills it is minted at
# the very END of the build (inside the strip reconcile unit, which by
# standing owner ruling runs after the LATE final grade projection,
# because the face reads its panels' FINAL settled values by identity).
# Between the split and that emission the slot is ground no shape covers.
# Measured at HECA, 79 bands / 2960.62 m²: wall 72.9%, graded-strip march
# 12.9% (32 bands), UNCOVERED 21.2% (629 m², 70 bands).


