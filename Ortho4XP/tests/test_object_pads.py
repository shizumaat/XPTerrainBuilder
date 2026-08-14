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
import math
import pathlib

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


def pad_frame(layout, hulls_m, *, target_m=None, base_y=None, agl=0.0,
              key: int = 1, structure_index: int = 0, resource=None,
              anchor_m=None):
    """One ``object_frame.ObjectPadFrame`` — the emitter's real input.

    ``hulls_m`` are CONTACT HULLS in local metres (one per ground part);
    the ring law dilates each by ``DSF_OBJECT_FOOT_PAD_MARGIN_M`` and
    unions them, so a hull of half-size H yields a ring of half-size
    H + 2 m and, after the erosion, a core back at H.

    THE RENDER DATUM defaults to a point inside the layout's first shape
    — the apron — because the ruling's coupling reads the PATCH there and
    an unhosted datum is by design not padable (its own twin below).  Its
    ground is therefore the apron's own solved value, and ``base_y`` is
    derived from ``target_m`` against it: ``target = apron + AGL +
    base_y`` is the whole arithmetic, spelled here so a test can state
    either end of it.
    """
    from auto_patch.object_frame import ObjectPadFrame, PadAnchor, PadPart

    resource = resource or f"Buildings/pad{key}.obj"
    if anchor_m is None:
        point = layout.shapes[0].polygon.representative_point()
        anchor_m = (point.x, point.y)
    anchor_latitude, anchor_longitude = layout.m_to_ll(*anchor_m)
    host_alt = float(layout.shapes[0].node_altitudes[0])
    if base_y is None:
        base_y = float(target_m) - host_alt - float(agl)

    parts = []
    for ordinal, hull in enumerate(hulls_m):
        hull_ll = tuple(
            (lon, lat) for lat, lon in
            (layout.m_to_ll(x, y) for x, y in hull))
        cx = sum(x for x, _y in hull) / len(hull)
        cy = sum(y for _x, y in hull) / len(hull)
        latitude, longitude = layout.m_to_ll(cx, cy)
        parts.append(PadPart(
            structure_index=structure_index,
            part_key=key * 100 + ordinal,
            base_resource=resource,
            base_y=float(base_y),
            latitude=latitude,
            longitude=longitude,
            contact_parts_lonlat=(hull_ll,)))
    return ObjectPadFrame(
        parts=tuple(parts),
        anchor_by_resource={resource: PadAnchor(
            latitude=anchor_latitude,
            longitude=anchor_longitude,
            above_ground_level_metres=float(agl))})


def pads(layout):
    return [s for s in layout.shapes if s.role == ROLE_OBJECT_PAD]


def cores(layout):
    return [s for s in pads(layout)
            if (s.ref or "").startswith(object_pads.REF_PAD_CORE + ":")]


def blends(layout):
    """The RETIRED shape family (weld or gap, owner 2026-08-13).  Kept as
    an assertion surface: every test that used to expect a blend now
    asserts there is none."""
    return [s for s in pads(layout)
            if (s.ref or "").startswith(object_pads.REF_PAD_BLEND + ":")]


def emit(layout, dem, frames):
    return object_pads.emit_object_pads(
        layout, dem, TILE_LAT, TILE_LON, icao="TEST",
        pad_frames=list(frames))


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
# EMISSION FROM THE FRAME (RULINGS "OBJECT PADS: EMISSION-TIME RELATIVE")
# ══════════════════════════════════════════════════════════════════════

def test_the_gate_is_byte_inert_off(dem, monkeypatch):
    monkeypatch.setattr(apc, "DSF_OBJECT_OBJECT_PADS", False)
    layout = make_layout()
    before = len(layout.shapes)
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)]
    assert emit(layout, dem, frames) == 0
    assert len(layout.shapes) == before
    assert not layout.object_pad_records


def test_the_target_is_the_patch_at_the_datum_plus_base_y(gate_on, dem):
    """THE RULING'S OWN CLAUSE, end to end: the pad's core holds
    ``patch(render datum) + AGL + base_y`` — nothing here consults a
    previous build, a sidecar or a mesh.  Moving the HOST's solved value
    moves the pad by exactly the same amount, which is what "relative"
    means."""
    for host_alt in (6.0, 7.0):
        layout = make_layout(apron_alt=host_alt)
        frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)],
                            base_y=0.5, agl=0.25)]
        assert emit(layout, dem, frames) >= 1
        core = cores(layout)[0]
        assert all(abs(a - (host_alt + 0.25 + 0.5)) <= 0.01
                   for a in core.node_altitudes)
        assert layout.object_pad_records[0]["target_ground_metres"] == \
            pytest.approx(host_alt + 0.75)


def test_a_request_emits_a_core_and_no_blend(gate_on, dem):
    """§5.1 clause 1 under WELD OR GAP: terrain meets the building base
    exactly under the contact hull, and the margin annulus is now a GAP
    the mesh drapes — the blend emitter is retired, so exactly one shape
    comes out of one ring."""
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)]
    assert emit(layout, dem, frames) == 1
    core = cores(layout)
    assert len(core) == 1
    assert blends(layout) == []
    assert all(abs(a - 6.5) <= 0.01 for a in core[0].node_altitudes)
    # The core IS the contact hull: the derived ring is that hull dilated
    # by the margin, and the core is it eroded back.
    assert math.sqrt(core[0].polygon.area) == pytest.approx(16.0, rel=0.05)


def test_an_over_cap_request_is_refused_and_emits_nothing(gate_on, dem):
    """§5.1 clause 1: a pad needing more relief than the cap is REFUSED —
    the cluster keeps its residual — and the refusal is a finding
    carrying the measured numbers (§5.5).  Never a truncated pad, which
    would promise a seat the terrain does not deliver."""
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=12.0)]
    assert emit(layout, dem, frames) == 0
    assert not pads(layout)
    assert not layout.object_pad_records
    over = [f for f in layout.object_pad_findings
            if f[0] == "pad_over_relief_cap"]
    assert len(over) == 1
    assert over[0][2] == pytest.approx(7.0)          # measured relief
    assert over[0][3] == pytest.approx(apc.DSF_OBJECT_PAD_MAX_RELIEF_M)


def test_the_frames_own_over_cap_flag_also_refuses(gate_on, dem):
    """ONE measurement condemns this pad, and it is the pad's OWN GROUND
    (RULINGS, Fable 2026-08-14): the part stands on a low graded shape at
    2.0 m and asks for 6.5 m, so it would stand 4.5 m over the ground it
    adjoins — refused, even though raw DEM (5.0 m) is only 1.5 m away.
    The frame's ``over_relief_cap`` flag and the emitter's admissibility
    test are the same comparison over the same pair, so they cannot
    disagree."""
    from auto_patch.layout import ROLE_GRADED_STRIP

    layout = make_layout()
    low = square_ring(0.0, 0.0, 30.0)
    layout.shapes.append(BuiltShape(
        polygon=Polygon(low + [low[0]]), role=ROLE_GRADED_STRIP,
        ref="low", node_altitudes=[2.0] * 5))
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)]
    assert emit(layout, dem, frames) == 0
    assert "pad_over_relief_cap" in kinds(layout.object_pad_findings)


# ══════════════════════════════════════════════════════════════════════
# THE CAP'S REFERENCE FRAME (RULINGS "PAD RELIEF CAP MEASURES AGAINST THE
# PAD'S OWN GROUND, NEVER RAW DEM", Fable 2026-08-14)
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def patch_authors_everything(monkeypatch):
    """The PATCH is the ground authority everywhere, at 40 m — the HECA
    class in miniature: an object standing correctly on a solved surface
    that sits tens of metres off raw DEM (5 m here), and whose PLATE lands
    on that same solved surface.

    One production seam is stubbed, ``patch_ground.field_from_layout``,
    so the emitter's own two-authority closure is the thing under test."""
    from auto_patch import patch_ground

    class _Field:
        def value_at(self, x, y):
            return 40.0, "apron"

    monkeypatch.setattr(patch_ground, "field_from_layout",
                        lambda layout: _Field())
    return 40.0


def test_the_relief_cap_measures_the_pads_own_ground_not_raw_dem(
        gate_on, dem, patch_authors_everything):
    """THE RULING.  The pad's own ground is 40 m (the patch's own solved
    value); the object renders 1 m above it, which is inside the 3 m cap,
    so the pad is SERVED — and the record carries the reference the cap
    used.  Against raw DEM the same pad reads 36 m of relief and was
    refused, which is what condemned 3,855 of ~3,910 HECA requests for
    standing exactly where their objects correctly stand."""
    ground = patch_authors_everything
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)],
                        base_y=1.0, agl=0.0)]
    assert emit(layout, dem, frames) == 1
    record = layout.object_pad_records[0]
    assert record["ground_reference_metres"] == pytest.approx(ground)
    assert record["relief_metres"] == pytest.approx(1.0)
    assert record["emitted_target_metres"] == pytest.approx(ground + 1.0)
    assert all(abs(a - (ground + 1.0)) <= 0.01
               for a in cores(layout)[0].node_altitudes)
    # The retired reference, stated so the flip is on the record.
    assert not object_pad_admissible(ground + 1.0, BASE_TERRAIN_M,
                                     apc.DSF_OBJECT_PAD_MAX_RELIEF_M)


def test_the_cap_boundary_stands_at_the_cap_value_on_that_same_ground(
        gate_on, dem, patch_authors_everything):
    """The cap VALUE is unchanged, only what it is measured against: a
    pad exactly at the cap over its own ground is admissible, and one a
    centimetre beyond is refused with its measured numbers."""
    assert patch_authors_everything == 40.0
    cap = float(apc.DSF_OBJECT_PAD_MAX_RELIEF_M)

    layout = make_layout()
    assert emit(layout, dem, [pad_frame(
        layout, [square_ring(0.0, 0.0, 8.0)], base_y=cap, agl=0.0)]) == 1
    assert layout.object_pad_records[0]["relief_metres"] == \
        pytest.approx(cap)

    layout = make_layout()
    assert emit(layout, dem, [pad_frame(
        layout, [square_ring(0.0, 0.0, 8.0)], base_y=cap + 0.01,
        agl=0.0)]) == 0
    over = [f for f in layout.object_pad_findings
            if f[0] == "pad_over_relief_cap"]
    assert len(over) == 1
    assert over[0][2] == pytest.approx(cap + 0.01)
    assert over[0][3] == pytest.approx(cap)
    assert not layout.object_pad_records


def test_a_plate_landing_off_its_objects_pavement_is_refused(gate_on, dem):
    """THE PEDESTAL, refused by construction (RULINGS "PAD CAP REFERENCE
    IS THE PLATE'S LANDING GROUND", owner 2026-08-14).

    HECA's western apron in miniature, with the real geometry and no stub:
    the object's parts stand on a SOLVED apron at 40 m, so the request's
    target is 41 m — but the pad ring is clipped OUT of that apron
    (pavement wins absolutely) and what survives lands on ambient DEM at
    5 m.  Measured against the parts' host the pad reads 1 m and was
    served: eight such plates, 5.6-8.0 m proud, are what stopped the
    first re-frame.  Measured where the plate LANDS it reads 36 m and is
    refused, and the cluster keeps the y-bake."""
    layout = make_layout(apron_ring=[(-10.0, -10.0), (200.0, -10.0),
                                     (200.0, 10.0), (-10.0, 10.0)],
                         apron_alt=40.0)
    # Parts on the apron, ring straddling its edge; datum far along the
    # same apron so it is hosted and outside the pad's own ring.
    frames = [pad_frame(layout, [square_ring(0.0, 6.0, 8.0)],
                        base_y=1.0, agl=0.0, anchor_m=(150.0, 0.0))]
    assert emit(layout, dem, frames) == 0
    assert not pads(layout)
    over = [f for f in layout.object_pad_findings
            if f[0] == "pad_over_relief_cap"]
    assert len(over) == 1
    assert over[0][2] > 30.0                       # plate vs its landing
    assert over[0][3] == pytest.approx(apc.DSF_OBJECT_PAD_MAX_RELIEF_M)


def test_the_two_authorities_split_patch_where_authored_ambient_beyond(
        gate_on, dem):
    """THE SAME two-authority rule the emission path uses (patch where the
    patch authors, ambient DEM where it does not) — measured on the other
    side of the split: this pad's parts stand off every emitted shape, so
    the reference IS the ambient DEM under them, and nothing about the
    re-frame moved a pad that was already sitting on raw terrain."""
    layout = make_layout()
    emit(layout, dem,
         [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)])
    record = layout.object_pad_records[0]
    assert record["ground_reference_metres"] == \
        pytest.approx(BASE_TERRAIN_M)
    assert record["relief_metres"] == pytest.approx(1.5)


def test_the_validator_reads_the_emitters_reference_not_the_raster(
        gate_on, dem, patch_authors_everything):
    """THE TWO-INSTRUMENTS GUARD (ruling R5, one solve).  A validator that
    re-sampled raw DEM here would refuse — 36 m over the raster — exactly
    what the emitter lawfully served.  It reads the recorded reference
    instead, and still fires when the emitted surface really does stand
    over the cap above that ground."""
    layout = make_layout()
    assert emit(layout, dem, [pad_frame(
        layout, [square_ring(0.0, 0.0, 8.0)], base_y=1.0, agl=0.0)]) == 1
    assert verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON) == []

    layout.object_pad_records[0]["ground_reference_metres"] = 20.0
    findings = verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON)
    assert [f[0] for f in findings] == ["pad_over_cap_emitted"]
    assert findings[0][2] == pytest.approx(21.0)


def test_a_part_below_the_residual_floor_raises_no_pad(gate_on, dem):
    """The materiality floor is the law's, not a tuning knob: a part
    already sitting on the ground within
    ``DSF_OBJECT_NOBAKE_PAD_FLOOR_M`` raises nothing at all — which is
    the owner's whole intent ("an object already close to terrain must
    not need moving")."""
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)],
                        target_m=BASE_TERRAIN_M + 0.05)]
    assert emit(layout, dem, frames) == 0
    assert not layout.object_pad_records


def test_an_unhosted_datum_is_left_to_the_y_bake(gate_on, dem):
    """The ruling is exact only where the PATCH authors the datum's
    ground.  A render datum standing off every emitted shape has no node
    to read, so the request is reported and the object keeps the y-bake —
    never approximated from the DEM (that is the design the premise test
    rejected)."""
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], base_y=1.5,
                        anchor_m=(4000.0, 4000.0))]
    assert emit(layout, dem, frames) == 0
    assert "pad_datum_unhosted" in kinds(layout.object_pad_findings)


def test_a_self_covering_request_routes_to_the_y_bake(gate_on, dem):
    """STEP 5, THE CIRCULARITY.  When the pad's own ring covers its
    render datum, raising the ground raises the object with it: the
    residual is ``AGL + base_y`` under EVERY target, so no pad can close
    it.  Measured at HECA: 1 of 1883 requests.  Such a request is routed
    to the y-bake — which moves the OBJECT — and never emitted."""
    layout = make_layout(apron_ring=square_ring(0.0, 0.0, 200.0))
    # Datum at the origin, inside the pad's own ring (and hosted by the
    # big apron, so the datum itself resolves).
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], base_y=1.5,
                        anchor_m=(0.0, 0.0))]
    assert emit(layout, dem, frames) == 0
    assert "pad_self_covering_datum" in kinds(layout.object_pad_findings)
    # …and the SAME request with its datum outside its ring emits.
    layout = make_layout(apron_ring=square_ring(150.0, 150.0, 40.0))
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], base_y=1.5,
                        anchor_m=(150.0, 150.0))]
    assert emit(layout, dem, frames) >= 1


def test_pavement_wins_absolutely_the_pad_is_clipped(gate_on, dem):
    """§5.1 clause 2, owner ruling R2: a pad never contributes, moves or
    re-values a pavement vertex.  The overlapping half is DIFFERENCED
    away, and the pavement shape is byte-identical across the emitter."""
    apron = square_ring(0.0, 20.0, 20.0)             # covers y in [0, 40]
    layout = make_layout(apron_ring=apron)
    apron_shape = layout.shapes[0]
    before = (apron_shape.polygon.wkb, list(apron_shape.node_altitudes))
    frames = [pad_frame(layout, [square_ring(0.0, -8.0, 8.0)],
                        target_m=6.5)]
    assert emit(layout, dem, frames) >= 1
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
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], base_y=1.5,
                        anchor_m=(50.0, 50.0))]
    assert emit(layout, dem, frames) == 0
    assert "pad_wholly_inside_pavement" in kinds(layout.object_pad_findings)


def test_the_pad_is_pulled_toward_pavement_and_never_touches_it(gate_on,
                                                                dem):
    """§5.1 clause 3 under WELD OR GAP.  The pull is UNCHANGED law: a
    short run to pavement governs the whole pad, and the shortfall is
    reported.  What changed is the transition — there is no blend annulus
    to weld, so the emitted core stands clear of the apron and the mesh
    drapes the gap.  A pad that shared an edge with pavement at a
    different value would now be an interior disagreement, which the
    ruling calls always a defect."""
    # Apron edge at y = 10, the pad's derived ring touching it exactly.
    layout = make_layout(apron_ring=[(-20.0, 9.99), (20.0, 9.99),
                                     (20.0, 50.0), (-20.0, 50.0)])
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)]
    assert emit(layout, dem, frames) >= 1
    # run ~= margin (2 m) at the 5 % groundside cap => 0.1 m of authority.
    core = cores(layout)[0]
    assert all(abs(a - (APRON_ALT_M + 0.1)) <= 0.02
               for a in core.node_altitudes)
    shortfall = [f for f in layout.object_pad_findings
                 if f[0] == "pad_pull_shortfall"]
    assert len(shortfall) == 1
    assert shortfall[0][2] == pytest.approx(0.4, abs=0.02)
    # THE GAP: no emitted pad vertex is on the apron ring.
    apron = layout.shapes[0].polygon
    assert core.polygon.distance(apron) > 1.0


def test_a_tight_hull_still_holds_the_base_on_a_shorter_erosion(gate_on,
                                                                dem):
    """The OTHH corpus class: a contact hull about a metre across.
    Eroding by the full 2 m margin would leave NO interior and the
    building base would be held nowhere — so the erosion shortens and a
    real core survives."""
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 0.5)], target_m=6.5)]
    assert emit(layout, dem, frames) >= 1
    core = cores(layout)[0]
    assert all(abs(a - 6.5) <= 0.01 for a in core.node_altitudes)
    assert core.polygon.area > 0.5
    assert layout.object_pad_records[0]["blend_width_m"] < MARGIN_M


def test_a_ring_with_no_usable_interior_is_refused_with_its_area(
        gate_on, dem, monkeypatch):
    """§5.4/§5.5: an inadmissible pad is REPORTED with its measured
    numbers, never emitted as a stand-in.  A ring the erosion consumes
    whole has nowhere to hold the base and would be a bare step onto raw
    DEM.  The erosion width is the LAW's
    (``grade_law.object_pad_blend_width_m``, capped at half the ring's
    own inradius so an interior always survives a real hull), so the
    degenerate case is driven through the law function rather than
    fabricated as geometry."""
    monkeypatch.setattr(object_pads, "object_pad_blend_width_m",
                        lambda area, perimeter, margin: 0.0)
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)]
    assert emit(layout, dem, frames) == 0
    refused = [f for f in layout.object_pad_findings
               if f[0] == "pad_no_contact_hull"]
    assert len(refused) == 1
    assert refused[0][2] > 0.0                     # the measured ring area


def test_a_pad_is_claimed_by_the_airport_whose_ground_it_stands_on(gate_on,
                                                                   dem):
    """A DSF cell can carry two airports' objects: measured on +25+051,
    all 823 OTHH terminal requests are recorded under OTBD because one
    Global Airports DSF cell carries both.  A patch is per airport, so
    GEOMETRY has to claim — otherwise the airport that needs the pads
    emits none and the one that does not emits them 5 km from its own
    ground."""
    layout = make_layout()
    mine = pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5,
                     key=1)
    # 5 km east — inside the tile, outside this airport entirely.
    far = pad_frame(layout,
                    [[(x + 5000.0, y) for x, y in square_ring(0.0, 0.0, 8.0)]],
                    target_m=6.5, key=2, structure_index=1)
    assert emit(layout, dem, [mine, far]) >= 1
    assert len(layout.object_pad_records) == 1, \
        "exactly the pad standing on this airport's ground"
    assert layout.object_pad_records[0]["resource_path"] == \
        "Buildings/pad1.obj"
    assert layout.object_pad_records[0]["icao"] == "TEST", \
        "the record is owned by the EMITTING airport"


def test_a_pad_is_clipped_by_earlier_terrain_features(gate_on, dem):
    """§5.4 precedence: pavement > existing terrain features > pads > raw
    DEM.  A band/skirt/OLS shape already in the layout takes the ground
    it covers; the pad keeps only the remainder."""
    from auto_patch.layout import ROLE_BOUNDARY

    layout = make_layout()
    strip = square_ring(0.0, 20.0, 20.0)
    layout.shapes.append(BuiltShape(
        polygon=Polygon(strip + [strip[0]]), role=ROLE_BOUNDARY,
        ref="band", node_altitudes=[5.2] * 5))
    frames = [pad_frame(layout, [square_ring(0.0, -6.0, 8.0)],
                        target_m=6.5)]
    assert emit(layout, dem, frames) >= 1
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
    frames = [pad_frame(layout, [square_ring(0.0, 17.0, 8.0)],
                        target_m=6.5)]
    emit(layout, dem, frames)                      # must not raise
    assert "pad_deformed_pavement" not in kinds(layout.object_pad_findings)


def test_two_pads_never_overlap_each_other(gate_on, dem):
    """Pad↔pad exclusivity: the second pad is clipped against the first,
    so no ground is claimed twice (the ``ols`` emitted-pieces rule)."""
    layout = make_layout()
    frames = [
        pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5,
                  key=1, structure_index=0),
        pad_frame(layout, [square_ring(8.0, 0.0, 8.0)], target_m=6.2,
                  key=2, structure_index=1),
    ]
    assert emit(layout, dem, frames) >= 2
    shapes = [s.polygon for s in pads(layout)]
    for i, a in enumerate(shapes):
        for b in shapes[i + 1:]:
            assert a.intersection(b).area == pytest.approx(0.0, abs=1e-6)


def test_emission_is_deterministic(gate_on, dem):
    """Same inputs, same pads — emitted in a stable seat order, never in
    dict/hash order.  This is the unit-scale statement of the ruling's
    own acceptance (a): with the read-back gone, a second run of the same
    build has nothing left to ratchet on."""
    runs = []
    for _ in range(2):
        layout = make_layout()
        frames = [
            pad_frame(layout, [square_ring(40.0, 0.0, 8.0)], target_m=6.4,
                      key=7, structure_index=1),
            pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5,
                      key=3, structure_index=0),
        ]
        emit(layout, dem, frames)
        runs.append([(s.ref, s.polygon.wkb, tuple(s.node_altitudes))
                     for s in pads(layout)])
    assert runs[0] == runs[1]


def test_re_emission_over_the_same_layout_is_byte_stable(gate_on, dem):
    """THE RATCHET'S UNIT TWIN.  The old consumer read its own previous
    ``emitted`` records back, so the population could only grow.  Now a
    second emission over a layout that already carries a build's pads
    reproduces exactly the same pads: the derivation reads the FRAME and
    the patch, and ``patch_ground`` drops pad roles at construction, so
    the pads it just emitted cannot become their own input."""
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)]
    assert emit(layout, dem, frames) >= 1
    first = [(s.ref, s.polygon.wkb, tuple(s.node_altitudes))
             for s in pads(layout)]
    # Emit AGAIN into the same layout — the pathological case the
    # read-back turned into a ratchet.
    emit(layout, dem, frames)
    second = [(s.ref, s.polygon.wkb, tuple(s.node_altitudes))
              for s in pads(layout)]
    assert len(second) == 2 * len(first), "the fixture must re-emit"
    assert second[len(first):] == first


# ══════════════════════════════════════════════════════════════════════
# THE READ-BACK IS RETIRED (R3 step 4) — the rails, loud
# ══════════════════════════════════════════════════════════════════════

def test_the_sidecar_reader_is_gone_from_the_emission_path():
    """The consumer functions are REMOVED, not merely unreferenced: a
    reader left in place is a reader something calls again."""
    for name in ("pads_for_airport", "merge_emitted_records",
                 "_airport_entry", "_blend_values"):
        assert not hasattr(object_pads, name), name


def test_no_terrain_module_reads_the_pad_sidecar():
    """The sidecar is the y-bake's WRITE-ONLY audit trail.  Grepping the
    build path is the assertion, because the failure this guards against
    is a future call site, not a stale one."""
    import pathlib

    root = pathlib.Path(object_pads.__file__).parent
    offenders = []
    for path in sorted(root.glob("*.py")):
        if path.name in ("object_pads.py", "post_mesh.py"):
            continue                              # the writer and the reader
        text = path.read_text()
        if "load_sidecar" in text or "OBJECT_FOOT_PAD_SIDECAR" in text:
            offenders.append(path.name)
    assert offenders == [], offenders


def test_the_driver_no_longer_persists_emitted_records():
    from auto_patch import driver

    source = pathlib.Path(driver.__file__).read_text()
    assert "merge_emitted_records" not in source


def test_emission_needs_no_patch_dir_when_frames_are_supplied(gate_on, dem):
    """Nothing on disk is consulted for a pad any more: hand the emitter
    frames and it emits, with no patch directory at all."""
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)]
    assert object_pads.emit_object_pads(
        layout, dem, TILE_LAT, TILE_LON, icao="TEST",
        pad_frames=frames, patch_dir=None) >= 1


def test_no_frames_means_no_pads_and_no_findings(gate_on, dem):
    layout = make_layout()
    assert object_pads.emit_object_pads(
        layout, dem, TILE_LAT, TILE_LON, icao="TEST", pad_frames=[]) == 0
    assert layout.object_pad_records == []


# ══════════════════════════════════════════════════════════════════════
# THE VALIDATOR (§5.5) — lockstep with the emitter, law unchanged
# ══════════════════════════════════════════════════════════════════════

def test_a_lawful_emission_is_finding_clean(gate_on, dem):
    layout = make_layout()
    emit(layout, dem,
         [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)])
    findings = verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON)
    assert findings == [], findings


def test_the_validator_reads_the_rendered_base_the_same_relative_way(
        gate_on, dem):
    """LOCKSTEP (R5) across the mechanism change: the verifier compares
    each core vertex against the target the EMITTER recorded — which is
    now the patch-relative rendered base — so it measures the coupling
    the ruling defines rather than an absolute number of its own."""
    layout = make_layout(apron_alt=6.75)
    emit(layout, dem, [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)],
                                 base_y=0.5, agl=0.25)])
    record = layout.object_pad_records[0]
    assert record["emitted_target_metres"] == pytest.approx(7.5)
    assert verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON) == []


def test_the_validator_catches_a_core_off_its_law_target(gate_on, dem):
    """Lockstep (R5): the reader recomputes the target from the SAME law
    the emitter used, so a surface that drifts from it is visible."""
    layout = make_layout()
    emit(layout, dem,
         [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=6.5)])
    core = cores(layout)[0]
    core.node_altitudes = [a + 0.5 for a in core.node_altitudes]
    findings = verification.check_object_pads(
        layout, dem, TILE_LAT, TILE_LON)
    assert "pad_core_off_target" in kinds(findings)


def test_the_validator_surfaces_refusals(gate_on, dem):
    """§5.5: "every refused pad (over-cap relief, inadmissible clip)
    surfaced as a finding carrying the measured numbers"."""
    layout = make_layout()
    emit(layout, dem,
         [pad_frame(layout, [square_ring(0.0, 0.0, 8.0)], target_m=12.0)])
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
# The ring law is unchanged; what moved is WHERE it is applied — in-run
# over the frame's contact parts instead of post-mesh over the rebake's.
# So the same structural properties are pinned on the new path: one pad
# per connected component, refusal accounting per component, and every
# emitted polygon inside the contact hulls it came from.
# ══════════════════════════════════════════════════════════════════════

def test_each_component_of_a_structure_becomes_its_own_pad(gate_on, dem):
    """§2.5: "each connected component of that union raised as its OWN
    request ring".  Three parts strung 40 m apart are three pads, each
    hugging its own object — not one rectangle over the ground between
    them."""
    layout = make_layout()
    frames = [pad_frame(layout, [square_ring(-40.0, -40.0, 5.0),
                                 square_ring(0.0, -40.0, 5.0),
                                 square_ring(40.0, -40.0, 5.0)],
                        target_m=6.5)]
    assert emit(layout, dem, frames) == 3
    assert len(cores(layout)) == 3
    records = layout.object_pad_records
    assert len(records) == 3
    assert sorted(r["ring_index"] for r in records) == [0, 1, 2]
    assert len({r["seat_key"] for r in records}) == 3
    assert len({r["fingerprint"] for r in records}) == 3
    # The retired law would have graded the 90 m strip between them.
    assert sum(r["area_m2"] for r in records) < 1200.0


def test_every_emitted_pad_lies_inside_its_contact_hulls(gate_on, dem):
    """THE STRUCTURAL ASSERTION (§2.5): every emitted pad polygon is
    covered by (the contact-hull union ⊕ margin), so no pad vertex is
    further than the margin from a real contact."""
    from shapely.ops import unary_union

    layout = make_layout()
    hulls = [square_ring(-30.0, -30.0, 6.0), square_ring(0.0, -45.0, 3.0),
             square_ring(25.0, -25.0, 8.0), square_ring(-5.0, -20.0, 4.0)]
    assert emit(layout, dem,
                [pad_frame(layout, hulls, target_m=6.5)]) > 0
    allowed = unary_union(
        [Polygon(hull + [hull[0]]) for hull in hulls]
    ).buffer(MARGIN_M + 0.05)                      # + the round-trip eps
    for shape in pads(layout):
        assert shape.polygon.within(allowed), shape.ref


def test_a_component_lost_to_pavement_does_not_condemn_its_siblings(
        gate_on, dem):
    """The refusal accounting still PARTITIONS: one component wholly
    inside the apron is refused with its own key while the other emits."""
    layout = make_layout(apron_ring=[(20.0, 20.0), (100.0, 20.0),
                                     (100.0, 100.0), (20.0, 100.0)])
    frames = [pad_frame(layout, [square_ring(-40.0, -40.0, 5.0),
                                 square_ring(60.0, 60.0, 5.0)],
                        target_m=6.5, anchor_m=(95.0, 25.0))]
    assert emit(layout, dem, frames) > 0
    assert len(cores(layout)) == 1
    refused = [f for f in layout.object_pad_findings
               if f[0] == "pad_wholly_inside_pavement"]
    assert len(refused) == 1
    assert refused[0][1] != layout.object_pad_records[0]["seat_key"]


# ── the law digest ────────────────────────────────────────────────────

def test_the_law_digest_moves_with_the_sidecar_version(monkeypatch):
    """The version is part of the pad law's fingerprint, so a record
    written under an older law can never match this build's digest."""
    before = object_pads.law_digest()
    monkeypatch.setattr(post_mesh, "OBJECT_FOOT_PAD_SIDECAR_VERSION", 3)
    assert object_pads.law_digest() != before
