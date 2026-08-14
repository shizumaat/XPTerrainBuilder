"""Terrain-side BUILDING PADS — emitted IN-RUN from the object pad frame
(docs/specs/per-cluster-object-seating-spec.md §5.1, §5.4, §5.5;
chartered by docs/specs/object-reseat-threshold-spec.md §2.3; mechanism
per RULINGS "OBJECT PADS: EMISSION-TIME RELATIVE", owner 2026-08-14).

WHAT THIS IS.  A DSF object renders its ``y = 0`` plane at the ground
under its placement anchor plus its authored offsets, so terrain that is
supposed to MEET a building base has to know what elevation the surface
will carry there.  This module answers that from THE SAME BUILD: the
mesh-free pad frame (``object_frame``, built once per build behind the
pristine-input cache) supplies the pack evidence — parts, contact bands,
``base_y``, render datums — and the emitted patch's own evaluated ground
(``patch_ground.PatchGroundField``, read post-solve) supplies the
elevation.  Pads are then emitted as ``object_pad`` terrain at the
resulting target.

WHAT THIS IS NOT, ANY MORE.  It does not read
``Patches/<tile>/o4_object_foot_pads.json``.  That read-back made a pad
the product of the PREVIOUS build's mesh — the cross-build convergence
the owner retired ("no convergence and no multi-build anything"), and
the measured ratchet (object_pad 689 → 723 → 736 over three identical
builds).  The sidecar survives as the y-bake's WRITE-ONLY audit trail;
nothing in the terrain path consumes it.

THE PAD LAW is NOT here.  Every scalar — target admissibility, the
pull-toward-pavement, the open-side blend — lives in ``grade_law`` and is
imported by BOTH this emitter and ``verification.check_object_pads``
(ruling R5, the one-solve doctrine).  This module owns geometry and
bookkeeping only.

POST-SOLVE EMISSION, the skirt / adjacent-ground / OLS idiom (§5.4).
Pads are never admitted to the solver: they are off-pavement terrain
whose values are pure law, so they need only CLIP and WELD against the
already-solved surfaces.  Precedence, verbatim from §5.4:

    pavement  >  existing terrain features  >  pads  >  raw DEM

Clause 2 of the PAD LAW (§5.1, the R2 hard clause — "they must not deform
the graded pavement") is executed by ``object_footprints.
clip_pad_ring_against_pavement``, the single function the spec names for
it; the feature clip and the pad↔pad clip follow in the same pass.  A
pavement vertex is never contributed to, moved or re-valued, and the
emitter proves it on every run by digesting every pavement shape before
and after itself (``PAVEMENT_DIGEST_FINDING``).

THE SHAPE OF A PAD.  A request records one ring PER CONNECTED COMPONENT
of its contact parts' hulls, each dilated by
``DSF_OBJECT_FOOT_PAD_MARGIN_M`` (``object_footprints.foot_pad_rings``,
object-reseat-threshold-spec §2.5 — the single group hull it replaced
spanned the water and parking lots between spread-out parts).  Each ring
is resolved into its own spec here and emitted on its own.

CORE ONLY — WELD OR GAP (owner 2026-08-13, "TRANSITION MACHINERY
RETIRES").  A pad used to emit two shapes: the eroded CORE at the target,
and a BLEND annulus ramping from it to raw DEM (or welding to pavement).
The annulus is a feather, and feathers retire as a class — the patch↔DEM
transition is Ortho4XP's own mesh drape.  So one ring now emits ONE
shape, the core, and the annulus it used to fill becomes exactly what the
ruling calls for: an ambient-DEM GAP the mesh drapes.  The erosion width
is unchanged (``grade_law.object_pad_blend_width_m`` on the ORIGINAL
ring), because it is what makes the core the contact hull; only the
filling of it is gone.  Nothing the pad emits touches another patch
surface, so the weld half of the law has nothing to weld: the clip
against pavement and features runs first and the erosion pulls the core
off every remaining edge.

``REF_PAD_CORE`` still tags the shape (``object_pad:<n>``), one role
literal, as the spec authorises.

DETERMINISM (the ruling's own acceptance).  Every input is this build's:
the frame is pack data, the ground is this build's solved patch.  No
sidecar is read, no record is persisted for the next build to re-emit,
and there is nothing left for a pad to converge to.

RECORDS.  ``emit_object_pads`` still stashes what it emitted on the
layout — ``object_pad_records`` — as the audit ``verification.
check_object_pads`` reads and the build log counts.  They are a report of
one build, never an input to the next; nothing merges them to disk.
"""

from __future__ import annotations

import hashlib
import json
import math
import os

from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

from . import config as _config
from .clearance import _GEOM_EXC, _open_coords
from .emit_decimate import Z_TOL_BOUNDARY_M, decimate_shape_group
from .grade_law import (
    object_pad_admissible,
    object_pad_blend_width_m,
    object_pad_pull_shortfall_m,
    object_pad_pull_toward_pavement,
    object_pad_relief_m,
)
from .layout import (
    ROLE_OBJECT_PAD,
    WELD_DONOR_ROLES,
    BuiltShape,
    PavementLayout,
)

#: The sidecar section this module owns.  ``post_mesh`` refreshes the
#: REQUESTS every rebake and carries this section across untouched.
EMITTED_SECTION_KEY = "emitted"

#: ``ref`` prefixes distinguishing the two shapes of one pad.  Refs, not
#: roles: ``object_pad`` is the one new role literal the spec authorises.
REF_PAD_CORE = "object_pad"
REF_PAD_BLEND = "object_pad_blend"

#: Clip products below this are slivers, not pads (the ``ols.py``
#: ``_MIN_PIECE_AREA_M2`` convention at the pad's much smaller scale).
_MIN_PIECE_AREA_M2 = 0.5

#: A vertex within this of a weld-donor shape's exterior is ON it and
#: adopts its value — ``adjacent_ground._STATIC_WELD_TOL_M`` verbatim, so
#: the two welds cannot disagree about what "coincident" means.
_WELD_TOL_M = 0.02

#: A blend piece with no core of its own whose every vertex already sits
#: within this of raw DEM is a no-op plate: emitting it would add
#: triangles that reproduce the terrain the mesh already has.  This is the
#: brief's materiality floor (0.01 m), used as a floor and never iterated.
_MATERIALITY_M = 0.01

#: THE EXCEPTION SET THIS MODULE GUARDS WITH.  ``clearance._GEOM_EXC``
#: (ValueError / GEOSException / TopologicalError) is the shapely-domain
#: set every emitter uses, but shapely also raises TypeError from the
#: numpy-dispatch layer when a predicate hands a function a geometry type
#: it does not accept — and that one is NOT a domain error, it is an
#: unhandled shape of input.  It aborted an OTHH build on 2026-08-09
#: (a clip that shared both a run and a corner with a pavement ring
#: returned a GeometryCollection).  A pad emitter must degrade to a
#: reported refusal, never to a dead build, so the guards here cover the
#: whole family.
_PAD_EXC = _GEOM_EXC + (TypeError, AttributeError, IndexError,
                        KeyError, ZeroDivisionError)

#: Finding kind emitted when a pavement shape changed across the emitter.
PAVEMENT_DIGEST_FINDING = "pad_deformed_pavement"


# ──────────────────────────────────────────────────────────────────────
# The sidecar
# ──────────────────────────────────────────────────────────────────────

def sidecar_path(patch_dir: str) -> str:
    """The tile's pad sidecar path inside ``patch_dir``.  The filename
    comes from ``post_mesh`` (one source; the name is wire-adjacent).

    NOTHING IN THE BUILD PATH READS THIS FILE any more (R3 step 4): the
    sidecar is the y-bake's write-only audit trail, and these readers
    exist for the offline instruments (``tools/object_pad_anchor_report``)
    and their twins."""
    from .post_mesh import OBJECT_FOOT_PAD_SIDECAR_FILENAME

    return os.path.join(patch_dir, OBJECT_FOOT_PAD_SIDECAR_FILENAME)


def load_sidecar(path: str):
    """The parsed sidecar, or ``None`` when absent/unreadable.

    Parsing is version-agnostic; USING it is not (see
    :func:`sidecar_is_current`).  A malformed file is treated as ABSENT —
    a pad consumer must never fail a build over its own audit trail."""
    try:
        with open(path) as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def sidecar_version(payload) -> int:
    """The sidecar's declared version, 0 when absent or unreadable."""
    try:
        return int((payload or {}).get("version") or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def sidecar_is_current(payload) -> bool:
    """Whether this sidecar's GEOMETRY was produced under the ring law
    this build implements (object-reseat-threshold-spec §2.5).

    Version 3 and below carry one convex-hull ring per residual group —
    the retired law, whose pads spanned the water and parking lots
    between spread-out parts; version 4 additionally carries the
    plan-box fallback rings the round-4 R1 law retired (up to 224,146 m2
    apiece).  Such a corpus is REFUSED wholesale rather
    than consumed: its requests are discarded, its ``emitted`` records
    expire, and the next rebake re-derives the requests under the current
    law (§5.2's convergence loop is exactly the mechanism that repairs
    it).  This is a floor, not an equality: a file written by a NEWER
    producer alongside this reader still carries at least these rings."""
    return sidecar_version(payload) >= _current_sidecar_version()


def _current_sidecar_version() -> int:
    from .post_mesh import OBJECT_FOOT_PAD_SIDECAR_VERSION

    return int(OBJECT_FOOT_PAD_SIDECAR_VERSION)


def law_digest() -> str:
    """Fingerprint of the PAD LAW as this build reads it.

    Every constant that can move a pad's geometry or its admissibility is
    in here, so flipping the gate or re-tuning a cap makes every stored
    record stale in one comparison (§5.2 staleness cause 1) instead of
    silently re-emitting pads the current law would not have produced."""
    parts = (
        "object_pad_law_v1",
        # The sidecar version IS part of the law: it names which ring
        # geometry produced a record (§2.5's hull → per-part union).
        f"sidecar={_current_sidecar_version()}",
        f"gate={int(bool(_config.DSF_OBJECT_OBJECT_PADS))}",
        f"relief={float(_config.DSF_OBJECT_PAD_MAX_RELIEF_M):.6f}",
        f"margin={float(_config.DSF_OBJECT_FOOT_PAD_MARGIN_M):.6f}",
        f"residual={float(_config.DSF_OBJECT_FOOT_PAD_RESIDUAL_M):.6f}",
        f"groundside={float(_config.GROUNDSIDE_MAX_GRADE):.6f}",
        # The retired plan-box fallback's surviving degenerate window
        # (round-4 spec R1): moving it changes which parts may raise a
        # request at all, which is admissibility.
        "planbox="
        f"{float(_config.DSF_OBJECT_PAD_PLAN_BOX_FALLBACK_MAX_M2):.6f}",
    )
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def seat_key(entry: dict) -> str:
    """The IDENTITY of the seat a pad serves — stable across builds and
    independent of the seat's VALUE.

    Two pad requests share a key iff they are the same foot / the same
    cluster of the same structure of the same resource at the same place
    — and, since §2.5, the same RING of that seat: one residual group's
    request now carries a ring per connected component of its parts, each
    of which is emitted, refused and remembered on its own.  The key is
    what lets a live request SUPERSEDE a stored record (§5.2 staleness
    cause 2); the fingerprint below is what says whether it moved."""
    return "|".join((
        str(entry.get("kind") or "foot"),
        str(entry.get("resource_path") or ""),
        str(entry.get("structure_index")),
        str(entry.get("cluster_id")),
        f"{float(entry.get('latitude') or 0.0):.9f}",
        f"{float(entry.get('longitude') or 0.0):.9f}",
        f"#{int(entry.get('ring_index') or 0)}",
    ))


def seat_fingerprint(entry: dict, digest: str | None = None) -> str:
    """Fingerprint of the SEAT that produced a pad: its identity plus the
    values that decide the pad's surface (the authored base and the
    ground elevation the seated base wants), plus the law digest.

    A rebake that moves the cluster's seat changes
    ``target_ground_metres`` and therefore this fingerprint, so the stored
    record is superseded rather than re-emitted at a stale height."""
    parts = (
        seat_key(entry),
        f"{float(entry.get('base_y') or 0.0):.4f}",
        f"{float(entry.get('target_ground_metres') or 0.0):.4f}",
        digest if digest is not None else law_digest(),
    )
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def specs_from_frames(frames, datum_ground_at, surface_ground_at, *,
                      icao: str = "", claim=None):
    """ONE airport's pad specs, derived IN-RUN from the pad frames.

    This replaces ``pads_for_airport`` — the sidecar read-back — with the
    ruling's emission-time derivation.  ``frames`` are the airport's
    ``object_frame.ObjectPadFrame``s (``post_mesh.pad_frames_from_worklist``
    in production); ``datum_ground_at`` is the emitted patch's own ground
    (the render datum's authority, per the ruling) and
    ``surface_ground_at`` is patch-or-DEM — the mesh's own rule, for the
    ground under a part.  See ``object_frame.pad_requests_from_frame``
    for why they are two.

    THE ARITHMETIC LIVES IN ``object_frame.pad_requests_from_frame``, not
    here: that function is the one place the rebake's ``seated=False``
    formula is spelled, so the emitter and the y-bake fallback cannot
    drift about what a request IS.  This function adds only what the
    request needs to be EMITTED and AUDITED — the seat identity, the
    fingerprint, the law digest — and the airport claim.

    THE CLAIM, unchanged in doctrine from the sidecar reader it replaces:
    a DSF cell can carry two airports' objects (measured on +25+051: all
    823 OTHH cluster requests recorded under OTBD), patches are
    per-airport, and airports do not share ground — so GEOMETRY decides
    which pads are this airport's.  ``claim(latitude, longitude) -> bool``;
    ``None`` claims everything, which is the unit tests' pure default.

    Returns ``(specs, findings)``.  ``findings`` are the frame's own —
    unhosted datums, unclaimed rings, and the self-covering requests step
    (5) routes to the y-bake — carried through so the pad verifier
    surfaces them beside the emitter's refusals.
    """
    from .config import (
        DSF_OBJECT_FOOT_PAD_MARGIN_M,
        DSF_OBJECT_NOBAKE_PAD_FLOOR_M,
        DSF_OBJECT_PAD_MAX_RELIEF_M,
    )
    from .object_frame import pad_requests_from_frame

    digest = law_digest()
    specs: list[dict] = []
    findings: list[tuple] = []
    seen: set[str] = set()
    for frame in frames or ():
        requests, frame_findings = pad_requests_from_frame(
            frame,
            datum_ground_at,
            surface_ground_at,
            residual_floor_m=float(DSF_OBJECT_NOBAKE_PAD_FLOOR_M),
            margin_metres=float(DSF_OBJECT_FOOT_PAD_MARGIN_M),
            maximum_relief_metres=float(DSF_OBJECT_PAD_MAX_RELIEF_M),
        )
        findings.extend(frame_findings)
        for request in requests:
            if claim is not None:
                try:
                    if not claim(float(request["latitude"]),
                                 float(request["longitude"])):
                        continue
                except (TypeError, ValueError):    # pragma: no cover
                    continue
            key = seat_key(request)
            if key in seen:
                # Two pools of one airport reaching the same seat is not
                # expected (pools partition the placements), so this is a
                # guard rather than a law — first spec wins, silently, the
                # way the sidecar reader's own dedup did.
                continue
            seen.add(key)
            spec = dict(request)
            spec["seat_key"] = key
            spec["fingerprint"] = seat_fingerprint(spec, digest)
            spec["law_digest"] = digest
            spec["source"] = "frame"
            specs.append(spec)
    specs.sort(key=lambda spec: spec["seat_key"])   # deterministic emission
    return specs, findings


# ──────────────────────────────────────────────────────────────────────
# Emission
# ──────────────────────────────────────────────────────────────────────

#: How far off its own built surfaces an airport still claims a pad.  The
#: worklist is per TILE and its entries are keyed by DSF attribution, so
#: geometry decides ownership (see ``specs_from_frames``); this is the
#: reach of that claim.  Generous against the airport's own extent (a
#: hangar apron outside the pavement hull is still the airport's) and an
#: order of magnitude under the separation between two airports that
#: share a tile (OTBD↔OTHH: ~4.4 km).
_CLAIM_MARGIN_M = 250.0


def _footprint_claim(layout: PavementLayout):
    """``claim(latitude, longitude) -> bool`` for THIS airport: is that
    point on ground this airport built?  The convex hull of every shape's
    bounding box, dilated by ``_CLAIM_MARGIN_M``.

    A layout with no shapes claims everything — an airport that built
    nothing cannot adjudicate ownership, and dropping pads on that basis
    would be a silent loss."""
    corners = []
    for s in layout.shapes:
        if s.polygon is None or s.polygon.is_empty:
            continue
        try:
            x0, y0, x1, y1 = s.polygon.bounds
        except (AttributeError, ValueError):       # pragma: no cover
            continue
        corners.extend(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
    if len(corners) < 3:
        return lambda _lat, _lon: True
    try:
        from shapely.geometry import MultiPoint

        hull = MultiPoint(corners).convex_hull.buffer(_CLAIM_MARGIN_M)
    except _PAD_EXC:                              # pragma: no cover
        return lambda _lat, _lon: True
    ll_to_m = layout.ll_to_m

    def claim(latitude: float, longitude: float) -> bool:
        try:
            x, y = ll_to_m(float(latitude), float(longitude))
            return bool(hull.covers(Point(x, y)))
        except _PAD_EXC:
            return False

    return claim


#: Cell size of the emitted-pad spatial hash.  Pad↔pad exclusivity is an
#: every-pad-against-every-earlier-pad question, and OTHH raises 733 of
#: them: a linear scan is ~10^6 geometry calls, a hash is a dict lookup.
_PAD_GRID_M = 128.0


def _pad_cells(bounds):
    x0, y0, x1, y1 = bounds
    for gx in range(int(math.floor(x0 / _PAD_GRID_M)),
                    int(math.floor(x1 / _PAD_GRID_M)) + 1):
        for gy in range(int(math.floor(y0 / _PAD_GRID_M)),
                        int(math.floor(y1 / _PAD_GRID_M)) + 1):
            yield (gx, gy)


def _pad_index_add(index: dict, polygon) -> None:
    """Register an emitted pad piece in the spatial hash."""
    try:
        bounds = polygon.bounds
    except (AttributeError, ValueError):           # pragma: no cover
        return
    for cell in _pad_cells(bounds):
        index.setdefault(cell, []).append(polygon)


def _pad_index_query(index: dict, bounds) -> list:
    """Every already-emitted pad piece whose cell the bounds reach, each
    once (a piece spanning several cells appears in each of them)."""
    if not index:
        return []
    out: list = []
    seen: set = set()
    for cell in _pad_cells(bounds):
        for polygon in index.get(cell, ()):
            if id(polygon) not in seen:
                seen.add(id(polygon))
                out.append(polygon)
    return out


def _pavement_shapes(layout: PavementLayout):
    """The GRADED PAVEMENT of §5.1 clause 2 — every shape whose role
    carries a within-shape grade cap.  Derived from the registry
    (``ROLE_GRADE_LIMITS``), never from a fresh list of role literals: a
    role added to the law joins the pad's clip automatically."""
    from .config import ROLE_GRADE_LIMITS

    return [s for s in layout.shapes
            if s.polygon is not None and not s.polygon.is_empty
            and ROLE_GRADE_LIMITS.get(s.role) is not None]


def _feature_shapes(layout: PavementLayout):
    """The TERRAIN FEATURES pads rank below (§5.4 precedence: skirt,
    bands, OLS cuts, bridge/tunnel plates, boundary) — the complement of
    the pavement set, minus pads themselves (pad↔pad exclusivity is
    handled by the running emitted set instead)."""
    from .config import ROLE_GRADE_LIMITS

    return [s for s in layout.shapes
            if s.polygon is not None and not s.polygon.is_empty
            and ROLE_GRADE_LIMITS.get(s.role) is None
            and s.role != ROLE_OBJECT_PAD]


def _specs_bounds(layout: PavementLayout, specs) -> tuple:
    """Bounding box in layout metres covering every pad this build may
    emit, dilated by the weld reach.  ``None`` when nothing is emitted."""
    ll_to_m = layout.ll_to_m
    x0 = y0 = float("inf")
    x1 = y1 = float("-inf")
    for spec in specs:
        for point in spec.get("ring_lonlat") or ():
            try:
                x, y = ll_to_m(float(point[1]), float(point[0]))
            except (TypeError, ValueError, IndexError):  # pragma: no cover
                continue
            x0, y0 = min(x0, x), min(y0, y)
            x1, y1 = max(x1, x), max(y1, y)
    if x0 > x1:
        return None
    pad = 1.0
    return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)


def _shapes_within(shapes, bounds):
    """The subset of ``shapes`` whose bbox meets ``bounds`` (all of them
    when ``bounds`` is None — an unknown reach watches everything)."""
    if bounds is None:
        return list(shapes)
    x0, y0, x1, y1 = bounds
    out = []
    for s in shapes:
        try:
            b = s.polygon.bounds
        except (AttributeError, ValueError):       # pragma: no cover
            continue
        if b[0] <= x1 and b[2] >= x0 and b[1] <= y1 and b[3] >= y0:
            out.append(s)
    return out


def _pavement_digest(shapes) -> str:
    """A digest over every pavement shape's geometry AND values — the
    runtime instrument for the R2 hard clause ("pavement shapes
    byte-identical to the pad-free emission", §5.5).  Taken at the
    emitter's entry and again at its exit, so any pavement a pad touched
    shows up as a finding on the build that did it rather than in a
    post-hoc diff nobody runs."""
    hasher = hashlib.sha1()
    for s in shapes:
        try:
            hasher.update(s.polygon.wkb)
        except (AttributeError, ValueError):       # pragma: no cover
            continue
        hasher.update(repr(s.node_altitudes).encode())
        hasher.update(repr(s.altitude).encode())
        hasher.update(repr((s.altitude_high, s.altitude_low)).encode())
    return hasher.hexdigest()


def _ring_reference(shape, cache: dict):
    """``(coords, alts)`` of a donor shape's exterior, memoised per shape.

    A donor apron ring can carry hundreds of vertices and every welded pad
    vertex asks it for a value; re-deriving the reference per query is the
    lazy-cache the band emitter's ``_static_edge_ref_cache`` exists to
    avoid.  ``(None, None)`` when the shape carries no values."""
    key = id(shape)
    hit = cache.get(key)
    if hit is not None:
        return hit
    from .verification import _shape_vertex_altitudes

    try:
        coords = _open_coords(shape.polygon)
    except _PAD_EXC:                              # pragma: no cover
        coords = []
    alts = _shape_vertex_altitudes(shape, len(coords)) if coords else None
    reference = (coords, alts) if (coords and alts) else (None, None)
    cache[key] = reference
    return reference


def _ring_edge_alt(shape, x: float, y: float, cache: dict):
    """The solved altitude of ``shape``'s exterior ring at (x, y), by
    interpolation along the ring — ``adjacent_ground``'s
    ``_ring_edge_reference`` semantics, kept local so the pad emitter has
    no import-time dependency on the band module."""
    coords, alts = _ring_reference(shape, cache)
    if not coords or len(coords) < 2 or not alts:
        return None
    best = None
    for i in range(len(coords)):
        ax, ay = coords[i]
        bx, by = coords[(i + 1) % len(coords)]
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        if seg2 <= 0.0:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / seg2))
        px, py = ax + t * dx, ay + t * dy
        d = math.hypot(x - px, y - py)
        value = alts[i] + t * (alts[(i + 1) % len(alts)] - alts[i])
        if best is None or d < best[0]:
            best = (d, value)
    return None if best is None else float(best[1])


class _WeldIndex:
    """Value donors for a pad's welded boundary rows.

    Scope is ``layout.WELD_DONOR_ROLES`` — THE single source for "who may
    donate a value to a soft terrain shape" (layout.py, user rulings
    2026-07-09/07-17).  Buildings, groundside lots and bridge plates are
    deliberately NOT donors: a pad meeting one of those keeps its own
    lawful value, because adopting a foreign authority corner is what
    minted the CYXY 9 m band tear."""

    def __init__(self, layout: PavementLayout):
        self.shapes = [s for s in layout.shapes
                       if s.role in WELD_DONOR_ROLES
                       and s.polygon is not None and not s.polygon.is_empty
                       and s.polygon.geom_type == "Polygon"]
        self.exteriors = [s.polygon.exterior for s in self.shapes]
        self._ref_cache: dict = {}
        try:
            self.tree = STRtree(self.exteriors) if self.exteriors else None
        except _PAD_EXC:                          # pragma: no cover
            self.tree = None

    def value_at(self, x: float, y: float):
        """The donor's solved value at (x, y) when the point lies ON a
        donor ring within ``_WELD_TOL_M``, else ``None``."""
        if self.tree is None:
            return None
        pt = Point(x, y)
        try:
            cand = self.tree.query_nearest(pt, max_distance=_WELD_TOL_M)
        except _PAD_EXC:                          # pragma: no cover
            return None
        cand = [int(i) for i in cand]
        if not cand:
            return None
        return _ring_edge_alt(self.shapes[min(cand)], x, y,
                              self._ref_cache)


def _clip_against(poly, blockers):
    """Exact difference against every blocker (no buffered standoff — the
    weld ruling: a standoff leaves a groove of raw DEM that renders as a
    knife-edge wall).  Returns the surviving Polygon parts."""
    for blocker in blockers:
        if poly is None or poly.is_empty:
            return []
        try:
            if poly.intersects(blocker):
                poly = poly.difference(blocker)
        except _PAD_EXC:
            return []
    if poly is None or poly.is_empty:
        return []
    parts = ([poly] if poly.geom_type == "Polygon"
             else [g for g in getattr(poly, "geoms", [])
                   if g.geom_type == "Polygon"])
    return [p for p in parts if p.area >= _MIN_PIECE_AREA_M2]


def _nearby(tree, polys, poly):
    if tree is None:
        return []
    try:
        return [polys[int(i)] for i in tree.query(poly)]
    except _PAD_EXC:                              # pragma: no cover
        return list(polys)


def emit_object_pads(layout: PavementLayout, dem, tile_lat: int,
                     tile_lon: int, *, icao: str = "",
                     pad_frames=None,
                     patch_dir: str | None = None) -> int:
    """Emit the airport's building pads.  Mutates ``layout.shapes``;
    returns the number of shapes emitted.

    No-op returning 0 when ``config.DSF_OBJECT_OBJECT_PADS`` is off, when
    there is no DEM, or when the airport has no object pack — the gate is
    read at CALL time, so a gate-off build is byte-identical to a
    pre-feature build even once this module is imported.

    ``pad_frames`` are the airport's ``object_frame.ObjectPadFrame``s.
    Passed in by the unit tests; resolved from the tile's Phase 2
    worklist (``post_mesh.pad_frames_from_worklist``) when only
    ``patch_dir`` is given, which is the production call.  The frame is
    built once per build behind the pristine-input cache, so resolving it
    here is a disk read on every build after the pack's first.

    THE GROUND IS THIS BUILD'S PATCH (RULINGS "OBJECT PADS: EMISSION-TIME
    RELATIVE").  ``patch_ground.field_from_layout`` reads the surface the
    solve just produced — which is why the ordering contract below is not
    merely about welds any more: the field must see the FINAL terrain.

    Ordering contract for the caller (§5.4): run this AFTER the
    adjacent-ground bands and the OLS cuts, i.e. last in the terrain
    block, before the tile cut.

    Records for the caller, all stashed on ``layout``:

      * ``object_pad_records`` — what this build emitted, for the log line
        and ``verification.check_object_pads``.  A report, never an input
        to another build: nothing persists them.
      * ``object_pad_findings`` — refusals, unhosted datums and the
        self-covering requests routed to the y-bake.
    """
    layout.object_pad_records = []
    layout.object_pad_findings = []
    if not _config.DSF_OBJECT_OBJECT_PADS or dem is None:
        return 0
    if layout is None or getattr(layout, "anchor", None) is None:
        return 0
    claim = _footprint_claim(layout)
    if pad_frames is None:
        if patch_dir is None:
            return 0
        from .post_mesh import pad_frames_from_worklist

        # NO placement-level claim here, deliberately: round-4 spec R2's
        # containment is applied to the REQUEST below (``specs_from_frames``
        # → ``claim``), which is where the retired sidecar reader applied
        # it too, and which lets the frames themselves be memoized once
        # per airport and shared with the flat-site detector's S4 read.
        pad_frames = pad_frames_from_worklist(patch_dir, icao)
    if not pad_frames:
        return 0

    from .config import (
        DSF_OBJECT_FOOT_PAD_MARGIN_M,
        DSF_OBJECT_PAD_MAX_RELIEF_M,
        GROUNDSIDE_MAX_GRADE,
    )
    from .elevation import _sample_dem
    from .patch_ground import field_from_layout

    margin = float(DSF_OBJECT_FOOT_PAD_MARGIN_M)
    ll_to_m = layout.ll_to_m

    # (The metre-frame DEM sampler that used to live here — the relief
    # cap's raw-DEM reference — is GONE with the re-frame: the ambient DEM
    # is now reached only through ``surface_at`` below, as the second half
    # of the pad's own two-authority ground.)
    ground_field = field_from_layout(layout)

    def patch_at(latitude: float, longitude: float):
        """The emitted patch's own ground at a world point, or ``None``
        where the patch authors nothing."""
        try:
            x, y = ll_to_m(float(latitude), float(longitude))
        except _PAD_EXC:                          # pragma: no cover
            return None
        value, _role = ground_field.value_at(x, y)
        return value

    def surface_at(latitude: float, longitude: float):
        """THE MESH'S OWN RULE: the patch where the patch authors, the
        ambient DEM where it does not — which is what the mesher will
        drape and therefore the ground a part will actually stand on."""
        value = patch_at(latitude, longitude)
        if value is not None:
            return value
        try:
            return _sample_dem(dem, tile_lat, tile_lon,
                               float(latitude), float(longitude))
        except _PAD_EXC:                          # pragma: no cover
            return None

    specs, findings = specs_from_frames(
        pad_frames, patch_at, surface_at, icao=icao, claim=claim)
    findings = list(findings)
    if not specs:
        layout.object_pad_findings = findings
        return 0

    pavement = _pavement_shapes(layout)
    pavement_polys = [s.polygon for s in pavement]
    # THE R2 INSTRUMENT, scoped to what a pad can reach.  Digesting every
    # pavement shape in the airport twice is real WKB work at a 5,000-shape
    # airport for a set most of which no pad comes within a kilometre of;
    # the shapes at RISK are those whose bbox meets the pads' own reach,
    # and those are digested in full.
    watched = _shapes_within(pavement, _specs_bounds(layout, specs))
    pavement_before = _pavement_digest(watched)
    feature_polys = [s.polygon for s in _feature_shapes(layout)]
    try:
        pavement_tree = STRtree(pavement_polys) if pavement_polys else None
    except _PAD_EXC:                              # pragma: no cover
        pavement_tree = None
    try:
        feature_tree = STRtree(feature_polys) if feature_polys else None
    except _PAD_EXC:                              # pragma: no cover
        feature_tree = None
    welds = _WeldIndex(layout)

    from .object_footprints import clip_pad_ring_against_pavement

    emitted_shapes: list = []
    pad_index: dict = {}
    records: list[dict] = []
    n_emitted = 0

    for index, spec in enumerate(specs):
        key = spec["seat_key"]
        try:
            ring_m = [ll_to_m(float(lat), float(lon))
                      for lon, lat in spec["ring_lonlat"]]
            outer = Polygon(ring_m)
            if not outer.is_valid:
                outer = outer.buffer(0)
        except _PAD_EXC:
            findings.append(("pad_ring_degenerate", key, 0.0, 0.0, ""))
            continue
        if outer.is_empty or outer.geom_type != "Polygon":
            findings.append(("pad_ring_degenerate", key, 0.0, 0.0, ""))
            continue

        target = float(spec.get("target_ground_metres") or 0.0)
        cx, cy = outer.centroid.x, outer.centroid.y
        at = _ll(layout, cx, cy)
        # THE PAD'S OWN GROUND, NEVER RAW DEM (RULINGS, Fable 2026-08-14).
        # The request carries the ground the emission path evaluated under
        # this pad's own parts — the patch where the patch authors, ambient
        # DEM where it does not.  It is READ here, never re-evaluated: a
        # second sampler (this was ``dem_at`` at the ring centroid) is a
        # second instrument, and at HECA our own solved apron stands tens
        # of metres off raw DEM, so that instrument refused 3,855 of ~3,910
        # requests for standing where the objects correctly stand.
        ground = spec.get("ground_reference_metres")
        if ground is None:
            findings.append(("pad_ground_unhosted", key, 0.0, 0.0, at))
            continue
        ground = float(ground)
        relief = object_pad_relief_m(target, ground)

        # §5.1 clause 1 — THE RELIEF CAP, re-framed.  An over-cap pad is
        # REFUSED with its measured numbers; the requesting cluster keeps
        # its residual and takes the y-bake path.  The frame's own
        # ``over_relief_cap`` still refuses beside it, unchanged: that one
        # is the WORST PART's residual against the ground under IT — also
        # an in-run local measurement, and a different question from this
        # one (a pad whose median target sits within the cap can still
        # carry a part floating far above it).  Neither reads raw DEM any
        # more, which is the whole of the re-frame.
        if (not object_pad_admissible(target, ground,
                                      DSF_OBJECT_PAD_MAX_RELIEF_M)
                or bool(spec.get("over_relief_cap"))):
            findings.append(("pad_over_relief_cap", key, abs(relief),
                             float(DSF_OBJECT_PAD_MAX_RELIEF_M), at))
            continue

        # §5.1 clause 2 — PAVEMENT WINS ABSOLUTELY.  Executed by the
        # function the spec names for it, called in the layout's METRE
        # frame: it is a pure planar difference and its sliver threshold
        # is a unit-free area FRACTION, so the law is identical while the
        # clip stays coordinate-EXACT.  (A degree round-trip would move a
        # welded vertex ~10 µm off the pavement chain it must share.)
        near_pav = _nearby(pavement_tree, pavement_polys, outer)
        pieces_ll = clip_pad_ring_against_pavement(
            list(outer.exterior.coords)[:-1],
            [list(p.exterior.coords)[:-1] for p in near_pav
             if p.geom_type == "Polygon"])
        if not pieces_ll:
            findings.append(("pad_wholly_inside_pavement", key,
                             abs(relief), 0.0, at))
            continue

        # §5.1 clause 4 — THE MARGIN RING, per request.  The derived ring
        # is the contact hull DILATED by the margin, so eroding it back
        # recovers the hull; a ring too tight to afford the full margin
        # keeps a real interior at a proportionally shorter erosion
        # (``grade_law.object_pad_blend_width_m``), which is what "a
        # ``DSF_OBJECT_FOOT_PAD_MARGIN_M``-class margin, per-request"
        # licenses.  Derived from the ORIGINAL ring, never from a clipped
        # piece, so the clip cannot move the law.
        #
        # WELD OR GAP: what the erosion leaves is no longer FILLED by a
        # blend annulus (that emitter retires, owner 2026-08-13) — it is
        # the ambient-DEM gap the mesh drapes, and it is also what keeps
        # the emitted core clear of every pavement and feature edge the
        # clip left, so the pad touches no other patch surface at all.
        blend_width = object_pad_blend_width_m(outer.area, outer.length,
                                               margin)
        core_full = None
        if blend_width > 0.0:
            try:
                eroded = outer.buffer(-blend_width, quad_segs=2)
                if eroded.geom_type == "Polygon" and not eroded.is_empty:
                    core_full = eroded
                elif eroded.geom_type == "MultiPolygon":
                    core_full = max(eroded.geoms, key=lambda g: g.area)
            except _PAD_EXC:                      # pragma: no cover
                core_full = None
        if core_full is None or core_full.area < _MIN_PIECE_AREA_M2:
            # No interior survives even the shortened ramp: the request's
            # contact hull has no usable area, so there is nowhere to hold
            # the building base and a pad here would be a bare step onto
            # raw DEM.  Refused WITH its measured ring area (§5.5), never
            # emitted as a stand-in.
            findings.append(("pad_no_contact_hull", key, float(outer.area),
                             float(_MIN_PIECE_AREA_M2), at))
            continue

        blockers = _nearby(feature_tree, feature_polys, outer) + \
            _pad_index_query(pad_index, outer.bounds)

        # PASS 1 — geometry.  Every surviving (part, core) pair of this
        # pad, and the STRICTEST pavement contact any of them has.
        parts: list = []
        run_m = float("inf")
        pav_value = None
        for piece_ll in pieces_ll:
            try:
                piece = Polygon(piece_ll)
                if not piece.is_valid:
                    piece = piece.buffer(0)
            except _PAD_EXC:                      # pragma: no cover
                continue
            for part in _clip_against(piece, blockers):
                core = None
                try:
                    inter = part.intersection(core_full)
                except _PAD_EXC:                  # pragma: no cover
                    inter = None
                if inter is not None and not inter.is_empty:
                    cands = ([inter] if inter.geom_type == "Polygon"
                             else [g for g in getattr(inter, "geoms", [])
                                   if g.geom_type == "Polygon"])
                    cands = [c for c in cands
                             if c.area >= _MIN_PIECE_AREA_M2]
                    if cands:
                        core = max(cands, key=lambda g: g.area)
                parts.append((part, core))
                run, value = _pavement_run(part, core, near_pav, welds)
                if value is not None and run < run_m:
                    run_m, pav_value = run, value

        # PASS 2 — the value.  §5.1 clause 3: ONE target for the whole
        # pad.  A pad is one seat; letting two of its pieces settle at
        # different heights would tear the surface under one building —
        # so the SHORTEST run to pavement anywhere on the pad governs the
        # whole of it, and pavement wins by exactly that much.
        if pav_value is not None:
            pulled = object_pad_pull_toward_pavement(
                target, pav_value, run_m, float(GROUNDSIDE_MAX_GRADE))
        else:
            pulled = target
        pulled_target = pulled
        shortfall = object_pad_pull_shortfall_m(target, pulled)

        # CORE ONLY (weld or gap).  A piece with no core contributes
        # NOTHING now: it used to become a blend plate, and a blend plate
        # with no core is a pure feather over ground the pad does not
        # hold — precisely the class the ruling retires.  What is left is
        # the pad itself, flat at its target, surrounded by gap.
        pad_shapes: list = []
        pad_area = 0.0
        for _part, core in parts:
            if core is None:
                continue
            coords = _open_coords(core)
            if len(coords) < 3:
                continue
            pad_shapes.append(BuiltShape(
                polygon=core, role=ROLE_OBJECT_PAD,
                ref=f"{REF_PAD_CORE}:{index}",
                node_altitudes=[round(pulled, 2)] * (len(coords) + 1)))
            pad_area += core.area

        if not pad_shapes:
            findings.append(("pad_clipped_away", key, abs(relief), 0.0, at))
            continue
        for shape in pad_shapes:
            layout.shapes.append(shape)
            emitted_shapes.append(shape)
            _pad_index_add(pad_index, shape.polygon)
            n_emitted += 1
        if shortfall > _MATERIALITY_M:
            findings.append(("pad_pull_shortfall", key, shortfall,
                             float(GROUNDSIDE_MAX_GRADE), at))
        records.append({
            "icao": str(icao or "").upper(),
            "seat_key": key,
            "fingerprint": spec["fingerprint"],
            "law_digest": spec.get("law_digest") or law_digest(),
            "kind": spec.get("kind"),
            "cluster_id": spec.get("cluster_id"),
            "structure_index": spec.get("structure_index"),
            "resource_path": spec.get("resource_path"),
            # The RING of the seat this record stands for (§2.5): part of
            # the seat key, so it must survive into the record.
            "ring_index": int(spec.get("ring_index") or 0),
            "latitude": spec.get("latitude"),
            "longitude": spec.get("longitude"),
            "base_y": spec.get("base_y"),
            "target_ground_metres": target,
            # THE CAP'S REFERENCE, recorded with the pad it governed, so
            # the verifier holds the cap on the EMITTED target against the
            # same ground the emitter used instead of re-sampling a raster
            # (lockstep, ruling R5).
            "ground_reference_metres": round(ground, 3),
            "emitted_target_metres": round(pulled_target, 3),
            "blend_width_m": round(blend_width, 4),
            "relief_metres": round(relief, 3),
            "area_m2": round(pad_area, 2),
            "shapes": len([s for s in pad_shapes]),
            "ring_lonlat": spec["ring_lonlat"],
            "index": index,
        })

    if emitted_shapes:
        _decimate_pad_group(layout, emitted_shapes)

    after = _pavement_digest(watched)
    if after != pavement_before:
        # The R2 hard clause failed at runtime.  This cannot happen by
        # construction (pads only append shapes and only decimate their
        # own group) — which is exactly why it is worth measuring: a
        # future change that breaks it is caught on the build that broke
        # it, by the law's own instrument.
        findings.append((PAVEMENT_DIGEST_FINDING, str(icao), 0.0, 0.0, ""))

    layout.object_pad_records = records
    layout.object_pad_findings = findings
    return n_emitted


def _ll(layout, x: float, y: float) -> str:
    try:
        lat, lon = layout.m_to_ll(x, y)
        return f"{lat:.5f},{lon:.5f}"
    except Exception:                              # pragma: no cover
        return "?,?"


def _pavement_run(part, core, near_pavement, welds: "_WeldIndex"):
    """``(run_m, pavement_value)`` for §5.1 clause 3, or ``(inf, None)``
    when this pad piece touches no pavement at all.

    ``run_m`` is the AVAILABLE RUN the law grades across: the planar
    distance from the pavement the pad welds to, to the pad's interior
    target region.  Measured core-to-pavement, so it is the SHORTEST run
    on this piece by construction — the strictest reading, which is the
    one that keeps the surface off the apron.  A piece whose core did not
    survive the clip has no run at all and takes the pavement's value
    outright.

    The pavement VALUE is read at the nearest point ON the donor's ring to
    that same core — the place the run is measured from, so the run and
    the value describe one cross-section.  Deliberately NOT
    ``part.intersection(contact.exterior)``: an exact clip against a
    pavement ring routinely shares a RUN and a CORNER with it at once, so
    that intersection comes back as a GeometryCollection of lines and
    points, which has no ``interpolate``.  Measured at OTHH 2026-08-09,
    where it aborted the build outright.  ``nearest_points`` is total over
    every geometry type.
    """
    contact = None
    best = None
    try:
        px0, py0, px1, py1 = part.bounds
    except _PAD_EXC:                               # pragma: no cover
        return float("inf"), None
    for pav in near_pavement:
        # Bbox reject first: a weld contact is within 2 cm, so a shape
        # whose box does not reach the piece's cannot be one, and the
        # exact ``distance`` (the expensive call, run once per candidate
        # per pad piece) is never made for it.
        try:
            bx0, by0, bx1, by1 = pav.bounds
        except _PAD_EXC:                           # pragma: no cover
            continue
        if (bx0 > px1 + _WELD_TOL_M or bx1 < px0 - _WELD_TOL_M
                or by0 > py1 + _WELD_TOL_M or by1 < py0 - _WELD_TOL_M):
            continue
        try:
            d = part.distance(pav)
        except _PAD_EXC:                           # pragma: no cover
            continue
        if d <= _WELD_TOL_M and (best is None or d < best):
            best = d
            contact = pav
    if contact is None:
        return float("inf"), None
    anchor = part if (core is None or core.is_empty) else core
    try:
        from shapely.ops import nearest_points

        point = nearest_points(anchor, contact.exterior)[1]
    except _PAD_EXC:
        return float("inf"), None
    if point is None or point.is_empty:            # pragma: no cover
        return float("inf"), None
    value = welds.value_at(point.x, point.y)
    if value is None:
        return float("inf"), None
    if core is None or core.is_empty:
        return 0.0, float(value)
    try:
        run = float(core.distance(contact))
    except _PAD_EXC:                               # pragma: no cover
        run = 0.0
    return max(0.0, run), float(value)


def _decimate_pad_group(layout: PavementLayout, emitted_shapes: list) -> int:
    """3D-collinear decimation over the pad group — the adjacent-ground /
    OLS group pattern (§5.4: "they enter ``emit_decimate`` at the same
    tier as adjacent-ground bands ... weld rows pinned").

    The layout-wide ``decimate_emit_nodes`` has already run by the time
    this emitter is called, so without this the pad rows reach the
    triangulator undecimated.  Vertices on a FOREIGN shape's boundary are
    force-kept: a pad is clipped EXACTLY against pavement and features, so
    its ring can trace a foreign constrained edge coordinate-exactly, and
    chord-cutting such a vertex diverges the two chains into the
    near-parallel sliver pair Ruppert refinement explodes on.  The
    core↔blend shared chain needs no special handling — both shapes are in
    the group, and ``decimate_shape_group``'s unanimity fixed point
    already refuses to drop a vertex one of them keeps."""
    if not emitted_shapes:
        return 0
    from shapely.geometry import box as _box

    ids = {id(s) for s in emitted_shapes}
    exteriors = [s.polygon.exterior for s in layout.shapes
                 if s.polygon is not None and not s.polygon.is_empty
                 and s.polygon.geom_type == "Polygon" and id(s) not in ids]
    try:
        tree = STRtree(exteriors) if exteriors else None
    except _PAD_EXC:                              # pragma: no cover
        tree = None

    def on_foreign_boundary(x, y):
        if tree is None:
            return False
        p = Point(x, y)
        try:
            cand = tree.query(_box(x - 0.06, y - 0.06, x + 0.06, y + 0.06))
        except _PAD_EXC:                          # pragma: no cover
            return False
        for gi in cand:
            try:
                if exteriors[int(gi)].distance(p) <= 0.05:
                    return True
            except _PAD_EXC:                      # pragma: no cover
                continue
        return False

    return decimate_shape_group(emitted_shapes, Z_TOL_BOUNDARY_M,
                                protect_predicate=on_foreign_boundary)
