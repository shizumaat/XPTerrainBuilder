"""Terrain-pin quarantine retirement (``O4_RETIRE_TERRAIN_PIN_QUARANTINE``).

Spec: ``docs/specs/quarantine-retirement-round1-spec.md`` (+ its 2026-08-02
AMENDMENT).  Owner law (RULINGS.md): quarantine is UNAUTHORIZED — a real
airport with real thresholds has a lawful surface, so a break region is a law
defect to attribute, never an answer.

The terrain-pinned pair export in ``final_grade_projection`` has TWO effects,
and the gate must retire BOTH (the amendment's ruling, after the round's
pre-condition STOP found the second one):

  1. BOOKKEEPING — ``layout._break_node_ll`` → the sidecar's ``break_nodes``
     → rows hidden from the validator.
  2. FREEZE — ``layout._final_projection_broken_keys`` → the NEXT projection
     run's ``pre_broken`` (solve.py:5104-5111, ungated) → ``immovable`` in
     ``feasibility_project`` (one_solve.py:2517-2532).  This is the
     load-bearing quarantine: measured at HECA, 202 of the 375 nodes the mid
     run carried into the late run were minted here, and 165 of those were
     NOT hard — free nodes frozen out of every sweep.

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


def test_gate_off_quarantines_the_terrain_pinned_pair(monkeypatch):
    """CONTROL: without the gate the pair is quarantined exactly as before —
    both effects present."""
    layout = _run(monkeypatch, retire=False)

    broken_ll = _break_ll(layout)
    assert PIN_A in broken_ll and PIN_B in broken_ll, (
        "gate off: the terrain-pinned over-cap pair must reach the break "
        f"sidecar (effect 1); got {sorted(broken_ll)}")

    carried = _carry_keys_xy(layout)
    assert PIN_A in carried and PIN_B in carried, (
        "gate off: the same pair must reach the projection carry that "
        f"freezes the next run (effect 2); got {sorted(carried)}")


def test_gate_on_reports_the_pair_without_quarantining_it(monkeypatch, capsys):
    """Under the gate the SAME pair is REPORTED and neither effect fires."""
    layout = _run(monkeypatch, retire=True)
    output = capsys.readouterr().out

    # It was found and said out loud — a silent retirement would read as
    # "the defect vanished" instead of "the defect is now visible".
    assert "[terrain-pin-retired]" in output, (
        "the gate must REPORT the population it no longer quarantines; "
        f"got:\n{output}")

    # EFFECT 1 retired: nothing reaches the break sidecar, so the validator
    # sees the over-cap pair instead of having it hidden.
    broken_ll = _break_ll(layout)
    assert PIN_A not in broken_ll and PIN_B not in broken_ll, (
        "gate on: the terrain-pinned pair must NOT reach the break sidecar; "
        f"got {sorted(broken_ll)}")

    # EFFECT 2 retired: nothing reaches the persisted carry, so the next
    # projection run cannot freeze these nodes via ``pre_broken``.
    carried = _carry_keys_xy(layout)
    assert PIN_A not in carried and PIN_B not in carried, (
        "gate on: the terrain-pinned pair must NOT reach "
        f"_final_projection_broken_keys; got {sorted(carried)}")

    # NOT OVER-RETIRED: this round retires ONE minter.  The two free corners
    # are quarantined by the projection's OWN envelope (the ``broken`` set
    # ``feasibility_project`` returns), a different minter that the spec
    # keeps this round — they must still be there, in both sinks.
    for free in _FREE:
        assert free in broken_ll and free in carried, (
            "gate on retired more than the terrain-pin export: the "
            f"envelope's own broken node {free} must survive in both sinks; "
            f"sidecar={sorted(broken_ll)} carry={sorted(carried)}")


def test_gate_default_is_off():
    """Default "0" this round — the flip is a separate, measured decision."""
    import os
    saved = os.environ.pop("O4_RETIRE_TERRAIN_PIN_QUARANTINE", None)
    try:
        assert RP._retire_terrain_pin_quarantine_enabled() is False
    finally:
        if saved is not None:
            os.environ["O4_RETIRE_TERRAIN_PIN_QUARANTINE"] = saved
