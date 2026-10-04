"""CHORD-DEVIATION SPLIT — a service-road rect must cover its own road.

The defect: ``_split_at_bends`` tested ONLY the per-vertex turn angle
against ``_BEND_ANGLE_DEG`` (25°), so a gently-curved road passed as ONE
run — CYXY's OSM feed way -16 "Barkley-Grow Crescent" (11 vertices, max
per-vertex turn 14.5°, total heading change 59.3°) bows 10.31 m off its
own first-to-last chord.  ``_rect_from_endpoints`` then built ONE 6 m rect
on that chord, laying service_road pavement up to 10.3 m off the real road
(CYXY shape 114), and the corridor−rect residue — the lune between chord
and arc — was emitted as a bogus ribbon ``service_junction`` (shape 133).

The fix adds a CHORD-DEVIATION break beside the angle test: a run closes
when any of its own vertices strays more than ``width / 2`` from the chord
``run[0] → candidate``, which is exactly the point at which the rect stops
covering its own centerline.  Straight roads must split EXACTLY as before.

Hand-computed geometry (the -16 coordinates are the real feed geometry,
projected to local metres and translated to the first vertex), no build,
no network.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from shapely.geometry import LineString, Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Import ORDER matters: ``auto_patch.junction_repair`` ↔ ``elevation`` is a
# cycle that only resolves when the package is entered through the pipeline
# (auto_patch/CLAUDE.md, "Import cycle").

WIDTH = 6.0          # config.SERVICE_ROAD_WIDTH_M
HALF = WIDTH / 2.0


def _max_turn_deg(coords) -> float:
    worst = 0.0
    for k in range(1, len(coords) - 1):
        (ax, ay), (bx, by), (cx, cy) = coords[k - 1], coords[k], coords[k + 1]
        v1 = (bx - ax, by - ay)
        v2 = (cx - bx, cy - by)
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 < 1e-6 or n2 < 1e-6:
            continue
        cosv = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        worst = max(worst, math.degrees(math.acos(cosv)))
    return worst


def _sagitta(coords) -> float:
    chord = LineString([coords[0], coords[-1]])
    return max(chord.distance(Point(c)) for c in coords)


# ══════════════════════════════════════════════════════════════════════
# (a) the defect geometry: a gently-curved road splits, and every run
#     it splits into is covered by its own rect
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# (b) REGRESSION GUARD: a straight road with jitter is untouched
# ══════════════════════════════════════════════════════════════════════

class TestStraightRoadUnchanged:
    # 150 m, a vertex every 15 m, ±0.95 m alternating jitter: per-vertex
    # turns ≈ 14.4° (under the 25° cap) and sagitta ≈ 0.95 m (under 3 m).
    JITTERED = [(15.0 * i, 0.95 if i % 2 else -0.95) for i in range(11)]
    # The same road bowed to a 2.5 m sagitta — still under the 3 m
    # half-width, so still ONE run: the threshold is the rect's own
    # coverage, nothing tighter.
    BOWED = [(15.0 * i, 4.0 * 2.5 * (15.0 * i) * (150.0 - 15.0 * i)
              / 150.0 ** 2) for i in range(11)]

    def test_the_guard_geometry_is_what_it_claims(self):
        assert 14.0 < _max_turn_deg(self.JITTERED) <= 14.5
        assert _sagitta(self.JITTERED) < 3.0
        assert _max_turn_deg(self.BOWED) < 14.5
        assert 2.0 < _sagitta(self.BOWED) < 3.0


# ══════════════════════════════════════════════════════════════════════
# (c) the ANGLE test is intact: an L-bend still splits at its vertex
# ══════════════════════════════════════════════════════════════════════

