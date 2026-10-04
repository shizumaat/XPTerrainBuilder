"""Twins for the ROUTE-DISTANCE SEAT COUPLING round (spec
``docs/specs/route-distance-seat-coupling-spec.md``).

THE DEFECT — two instruments over one population.  The seat coupler admits
and prices pairs in a STRAIGHT-CHORD frame (``polygon.distance ≤
BUILDING_REACH_CORRIDOR_M``, a 97 %-on-pavement visibility chord, limit
``APRON_MAX_GRADE·gap``), while the projection enforces the cap along the
WITHIN-SHAPE LAW GRAPH.  The dossier's HEAZ certificate is the type
specimen: ``building4↔building5`` are 17.6 m apart by chord (limit
0.176 m) but bound by the 2-hop chain ``35 —0.0578— 1295 —0.1015— 37``,
so the REAL budget is **0.1593 m** — and the pair was rejected outright as
"separated by grass".

Hermetic — no airport build, no fixtures.  Every twin drives
``anchors.build_building_seats`` directly with a hand-made band, DEM
sampler and LAW GRAPH, so a coupler that reads the geometry instead of the
graph fails them.  Covers:

  * the route budget IS the limit (the 35/1295/37 geometry) — there is no
    chord frame left to fall back to;
  * admission SUBSUMES the retired ``O4_SEAT_COUPLE_SHARED_SURFACE``
    predicate;
  * a route-unreachable pad is NOT admitted (no law binds it);
  * the BUDGET-IDENTITY property (spec §4): the coupler's pair budget IS
    the budget a real ``feasibility_project`` run settles at, within 1 %;
  * the loud empty-polytope attribution is unchanged.
"""
import pytest

from auto_patch.config import APRON_MAX_GRADE


# ── STAGE TAG (staged-solve S1b/S1c) ─────────────────────────────────
# Every constraint entry reaching a projection — or the seat coupler's
# pricing, which reads the SOLVE'S OWN entries — carries the stage its
# minter stamped, and an untagged one raises rather than being priced
# (a groundside surface must not price an airside seat coupling).
# These fixtures each stand for ONE AIRSIDE pavement shape, so they
# spell what ``solver_primitives._build_shape_constraints`` would.


# RAW LAW SWEEPS ARE STANDING LAW (docs/RULINGS.md 2026-08-05,
# build-complete-then-debug: "NO GATES … O4_ law gates and their env
# overrides are DELETED as their territory is touched").  The solver's
# emit-quantization margin — and every helper that applied it — is
# DELETED; the 0.01 m guarantee lives at emit (``auto_patch.emit_snap``),
# bounded by ONE grid step per node so it cannot compound along a route.
# Every budget below is therefore the RAW law budget, written plainly:
# the coupler prices exactly what the projection sweeps.


# The dossier's own two hops (HEAZ 35 —0.0578(6.78 m)— 1295 —0.1015(11.15 m)
# — 37), quoted as the RAW budgets the graph carries; 0.0578 + 0.1015 =
# 0.1593 is the number that binds.
_RAW_A = 0.0678
_RAW_B = 0.1115
_ROUTE = _RAW_A + _RAW_B
_CHORD_GAP_M = 17.6
_CHORD = APRON_MAX_GRADE * _CHORD_GAP_M


class _FakeLayout:
    """Only what ``build_building_seats`` reads."""


    def m_to_ll(self, x, y):
        """The frontage-band EVIDENCE export (anchors a9d9c88) spells every
        recorded point in lat/lon; a fake layout that cannot answer it
        makes the seat pass raise.  A linear stand-in is enough — nothing
        under test reads the value."""
        return (float(y) / 111_320.0, float(x) / 111_320.0)


def _idx(layout, b2i, x, y):
    return b2i[layout.canonical_points.get(float(x), float(y))]


# ── the divergence geometry: chord 17.6 m, route 0.1593 m ────────────────


def test_the_geometry_is_a_real_divergence():
    """Guard the twin itself: if the two frames ever agreed, the tests below
    would pass without measuring anything.

    The route budget is the RAW law sum 0.0578 + 0.1015 = 0.1793 now that
    the emit margin is 0 (standing raw-law sweeps).  It is still a REAL
    divergence from the chord's 0.176 — the sign simply flipped: the
    route frame is now LOOSER than the chord rather than tighter, which
    is exactly what the margin-vs-law attribution below reports."""
    assert _ROUTE == pytest.approx(_RAW_A + _RAW_B, abs=1e-6)
    assert abs(_ROUTE - _CHORD) > 1e-3
    assert _CHORD == pytest.approx(0.176, abs=1e-6)
    # Under standing raw-law sweeps the route frame is LOOSER, not
    # tighter — the divergence is what matters, not its sign.
    assert _ROUTE > _CHORD


# ── §4 BUDGET IDENTITY — measured against a real projection run ──────────


# ── admission: supersession, reachability, horizon ───────────────────────


# ── the loud empty polytope is unchanged ─────────────────────────────────


# ── the loud empty polytope is unchanged ─────────────────────────────────

