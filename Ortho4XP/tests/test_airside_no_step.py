"""THE AIRSIDE NO-STEP LAW — §2 twins for
docs/specs/airside-no-step-law-spec.md (owner ruling RULINGS 2026-08-27,
"NO STEPS IN AIRSIDE PAVEMENT").

THE DEFECT.  At the round-3 dip site every pointwise NEIGHBOUR pair was
inside its budget and the surface still carried +0.60 m of relief across
30 m and +1.07 m across 50-75 m: the low membrane nodes sat 130-137 m
from the nearest anchored station and reached it only through a CHAIN of
50 m x cap budgets, which accumulate.  No family priced a NON-neighbour
airside pair against its DIRECT distance.

These twins pin the legs the spec names:
  * §1.1 — a direct-distance pair over ``cap x DIRECT distance`` is a law
    edge, WITHIN one shape and ACROSS airside shape boundaries; the same
    relief spread over 200 m is lawful and gets no over-budget edge;
  * §1.3 — the SENIORITY ladder: a cross-tier edge names its SENIOR
    endpoint, and the preservation membership holds that endpoint
    CONSTANT, so the junction cannot come down to meet the membrane;
  * §1.2 — the RATE term: one bowl depth at two widths, narrow violates
    and wide passes (the owner's refinement, verbatim);
  * §1.4 — DEM demotion is scoped to AIRSIDE membrane interior;
  * the FLAG defaults ON and OFF is vacuous everywhere; empty airside is
    vacuous by construction.

No network, no DEM, no X-Plane install.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from shapely.geometry import Polygon

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


ANCHOR = (30.12, 31.40)


class _Shape:
    def __init__(self, polygon, role="apron"):
        self.polygon = polygon
        self.role = role
        self.ref = ""
        self.fan_ramp_zone = False
        self.lateral_cap = None
        self.adopts_apron_grade = False
        self.adopts_taxi_grade = False
        self.single_poly = False


class _CPS:
    """The canonical registry's contract, at its own 0.5 m tolerance."""

    def __init__(self):
        self._k = {}

    def get_or_add(self, x, y):
        k = (int(round(x / 0.5)), int(round(y / 0.5)))
        self._k.setdefault(k, k)
        return k


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.anchor = ANCHOR
        self.canonical_points = _CPS()

    def m_to_ll(self, x, y):
        return (ANCHOR[0] + y / 111_320.0, ANCHOR[1] + x / 96_000.0)


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


# ═════════════════════════════════════════════════════════════════════
# THE REGISTER AND THE CONSTANTS
# ═════════════════════════════════════════════════════════════════════


def test_the_window_and_k_are_config_constants():
    """Spec §1.1/§1.3: both are config constants (and STANDARDS.md
    carries their note)."""
    import auto_patch.config as CFG
    assert CFG.AIRSIDE_NO_STEP_WINDOW_M == 150.0
    assert CFG.AIRSIDE_NO_STEP_K == 16
    assert CFG.AIRSIDE_NO_STEP is True
    txt = (_ROOT / "docs" / "STANDARDS.md").read_text(encoding="utf-8")
    assert "AIRSIDE_NO_STEP_WINDOW_M" in txt
    assert "AIRSIDE_NO_STEP_K" in txt


# ═════════════════════════════════════════════════════════════════════
# §1.1 — THE LOCAL DIRECT-DISTANCE GRADE
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §1.3 — THE SENIORITY LADDER
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# §1.2 — THE RATE OF CHANGE
# ═════════════════════════════════════════════════════════════════════

def _bowl_way(cg, nodes, width_m, depth_m, wid="w1", role="apron"):
    """A 5-station polyline: flat, down by ``depth_m`` at the centre,
    back up — total span ``width_m``.  Emitted as an ``apron_lattice``
    breakline (an airside membrane polyline, spec §1.2)."""
    half = width_m / 2.0
    xs = [-half, -half / 2.0, 0.0, half / 2.0, half]
    zs = [100.0, 100.0, 100.0 - depth_m, 100.0, 100.0]
    nids = []
    for k, x in enumerate(xs):
        nid = f"{wid}n{k}"
        nodes[nid] = (30.12 + 0.0, 31.40 + x / 96_000.0)
        nids.append(nid)
    return cg.Way(wid=wid, role=role, ref="", aeroway="",
                  nids=nids, elevs=zs, tags={})


def test_a_bowl_is_lawful_WIDE_and_unlawful_NARROW():
    """Spec §2 twin 3 and the owner's refinement, verbatim: *"A 1.5 m
    'dip' could be ok assuming it was spread across enough area to be
    smooth, like the runway curvature and rate change rules."*  Same
    depth, two widths."""
    import check_grade as cg

    def _ll_to_m(lat, lon):
        return ((lon - 31.40) * 96_000.0, (lat - 30.12) * 111_320.0)

    for width, expect_rows in ((30.0, True), (600.0, False)):
        nodes = {}
        w = _bowl_way(cg, nodes, width, 1.5)
        rows, n_st, n_ways = cg._check_airside_no_step_rate(
            [], [w], nodes, _ll_to_m)
        assert n_st > 0, "no station was censused"
        if expect_rows:
            assert rows, (
                f"a 1.5 m bowl concentrated over {width:g} m must violate "
                f"the rate law")
        else:
            assert not rows, (
                f"a 1.5 m bowl spread over {width:g} m is LAWFUL — the "
                f"owner's refinement")


def test_the_rate_reader_uses_the_strip_families_own_machinery():
    import check_grade as cg
    import inspect
    src = inspect.getsource(cg._check_airside_no_step_rate)
    assert "_strip_longitudinal_breaches" in src
    assert "_rate_reader_blind_spot" in src
    assert "_site_key" in src


# ═════════════════════════════════════════════════════════════════════
# §1.6 — THE CENSUS FAMILY
# ═════════════════════════════════════════════════════════════════════

def test_the_family_is_registered():
    """``LAW_FAMILIES`` registration, so omission is structurally
    impossible (``tests/test_harness.py`` twins)."""
    import check_grade as cg
    keys = [k for (k, _t, _b) in cg.LAW_FAMILIES]
    assert "airside_no_step" in keys
    assert cg.LAW_FAMILIES[keys.index("airside_no_step")][2] == "within"


def test_the_census_prices_exactly_the_published_edge_list():
    """Spec §1.6: "prices exactly the sidecar-published §1.3 edge
    enumeration (the ``apron_lattice_membrane`` precedent: solver
    publishes, census prices the same list — one law, one population)".
    ONE implementation serves both families."""
    import check_grade as cg
    import inspect
    src = inspect.getsource(cg._check_airside_no_step)
    assert "_check_published_law_edges" in src
    assert "_check_published_law_edges" in inspect.getsource(
        cg._check_apron_lattice_membrane)


def test_a_published_edge_over_budget_mints_exactly_one_row():
    import check_grade as cg

    def _ll_to_m(lat, lon):
        return ((lon - 31.40) * 96_000.0, (lat - 30.12) * 111_320.0)

    nodes = {"a": (30.12, 31.40), "b": (30.12, 31.40 + 40.0 / 96_000.0)}
    w = cg.Way(wid="w", role="apron", ref="", aeroway="",
               nids=["a", "b"], elevs=[100.0, 101.5], tags={})
    recs = [{"a": [30.12, 31.40],
             "b": [30.12, 31.40 + 40.0 / 96_000.0],
             "budget_m": 0.6, "provenance": "airside_no_step"}]
    rows, n_checked, n_unmatched = cg._check_airside_no_step(
        recs, [w], [], nodes, _ll_to_m)
    assert n_checked == 1 and n_unmatched == 0
    assert len(rows) == 1
    assert rows[0].de_m == pytest.approx(1.5, abs=1e-6)


def test_a_sub_quantization_excess_mints_no_row():
    """The emit-quantization envelope (air1 attribution 2026-09-01).

    ``alt_abs`` emits at 2 dp, so a pair the solve landed EXACTLY at its
    budget re-reads up to 0.01 m over from rounding alone — and the
    junction-family weld hubs carry the same decimetre envelope the
    within-shape reader already grants (``_pair_quant_noise_m``).  The
    published-edge reader prices the SAME encoding, so it grants the
    SAME envelope: excess at or below ``_pair_quant_noise_m`` of the
    worse-encoded endpoint way is rounding, not a step.  Over the
    envelope still mints exactly one row (the sibling test above).
    """
    import check_grade as cg
    import inspect

    src = inspect.getsource(cg._check_published_law_edges)
    assert "_pair_quant_noise_m" in src, (
        "the published-edge reader must price the emit encoding with "
        "the same envelope authority as the within-shape reader")

    def _ll_to_m(lat, lon):
        return ((lon - 31.40) * 96_000.0, (lat - 30.12) * 111_320.0)

    nodes = {"a": (30.12, 31.40), "b": (30.12, 31.40 + 40.0 / 96_000.0)}
    # apron encoding: envelope = ELEV_ROUNDING_NOISE_M (0.03).  Budget
    # 0.60, emitted |dz| 0.62 — 0.02 over, inside the envelope: NO row.
    w = cg.Way(wid="w", role="apron", ref="", aeroway="",
               nids=["a", "b"], elevs=[100.00, 100.62], tags={})
    recs = [{"a": [30.12, 31.40],
             "b": [30.12, 31.40 + 40.0 / 96_000.0],
             "budget_m": 0.6, "provenance": "airside_no_step"}]
    rows, n_checked, n_unmatched = cg._check_airside_no_step(
        recs, [w], [], nodes, _ll_to_m)
    assert n_checked == 1 and n_unmatched == 0
    assert rows == [], "a sub-envelope excess is emit rounding, not a step"
    # …and one full centimetre PAST the envelope is a real row.
    w2 = cg.Way(wid="w", role="apron", ref="", aeroway="",
                nids=["a", "b"], elevs=[100.00, 100.64], tags={})
    rows2, _n, _u = cg._check_airside_no_step(
        recs, [w2], [], nodes, _ll_to_m)
    assert len(rows2) == 1


# ═════════════════════════════════════════════════════════════════════
# §1.4 — DEM DEMOTION
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# THE FLAG, AND VACUITY
# ═════════════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════════════════
# AMENDMENT 2 — THE TWO-PASS CONFORM
# ═════════════════════════════════════════════════════════════════════


def test_the_pass_2_reseed_is_gated_OFF_with_its_measurement():
    """§1.4's taut re-seed is RETIRED-KEPT-GATED (default OFF) on this
    lane's own measurement — the repo's retired-kept-gated idiom, so the
    finding is not hidden and a ruling has an arm to be made on."""
    import auto_patch.config as CFG
    assert CFG.AIRSIDE_NO_STEP_RESEED is False
    src = Path(CFG.__file__).read_text(encoding="utf-8")
    i = src.index("AIRSIDE_NO_STEP_RESEED = (")
    note = src[max(0, i - 1800):i]
    assert "O4_AIRSIDE_NO_STEP_RESEED=1" in note
    assert "re-seeded ZERO nodes" in note, (
        "a gated-off mechanism must carry the measurement that gated it")
    assert "88 -> 186" in note, (
        "…including the wider cut that scoped it back")


# ═════════════════════════════════════════════════════════════════════
# HECA ROUND 4 §H1 — THE COVERAGE GUARANTEE AND THE DO-NO-HARM
# RELAXATION (docs/specs/heca-round4-spec.md; RULINGS 2026-08-28b
# items 1 and 2)
# ═════════════════════════════════════════════════════════════════════


def test_H1_the_round4_flag_defaults_are_the_SHIP_configuration():
    """§Shared named five flags default ON; spec Amendment 1 §1 ruled
    ``ROAD_EVIDENCE_SEVER`` RETIRED-KEPT-GATED **OFF** on the lane's own
    measurement (IoU 0.8221 against the 0.90 bar; +61/+37/+435 census
    cost at HECA/SPJC/LEMD, OFF strictly better everywhere).  So the
    ALL-DEFAULTS arm is the lane's ``k_heca_noh3`` configuration, and
    that is what this pins — a default is a ruling, not a preference."""
    import auto_patch.config as CFG
    for name in ("MEMBRANE_LAW_FLOOR", "PASS2_RELAXATION",
                 "ADOPT_FREEZE_AIRSIDE_ONLY", "TRANSVERSE_NO_STEP"):
        assert getattr(CFG, name) is True, name
        assert name in CFG.__all__, f"{name} is not in the registry"
    assert CFG.ROAD_EVIDENCE_SEVER is False, (
        "§H3 ships default-OFF (spec Amendment 1 §1)")
    assert "ROAD_EVIDENCE_SEVER" in CFG.__all__


# ═════════════════════════════════════════════════════════════════════
# HECA ROUND 4 §H4 — THE TRANSVERSE PROFILE OBEYS NO-STEP ON ITS OWN
# RING (RULINGS 2026-08-28b item 5(a))
# ═════════════════════════════════════════════════════════════════════


# RETIRED with the v1 engine (stage B round 2, lane ``v1cut``, 2026-10-04) —
# the test read the SOURCE of a deleted v1 module:
# ``test_the_sidecar_key_is_published_unconditionally``.
