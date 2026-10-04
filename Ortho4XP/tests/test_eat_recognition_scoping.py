"""EAT RECOGNITION SCOPING — routed wrap, vacuous bound, cut-only pin.

Owner ruling 2026-08-25c (docs/RULINGS.md; spec
``docs/specs/eat-recognition-scoping-spec.md``): **an end-around taxiway
is a ROUTED WRAP, bounded by the surface's own geometry, and its pin only
CUTS.**  The anchor-rect MECHANISM of 2026-07-27 — the corridor rect, the
``end_elev + eat_pavement_ceiling(D_mid)`` value, the region table, the
contradiction guard — is untouched; what these twins pin is WHICH
pavement is recognised as an end-around taxiway in the first place.

Measured basis (LEMD +40-004, 2026-08-25): 149 pins over 10 crossing
segments at 1.0-4.6 km beyond the 14R / 36R ends, owning shapes plain
apron and junction rings, the 36R pins 59-66 m ABOVE the adjacent
DEM-seeded pavement.  All 12 contradictory final-band anchor pairs were
EAT-pin vs EAT-pin, the phase-A harmonic split an empty polytope at
2,291 nodes, and the build died on the final-band inversion assert.  The
owner rules LEMD HAS NO EATs.  Real ones cross at 439-482 m (KCLT).

The three clauses, one twin apiece plus the gate:

  (a) a wrap — crossing centreline, regulation below reference — pins
      EXACTLY as it did before this round;
  (b) an apron ring in the corridor with no through-centreline: no rect;
  (c) a crossing whose route binds on ONE side only (a dead-end spur):
      no rect — priced at the guard site on the law graph;
  (d) a wrap beyond the FAR BOUND: no rect.  Two rules set that bound
      and the stricter governs — ``D_clear = setback + tail/slope``
      (2026-08-25c) and the 600 m recognition cap
      ``EAT_MAX_CROSSING_DIST_M`` (2026-08-25d);
  (e) a wrap whose regulation sits ABOVE the reference everywhere: the
      rect is refused whole and says so out loud;
  (f) gate OFF: the 2026-07-27 recognition exactly.

AMENDED by owner ruling 2026-08-25d.  25c's three clauses all PASSED
LEMD's 14R wrap at D = 1066 m — a taxi centreline genuinely crosses the
extended centreline there, inside the 1280 m vacuous bound, and the
regulation value genuinely cuts — so it was the one rect left standing
of the original ten.  The owner rules that is not an end-around taxiway
but the airport's own taxi network crossing a projected line: **nothing
is recognised beyond 600 m**, the measured band of real EATs being
439-482 m.

Hermetic: hand-built layouts, no DEM files, no X-Plane, no network.
"""
from __future__ import annotations

from shapely.geometry import Polygon

import auto_patch.config as cfg

# The same frame ``tests/test_eat_ceiling.py`` uses: a 45 m (code E)
# runway lying along −x with its DER at the origin, outward +x.
_RWY = Polygon([(-1000.0, -22.0), (0.0, -22.0), (0.0, 22.0),
                (-1000.0, 22.0)])
_ANCHOR_XY = (0.0, -22.0)
_END_ELEV = 100.0
_HALF = 22.5


def _rect(x0, x1, y0=-10.0, y1=10.0):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _end_spec():
    return {
        "p0": (0.0, 0.0),
        "outward": (1.0, 0.0),
        "code_letter": "E",
        "code_number": 4,
        "slope": float(cfg.EAT_FAA_DEPARTURE_SLOPE),
        "setback_m": float(cfg.EAT_FAA_SETBACK_M),
        "tail_height_m": float(cfg.TAIL_HEIGHT_BY_CODE_LETTER["E"]),
        "anchor_xy": _ANCHOR_XY,
        "half_width_m": _HALF,
        "end_id": "09",
    }


def _ring(poly):
    return list(poly.exterior.coords)[:-1]


def _taxi_idx(layout, b2i, poly):
    cps = layout.canonical_points
    return [b2i[cps.get_or_add(float(x), float(y))] for (x, y) in _ring(poly)]


# ── (c) A WRAP ROUTES ON BOTH SIDES ────────────────────────────────
#: A runway anchor at 0 and a taxi chain 0-1-2 reaching the rect's node
#: 3 on ONE side; node 4 (the far side) hangs off nothing.  Exactly what
#: ``u_spine_adj_airside`` looks like for a dead-end spur.


# ── (d2) THE 600 m RECOGNITION CAP (owner 2026-08-25d) ─────────────
class TestTheRecognitionCap:
    """(d2) The clause-2 companion the LEMD survivor forced.  25c's
    three clauses ALL passed LEMD's 14R wrap at D = 1066 m — a taxi
    centreline really does cross the extended centreline there, inside
    the 1280 m vacuous bound, and its regulation value really does cut.
    The owner rules that is not an end-around taxiway: **no rect is
    recognised beyond 600 m**, because real EATs cross at 439-482 m."""

    def test_the_cap_is_the_owners_measured_value(self):
        assert cfg.EAT_MAX_CROSSING_DIST_M == 600.0
        assert "EAT_MAX_CROSSING_DIST_M" in cfg.__all__


# ── (f) THE GATE ───────────────────────────────────────────────────


# RETIRED with the v1 engine (stage B round 2, lane ``v1cut``, 2026-10-04) —
# it read config.py's source for O4_EAT_SCOPING_V2, a v1 recognition gate
# nothing reads any more (removed in the config split):
# ``TestTheGate.test_the_gate_defaults_on``.
