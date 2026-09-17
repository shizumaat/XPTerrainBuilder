"""§40 (5) (4) THE ``runway_step`` DEFECT FAMILY (Fable 2026-09-15; owner
RULINGS 2026-09-15az) and the two options §40 (5) added to the ONE step
reader they are stated through.

``runway_transverse`` is the CROWN reading — a vertex against the runway's
own AXIS at its lateral offset — so a pair 490 m off-axis is not a crown
pair and no DEFECT family priced a step between two faces of ONE role.
LEMD 40.4613609,-3.5446852 stepped 0.950 m over 1 m between two ``runway``
faces on rolled-on pavement while every DEFECT family read ZERO.
"""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import cliff_grade
from auto_patch_v2.verify.census import DEFECT_KEYS, READERS
from auto_patch_v2.verify.frame import Patch, Shape
from auto_patch_v2.verify.runway import runway_step
from auto_patch_v2.verify.steps import _edges, _step_rows, mid_edge_step

LAT0, LON0 = 0.0, 0.0


def _two_faces(step_m: float, role_a="runway", role_b="runway", gap=0.20):
    """Two 40 x 40 m faces of ``role_a`` / ``role_b`` sharing a boundary
    ``gap`` metres apart, the second ``step_m`` higher."""
    law = Law.for_airport("CYXY")
    rings = (((0.0, 0.0), (40.0, 0.0), (40.0, 40.0), (0.0, 40.0)),
             ((40.0 + gap, 0.0), (80.0, 0.0), (80.0, 40.0), (40.0 + gap, 40.0)))
    xy, z, ll, shapes = {}, {}, {}, []
    vid = 0
    for k, (ring, role) in enumerate(zip(rings, (role_a, role_b))):
        ids = []
        for x, y in ring:
            xy[vid] = (x, y)
            z[vid] = 100.0 + (step_m if k else 0.0)
            ll[vid] = (LAT0 + math.degrees(y / 6371000.0),
                       LON0 + math.degrees(x / 6371000.0))
            ids.append(vid)
            vid += 1
        shapes.append(Shape(k, role, "09/27" if role in ("runway", "runway_crossing")
                            else f"pav{k}", tuple(ids),
                            tuple(xy[i] for i in ids), tuple(z[i] for i in ids),
                            code_letter="C", code_number=2))
    return Patch(law, LAT0, LON0, xy, z, ll, tuple(shapes), (), {})


FLOOR = Law.for_airport("CYXY").tables.emit.materiality.runway_step_m


def test_the_family_is_registered_as_a_defect_with_a_reader():
    assert "runway_step" in READERS and "runway_step" in DEFECT_KEYS
    assert "runway_step" in Law.for_airport("CYXY").tables.families


def test_a_step_between_two_runway_faces_over_the_floor_is_a_defect():
    rows = runway_step(_two_faces(0.95))
    assert rows, "the 0.95 m step between two runway faces must be priced"
    assert max(abs(r["magnitude_m"]) for r in rows) == pytest.approx(0.95, abs=1e-6)
    assert all(r["family"] == "runway_step" for r in rows)


def test_a_step_under_the_floor_is_not():
    assert runway_step(_two_faces(FLOOR - 0.01)) == []


def test_the_floor_is_the_runway_s_own_and_not_the_cockpit_s_visual_one():
    """0.10 m, not ``materiality.step_m`` (0.5): a step the general step
    families forgive on rolled-on runway pavement is the whole defect."""
    p = _two_faces(0.30)
    assert FLOOR == pytest.approx(0.10)
    assert mid_edge_step(p) == [], "0.30 m is under the general 0.5 m step_m"
    assert runway_step(p), "...and over the runway's own 0.10 m floor"


def test_only_runway_family_pairs_are_priced():
    assert runway_step(_two_faces(0.95, role_b="junction")) == []
    assert runway_step(_two_faces(0.95, role_a="junction",
                                  role_b="junction")) == []
    assert runway_step(_two_faces(0.95, role_b="runway_crossing"))


def test_the_options_are_an_extension_not_a_fork():
    """``_step_rows`` with neither option is byte-for-byte the reading the
    three existing step families have always had (owner `7e90032`: extend
    a near-fit, never fork it)."""
    p = _two_faces(0.95)
    ins = p.law.tables.emit.instrument
    edges = _edges(p)
    probes = [(sh, (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1])), 0.5 * (za + zb))
              for sh, a, b, za, zb in edges]
    plain = _step_rows(p, "mid_edge_step", probes, edges, ins.edge_search_m,
                       ins.step_contact_tol_m, p.law.tables.emit.materiality.step_m)
    assert plain == mid_edge_step(p)


def test_the_cap_term_can_only_relax_never_bind_inside_the_contact_tolerance():
    """The ruled allowance is ``max(runway_step_m, cap x d)``.  A row only
    exists within the contact tolerance (1.0 m), where the shoulder cap's
    term is at most 0.025 m — always under the 0.10 m floor — so the floor
    governs every row and the harness's flat reading is the same number."""
    law = Law.for_airport("CYXY")
    ins = law.tables.emit.instrument
    cap = law.ruleset.runway.shoulder_transverse_max
    assert cap * ins.step_contact_tol_m < FLOOR, (cap, ins.step_contact_tol_m)


# ── the span rule and the cliff escape (owner RULINGS 2026-09-12ad / 12af,
#    ruled for this family 2026-09-16; lane ``v2hecastep``) ──────────────

def test_a_spanned_pair_under_the_cliff_grade_is_a_slope_and_is_reported():
    """HECA's survivor: 0.1693 m over 0.992 m between two runway faces that
    SHARE a vertex — a 17 % SLOPE on a continuous surface.  It stays a
    census row (the family counts it) and carries ZERO excess, so
    ``defect_gate`` files it under the floor and no tile aborts on it."""
    from auto_patch_v2.verify.census import defect_excess_m, defect_gate
    p = _two_faces(0.1693, gap=0.992)
    rows = runway_step(p)
    assert rows, "the row is still a census row — REPORT is not deletion"
    assert all(r["reading"] == "slope" for r in rows)
    assert all(r["cap_pct"] == pytest.approx(100.0 * cliff_grade(p.law)) for r in rows)
    assert all(defect_excess_m(r) == 0.0 for r in rows)
    defects, under = defect_gate(p.law, {"runway_step": rows})
    assert defects == {} and under["runway_step"]["rows"] == len(rows)


def test_at_or_over_the_cliff_grade_it_stays_a_defect_whatever_the_span():
    """The check that the rule keeps the family's teeth: HECA's three face-37
    rows read 187 % / 126 % / 188 % over 0.365 / 0.455 / 0.182 m."""
    from auto_patch_v2.verify.census import defect_excess_m, defect_gate
    for step, gap in ((0.6845, 0.365), (0.5715, 0.455), (0.3422, 0.182)):
        p = _two_faces(step, gap=gap)
        rows = runway_step(p)
        assert rows, (step, gap)
        assert all(r["reading"] == "cliff" for r in rows)
        # the whole magnitude is the excess, exactly as before the rule
        assert max(defect_excess_m(r) for r in rows) == pytest.approx(step, abs=1e-6)
        assert defect_gate(p.law, {"runway_step": rows})[0]["runway_step"] == len(rows)


def test_a_welded_pair_under_the_floor_is_unchanged_by_the_rule():
    """d ~ 0 is why the floor exists: a hair-wide pair is judged by the
    0.10 m floor and the cliff line never enters."""
    assert runway_step(_two_faces(FLOOR - 0.01, gap=0.02)) == []
    rows = runway_step(_two_faces(0.30, gap=0.02))
    assert rows and all(r["reading"] == "cliff" for r in rows)


def test_the_cliff_line_is_imported_and_never_re_spelled():
    """§31 (7)'s ONE derivation site: the family reads the design surface's
    own bank slope through ``law.tables.cliff_grade`` (RULINGS 2026-09-12af)."""
    law = Law.for_airport("CYXY")
    assert cliff_grade(law) == pytest.approx(law.tables.emit.design.bank_slope)
