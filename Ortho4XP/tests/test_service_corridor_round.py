"""SERVICE-CORRIDOR ROUND — the twins.

Spec: ``docs/specs/service-corridor-round-spec.md``, implementing the owner
rulings of 2026-08-12b (``docs/RULINGS.md``): service roads ENABLED AND
BUILT; apt.dat truck routes are an authoritative corridor source and ONE
corridor = ONE continuous law object end-to-end; a road's own course is
never terraced (free ends grade to DEM under the road cap, and no wall may
cut across a corridor's course); the road-width classification read is
corridor-aware.

Each class below is one ruling, stated as the measured defect it closes:

1. SOURCES — the minter runs (gate default ON, env kill switch recorded in
   the gate provenance) and the two sources DEDUPE at centerline level, so
   one physical corridor is never minted (and never spined) twice.
2. MINTING — pavement is minted only where NONE exists: an existing apron /
   ribbon is never double-paved.
3. ONE LAW OBJECT PER CORRIDOR — a corridor course registers as ONE chain
   whose axis coverage has no axis-free gap, and it REPLACES the free-road
   scoped pieces it covers rather than duplicating them (the HECA
   four-disjoint-axes state is the named defect).  The sidecar mirror agrees
   by construction because both readers walk ``centerline_specs``.
4. FREE-END LAW — a corridor end over open terrain reaches DEM at the road
   cap, and the groundside terrace-wall emitter may not emit a wall across a
   corridor's course (the ruled KCLT lot-road wall).
5. CLASSIFICATION — a contiguous widening (a lot entrance) never vetoes a
   road ribbon: the corridor-width part still reads as a corridor.
6. ONE GRADE NUMBER — ``config.SERVICE_ROAD_MAX_GRADE`` and no second
   spelling anywhere in the road path.

Hand-computed geometry, no build, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

from shapely.geometry import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import ORDER matters: ``auto_patch.junction_repair`` ↔ ``elevation`` is a
# cycle that only resolves when the package is entered through the pipeline
# (auto_patch/CLAUDE.md, "Import cycle").
from auto_patch import config as CFG                          # noqa: E402


def _rect(x0, y0, x1, y1) -> Polygon:
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


# ══════════════════════════════════════════════════════════════════════
# 1 — SOURCES: the gate, the kill switch, the centerline-level dedupe
# ══════════════════════════════════════════════════════════════════════

class TestSources:
    def test_the_minter_is_on_by_default(self):
        """Owner 2026-08-12b: service roads are ENABLED AND BUILT."""
        assert CFG.ENABLE_SERVICE_ROADS is True

    def test_the_kill_switch_is_an_o4_gate_in_the_provenance(self):
        """The switch must be readable off a shipped patch, so it has to be
        an ``O4_`` env gate the config introspection can see — a bare
        module constant would be invisible."""
        from auto_patch import provenance
        gates = provenance.introspect_config_gates()
        assert "O4_ENABLE_SERVICE_ROADS" in gates
        assert gates["O4_ENABLE_SERVICE_ROADS"]["default"] == "1"
        assert "O4_ENABLE_SERVICE_ROADS" in provenance.gate_provenance()["on"]


# ══════════════════════════════════════════════════════════════════════
# 2 — MINTING: rects + junction fill, pavement-clear
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# 3 — ONE LAW OBJECT PER CORRIDOR
# ══════════════════════════════════════════════════════════════════════

BRANCH = [(300.0, 0.0), (300.0, 120.0)]


class _FakeCenterline:
    def __init__(self, pts, is_service=False, seg_sizes=None):
        self.line = LineString(pts)
        self.route_line = None
        self.is_service = is_service
        self.name = "N" if is_service else "T"
        self.seg_sizes = (list(seg_sizes) if seg_sizes is not None
                          else [""] * (len(pts) - 1))


# ══════════════════════════════════════════════════════════════════════
# 4 — FREE-END LAW: DEM tie, and no wall across a road's course
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# 5 — CLASSIFICATION: a widening never vetoes the ribbon
# ══════════════════════════════════════════════════════════════════════


class TestCorridorAwareWidthRead:


    def test_the_service_adjacency_feature_is_live(self):
        """Ruling 5: the RULINGS:128 corollary goes live."""
        assert CFG.SCORER_SERVICE_ADJ is True


# ══════════════════════════════════════════════════════════════════════
# 6 — ONE GRADE NUMBER
# ══════════════════════════════════════════════════════════════════════


class TestOneGradeNumber:
    def test_the_role_table_reads_the_constant(self):
        assert (CFG.ROLE_GRADE_LIMITS["service_road"]
                == CFG.SERVICE_ROAD_MAX_GRADE)
        assert (CFG.ROLE_GRADE_LIMITS["service_junction"]
                == CFG.SERVICE_ROAD_MAX_GRADE)
        assert (CFG.GROUNDSIDE_PAVEMENT_MAX_GRADE
                == CFG.SERVICE_ROAD_MAX_GRADE)


# ══════════════════════════════════════════════════════════════════════
# 7 — FINALARCH items 4/5: stage-aware anchors and the fallback
#     neighbour term (S1f dossier item 5; RULINGS 2026-08-14)
# ══════════════════════════════════════════════════════════════════════


# RETIRED with the v1 engine (stage B round 2, lane ``v1cut``, 2026-10-04) —
# both scanned sources (pavement/service_roads.py, grade_graph.py) are deleted
# v1 modules:
# ``TestOneGradeNumber.test_no_second_grade_number_is_spelled_in_the_road_path``.
