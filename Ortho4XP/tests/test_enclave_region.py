"""ENCLAVE REGION LAW — the published region, and its three consumers.

Spec: ``docs/specs/enclave-region-law-spec.md``.  Owner law: G-ENCLAVE
2026-07-28 ("groundside can never be surrounded by airside pavement
unless it has a tunnel or bridge service road to get out") extended
2026-08-07 to EVERYTHING inside such a region, paved or bare — "such an
area is airside-interior and takes the gap interior ring + spine
treatment; a retaining wall or groundside terrace there is a defect
regardless of which mechanism minted it".

Synthetic fixtures only: a rectangular pavement frame enclosing one hole,
the same shape as the gap-fill and pocket-collar unit fixtures.

What this pins, criterion by criterion (spec acceptance 5):

  * ONE COMPUTATION — the role sets the three former constructions used
    are pinned equal, and a build publishes the regions exactly ONCE
    (the consumers read the store, they never recompute);
  * POINT-IN-ENCLAVE — a shape that does NOT fill its enclave still
    reads enclosed (the retired ring-cover predicate's blind spot), and
    bare ground inside the region is reachable by the same test;
  * THE ESCAPE CLAUSE — applied once, in the publication, so no consumer
    can forget it;
  * THE GAP BLOCKER — an in-enclave shape does not veto the ruled
    ring+spine treatment, and the SAME geometry with nothing published
    still does (the A/B that shows the law is doing the work);
  * THE BAND CONSUMER — enclave-facing stations stand down in the
    emitter's march AND in the validator's mirror, while frontage facing
    open terrain is untouched; and the keep-out is POCKET-scoped, so an
    airfield infield keeps its graded strips.
"""
from __future__ import annotations

import os
import sys

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.prepared import prep

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ``pipeline`` first: junction_repair <-> elevation is an import cycle.
import auto_patch.pipeline as _PIPELINE  # noqa: E402,F401
from auto_patch import adjacent_ground as AG  # noqa: E402
from auto_patch import enclaves as EN  # noqa: E402
from auto_patch import gap_fill as GF  # noqa: E402
from auto_patch import pavement_scoring as PS  # noqa: E402
from auto_patch import verification as VF  # noqa: E402
from auto_patch.clearance import _AIRSIDE_PAVEMENT_ROLES  # noqa: E402
from auto_patch.config import (  # noqa: E402
    GAP_FILL_MAX_WIDTH_M,
    GAP_FILL_MIN_AREA_M2,
)
from auto_patch.layout import (  # noqa: E402
    BuiltShape,
    ROLE_APRON,
    ROLE_BUILDING,
    ROLE_GRADED_STRIP,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_RUNWAY,
    ROLE_STUB,
    ROLE_TUNNEL_RAMP,
)

EDGE_ALT = 100.0
# The hole: x in [30, 130], y in [30, 90] -> 100 x 60 m = 6,000 m2.
# Area over ``GAP_FILL_MIN_AREA_M2`` and short side under
# ``GAP_FILL_MAX_WIDTH_M``, so it is both a gap candidate and a
# pocket-width enclave.
HOLE = (30.0, 30.0, 130.0, 90.0)


class _FakeLayout:
    """The minimum surface the enclave/gap code reads off a layout."""

    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.airport_boundary = None
        self.anchor = (0.0, 0.0)

    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)

    def ll_to_m(self, lat, lon):
        return (lon * 111320.0, lat * 111320.0)


def _rect(x0, y0, x1, y1, role, alt=EDGE_ALT):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return BuiltShape(polygon=poly, role=role,
                      node_altitudes=[alt] * len(poly.exterior.coords))


def _frame(extra=()):
    """A rectangular pavement frame enclosing ``HOLE``.

    South and north bars are RUNWAY, the two end bars STUB — every role
    in the airside surround set.  ``extra`` shapes are appended as-is."""
    x0, y0, x1, y1 = HOLE
    shapes = [
        _rect(0.0, 0.0, 160.0, y0, ROLE_RUNWAY),        # south bar
        _rect(0.0, y1, 160.0, 120.0, ROLE_RUNWAY),      # north bar
        _rect(0.0, y0, x0, y1, ROLE_STUB),              # west bar
        _rect(x1, y0, 160.0, y1, ROLE_STUB),            # east bar
    ]
    shapes.extend(extra)
    return _FakeLayout(shapes)


def _sliver(cx=80.0, cy=60.0, half=1.2, role=ROLE_GROUNDSIDE_PAVEMENT):
    """A small shape floating in the middle of the hole.

    ~5.8 m2 — over the gap blocker's 1.0 m2 bar (so it vetoes today) and
    under the scorer's 10 m2 candidate floor (so the old sweep could
    never even look at it).  It touches nothing: three of its flanks
    face the void's own bare interior, which is why a ring-COVERAGE
    predicate can never call it enclosed."""
    return _rect(cx - half, cy - half, cx + half, cy + half, role)


def _dem_at(x, y):
    return EDGE_ALT - 3.0


# ═════════════════════════════════════════════════════════════════════
# 1. ONE computation
# ═════════════════════════════════════════════════════════════════════

def test_the_three_role_sets_are_one_set():
    """The enclave union, the gap detection union and the touch chain all
    ran off byte-identical role sets; the region law now owns the
    vocabulary and this pins the coincidence, so a divergence has to be
    a conscious act rather than a silent drift."""
    assert EN.ENCLAVE_AIRSIDE_ROLES == frozenset(_AIRSIDE_PAVEMENT_ROLES)
    assert EN.ENCLAVE_AIRSIDE_ROLES == PS._CHAIN_ROLES
    # Buildings JOIN the surround (owner, CYXY building4): a vehicle
    # cannot leave through a building.
    assert ROLE_BUILDING in EN.ENCLAVE_SURROUND_ROLES
    assert ROLE_BUILDING not in EN.ENCLAVE_AIRSIDE_ROLES
    assert ROLE_TUNNEL_RAMP in EN.ENCLAVE_ESCAPE_ROLES


def test_regions_are_published_once_and_read_many_times(monkeypatch):
    """Single-pass principle: the geometry is built ONE time and the
    consumers read the store."""
    calls = []
    real = EN.compute_airside_enclaves
    monkeypatch.setattr(EN, "compute_airside_enclaves",
                        lambda layout: calls.append(1) or real(layout))
    layout = _frame([_sliver()])
    EN.publish_airside_enclaves(layout)
    assert len(calls) == 1
    # Three consumer reads, no recomputation.
    assert EN.point_in_enclave(layout, 80.0, 60.0) is True
    assert EN.enclave_covering(layout, Polygon(
        [(HOLE[0], HOLE[1]), (HOLE[2], HOLE[1]),
         (HOLE[2], HOLE[3]), (HOLE[0], HOLE[3])])) is not None
    assert EN.enclave_band_keepout_prepared(layout) is not None
    assert len(calls) == 1


def test_the_settled_frame_replaces_the_classify_frame():
    """TWO FRAMES, ONE STORE.  G-ENCLAVE must run at classification, but
    that union is mid-build and more FRAGMENTED than the surface that
    ships — a fragment can be pocket-width where the settled region is a
    3.4 km² infield.  The re-publication REPLACES the store and clears
    every derived cache, so no consumer can read a frame it was not
    built for (measured at HECA: reading the classify frame in the band
    march deleted 152,734 m² of Annex 14 graded strip)."""
    from auto_patch import enclaves as EN

    layout = _frame()
    EN.publish_airside_enclaves(layout)
    assert getattr(layout, EN._STAGE_ATTRIBUTE) == "classify"
    keepout_classify = EN.enclave_band_keepout_union(layout)
    assert keepout_classify is not None

    # The settled frame: a wall of pavement now splits the hole, and the
    # west half is filled outright — a different region set entirely.
    x0, y0, x1, y1 = HOLE
    layout.shapes.append(_rect(x0, y0, 80.0, y1, ROLE_APRON))
    EN.republish_airside_enclaves_settled(layout)
    assert getattr(layout, EN._STAGE_ATTRIBUTE) == "settled"
    records = EN.airside_enclaves(layout)
    assert len(records) == 1
    assert records[0].area_m2 == pytest.approx((x1 - 80.0) * (y1 - y0))
    # Every derived cache followed the store.
    keepout_settled = EN.enclave_band_keepout_union(layout)
    assert keepout_settled.area == pytest.approx(records[0].area_m2)
    assert keepout_settled.area < keepout_classify.area
    assert EN.point_in_enclave(layout, 50.0, 60.0) is False   # now paved
    assert EN.point_in_enclave(layout, 100.0, 60.0) is True


def test_the_settled_republication_is_inert_without_a_classify_frame():
    """No classifier ran (scoring off, synthetic layouts): nothing was
    published, so the re-publication does not invent a frame — the lazy
    accessor computes in the frame its first reader asks from."""
    from auto_patch import enclaves as EN

    layout = _frame()
    assert EN.republish_airside_enclaves_settled(layout) == []
    assert getattr(layout, EN.ENCLAVE_STORE_ATTRIBUTE, None) is None
    assert len(EN.airside_enclaves(layout)) == 1


def test_an_unpublished_layout_computes_lazily_once(monkeypatch):
    """Scoring off / synthetic layouts: the accessor publishes on first
    read and never recomputes after that."""
    calls = []
    real = EN.compute_airside_enclaves
    monkeypatch.setattr(EN, "compute_airside_enclaves",
                        lambda layout: calls.append(1) or real(layout))
    layout = _frame()
    assert len(EN.airside_enclaves(layout)) == 1
    assert len(EN.airside_enclaves(layout)) == 1
    assert len(calls) == 1


# ═════════════════════════════════════════════════════════════════════
# 2. Point-in-enclave
# ═════════════════════════════════════════════════════════════════════

def test_the_region_is_the_hole():
    layout = _frame()
    records = EN.publish_airside_enclaves(layout)
    assert len(records) == 1
    x0, y0, x1, y1 = HOLE
    assert records[0].area_m2 == pytest.approx((x1 - x0) * (y1 - y0))
    assert records[0].short_side_m == pytest.approx(y1 - y0)
    assert records[0].escape_ids == ()


def test_bare_ground_and_a_non_filling_shape_both_read_enclosed():
    """The law gap the dossier attributed: 87.6 % of the specimen enclave
    is bare ground outside the shape universe, and its one pavement shape
    read 0.0 % ring coverage.  A region test reaches both."""
    sliver = _sliver()
    layout = _frame([sliver])
    EN.publish_airside_enclaves(layout)
    # Bare ground, no shape at all.
    assert EN.point_in_enclave(layout, 50.0, 45.0) is True
    # The floating shape, which fills 0.1 % of the region.
    assert EN.shape_in_enclave(layout, sliver) is True
    assert sliver.polygon.area < 10.0            # under the old floor
    # Outside the frame is open terrain, never an enclave.
    assert EN.point_in_enclave(layout, 200.0, 200.0) is False
    assert EN.point_in_enclave(layout, 80.0, 10.0) is False


def test_an_enclave_shape_reverdicts_out_of_groundside():
    """End-to-end through the classifier's own gate: G-ENCLAVE removes
    GROUNDSIDE for a shape in a published enclave."""
    layout = _frame()
    EN.publish_airside_enclaves(layout)
    record = PS.score_shape(_sliver().polygon, layout, enclosed=True)
    assert "G-ENCLAVE" in record["gates"]
    assert "GROUNDSIDE" not in record["candidates"]


# ═════════════════════════════════════════════════════════════════════
# 3. The escape clause
# ═════════════════════════════════════════════════════════════════════

def test_a_touching_tunnel_ramp_defeats_the_region():
    x0, _y0, x1, y1 = HOLE
    ramp = _rect((x0 + x1) / 2 - 5.0, y1 - 2.0,
                 (x0 + x1) / 2 + 5.0, y1 + 8.0, ROLE_TUNNEL_RAMP)
    layout = _frame([ramp])
    assert EN.publish_airside_enclaves(layout) == []
    assert EN.point_in_enclave(layout, 80.0, 60.0) is False
    assert EN.enclave_band_keepout_union(layout) is None


def test_an_is_bridge_shape_defeats_the_region():
    """``is_bridge`` pavement is an escape too — the predicate reads the
    flag, not only the role."""
    x0, _y0, x1, y1 = HOLE
    deck = _rect((x0 + x1) / 2 - 5.0, y1 - 2.0,
                 (x0 + x1) / 2 + 5.0, y1 + 8.0, ROLE_GRADED_STRIP)
    deck.is_bridge = True
    layout = _frame([deck])
    assert EN.publish_airside_enclaves(layout) == []


def test_a_distant_ramp_is_not_an_escape():
    ramp = _rect(300.0, 300.0, 320.0, 320.0, ROLE_TUNNEL_RAMP)
    layout = _frame([ramp])
    assert len(EN.publish_airside_enclaves(layout)) == 1


# ═════════════════════════════════════════════════════════════════════
# 4. The gap-fill blocker
# ═════════════════════════════════════════════════════════════════════

def _gap_faces(layout):
    return [s for s in layout.shapes
            if s.role == ROLE_GRADED_STRIP and s.ref == "gap_fill_spine"]


def test_an_in_enclave_shape_does_not_veto_the_ruled_treatment():
    """THE specimen mechanism, in a fixture: a 5.8 m2 groundside sliver
    sent a whole apron-ringed void to the band consumer.  With the
    region published, the void takes the ring + spine treatment."""
    layout = _frame([_sliver()])
    EN.publish_airside_enclaves(layout)
    n = GF.emit_gap_fill_spines(layout, None, 0, 0)
    assert n >= 1
    assert _gap_faces(layout)


def test_the_same_sliver_still_vetoes_with_nothing_published():
    """The A/B that shows the LAW is doing the work, not the geometry:
    identical shapes, an empty published set, and the foreign-shape
    blocker fires exactly as it did before."""
    layout = _frame([_sliver()])
    layout.airside_enclaves = []          # nothing published
    assert GF.emit_gap_fill_spines(layout, None, 0, 0) == 0
    assert _gap_faces(layout) == []


def test_a_foreign_shape_outside_any_enclave_still_vetoes():
    """The blocker is not disabled — a shape in a gap that is NOT a
    published enclave (here: the escape clause voids the region) blocks
    exactly as before."""
    x0, _y0, x1, y1 = HOLE
    ramp = _rect((x0 + x1) / 2 - 5.0, y1 - 2.0,
                 (x0 + x1) / 2 + 5.0, y1 + 8.0, ROLE_TUNNEL_RAMP)
    layout = _frame([_sliver(), ramp])
    EN.publish_airside_enclaves(layout)
    assert EN.airside_enclaves(layout) == []
    assert GF.emit_gap_fill_spines(layout, None, 0, 0) == 0


def test_surround_material_and_the_runway_end_regime_are_never_exempt():
    """The exemption covers what an enclave CONTAINS, not what DEFINES
    it: a building is the owner's own escape-proof boundary material
    (CYXY building4) and a runway-end skirt carries the governed
    runway-end profile, so each is decided by its own law/gate — pinned
    directly on the predicate, since both are gap PARENTS by default and
    only reach the blocker with their sub-gate off."""
    from auto_patch.layout import REF_RUNWAY_END_SKIRT, ROLE_RUNWAY_CLEARANCE

    pad = _rect(70.0, 50.0, 90.0, 70.0, ROLE_BUILDING)
    skirt = BuiltShape(polygon=Polygon([(70.0, 50.0), (90.0, 50.0),
                                        (90.0, 70.0), (70.0, 70.0)]),
                       role=ROLE_RUNWAY_CLEARANCE,
                       ref=REF_RUNWAY_END_SKIRT,
                       node_altitudes=[EDGE_ALT] * 5)
    assert GF._enclave_exempt(pad) is False
    assert GF._enclave_exempt(skirt) is False
    # What the law DOES reach: the enclave's interior contents.
    assert GF._enclave_exempt(_sliver()) is True
    assert GF._enclave_exempt(
        _rect(70.0, 50.0, 72.0, 52.0, ROLE_GRADED_STRIP)) is True


def test_the_construct_pass_mirrors_the_emitter():
    """Parity is load-bearing (the emitter matches spines against the
    pre-solve store by coordinate), so the pre-solve construction must
    apply the same enclave rule."""
    layout = _frame([_sliver()])
    EN.publish_airside_enclaves(layout)
    assert GF.construct_gap_fill_presolve(layout) >= 1

    layout2 = _frame([_sliver()])
    layout2.airside_enclaves = []
    assert GF.construct_gap_fill_presolve(layout2) == 0


# ═════════════════════════════════════════════════════════════════════
# 5. The adjacent-ground band consumer
# ═════════════════════════════════════════════════════════════════════

def _march(layout, shape, enclave_prep):
    """The emitter's shared station march for one frame bar (the
    pocket-collar unit fixture's harness, verbatim except the zone)."""
    from auto_patch.config import (CLEARANCE_MAX_REACH_M,
                                   CLEARANCE_STATION_STEP_M,
                                   taxiway_strip_graded_half_width_for_letter)
    from auto_patch.grade_law import adjacent_ground_envelope

    width = taxiway_strip_graded_half_width_for_letter("C")
    reach = CLEARANCE_MAX_REACH_M["taxiway"]

    def ceil_off(d):
        return adjacent_ground_envelope("taxiway", None, "C", d)[1]

    def floor_depth(d):
        f = adjacent_ground_envelope("taxiway", None, "C", min(d, width))[0]
        return None if f is None else -f

    others = [s.polygon for s in layout.shapes if s is not shape
              and s.polygon is not None and not s.polygon.is_empty]
    prep_static = prep(unary_union(others))
    coords = list(shape.polygon.exterior.coords)
    return AG._derive_shape_stations_and_bands(
        coords, bool(shape.polygon.exterior.is_ccw),
        list(shape.node_altitudes), None, width, reach, 1.0,
        floor_depth, ceil_off, CLEARANCE_STATION_STEP_M, prep_static,
        set(), _dem_at, enclave_zone_prep=enclave_prep)


def _hole_facing_refs(stations, st_alts):
    """Stations on the south bar's NORTH edge (y = 30) — the frontage
    that faces the hole — that kept an edge reference."""
    x0, y0, x1, _y1 = HOLE
    return sum(1 for (sx, sy), a in zip(stations, st_alts)
               if a is not None and abs(sy - y0) < 1e-6 and x0 < sx < x1)


def _open_terrain_refs(stations, st_alts):
    """Stations on the south bar's SOUTH edge (y = 0), facing open
    terrain — the control."""
    return sum(1 for (_sx, sy), a in zip(stations, st_alts)
               if a is not None and abs(sy) < 1e-6)


def test_the_band_march_stands_down_inside_an_enclave():
    layout = _frame()
    EN.publish_airside_enclaves(layout)
    zone = AG._enclave_zone_prep(layout)         # the consumer's wrapper
    assert zone is not None
    south = layout.shapes[0]

    _f0, _c0, st0, alts0, _o0 = _march(layout, south, None)
    _f1, _c1, st1, alts1, _o1 = _march(layout, south, zone)

    assert _hole_facing_refs(st0, alts0) > 0
    assert _hole_facing_refs(st1, alts1) == 0
    # Only the enclave frontage stood down.
    assert _open_terrain_refs(st1, alts1) == _open_terrain_refs(st0, alts0)


def test_the_stand_down_is_counted_as_its_own_apparatus_row():
    layout = _frame()
    EN.publish_airside_enclaves(layout)
    zone = AG._enclave_zone_prep(layout)
    AG._reset_apparatus_hits()
    _march(layout, layout.shapes[0], zone)
    assert AG._APPARATUS_HITS["enclave_zone_excluded_stations"] > 0


def test_the_validator_mirror_skips_the_same_stations():
    """MIRROR 8: the reader must not flag ground the emitter lawfully
    never banded, or every enclave becomes a should_fill finding."""
    layout = _frame()
    EN.publish_airside_enclaves(layout)
    zone = VF._airside_enclave_zone_prep(layout)
    assert zone is not None
    south = layout.shapes[0]
    coords = list(south.polygon.exterior.coords)
    ring_alts = list(south.node_altitudes)

    def _never_covered(px, py):
        return False

    args = (coords, bool(south.polygon.exterior.is_ccw), ring_alts,
            None, 5.0, set(), _never_covered)
    st_x0, st_y0, _o0, ref0, _f0, _s0, _e0 = VF._adjacent_ground_stations(
        *args)
    st_x1, st_y1, _o1, ref1, _f1, _s1, _e1 = VF._adjacent_ground_stations(
        *args, enclave_zone_prep=zone)

    st0 = list(zip(st_x0, st_y0))
    st1 = list(zip(st_x1, st_y1))
    assert _hole_facing_refs(st0, ref0) > 0
    assert _hole_facing_refs(st1, ref1) == 0
    assert _open_terrain_refs(st1, ref1) == _open_terrain_refs(st0, ref0)


def test_an_infield_sized_region_is_published_but_not_band_territory():
    """The keep-out is POCKET-scoped.  A big airport's runway/taxiway
    loops make the whole INFIELD a bounded complement component; its
    graded strips are Annex 14 ground the bands own, so the keep-out
    must not reach it — while G-ENCLAVE and the gap blocker still see
    the region."""
    wide = 3.0 * GAP_FILL_MAX_WIDTH_M
    infield = Polygon([(0.0, 0.0), (wide + 60.0, 0.0),
                       (wide + 60.0, wide + 60.0), (0.0, wide + 60.0)])
    hole = Polygon([(30.0, 30.0), (30.0 + wide, 30.0),
                    (30.0 + wide, 30.0 + wide), (30.0, 30.0 + wide)])
    donut = infield.difference(hole)
    ring = BuiltShape(polygon=donut, role=ROLE_RUNWAY,
                      node_altitudes=[EDGE_ALT]
                      * len(donut.exterior.coords))
    apron = _rect(-60.0, -60.0, -10.0, -10.0, ROLE_APRON)
    layout = _FakeLayout([ring, apron])
    records = EN.publish_airside_enclaves(layout)
    assert len(records) == 1
    assert records[0].short_side_m > GAP_FILL_MAX_WIDTH_M
    assert EN.point_in_enclave(layout, 30.0 + wide / 2, 30.0 + wide / 2)
    assert EN.enclave_band_keepout_union(layout) is None
    assert AG._enclave_zone_prep(layout) is None


def test_a_sub_gap_area_pocket_is_still_band_keepout():
    """A pocket UNDER ``GAP_FILL_MIN_AREA_M2`` gets no gap face (the gap
    law's economy floor), and it is still enclave interior: the band and
    its retaining wall stay out.  HECA carries one such void, 82.9 m2
    with a wall in it."""
    small = (30.0, 30.0, 38.0, 38.0)     # 64 m2 < GAP_FILL_MIN_AREA_M2
    x0, y0, x1, y1 = small
    shapes = [
        _rect(0.0, 0.0, 70.0, y0, ROLE_RUNWAY),
        _rect(0.0, y1, 70.0, 70.0, ROLE_RUNWAY),
        _rect(0.0, y0, x0, y1, ROLE_STUB),
        _rect(x1, y0, 70.0, y1, ROLE_STUB),
    ]
    layout = _FakeLayout(shapes)
    records = EN.publish_airside_enclaves(layout)
    assert len(records) == 1
    assert records[0].area_m2 < GAP_FILL_MIN_AREA_M2
    assert EN.enclave_band_keepout_union(layout) is not None
