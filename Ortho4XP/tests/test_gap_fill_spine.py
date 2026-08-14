"""Gap-fill + drainage SPINE emitter (user design ruling 2026-07-09).

Synthetic fixtures only (no airport build): a rectangular pavement FRAME
— two parallel runway rectangles joined by two end stubs — encloses one
rectangular hole.  The emitter must grade that hole as ONE unit, boundary
VERBATIM + a single drainage spine, splitting it into two half-gap faces.

Pins:
  * exactly TWO half-gap faces emitted from one enclosed gap;
  * every NON-spine (boundary) face vertex is a VERBATIM pavement ring
    vertex (chain identity — no new boundary geometry);
  * every deep-interior spine value sits inside the law drainage corridor
    (computed from ``adjacent_ground_envelope`` directly) and below the
    pavement edge;
  * a gap wider than ``GAP_FILL_MAX_WIDTH_M`` emits nothing;
  * the gate off emits nothing.
"""
import math

import pytest
from shapely.geometry import Point as _pt, Polygon

from auto_patch import gap_fill as GF
from auto_patch.gap_fill import emit_gap_fill_spines, _parent_family_code
from auto_patch.grade_law import adjacent_ground_envelope
from auto_patch.emit_decimate import _key
from auto_patch.layout import (
    BuiltShape, ROLE_BUILDING, ROLE_GRADED_STRIP, ROLE_RUNWAY,
    ROLE_RUNWAY_CLEARANCE, ROLE_STUB,
)

EDGE_ALT = 100.0
PAD_ALT = 103.0                           # distinct flat pad authority


class _FakeLayout:
    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)

    def ll_to_m(self, lat, lon):
        return (lon * 111320.0, lat * 111320.0)

    def __init__(self, shapes):
        self.shapes = shapes
        self.airport_boundary = None
        self.anchor = (0.0, 0.0)


def _rect(x0, y0, x1, y1, role):
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    coords = list(poly.exterior.coords)
    return BuiltShape(polygon=poly, role=role,
                      node_altitudes=[EDGE_ALT] * len(coords))


def _frame_layout(gap_half_width_m):
    """A rectangular pavement frame enclosing ONE rectangular hole.

    Two long parallel RUNWAY rects (long enough to key ICAO code 3, so a
    30 m half-gap lands inside the graded band) joined by two end STUBS;
    the hole spans ``2*gap_half_width_m`` across.  All pavement flat at
    ``EDGE_ALT``."""
    length = 1300.0                       # code 3 → 75 m graded half-width
    inner_x0, inner_x1 = 30.0, length - 30.0
    y_bot0, y_bot1 = 0.0, 30.0
    y_gap0 = y_bot1
    y_gap1 = y_gap0 + 2.0 * gap_half_width_m
    y_top0, y_top1 = y_gap1, y_gap1 + 30.0
    shapes = [
        _rect(0.0, y_bot0, length, y_bot1, ROLE_RUNWAY),        # bottom
        _rect(0.0, y_top0, length, y_top1, ROLE_RUNWAY),        # top
        _rect(0.0, y_gap0, inner_x0, y_gap1, ROLE_STUB),        # left end
        _rect(inner_x1, y_gap0, length, y_gap1, ROLE_STUB),     # right end
    ]
    return _FakeLayout(shapes), list(shapes)   # pav = snapshot of pavement


def _pad_rect(x0, y0, x1, y1, alt):
    """A flat ROLE_BUILDING pad at ``alt`` (buildings are flat)."""
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    coords = list(poly.exterior.coords)
    return BuiltShape(polygon=poly, role=ROLE_BUILDING,
                      node_altitudes=[alt] * len(coords))


def _small_frame():
    """A compact rectangular frame enclosing ONE small hole
    (x in [30, 130], y in [30, 90] → 100 x 60 = 6000 m2).  Used for the
    pad-FILL / sub-min-residual cases, where the skip happens on the
    residual-area gate before any drainage-envelope read."""
    length = 160.0
    shapes = [
        _rect(0.0, 0.0, length, 30.0, ROLE_RUNWAY),      # bottom
        _rect(0.0, 90.0, length, 120.0, ROLE_RUNWAY),    # top
        _rect(0.0, 30.0, 30.0, 90.0, ROLE_STUB),         # left end
        _rect(130.0, 30.0, length, 90.0, ROLE_STUB),     # right end
    ]
    return _FakeLayout(shapes), list(shapes)


def _pavement_keys(shapes):
    keys = set()
    for s in shapes:
        for vx, vy in s.polygon.exterior.coords:
            keys.add(_key(vx, vy))
    return keys


def _faces(layout):
    return [s for s in layout.shapes if s.role == ROLE_GRADED_STRIP]


def test_encloses_gap_emits_exactly_two_faces():
    """Open-way redesign (user 2026-07-09 round 2): ONE face — the gap
    polygon verbatim — plus the spine as an interior OPEN WAY held off
    the boundary (layout.gap_spines)."""
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    n = emit_gap_fill_spines(layout, None, 0, 0)
    faces = _faces(layout)
    assert n == 1
    assert len(faces) == 1
    for f in faces:
        assert f.ref == "gap_fill_spine"
        # node_altitudes carry the closing repeat.
        assert len(f.node_altitudes) == len(f.polygon.exterior.coords)
    spines = getattr(layout, "gap_spines", None)
    assert spines and len(spines) == 1
    pts_ll, vals = spines[0]
    assert len(pts_ll) == len(vals) >= 2


def test_boundary_vertices_are_verbatim_pavement_vertices():
    """Chain identity: every face vertex is either a VERBATIM pavement
    ring vertex or a spine vertex (the shared edge of the two faces).  No
    face vertex is new boundary geometry."""
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    emit_gap_fill_spines(layout, None, 0, 0)
    faces = _faces(layout)
    assert len(faces) == 1
    pav_keys = _pavement_keys(pav)

    coords = list(faces[0].polygon.exterior.coords)[:-1]
    for x, y in coords:
        assert _key(x, y) in pav_keys, (
            "boundary vertex is not a verbatim pavement vertex")


def test_spine_values_lie_in_the_law_drainage_corridor():
    """Deep-interior spine values fall BELOW the pavement edge and stay
    inside the two-parent drainage interval — bounds taken straight from
    ``adjacent_ground_envelope`` (no hard-coded numbers).  The spine now
    lives in ``layout.gap_spines`` (open-way redesign) with lat/lon
    points; values are checked against the interval at each point."""
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    emit_gap_fill_spines(layout, None, 0, 0)
    spines = getattr(layout, "gap_spines", None)
    assert spines and len(spines) == 1
    pts_ll, vals = spines[0]
    checked = 0
    for (la, lo), alt in zip(pts_ll, vals):
        vx, vy = layout.ll_to_m(la, lo)
        dists = sorted(
            ((s.polygon.exterior.distance(_pt(vx, vy)), s) for s in pav),
            key=lambda t: t[0])
        (dA, sA), (dB, sB) = dists[0], dists[1]
        if dA < 2.0 or dB < 2.0:
            continue                     # near an end pin — skip
        lo_b, hi_b = None, None
        for d, s in ((dA, sA), (dB, sB)):
            _r, _cn, _cl = _parent_family_code(layout, s)
            fl, ce = adjacent_ground_envelope(_r, _cn, _cl, d)
            if fl is None and ce is None:
                continue
            e = 100.0                    # flat fixture pavement
            f_ = e + fl if fl is not None else None
            c_ = e + ce if ce is not None else None
            if f_ is not None:
                lo_b = f_ if lo_b is None else max(lo_b, f_)
            if c_ is not None:
                hi_b = c_ if hi_b is None else min(hi_b, c_)
        if lo_b is None or hi_b is None:
            continue
        assert lo_b - 0.2 <= alt <= hi_b + 0.2, (
            f"spine value {alt} outside [{lo_b}, {hi_b}]")
        checked += 1
    assert checked >= 1


def test_wide_gap_emits_nothing():
    """A gap whose short side exceeds GAP_FILL_MAX_WIDTH_M stays with the
    corridor-band emitter (half-gap 100 m → 200 m short side > 160 m)."""
    layout, _ = _frame_layout(gap_half_width_m=100.0)
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n == 0
    assert _faces(layout) == []


def test_gate_off_emits_nothing(monkeypatch):
    monkeypatch.setattr(GF, "GAP_FILL_SPINE_ENABLED", False)
    # The interior-ring sub-gate (default ON since the round-8 flip,
    # 2026-07-11) REQUIRES the spine gate — hard error otherwise
    # (covered by test_gap_interior_rings) — so a plain gate-off run
    # patches both.
    monkeypatch.setattr(GF, "GAP_FILL_INTERIOR_RINGS_ENABLED", False)
    layout, _ = _frame_layout(gap_half_width_m=30.0)
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n == 0
    assert _faces(layout) == []


# ── BUILDING-PAD GAP PARENTS (user design 2026-07-09, queue item 5) ──


def test_pad_filling_gap_lawfully_skips():
    """A building pad that FILLS the between-pavement hole leaves no
    residual ground above GAP_FILL_MIN_AREA_M2 → lawful skip (the
    building IS the surface; there is no ground to drain)."""
    layout, pav = _small_frame()
    # Hole is x in [30, 130], y in [30, 90]; a pad covering it exactly
    # leaves residual area 0 < GAP_FILL_MIN_AREA_M2.
    layout.shapes.append(_pad_rect(30.0, 30.0, 130.0, 90.0, PAD_ALT))
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n == 0
    assert _faces(layout) == []


def test_pad_residual_below_min_area_skips():
    """A pad that leaves only a sub-min sliver of residual ground
    (100 x 0.8 = 80 m2 < GAP_FILL_MIN_AREA_M2) is a lawful skip."""
    layout, pav = _small_frame()
    layout.shapes.append(_pad_rect(30.0, 30.0, 130.0, 89.2, PAD_ALT))
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n == 0
    assert _faces(layout) == []


def test_pad_touching_ring_emits_with_pad_chain_verbatim():
    """A pad that bites a notch out of the hole (its bottom edge
    COLLINEAR with the runway edge, its interior corners inside the
    hole) emits the residual ground.  The pad ring vertices appear
    VERBATIM in the emitted face boundary (chain identity — every face
    vertex is a pavement OR pad ring vertex) and carry the pad's flat
    authoritative value (pad-value-wins at pad nodes)."""
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    # Notch pad: bottom edge y=30 lies on the runway top edge; interior
    # corners (600,70),(700,70) sit inside the hole (y in [30, 90]).
    layout.shapes.append(_pad_rect(600.0, 30.0, 700.0, 70.0, PAD_ALT))
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n >= 1
    faces = _faces(layout)
    assert faces
    pav_keys = _pavement_keys(pav)
    pad_keys = {_key(600.0, 70.0), _key(700.0, 70.0),
                _key(600.0, 30.0), _key(700.0, 30.0)}
    face_keys = set()
    pad_node_vals = []
    for f in faces:
        coords = list(f.polygon.exterior.coords)
        for i, (x, y) in enumerate(coords[:-1]):
            k = _key(x, y)
            # Chain identity: every boundary vertex is verbatim.
            assert k in pav_keys or k in pad_keys, (
                "face vertex is neither a pavement nor a pad ring vertex")
            face_keys.add(k)
            if k in (_key(600.0, 70.0), _key(700.0, 70.0)):
                pad_node_vals.append(f.node_altitudes[i])
    # The pad's interior corners are IN the boundary (pad chain verbatim).
    assert _key(600.0, 70.0) in face_keys
    assert _key(700.0, 70.0) in face_keys
    # ... and every such shared node carries the pad's flat value.
    assert pad_node_vals
    for v in pad_node_vals:
        assert abs(v - PAD_ALT) < 0.2, (
            f"pad node value {v} did not adopt the pad authority {PAD_ALT}")


def test_pad_parent_gate_off_pad_blocks(monkeypatch):
    """With O4_GAP_FILL_PAD_PARENTS off, a building pad is a BLOCKER
    again (the pre-pad behavior): the hole is skipped as foreign-shape-
    inside and nothing emits."""
    monkeypatch.setenv("O4_GAP_FILL_PAD_PARENTS", "0")
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    layout.shapes.append(_pad_rect(600.0, 30.0, 700.0, 70.0, PAD_ALT))
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n == 0
    assert _faces(layout) == []


# ── RUNWAY-END SKIRT GAP PARENTS (supervisor follow-up 2026-07-09) ──


def _skirt_rect(x0, y0, x1, y1, corner_alts):
    """A runway-end skirt fixture: role runway_clearance,
    ref runway_end_skirt, NON-flat per-vertex node_altitudes carrying a
    governed runway-end profile (4 corner values, closing repeat
    appended)."""
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return BuiltShape(polygon=poly, role=ROLE_RUNWAY_CLEARANCE,
                      ref="runway_end_skirt",
                      node_altitudes=list(corner_alts) + [corner_alts[0]])


def test_skirt_notch_emits_with_nonflat_profile_adopted():
    """A skirt biting a notch out of the hole (bottom edge collinear
    with the runway edge, interior corners inside the hole) emits the
    residual ground; the shared skirt-ring nodes adopt the skirt's
    PER-VERTEX profile values — NOT a flat mean — mirroring
    pad-wins-at-pad-nodes for a non-flat authority."""
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    # Corner order: (600,30) (700,30) (700,70) (600,70); a sloping
    # runway-end profile — the two interior corners carry DISTINCT
    # values so adoption of the profile (not an average) is provable.
    layout.shapes.append(
        _skirt_rect(600.0, 30.0, 700.0, 70.0,
                    [100.0, 100.0, 104.0, 106.0]))
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n >= 1
    faces = _faces(layout)
    assert faces
    pav_keys = _pavement_keys(pav)
    skirt_keys = {_key(600.0, 30.0), _key(700.0, 30.0),
                  _key(700.0, 70.0), _key(600.0, 70.0)}
    expected = {_key(600.0, 70.0): 106.0, _key(700.0, 70.0): 104.0}
    seen = {}
    for f in faces:
        coords = list(f.polygon.exterior.coords)
        for i, (x, y) in enumerate(coords[:-1]):
            k = _key(x, y)
            assert k in pav_keys or k in skirt_keys, (
                "face vertex is neither a pavement nor a skirt ring vertex")
            if k in expected:
                seen[k] = f.node_altitudes[i]
    assert set(seen) == set(expected), "skirt interior corners not in face"
    for k, want in expected.items():
        assert abs(seen[k] - want) < 0.05, (
            f"skirt node value {seen[k]} did not adopt the skirt "
            f"profile value {want}")


def test_skirt_wholly_inside_emits_annular_face_and_spine_avoids_it():
    """A skirt WHOLLY inside the hole (the CYXY census hole 27 shape):
    the residual is annular, its exterior is the pavement ring verbatim,
    and it emits.  Every drainage-spine segment stays clear of the skirt
    footprint (no open way crosses the parent ring)."""
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    skirt = _skirt_rect(600.0, 45.0, 700.0, 55.0,
                        [101.0, 101.0, 102.0, 102.0])
    layout.shapes.append(skirt)
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n == 1
    faces = _faces(layout)
    assert len(faces) == 1
    pav_keys = _pavement_keys(pav)
    for x, y in list(faces[0].polygon.exterior.coords)[:-1]:
        assert _key(x, y) in pav_keys, (
            "annular-face exterior vertex is not a verbatim pavement vertex")
    spines = getattr(layout, "gap_spines", None)
    assert spines
    from shapely.geometry import LineString
    for pts_ll, vals in spines:
        assert len(pts_ll) == len(vals) >= 2
        pts_m = [layout.ll_to_m(la, lo) for la, lo in pts_ll]
        for a, b in zip(pts_m, pts_m[1:]):
            seg = LineString([a, b])
            inside_len = seg.intersection(skirt.polygon).length
            assert inside_len < 1e-6, (
                f"spine segment crosses the skirt footprint "
                f"(overlap {inside_len:.3f} m)")


def test_skirt_wholly_inside_face_does_not_bury_the_skirt():
    """Regression (CYXY test_no_self_overlap): a skirt WHOLLY inside the
    hole makes an ANNULAR residual, but ``_open_coords`` keeps only the
    exterior ring.  Without re-attaching the parent hole the emitted
    graded_strip refills the skirt footprint and overlaps it (1,925 m² at
    CYXY).  The emitted face must carry the skirt as an interior ring so
    it never covers the skirt, while its EXTERIOR ring (and the
    ``node_altitudes`` aligned to it) is unchanged."""
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    skirt = _skirt_rect(600.0, 45.0, 700.0, 55.0,
                        [101.0, 101.0, 102.0, 102.0])
    layout.shapes.append(skirt)
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n == 1
    faces = _faces(layout)
    assert len(faces) == 1
    face = faces[0]
    # The face must NOT cover the skirt footprint (the whole point).
    overlap = face.polygon.intersection(skirt.polygon).area
    assert overlap < 1e-6, (
        f"emitted graded_strip buries the skirt footprint "
        f"(overlap {overlap:.3f} m2)")
    # It carries the skirt as a verbatim interior ring (a true annulus).
    assert len(face.polygon.interiors) == 1, (
        "annular face lost its parent hole")
    skirt_keys = {_key(x, y) for x, y in skirt.polygon.exterior.coords}
    for x, y in face.polygon.interiors[0].coords:
        assert _key(x, y) in skirt_keys, (
            "interior ring vertex is not a verbatim skirt vertex")
    # node_altitudes stay aligned to the (unchanged) EXTERIOR ring — the
    # only ring to_osm reads — one value per closed exterior vertex.
    assert len(face.node_altitudes) == len(face.polygon.exterior.coords)


def test_parent_minting_crossings_lawfully_skips():
    """A parent straddling the gap ring MID-EDGE (its ring crossing a
    pavement edge away from any shared vertex) would make the residual
    boundary contain difference-MINTED crossing vertices — not chain
    identity.  The face must lawfully skip (zero-lens law), emitting
    nothing."""
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    # Bottom edge y=20 sits INSIDE the bottom runway (y 0..30); the
    # skirt sides cross the gap ring at (600,30)/(700,30), which are
    # vertices of NEITHER ring — minted crossings.
    layout.shapes.append(
        _skirt_rect(600.0, 20.0, 700.0, 70.0,
                    [100.0, 100.0, 104.0, 106.0]))
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n == 0
    assert _faces(layout) == []


def test_skirt_parent_gate_off_skirt_blocks(monkeypatch):
    """With O4_GAP_FILL_SKIRT_PARENTS off, a runway-end skirt is a
    BLOCKER again (the pre-extension behavior): the hole is skipped as
    foreign-shape-inside and nothing emits."""
    monkeypatch.setenv("O4_GAP_FILL_SKIRT_PARENTS", "0")
    layout, pav = _frame_layout(gap_half_width_m=30.0)
    layout.shapes.append(
        _skirt_rect(600.0, 30.0, 700.0, 70.0,
                    [100.0, 100.0, 104.0, 106.0]))
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n == 0
    assert _faces(layout) == []


# ── OPEN-FRONTAGE CORRIDOR SPINE (slice B pilot, ruling 3) ──────────────
# Two PARALLEL runway rects with an OPEN corridor between them (no end
# stubs — the corridor is open at both ends, so it is NOT an interior ring
# and the enclosed-gap path never touches it).  The pilot must detect it,
# emit ONE face (long sides = the two runway edges verbatim, ends = straight
# closures across the mouth) + one drainage spine, and be a total no-op with
# its gate off.
OPEN_FRONTAGE_REF = "open_frontage_spine"


def _corridor_layout(gap_width_m):
    """Two long parallel RUNWAY rects (code-3 length) with a corridor
    ``gap_width_m`` wide OPEN at both ends between them."""
    length = 1300.0
    shapes = [
        _rect(0.0, 0.0, length, 30.0, ROLE_RUNWAY),                 # bottom
        _rect(0.0, 30.0 + gap_width_m, length, 60.0 + gap_width_m,  # top
              ROLE_RUNWAY),
    ]
    return _FakeLayout(shapes), list(shapes)


def _open_faces(layout):
    return [s for s in layout.shapes
            if s.role == ROLE_GRADED_STRIP and s.ref == OPEN_FRONTAGE_REF]


def test_open_corridor_emits_one_verbatim_face_and_spine(monkeypatch):
    """Gate ON: a runway ↔ parallel-runway corridor emits ONE
    open-frontage face whose every boundary vertex is a VERBATIM pavement
    ring vertex (long sides verbatim; the mouth closures connect two
    pavement vertices), plus one interior drainage spine."""
    monkeypatch.setenv("O4_OPEN_FRONTAGE_SPINE", "1")
    layout, pav = _corridor_layout(gap_width_m=60.0)
    emit_gap_fill_spines(layout, None, 0, 0)
    faces = _open_faces(layout)
    assert len(faces) == 1
    pav_keys = _pavement_keys(pav)
    for x, y in list(faces[0].polygon.exterior.coords)[:-1]:
        assert _key(x, y) in pav_keys, (
            "open-frontage face vertex is not a verbatim pavement vertex")
    assert len(faces[0].node_altitudes) == len(
        faces[0].polygon.exterior.coords)
    spines = getattr(layout, "gap_spines", None)
    assert spines and len(spines) >= 1
    pts_ll, vals = spines[-1]
    assert len(pts_ll) == len(vals) >= 2


def test_open_corridor_spine_values_below_pavement(monkeypatch):
    """The corridor drainage spine falls BELOW the pavement edge value
    (it delivers drainage between the two pavements)."""
    monkeypatch.setenv("O4_OPEN_FRONTAGE_SPINE", "1")
    layout, pav = _corridor_layout(gap_width_m=60.0)
    emit_gap_fill_spines(layout, None, 0, 0)
    spines = getattr(layout, "gap_spines", None)
    assert spines
    pts_ll, vals = spines[-1]
    # Deep-interior stations (away from the >=2 m end hold) drain down.
    assert min(vals) < EDGE_ALT


def test_open_corridor_over_width_cap_skips(monkeypatch):
    """A gap wider than 2*OPEN_FRONTAGE_CLOSE_M (= GAP_FILL_MAX_WIDTH_M)
    is never bridged by the morphological closing, so no corridor is
    detected and nothing emits — the wide middle stays with the corridor
    band / daylight law."""
    monkeypatch.setenv("O4_OPEN_FRONTAGE_SPINE", "1")
    layout, pav = _corridor_layout(gap_width_m=200.0)
    emit_gap_fill_spines(layout, None, 0, 0)
    assert _open_faces(layout) == []


def test_open_corridor_gate_off_is_noop():
    """Gate OFF (env unset): the pilot emits nothing — no open-frontage
    face, and the two parallel runways leave the layout with only their
    own two shapes (no enclosed gap exists, so gap-fill is also a no-op)."""
    layout, pav = _corridor_layout(gap_width_m=60.0)
    before = list(layout.shapes)
    emit_gap_fill_spines(layout, None, 0, 0)
    assert _open_faces(layout) == []
    assert layout.shapes == before
    assert not getattr(layout, "gap_spines", None)


def test_concave_notch_of_one_shape_is_not_a_corridor(monkeypatch):
    """A concave notch faced by a SINGLE pavement shape is not a
    between-pavement corridor (needs >= 2 distinct facing shapes) — the
    pilot skips it."""
    monkeypatch.setenv("O4_OPEN_FRONTAGE_SPINE", "1")
    # One U-shaped pavement (a single ring with a concave bay) + a far
    # second shape so the airside count >= 2 but only ONE faces the bay.
    u_ring = Polygon([
        (0.0, 0.0), (300.0, 0.0), (300.0, 200.0), (200.0, 200.0),
        (200.0, 60.0), (100.0, 60.0), (100.0, 200.0), (0.0, 200.0)])
    u = BuiltShape(polygon=u_ring, role=ROLE_RUNWAY,
                   node_altitudes=[EDGE_ALT] * len(u_ring.exterior.coords))
    far = _rect(2000.0, 2000.0, 2100.0, 2100.0, ROLE_RUNWAY)
    layout = _FakeLayout([u, far])
    emit_gap_fill_spines(layout, None, 0, 0)
    assert _open_faces(layout) == []


# ══════════════════════════════════════════════════════════════════════
# R19-2 — AN ENCLOSED HOLE IS SUBDIVIDED BEFORE IT IS REFUSED ON WIDTH
# ══════════════════════════════════════════════════════════════════════
#
# HECA's 22,483 m² enclosed airside hole gets no fill: its min-rect short
# side is 188.5 m, 8 % over ``GAP_FILL_MAX_WIDTH_M``.  But the hole is
# not one wide field — the groundside/service surfaces standing in it
# already divide it into pockets, every one of them far under the cap.
# Those shapes bound the ground the way pavement does (the same argument
# ``_parent_residual_faces`` makes for pads and skirts), so an ENCLOSED
# hole is subdivided by them and each residual face takes the SAME width
# test.  The cap itself never moves: a blanket raise would take the
# airport's 3.40 km² infield with it.

def _groundside_strip(x0, y0, x1, y1):
    from auto_patch.layout import ROLE_GROUNDSIDE_PAVEMENT
    poly = Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return BuiltShape(polygon=poly, role=ROLE_GROUNDSIDE_PAVEMENT,
                      ref="lot",
                      node_altitudes=[EDGE_ALT - 1.0]
                      * len(poly.exterior.coords))


def _wide_hole_with_subdivider(strip_y0=120.0, strip_y1=140.0,
                               gap_half_width_m=100.0):
    """A frame whose hole is WIDER than the cap (2 × half-width), with a
    groundside lot spanning it — the HECA geometry in miniature."""
    layout, pav = _frame_layout(gap_half_width_m=gap_half_width_m)
    layout.shapes.append(_groundside_strip(30.0, strip_y0, 1270.0,
                                           strip_y1))
    return layout, pav


def test_a_wide_enclosed_hole_is_subdivided_by_its_groundside():
    """The whole hole is 200 m across (over the 175 m cap); split by the
    lot it is two ~90 m pockets, and those are gradeable ground."""
    layout, _ = _wide_hole_with_subdivider()
    n = emit_gap_fill_spines(layout, None, 0, 0)
    assert n > 0, (
        "the hole was refused whole — the pockets its groundside "
        "divides it into are far under the width cap")
    faces = _faces(layout)
    assert faces
    lot = next(s for s in layout.shapes if (s.ref or "") == "lot")
    for f in faces:
        assert f.polygon.intersection(lot.polygon).area <= 1.0, (
            "a residual face was graded OVER the groundside that "
            "subdivides it — the subdivider is not gradeable ground")


def test_the_width_cap_never_rises():
    """The control that keeps this from being a cap raise: subdivide a
    hole whose PARTS are still over the cap and nothing emits."""
    layout, _ = _wide_hole_with_subdivider(
        strip_y0=440.0, strip_y1=460.0, gap_half_width_m=250.0)
    assert emit_gap_fill_spines(layout, None, 0, 0) == 0
    assert _faces(layout) == []


def test_one_oversize_pocket_abandons_the_whole_subdivision():
    """THE GUARD, made observable.  A hole that splits into one pocket
    UNDER the cap and one OVER it is left exactly as it was — veto
    standing, nothing emitted.

    Why all-or-nothing: HECA's 3.40 km² infield is vetoed by a
    service_junction too, and handing its oversize parts to the width
    skip would pass them to the pocket-collar rings, which stand the
    adjacent-ground bands down over the whole region (150,438 m² of
    Annex 14 §3.4.11-13 graded strip, measured — see
    ``_enclave_treatable``).  A region is subdivided only when the
    subdivision answers for ALL of it."""
    layout, _ = _wide_hole_with_subdivider(
        strip_y0=120.0, strip_y1=140.0, gap_half_width_m=200.0)
    assert emit_gap_fill_spines(layout, None, 0, 0) == 0, (
        "the 90 m pocket was graded while its 290 m sibling was handed "
        "to the width skip — the subdivision must answer for the whole "
        "hole or not run")
    assert _faces(layout) == []


def test_a_non_subdivider_blocker_keeps_the_veto():
    """The deferral is for the hole's OWN subdividers only.  One tunnel
    ramp inside — a law-cut hole in the ground with its own profile, not
    interior ground the gap law may read (R6, OTHH S6) — and the veto
    stands whatever else is in there."""
    from auto_patch.layout import ROLE_TUNNEL_RAMP
    layout, _ = _wide_hole_with_subdivider()
    ramp = Polygon([(400.0, 60.0), (500.0, 60.0), (500.0, 100.0),
                    (400.0, 100.0)])
    layout.shapes.append(BuiltShape(
        polygon=ramp, role=ROLE_TUNNEL_RAMP, ref="ramp",
        node_altitudes=[EDGE_ALT - 6.0] * len(ramp.exterior.coords)))
    assert emit_gap_fill_spines(layout, None, 0, 0) == 0
    assert _faces(layout) == []


# ══════════════════════════════════════════════════════════════════════
# RULING 3 (Fable 2026-08-12b) — EXCAVATION-RIM POCKETS
# ══════════════════════════════════════════════════════════════════════
#
# "A coverage hole whose boundary is >= 75 % graded features (apron /
# roads / junctions / groundside pavement / pads) is ENCLOSED for
# gap-fill purposes even with an open segment."
#
# The site: HECA's knoll at 30.1136676,31.4086362 — an apron excavated
# ~13 m below natural grade, its rim pocket bounded by apron E/S,
# groundside W and a service road/junction + building pad N, OPEN to the
# SW.  Before this law it was not a candidate AT ALL (no `[gap-fill]
# candidate` line within 40 m of it in either measured arm), because it
# is not an interior ring of the airside union.
#
# The fixture is that shape at fixture scale: a U of graded features
# around a pocket, open on ONE side.

from auto_patch.layout import (                       # noqa: E402
    ROLE_APRON, ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD,
)


def _rim_pocket_layout(open_side_m=40.0, pocket=140.0, with_west=True):
    """A pocket of ``pocket`` m square with graded features on its N, E
    and (optionally) W sides, open to the south.

    ``open_side_m`` is how much of the south side is left open: the rest
    is closed by an apron tongue, so the graded fraction is tunable.
    ``with_west=False`` drops the west arm — the ~50 % rim control.
    """
    shapes = [
        # NORTH — a service road along the whole top.
        _rect(-40.0, pocket, pocket + 40.0, pocket + 30.0,
              ROLE_SERVICE_ROAD),
        # EAST — the excavated apron.
        _rect(pocket, -40.0, pocket + 40.0, pocket + 30.0, ROLE_APRON),
        # SOUTH — an apron tongue closing all but ``open_side_m``.
        _rect(open_side_m, -40.0, pocket, 0.0, ROLE_APRON),
    ]
    if with_west:
        shapes.append(_rect(-40.0, -40.0, 0.0, pocket + 30.0,
                            ROLE_GROUNDSIDE_PAVEMENT))
    return _FakeLayout(shapes), list(shapes)


def test_an_excavation_rim_pocket_joins_the_graded_domain(monkeypatch):
    """>= 75 % graded rim with ONE open segment: the pocket is a gap-fill
    candidate and grades, boundary verbatim + one drainage spine."""
    monkeypatch.setattr(GF, "GAP_FILL_RIM_POCKETS_ENABLED", True)
    layout, pav = _rim_pocket_layout()
    n = emit_gap_fill_spines(layout, None, 0, 0)
    faces = _faces(layout)
    assert n == 1 and len(faces) == 1, (
        "the rim pocket was not admitted — before ruling 3 it was never "
        "even a candidate")
    # CHAIN IDENTITY: every face vertex is either a VERBATIM bounding-
    # feature ring vertex or an exact ON-EDGE point of one (the corner
    # where two bounding features meet is a T-vertex of both — the
    # survivable class; the enclosed path calls it a union-divergence
    # point).  What must never appear is a free-floating minted vertex —
    # the near-parallel lens Ruppert refinement explodes on.
    pav_keys = _pavement_keys(pav)
    exteriors = [s.polygon.exterior for s in pav]
    for x, y in list(faces[0].polygon.exterior.coords)[:-1]:
        if _key(x, y) in pav_keys:
            continue
        assert min(e.distance(_pt(x, y)) for e in exteriors) <= 1e-6, (
            f"rim-pocket face vertex ({x:.2f},{y:.2f}) is neither a "
            f"feature ring vertex nor on a feature edge")
    assert len(faces[0].node_altitudes) == len(
        faces[0].polygon.exterior.coords)
    spines = getattr(layout, "gap_spines", None)
    assert spines and len(spines) == 1


def test_a_half_open_pocket_is_left_to_the_band_law(monkeypatch):
    """THE CONTROL the ruling names: drop the west arm and the rim falls
    to ~50 % graded — open terrain the corridor-band / daylight law owns.
    Nothing is emitted and the layout is untouched."""
    monkeypatch.setattr(GF, "GAP_FILL_RIM_POCKETS_ENABLED", True)
    layout, _ = _rim_pocket_layout(with_west=False)
    before = list(layout.shapes)
    assert emit_gap_fill_spines(layout, None, 0, 0) == 0
    assert _faces(layout) == []
    assert layout.shapes == before


def test_a_through_channel_is_not_a_rim_pocket(monkeypatch):
    """SCOPE, measured against the open-frontage pilot: two facing
    pavements with a channel open at BOTH ends read >= 75 % graded rim
    too, but they are the corridor law's subject and its gate
    (``O4_OPEN_FRONTAGE_SPINE``) is default-OFF pending the owner's
    in-sim review.  A rim pocket is a RECESS — exactly ONE open run — so
    the corridor stays with its own law and this one cannot turn it on
    through the back door."""
    monkeypatch.setattr(GF, "GAP_FILL_RIM_POCKETS_ENABLED", True)
    layout, _ = _corridor_layout(gap_width_m=60.0)
    before = list(layout.shapes)
    assert emit_gap_fill_spines(layout, None, 0, 0) == 0
    assert _faces(layout) == []
    assert layout.shapes == before


def test_the_rim_pocket_default_state_is_a_noop():
    """THE DEFAULT STATE (ruling 2026-08-12b, after the HECA closing
    read): the gate ships OFF, so a rim pocket is byte-identical to the
    pre-ruling behaviour with no env set at all.

    HECA is why: at the post-solve-only default the arm minted 1,330 new
    airside within_shape rows of which 1,238 sit OFF-FACE (median 63 m,
    worst 140-207 m out at up to 11.31 m apron|apron) -- a third channel
    moving airside pavement, ~30x the OTHH absorption class the
    post-solve-only posture closed.  The detector, the width law and that
    posture stay landed and twinned; the staged-solve round owns the
    attribution and the re-enable."""
    assert GF.GAP_FILL_RIM_POCKETS_ENABLED is False, (
        "the rim-pocket gate must ship OFF")
    layout, _ = _rim_pocket_layout()
    before = list(layout.shapes)
    assert emit_gap_fill_spines(layout, None, 0, 0) == 0
    assert layout.shapes == before


def test_every_gap_pass_sees_the_same_candidates(monkeypatch):
    """THREE-PASS PARITY (the requirement the lane identified and the
    lead accepted as the work).  The pre-solve construction, the spine
    emitter and the pit floor must all read ONE candidate list — a region
    one pass grades and another does not know about is how a spine gets
    built with no emitter, or an emitter with no pre-solve spine.

    Asserted structurally, on the source: all three call the shared
    ``_gap_candidate_polys``, and none reaches past it to the
    enclosed-only detector."""
    import inspect
    for fn in (GF.construct_gap_fill_presolve, GF.emit_gap_fill_spines,
               GF.emit_gap_interior_floor):
        src = inspect.getsource(fn)
        assert "_gap_candidate_polys(layout, airside)" in src, (
            f"{fn.__name__} does not read the shared candidate list")
        assert "_gap_detection_polys(layout, airside)" not in src, (
            f"{fn.__name__} still reads the enclosed-only detector — the "
            f"three passes would disagree about the rim pockets")


def test_the_absorption_gate_is_retired_and_its_removal_is_inert():
    """THE GATE RETIREMENT (owner ruling 2026-08-13, RULINGS "OTHH -639
    ADJUDICATED"; S3 dossier §6) AND ITS INERTNESS TWIN.

    ``O4_RIM_PRESOLVE_ABSORB`` withheld rim-pocket spine vertices from
    the one solve.  It never ran in production — pockets ship OFF, so
    ``_rim_pocket_polys`` returns [] and ``rim_ids`` is empty — and
    which constructs a stage may move is the STAGE TAG's job now, never
    a per-construct flag.

    Two halves, and the second is the twin the removal owes: the symbol
    is GONE from both modules, and with pockets OFF the retired branch's
    subject does not exist, so the construction is unchanged."""
    import inspect
    from auto_patch import config as _cfg
    assert not hasattr(_cfg, "RIM_PRESOLVE_ABSORB"), (
        "the retired absorption gate is still defined in config")
    assert not hasattr(GF, "RIM_PRESOLVE_ABSORB"), (
        "gap_fill still imports the retired absorption gate")
    _code = "\n".join(
        ln for ln in inspect.getsource(
            GF.construct_gap_fill_presolve).splitlines()
        if not ln.lstrip().startswith("#"))     # the note may name it
    assert "RIM_PRESOLVE_ABSORB" not in _code, (
        "the retired gate's branch is still in the pre-solve construction")
    # INERT WHILE POCKETS ARE OFF: the branch's whole subject (``rim_ids``)
    # is empty at the shipped default, so nothing it used to do happens.
    assert GF.GAP_FILL_RIM_POCKETS_ENABLED is False, (
        "the rim-pocket gate must ship OFF")
    layout, _ = _rim_pocket_layout()
    airside = GF._airside_shapes(layout)
    assert GF._rim_pocket_polys(layout, airside) == []
    _cands, rim_ids = GF._gap_candidate_polys(layout, airside)
    assert rim_ids == set(), (
        "pockets OFF must leave the retired branch no subject at all")
    assert GF.construct_gap_fill_presolve(layout) == 0
    assert not getattr(layout, "gap_fill_presolve", None)
    assert emit_gap_fill_spines(layout, None, 0, 0) == 0


def test_a_rim_pocket_spine_is_constructed_when_pockets_are_on(monkeypatch):
    """With the gate retired, a rim pocket enters the pre-solve store
    like any other gap — admission to a solve STAGE is decided by the
    stage tag (``solve_stage``), not by dropping the construct.  Emission
    is unaffected either way (S3 dossier §6.3)."""
    monkeypatch.setattr(GF, "GAP_FILL_RIM_POCKETS_ENABLED", True)
    layout, _ = _rim_pocket_layout()
    assert GF.construct_gap_fill_presolve(layout) == 1
    assert emit_gap_fill_spines(layout, None, 0, 0) == 1
    assert len(_faces(layout)) == 1


# ══════════════════════════════════════════════════════════════════════
# THE ENCLOSURE HOST'S STAGE (staged-solve lane S1d)
# ══════════════════════════════════════════════════════════════════════
#
# S4 measured that flipping ``O4_GAP_FILL_RIM_POCKETS=1`` makes rim-pocket
# drainage spines WRITE AIRSIDE elevations: the spine constraint was
# stamped ``STAGE_A`` unconditionally, on the (true, but only for the
# ENCLOSED path) reasoning that a gap is an interior ring of the airside
# union.  A RIM POCKET is admitted precisely because it is NOT — its rim
# may be wholly groundside — so the stage is now decided per candidate by
# ``gap_fill._gap_host_stage`` and carried on the pre-solve entry.
#
# The rim geometry is IDENTICAL across these fixtures and only the ROLES
# move, so nothing but the host verdict can explain a difference.

from auto_patch.solve_stage import (                  # noqa: E402
    STAGE_A as _ST_A, STAGE_B as _ST_B)

#: Two aprons far enough from the pocket (and from each other) that they
#: bound nothing and close into no corridor — the ``len(airside) >= 2``
#: precondition of ``construct_gap_fill_presolve``, and nothing else.
#: ``OPEN_FRONTAGE_CLOSE_M`` is 87.5 m; these clear 2x that with room.
_FAR_AIRSIDE_BOXES = ((1000.0, 0.0, 1100.0, 100.0),
                      (1500.0, 0.0, 1600.0, 100.0))


def _rim_pocket_layout_roles(north, east, south, west, *, pocket=140.0,
                             open_side_m=40.0, far_airside=True):
    """``_rim_pocket_layout``'s geometry with the four rim arms' ROLES
    given explicitly (plus, by default, the two far-away aprons that
    satisfy the construction's airside-count precondition without
    touching the pocket)."""
    shapes = [
        _rect(-40.0, pocket, pocket + 40.0, pocket + 30.0, north),   # N
        _rect(pocket, -40.0, pocket + 40.0, pocket + 30.0, east),    # E
        _rect(open_side_m, -40.0, pocket, 0.0, south),               # S
        _rect(-40.0, -40.0, 0.0, pocket + 30.0, west),               # W
    ]
    if far_airside:
        shapes += [_rect(*b, ROLE_APRON) for b in _FAR_AIRSIDE_BOXES]
    return _FakeLayout(shapes), list(shapes)


def test_a_wholly_groundside_rim_pocket_is_hosted_by_stage_b(monkeypatch):
    """T1.  No airside arm on the rim ⇒ the enclosure is groundside and
    its drainage spine is a stage-B variable.  This is the S4 write: at
    ``STAGE_A`` these spine nodes are free variables of the AIRSIDE pass,
    which is groundside authoring airside."""
    monkeypatch.setattr(GF, "GAP_FILL_RIM_POCKETS_ENABLED", True)
    layout, _ = _rim_pocket_layout_roles(
        ROLE_SERVICE_ROAD, ROLE_GROUNDSIDE_PAVEMENT,
        ROLE_SERVICE_ROAD, ROLE_GROUNDSIDE_PAVEMENT)
    assert GF.construct_gap_fill_presolve(layout) == 1
    assert layout.gap_fill_presolve[0]["host_stage"] == _ST_B


def test_an_airside_rim_arm_is_read_not_written_still_stage_b(monkeypatch):
    """T2, THE ASSERTION THIS TWIN NOW MAKES BY RULING.

    RULINGS 2026-08-14 "RIM-POCKET SPINES ARE UNCONDITIONALLY STAGE B"
    (Fable, resolving S1d's stop) REVERSES this test's predecessor,
    ``test_one_airside_arm_makes_the_rim_pocket_stage_a``, which asserted
    that an apron on the rim hands the enclosure to stage A.  The ruling:
    that branch repeated the false-enclosure premise one level up —
    airside-is-king means airside is never PULLED, not that everything
    touching airside becomes an airside VARIABLE.  A rim-pocket spine
    RECEIVES; an airside rim arm is an IMMUTABLE BOUNDARY it READS (the
    corridor-mouth weld posture).  The intent changed by ruling, so the
    assertion changed with it; the fixture did not move.

    The shipped ``_rim_pocket_layout`` has an apron on the E and S rim —
    the exact geometry the predecessor called stage A — and it is stage
    B here.  T1 (wholly groundside rim) asserts the same verdict, so the
    pair also proves what the ruling claims structurally: rim composition
    can no longer reach the verdict at all."""
    monkeypatch.setattr(GF, "GAP_FILL_RIM_POCKETS_ENABLED", True)
    layout, _ = _rim_pocket_layout()
    assert GF.construct_gap_fill_presolve(layout) == 1
    assert layout.gap_fill_presolve[0]["host_stage"] == _ST_B


def test_an_all_airside_rim_pocket_is_stage_b_too(monkeypatch):
    """T2b, THE RULING'S LETTER AT ITS LIMIT CASE: a pocket every one of
    whose rim arms is lawful airside is STILL a rim pocket, so it is
    still stage B — the ruling admits no "genuinely airside-enclosed"
    exception, because such a region is not an interior ring of the
    airside union (``_gap_detection_polys`` would have found it and it
    would never have reached the rim-pocket path).  Its spine reads four
    immutable airside boundaries and writes none of them.

    The reporting helper is asserted beside the verdict, on the SAME
    candidate polygon the construction stages, so the census line a build
    prints cannot drift from the geometry it describes.  It also records
    why this class is near-empty by construction: the pocket is admitted
    at all only because it is NOT closed (the open south segment lies on
    no shape's exterior), so ``n_air < n_mid`` even here — a rim that
    really did close all the way round would have been an interior ring
    of the airside union and never have reached the rim-pocket path."""
    monkeypatch.setattr(GF, "GAP_FILL_RIM_POCKETS_ENABLED", True)
    layout, _ = _rim_pocket_layout_roles(
        ROLE_APRON, ROLE_APRON, ROLE_APRON, ROLE_APRON, far_airside=False)
    airside = GF._airside_shapes(layout)
    cands, rim_ids = GF._gap_candidate_polys(layout, airside)
    pockets = [p for p in cands if id(p) in rim_ids]
    assert len(pockets) == 1, "the all-airside rim is still a POCKET"
    n_mid, n_air = GF._rim_airside_arm_mids(airside, pockets[0])
    assert n_mid > 0 and 0 < n_air < n_mid
    assert GF.construct_gap_fill_presolve(layout) == 1
    assert layout.gap_fill_presolve[0]["host_stage"] == _ST_B


def test_a_pad_on_the_rim_does_not_make_the_host_airside(monkeypatch):
    """T3, the ``ROLE_BUILDING`` WRINKLE, in lockstep with the generic
    fold it must NOT use.

    ``solve_stage.stage_of_roles`` returns STAGE_A for
    ``{service_road, building}`` because ``ROLE_BUILDING`` is not in
    ``layout.GROUNDSIDE_ROLES``.  For a NODE that is the conservative
    side (airside wins a shared seat).  For an ENCLOSURE HOST it is the
    wrong side — a pad bounds ground, it does not make the ground
    airside — so ``_gap_host_stage`` tests IDENTITY against the airside
    list instead and never names the role at all.  Both halves are
    asserted here so the test documents WHY."""
    monkeypatch.setattr(GF, "GAP_FILL_RIM_POCKETS_ENABLED", True)
    layout, _ = _rim_pocket_layout_roles(
        ROLE_SERVICE_ROAD, ROLE_SERVICE_ROAD, ROLE_SERVICE_ROAD,
        ROLE_BUILDING)
    assert GF.construct_gap_fill_presolve(layout) == 1
    assert layout.gap_fill_presolve[0]["host_stage"] == _ST_B
    from auto_patch import solve_stage
    assert solve_stage.stage_of_roles(
        {ROLE_SERVICE_ROAD, ROLE_BUILDING}) == solve_stage.STAGE_A, (
        "the generic node fold is what this host rule must not be")


def test_at_the_shipped_default_every_gap_host_is_airside():
    """T4, INERTNESS.  Rim pockets ship OFF, so the only candidates are
    the enclosed interior rings of the airside union — airside-hosted by
    construction, with no geometry test — and the tag is STAGE_A
    everywhere, exactly as before S1d.  The groundside-rim geometry
    produces no candidate at all."""
    assert GF.GAP_FILL_RIM_POCKETS_ENABLED is False, (
        "the rim-pocket gate must ship OFF")
    layout, _ = _frame_layout(30.0)
    assert GF.construct_gap_fill_presolve(layout) >= 1
    assert [e["host_stage"] for e in layout.gap_fill_presolve] == \
        [_ST_A] * len(layout.gap_fill_presolve)
    gs, _ = _rim_pocket_layout_roles(
        ROLE_SERVICE_ROAD, ROLE_GROUNDSIDE_PAVEMENT,
        ROLE_SERVICE_ROAD, ROLE_GROUNDSIDE_PAVEMENT)
    assert GF.construct_gap_fill_presolve(gs) == 0
