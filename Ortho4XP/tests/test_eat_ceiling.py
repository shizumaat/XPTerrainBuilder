"""END-AROUND TAXIWAY (EAT) departure-surface law — owner rulings
2026-07-27, ANCHOR-RECT revision (docs/specs/eat-anchor-rect-spec.md).

An end-around taxiway loops beyond a runway end and crosses the extended
centreline, so an aircraft on it stands under the departure / take-off-climb
surface.  The surface must clear the aircraft's TAIL, which forces the EAT
PAVEMENT below the runway-end elevation (KATL taxiway Victor ≈ −9 m).

This file pins:

  * the LAW — ``grade_law.eat_pavement_ceiling`` at the KCLT-class numbers
    (D = 460 m, code E: FAA −8.6 m, EASA −12.1 m off the runway end);
  * the REGION selector — FAA for North America (ICAO K/C/P/M), EASA
    everywhere else;
  * the ANCHOR RECT — the crossing segment (extended centreline corridor
    at the runway's DECLARED half-width ∩ taxi/junction/apron pavement,
    beyond the 300 m minimum crossing distance) HARD-PINNED flat at
    ``end_elev + eat_pavement_ceiling(D_mid)`` inside
    ``solver_primitives._seed_elevations`` — the regulation value,
    unconditionally; lower value wins where two ends' corridors overlap;
    senior pins (runway / seam) never overridden;
  * the scoping HELPERS the rect construction and the verification
    reader share (``eat_end_projection``, ``eat_scoping_bounds``,
    ``eat_ceiling_offset``, ``_eat_shape_may_be_governed``);
  * the GATE — off ⇒ no pins, no findings, and verify output with no
    trace of the feature.

The first implementation's one-sided pavement↔pavement interval edges
(``_build_eat_ceiling_constraints``) are RETIRED: their negative slab
weights blew up the reach-envelope Dijkstra (KCLT killed at 15 min CPU /
20.3 GB).  The gate now defaults ON — the tests still state the gate they
want explicitly, so neither direction silently stops testing anything if
the default ever moves again.

Hermetic: hand-built layouts, no fixtures, no DEM files, no X-Plane, no
network.
"""
import pytest
from shapely.geometry import Polygon

import auto_patch.config as cfg


@pytest.fixture(autouse=True)
def _eat_gate_on(monkeypatch):
    """Every test here states the gate it wants; the default (ON) and
    any ``O4_*`` override in the developer's shell must not silently
    decide what these tests measure.  The gate-OFF tests re-patch it to
    False."""
    monkeypatch.setattr(cfg, "EAT_SURFACE_CEILING_ENABLED", True)


def test_gate_defaults_on_with_the_anchor_rect_revision():
    """The anchor-rect revision rides the positive-weight hard-anchor
    machinery — no negative slab exists anywhere — so the build-time
    blocker that kept the first implementation gated off is structurally
    gone and the owner ruling is to ship the law ON.

    Read from the source line, not the imported value: the autouse
    fixture above (and any ``O4_*`` override in the developer's shell)
    deliberately moves the imported one."""
    import re
    from pathlib import Path
    src = (Path(cfg.__file__)).read_text(encoding="utf-8")
    m = re.search(r'O4_EAT_SURFACE_CEILING",\s*"(\d)"', src)
    assert m is not None, "the gate's env default line moved"
    assert m.group(1) == "1"


def test_tail_height_table_is_the_ac_table_1_1_set():
    assert cfg.TAIL_HEIGHT_BY_CODE_LETTER == {
        "A": 6.1, "B": 9.1, "C": 13.7, "D": 18.3, "E": 20.1, "F": 24.4}
    # Same key set as the wingspan table it sits beside.
    assert (set(cfg.TAIL_HEIGHT_BY_CODE_LETTER)
            == set(cfg.WINGSPAN_BY_CODE_LETTER))


# ── the REGION selector ──────────────────────────────────────────────
_FAA = (cfg.EAT_FAA_DEPARTURE_SLOPE, cfg.EAT_FAA_SETBACK_M)
_EASA = (cfg.EAT_EASA_TAKEOFF_CLIMB_SLOPE, cfg.EAT_EASA_SETBACK_M)


@pytest.mark.parametrize("icao,expected", [
    ("KCLT", _FAA),       # contiguous USA
    ("CYYZ", _FAA),       # Canada
    ("PANC", _FAA),       # Alaska / US Pacific
    ("MMMX", _FAA),       # Mexico
    ("EGLL", _EASA),      # United Kingdom
    ("LFPG", _EASA),      # France
    ("HECA", _EASA),      # Egypt
    ("SPJC", _EASA),      # Peru
])
def test_region_selection(icao, expected):
    assert cfg.eat_surface_slope_and_setback(icao) == expected


def test_runway_code_letter_resolves_a_45m_runway_to_E():
    """ADG IV and V share the 150 ft width; a ceiling law takes the
    taller tail (E), which is what KCLT/KATL actually are."""
    assert cfg.runway_code_letter(45.0) == "E"
    assert cfg.runway_code_letter(60.0) == "F"
    assert cfg.runway_code_letter(30.0) == "D"
    assert cfg.runway_code_letter(23.0) == "C"


# ── the anchor-rect pin builder ──────────────────────────────────────
# Runway lying along −x, its EAST end (the DER) at x = 0.
_RWY = Polygon([(-1000.0, -22.0), (0.0, -22.0), (0.0, 22.0),
                (-1000.0, 22.0)])
_ANCHOR_XY = (0.0, -22.0)          # a runway ring vertex at the end
_END_ELEV = 100.0                  # the runway's (flat) profile value
_HALF = 22.5                       # declared 45 m runway → half-width


def _rect(x0, x1, y0, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _end_spec(letter="E", slope=None, setback=None):
    slope = cfg.EAT_FAA_DEPARTURE_SLOPE if slope is None else slope
    setback = cfg.EAT_FAA_SETBACK_M if setback is None else setback
    return {
        "p0": (0.0, 0.0),
        "outward": (1.0, 0.0),
        "code_letter": letter,
        "code_number": 4,
        "slope": float(slope),
        "setback_m": float(setback),
        "tail_height_m": float(cfg.TAIL_HEIGHT_BY_CODE_LETTER[letter]),
        "anchor_xy": _ANCHOR_XY,
        "half_width_m": _HALF,
    }


_IN = _rect(390.0, 410.0, -10.0, 10.0)            # s ≈ 400 m, |q| ≤ 10


def _taxi_idx(layout, b2i, poly):
    cps = layout.canonical_points
    return [b2i[cps.get_or_add(float(x), float(y))]
            for (x, y) in list(poly.exterior.coords)[:-1]]


# ══════════════════════════════════════════════════════════════════════
# THE CONTRADICTION GUARD — an EAT pin never contradicts a senior hard
# anchor within route budget (docs/specs/
# eat-anchor-contradiction-guard-spec.md)
# ══════════════════════════════════════════════════════════════════════


