"""Terrain-side BUILDING PADS — the pad request CONSUMER
(``auto_patch.object_pads``), its law (``grade_law.object_pad_*``) and its
validator (``verification.check_object_pads``).

Spec: ``docs/specs/per-cluster-object-seating-spec.md`` §5.1 (THE PAD
LAW), §5.2 (next-build convergence + ``emitted`` records), §5.4
(emission: role, precedence, decimation, ordering), §5.5 (validator
reader); chartered by ``docs/specs/object-reseat-threshold-spec.md`` §2.3
(gate default ON, env kill switch).

Headless and fixture-free: a synthetic flat DEM, one apron rectangle and
hand-built pad requests, so every assertion is about the LAW and the
emitter's contract rather than about one airport's terrain.

What is pinned here:

* THE TARGET (§5.1 clause 1) — the pad's core holds the request's
  ``target_ground_metres`` exactly; an over-cap request is REFUSED with
  its measured numbers and emits nothing;
* PAVEMENT WINS ABSOLUTELY (§5.1 clause 2, the R2 hard clause) — pads are
  clipped against pavement, a pad wholly inside pavement is inadmissible,
  and every pavement shape is byte-identical across the emitter;
* THE WELD (§5.1 clause 3, ruling R4) — a pad boundary vertex on a
  pavement ring carries the pavement's own value, and a short run pulls
  the pad TARGET toward the pavement with the shortfall reported;
* THE OPEN-SIDE BLEND (§5.1 clause 4) — the pad meets raw DEM at the
  margin edge, so there is no cliff onto untouched ground;
* CONVERGENCE (§5.2) — an ``emitted`` record re-emits byte-stably after
  its request converges away, a live request supersedes its record, and a
  law change expires it with a reason;
* the GATE is byte-inert off;
* the validator is finding-clean on a lawful emission and fires on a
  tampered one (lockstep, ruling R5).
"""
import copy
import json
import math

import numpy as np
import pytest
from shapely.geometry import Polygon

from auto_patch import config as apc
from auto_patch import object_pads, post_mesh, verification
from auto_patch.grade_law import (
    object_pad_admissible,
    object_pad_blend_elevation,
    object_pad_pull_shortfall_m,
    object_pad_pull_toward_pavement,
    object_pad_relief_m,
)
from auto_patch.layout import (
    R_EARTH,
    ROLE_APRON,
    ROLE_OBJECT_PAD,
    BuiltShape,
    PavementLayout,
)

LAT0, LON0 = 25.25, 51.60
TILE_LAT, TILE_LON = 25, 51
COS0 = math.cos(math.radians(LAT0))
BASE_TERRAIN_M = 5.0
APRON_ALT_M = 6.0
MARGIN_M = 2.0                       # DSF_OBJECT_FOOT_PAD_MARGIN_M default


class FakeDEM:
    """The read surface of ``O4_DEM_Utils.DEM`` the sampler uses."""

    def __init__(self, n: int = 1201, base: float = BASE_TERRAIN_M):
        self.x0, self.x1, self.y0, self.y1 = 0.0, 1.0, 0.0, 1.0
        self.nxdem = self.nydem = n
        self.alt_dem = np.full((n, n), float(base), dtype=np.float32)
        self.nodata = -32768

    def alt(self, node):
        x, y = node
        nmax = self.nxdem - 1
        x = min(max(float(x), self.x0), self.x1)
        y = min(max(float(y), self.y0), self.y1)
        j = int(round(x * nmax))
        i = int(round((1.0 - y) * nmax))
        return float(self.alt_dem[i, j])


def make_layout(apron_ring=None, apron_alt: float = APRON_ALT_M):
    """A layout holding one flat apron rectangle (the graded pavement the
    PAD LAW clips and welds against).  ``apron_ring`` in local metres."""
    layout = PavementLayout(icao="TEST", anchor=(LAT0, LON0))
    if apron_ring is None:
        # Near enough that the pads at the origin are unambiguously THIS
        # airport's ground (the tile sidecar is claimed geometrically —
        # ``object_pads._footprint_claim``), far enough that nothing welds
        # or clips unless a test moves it.
        apron_ring = [(20.0, 20.0), (100.0, 20.0),
                      (100.0, 100.0), (20.0, 100.0)]
    layout.shapes.append(BuiltShape(
        polygon=Polygon(apron_ring + [apron_ring[0]]),
        role=ROLE_APRON, ref="APRON",
        altitude=apron_alt,
        node_altitudes=[apron_alt] * (len(apron_ring) + 1)))
    return layout


def square_ring(cx: float, cy: float, half: float):
    return [(cx - half, cy - half), (cx + half, cy - half),
            (cx + half, cy + half), (cx - half, cy + half)]


def request(layout, ring_m, target_m: float, *, cluster_id: int = 1,
            base_y: float = 0.0, over_cap: bool = False,
            extra_rings_m=()) -> dict:
    """One ``ClusterPadRequest`` in the sidecar's own shape (post_mesh
    writes exactly these keys; rings are ``(lon, lat)``, unclosed).

    Since the footprint-hugging law (object-reseat-threshold-spec §2.5) a
    request carries ``rings_lonlat`` — one ring per connected component
    of its contact parts — so ``extra_rings_m`` adds the further
    components of a spread-out group."""
    def _ll(ring):
        out = []
        for x, y in ring:
            lat, lon = layout.m_to_ll(x, y)
            out.append([lon, lat])
        return out

    rings_ll = [_ll(ring) for ring in (ring_m, *extra_rings_m)]
    cx = sum(p[0] for p in ring_m) / len(ring_m)
    cy = sum(p[1] for p in ring_m) / len(ring_m)
    lat, lon = layout.m_to_ll(cx, cy)
    return {
        "kind": "cluster",
        "cluster_id": cluster_id,
        "structure_index": 0,
        "resource_path": f"Buildings/pad{cluster_id}.obj",
        "latitude": lat,
        "longitude": lon,
        "base_y": base_y,
        "residual_metres": target_m - BASE_TERRAIN_M,
        "target_ground_metres": target_m,
        "part_count": 1,
        "over_relief_cap": over_cap,
        "pavement_clipped": False,
        "rings_lonlat": rings_ll,
    }


def sidecar(requests, emitted=None, icao: str = "TEST",
            version: int | None = None) -> dict:
    payload = {
        "version": (post_mesh.OBJECT_FOOT_PAD_SIDECAR_VERSION
                    if version is None else version),
        "tile": "+25+051",
        "airports": [{"icao": icao, "pack_root": "", "requests": requests}],
    }
    if emitted is not None:
        payload["emitted"] = emitted
    return payload


def pads(layout):
    return [s for s in layout.shapes if s.role == ROLE_OBJECT_PAD]


def cores(layout):
    return [s for s in pads(layout)
            if (s.ref or "").startswith(object_pads.REF_PAD_CORE + ":")]


def blends(layout):
    return [s for s in pads(layout)
            if (s.ref or "").startswith(object_pads.REF_PAD_BLEND + ":")]


def emit(layout, dem, side):
    return object_pads.emit_object_pads(
        layout, dem, TILE_LAT, TILE_LON, icao="TEST", sidecar=side)


def kinds(findings):
    return {f[0] for f in findings}


@pytest.fixture
def gate_on(monkeypatch):
    """The gate is read at CALL time precisely so this works."""
    monkeypatch.setattr(apc, "DSF_OBJECT_OBJECT_PADS", True)


@pytest.fixture
def dem():
    return FakeDEM()


# ══════════════════════════════════════════════════════════════════════
# THE PAD LAW — pure scalars (grade_law), shared by emitter and validator
# ══════════════════════════════════════════════════════════════════════

def test_the_relief_cap_is_the_owners_cap_and_is_symmetric():
    """§5.1 clause 1: "as close as feasible to DEM, then some adjustment
    to terrain is acceptable" — bounded by DSF_OBJECT_PAD_MAX_RELIEF_M,
    and pads may RAISE or LOWER (a cut bench is a pad)."""
    assert object_pad_relief_m(8.0, 5.0) == pytest.approx(3.0)
    assert object_pad_relief_m(2.0, 5.0) == pytest.approx(-3.0)
    assert object_pad_admissible(8.0, 5.0, 3.0)
    assert object_pad_admissible(2.0, 5.0, 3.0)
    assert not object_pad_admissible(8.01, 5.0, 3.0)
    assert not object_pad_admissible(1.99, 5.0, 3.0)


def test_the_pull_toward_pavement_never_moves_the_pavement():
    """§5.1 clause 3: where the run is too short for the step, the PAD's
    target is pulled toward the pavement value — pavement wins over the
    building base too — and the shortfall is a residual, not a cliff."""
    # Long run: the full step fits at the cap, so nothing is pulled.
    assert object_pad_pull_toward_pavement(6.5, 6.0, 40.0, 0.05) == \
        pytest.approx(6.5)
    # Short run: the pad gives way, by exactly cap * run.
    pulled = object_pad_pull_toward_pavement(6.5, 6.0, 2.0, 0.05)
    assert pulled == pytest.approx(6.1)
    assert object_pad_pull_shortfall_m(6.5, pulled) == pytest.approx(0.4)
    # Symmetric below the pavement, and a zero run pins to pavement.
    assert object_pad_pull_toward_pavement(5.5, 6.0, 2.0, 0.05) == \
        pytest.approx(5.9)
    assert object_pad_pull_toward_pavement(5.5, 6.0, 0.0, 0.05) == \
        pytest.approx(6.0)


def test_the_blend_width_is_per_request_and_never_eats_the_interior():
    """§5.1 clause 4 says the blend crosses "a
    ``DSF_OBJECT_FOOT_PAD_MARGIN_M``-class margin, PER-REQUEST".  A
    generous ring keeps the nominal 2 m; a ring only a few metres across
    — the OTHH corpus's median cluster request is 18 m², a ~1 m hull
    dilated to a 12-gon — would be entirely consumed by it, so the blend
    takes at most half the pad's own inradius and the interior survives."""
    from auto_patch.grade_law import object_pad_blend_width_m

    # 20 x 20 m ring: inradius 10, half of that is 5 ⇒ the nominal margin.
    assert object_pad_blend_width_m(400.0, 80.0, 2.0) == pytest.approx(2.0)
    # 5 x 5 m ring: inradius 2.5 ⇒ a 1.25 m ramp, and 2.5 x 2.5 m of core.
    assert object_pad_blend_width_m(25.0, 20.0, 2.0) == pytest.approx(1.25)
    # Degenerate input can never mint a pad.
    assert object_pad_blend_width_m(0.0, 0.0, 2.0) == 0.0


def test_the_open_side_blend_reaches_raw_dem_at_the_margin_edge():
    """§5.1 clause 4: signed offset from the pad edge anchor, decaying to
    zero at the margin — so the pad meets untouched ground exactly, with
    no standoff groove and no unbounded tail."""
    assert object_pad_blend_elevation(8.0, 5.0, 0.0, 2.0) == \
        pytest.approx(8.0)
    assert object_pad_blend_elevation(8.0, 5.0, 1.0, 2.0) == \
        pytest.approx(6.5)
    assert object_pad_blend_elevation(8.0, 5.0, 2.0, 2.0) == \
        pytest.approx(5.0)
    assert object_pad_blend_elevation(8.0, 5.0, 9.0, 2.0) == \
        pytest.approx(5.0)
    # A degenerate margin cannot mint a pad out of nothing.
    assert object_pad_blend_elevation(8.0, 5.0, 0.0, 0.0) == \
        pytest.approx(5.0)


# ══════════════════════════════════════════════════════════════════════
# EMISSION
# ══════════════════════════════════════════════════════════════════════

def test_the_gate_is_byte_inert_off(dem, monkeypatch):
    monkeypatch.setattr(apc, "DSF_OBJECT_OBJECT_PADS", False)
    layout = make_layout()
    before = len(layout.shapes)
    side = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)])
    assert emit(layout, dem, side) == 0
    assert len(layout.shapes) == before
    assert not layout.object_pad_records


def test_a_request_emits_a_core_at_target_and_a_blend_to_dem(gate_on, dem):
    """§5.1 clauses 1 + 4 end to end: terrain meets the building base
    exactly under the contact hull, and reaches raw DEM at the margin."""
    layout = make_layout()
    side = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)])
    assert emit(layout, dem, side) >= 2
    core = cores(layout)
    blend = blends(layout)
    assert len(core) == 1 and len(blend) == 1
    assert all(abs(a - 6.5) <= 0.01 for a in core[0].node_altitudes)
    assert all(abs(a - BASE_TERRAIN_M) <= 0.01
               for a in blend[0].node_altitudes)
    # The blend is an ANNULUS: the core is its hole, so the two shapes
    # share a chain instead of stacking (the hole's authority is the
    # shape standing in it — layout.to_osm).
    assert len(blend[0].polygon.interiors) == 1
    assert blend[0].polygon.intersection(core[0].polygon).area == \
        pytest.approx(0.0, abs=1e-6)
    # The core IS the contact hull: the recorded ring dilated by the
    # margin, eroded back.
    assert math.sqrt(core[0].polygon.area) == pytest.approx(
        2 * (10.0 - MARGIN_M), rel=0.02)


def test_an_over_cap_request_is_refused_and_emits_nothing(gate_on, dem):
    """§5.1 clause 1: a pad needing more relief than the cap is REFUSED —
    the cluster keeps its residual — and the refusal is a finding
    carrying the measured numbers (§5.5).  Never a truncated pad, which
    would promise a seat the terrain does not deliver."""
    layout = make_layout()
    side = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 12.0)])
    assert emit(layout, dem, side) == 0
    assert not pads(layout)
    assert not layout.object_pad_records
    over = [f for f in layout.object_pad_findings
            if f[0] == "pad_over_relief_cap"]
    assert len(over) == 1
    assert over[0][2] == pytest.approx(7.0)          # measured relief
    assert over[0][3] == pytest.approx(apc.DSF_OBJECT_PAD_MAX_RELIEF_M)


def test_the_producers_own_over_cap_flag_also_refuses(gate_on, dem):
    """The rebake measured the residual against the MESH; this build
    measures against the DEM.  Either measurement condemning the pad is
    enough — a pad the producer already called inadmissible is not
    resurrected by a friendlier raster."""
    layout = make_layout()
    side = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5,
                            over_cap=True)])
    assert emit(layout, dem, side) == 0
    assert "pad_over_relief_cap" in kinds(layout.object_pad_findings)


def test_pavement_wins_absolutely_the_pad_is_clipped(gate_on, dem):
    """§5.1 clause 2, owner ruling R2: a pad never contributes, moves or
    re-values a pavement vertex.  The overlapping half is DIFFERENCED
    away, and the pavement shape is byte-identical across the emitter."""
    apron = square_ring(0.0, 20.0, 20.0)             # covers y in [0, 40]
    layout = make_layout(apron_ring=apron)
    apron_shape = layout.shapes[0]
    before = (apron_shape.polygon.wkb, list(apron_shape.node_altitudes))
    side = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)])
    assert emit(layout, dem, side) >= 1
    assert (apron_shape.polygon.wkb,
            list(apron_shape.node_altitudes)) == before
    for s in pads(layout):
        assert s.polygon.intersection(apron_shape.polygon).area == \
            pytest.approx(0.0, abs=1e-6)
    assert "pad_deformed_pavement" not in kinds(layout.object_pad_findings)


def test_a_pad_wholly_inside_pavement_is_inadmissible(gate_on, dem):
    """§5.4: an inadmissible clip is REPORTED, never emitted as a
    shrunken stand-in.  (At HECA the Private Hall's north face is inside
    an apron polygon — a pad that ignored the apron would grade it.)"""
    layout = make_layout(apron_ring=square_ring(0.0, 0.0, 60.0))
    side = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)])
    assert emit(layout, dem, side) == 0
    assert "pad_wholly_inside_pavement" in kinds(layout.object_pad_findings)


def test_a_welded_boundary_carries_the_pavements_own_value(gate_on, dem):
    """§5.1 clause 3 + ruling R4: where the pad boundary runs along a
    pavement edge it lies ON the pavement ring and ADOPTS its solved
    value — a weld, no cliff, no standoff groove — and the short run
    pulls the pad target toward the pavement with the shortfall
    reported."""
    # Apron edge at y = 10, the pad's outer ring touching it exactly.
    layout = make_layout(apron_ring=[(-20.0, 10.0), (20.0, 10.0),
                                     (20.0, 50.0), (-20.0, 50.0)])
    side = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)])
    assert emit(layout, dem, side) >= 2
    welded = [(x, y, a)
              for s in blends(layout)
              for (x, y), a in zip(list(s.polygon.exterior.coords)[:-1],
                                   s.node_altitudes)
              if abs(y - 10.0) <= 0.02]
    assert welded, "the pad's boundary row on the apron edge is missing"
    assert all(abs(a - APRON_ALT_M) <= 0.01 for _x, _y, a in welded), \
        "a welded vertex must carry the PAVEMENT value, not the pad's"
    # run = margin (2 m) at the 5 % groundside cap ⇒ 0.1 m of authority.
    core = cores(layout)[0]
    assert all(abs(a - (APRON_ALT_M + 0.1)) <= 0.01
               for a in core.node_altitudes)
    shortfall = [f for f in layout.object_pad_findings
                 if f[0] == "pad_pull_shortfall"]
    assert len(shortfall) == 1
    assert shortfall[0][2] == pytest.approx(0.4, abs=0.02)


def test_a_tight_ring_still_holds_the_base_on_a_shorter_ramp(gate_on, dem):
    """The OTHH corpus class: a request whose contact hull is about a
    metre across.  Eroding by the full 2 m margin would leave NO interior
    and the building base would be held nowhere — so the ramp shortens
    and a real core survives, still meeting raw DEM at the rim."""
    layout = make_layout()
    side = sidecar([request(layout, square_ring(0.0, 0.0, 2.5), 6.5)])
    assert emit(layout, dem, side) >= 2
    core = cores(layout)[0]
    assert all(abs(a - 6.5) <= 0.01 for a in core.node_altitudes)
    assert core.polygon.area == pytest.approx(6.25, rel=0.05)
    blend = blends(layout)[0]
    assert all(abs(a - BASE_TERRAIN_M) <= 0.01
               for a in blend.node_altitudes), \
        "the rim must still land on raw DEM — a shorter ramp, not a cliff"
    assert layout.object_pad_records[0]["blend_width_m"] == \
        pytest.approx(1.25)


def test_a_ring_with_no_usable_interior_is_refused_with_its_area(gate_on,
                                                                dem):
    """§5.4/§5.5: an inadmissible pad is REPORTED with its measured
    numbers, never emitted as a stand-in.  A sub-metre ring has nowhere
    to hold the base and would be a bare step onto raw DEM."""
    layout = make_layout()
    side = sidecar([request(layout, square_ring(0.0, 0.0, 0.4), 6.5)])
    assert emit(layout, dem, side) == 0
    refused = [f for f in layout.object_pad_findings
               if f[0] == "pad_no_contact_hull"]
    assert len(refused) == 1
    assert refused[0][2] == pytest.approx(0.64, rel=0.05)   # ring area


def test_a_pad_is_claimed_by_the_airport_whose_ground_it_stands_on(gate_on,
                                                                   dem):
    """The tile sidecar's per-airport blocks are keyed by DSF
    ATTRIBUTION, not by whose ground the pad is on: measured on +25+051,
    all 823 OTHH terminal requests are recorded under OTBD because one
    Global Airports DSF cell carries both.  A patch is per airport, so
    GEOMETRY has to claim — otherwise the airport that needs the pads
    emits none and the one that does not emits them 5 km from its own
    ground."""
    layout = make_layout()
    mine = request(layout, square_ring(0.0, 0.0, 10.0), 6.5, cluster_id=1)
    # 5 km east — inside the tile, outside this airport entirely.
    far_ring = [(x + 5000.0, y) for x, y in square_ring(0.0, 0.0, 10.0)]
    theirs = request(layout, far_ring, 6.5, cluster_id=2)
    side = sidecar([mine, theirs], icao="OTHER")
    assert emit(layout, dem, side) >= 2
    assert len(layout.object_pad_records) == 1, \
        "exactly the pad standing on this airport's ground"
    assert layout.object_pad_records[0]["cluster_id"] == 1
    assert layout.object_pad_records[0]["icao"] == "TEST", \
        "the record is owned by the EMITTING airport, not the block's"


def test_a_pad_is_clipped_by_earlier_terrain_features(gate_on, dem):
    """§5.4 precedence: pavement > existing terrain features > pads > raw
    DEM.  A band/skirt/OLS shape already in the layout takes the ground
    it covers; the pad keeps only the remainder."""
    from auto_patch.layout import ROLE_GRADED_STRIP

    layout = make_layout()
    strip = square_ring(0.0, 20.0, 20.0)
    layout.shapes.append(BuiltShape(
        polygon=Polygon(strip + [strip[0]]), role=ROLE_GRADED_STRIP,
        ref="band", node_altitudes=[5.2] * 5))
    side = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)])
    assert emit(layout, dem, side) >= 1
    band = layout.shapes[1].polygon
    for s in pads(layout):
        assert s.polygon.intersection(band).area == pytest.approx(
            0.0, abs=1e-6)


def test_a_pad_touching_pavement_at_points_only_does_not_abort(gate_on,
                                                               dem):
    """REGRESSION (OTHH, 2026-08-09): a pad piece can touch a pavement
    ring at ISOLATED POINTS — the mouth of a notched apron is the type
    case — and ``part.intersection(ring)`` then returns a MultiPoint,
    which ``interpolate`` rejects with a TypeError.  That is not a
    shapely-domain error, so it escaped the emitter's guard and took the
    whole OTHH build down with a traceback.

    Two things are pinned: the contact point is resolved by
    ``nearest_points`` (total over every geometry type), and the run is
    measured core-to-pavement rather than from whatever point the
    intersection happened to yield."""
    # The notched apron and the block filling its mouth: touching at
    # exactly the two notch corners and nowhere else.
    notch = [(-30.0, -30.0), (30.0, -30.0), (30.0, 10.0), (6.0, 10.0),
             (6.0, -4.0), (-6.0, -4.0), (-6.0, 10.0), (-30.0, 10.0)]
    layout = make_layout(apron_ring=notch)
    apron = layout.shapes[0].polygon
    part = Polygon([(-6.0, 10.0), (6.0, 10.0), (6.0, 24.0), (-6.0, 24.0)])
    assert part.distance(apron) == pytest.approx(0.0)
    assert part.intersection(apron.exterior).geom_type == "MultiPoint", \
        "the fixture no longer reproduces the point-only contact"

    run, value = object_pads._pavement_run(
        part, part.buffer(-2.0), [apron], object_pads._WeldIndex(layout))
    assert value == pytest.approx(APRON_ALT_M)
    assert math.isfinite(run)

    # …and the whole emitter stays total over the same geometry.
    side = sidecar([request(layout, square_ring(0.0, 17.0, 10.0), 6.5)])
    emit(layout, dem, side)                        # must not raise
    assert "pad_deformed_pavement" not in kinds(layout.object_pad_findings)


def test_two_pads_never_overlap_each_other(gate_on, dem):
    """Pad↔pad exclusivity: the second pad is clipped against the first,
    so no ground is claimed twice (the ``ols`` emitted-pieces rule)."""
    layout = make_layout()
    side = sidecar([
        request(layout, square_ring(0.0, 0.0, 10.0), 6.5, cluster_id=1),
        request(layout, square_ring(8.0, 0.0, 10.0), 6.2, cluster_id=2),
    ])
    assert emit(layout, dem, side) >= 2
    shapes = [s.polygon for s in pads(layout)]
    for i, a in enumerate(shapes):
        for b in shapes[i + 1:]:
            assert a.intersection(b).area == pytest.approx(0.0, abs=1e-6)


def test_emission_is_deterministic(gate_on, dem):
    """Same inputs, same pads — the requests are emitted in a stable seat
    order, never in dict/hash order."""
    side = sidecar([
        request(make_layout(), square_ring(40.0, 0.0, 10.0), 6.4,
                cluster_id=7),
        request(make_layout(), square_ring(0.0, 0.0, 10.0), 6.5,
                cluster_id=3),
    ])
    runs = []
    for _ in range(2):
        layout = make_layout()
        emit(layout, dem, copy.deepcopy(side))
        runs.append([(s.ref, s.polygon.wkb, tuple(s.node_altitudes))
                     for s in pads(layout)])
    assert runs[0] == runs[1]


# ══════════════════════════════════════════════════════════════════════
# CONVERGENCE (§5.2) — the ``emitted`` records
# ══════════════════════════════════════════════════════════════════════

def test_a_record_is_written_for_every_emitted_pad(gate_on, dem):
    layout = make_layout()
    side = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)])
    emit(layout, dem, side)
    assert len(layout.object_pad_records) == 1
    record = layout.object_pad_records[0]
    assert record["icao"] == "TEST"
    assert record["target_ground_metres"] == pytest.approx(6.5)
    assert record["emitted_target_metres"] == pytest.approx(6.5)
    assert record["law_digest"] == object_pads.law_digest()
    assert record["ring_lonlat"]


def test_the_pad_survives_its_request_converging_away(gate_on, dem):
    """§5.2, the whole point of the loop: build N emits pads, build N's
    rebake re-measures against terrain that now meets the feet, the
    residuals fall under the tolerance and the REQUESTS VANISH.  The pads
    must not vanish with them, or the next rebake re-raises the same
    requests forever."""
    first = make_layout()
    side1 = sidecar([request(first, square_ring(0.0, 0.0, 10.0), 6.5)])
    emit(first, dem, side1)
    records = first.object_pad_records
    assert records

    # What post_mesh now writes at the fixed point: requests emptied,
    # the consumer's section carried across.
    side2 = sidecar([], emitted=records)
    second = make_layout()
    assert emit(second, dem, side2) == len(pads(first))
    assert [(s.ref, s.polygon.wkb, tuple(s.node_altitudes))
            for s in pads(second)] == \
        [(s.ref, s.polygon.wkb, tuple(s.node_altitudes)) for s in pads(first)]
    assert "pad_record_expired" not in kinds(second.object_pad_findings)

    # ...and build N+2 is a FIXED POINT: re-emitting from the records the
    # re-emission wrote changes nothing at all.
    third = make_layout()
    emit(third, dem, sidecar([], emitted=second.object_pad_records))
    assert [(s.ref, s.polygon.wkb, tuple(s.node_altitudes))
            for s in pads(third)] == \
        [(s.ref, s.polygon.wkb, tuple(s.node_altitudes)) for s in pads(first)]


def test_a_live_request_supersedes_its_own_stored_record(gate_on, dem):
    """§5.2 staleness cause 2: the rebake just measured this seat, so the
    fresh request wins over the record — the pad re-emits at the NEW
    target instead of standing at a stale height."""
    layout = make_layout()
    ring = square_ring(0.0, 0.0, 10.0)
    emit(layout, dem, sidecar([request(layout, ring, 6.5)]))
    stale = layout.object_pad_records
    moved = make_layout()
    emit(moved, dem, sidecar([request(moved, ring, 7.25)], emitted=stale))
    assert len(cores(moved)) == 1, "the seat must emit once, not twice"
    assert all(abs(a - 7.25) <= 0.01
               for a in cores(moved)[0].node_altitudes)


def test_a_law_change_expires_the_record_with_a_reason(gate_on, dem,
                                                       monkeypatch):
    """§5.2 staleness cause 1 + §5.5 ("no silent pad loss"): when the law
    moves, a stored record is DROPPED and the drop is reported."""
    layout = make_layout()
    emit(layout, dem, sidecar([request(layout, square_ring(0.0, 0.0, 10.0),
                                       6.5)]))
    records = layout.object_pad_records
    monkeypatch.setattr(apc, "DSF_OBJECT_PAD_MAX_RELIEF_M", 2.5)
    after = make_layout()
    assert emit(after, dem, sidecar([], emitted=records)) == 0
    expired = [f for f in after.object_pad_findings
               if f[0] == "pad_record_expired"]
    assert len(expired) == 1 and expired[0][4] == "law_digest_changed"


def test_the_pure_resolver_falls_back_to_the_recorded_icao():
    """``pads_for_airport`` without a geometric claim is the PURE form:
    it resolves by the sidecar's own ICAO blocks, so the convergence law
    (request wins over record; a stale law digest expires a record) can be
    read and tested without a layout in the room."""
    layout = make_layout()
    live = request(layout, square_ring(0.0, 0.0, 10.0), 6.5, cluster_id=1)
    side = sidecar([live], emitted=[
        {"icao": "TEST", "seat_key": object_pads.seat_key(live),
         "law_digest": object_pads.law_digest(), "index": 0,
         "ring_lonlat": live["rings_lonlat"][0]},
        {"icao": "TEST", "seat_key": "gone", "law_digest": "stale",
         "index": 1, "ring_lonlat": live["rings_lonlat"][0]},
        {"icao": "OTHER", "seat_key": "elsewhere",
         "law_digest": object_pads.law_digest(), "index": 2,
         "ring_lonlat": live["rings_lonlat"][0]},
    ])
    specs, expired = object_pads.pads_for_airport(side, "TEST")
    assert [s["source"] for s in specs] == ["request"], \
        "the live request supersedes its own record; the other airport's " \
        "record is not ours"
    assert expired == [("gone", "law_digest_changed")]


def test_records_merge_into_the_sidecar_per_airport(tmp_path):
    """The tile sidecar is shared by every airport in the tile and
    airports build in a ProcessPool, so the merge must REPLACE one
    airport's records and leave the others alone."""
    path = tmp_path / "o4_object_foot_pads.json"
    path.write_text(json.dumps(sidecar([], emitted=[
        {"icao": "AAAA", "seat_key": "a", "index": 0},
        {"icao": "TEST", "seat_key": "old", "index": 0},
    ])))
    assert object_pads.merge_emitted_records(
        str(path), "TEST", [{"icao": "TEST", "seat_key": "new", "index": 0}])
    payload = json.loads(path.read_text())
    keys = {(r["icao"], r["seat_key"]) for r in payload["emitted"]}
    assert keys == {("AAAA", "a"), ("TEST", "new")}
    # An airport that emitted nothing FORGETS its records rather than
    # re-emitting them forever.
    assert object_pads.merge_emitted_records(str(path), "TEST", [])
    payload = json.loads(path.read_text())
    assert {(r["icao"], r["seat_key"]) for r in payload["emitted"]} == \
        {("AAAA", "a")}


def test_the_sidecar_version_carries_the_emitted_section():
    """§5.2: the ``emitted`` section is a sidecar version bump, and
    ``post_mesh`` — which refreshes the REQUESTS every rebake — is the
    module that must carry it across.  Version 4 was the
    footprint-hugging ring law (object-reseat-threshold-spec §2.5);
    version 5 retires the plan-box fallback (round-4 spec R1), which is
    a GEOMETRY change and therefore a bump."""
    from auto_patch import post_mesh

    assert post_mesh.OBJECT_FOOT_PAD_SIDECAR_VERSION == 5


def test_the_consumer_reads_the_sidecar_from_the_patch_dir(gate_on, dem,
                                                           tmp_path):
    """Production path: no ``sidecar=`` argument, just the tile's patch
    directory — which is where post_mesh writes it and where auto-patch
    features already load from."""
    layout = make_layout()
    payload = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)])
    (tmp_path / "o4_object_foot_pads.json").write_text(json.dumps(payload))
    n = object_pads.emit_object_pads(
        layout, dem, TILE_LAT, TILE_LON, icao="TEST",
        patch_dir=str(tmp_path))
    assert n >= 2 and cores(layout)
    # A tile with no sidecar is simply a tile with no pads.
    bare = make_layout()
    assert object_pads.emit_object_pads(
        bare, dem, TILE_LAT, TILE_LON, icao="TEST",
        patch_dir=str(tmp_path / "empty")) == 0


# ══════════════════════════════════════════════════════════════════════
# THE VALIDATOR (§5.5) — lockstep with the emitter
# ══════════════════════════════════════════════════════════════════════

def test_a_lawful_emission_is_finding_clean(gate_on, dem):
    layout = make_layout()
    emit(layout, dem, sidecar([request(layout, square_ring(0.0, 0.0, 10.0),
                                       6.5)]))
    findings = verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON)
    assert findings == [], findings


def test_the_validator_catches_a_core_off_its_law_target(gate_on, dem):
    """Lockstep (R5): the reader recomputes the target from the SAME law
    the emitter used, so a surface that drifts from it is visible."""
    layout = make_layout()
    emit(layout, dem, sidecar([request(layout, square_ring(0.0, 0.0, 10.0),
                                       6.5)]))
    core = cores(layout)[0]
    core.node_altitudes = [a + 0.5 for a in core.node_altitudes]
    findings = verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON)
    assert "pad_core_off_target" in kinds(findings)


def test_the_validator_catches_a_broken_weld(gate_on, dem):
    """§5.5: "every pad↔pavement shared-boundary vertex carries the
    pavement's value exactly (weld; a mismatch is a groove/cliff
    finding)"."""
    layout = make_layout(apron_ring=[(-20.0, 10.0), (20.0, 10.0),
                                     (20.0, 50.0), (-20.0, 50.0)])
    emit(layout, dem, sidecar([request(layout, square_ring(0.0, 0.0, 10.0),
                                       6.5)]))
    blend = blends(layout)[0]
    blend.node_altitudes = [a - 0.9 for a in blend.node_altitudes]
    findings = verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON)
    assert "pad_weld_mismatch" in kinds(findings)


def test_the_validator_surfaces_refusals_and_expiries(gate_on, dem):
    """§5.5: "every refused pad (over-cap relief, inadmissible clip)
    surfaced as a finding carrying the measured numbers" and "every
    ``emitted`` sidecar record either re-emitted or expired-with-reason
    (no silent pad loss)"."""
    layout = make_layout()
    emit(layout, dem, sidecar([request(layout, square_ring(0.0, 0.0, 10.0),
                                       12.0)]))
    findings = verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON)
    assert "pad_over_relief_cap" in kinds(findings)
    assert findings[0][2] == pytest.approx(7.0)      # worst-first


def test_the_validator_is_silent_without_pads(dem):
    layout = make_layout()
    assert verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON) == []


# ══════════════════════════════════════════════════════════════════════
# FOOTPRINT-HUGGING RINGS (object-reseat-threshold-spec §2.5)
#
# The consumer's geometry is UNCHANGED by that amendment — it consumes
# rings verbatim — so what is pinned here is that it consumes the
# SMALLER rings correctly: one pad per ring, blend width and refusal
# accounting per ring, and every emitted polygon inside the contact
# hulls its request was built from.
# ══════════════════════════════════════════════════════════════════════

def contact_parts(layout, boxes_m):
    """Hand-built contact parts in the sidecar's ``(lon, lat)``
    convention — ``boxes_m`` are ``(cx, cy, half)`` in local metres."""
    parts = []
    for cx, cy, half in boxes_m:
        part = []
        for x, y in square_ring(cx, cy, half):
            lat, lon = layout.m_to_ll(x, y)
            part.append((lon, lat))
        parts.append(part)
    return parts


def request_from_parts(layout, parts, target_m: float, *,
                       cluster_id: int = 1) -> dict:
    """The producer's own path, in miniature: parts → rings (the §2.5
    union law) → one request record carrying them all."""
    from auto_patch.object_footprints import foot_pad_rings

    rings = foot_pad_rings([list(part) for part in parts], MARGIN_M)
    points = [point for part in parts for point in part]
    lat = sum(p[1] for p in points) / len(points)
    lon = sum(p[0] for p in points) / len(points)
    return {
        "kind": "cluster",
        "cluster_id": cluster_id,
        "structure_index": 0,
        "resource_path": "Buildings/spread.obj",
        "latitude": lat,
        "longitude": lon,
        "base_y": 0.0,
        "residual_metres": target_m - BASE_TERRAIN_M,
        "target_ground_metres": target_m,
        "part_count": len(parts),
        "over_relief_cap": False,
        "pavement_clipped": False,
        "rings_lonlat": [[list(point) for point in ring] for ring in rings],
    }


def test_each_ring_of_a_request_becomes_its_own_pad(gate_on, dem):
    """§2.5: "each connected component of that union raised as its OWN
    request ring".  Three parts strung 40 m apart are three pads, each
    hugging its own object — not one rectangle over the ground between
    them."""
    layout = make_layout()
    parts = contact_parts(layout, [(-40.0, -40.0, 5.0), (0.0, -40.0, 5.0),
                                   (40.0, -40.0, 5.0)])
    spec = request_from_parts(layout, parts, 6.5)
    assert len(spec["rings_lonlat"]) == 3

    assert emit(layout, dem, sidecar([spec])) >= 6
    assert len(cores(layout)) == 3
    # One record per RING, each with its own seat key and ring index.
    records = layout.object_pad_records
    assert len(records) == 3
    assert sorted(r["ring_index"] for r in records) == [0, 1, 2]
    assert len({r["seat_key"] for r in records}) == 3
    assert len({r["fingerprint"] for r in records}) == 3
    # The retired law would have graded the 90 m strip between them.
    assert sum(r["area_m2"] for r in records) < 1200.0


def test_every_emitted_pad_lies_inside_its_contact_hulls(gate_on, dem):
    """THE STRUCTURAL ASSERTION (§2.5), consumer side: every emitted pad
    polygon is covered by (its request's contact-hull union ⊕ margin),
    so no pad vertex is further than the margin from a real contact."""
    from shapely.geometry import MultiPoint
    from shapely.ops import unary_union

    layout = make_layout()
    parts = contact_parts(layout, [(-30.0, -30.0, 6.0), (0.0, -45.0, 3.0),
                                   (25.0, -25.0, 8.0), (-5.0, -20.0, 4.0)])
    spec = request_from_parts(layout, parts, 6.5)
    assert emit(layout, dem, sidecar([spec])) > 0

    hulls_m = unary_union([
        MultiPoint([layout.ll_to_m(lat, lon) for lon, lat in part]).convex_hull
        for part in parts])
    allowed = hulls_m.buffer(MARGIN_M + 0.05)      # + the round-trip eps
    for shape in pads(layout):
        assert shape.polygon.within(allowed), shape.ref


def test_a_ring_lost_to_pavement_does_not_condemn_its_siblings(gate_on, dem):
    """The refusal accounting still PARTITIONS: one component wholly
    inside the apron is refused with its own key while the other emits."""
    layout = make_layout(apron_ring=[(20.0, 20.0), (100.0, 20.0),
                                     (100.0, 100.0), (20.0, 100.0)])
    parts = contact_parts(layout, [(-40.0, -40.0, 5.0), (60.0, 60.0, 5.0)])
    spec = request_from_parts(layout, parts, 6.5)
    assert len(spec["rings_lonlat"]) == 2

    assert emit(layout, dem, spec_sidecar := sidecar([spec])) > 0
    assert spec_sidecar["version"] == post_mesh.OBJECT_FOOT_PAD_SIDECAR_VERSION
    assert len(cores(layout)) == 1
    refused = [f for f in layout.object_pad_findings
               if f[0] == "pad_wholly_inside_pavement"]
    assert len(refused) == 1
    assert refused[0][1] != layout.object_pad_records[0]["seat_key"]


# ── the version-4 gate ────────────────────────────────────────────────

def test_a_version_3_sidecar_is_refused_not_consumed(gate_on, dem):
    """§2.5: "Sidecar version bumps (3 → 4) so hull-ring request corpora
    are discarded".  A v3 file's rings are the retired law's geometry —
    the consumer emits NOTHING from it and says why."""
    layout = make_layout()
    stale = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)],
                    version=3)
    # The retired shape, verbatim: v3 carried one "ring_lonlat" per
    # request.  Even carrying BOTH keys it must not be consumed.
    stale["airports"][0]["requests"][0]["ring_lonlat"] = \
        stale["airports"][0]["requests"][0]["rings_lonlat"][0]

    assert emit(layout, dem, stale) == 0
    assert pads(layout) == []
    expired = [f for f in layout.object_pad_findings
               if f[0] == "pad_record_expired"]
    assert expired and all(f[4] == "sidecar_version_stale" for f in expired)


def test_version_3_emitted_records_drop_rather_than_re_emit(gate_on, dem):
    """"``emitted`` records with stale-version fingerprints drop and the
    §5.2 convergence loop re-derives" — the record is reported expired,
    by key, so the loss is measured."""
    layout = make_layout()
    live = sidecar([request(layout, square_ring(0.0, 0.0, 10.0), 6.5)])
    emit(layout, dem, live)
    records = layout.object_pad_records
    assert records

    after = make_layout()
    stale = sidecar([], emitted=records, version=3)
    assert emit(after, dem, stale) == 0
    expired = dict((f[1], f[4]) for f in after.object_pad_findings
                   if f[0] == "pad_record_expired")
    assert expired == {r["seat_key"]: "sidecar_version_stale"
                       for r in records}


def test_a_stale_sidecar_is_never_relabelled_current(tmp_path):
    """The merge must not LAUNDER a hull-law corpus by stamping the new
    version on it: with nothing to add it leaves the file alone."""
    path = tmp_path / "o4_object_foot_pads.json"
    payload = sidecar([], emitted=[{"icao": "TEST", "seat_key": "old"}],
                      version=3)
    path.write_text(json.dumps(payload))
    assert object_pads.merge_emitted_records(str(path), "TEST", []) is False
    assert json.loads(path.read_text()) == payload


def test_the_law_digest_moves_with_the_sidecar_version(monkeypatch):
    """The version is part of the pad law's fingerprint, so a record
    written under the hull law can never match this build's digest."""
    before = object_pads.law_digest()
    monkeypatch.setattr(post_mesh, "OBJECT_FOOT_PAD_SIDECAR_VERSION", 3)
    assert object_pads.law_digest() != before
