"""ROAD ↔ AIRSIDE CROSSING CONFORMANCE — the §2 twin, Amendment 1 frame.

Spec: ``docs/specs/road-airside-crossing-conformance-spec.md`` + Amendment 1
(Fable, 2026-08-26 late).  Owner, verbatim: *service roads crossing
taxiways, like here: 30.104671, 31.3973462, have to grade smoothly to match
the apron elevation, not leave a cliff.*  AIRSIDE IS KING: the road takes
the airside value; the airside surface feels ZERO pull.

WHAT THIS LANE MEASURED BEFORE THE AMENDMENT, and what each clause of it
therefore has a twin for:

* **FRAME** — the carve separates a road ring from the pavement it meets by
  ``GROUNDSIDE_CLEARANCE_M`` and fills the gap with an ``adjacent_ground``
  strip, so a contiguous-run test over the SETTLED arrangement finds no
  paved run at the mouth.  Attempts 1-2 asked there and the owner's site
  was invisible through two HECA builds.  Detection is now asked in the
  SOURCE frame.
* **SCOPE** — "cross-section reaches airside" produced 285 stretches /
  32.1 km at HECA.  A crossing is now a TRAVERSAL: enter and exit.
* **ADOPTION** — registering the stretches as centerlines and seating
  their mouths as solver anchors put terms in the ONE solve, and the one
  solve is global: +124 (attempt 1) and +78 (attempt 2) airside rows
  against a matched flag-off arm, 52 % of them more than 25 m from any
  road and 20 % more than 100 m.  Values are now ADOPTED post-solve onto
  ROAD-FAMILY nodes only, and a vertex any non-road shape also carries is
  FROZEN — so the airside census cannot move.

Hand-computed geometry, no build, no network, no solver.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import ORDER matters (auto_patch/CLAUDE.md, "Import cycle").
from auto_patch import config as CFG                          # noqa: E402

CAP = CFG.SERVICE_ROAD_MAX_GRADE

AMBIENT = 100.0                 # what the road solved to on its own


class _Layout:
    def __init__(self, shapes, service_lines=(), corridor_lines=(),
                 source_union=None):
        self.icao = "TEST"
        self.shapes = list(shapes)
        self.anchor = (0.0, 0.0)
        self.canonical_points = None
        self.apt_taxi_centerlines = []
        self._service_corridor_lines = list(corridor_lines)
        self._slice_service_subsegments = list(service_lines)
        self._apron_spine_subsegments = []
        self.source_pavement_union = source_union


# ══════════════════════════════════════════════════════════════════════
# Amendment 1 §1 — THE FRAME IS THE SOURCE PAVEMENT
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# Amendment 1 §2 — CROSSINGS ONLY
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# Amendment 1 §3 — ADOPTION, NEVER CONSTRAINT
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# §1.4 — THE FLAG
# ══════════════════════════════════════════════════════════════════════

class TestTheFlag:

    def test_the_flag_is_default_on(self):
        assert CFG.ROAD_AIRSIDE_CROSSING_CONFORM is True


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 4 / HECA ROUND 4 §H2 — THE FREEZE IS AIRSIDE-ONLY
# (docs/specs/heca-round4-spec.md §H2; the ruling Amendment 2 §3
#  promised; RULINGS 2026-08-28b item 5(b))
# ══════════════════════════════════════════════════════════════════════


class TestTheFreezeIsAirsideOnly:

    def test_the_flag_is_default_on(self):
        assert CFG.ADOPT_FREEZE_AIRSIDE_ONLY is True


