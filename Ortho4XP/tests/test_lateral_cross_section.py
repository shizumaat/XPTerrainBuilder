"""The lateral CROSS-SECTION restoration (fabric Phase B, battery round).

Three facts, each of which was a real miss:

1. The emitter's span rule and the TRANSVERSE validator's span rule are
   ONE rule — the minimum width they price is the same number
   (``_BRACKET_MIN_WIDTH_M`` vs ``check_grade._TRANSVERSE_MIN_WIDTH_M``).
   Two copies drifting is exactly the census-wrapper defect class.
2. An axis running ALONG a pavement edge still yields a foot on the FAR
   edge.  The nearest-projection rule missed it whenever the corridor was
   wider than the dead lookup's 12 m fallback (CYXY apron ``shapeID 115``:
   far edge 19.7-23.2 m away, one 480 m segment, 1.5 m of cross-fall
   priced over 18 m).
3. ``station_step_m=None`` — the pre-solve call site — is untouched, so
   the fabric flags' OFF arm stays byte-identical.
"""
from __future__ import annotations

import os
import sys

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))


class _CL:
    def __init__(self, line, is_service=False):
        self.line = line
        self.is_service = is_service


class _Layout:
    def __init__(self, shapes, centerlines):
        self.shapes = shapes
        self.apt_taxi_centerlines = centerlines


def _corridor(width=20.0, length=480.0):
    """A long thin apron whose NEAR edge carries the axis and whose FAR
    edge is a single segment — the CYXY shape, minimally."""
    return Polygon([(0.0, 0.0), (0.0, length),
                    (width, length), (width, 0.0)])


# ═══════════════════════════════════════════════════════════════════════
# RULING (1) — CROSS-SECTION PAIRS ENTER THE SOLVE'S LAW CONTEXT
# (fabric-phase-b-spec.md "R-a/R-b ROUND OUTCOME + LEAD RULINGS 2":
#  priced ⟺ bound, the generation-binding law.)
# ═══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# THE SERVICE-ROAD HALF OF THE LOCKSTEP (S7 escalation, ruled 2026-08-14)
# ══════════════════════════════════════════════════════════════════════
# THE DEFECT, measured by S7: ``check_grade._TRANSVERSE_ROLES`` excluded
# ``service_road`` behind a comment claiming lockstep with "the lateral
# pass's own target roles" — but ``insert_service_lateral_nodes`` plants
# aligned cross-section vertices on service_road edges from the
# truck-route spine, and ``grade_graph`` binds those bodies across the
# route at ``SERVICE_ROAD_MAX_TRANSVERSE`` (``service_road`` joins
# ``SOFT_VISIBILITY_ROLES`` under ``config.SVC_SPINE_FIRST``, default ON).
# A generation-binding constraint whose validator read NOTHING: the
# cross-road tear the emitter was built to make unrepresentable censused
# zero.  The two tests below are the pair the campaign standard asks for
# — the scope is ONE list, and the census bites on the surface the
# generator binds.

def _law_reader():
    """``tools/check_grade`` as the census loads it."""
    import importlib.util as _ilu
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    spec = _ilu.spec_from_file_location(
        "s8_lockstep_check_grade", root / "tools" / "check_grade.py")
    mod = _ilu.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _service_road_census(tmp_path, dz_m, *, service_axis=True):
    """Census a 10 m service_road with ``dz_m`` across it, under a spine
    of the given kind.  Returns ``(check_grade, transverse rows)``."""
    from conftest import write_synthetic_patch, synthetic_patch_ll
    from auto_patch import config as CFG
    cg = _law_reader()
    z0 = 100.0
    ring = [(-5.0, 0.0, z0), (5.0, 0.0, z0 + dz_m),
            (5.0, 50.0, z0 + dz_m), (-5.0, 50.0, z0)]
    cap_l = (CFG.SERVICE_ROAD_MAX_GRADE if service_axis
             else CFG.TAXI_MAX_GRADE)
    axis = [synthetic_patch_ll(0.0, y) for y in (0.0, 50.0)]
    osm = write_synthetic_patch(
        tmp_path, [{"role": "service_road", "ref": "SVC1", "ring": ring}],
        sidecar={"axes_exact": [[axis, [cap_l], 0, bool(service_axis)]]})
    fam = {}
    cg.run_checks_law_true(osm, family_out=fam, quiet=True, top_n=0)
    return cg, fam["transverse"]


def test_a_service_road_cross_section_over_its_cap_IS_censused(tmp_path):
    """GENERATION-BOUND ⇒ VALIDATOR-READ.  0.60 m across a 10 m road is
    6 % — three times ``SERVICE_ROAD_MAX_TRANSVERSE`` — and the truck
    route's own cross-section law says so."""
    from auto_patch import config as CFG
    cg, rows = _service_road_census(tmp_path, 0.60)
    assert rows, ("a 6 % service-road cross-section censused ZERO — the "
                  "transverse family is blind to the surface the service "
                  "lateral pass binds")
    assert all(cg.row_roles(r) == ("service_road", "service_road")
               for r in rows)
    # priced at the ROAD's own transverse cap, one constant.
    worst = max(rows, key=lambda r: r.grade_pct)
    assert worst.grade_pct == pytest.approx(6.0, abs=0.2)
    assert worst.excess_pct == pytest.approx(
        100.0 * (0.60 - CFG.SERVICE_ROAD_MAX_TRANSVERSE * 10.0
                 - cg.ELEV_ROUNDING_NOISE_M) / 10.0, abs=0.2)


def test_a_lawful_service_road_cross_section_censuses_zero(tmp_path):
    """The other direction, without which the test above proves only that
    the family fires: 0.10 m across 10 m is 1 %, inside the 2 % cap."""
    _cg, rows = _service_road_census(tmp_path, 0.10)
    assert rows == [], "a compliant cross-section must mint no row"


def test_a_TAXI_axis_still_prices_no_service_road(tmp_path):
    """The scope is directional, and stays so: an aircraft spine does not
    censure a truck road (the mirror of 'a truck route is not an aircraft
    spine'), so the same over-cap road under a TAXI axis reads zero —
    that surface's law belongs to its own spine."""
    _cg, rows = _service_road_census(tmp_path, 0.60, service_axis=False)
    assert rows == []


# ═══════════════════════════════════════════════════════════════════════
# R2 — THE LATERAL PASS READS THE REGISTERED CHAINS (service-road law
# spec 2026-08-15).  ``insert_service_lateral_nodes`` consumes
# ``grade_graph.service_chain_lines`` (the ONE registered service set)
# unioned with the row-1206 courses, deduped by the existing chain
# dedupe — so cross-section feet land on FEED-chain roads the row-1206
# filter never saw.
# ═══════════════════════════════════════════════════════════════════════


# RETIRED with the v1 engine (stage B round 2, lane ``v1cut``, 2026-10-04) —
# the test read the SOURCE of a deleted v1 module:
# ``test_the_solve_ingests_the_family_at_BOTH_edge_set_sites``.
