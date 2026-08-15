"""SERVICE-ROAD STOP — owner ruling 2026-08-15.

"Gap-fill spines and drainage must STOP at a service road, never run
through it."  Mechanism (HECA patch HECA_20260815T1329, recon
2026-08-15): ``_enclave_exempt`` exempted ``service_road`` /
``service_junction`` from the enclave-pocket blocker set, so for every
pocket-width gap the roads never registered as blockers, the R19-2
subdivision never ran, and ``_build_spine`` marched through road
pavement (31 faces burying 21,099 m² of road, 9 spines 108 m inside
roads).  The fix keeps the roads on the HARD blocker set — which routes
a road-crossed pocket into the existing R19-2 subdivision — and mirrors
that subdivision into ``construct_gap_fill_presolve`` so the pre-solve
value store still coordinate-matches what emits (the SUPERSET contract).

Three pins, per the frozen design:
  (a) a pocket-width gap crossed by a service road SUBDIVIDES — no gap
      face (and hence no spine) intersects the road, on BOTH the emit
      and the construct paths, and the two paths coordinate-match;
  (b) a gap with NO road is byte-identical to the pre-fix baseline;
  (c) the ``_enclave_exempt`` truth table for the touched roles.

Synthetic fixtures reuse ``test_enclave_region``'s frame (same HOLE).
"""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ``pipeline`` first: junction_repair <-> elevation is an import cycle.
import auto_patch.pipeline as _PIPELINE  # noqa: E402,F401
from auto_patch import enclaves as EN  # noqa: E402
from auto_patch import gap_fill as GF  # noqa: E402
from auto_patch.layout import (  # noqa: E402
    ROLE_GRADED_STRIP,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_SERVICE_JUNCTION,
    ROLE_SERVICE_ROAD,
)

from test_enclave_region import (  # noqa: E402
    HOLE,
    _frame,
    _rect,
    _sliver,
)


def _road(role=ROLE_SERVICE_ROAD):
    """A 10 m wide service road crossing the HOLE fully, north-south.

    It spans exactly y in [30, 90] (the hole's own extent) so the
    difference-minted residual corners coincide with the road's OWN ring
    vertices — chain-safe by construction, like HECA's roads whose rings
    the residual pockets share."""
    x0, y0, x1, y1 = HOLE
    return _rect(75.0, y0, 85.0, y1, role)


def _gap_faces(layout):
    return [s for s in layout.shapes
            if s.role == ROLE_GRADED_STRIP and s.ref == "gap_fill_spine"]


# ═════════════════════════════════════════════════════════════════════
# (a) The road-crossed pocket subdivides — emit path
# ═════════════════════════════════════════════════════════════════════

def test_a_road_crossed_pocket_subdivides_and_no_face_touches_the_road():
    """THE owner's site, in a fixture (spine -13297 crossing
    service_junction -10926 for 8.4 m at HECA): a pocket-width enclave
    gap crossed by a service road takes the ruled treatment on the
    RESIDUAL pockets only — no graded face (and hence no spine, which
    lives strictly inside its face) intersects the road."""
    road = _road()
    layout = _frame([road])
    EN.publish_airside_enclaves(layout)
    assert EN.airside_enclaves(layout)          # the region IS published
    n = GF.emit_gap_fill_spines(layout, None, 0, 0)
    assert n >= 2, "both residual pockets must take the treatment"
    faces = _gap_faces(layout)
    assert faces
    for f in faces:
        assert f.polygon.intersection(road.polygon).area <= 1.0, (
            "a gap face was graded OVER the service road the spine "
            "must stop at")


def test_a_service_junction_blocks_identically():
    """Same law, the junction spelling of the role (the owner's HECA
    specimen blocker -10926 is a service_junction)."""
    road = _road(role=ROLE_SERVICE_JUNCTION)
    layout = _frame([road])
    EN.publish_airside_enclaves(layout)
    n = GF.emit_gap_fill_spines(layout, None, 0, 0)
    assert n >= 2
    for f in _gap_faces(layout):
        assert f.polygon.intersection(road.polygon).area <= 1.0


# ═════════════════════════════════════════════════════════════════════
# (a) The construct twin — mirrored subdivision + coordinate parity
# ═════════════════════════════════════════════════════════════════════

def test_the_construct_pass_mirrors_the_subdivision():
    """The SUPERSET contract's new branch: the pre-solve constructor
    mints spines for the SAME residual pockets the emitter will emit —
    per pocket, and never inside the road."""
    road = _road()
    layout = _frame([road])
    EN.publish_airside_enclaves(layout)
    assert GF.construct_gap_fill_presolve(layout) >= 2
    for entry in layout.gap_fill_presolve:
        for px, py in entry["spine"]:
            from shapely.geometry import Point
            assert not road.polygon.buffer(-1e-9).contains(Point(px, py)), (
                "a pre-solve spine station inside the service road")


def test_construct_and_emit_coordinate_match_per_pocket():
    """Parity is LOAD-BEARING: the emitter matches spines against the
    pre-solve store by coordinate (``_solved_spine_values``, 0.01 m).
    Values written into the store must be consumed by the emission of
    the SAME layout — every constructed station finds its emitted twin
    (the movement report counts one delta per matched station)."""
    road = _road()
    layout = _frame([road])
    EN.publish_airside_enclaves(layout)
    n_entries = GF.construct_gap_fill_presolve(layout)
    assert n_entries >= 2
    n_stations = 0
    for entry in layout.gap_fill_presolve:
        entry["values"] = [100.0] * len(entry["spine"])
        n_stations += len(entry["spine"])
    assert GF.emit_gap_fill_spines(layout, None, 0, 0) >= 2
    deltas = getattr(layout, "_gap_spine_value_deltas", None)
    assert deltas, ("no emitted spine consumed the pre-solve store — "
                    "the construct pass no longer mirrors the emitter")
    assert len(deltas) == n_stations, (
        f"{len(deltas)} matched station(s) of {n_stations} constructed "
        f"— a constructed pocket emitted on the analytic fallback")


# ═════════════════════════════════════════════════════════════════════
# (b) The no-road regression guard — byte-identical to the baseline
# ═════════════════════════════════════════════════════════════════════

# sha256 of ``_serialize`` over the no-road fixture, captured on the
# PRE-FIX tree (worktree gapstop @ b166906e, 2026-08-15) and re-verified
# byte-identical after the fix landed.
_NO_ROAD_BASELINE_SHA256 = (
    "4e4a005625186a1c710aff9fbb9bea5e4946b706e1381e2dc50f6d468d231fe0")


def _serialize(layout) -> str:
    rows = []
    for s in layout.shapes:
        na = getattr(s, "node_altitudes", None) or []
        coords = list(s.polygon.exterior.coords) if s.polygon else []
        rows.append("|".join([
            str(getattr(s, "role", None)),
            str(getattr(s, "ref", None)),
            ";".join(f"{x:.6f},{y:.6f}" for x, y in coords),
            ";".join("None" if a is None else f"{a:.6f}" for a in na),
        ]))
    pre = getattr(layout, "gap_fill_presolve", None) or []
    for e in pre:
        rows.append("PRESOLVE|" + str(e.get("host_stage")) + "|"
                    + ";".join(f"{x:.6f},{y:.6f}" for x, y in e["spine"]))
    return "\n".join(rows)


def test_a_gap_with_no_road_is_byte_identical_to_the_baseline():
    """The fix must be INERT off its trigger: a pocket with no service
    road takes the identical treatment, station for station, byte for
    byte (construct + emit, serialized and hashed against the pre-fix
    capture)."""
    layout = _frame()
    EN.publish_airside_enclaves(layout)
    assert GF.construct_gap_fill_presolve(layout) == 1
    assert GF.emit_gap_fill_spines(layout, None, 0, 0) == 1
    digest = hashlib.sha256(_serialize(layout).encode()).hexdigest()
    assert digest == _NO_ROAD_BASELINE_SHA256


# ═════════════════════════════════════════════════════════════════════
# (c) The _enclave_exempt truth table for the touched roles
# ═════════════════════════════════════════════════════════════════════

def test_enclave_exempt_truth_table_for_the_touched_roles():
    """Owner ruling 2026-08-15: service_road / service_junction are
    NEVER exempt.  groundside_pavement is deliberately NOT touched (not
    ruled — open question recorded at ``_SERVICE_ROAD_BLOCKER_ROLES``),
    and the enclave law's ordinary interior contents stay exempt."""
    assert GF._enclave_exempt(
        _rect(70.0, 50.0, 90.0, 70.0, ROLE_SERVICE_ROAD)) is False
    assert GF._enclave_exempt(
        _rect(70.0, 50.0, 90.0, 70.0, ROLE_SERVICE_JUNCTION)) is False
    # NOT ruled: groundside pavement keeps its exemption.
    assert GF._enclave_exempt(
        _sliver(role=ROLE_GROUNDSIDE_PAVEMENT)) is True
    assert GF._enclave_exempt(
        _rect(70.0, 50.0, 72.0, 52.0, ROLE_GRADED_STRIP)) is True
    # And the set is exactly the two ruled roles.
    assert GF._SERVICE_ROAD_BLOCKER_ROLES == frozenset(
        (ROLE_SERVICE_ROAD, ROLE_SERVICE_JUNCTION))
