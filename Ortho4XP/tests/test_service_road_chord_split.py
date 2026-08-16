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
import auto_patch.pipeline                                    # noqa: E402,F401
from auto_patch.pavement.service_roads import (                # noqa: E402
    _BEND_ANGLE_DEG, _max_chord_deviation, _rect_from_endpoints,
    _split_at_bends, build_service_road_network)

# CYXY OSM feed way -16, "Barkley-Grow Crescent" (highway=tertiary),
# local metres relative to its first vertex.  Length 162.79 m, chord
# 160.28 m, sagitta 10.31 m, max per-vertex turn 14.5°.
BARKLEY_GROW = [
    (0.0, 0.0),
    (10.913, 3.05),
    (27.62, 9.139),
    (40.81, 14.984),
    (74.497, 30.357),
    (82.556, 32.539),
    (88.901, 33.118),
    (94.025, 33.507),
    (132.667, 33.452),
    (143.722, 35.645),
    (154.94, 41.044),
]
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


def _run_deviation(run) -> float:
    """A run's own max chord deviation — the number the rect must cover."""
    return _max_chord_deviation(run, run[-1][0], run[-1][1])


# ══════════════════════════════════════════════════════════════════════
# (a) the defect geometry: a gently-curved road splits, and every run
#     it splits into is covered by its own rect
# ══════════════════════════════════════════════════════════════════════

class TestCurvedRoadSplits:
    def test_the_defect_premise_holds(self):
        """Every per-vertex turn is lawful; the CHORD is what is wrong."""
        assert len(BARKLEY_GROW) == 11
        assert _max_turn_deg(BARKLEY_GROW) < _BEND_ANGLE_DEG
        assert _sagitta(BARKLEY_GROW) > HALF          # 10.31 m vs 3 m

    def test_angle_test_alone_still_yields_one_run(self):
        """Without a width there is no second test — the old behavior."""
        assert len(_split_at_bends(BARKLEY_GROW)) == 1

    def test_it_splits_into_at_least_two_runs(self):
        runs = _split_at_bends(BARKLEY_GROW, WIDTH)
        assert len(runs) >= 2

    def test_every_run_stays_within_half_width_of_its_chord(self):
        for run in _split_at_bends(BARKLEY_GROW, WIDTH):
            assert _run_deviation(run) <= HALF + 1e-9

    def test_runs_are_contiguous_and_cover_the_road(self):
        """Splitting loses no course: runs chain end-to-start and their
        lengths sum to the polyline (each break shares its vertex)."""
        runs = _split_at_bends(BARKLEY_GROW, WIDTH)
        assert runs[0][0] == BARKLEY_GROW[0]
        assert runs[-1][-1] == BARKLEY_GROW[-1]
        for prev, nxt in zip(runs, runs[1:]):
            assert prev[-1] == nxt[0]
        total = sum(LineString(r).length for r in runs)
        assert abs(total - LineString(BARKLEY_GROW).length) < 1e-6

    def test_the_rects_now_cover_the_real_road(self):
        """Each run's rect (trimmed like the builder does) holds its own
        piece of centerline; before the fix ONE rect sat 10.3 m off."""
        for run in _split_at_bends(BARKLEY_GROW, WIDTH):
            (ax, ay), (bx, by) = run[0], run[-1]
            L = math.hypot(bx - ax, by - ay)
            if L <= WIDTH:
                continue
            ux, uy = (bx - ax) / L, (by - ay) / L
            built = _rect_from_endpoints(ax + ux * HALF, ay + uy * HALF,
                                         bx - ux * HALF, by - uy * HALF,
                                         WIDTH)
            assert built is not None
            rect, axis = built
            for vx, vy in run:
                assert axis.distance(Point(vx, vy)) <= HALF + 1e-9

    def test_network_residue_collapses(self, monkeypatch):
        """End-to-end, OLD vs NEW on the same input: the corridor−rect
        residue that was emitted as the bogus ribbon junction (CYXY shape
        133, 573 m²) collapses once the road is split into runs its rects
        can cover.  Residue never reaches zero by design — a run may still
        bow up to half a width off its chord — so this pins the ORDER of
        magnitude, not zero."""
        import auto_patch.pavement.service_roads as SR

        line = LineString(BARKLEY_GROW)

        def build():
            return SR.build_service_road_network(
                [(line, "road")], None, width=WIDTH, min_len=1.0,
                mouth_join=False)

        new_rects, new_junctions = build()
        with monkeypatch.context() as m:
            # The pre-fix splitter: angle test only.
            m.setattr(SR, "_split_at_bends",
                      lambda coords, width=None: _split_at_bends(coords))
            old_rects, old_junctions = build()

        assert len(old_rects) == 1                  # ONE rect on the chord
        assert len(new_rects) >= 2
        old_area = sum(p.area for p, _r, _n in old_junctions)
        new_area = sum(p.area for p, _r, _n in new_junctions)
        old_max = max(p.area for p, _r, _n in old_junctions)
        new_max = max(p.area for p, _r, _n in new_junctions)
        assert new_area < 0.5 * old_area
        assert new_max < 0.5 * old_max
        assert new_max < 200.0                      # no ribbon-class lune


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

    def test_it_stays_one_run(self):
        assert len(_split_at_bends(self.JITTERED, WIDTH)) == 1
        assert len(_split_at_bends(self.BOWED, WIDTH)) == 1

    def test_width_changes_nothing_below_the_threshold(self):
        assert (_split_at_bends(self.JITTERED, WIDTH)
                == _split_at_bends(self.JITTERED))
        assert (_split_at_bends(self.BOWED, WIDTH)
                == _split_at_bends(self.BOWED))


# ══════════════════════════════════════════════════════════════════════
# (c) the ANGLE test is intact: an L-bend still splits at its vertex
# ══════════════════════════════════════════════════════════════════════

class TestLBendUnchanged:
    L_BEND = [(0.0, 0.0), (25.0, 0.0), (50.0, 0.0), (50.0, 25.0),
              (50.0, 50.0)]

    def test_the_bend_is_sharp(self):
        assert _max_turn_deg(self.L_BEND) > _BEND_ANGLE_DEG

    def test_it_splits_at_the_bend_vertex_exactly_as_before(self):
        runs = _split_at_bends(self.L_BEND, WIDTH)
        assert len(runs) == 2
        assert runs[0][-1] == (50.0, 0.0)
        assert runs[1][0] == (50.0, 0.0)
        assert runs == _split_at_bends(self.L_BEND)
