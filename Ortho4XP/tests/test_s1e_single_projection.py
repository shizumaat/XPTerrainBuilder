"""S1e TWINS — the single projection and the two value-carry laws.

Owner ruling 2026-08-14, "THE DOUBLE PROJECTION RETIRES; THE ROUND DOES NOT
CLOSE WITHOUT IT" (RULINGS.md), superseding the 2026-07-18 keep-both
ruling.  Its acceptance list is three items; two of them are structural and
are twinned here (the third, the census, is an arm):

  1. the pipeline runs ONE ``final_grade_projection`` per build;
  2. post-solve refinement is VALUE-PRESERVING — it carries solved values
     through geometry operations by interpolation or by weld adoption,
     never by re-projection.

Both twins are cheap and offline: (1) is an AST fact about ``pipeline.py``,
(2) unit-tests the carry classifier that the geometry seam audit — the
lane's acceptance instrument — decides the RE-PROJECTION CLASS with.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from auto_patch.geom_guard import (
    SEAM_MATERIAL_M,
    _classify_insert_values,
    _GROUNDSIDE_SIDE_ROLES,
)
from auto_patch.layout import GROUNDSIDE_ROLES, ROLE_SERVICE_JUNCTION


_PIPELINE = (pathlib.Path(__file__).resolve().parents[1]
             / "src" / "auto_patch" / "pipeline.py")

#: Every local alias the pipeline binds the projection to.  A future rename
#: that this list misses would make the twin blind, so the twin also
#: asserts the import sites it found — see
#: ``test_every_projection_import_alias_is_covered``.
_PROJECTION_NAMES = frozenset({"final_grade_projection", "_late_fgp"})


def _pipeline_tree() -> ast.AST:
    return ast.parse(_PIPELINE.read_text())


# ── (1) ONE PROJECTION ───────────────────────────────────────────────────

def test_the_pipeline_calls_the_grade_projection_exactly_once():
    """THE acceptance item: one ``final_grade_projection`` call per build.

    Counted structurally rather than by build log so a second call cannot
    be re-introduced and only noticed at the next measured arm.
    """
    calls = [n for n in ast.walk(_pipeline_tree())
             if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)
             and n.func.id in _PROJECTION_NAMES]
    assert len(calls) == 1, (
        "the pipeline must call final_grade_projection exactly ONCE "
        f"(owner ruling 2026-08-14); found {len(calls)} call(s) at "
        f"line(s) {[c.lineno for c in calls]}")


def test_every_projection_import_alias_is_covered_by_the_twin():
    """The twin's name list must cover every alias the pipeline binds.

    Without this, renaming the alias silently disarms the count above —
    the exact silent-drift shape ``blast.py`` flags for role literals.
    """
    aliases = set()
    for node in ast.walk(_pipeline_tree()):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "final_grade_projection":
                    aliases.add(a.asname or a.name)
    assert aliases, "the pipeline no longer imports final_grade_projection"
    assert aliases <= _PROJECTION_NAMES, (
        f"unknown projection alias(es) {sorted(aliases - _PROJECTION_NAMES)} "
        f"— add them to _PROJECTION_NAMES or the single-call twin goes "
        f"blind")


def test_the_one_projection_is_given_the_dem_frame():
    """The surviving call carries ``dem`` + tile frame.

    ``dem`` drives the flatness-certificate lazy tier; collapsing to one
    projection WITHOUT it would silently expand every certified-flat shape
    — a cost the collapse was run to remove, paid back invisibly.
    """
    call = next(n for n in ast.walk(_pipeline_tree())
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and n.func.id in _PROJECTION_NAMES)
    kw = {k.arg for k in call.keywords}
    assert {"dem", "tile_lat", "tile_lon"} <= kw, (
        f"the one projection must carry the DEM/tile frame; got {sorted(kw)}")


def test_the_projection_has_no_enabling_gate():
    """``O4_FINAL_PROJECTION_LATE`` is deleted (owner 2026-08-05, no gates).

    With one projection, turning it off leaves a build with NO grade
    projection — a law-breaking configuration, not an experiment.
    """
    reads = [n for n in ast.walk(_pipeline_tree())
             if isinstance(n, ast.Constant)
             and n.value == "O4_FINAL_PROJECTION_LATE"]
    assert not reads, (
        "O4_FINAL_PROJECTION_LATE is still read at line(s) "
        f"{[n.lineno for n in reads]} — with one projection a gate that "
        f"can switch it off is a law-breaking configuration")


# ── (2) THE CARRY LAWS ───────────────────────────────────────────────────

def _ring(*pts):
    return tuple((float(x), float(y)) for x, y in pts)


def test_a_densified_vertex_that_interpolates_its_span_is_carried():
    """The cut / densify law: interpolate along the edge."""
    prev_ring = _ring((0, 0), (100, 0), (100, 100))
    prev_alts = (10.0, 20.0, 30.0)
    cur_ring = _ring((0, 0), (25, 0), (100, 0), (100, 100))
    cur_alts = (10.0, 12.5, 20.0, 30.0)          # exact lerp at t = 0.25
    out = _classify_insert_values(prev_ring, prev_alts, cur_ring, cur_alts)
    assert out["inserted"] == 1
    assert out["lerp_exact"] == 1
    assert out["off_lerp"] == 0 and out["no_value"] == 0


def test_a_vertex_off_its_span_with_no_weld_partner_is_not_carried():
    """The class the ruling drives to zero: a value nothing justifies."""
    prev_ring = _ring((0, 0), (100, 0), (100, 100))
    prev_alts = (10.0, 20.0, 30.0)
    cur_ring = _ring((0, 0), (50, 0), (100, 0), (100, 100))
    cur_alts = (10.0, 17.0, 20.0, 30.0)          # lerp wants 15.0
    out = _classify_insert_values(prev_ring, prev_alts, cur_ring, cur_alts)
    assert out["off_lerp"] == 1
    assert out["worst_m"] == pytest.approx(2.0)
    assert out["sites"], "an un-carried insert must name its site"


def test_a_welded_vertex_adopts_the_shared_value_and_is_carried():
    """The weld law: a shared node has ONE value.

    Scoring a weld against the host edge's lerp would demand the weld
    re-tear the seam it was run to close — so where a neighbour already
    carries the value at that coordinate, the insert is value-preserving
    even though it is off the lerp.
    """
    prev_ring = _ring((0, 0), (100, 0), (100, 100))
    prev_alts = (10.0, 20.0, 30.0)
    cur_ring = _ring((0, 0), (50, 0), (100, 0), (100, 100))
    cur_alts = (10.0, 17.0, 20.0, 30.0)          # lerp wants 15.0
    shared = {(50.0, 0.0): {"neighbour": 17.0}}
    out = _classify_insert_values(prev_ring, prev_alts, cur_ring, cur_alts,
                                  shared_at=shared, self_key="me")
    assert out["weld_adopt"] == 1
    assert out["off_lerp"] == 0


def test_a_shapes_own_value_never_vouches_for_its_own_weld():
    """The weld evidence must come from ANOTHER shape.

    Otherwise every insert vouches for itself and the law is vacuous.
    """
    prev_ring = _ring((0, 0), (100, 0), (100, 100))
    prev_alts = (10.0, 20.0, 30.0)
    cur_ring = _ring((0, 0), (50, 0), (100, 0), (100, 100))
    cur_alts = (10.0, 17.0, 20.0, 30.0)
    shared = {(50.0, 0.0): {"me": 17.0}}
    out = _classify_insert_values(prev_ring, prev_alts, cur_ring, cur_alts,
                                  shared_at=shared, self_key="me")
    assert out["weld_adopt"] == 0
    assert out["off_lerp"] == 1


def test_a_valueless_insert_is_never_counted_as_carried():
    prev_ring = _ring((0, 0), (100, 0), (100, 100))
    prev_alts = (10.0, 20.0, 30.0)
    cur_ring = _ring((0, 0), (50, 0), (100, 0), (100, 100))
    cur_alts = (10.0, None, 20.0, 30.0)
    out = _classify_insert_values(prev_ring, prev_alts, cur_ring, cur_alts)
    assert out["no_value"] == 1
    assert out["lerp_exact"] == 0 and out["weld_adopt"] == 0


def test_the_near_class_sits_under_the_standing_materiality_floor():
    """``lerp_near`` is PASS-with-residual, never a silent widening.

    It must be bounded by the round's own 0.01 m elevation floor, so a
    stage cannot drift a decimetre and still read as carried.
    """
    prev_ring = _ring((0, 0), (100, 0), (100, 100))
    prev_alts = (10.0, 20.0, 30.0)
    cur_ring = _ring((0, 0), (50, 0), (100, 0), (100, 100))
    just_under = 15.0 + SEAM_MATERIAL_M * 0.5
    just_over = 15.0 + SEAM_MATERIAL_M * 2.0
    near = _classify_insert_values(
        prev_ring, prev_alts, cur_ring, (10.0, just_under, 20.0, 30.0))
    over = _classify_insert_values(
        prev_ring, prev_alts, cur_ring, (10.0, just_over, 20.0, 30.0))
    assert near["lerp_near"] == 1 and near["off_lerp"] == 0
    assert over["off_lerp"] == 1 and over["lerp_near"] == 0


# ── The population split the guard's headline number hides ───────────────

def test_the_stage_b_roles_the_audit_splits_out_are_the_solves_own():
    """The split must be keyed on the SOLVE's partition, not a second list.

    ``geom_guard._AIRSIDE_ROLES`` calls ``service_junction`` airside while
    ``layout.GROUNDSIDE_ROLES`` — the projection's RECEIVER set — puts it
    on the groundside side.  The audit books its post-solve authorship as
    stage-B seating; that carve-out is only legitimate while the role
    really is a groundside receiver, so the twin asserts the relation
    rather than the literal.
    """
    assert ROLE_SERVICE_JUNCTION in GROUNDSIDE_ROLES
    assert _GROUNDSIDE_SIDE_ROLES <= GROUNDSIDE_ROLES, (
        "a role the audit excuses as stage-B seating must actually be a "
        "groundside receiver in the solve partition")
