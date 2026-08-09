"""Apron-wall continuity, scope, and the emit-side corridor clamp.

Three defects diagnosed 2026-07-25 from the owner's in-sim "ramps and
sharp drops" report at SPJC (apron -10153, SW frontage) plus the owner's
follow-up scope ruling, all headless here:

  F1 ``O4_APRON_WALL_CONTINUITY`` — a wall run whose clip residue is a
     MultiPolygon used to be dropped WHOLE (SPJC: 4 runs / 240.4 m²).
     Every part now emits; confetti parts are gated and counted.
  F4 same gate — run HYSTERESIS: stations millimetres under the drop
     threshold no longer chop a continuous frontage into pieces.
  F3 ``O4_BAND_CORRIDOR_CLAMP`` — the solved band value is forced into
     THIS shape's own law corridor (the cross-shape canonical-variable
     collision that put 34.49 m where the corridor was [36.00, 36.06]).
  F5 ``O4_APRON_WALL_SCOPE`` — owner ruling 2026-07-25: an apron wall
     (and the shoulder fill band) only where another built pavement lies
     within 5 m; open-terrain frontage is ungoverned on the FILL side.

Every gate is asserted to restore the pre-fix behaviour when OFF.
"""
import math

import pytest
from shapely.geometry import Polygon

from auto_patch import adjacent_ground as AG
from auto_patch.config import (
    APRON_EDGE_WALL_MIN_DROP_M,
    APRON_SHOULDER_WIDTH_M,
    APRON_WALL_MIN_RUN_M,
    APRON_WALL_PAVEMENT_ADJACENCY_M,
    APRON_WALL_RUN_HYSTERESIS_M,
    CLEARANCE_STATION_STEP_M,
)
from auto_patch.grade_law import adjacent_ground_envelope
from auto_patch.layout import BuiltShape, ROLE_APRON, ROLE_RETAINING_WALL


# ── THIS FILE IS THE PRE-W2 CORRIDOR, HELD AS THE FLAG-OFF ARM ────────
# W2 (fabric-phase-b-spec.md) changed this law on purpose: reg-set
# ruling 1 drops the ICAO mandatory-DOWN graded strip, F-10 gives the
# taxiway/apron edge its own lip family, and ruling 4 retires the apron
# surround and the service-road shadow outright.  Every assertion below
# was written against the pre-W2 corridor and still certifies something
# load-bearing — the byte-identity of each flag's OFF arm — so it is
# PINNED to that world here rather than rewritten.  The successor
# behaviour (the ON arm, which is the default build) has its own twins
# in ``tests/test_fabric_phase_b.py``.
@pytest.fixture(autouse=True)
def _pre_w2_corridor(monkeypatch):
    for env in ("O4_FABRIC_W2_ICAO_STRIP_AUTHORITY", "O4_FABRIC_W2_TAXIWAY_LIP_AUTHORITY",
                "O4_FABRIC_W2_RETIRE_APRON_SURROUND",
                "O4_FABRIC_W2_RETIRE_APRON_EDGE_WALLS",
                "O4_FABRIC_W2_RETIRE_SERVICE_SHADOW"):
        monkeypatch.setenv(env, "0")


STEP = CLEARANCE_STATION_STEP_M
EDGE_ALT = 100.0


@pytest.fixture(autouse=True)
def _gates_on(monkeypatch):
    """Pin all three gates ON for this module regardless of the ambient
    ``O4_*`` environment (the gate-OFF halves patch them back off
    individually), so an A/B suite run cannot silently skip the fixes."""
    monkeypatch.setattr(AG, "_APRON_WALL_CONTINUITY", True)
    monkeypatch.setattr(AG, "_APRON_WALL_SCOPE", True)
    monkeypatch.setattr(AG, "_BAND_CORRIDOR_CLAMP", True)
    from auto_patch import config as cfg
    monkeypatch.setattr(cfg, "APRON_WALL_SCOPE_ENABLED", True)


class _FakeLayout:
    def __init__(self, shapes=None):
        self.shapes = list(shapes or [])
        self.airport_boundary = None
        self.anchor = (0.0, 0.0)


def _apron_ceil_off(d):
    return adjacent_ground_envelope("apron", None, None, d)[1]


def _straight_edge(length_m=120.0):
    """Stations along the x-axis at y=0, outward normal +y, flat edge."""
    n = int(length_m // STEP) + 1
    stations = [(k * STEP, 0.0) for k in range(n)]
    alts = [EDGE_ALT] * n
    outs = [(0.0, 1.0)] * n
    return stations, alts, outs


def _deep_dem(drop=APRON_EDGE_WALL_MIN_DROP_M + 4.0):
    """A DEM that sits ``drop`` below the shoulder outer edge everywhere."""
    shoulder = EDGE_ALT + _apron_ceil_off(APRON_SHOULDER_WIDTH_M)
    return lambda x, y: shoulder - drop


def _drop_profile(by_x):
    """DEM feed whose drop below the shoulder edge varies with x.

    ``by_x(x) -> drop_m``; the wall face is sampled at the shoulder outer
    point, so ``x`` is the station's own x."""
    shoulder = EDGE_ALT + _apron_ceil_off(APRON_SHOULDER_WIDTH_M)
    return lambda x, y: shoulder - by_x(x)


def _wall_shapes(layout):
    return [s for s in layout.shapes if s.role == ROLE_RETAINING_WALL]


# ──────────────────────────────────────────────────────────────────────
# F1 — multipart-safe wall emission
# ──────────────────────────────────────────────────────────────────────
def test_multipart_clip_residue_emits_every_part():
    """A nick in the middle of a long run splits the clip residue into
    two lobes.  Pre-fix the WHOLE run was dropped; both lobes now emit."""
    stations, alts, outs = _straight_edge(length_m=100.0)
    # The wall face occupies y in [3, 4]; this notch crosses it at x 45-50.
    notch = Polygon([(45.0, 2.0), (50.0, 2.0), (50.0, 6.0), (45.0, 6.0)])

    layout = _FakeLayout()
    n, union = AG._emit_apron_walls(
        layout, stations, alts, outs, _apron_ceil_off, STEP,
        _deep_dem(), notch, None)
    assert n == 2, "both lobes of the nicked run must emit"
    walls = _wall_shapes(layout)
    assert len(walls) == 2
    # No area is lost beyond the notch itself (face is 1 m deep, 100 m long,
    # minus the 5 m the notch removes).
    total = sum(s.polygon.area for s in walls)
    assert abs(total - 95.0) < 1.0, total
    assert union is not None and abs(union.area - total) < 1e-6


def test_multipart_run_is_dropped_whole_with_the_gate_off(monkeypatch):
    """Gate OFF reproduces the diagnosed defect exactly — the byte-identity
    baseline."""
    monkeypatch.setattr(AG, "_APRON_WALL_CONTINUITY", False)
    stations, alts, outs = _straight_edge(length_m=100.0)
    notch = Polygon([(45.0, 2.0), (50.0, 2.0), (50.0, 6.0), (45.0, 6.0)])
    layout = _FakeLayout()
    n, _ = AG._emit_apron_walls(
        layout, stations, alts, outs, _apron_ceil_off, STEP,
        _deep_dem(), notch, None)
    assert n == 0 and not layout.shapes


def test_sub_minimum_wall_part_is_skipped_and_counted(capsys):
    """Decomposing the residue also surfaces confetti; a part below the
    minimum run length is skipped, and the skip is REPORTED."""
    stations, alts, outs = _straight_edge(length_m=100.0)
    # Leaves a 4 m stub at x<4 (below APRON_WALL_MIN_RUN_M) and a 50 m
    # lobe past x=50.
    cut = Polygon([(4.0, 2.0), (50.0, 2.0), (50.0, 6.0), (4.0, 6.0)])
    layout = _FakeLayout()
    n, _ = AG._emit_apron_walls(
        layout, stations, alts, outs, _apron_ceil_off, STEP,
        _deep_dem(), cut, None)
    assert n == 1, "only the long lobe survives the confetti gate"
    (wall,) = _wall_shapes(layout)
    assert wall.polygon.bounds[0] >= 49.9
    out = capsys.readouterr().out
    assert "sub-minimum part(s) skipped" in out
    assert "1 sub-minimum" in out


def test_wall_part_run_length_is_the_long_side():
    poly = Polygon([(0.0, 3.0), (12.0, 3.0), (12.0, 4.0), (0.0, 4.0)])
    assert abs(AG._wall_part_run_length(poly) - 12.0) < 1e-6
    # Rotated 45°: still the long side, not a bbox diagonal.
    c, s = math.cos(math.pi / 4), math.sin(math.pi / 4)
    rot = Polygon([(x * c - y * s, x * s + y * c)
                   for x, y in poly.exterior.coords[:-1]])
    assert abs(AG._wall_part_run_length(rot) - 12.0) < 1e-6


# ──────────────────────────────────────────────────────────────────────
# F4 — wall-run hysteresis
# ──────────────────────────────────────────────────────────────────────
def _drop_at(x):
    """The SPJC flap: two stations millimetres under the 1.5 m threshold
    in the middle of an otherwise qualifying 100 m frontage."""
    if x in (45.0, 50.0):
        return 1.4988 if x == 45.0 else 1.4936
    return APRON_EDGE_WALL_MIN_DROP_M + 0.5


def test_hysteresis_merges_the_millimetre_flap_into_one_run():
    stations, alts, outs = _straight_edge(length_m=100.0)
    layout = _FakeLayout()
    n, _ = AG._emit_apron_walls(
        layout, stations, alts, outs, _apron_ceil_off, STEP,
        _drop_profile(_drop_at), None, None)
    assert n == 1, "the flap stations must not split the frontage"
    (wall,) = _wall_shapes(layout)
    x0, _y0, x1, _y1 = wall.polygon.bounds
    assert x1 - x0 > 95.0, "one continuous ~100 m wall"


def test_flap_splits_the_frontage_with_the_gate_off(monkeypatch):
    monkeypatch.setattr(AG, "_APRON_WALL_CONTINUITY", False)
    stations, alts, outs = _straight_edge(length_m=100.0)
    layout = _FakeLayout()
    n, _ = AG._emit_apron_walls(
        layout, stations, alts, outs, _apron_ceil_off, STEP,
        _drop_profile(_drop_at), None, None)
    assert n == 2, "the pre-fix behaviour: two runs, a bare notch between"


def test_a_run_never_starts_below_the_full_threshold():
    """Hysteresis relaxes CONTINUATION only — a frontage that never
    reaches the ruled threshold gets no wall at all."""
    stations, alts, outs = _straight_edge(length_m=100.0)
    just_under = APRON_EDGE_WALL_MIN_DROP_M - 0.5 * APRON_WALL_RUN_HYSTERESIS_M
    assert just_under > APRON_EDGE_WALL_MIN_DROP_M - APRON_WALL_RUN_HYSTERESIS_M
    layout = _FakeLayout()
    n, _ = AG._emit_apron_walls(
        layout, stations, alts, outs, _apron_ceil_off, STEP,
        _drop_profile(lambda x: just_under), None, None)
    assert n == 0 and not layout.shapes


def test_hysteresis_does_not_reach_past_its_own_band():
    """A station further under the threshold than the hysteresis still
    breaks the run (the trigger is not unbounded)."""
    def profile(x):
        if 40.0 <= x <= 55.0:
            return APRON_EDGE_WALL_MIN_DROP_M - 1.0
        return APRON_EDGE_WALL_MIN_DROP_M + 0.5

    stations, alts, outs = _straight_edge(length_m=100.0)
    layout = _FakeLayout()
    n, _ = AG._emit_apron_walls(
        layout, stations, alts, outs, _apron_ceil_off, STEP,
        _drop_profile(profile), None, None)
    assert n == 2


# ──────────────────────────────────────────────────────────────────────
# F3 — emit-side corridor clamp
# ──────────────────────────────────────────────────────────────────────
def _square_ring(side=20.0):
    coords = [(0.0, 0.0), (side, 0.0), (side, side), (0.0, side),
              (0.0, 0.0)]
    return coords, [EDGE_ALT] * len(coords)


def _entry(value_at_3m):
    """One solved CUT row 3 m outward carrying ``value_at_3m``."""
    pts = [(0.0, -3.0), (10.0, -3.0), (20.0, -3.0)]
    return {
        "zone_rows": [{"kind": "cut", "d0": 3.0, "pts": pts,
                       "depths": [3.0] * 3, "hosts": [(0.0, 0.0)] * 3}],
        "zone_values": {AG._vertex_key(*p): value_at_3m for p in pts},
    }


def _apron_envelope():
    def envelope_at(d):
        return adjacent_ground_envelope("apron", None, None, d)
    return envelope_at


def _corridor_at(d):
    fo, co = adjacent_ground_envelope("apron", None, None, d)
    return (EDGE_ALT + fo if fo is not None else None,
            EDGE_ALT + co if co is not None else None)


def test_solved_value_outside_the_corridor_is_clamped_and_counted():
    """The diagnosed collision: a foreign shape's variable drags this
    shape's band 1.5 m below its own corridor floor."""
    floor, ceiling = _corridor_at(3.0)
    assert floor is not None
    rogue = floor - 1.56          # the SPJC magnitude
    coords, ring_alts = _square_ring()
    AG._reset_apparatus_hits()
    resample = AG._make_solved_band_resampler(
        _entry(rogue), coords, ring_alts,
        lambda x, y, k: (999.0, False),
        envelope_at=_apron_envelope(), graded_width_m=APRON_SHOULDER_WIDTH_M)
    value, is_weld = resample(0.0, -3.0, "cut")
    assert not is_weld
    # "cut" drops the floor by design (below-floor terrain is the fill
    # machinery's) — so a CUT query is NOT floor-clamped ...
    assert abs(value - round(rogue, 1)) < 1e-6
    # ... but a FILL query at the same point is.
    value, _ = resample(0.0, -3.0, "fill")
    assert abs(value - round(floor, 1)) < 0.05, value
    assert AG._APPARATUS_HITS["band_corridor_clamped_vertices"] >= 1
    assert AG._BAND_CLAMP_MAX_DELTA_M > 1.0


def test_solved_value_above_the_ceiling_is_clamped():
    _floor, ceiling = _corridor_at(3.0)
    assert ceiling is not None
    coords, ring_alts = _square_ring()
    AG._reset_apparatus_hits()
    resample = AG._make_solved_band_resampler(
        _entry(ceiling + 5.0), coords, ring_alts,
        lambda x, y, k: (999.0, False),
        envelope_at=_apron_envelope(), graded_width_m=APRON_SHOULDER_WIDTH_M)
    value, _ = resample(0.0, -3.0, "cut")
    assert abs(value - round(ceiling, 1)) < 0.05, value
    assert AG._APPARATUS_HITS["band_corridor_clamped_vertices"] == 1


def test_solved_value_inside_the_corridor_passes_untouched():
    floor, ceiling = _corridor_at(3.0)
    lawful = round(0.5 * (floor + ceiling), 2)
    coords, ring_alts = _square_ring()
    AG._reset_apparatus_hits()
    resample = AG._make_solved_band_resampler(
        _entry(lawful), coords, ring_alts,
        lambda x, y, k: (999.0, False),
        envelope_at=_apron_envelope(), graded_width_m=APRON_SHOULDER_WIDTH_M)
    value, _ = resample(0.0, -3.0, "cut")
    assert abs(value - round(lawful, 1)) < 1e-6
    assert AG._APPARATUS_HITS["band_corridor_clamped_vertices"] == 0


def test_corridor_clamp_gate_off_returns_the_raw_solved_value(monkeypatch):
    monkeypatch.setattr(AG, "_BAND_CORRIDOR_CLAMP", False)
    _floor, ceiling = _corridor_at(3.0)
    rogue = ceiling + 5.0
    coords, ring_alts = _square_ring()
    AG._reset_apparatus_hits()
    resample = AG._make_solved_band_resampler(
        _entry(rogue), coords, ring_alts,
        lambda x, y, k: (999.0, False),
        envelope_at=_apron_envelope(), graded_width_m=APRON_SHOULDER_WIDTH_M)
    value, _ = resample(0.0, -3.0, "cut")
    assert abs(value - round(rogue, 1)) < 1e-6
    assert AG._APPARATUS_HITS["band_corridor_clamped_vertices"] == 0


def test_weld_row_is_never_clamped():
    """A vertex ON the pavement ring carries the pavement value verbatim —
    pavement identity outranks the corridor."""
    coords, ring_alts = _square_ring()
    AG._reset_apparatus_hits()
    resample = AG._make_solved_band_resampler(
        _entry(EDGE_ALT), coords, ring_alts,
        lambda x, y, k: (999.0, False),
        envelope_at=_apron_envelope(), graded_width_m=APRON_SHOULDER_WIDTH_M)
    assert resample(5.0, 0.0, "cut") == (EDGE_ALT, True)
    assert AG._APPARATUS_HITS["band_corridor_clamped_vertices"] == 0


# ──────────────────────────────────────────────────────────────────────
# F5 — apron wall SCOPE (pavement adjacency, owner ruling 2026-07-25)
# ──────────────────────────────────────────────────────────────────────
def _apron(x0, y0, x1, y1):
    return BuiltShape(polygon=Polygon([(x0, y0), (x1, y0), (x1, y1),
                                       (x0, y1)]),
                      role=ROLE_APRON, ref="apron",
                      node_altitudes=[EDGE_ALT] * 5)


def _neighbour_pavement(gap_m, length_m=100.0):
    """A second apron running parallel to y=0, ``gap_m`` outward."""
    return _apron(0.0, gap_m, length_m, gap_m + 20.0)


def _qualifier(host, others):
    layout = _FakeLayout([host] + list(others))
    return AG.apron_wall_frontage_qualifier(
        host, AG.apron_wall_pavement_adjacency_index(layout))


def test_qualifier_sees_pavement_inside_the_radius():
    host = _apron(0.0, -20.0, 100.0, 0.0)
    near = _neighbour_pavement(APRON_WALL_PAVEMENT_ADJACENCY_M - 1.0)
    q = _qualifier(host, [near])
    assert q is not None
    assert q(50.0, 0.0) is True


def test_qualifier_rejects_open_terrain_frontage():
    host = _apron(0.0, -20.0, 100.0, 0.0)
    far = _neighbour_pavement(APRON_WALL_PAVEMENT_ADJACENCY_M + 1.0)
    q = _qualifier(host, [far])
    assert q(50.0, 0.0) is False
    # The host never qualifies itself.
    assert _qualifier(host, [])(50.0, 0.0) is False


def test_qualifier_ignores_emitted_terrain_shapes():
    """A ``graded_strip`` band or a ``retaining_wall`` face is not
    pavement — otherwise the validator (which runs AFTER emission) would
    see a different index than the emitter did."""
    from auto_patch.layout import ROLE_GRADED_STRIP
    host = _apron(0.0, -20.0, 100.0, 0.0)
    band = BuiltShape(polygon=Polygon([(0.0, 1.0), (100.0, 1.0),
                                       (100.0, 3.0), (0.0, 3.0)]),
                      role=ROLE_GRADED_STRIP, ref="adjacent_ground")
    wall = BuiltShape(polygon=Polygon([(0.0, 3.0), (100.0, 3.0),
                                       (100.0, 4.0), (0.0, 4.0)]),
                      role=ROLE_RETAINING_WALL, ref="adjacent_ground_wall")
    assert _qualifier(host, [band, wall])(50.0, 0.0) is False


def test_qualifier_is_none_with_the_gate_off(monkeypatch):
    monkeypatch.setattr(AG, "_APRON_WALL_SCOPE", False)
    host = _apron(0.0, -20.0, 100.0, 0.0)
    near = _neighbour_pavement(1.0)
    layout = _FakeLayout([host, near])
    assert AG.apron_wall_frontage_qualifier(
        host, AG.apron_wall_pavement_adjacency_index(layout)) is None


def test_wall_emits_with_pavement_at_4m_and_not_at_6m():
    stations, alts, outs = _straight_edge(length_m=100.0)
    host = _apron(0.0, -20.0, 100.0, 0.0)

    near = _FakeLayout()
    n_near, _ = AG._emit_apron_walls(
        near, stations, alts, outs, _apron_ceil_off, STEP,
        _deep_dem(), None, None,
        station_filter=_qualifier(host, [_neighbour_pavement(4.0)]))
    assert n_near >= 1, "pavement 4 m out ⇒ the wall law applies"

    far = _FakeLayout()
    n_far, _ = AG._emit_apron_walls(
        far, stations, alts, outs, _apron_ceil_off, STEP,
        _deep_dem(), None, None,
        station_filter=_qualifier(host, [_neighbour_pavement(6.0)]))
    assert n_far == 0 and not far.shapes, \
        "open terrain ⇒ no wall; the raw DEM grades to the apron edge"


def test_open_frontage_drops_the_fill_band_but_keeps_the_cut():
    """The march-level half of the ruling: no shoulder/fill band on
    open-terrain apron frontage; a wingtip CUT still fires."""
    host = _apron(0.0, -20.0, 200.0, 0.0)
    coords = list(host.polygon.exterior.coords)
    ccw = bool(host.polygon.exterior.is_ccw)
    ring_alts = [EDGE_ALT] * len(coords)
    ceil_off, envelope_at, floor_depth = AG._band_family_closures(
        "apron", None, None, APRON_SHOULDER_WIDTH_M)
    from shapely.prepared import prep
    prep_static = prep(host.polygon)

    def _bands(sample, station_filter):
        AG._reset_apparatus_hits()
        return AG._derive_shape_stations_and_bands(
            coords, ccw, ring_alts, None, APRON_SHOULDER_WIDTH_M,
            100.0, 1.0, floor_depth, ceil_off, STEP, prep_static, set(),
            sample, fill_station_filter=station_filter)

    open_q = _qualifier(host, [_neighbour_pavement(6.0, length_m=200.0)])
    near_q = _qualifier(host, [_neighbour_pavement(4.0, length_m=200.0)])

    # Terrain 20 m BELOW the edge: a fill band is owed ... unless the
    # frontage is open terrain.
    low = lambda x, y: EDGE_ALT - 20.0
    fill_near, _cut, _st, _sa, _ou = _bands(low, near_q)
    assert fill_near, "pavement-adjacent frontage still fills"
    fill_open, _cut, _st, _sa, _ou = _bands(low, open_q)
    assert not fill_open, "open-terrain frontage is ungoverned on fill"
    assert AG._APPARATUS_HITS["apron_open_frontage_stations"] > 0

    # Terrain 20 m ABOVE the edge: the CUT fires either way.
    high = lambda x, y: EDGE_ALT + 20.0
    _f, cut_open, _st, _sa, _ou = _bands(high, open_q)
    assert cut_open, "a wingtip obstruction is cut wherever it stands"


def test_open_frontage_keeps_its_fill_band_with_the_gate_off(monkeypatch):
    monkeypatch.setattr(AG, "_APRON_WALL_SCOPE", False)
    host = _apron(0.0, -20.0, 200.0, 0.0)
    layout = _FakeLayout([host, _neighbour_pavement(6.0, length_m=200.0)])
    assert AG.apron_wall_frontage_qualifier(
        host, AG.apron_wall_pavement_adjacency_index(layout)) is None


# ──────────────────────────────────────────────────────────────────────
# F5 — validator lockstep (MIRROR 6)
# ──────────────────────────────────────────────────────────────────────
def _run_validator(monkeypatch, shapes, dem_offset_m):
    """``check_adjacent_ground`` over ``shapes`` with a flat DEM sitting
    ``dem_offset_m`` relative to the pavement edge."""
    from auto_patch import elevation, verification
    from auto_patch.layout import PavementLayout
    monkeypatch.setattr(
        elevation, "_sample_dem",
        lambda dem, tl, tn, lat, lon: EDGE_ALT + dem_offset_m)
    layout = PavementLayout(icao="ZZZZ", anchor=(0.0, 0.0))
    layout.shapes.extend(shapes)
    return verification.check_adjacent_ground(
        layout, dem=object(), tile_lat=0, tile_lon=0)


def test_validator_mirrors_the_open_frontage_scope(monkeypatch):
    """MIRROR 6: without it the reader flags every open apron edge the
    emitter is no longer allowed to fill."""
    host = _apron(0.0, -20.0, 200.0, 0.0)
    far = _neighbour_pavement(50.0, length_m=200.0)
    findings = _run_validator(monkeypatch, [host, far], dem_offset_m=-20.0)
    assert not [f for f in findings if f[0] == "should_fill"], findings


def test_validator_mirror_adds_no_findings_either_way(monkeypatch):
    """MIRROR 6 is a LOCKSTEP guarantee, and today an INERT one: the apron
    family's fill cap is the 3 m shoulder, which sits inside the reader's
    own 5 m station step, so ``check_adjacent_ground`` already mints no
    apron ``should_fill`` at all (the documented SUB-STEP CAPS divergence,
    which only ever makes the reader flag LESS).  Pinned both ways so a
    future change to either number cannot silently start flagging ground
    the owner's ruling leaves ungoverned."""
    from auto_patch import config as cfg
    host = _apron(0.0, -20.0, 200.0, 0.0)
    far = _neighbour_pavement(50.0, length_m=200.0)
    on = _run_validator(monkeypatch, [host, far], dem_offset_m=-20.0)
    monkeypatch.setattr(cfg, "APRON_WALL_SCOPE_ENABLED", False)
    off = _run_validator(monkeypatch, [host, far], dem_offset_m=-20.0)
    assert on == off
    assert not [f for f in on if f[0] == "should_fill"]


def test_validator_keeps_pavement_adjacent_frontage_in_scope(monkeypatch):
    """A frontage WITH pavement inside 5 m stays governed — the mirror
    narrows the scope, it does not disable the reader (asserted at the
    qualifier, the mirror's only input)."""
    host = _apron(0.0, -20.0, 200.0, 0.0)
    near = _apron(0.0, 4.0, 200.0, 24.0)
    q = _qualifier(host, [near])
    assert all(q(x, 0.0) for x in (10.0, 100.0, 190.0))


def test_validator_still_flags_cuts_on_open_frontage(monkeypatch):
    host = _apron(0.0, -20.0, 200.0, 0.0)
    far = _neighbour_pavement(50.0, length_m=200.0)
    findings = _run_validator(monkeypatch, [host, far], dem_offset_m=+20.0)
    assert any(f[0] == "should_cut" for f in findings), findings


def test_pavement_block_clips_the_wall_off_groundside():
    """BUILT-PAVEMENT KEEPOUT (owner defect 2026-07-27, HECA wall
    #1668): the wall SCOPE counts groundside as the qualifying
    neighbour, but the clip set excluded it — a wall owed at a 4-5 m
    apron↔groundside step emitted ON TOP of the groundside surface.
    ``pavement_block`` now clips it out."""
    stations, alts, outs = _straight_edge(length_m=100.0)
    # The wall face occupies y in [3, 4]; groundside pavement covers the
    # middle 40 m of the frontage (buffered block, as the call site
    # builds it).
    groundside = Polygon([(30.0, 2.0), (70.0, 2.0),
                          (70.0, 6.0), (30.0, 6.0)])

    layout = _FakeLayout()
    n, union = AG._emit_apron_walls(
        layout, stations, alts, outs, _apron_ceil_off, STEP,
        _deep_dem(), None, None,
        pavement_block=groundside.buffer(1.0))
    walls = _wall_shapes(layout)
    assert n == len(walls) == 2, "the run splits around the keepout"
    for s in walls:
        assert s.polygon.intersection(groundside).area < 1e-6, (
            "no wall face may cover the groundside pavement")


def test_no_pavement_block_keeps_the_full_run():
    """``pavement_block=None`` (every airport without groundside near an
    apron wall) is byte-identical to the pre-fix emission."""
    stations, alts, outs = _straight_edge(length_m=100.0)
    layout = _FakeLayout()
    n, _ = AG._emit_apron_walls(
        layout, stations, alts, outs, _apron_ceil_off, STEP,
        _deep_dem(), None, None, pavement_block=None)
    assert n == 1
    walls = _wall_shapes(layout)
    assert len(walls) == 1 and abs(walls[0].polygon.area - 100.0) < 1.0
