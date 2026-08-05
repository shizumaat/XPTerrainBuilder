"""Terrain-pin quarantine retirement (``O4_RETIRE_TERRAIN_PIN_QUARANTINE``).

Spec: ``docs/specs/quarantine-retirement-round1-spec.md`` (+ its 2026-08-02
AMENDMENT).  Owner law (RULINGS.md): quarantine is UNAUTHORIZED — a real
airport with real thresholds has a lawful surface, so a break region is a law
defect to attribute, never an answer.

The terrain-pinned pair export in ``final_grade_projection`` had TWO effects,
and the gate retired BOTH (the amendment's ruling, after the round's
pre-condition STOP found the second one):

  1. BOOKKEEPING — ``layout._break_node_ll`` → the sidecar's ``break_nodes``
     → rows hidden from the validator.
  2. FREEZE — ``layout._final_projection_broken_keys`` → the NEXT projection
     run's ``pre_broken`` → ``immovable`` in ``feasibility_project``.  This
     was the load-bearing quarantine: measured at HECA, 202 of the 375 nodes
     the mid run carried into the late run were minted here, and 165 of those
     were NOT hard — free nodes frozen out of every sweep.

UPDATED 2026-08-04 (spec ``docs/specs/kill-half-spec.md`` §§1-2).  The gate
is DEFAULT ON, and BOTH SINKS ARE THEMSELVES DELETED — so this file no
longer pins "the gate retires the two effects" (there is nothing left to
retire them from).  It pins the stronger property the kill round asserts:
NO code path writes either sink, gate on or off, and the retirement REPORT
still names the population.

Hermetic, on the ``_FakeShape`` / ``_FakeLayout`` pattern of
``test_final_projection_snapshot_recapture.py`` — no fixtures, no DEM, no
network.  The identity ``m_to_ll`` makes an INTEGRAL coordinate a tile-seam
terrain pin (solve.py:4711-4717), which is how the synthetic pair is minted.
"""
import auto_patch.config  # noqa: F401  (config import side effects)
from auto_patch.canonical_points import CanonicalPointRegistry
from auto_patch.elevation_per_surface.route_profile import solve as RP
from auto_patch.layout import ROLE_APRON

from shapely.geometry import Polygon


class _FakeShape:
    def __init__(self, role, polygon, *, ref=None, altitude=None,
                 altitude_high=None, altitude_low=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = altitude
        self.altitude_high = altitude_high
        self.altitude_low = altitude_low
        self.node_altitudes = node_altitudes
        self.is_bridge = False


class _FakeLayout:
    def __init__(self, shapes, icao="TEST"):
        self.shapes = shapes
        self.icao = icao
        self.canonical_points = CanonicalPointRegistry()

    def m_to_ll(self, x, y):
        return (x, y)


# The two terrain-pinned vertices: integral ``x`` ⇒ integral ``la`` under the
# identity ``m_to_ll`` ⇒ tile-seam pin ⇒ ``terrain_hard``.  They are 10 m
# apart on the ring and 2.0 m apart in elevation; the apron cap is 1 %, so the
# pair's budget is 0.10 m and the edge is ~1.9 m over — far outside the
# export's own 0.03 m tolerance.  Both ends are hard, so the projection cannot
# close it: it survives to the export exactly like a real hillside strip
# welded between two ground-truth pins.
PIN_A = (0.0, 0.3)
PIN_B = (0.0, 10.3)
_FREE = [(10.3, 0.3), (10.3, 10.3)]


def _terrain_pinned_pair_layout():
    """A 10 m apron square whose two seam-pinned corners disagree by 2 m."""
    ring = [PIN_A, _FREE[0], _FREE[1], PIN_B]
    polygon = Polygon(ring)
    # ``node_altitudes`` follows the polygon's own (closed) coord order.
    coords = list(polygon.exterior.coords)
    altitudes = []
    for (x, y) in coords:
        if (x, y) == PIN_B:
            altitudes.append(102.0)
        else:
            altitudes.append(100.0)
    shape = _FakeShape(ROLE_APRON, polygon, node_altitudes=altitudes)
    return _FakeLayout([shape])


def _break_ll(layout):
    return {(round(la, 6), round(lo, 6))
            for (la, lo) in (getattr(layout, "_break_node_ll", None) or [])}


def _carry_keys_xy(layout):
    """The persisted freeze set.  A canonical-point key IS the canonical
    ``(x, y)`` tuple (``CanonicalPointRegistry.get_or_add``)."""
    keys = getattr(layout, "_final_projection_broken_keys", None) or set()
    return {(round(float(x), 6), round(float(y), 6)) for (x, y) in keys}


def _run(monkeypatch, retire):
    monkeypatch.delenv("O4_FINAL_GRADE_PROJECTION", raising=False)
    monkeypatch.setenv("O4_RETIRE_TERRAIN_PIN_QUARANTINE",
                       "1" if retire else "0")
    layout = _terrain_pinned_pair_layout()
    RP.final_grade_projection(layout, icao="TEST")
    return layout


def test_neither_sink_exists_gate_either_way(monkeypatch):
    """★ THE KILL (spec kill-half §2).  Both sinks are deleted, so NOTHING
    — not the terrain-pin export, not the envelope's own inverted nodes,
    not the weld relimit — writes ``_break_node_ll`` or
    ``_final_projection_broken_keys``.  Asserted with the gate BOTH ways:
    gate-off used to be the "quarantine as before" control, and there is
    no longer an as-before to fall back to."""
    for retire in (False, True):
        layout = _run(monkeypatch, retire=retire)
        assert _break_ll(layout) == set(), (
            f"retire={retire}: the break sidecar sink is deleted; got "
            f"{sorted(_break_ll(layout))}")
        assert _carry_keys_xy(layout) == set(), (
            f"retire={retire}: the freeze carry is deleted; got "
            f"{sorted(_carry_keys_xy(layout))}")


def test_gate_on_reports_the_pair(monkeypatch, capsys):
    """The REPORT half survives the kill: the population is still named."""
    _run(monkeypatch, retire=True)
    output = capsys.readouterr().out
    # It was found and said out loud — a silent retirement would read as
    # "the defect vanished" instead of "the defect is now visible".
    assert "[terrain-pin-retired]" in output, (
        "the gate must REPORT the population it no longer quarantines; "
        f"got:\n{output}")


def test_the_retirement_is_standing_law():
    """FLIPPED 2026-08-04 (spec ``docs/specs/kill-half-spec.md`` §1) and
    UNGATED in the build-complete-then-debug round.

    Evidence: quarantine-retirement round 1 ``ceef13f`` — the export minted
    94.2 % of HECA's residual break nodes and froze 165 free nodes out of
    the LATE airside projection.  The owner law it enforces (quarantine is
    UNAUTHORIZED) is not optional, so there is no arm that restores the
    export — not even an env override."""
    import os
    saved = os.environ.pop("O4_RETIRE_TERRAIN_PIN_QUARANTINE", None)
    try:
        assert RP._retire_terrain_pin_quarantine_enabled() is True
        os.environ["O4_RETIRE_TERRAIN_PIN_QUARANTINE"] = "0"
        assert RP._retire_terrain_pin_quarantine_enabled() is True, \
            "the gate is retired — no env value may re-enable the export"
    finally:
        os.environ.pop("O4_RETIRE_TERRAIN_PIN_QUARANTINE", None)
        if saved is not None:
            os.environ["O4_RETIRE_TERRAIN_PIN_QUARANTINE"] = saved
