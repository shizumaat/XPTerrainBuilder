"""Post-mesh stage: re-anchor DSF objects against the freshly built mesh.

Contract frozen by workstream W1 (``docs/dsf_object_integration_spec.md``
section 4-W7, as amended by A4/A5); implemented in workstream W7.

Phase 2 of the DSF object integration cannot run before the mesh exists —
the y offsets encode one specific built ``Data<tile>.mesh``.  The hook is
a single guarded call at the END of ``O4_Mesh_Utils.build_mesh`` (and
``sort_mesh``), not in ``build_all``'s callers: the GUI's per-step Mesh
button and Shift-click sort_mesh bypass ``build_all`` entirely, and an
out-of-band rebuild is exactly how the 1.19 m staleness incident happened
(amendment A4).  The mesh path comes from ``FNAMES.mesh_file(
tile.build_dir, ...)`` — never the ``Custom Scenery/zOrtho4XP_*`` symlink
the prototype hard-coded.

Inputs arrive via the worklist sidecar
``Patches/<lon lat>/o4_object_anchor_worklist.json``, written once per
tile by the driver's MAIN process (workers race, amendment A5) before the
rebuild-skip gate, carrying identification only::

    {"version": 2, "tile": "+35-081", "xplane_root": ...,
     "airports": [{"icao": ..., "dsf_path": ..., "dsf_mtime": ...,
                   "pack_root": ..., "xplane_root": ...,
                   "source": "apt_dat" | "pack_scan"}]}

Since version 2 (amendment A22) an airport may contribute SEVERAL
entries — one per scenery pack placing objects near it — because object
discovery is independent of the apt.dat geometry contest.  Readers stay
version-agnostic: a v1 file is simply the apt.dat-only subset (entries
without ``source``) and processes identically.

Discovery (placements, pools, partition) happens here, post-mesh — the
geometry caches key on (path, mtime), so repeat builds are cheap and
there is no stale-groups special case.  A worklist ``dsf_mtime`` that
disagrees with disk is merely noted: discovery is authoritative, the
worklist is identification only (amendment A5), and the CURRENT DSF is
what discovery reads regardless.

Invariant I-4's enforcement point is HERE (amendment A13, item 2): a
resource with more than one terrain-draped ``OBJECT`` placement is
excluded from Phase 2 before any decision is built — a shared ``.obj``
file cannot carry per-placement offsets.  (Phase 1 ACCEPTS the same
resources: N placements are N buildings, invariant I-5.)

Reporting follows ``verification.verify_and_log``: runtime validators are
pure reporters; an exception here must NEVER fail the tile (the caller
wraps this in try/except, and the function additionally contains every
per-airport failure itself).  Console gets one summary line per airport;
full detail goes to verbosity level 2, plus the "restart X-Plane
(objects are cached)" reminder once per corrected pack.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import pickle

import O4_UI_Utils as UI

from . import dsf_reader, obj8_reader, object_anchor, object_rebake
from .mesh_sampler import MeshElevationSampler

# One file per tile, next to the tile's auto-patches.  The driver writes
# it (main process only); this module and tools/reanchor_dsf_objects.py
# read it.
OBJECT_ANCHOR_WORKLIST_FILENAME = "o4_object_anchor_worklist.json"
# 2: one entry per (airport, pack) — object discovery independent of
#    the apt.dat geometry contest (amendment A22, field case LSGL
#    2026-07-23); entries carry a "source" tag.  Readers are
#    version-agnostic (a v1 file is the apt.dat-only subset).
# 3: entries are per (airport, pack) BY CONTAINMENT (round-4 spec R2).
#    A DSF cell carrying two airports' objects now appears once per
#    airport, each entry carrying that airport's "claim" geometry
#    (thresholds hull dilated by object_pads._CLAIM_MARGIN_M) so Phase 2
#    can partition the cell's placements between them.  Under version 2
#    the cell went whole to whichever airport sorted first: on +25+051
#    OTBD owned the entire OTHH Aeroscape pack.  Readers stay
#    version-agnostic — an entry with no "claim" simply claims every
#    placement of its DSF, which IS the version-2 behaviour.
OBJECT_ANCHOR_WORKLIST_VERSION = 3

# Per-tile record of the foot-pad REQUESTS the foot re-anchor raised
# (multi-ground-cluster objects whose best rigid offset still leaves a
# foot off the mesh past ``DSF_OBJECT_FOOT_PAD_RESIDUAL_M``).  Written
# next to the worklist after every rebake — refreshed each run, removed
# when no request remains — carrying, per request, the pad rings
# (``object_footprints.foot_pad_rings``) and the target ground
# elevation.  A future terrain-shaping stream consumes it; until then
# it is the durable audit trail for feet a rigid body cannot seat.
OBJECT_FOOT_PAD_SIDECAR_FILENAME = "o4_object_foot_pads.json"
# 2: per-CLUSTER pad requests join the per-foot ones (per-cluster seating
#    spec section 5.3).  Every request now carries a "kind" tag —
#    "foot" | "cluster" — and cluster requests additionally carry
#    "cluster_id", "part_count" and "over_relief_cap".  A version-1 file
#    is exactly the "foot"-only subset, so readers stay
#    version-agnostic.
# 3: the pad CONSUMER's ``emitted`` section joins the requests
#    (per-cluster seating spec section 5.2).  It is written by
#    ``object_pads`` in the auto-patch phase, carried across this
#    module's refresh untouched, and records per emitted pad its ring,
#    its target and the fingerprint of the seat that produced it — the
#    memory that keeps a pad standing after the request that asked for
#    it converges away.  A version-2 file is exactly the request-only
#    subset, so readers stay version-agnostic here too.
# 4: THE RING LAW CHANGED (object-reseat-threshold-spec section 2.5,
#    2026-08-09).  A request no longer carries one "ring_lonlat" — the
#    convex hull of its whole residual group, which bridged the water and
#    parking lots between spread-out parts — but "rings_lonlat", the
#    connected components of its per-part contact hulls dilated by
#    DSF_OBJECT_FOOT_PAD_MARGIN_M.  Readers STOP being version-agnostic
#    here: a version-3 file's rings are the retired law's geometry, so it
#    is REFUSED wholesale on read (requests and ``emitted`` records both,
#    ``object_pads.sidecar_is_current``) and the next rebake re-derives.
# 5: THE PLAN-BOX FALLBACK IS RETIRED (round-4 spec R1, 2026-08-10).  A
#    part with no contact-band triangle used to fall back to its welded
#    mega-part's PLAN BOX; on the owner's OTHH build that was 61 rings,
#    83 % of all pad area, worst 224,146 m2 around a pier-supported
#    viaduct.  Such a part now raises no request at all, and the box
#    survives only for a degenerate part standing IN the contact band
#    with a plan box under DSF_OBJECT_PAD_PLAN_BOX_FALLBACK_MAX_M2.  The
#    version bump is what discards the thirty-hectare requests already
#    on disk — same refusal machinery as version 4.
OBJECT_FOOT_PAD_SIDECAR_VERSION = 5

# A single pad ring component larger than this is REPORTED at verbosity
# 1 with the resource that asked for it (object-reseat-threshold-spec
# section 2.5 v2b).  Observability only: nothing is refused, resized or
# dropped on account of it — the owner's in-sim defect was a 162,219 m²
# pad, and a build that makes one that big should say so out loud.
OBJECT_PAD_RING_REPORT_AREA_M2 = 10_000.0


def _ring_area_square_metres(ring_lonlat) -> float:
    """Metric area of a small ``(lon, lat)`` ring — the local
    equirectangular scale at the ring's own latitude, the same
    projection ``object_footprints`` builds the ring in."""
    if not ring_lonlat or len(ring_lonlat) < 3:
        return 0.0
    from shapely.geometry import Polygon

    latitudes = [latitude for _longitude, latitude in ring_lonlat]
    centroid_latitude = sum(latitudes) / len(latitudes)
    metres_per_degree_longitude = (
        obj8_reader.METRES_PER_DEGREE_LATITUDE
        * math.cos(math.radians(centroid_latitude))
    )
    polygon = Polygon([
        (longitude * metres_per_degree_longitude,
         latitude * obj8_reader.METRES_PER_DEGREE_LATITUDE)
        for longitude, latitude in ring_lonlat
    ])
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return float(polygon.area)

# The counts returned by rebake_dsf_objects, all starting at zero.
_COUNT_KEYS = (
    "airports_processed",
    "packs_corrected",
    "structures_baked",
    "structures_needing_pad",
    "vertices_offset",
    "objects_skipped",
    "objects_reverted",
    "objects_partially_baked",
    "airports_failed",
    "foot_pad_requests",
    # Per-cluster seating (DSF_OBJECT_CLUSTER_SEATING): terrain-pad
    # requests raised by seated clusters, and the reported seams of
    # elevated components that span two clusters.
    "cluster_pad_requests",
    "cluster_bridge_seams",
    # Seating units (structures + clusters) the reseat threshold left
    # alone: the pack was deliberately not modified for them and the
    # terrain adapts instead (object-reseat-threshold spec section 2.1).
    "units_below_bake_threshold",
    # Airports whose recorded run fingerprint still matched every input,
    # so nothing was re-derived (O4_REANCHOR_SHORT_CIRCUIT).
    "airports_up_to_date",
    # Basin facilities seated by the dedicated rim-flush law, and the
    # per-facility clearance FINDINGS it raised
    # (docs/specs/basin-rim-flush-seating-spec.md section 2.2 items 5
    # and 7).  A finding means the section-2.1 seat margin is too small
    # for that airport — an owner decision, never a silent re-derive.
    "basin_rim_flush_seated",
    "basin_clearance_findings",
    # Round-12 bridge FINDINGS (docs/specs/round12-bridge-deck-datum-
    # spec.md).  ``bridge_seat_fallback`` (R12-2): a refused family with
    # no measurable deck, kept on the generic y-bake.
    # ``bridge_verdict_frame_split`` (R12-3): a resource the post-mesh
    # classification judges differently from the pipeline-time cache.
    # Both are recorded and counted; neither changes a seat or a verdict.
    "bridge_seat_fallbacks",
    "bridge_verdict_frame_splits",
    # Amendment 4: families seated by an agreeing coalition, and the
    # deck members that did NOT agree with it.  Informational — the
    # seat happened — but counted, because the outliers are the evidence
    # trail for the canal-floor residual.
    "bridge_seat_coalitions",
    "bridge_seat_coalition_outliers",
)


def object_anchor_worklist_path(tile) -> str:
    """The tile's worklist sidecar path, derived the same way the driver
    derives its auto-patch paths (``FNAMES.patch_dir``)."""
    import O4_File_Names as FNAMES

    return os.path.join(
        FNAMES.patch_dir(
            int(math.floor(tile.lat)), int(math.floor(tile.lon))
        ),
        OBJECT_ANCHOR_WORKLIST_FILENAME,
    )


#: How a point reached its owner (R11-1).  ``assign(..., with_mode=True)``
#: returns one of these beside the icao.  Only ``CLAIM_CONTAINMENT`` says
#: the airport's own claim geometry holds the point; the other two are the
#: never-drop FALLBACKS, correct for object ANCHORING and no licence to
#: rewrite terrain (docs/specs/round11-kmci-flat-claim-spec.md R11-1).
CLAIM_CONTAINMENT = "containment"
CLAIM_SOLE_ENTRY = "sole_entry"
CLAIM_NEAREST = "nearest"


def worklist_claim_assigner(entries):
    """``assign(dsf_path, latitude, longitude) -> icao | None`` — WHICH
    AIRPORT OWNS A POINT (round-4 spec R2).

    An object belongs to the airport whose claim geometry — the
    thresholds hull dilated by ``object_pads._CLAIM_MARGIN_M``, recorded
    per worklist entry by the driver — CONTAINS it.  An object no
    airport claims goes to the nearest airport's entry, so nothing is
    ever dropped for want of an owner.

    The candidate set is scoped PER DSF: only airports that actually
    hold an entry for that DSF can win it, which is what guarantees
    every placement lands in some entry that will be processed.  A DSF
    with a single entry answers that entry for every point (the
    version-2 behaviour, kept exactly), and so does an entry whose
    claim geometry is missing or unusable — a claim nobody can test is
    never a reason to lose objects.

    ``assign(..., with_mode=True)`` returns ``(icao, mode)`` instead —
    the SAME icao, plus HOW it was reached (``CLAIM_CONTAINMENT`` /
    ``CLAIM_SOLE_ENTRY`` / ``CLAIM_NEAREST``, and ``None`` mode with a
    ``None`` icao).  R11-1: a caller that would move TERRAIN on the
    strength of a claim has to know whether the claim was tested or
    merely defaulted to, and only the containment answer is a test.  The
    default call is unchanged in answer AND in cost — the sole-entry
    short-circuit still returns before any geometry is touched, and the
    containment test a mode-asking caller needs is paid only by that
    caller.
    """
    import math as _math

    by_dsf: dict[str, list[tuple]] = {}
    for entry in entries or ():
        dsf_path = entry.get("dsf_path")
        if not dsf_path:
            continue
        claim = entry.get("claim") or {}
        centre = claim.get("centre_lonlat")
        hull = claim.get("hull_lonlat") or ()
        polygon = None
        if len(hull) >= 4:
            try:
                from shapely.geometry import Polygon as _Polygon

                candidate = _Polygon([(float(x), float(y)) for x, y in hull])
                polygon = candidate if candidate.is_valid else None
            except Exception:
                polygon = None
        by_dsf.setdefault(os.path.realpath(dsf_path), []).append(
            (entry.get("icao"), polygon, centre, claim.get("radius_m"))
        )

    def assign(dsf_path: str, latitude: float, longitude: float,
               with_mode: bool = False):
        candidates = by_dsf.get(os.path.realpath(dsf_path or "")) or ()
        if not candidates:
            return (None, None) if with_mode else None
        if len(candidates) == 1 and not with_mode:
            return candidates[0][0]
        containing = []
        for icao, polygon, centre, radius in candidates:
            if polygon is None:
                if centre and radius:
                    scale = max(0.1, _math.cos(_math.radians(latitude)))
                    if _math.hypot(
                        (longitude - centre[0]) * 111320.0 * scale,
                        (latitude - centre[1]) * 111320.0,
                    ) <= float(radius):
                        containing.append((0.0, icao))
                continue
            try:
                from shapely.geometry import Point as _Point

                if polygon.covers(_Point(longitude, latitude)):
                    containing.append((polygon.area, icao))
            except Exception:
                continue
        if containing:
            # Smallest claiming hull wins a genuine overlap: the tighter
            # claim is the more specific one.
            winner = min(containing)[1]
            return (winner, CLAIM_CONTAINMENT) if with_mode else winner
        if with_mode and len(candidates) == 1:
            # The version-2 answer — this DSF's only entry takes the
            # point — reported for what it is: NOT a containment test.
            return (candidates[0][0], CLAIM_SOLE_ENTRY)
        nearest = None
        for icao, _polygon, centre, _radius in candidates:
            if not centre:
                continue
            scale = max(0.1, _math.cos(_math.radians(latitude)))
            distance = _math.hypot(
                (longitude - centre[0]) * 111320.0 * scale,
                (latitude - centre[1]) * 111320.0,
            )
            if nearest is None or (distance, icao) < nearest:
                nearest = (distance, icao)
        winner = nearest[1] if nearest else candidates[0][0]
        return (winner, CLAIM_NEAREST) if with_mode else winner

    return assign


def _mesh_is_newer_than_alt(tile, mesh_path: str) -> bool:
    """O3 ordering guard: is the built mesh at least as new as the tile's
    ``.alt`` elevation raster?

    The mesh is derived from the ``.alt`` written in step 1 (with airport
    elevation insets baked in).  Returns ``True`` when the mesh is newer
    than (or equal to) the newest ``.alt`` for this tile, so the object
    y-bake is sampling the current elevation state.  Returns ``False`` only
    when an ``.alt`` exists and is STRICTLY newer than the mesh (stale mesh
    -- the caller must not sample it).  When no ``.alt`` is found on disk
    (already cleaned up, or a standalone probe), returns ``True`` -- there
    is nothing to be stale against and the mesh is authoritative.
    """
    import glob

    import O4_File_Names as FNAMES

    try:
        mesh_mtime = os.path.getmtime(mesh_path)
    except OSError:
        return True
    # All .alt variants for this tile (plain ``Data<tile>.alt`` plus any
    # ``Data<tile>.<iterate>.alt`` from the densify path).
    tile_stub = os.path.join(
        tile.build_dir, "Data" + FNAMES.short_latlon(tile.lat, tile.lon)
    )
    alt_candidates = [tile_stub + ".alt"] + glob.glob(tile_stub + ".*.alt")
    newest_alt_mtime = None
    for alt_path in alt_candidates:
        try:
            alt_mtime = os.path.getmtime(alt_path)
        except OSError:
            continue
        if newest_alt_mtime is None or alt_mtime > newest_alt_mtime:
            newest_alt_mtime = alt_mtime
    if newest_alt_mtime is None:
        return True
    # A one-second slack absorbs filesystem mtime granularity (some FSes
    # store whole seconds); only a genuinely older mesh trips the guard.
    return mesh_mtime >= newest_alt_mtime - 1.0


def _is_protected_scenery_root(pack_root: str) -> bool:
    """True when ``pack_root`` lies inside the base simulator — any path
    with a ``Global Scenery`` or ``Resources`` component (amendment A15).
    Only Custom Scenery packs are ever rebake candidates."""
    components = os.path.normpath(pack_root).split(os.sep)
    return "Global Scenery" in components or "Resources" in components


def _resolved_path_is_inside_pack(physical_path: str, pack_root: str) -> bool:
    """True when the resolved object file lives under the pack that owns
    the DSF.  A ``library.txt``-resolved resource lands in ANOTHER pack:
    a shared library object serves many airports and must never carry one
    airport's offsets (amendment A15, guard 2)."""
    try:
        return (
            os.path.commonpath(
                [os.path.abspath(physical_path), os.path.abspath(pack_root)]
            )
            == os.path.abspath(pack_root)
        )
    except ValueError:  # different drives (Windows)
        return False


def _pool_world_bounds(
    pool: object_anchor.ObjectPool,
    geometry_by_resource: dict,
) -> tuple[float, float, float, float]:
    """``(minimum_longitude, minimum_latitude, maximum_longitude,
    maximum_latitude)`` covering every pool member's anchor expanded by
    its solid reach.  Reach bounds every solid vertex by definition, so
    the sampler (which adds its own ~200 m ``margin_degrees``) retains
    every triangle a structure or anchor sample can touch."""
    minimum_longitude = minimum_latitude = math.inf
    maximum_longitude = maximum_latitude = -math.inf
    for placement in pool.placements:
        geometry = geometry_by_resource.get(placement.resource_path)
        reach_metres = (
            geometry.solid_reach_metres() if geometry is not None else 0.0
        )
        latitude_degrees = (
            reach_metres / obj8_reader.METRES_PER_DEGREE_LATITUDE
        )
        metres_per_degree_longitude = (
            obj8_reader.METRES_PER_DEGREE_LATITUDE
            * math.cos(math.radians(placement.latitude))
        )
        longitude_degrees = (
            reach_metres / metres_per_degree_longitude
            if metres_per_degree_longitude > 0.0
            else 0.0
        )
        minimum_longitude = min(
            minimum_longitude, placement.longitude - longitude_degrees
        )
        maximum_longitude = max(
            maximum_longitude, placement.longitude + longitude_degrees
        )
        minimum_latitude = min(
            minimum_latitude, placement.latitude - latitude_degrees
        )
        maximum_latitude = max(
            maximum_latitude, placement.latitude + latitude_degrees
        )
    return (
        minimum_longitude,
        minimum_latitude,
        maximum_longitude,
        maximum_latitude,
    )


# Bump when partition_structures' output shape or semantics change, or
# when anything new starts feeding the partition (the pickle payload and
# the hash must both change meaning together).
# 3: Structure.contact_edges — the epsilon-contact edges threaded
#    through to per-cluster seating (a version-2 pickle has no such
#    attribute, and seating must never read one).
# 4: connector-split groups carry the split's RE-DERIVED edges instead
#    of an empty set (a version-3 pickle left exactly the split
#    mega-structures unclusterable).
_PARTITION_CACHE_VERSION = 4


def _cached_partition_structures(
    pool,
    geometry_by_resource,
    geometry_source_by_resource,
    pack_root,
    epsilon_metres,
):
    """``object_anchor.partition_structures`` behind a pack sidecar cache.

    The partition is a pure function of the pool's placements and the
    authored OBJ8 geometry (module contract in ``object_anchor``): it
    never touches the mesh or DEM, yet dominated the whole post-mesh
    rebake (profiled 2026-07-15: 195 s of 385 s at KBNA) and reruns on
    every mesh build.  Cached per pool under
    ``Airport_mod_cache/<pack>/`` (the ruling-established home for
    Ortho4XP-only sidecars).

    The key is a CONTENT hash — placements plus the bytes of each
    geometry source file (the ``.anchor_bak`` original when present,
    ruling R1) — not a size/mtime fingerprint: the rebake itself
    rewrites pack ``.obj`` files every run, so mtimes churn while the
    partition inputs stay identical.  ``object_anchor`` stays pure; the
    file input/output lives here with the rest of Phase 2's disk work.
    ``O4_OBJECT_PARTITION_CACHE=0`` disables.  Cache misses (corrupt or
    version-skewed files included) silently recompute.
    """
    cache_directory = dsf_reader.airport_mod_cache_dir(pack_root)
    if (
        cache_directory is None
        or os.environ.get("O4_OBJECT_PARTITION_CACHE", "1") != "1"
    ):
        return object_anchor.partition_structures(
            pool, geometry_by_resource, epsilon_metres=epsilon_metres
        )

    from .config import DSF_OBJECT_ELEVATED_BASE_M

    digest = hashlib.sha1()
    digest.update(
        repr(
            (
                _PARTITION_CACHE_VERSION,
                epsilon_metres,
                DSF_OBJECT_ELEVATED_BASE_M,
            )
        ).encode()
    )
    for placement in pool.placements:
        digest.update(repr(placement).encode())
    for resource_path in sorted(
        {placement.resource_path for placement in pool.placements}
    ):
        source_path = geometry_source_by_resource.get(resource_path)
        if source_path is None:
            continue
        digest.update(resource_path.encode())
        try:
            with open(source_path, "rb") as handle:
                digest.update(handle.read())
        except OSError:
            # Unreadable source — do not risk a stale key; skip caching.
            return object_anchor.partition_structures(
                pool, geometry_by_resource, epsilon_metres=epsilon_metres
            )
    cache_path = os.path.join(
        cache_directory,
        "o4_object_partition_%s.cache" % digest.hexdigest()[:16],
    )

    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "rb") as handle:
                payload = pickle.load(handle)
            if payload.get("version") == _PARTITION_CACHE_VERSION:
                return payload["structures"]
        except Exception:
            pass  # corrupt/unreadable cache — recompute below

    structures = object_anchor.partition_structures(
        pool, geometry_by_resource, epsilon_metres=epsilon_metres
    )
    try:
        os.makedirs(cache_directory, exist_ok=True)
        temporary_path = cache_path + ".tmp"
        with open(temporary_path, "wb") as handle:
            pickle.dump(
                {
                    "version": _PARTITION_CACHE_VERSION,
                    "structures": structures,
                },
                handle,
            )
        os.replace(temporary_path, cache_path)
    except OSError:
        pass  # caching is best-effort; the result is already computed
    return structures


def pad_frame_cache_key(pool, pack_root: str) -> str:
    """The PAD FRAME's cache key, on PRISTINE pack inputs.

    Owner ruling 2026-08-13, "AIRPORT DERIVED CACHES KEY ON PRISTINE
    INPUTS": the y-bake rewrites pack ``.obj`` files every run, so a key
    over the files ON DISK churns while the frame's real inputs — the
    AUTHORED geometry — never moved.  The pristine entries come from the
    one implementation
    (``object_rebake.pristine_object_fingerprint_entries``), never
    re-spelled here, so this cache and the footprint / classification
    sidecars cannot disagree about what "unchanged pack" means.

    The law scalars that SHAPE the frame ride in the key too: change the
    elevated-base cut or the contact band and the parts change, which a
    key over inputs alone would not see.
    """
    from .config import (
        DSF_OBJECT_ELEVATED_BASE_M,
        DSF_OBJECT_FOOT_BAND_M,
        DSF_OBJECT_PAD_PLAN_BOX_FALLBACK_MAX_M2,
    )
    from .object_frame import PAD_FRAME_VERSION
    from .object_rebake import pristine_object_fingerprint_entries

    digest = hashlib.sha1()
    digest.update(repr((
        PAD_FRAME_VERSION,
        DSF_OBJECT_ELEVATED_BASE_M,
        DSF_OBJECT_FOOT_BAND_M,
        DSF_OBJECT_PAD_PLAN_BOX_FALLBACK_MAX_M2,
    )).encode())
    for placement in pool.placements:
        digest.update(repr(placement).encode())
    for entry in pristine_object_fingerprint_entries(pack_root):
        digest.update(entry.encode())
    return digest.hexdigest()[:16]


def cached_pad_frame(pool, geometry_by_resource, structures, pack_root):
    """``object_frame.build_pad_frame`` behind the pristine-key sidecar.

    The frame is PACK data and mesh-free, so it is built ONCE per build —
    in-run, pre-solve — and both consumers read this one product: the pad
    emitter (through the emitted patch's own ground) and the y-bake
    fallback (through the built mesh).  That is Fable's R3, "one frame,
    single pass"; the alternative costed at 66.6 s per HECA build was
    building it twice.

    ``O4_OBJECT_PAD_FRAME_CACHE=0`` disables the disk half only — the
    frame is still built, so the flag can never change a result, just
    what it costs.  A corrupt or version-skewed file recomputes
    silently, like every other sidecar here.
    """
    from . import object_frame

    fresh = lambda: object_frame.build_pad_frame(   # noqa: E731
        pool, geometry_by_resource, structures)

    cache_directory = dsf_reader.airport_mod_cache_dir(pack_root)
    if (
        cache_directory is None
        or os.environ.get("O4_OBJECT_PAD_FRAME_CACHE", "1") != "1"
    ):
        return fresh()

    cache_path = os.path.join(
        cache_directory,
        "o4_object_pad_frame_%s.cache" % pad_frame_cache_key(pool, pack_root),
    )
    if os.path.isfile(cache_path):
        try:
            with open(cache_path, "rb") as handle:
                payload = pickle.load(handle)
            if payload.get("version") == object_frame.PAD_FRAME_VERSION:
                return payload["frame"]
        except Exception:
            pass  # corrupt/unreadable cache — recompute below

    frame = fresh()
    try:
        os.makedirs(cache_directory, exist_ok=True)
        temporary_path = cache_path + ".tmp"
        with open(temporary_path, "wb") as handle:
            pickle.dump(
                {"version": object_frame.PAD_FRAME_VERSION, "frame": frame},
                handle,
            )
        os.replace(temporary_path, cache_path)
    except OSError:
        pass  # caching is best-effort; the result is already computed
    return frame


def pad_frames_for_airport(
    dsf_path: str,
    pack_root: str | None,
    xplane_root: str | None,
    *,
    epsilon_metres: float | None = None,
    claims_placement=None,
    skipped: list | None = None,
) -> list:
    """Every :class:`object_frame.ObjectPadFrame` one airport's DSF yields
    — the SAME decomposition Phase 2 uses, with the mesh removed.

    THE BINDING CONSTRAINT (R3 step 3, and the R1 failure Fable rejected).
    The pools this walks must be the POST-MESH ones: ``_resolve_pack
    _geometry`` → ``object_anchor.discover_object_pools`` →
    ``_cached_partition_structures`` → :func:`cached_pad_frame`, in that
    order and through those functions.  ``dsf_reader.
    _compute_dsf_object_buildings``' Phase-1 decomposition admits a
    DIFFERENT resource set (amendment A15's outside-the-pack refusal and
    invariant I-4's multi-placement refusal are Phase-2 only; the
    connector prefilter and the terrain classification are Phase-1 only),
    so a frame built on Phase-1 pools would miss the pristine cache key
    and the build would pay for the frame TWICE — the whole reason R3
    exists.  Everything the two paths share is therefore CALLED here, not
    re-spelled: this function is discovery order, nothing else.

    MESH-FREE by construction: no ``mesh_path``, no ``MeshElevationSampler``,
    no run-record short circuit (that record is about a BAKE), and no
    basin / bridge-abutment pass (both are seating laws that read the
    built mesh).  It is therefore callable in-run, pre-solve, which is
    where the pad emitter needs it.

    ``claims_placement(latitude, longitude) -> bool`` is round-4 spec R2's
    containment, identical in meaning to
    :func:`discover_and_rebake_airport`'s: a DSF cell carrying two
    airports' objects yields each airport only its own placements.

    Frames come back in pool order.  A pack that is base/global scenery,
    a DSF with no ``.obj`` placements, or a claim that empties the subset
    all yield ``[]`` — never an exception, because a build must not fail
    over an object pack it could not read.
    """
    from .config import DSF_OBJECT_CONTACT_EPSILON_M

    if epsilon_metres is None:
        epsilon_metres = DSF_OBJECT_CONTACT_EPSILON_M
    if skipped is None:
        skipped = []

    lines = dsf_reader._load_dsf_text(dsf_path)
    if not lines:
        skipped.append(
            (dsf_path, "DSF text unavailable (missing file or DSFTool)"))
        return []
    placements = obj8_reader.read_dsf_object_placements(
        lines,
        accept_resource=lambda resource: resource.lower().endswith(".obj"),
    )
    if not placements:
        return []
    if pack_root is None:
        pack_root = dsf_reader._pack_root_for_dsf(dsf_path)
    # Amendment A15 guard 1, verbatim from the rebake: base and global
    # scenery are never rebaked, so no pad ever answers for one either.
    if pack_root is None or _is_protected_scenery_root(pack_root):
        skipped.append(
            (dsf_path,
             "pack is base or global scenery — never rebaked "
             "(amendment A15)"))
        return []

    # Invariant I-4's census counts over the WHOLE cell (round-4 spec R2),
    # the claim then narrows to this airport — the same order the rebake
    # uses, so a resource placed at two airports is excluded at both.
    placement_count_over_whole_dsf: dict[str, int] = {}
    for placement in placements:
        placement_count_over_whole_dsf[placement.resource_path] = (
            placement_count_over_whole_dsf.get(placement.resource_path, 0) + 1
        )
    if claims_placement is not None:
        placements = [
            placement
            for placement in placements
            if claims_placement(placement.latitude, placement.longitude)
        ]
        if not placements:
            return []

    (
        resolved_paths,
        geometry_by_resource,
        geometry_source_by_resource,
    ) = _resolve_pack_geometry(
        placements,
        placement_count_over_whole_dsf,
        pack_root,
        xplane_root,
        skipped,
    )
    if not resolved_paths:
        return []

    pools = object_anchor.discover_object_pools(
        [placement for placement in placements
         if placement.resource_path in resolved_paths],
        resolved_paths,
        geometry_by_resource,
        epsilon_metres=epsilon_metres,
    )
    frames = []
    for pool in pools:
        pool_geometry_by_resource = {
            resource_path: geometry_by_resource[resource_path]
            for resource_path in pool.resolved_paths
        }
        structures = _cached_partition_structures(
            pool,
            pool_geometry_by_resource,
            geometry_source_by_resource,
            pack_root,
            epsilon_metres,
        )
        frames.append(cached_pad_frame(
            pool, pool_geometry_by_resource, structures, pack_root))
    return frames


#: In-PROCESS memo for :func:`pad_frames_from_worklist`.  One airport is
#: built once per worker, but its frames are read TWICE inside that build
#: — by the flat-site detector's S4 signal (pre-solve) and by the pad
#: emitter (post-solve).  The partition and the frame are disk-cached,
#: but the walk to them (DSF text, geometry resolution, pool discovery)
#: is not, and doing it twice is the duplicated-frame cost R3 exists to
#: remove.  Keyed by the inputs that select the frames; never persisted.
_PAD_FRAME_MEMO: dict = {}


def pad_frames_from_worklist(patch_dir: str, icao: str, *,
                             claims_placement=None) -> list:
    """The airport's pad frames, resolved through the tile's Phase 2
    worklist sidecar — the in-run entry point.

    The worklist is written by the driver in the MAIN process BEFORE any
    airport build starts (``driver._write_object_anchor_worklist``,
    amendment A5), so a build worker can read it; and it is the SAME file
    ``rebake_dsf_objects`` reads, so the emitter and the y-bake can never
    disagree about which packs an airport has.  No worklist — the
    standalone patch build, a tile with no object packs — means no pads,
    which is exactly what the sidecar-reading consumer did before it.
    """
    path = os.path.join(patch_dir or "", OBJECT_ANCHOR_WORKLIST_FILENAME)
    try:
        with open(path) as handle:
            worklist = json.load(handle)
    except (OSError, ValueError):
        return []
    memo_key = (os.path.realpath(path), str(icao or "").upper(),
                claims_placement is not None)
    hit = _PAD_FRAME_MEMO.get(memo_key)
    if hit is not None:
        return list(hit)
    frames: list = []
    for entry in worklist.get("airports") or ():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("icao") or "").upper() != str(icao or "").upper():
            continue
        dsf_path = entry.get("dsf_path")
        if not dsf_path or not os.path.isfile(dsf_path):
            continue
        try:
            frames.extend(pad_frames_for_airport(
                dsf_path,
                entry.get("pack_root"),
                entry.get("xplane_root") or worklist.get("xplane_root"),
                claims_placement=claims_placement,
            ))
        except Exception as exception:            # pragma: no cover
            # Per-pack containment, the rebake's own posture: one broken
            # pack never fails an airport's terrain.
            UI.vprint(2, f"  [object-pads] {icao}: pad frame for "
                         f"{os.path.basename(str(dsf_path))} failed "
                         f"({exception}); continuing")
    _PAD_FRAME_MEMO[memo_key] = list(frames)
    return frames


def _merge_cluster_counts(decisions: list) -> dict:
    """Sum the per-pool per-cluster seating counts for the run record
    (spec section 3.5: reporting only)."""
    merged: dict[str, int] = {}
    for _pool, decision in decisions:
        for name, value in (decision.cluster_counts or {}).items():
            merged[name] = merged.get(name, 0) + value
    return merged


def _resolve_pack_geometry(
    placements,
    placement_count_by_resource: dict[str, int],
    pack_root: str,
    xplane_root: str | None,
    skipped: list,
    *,
    apply_reach_floor: bool = True,
) -> tuple[dict[str, str], dict, dict[str, str]]:
    """Resolve every placement's ``.obj``, load its AUTHORED geometry and
    apply the discovery-level admission rules.  Returns
    ``(resolved_paths, geometry_by_resource, geometry_source_by_resource)``
    and appends skip-and-report entries to ``skipped``.

    ONE implementation for both Phase 2 paths — the generic y-bake and
    the section-2.2 basin rim-flush pass — so the safety guards
    (amendment A15's outside-the-pack refusal, ruling R1's read from
    ``.anchor_bak``, invariant I-4's multi-placement refusal) can never
    hold in one and not the other.

    ``apply_reach_floor`` is the ONE difference between the two callers,
    and it is a law difference, not a tuning knob.  The reach floor asks
    "is this object big enough that a wrong anchor would show?" — the
    generic law's own admission test.  A basin facility is admitted by
    the CLASSIFIER instead (its terrain was cut for it), and its anchor
    sits INSIDE its own body, so its reach is barely half the pit's
    width: the OTHH Drainage bowls measure well under the 25 m floor and
    would be silently dropped by a test that has nothing to say about
    them.
    """
    from .config import (
        DSF_OBJECT_ELEVATED_BASE_M,
        DSF_OBJECT_FOOT_ANCHOR,
        DSF_OBJECT_FOOT_MIN_REACH_M,
        DSF_OBJECT_MIN_REACH_M,
    )

    resolved_paths: dict[str, str] = {}
    geometry_by_resource: dict = {}
    geometry_source_by_resource: dict[str, str] = {}
    for resource_path in sorted(
        {placement.resource_path for placement in placements}
    ):
        physical_path = obj8_reader.resolve_object_resource(
            resource_path, pack_root, xplane_root
        )
        if physical_path is None:
            continue
        # Amendment A15, guard 2: a library-resolved resource lives in
        # ANOTHER pack; baking it would push one airport's offsets into
        # an object shared by many.  Skip-and-report.
        if not _resolved_path_is_inside_pack(physical_path, pack_root):
            skipped.append(
                (
                    resource_path,
                    "resolved through library.txt outside the pack — "
                    "shared library objects are never rebaked "
                    "(amendment A15)",
                )
            )
            continue
        # Ruling R1: geometry is ALWAYS read from the backup when one
        # exists — on a re-run the live file already carries baked
        # offsets, and parsing it would misclassify every corrected
        # structure as elevated (its base y is no longer 0).  The
        # rebake writer makes the same choice (``object_rebake.apply``
        # reads ``<name>.anchor_bak``); vertex ordering is identical in
        # both files, so the per-vertex deltas line up.
        backup_path = physical_path + object_rebake.BACKUP_SUFFIX
        geometry_source_path = (
            backup_path if os.path.isfile(backup_path) else physical_path
        )
        geometry = dsf_reader._load_object_geometry(geometry_source_path)
        if geometry is None or not geometry.has_solid_geometry:
            continue
        # The reach floor keeps compact, correctly anchored objects out
        # of Phase 2 — but an author-BAKED vertical offset breaks the
        # metric's premise: X-Plane mis-places such an object no matter
        # how compact it is (the KBNA stairs reach 24.3 m and 20.6 m,
        # under the floor).  Baked-offset geometry — lowest solid vertex
        # above the elevated threshold — is admitted at the reduced
        # foot-re-anchor floor instead (config rationale at
        # DSF_OBJECT_FOOT_MIN_REACH_M).
        if apply_reach_floor:
            minimum_solid_y = min(
                geometry.vertices[vertex_index][1]
                for triangle in geometry.solid_triangles
                for vertex_index in triangle
            )
            reach_floor_metres = (
                DSF_OBJECT_FOOT_MIN_REACH_M
                if DSF_OBJECT_FOOT_ANCHOR
                and minimum_solid_y > DSF_OBJECT_ELEVATED_BASE_M
                else DSF_OBJECT_MIN_REACH_M
            )
            if geometry.solid_reach_metres() < reach_floor_metres:
                # SKIP-AND-REPORT, never a bare ``continue`` (basin-group-
                # seat spec §2.4, trap T5): this drop used to be the one
                # silent fate in Phase 2 discovery, so a resource that
                # never reached a decision left no trace of WHY.  The
                # entry is data for the caller's report; nothing about
                # the drop itself changes.
                skipped.append(
                    (
                        resource_path,
                        f"solid reach {geometry.solid_reach_metres():.1f} m "
                        f"is under the {reach_floor_metres:.1f} m floor — "
                        "a compact object whose anchor error would not "
                        "show is left at its authored y",
                    )
                )
                continue
        # Invariant I-4, enforced at Phase 2 discovery (amendment A13):
        # a resource with several terrain-draped placements would need a
        # different correction per placement, which one shared file
        # cannot carry.  Phase 1 accepts the same resource (N placements
        # = N buildings, invariant I-5); Phase 2 must not.
        placement_count = placement_count_by_resource[resource_path]
        if placement_count > 1:
            skipped.append(
                (
                    resource_path,
                    f"{placement_count} terrain-draped OBJECT placements "
                    "— a shared file cannot carry per-placement offsets "
                    "(invariant I-4)",
                )
            )
            continue
        resolved_paths[resource_path] = physical_path
        geometry_by_resource[resource_path] = geometry
        geometry_source_by_resource[resource_path] = geometry_source_path
    return resolved_paths, geometry_by_resource, geometry_source_by_resource


def _basin_facility_rim_sample_ring(
    body_rings_longitude_latitude,
    origin_latitude: float,
    origin_longitude: float,
) -> tuple[list, list]:
    """``R_mesh``'s SAMPLE RING for one basin facility (spec section 2.2
    item 5): the facility body outline offset OUTWARD by
    ``_TUNNEL_RIM_BAND_WIDTH_M + 1.0`` m — the first terrain outside our
    own plates — sampled every ``<= 10`` m.

    Returns ``(sample_points_latitude_longitude, body_frame_parts)``; the
    parts are returned for the caller's diagnostics.  Pure geometry: no
    mesh is touched here, so the caller can size its sampler from the
    ring before building one.
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    # The band width and the sample step are the EMITTER's constants —
    # imported, never re-spelled: R_mesh has to land on the ground just
    # outside the very band the emitter laid, and a private copy of
    # either number is a second band.
    from .object_terrain_assembly import (
        _BASIN_RIM_SAMPLE_STEP_M,
        _TUNNEL_RIM_BAND_WIDTH_M,
    )

    body_parts: list = []
    for ring in body_rings_longitude_latitude:
        points = [
            obj8_reader.lonlat_to_local_offset(
                origin_latitude, origin_longitude, 0.0, latitude, longitude
            )
            for longitude, latitude in ring
        ]
        if len(points) < 3:
            continue
        try:
            polygon = Polygon(points)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
        except Exception:
            continue
        for part in getattr(polygon, "geoms", [polygon]):
            if part.geom_type == "Polygon" and not part.is_empty:
                body_parts.append(part)
    if not body_parts:
        return [], []
    try:
        body = unary_union(body_parts)
        band = body.buffer(
            _TUNNEL_RIM_BAND_WIDTH_M + 1.0, join_style=2, mitre_limit=2.0
        )
    except Exception:
        return [], body_parts

    sample_points: list = []
    for part in getattr(band, "geoms", [band]):
        exterior = getattr(part, "exterior", None)
        if exterior is None:
            continue
        length = float(exterior.length)
        if not (length > 0.0):
            continue
        step_count = max(
            4, int(math.ceil(length / _BASIN_RIM_SAMPLE_STEP_M))
        )
        for index in range(step_count):
            point = exterior.interpolate(length * index / step_count)
            sample_points.append(
                obj8_reader.local_offset_to_lonlat(
                    origin_latitude, origin_longitude, 0.0,
                    point.x, point.y,
                )
            )
    return sample_points, body_parts


def _bake_basin_rim_flush_facilities(
    facilities,
    all_placements,
    pack_root: str,
    xplane_root: str | None,
    mesh_path: str,
    *,
    epsilon_metres: float,
    write_changes: bool,
    measure_only: bool,
    result: dict,
) -> None:
    """THE BASIN RIM-FLUSH SEAT (docs/specs/basin-rim-flush-seating-spec.md
    section 2.2, ACTIVATED by the owner's 2026-08-09 in-sim verdict).

    The section-2.1e experiment cut the trenches and left the objects
    draped, and the sim answered: the anchor-INSIDE facilities "are sunk
    below the bottom of their trench" — a draped object seats on the
    terrain at its anchor, and with the anchor pillar gone that terrain
    IS the trench floor.  The anchor-OUTSIDE facilities "look just
    right" and are out of scope (item 6): they drape on neighbour
    terrain, measured within 0.4 m, and a regression there is a defect.

    Per anchor-inside facility, one dedicated law::

        R_mesh = median BUILT-MESH elevation on the body outline offset
                 outward by (_TUNNEL_RIM_BAND_WIDTH_M + 1.0) m, every
                 <= 10 m
        delta  = R_mesh - mesh_at_anchor

    applied WHOLE-FACILITY-RIGIDLY: one seat target for every member
    shell, each member's own delta measured from its OWN anchor's ground
    (invariant I-3), so every member's ``y = 0`` plane — the authored rim
    plane, recon section 1 — lands on ``R_mesh``.  The generic
    median/A3/threshold arithmetic never runs here: these resources were
    filtered out of the generic discovery, and the delta is metres by
    construction (the trench is metres deep), which is what the reseat
    threshold's "units >= 1 m reseat" already says about them.

    ``measure_only`` (the tile's ``modify_custom_airports`` switch off)
    is honoured exactly as the generic law honours it: the decision is
    computed and RECORDED, no delta is produced, nothing is written to
    the pack, and ``object_rebake.apply`` still runs so a previously
    baked pack converges back to its authored bytes.
    """
    if not facilities:
        return

    from dataclasses import replace
    from statistics import median

    from .config import (
        TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M,
        TUNNEL_FLOOR_BELOW_OBJECT_DECK_M,
    )
    from .object_terrain_assembly import BASIN_RIM_FLUSH_DECISION_KIND

    placement_count_by_resource: dict[str, int] = {}
    for placement in all_placements:
        placement_count_by_resource[placement.resource_path] = (
            placement_count_by_resource.get(placement.resource_path, 0) + 1
        )

    for facility in facilities:
        member_resources = set(facility.object_resources)
        record = {
            "resources": sorted(member_resources),
            "anchor_longitude_latitude": list(
                facility.anchor_longitude_latitude),
            "anchor_inside_body": bool(facility.anchor_inside_body),
            "solid_minimum_y_m": float(facility.solid_minimum_y_m),
            "measure_only": bool(measure_only),
            "baked": False,
            "decision_kind": BASIN_RIM_FLUSH_DECISION_KIND,
        }
        result["basin_rim_flush"].append(record)

        if not facility.anchor_inside_body:
            # Item 6: measured correct in-sim; left draped, untouched.
            record["decision"] = (
                "not baked — the facility anchor lies OUTSIDE its body, "
                "so the object drapes on neighbour terrain (spec section "
                "2.2 item 6)"
            )
            continue

        member_placements = [
            placement
            for placement in all_placements
            if placement.resource_path in member_resources
        ]
        if not member_placements:
            record["decision"] = (
                "not baked — no member placement in this DSF")
            continue

        skipped: list = []
        (
            resolved_paths,
            geometry_by_resource,
            geometry_source_by_resource,
        ) = _resolve_pack_geometry(
            member_placements,
            placement_count_by_resource,
            pack_root,
            xplane_root,
            skipped,
            # The classifier admitted this facility; the generic law's
            # size test has nothing to say about it (see the helper).
            apply_reach_floor=False,
        )
        result["skipped"].extend(skipped)
        if not resolved_paths:
            record["decision"] = (
                "not baked — no usable member geometry resolved inside "
                "the pack")
            continue

        origin_longitude, origin_latitude = (
            facility.anchor_longitude_latitude)
        sample_points, _body_parts = _basin_facility_rim_sample_ring(
            facility.body_rings_longitude_latitude,
            origin_latitude,
            origin_longitude,
        )
        if not sample_points:
            record["decision"] = (
                "not baked — the facility body outline is degenerate, so "
                "no rim band could be built")
            continue

        latitudes = [latitude for latitude, _longitude in sample_points]
        longitudes = [longitude for _latitude, longitude in sample_points]
        for placement in member_placements:
            latitudes.append(placement.latitude)
            longitudes.append(placement.longitude)
        bounds = (
            min(longitudes), min(latitudes),
            max(longitudes), max(latitudes),
        )
        try:
            sampler = MeshElevationSampler(mesh_path, bounds)
        except (ValueError, OSError) as error:
            # Invariant I-13: no mesh here means no answer, never a
            # plausible one.
            record["decision"] = (
                f"not baked — no mesh under the facility ({error})")
            for placement in member_placements:
                result["skipped"].append(
                    (
                        placement.resource_path,
                        f"basin rim-flush: no mesh triangles under the "
                        f"facility ({error})",
                    )
                )
            continue

        rim_samples = []
        for latitude, longitude in sample_points:
            elevation = sampler.elevation_at_or_none(latitude, longitude)
            if elevation is not None and elevation == elevation:
                rim_samples.append(float(elevation))
        if not rim_samples:
            record["decision"] = (
                "not baked — the built mesh answered nowhere on the rim "
                "band, so R_mesh is unmeasured (never guessed)")
            for placement in member_placements:
                result["skipped"].append(
                    (
                        placement.resource_path,
                        "basin rim-flush: no built-mesh sample on the rim "
                        "band — R_mesh unmeasured, facility left unbaked",
                    )
                )
            continue
        rim_mesh_elevation = float(median(rim_samples))
        record["r_mesh_m"] = rim_mesh_elevation
        record["rim_sample_count"] = len(rim_samples)

        anchor_ground_by_resource: dict[str, float] = {}
        anchor_by_resource: dict[str, tuple[float, float, float]] = {}
        unmeasured_anchor = None
        for placement in member_placements:
            if placement.resource_path not in resolved_paths:
                continue
            anchor_ground = sampler.elevation_at_or_none(
                placement.latitude, placement.longitude
            )
            if anchor_ground is None:
                unmeasured_anchor = placement.resource_path
                break
            # Amendment A18: an OBJECT_AGL placement puts y = 0 at
            # terrain(anchor) + elevation.
            anchor_ground_by_resource[placement.resource_path] = (
                anchor_ground + placement.above_ground_level_metres
            )
            anchor_by_resource[placement.resource_path] = (
                placement.latitude,
                placement.longitude,
                placement.heading_degrees,
            )
        if unmeasured_anchor is not None or not anchor_ground_by_resource:
            record["decision"] = (
                "not baked — a member anchor lies outside the built mesh "
                f"({unmeasured_anchor}); never nearest-vertex sampled "
                "(invariant I-13)")
            for placement in member_placements:
                result["skipped"].append(
                    (
                        placement.resource_path,
                        "basin rim-flush: a member anchor lies outside "
                        "the built mesh — facility left unbaked "
                        "(invariant I-13)",
                    )
                )
            continue

        # The trench FLOOR as built: the terrain a draped member seats
        # on is the floor pan, so the measured anchor ground IS the
        # floor (that is the whole content of the owner's verdict).
        floor_elevation = min(anchor_ground_by_resource.values())
        record["mesh_at_anchor_m"] = floor_elevation
        record["delta_m"] = rim_mesh_elevation - floor_elevation

        # ── ITEM 7 — CLEARANCE VERIFICATION, NOT HOPE ──
        # Assert ``R_mesh + y_true_min >= floor + TUNNEL_FLOOR_BELOW_
        # OBJECT_DECK_M - 0.01``: the seated object's deepest solid must
        # still clear the cut floor by the promised margin.  ``R_est``
        # is recovered from the section-2.1 floor law it was the input
        # to (``floor = R_est + y_true_min - DECK - MARGIN``), so the
        # finding can name the measured ``R_mesh - R_est`` the spec asks
        # for without re-deriving a DEM estimate post-mesh.
        true_minimum_y = float(facility.solid_minimum_y_m)
        deck_clearance_m = float(TUNNEL_FLOOR_BELOW_OBJECT_DECK_M)
        seat_margin_m = float(TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M)
        clearance_metres = (
            rim_mesh_elevation + true_minimum_y
            - (floor_elevation + deck_clearance_m)
        )
        rim_estimate = (
            floor_elevation
            + deck_clearance_m
            + seat_margin_m
            - true_minimum_y
        )
        record["clearance_m"] = clearance_metres
        record["rim_estimate_m"] = rim_estimate
        record["r_mesh_minus_r_est_m"] = rim_mesh_elevation - rim_estimate
        record["clearance_finding"] = clearance_metres < -0.01
        if record["clearance_finding"]:
            # Loud, per facility, never silent and never self-corrected:
            # a violation means the margin constant is too small for
            # THIS airport, which is an owner decision.
            UI.vprint(
                0,
                "  [object-anchor] BASIN CLEARANCE FINDING "
                f"{sorted(member_resources)}: seating at R_mesh "
                f"{rim_mesh_elevation:.2f} m leaves the deepest solid "
                f"({true_minimum_y:.2f} m) only "
                f"{clearance_metres + float(deck_clearance_m):.2f} m above "
                f"the built floor {floor_elevation:.2f} m — "
                f"{-clearance_metres:.2f} m short of the promised "
                f"{deck_clearance_m:.2f} m.  "
                "Measured R_mesh - R_est = "
                f"{record['r_mesh_minus_r_est_m']:.2f} m against a "
                f"{seat_margin_m:.2f} m "
                "O4_TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M — the margin is too "
                "small for this airport (reported, never re-derived).",
            )

        pools = object_anchor.discover_object_pools(
            [
                placement
                for placement in member_placements
                if placement.resource_path in resolved_paths
            ],
            resolved_paths,
            geometry_by_resource,
            epsilon_metres=epsilon_metres,
        )
        baked_resources: list[str] = []
        for pool in pools:
            pool_geometry_by_resource = {
                resource_path: geometry_by_resource[resource_path]
                for resource_path in pool.resolved_paths
            }
            structures = _cached_partition_structures(
                pool,
                pool_geometry_by_resource,
                geometry_source_by_resource,
                pack_root,
                epsilon_metres,
            )
            delta_by_resource_and_vertex: dict[str, dict[int, float]] = {}
            decision_structures = []
            for structure in structures:
                if measure_only:
                    decision_structures.append(
                        replace(
                            structure,
                            skip_reason=(
                                "modify_custom_airports is off — "
                                "measure-only run: the basin_rim_flush "
                                "seat was computed and recorded, the "
                                "pack is not modified"
                            ),
                        )
                    )
                    continue
                decision_structures.append(structure)
                for resource_path, triangles in (
                    structure.triangles_by_resource.items()
                ):
                    if resource_path not in anchor_ground_by_resource:
                        continue
                    # WHOLE-FACILITY RIGID: one seat target, each
                    # member's delta from its own anchor ground.
                    delta = (
                        rim_mesh_elevation
                        - anchor_ground_by_resource[resource_path]
                    )
                    resource_deltas = (
                        delta_by_resource_and_vertex.setdefault(
                            resource_path, {})
                    )
                    for triangle in triangles:
                        for vertex_index in triangle:
                            resource_deltas[vertex_index] = delta
            pool_resources = set(pool.resolved_paths)
            decision = object_anchor.RebakeDecision(
                structures=decision_structures,
                delta_by_resource_and_vertex=delta_by_resource_and_vertex,
                # Scoped to THIS pool: ``object_rebake.apply``'s
                # reversion pass un-bakes every resource a decision
                # "knows" but did not write, and a facility's second
                # pool is not this decision's business.
                anchor_ground_by_resource={
                    resource_path: ground
                    for resource_path, ground
                    in anchor_ground_by_resource.items()
                    if resource_path in pool_resources
                },
                skipped=[],
                anchor_by_resource={
                    resource_path: anchor
                    for resource_path, anchor
                    in anchor_by_resource.items()
                    if resource_path in pool_resources
                },
                decision_kind_by_resource={
                    resource_path: BASIN_RIM_FLUSH_DECISION_KIND
                    for resource_path in delta_by_resource_and_vertex
                },
            )
            result["decisions"].append((pool, decision))
            if write_changes:
                report = object_rebake.apply(decision, pack_root, mesh_path)
                result["objects_written"].extend(report.objects_written)
                result["vertices_offset"] += report.vertices_offset_total
                result["structures_baked"] += report.structures_baked
                result["structures_needing_pad"] += (
                    report.structures_needing_pad
                )
                result["skipped"].extend(report.skipped)
                result["objects_reverted"].extend(report.objects_reverted)
                result["reversions_missing_backup"].extend(
                    report.reversions_missing_backup
                )
                result["partially_baked"].extend(report.partially_baked)
                baked_resources.extend(report.objects_written)
            else:
                result["structures_baked"] += sum(
                    1
                    for structure in decision_structures
                    if structure.skip_reason is None
                )
                baked_resources.extend(
                    sorted(delta_by_resource_and_vertex))
        # "baked" means the pack was WRITTEN.  A dry run computes the
        # same seat and writes nothing, and saying otherwise would put a
        # bake in a report that never touched a file.
        record["baked"] = bool(baked_resources) and write_changes
        record["dry_run"] = not write_changes
        record["objects_written"] = sorted(set(baked_resources))
        if measure_only:
            record["decision"] = (
                "measure-only (modify_custom_airports off): "
                f"basin_rim_flush seat at R_mesh {rim_mesh_elevation:.2f} "
                f"m recorded, delta {record['delta_m']:.2f} m NOT written")
        else:
            record["decision"] = (
                ("basin_rim_flush (dry run, nothing written): would seat "
                 if not write_changes else "basin_rim_flush: seated ")
                + f"at R_mesh {rim_mesh_elevation:.2f} m, delta "
                f"{record['delta_m']:.2f} m over "
                f"{len(record['objects_written'])} object file(s)")
        UI.vprint(
            1,
            f"  [object-anchor] basin_rim_flush {sorted(member_resources)}: "
            + record["decision"],
        )


def _facility_body_polygon(body_rings_longitude_latitude):
    """The facility BODY as one shapely geometry in ``(longitude,
    latitude)`` degrees, or ``None`` when the rings degenerate.

    Degrees, not metres: the group-membership test compares this body
    against structure hulls built in the same degree frame, and a body
    that travelled through a metre frame and back would be a second
    reading of the ring the classifier already fixed."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    parts = []
    for ring in body_rings_longitude_latitude:
        if len(ring) < 3:
            continue
        try:
            polygon = Polygon([(float(longitude), float(latitude))
                               for longitude, latitude in ring])
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
        except Exception:
            continue
        if polygon.is_empty:
            continue
        parts.append(polygon)
    if not parts:
        return None
    try:
        body = unary_union(parts)
    except Exception:
        return None
    return None if body.is_empty else body


def _bounds_overlap(first, second) -> bool:
    """Axis-aligned ``(min_x, min_y, max_x, max_y)`` overlap test."""
    return not (
        first[2] < second[0]
        or second[2] < first[0]
        or first[3] < second[1]
        or second[3] < first[1]
    )


def _structure_plan_bounds(
    structure, geometry_by_resource, placement_by_resource
) -> tuple[float, float, float, float] | None:
    """A cheap SUPERSET bound of one structure's plan extent, in
    ``(min_longitude, min_latitude, max_longitude, max_latitude)``.

    Per member resource: the axis-aligned box of its local ``(x, z)``
    vertices (pure arithmetic, no projection), whose four corners are
    then projected through that resource's own placement.  The projected
    corners are the corners of the ROTATED box, so their bound contains
    every projected vertex — which is all a prefilter must guarantee.
    Returns ``None`` when nothing projects."""
    minimum_longitude = minimum_latitude = math.inf
    maximum_longitude = maximum_latitude = -math.inf
    for resource_path, triangles in structure.triangles_by_resource.items():
        geometry = geometry_by_resource.get(resource_path)
        placement = placement_by_resource.get(resource_path)
        if geometry is None or placement is None or not triangles:
            continue
        minimum_x = minimum_z = math.inf
        maximum_x = maximum_z = -math.inf
        vertices = geometry.vertices
        for triangle in triangles:
            for vertex_index in triangle:
                local_x, _local_y, local_z = vertices[vertex_index]
                if local_x < minimum_x:
                    minimum_x = local_x
                if local_x > maximum_x:
                    maximum_x = local_x
                if local_z < minimum_z:
                    minimum_z = local_z
                if local_z > maximum_z:
                    maximum_z = local_z
        if minimum_x > maximum_x:
            continue
        for corner_x, corner_z in (
            (minimum_x, minimum_z),
            (maximum_x, minimum_z),
            (maximum_x, maximum_z),
            (minimum_x, maximum_z),
        ):
            latitude, longitude = obj8_reader.local_offset_to_lonlat(
                placement.latitude,
                placement.longitude,
                placement.heading_degrees,
                corner_x,
                corner_z,
            )
            minimum_longitude = min(minimum_longitude, longitude)
            maximum_longitude = max(maximum_longitude, longitude)
            minimum_latitude = min(minimum_latitude, latitude)
            maximum_latitude = max(maximum_latitude, latitude)
    if minimum_longitude > maximum_longitude:
        return None
    return (
        minimum_longitude, minimum_latitude,
        maximum_longitude, maximum_latitude,
    )


def _structure_reaches_body(
    structure, geometry_by_resource, placement_by_resource, body, body_bounds
) -> bool:
    """Whether one partition structure's HORIZONTAL FOOTPRINT reaches the
    facility body (basin-group-seat spec §2.2).

    Two stages, and the cheap one runs first: the projected plan bound
    above rejects the thousands of structures nowhere near the pit
    without touching shapely, and only a surviving candidate pays for the
    convex hull of its projected vertices — the same footprint reading
    ``object_footprints.structure_ring`` takes by default."""
    from shapely.geometry import MultiPoint

    bounds = _structure_plan_bounds(
        structure, geometry_by_resource, placement_by_resource)
    if bounds is None or not _bounds_overlap(bounds, body_bounds):
        return False
    points: list[tuple[float, float]] = []
    for resource_path, triangles in structure.triangles_by_resource.items():
        geometry = geometry_by_resource.get(resource_path)
        placement = placement_by_resource.get(resource_path)
        if geometry is None or placement is None:
            continue
        seen: set[int] = set()
        vertices = geometry.vertices
        for triangle in triangles:
            for vertex_index in triangle:
                if vertex_index in seen:
                    continue
                seen.add(vertex_index)
                local_x, _local_y, local_z = vertices[vertex_index]
                latitude, longitude = obj8_reader.local_offset_to_lonlat(
                    placement.latitude,
                    placement.longitude,
                    placement.heading_degrees,
                    local_x,
                    local_z,
                )
                points.append((longitude, latitude))
    if not points:
        return False
    try:
        footprint = MultiPoint(points).convex_hull
        return bool(body.intersects(footprint))
    except Exception:
        return False


def _seat_group_structures(
    pools,
    structures_by_pool_index,
    geometry_by_resource,
    placement_by_resource,
    body,
    body_bounds,
    seed_resources,
) -> dict[int, list]:
    """THE SEAT GROUP: ``{pool index: [structures]}`` (spec §2.2).

    Seeded by every partition structure whose footprint intersects the
    body — plus every structure carrying one of ``seed_resources``, the
    facility's own interface members, so a member the classifier already
    withheld from the generic pass can never end up withheld AND unseated
    (the pre-amendment failure mode this docket exists to end).

    Then CLOSED over two relations, because neither may be torn: a
    structure is one rigid body, and a shared-datum ``.obj`` file is one
    authored body — so a resource in the group brings ALL of its
    structures, and a structure in the group brings all of its resources.
    The closure is the reason "one delta per member, total" is
    implementable at all; without it a file could take the group delta
    over the vertices inside the pit and its authored y everywhere else,
    which is the same tear one level down."""
    group_by_pool: dict[int, list] = {}
    for pool_index, pool in enumerate(pools):
        structures = structures_by_pool_index.get(pool_index)
        if not structures:
            continue
        structures_by_resource: dict[str, list] = {}
        for structure in structures:
            for resource_path in structure.triangles_by_resource:
                structures_by_resource.setdefault(
                    resource_path, []).append(structure)
        selected: list = []
        selected_ids: set[int] = set()
        pending: list = []
        for structure in structures:
            seeded = any(
                resource_path in seed_resources
                for resource_path in structure.triangles_by_resource
            )
            if seeded or _structure_reaches_body(
                structure, geometry_by_resource, placement_by_resource,
                body, body_bounds,
            ):
                pending.append(structure)
        seen_resources: set[str] = set()
        while pending:
            structure = pending.pop()
            if id(structure) in selected_ids:
                continue
            selected_ids.add(id(structure))
            selected.append(structure)
            for resource_path in structure.triangles_by_resource:
                if resource_path in seen_resources:
                    continue
                seen_resources.add(resource_path)
                pending.extend(
                    structures_by_resource.get(resource_path, ()))
        if selected:
            group_by_pool[pool_index] = selected
    return group_by_pool


def _bake_basin_group_seat_facilities(
    facilities,
    all_placements,
    pack_root: str,
    xplane_root: str | None,
    mesh_path: str,
    *,
    epsilon_metres: float,
    write_changes: bool,
    measure_only: bool,
    result: dict,
    reserved_resources: set[str] | None = None,
) -> set[str]:
    """THE BASIN GROUP SEAT (docs/specs/basin-group-seat-spec.md, docket
    B of the basin-region round; ``config.BASIN_GROUP_SEAT``).

    A shared-datum pack authors every inter-object vertical relationship
    through ONE flat drape.  The section-2.2 rim-flush law seats the
    facility's interface members onto ``R_mesh`` and leaves everything
    else to the generic pass, so at LEMD T4S one member seated at anchor
    ground 595.97 while its neighbours cluster-seated at 597.52 — a
    1.544 m two-instrument gap at one identical point — four structures
    A3-skipped, and an 8.95 m cut seam INSIDE the fused terminal complex
    whose below-grade decks must stay −2/−3/−7 relative to it.

    The law, the R12-2 bridge seat's shape applied to basins::

        SEAT GROUP = every partition structure whose horizontal footprint
                     intersects the facility body (closed over structures
                     and files — see :func:`_seat_group_structures`)
        G          = R_mesh          (the §2.2 rim-band median, unchanged)
        delta(member) = G − anchor_ground(member)

    so every member ends with ``mesh(anchor) + delta == G`` exactly and
    every authored pairwise relationship survives.  THE ONE INSTRUMENT
    (trap T7): every ``anchor_ground`` here is read by THIS pass's
    sampler in one pass — the generic pass's ground for those anchors is
    never consulted, because those anchors never reach the generic pass:
    the group is widened into SEATED and withheld-from-generic in the
    same step (the LSGG starvation law), which is what the returned
    claim set is for.

    Item 6 is a THRESHOLD, not a topology (spec §2.3 item 2): a group
    whose every ``|delta|`` is under ``DSF_OBJECT_BAKE_MIN_DELTA_M`` is a
    RECORDED no-op — which reproduces the OTHH anchor-outside
    measurement (drape correct to ≤ 0.4 m) while fixing LEMD, where the
    drape at the datum misses the rim by ~1.5 m.

    ``reserved_resources`` are the resources another dedicated law has
    already claimed this run (the R6-3 bridge abutment seat, which runs
    first).  They are dropped from this pass's population before
    anything is partitioned, so no object can ever be reached by two
    seating laws — the same disjointness the generic pass gets from the
    claim set this function returns.

    Returns the set of resource paths this law CLAIMED — seated or
    no-op'd — for the caller to withhold from the generic pass.
    """
    if not facilities:
        return set()

    from dataclasses import replace
    from statistics import median

    from .config import (
        DSF_OBJECT_BAKE_MIN_DELTA_M,
        TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M,
        TUNNEL_FLOOR_BELOW_OBJECT_DECK_M,
    )
    from .object_terrain_assembly import BASIN_GROUP_SEAT_DECISION_KIND

    claimed_resources: set[str] = set()

    placement_count_by_resource: dict[str, int] = {}
    for placement in all_placements:
        placement_count_by_resource[placement.resource_path] = (
            placement_count_by_resource.get(placement.resource_path, 0) + 1
        )
    reserved = set(reserved_resources or ())
    population = [
        placement
        for placement in all_placements
        if placement.resource_path not in reserved
    ]

    # ONE discovery for the whole DSF.  The seat group is defined over
    # partition structures, and the structures that matter here include
    # both the R4-excluded facility members (which the generic discovery
    # never sees) and their at-grade neighbours (which it does) — so the
    # population is every placement, admitted by the CLASSIFIER's
    # judgement rather than the generic law's reach floor (the helper's
    # own docstring: a basin facility's reach says nothing about it).
    discovery_skipped: list = []
    (
        resolved_paths,
        geometry_by_resource,
        geometry_source_by_resource,
    ) = _resolve_pack_geometry(
        population,
        placement_count_by_resource,
        pack_root,
        xplane_root,
        discovery_skipped,
        apply_reach_floor=False,
    )
    skip_reason_by_resource = {
        resource_path: reason for resource_path, reason in discovery_skipped
    }
    if not resolved_paths:
        for facility in facilities:
            result["basin_group_seat"].append({
                "resources": sorted(facility.object_resources),
                "baked": False,
                "decision_kind": BASIN_GROUP_SEAT_DECISION_KIND,
                "decision": (
                    "not baked — no usable geometry resolved inside the "
                    "pack"),
            })
        return claimed_resources

    placement_by_resource = {
        placement.resource_path: placement
        for placement in population
        if placement.resource_path in resolved_paths
    }
    pools = object_anchor.discover_object_pools(
        [
            placement
            for placement in population
            if placement.resource_path in resolved_paths
        ],
        resolved_paths,
        geometry_by_resource,
        epsilon_metres=epsilon_metres,
    )
    pool_bounds = [
        _pool_world_bounds(
            pool,
            {
                resource_path: geometry_by_resource[resource_path]
                for resource_path in pool.resolved_paths
            },
        )
        for pool in pools
    ]
    # Partitions are computed ONCE per pool and only for pools that can
    # reach a body — the partition is the expensive half of Phase 2, and
    # a pool two kilometres from every pit can be rejected on its bounds.
    structures_by_pool_index: dict[int, list] = {}

    for facility in facilities:
        member_resources = set(facility.object_resources)
        record = {
            "resources": sorted(member_resources),
            "anchor_longitude_latitude": list(
                facility.anchor_longitude_latitude),
            "anchor_inside_body": bool(facility.anchor_inside_body),
            "solid_minimum_y_m": float(facility.solid_minimum_y_m),
            "measure_only": bool(measure_only),
            "baked": False,
            "decision_kind": BASIN_GROUP_SEAT_DECISION_KIND,
        }
        result["basin_group_seat"].append(record)

        # §2.4 (trap T5): an interface member the discovery dropped is
        # LOUD and named against its facility.  A multi-placement member
        # keeps its I-4 skip — one shared file cannot carry per-placement
        # offsets — but it is no longer silent to the facility whose
        # relationships it is missing from.
        for resource_path in sorted(member_resources):
            if resource_path in resolved_paths:
                continue
            reason = skip_reason_by_resource.get(
                resource_path,
                "no geometry resolved inside the pack")
            UI.vprint(
                0,
                "  [object-anchor] BASIN GROUP SEAT: facility member "
                f"{resource_path} is NOT in the seat group of the basin "
                f"at {facility.anchor_longitude_latitude} — {reason}",
            )

        body = _facility_body_polygon(
            facility.body_rings_longitude_latitude)
        if body is None:
            record["decision"] = (
                "not baked — the facility body outline is degenerate, so "
                "no seat group could be formed")
            continue
        body_bounds = body.bounds

        for pool_index, pool in enumerate(pools):
            if pool_index in structures_by_pool_index:
                continue
            if not _bounds_overlap(pool_bounds[pool_index], body_bounds):
                continue
            pool_geometry_by_resource = {
                resource_path: geometry_by_resource[resource_path]
                for resource_path in pool.resolved_paths
            }
            structures_by_pool_index[pool_index] = (
                _cached_partition_structures(
                    pool,
                    pool_geometry_by_resource,
                    geometry_source_by_resource,
                    pack_root,
                    epsilon_metres,
                )
            )

        group_by_pool = _seat_group_structures(
            pools,
            {
                pool_index: structures
                for pool_index, structures in structures_by_pool_index.items()
                if _bounds_overlap(pool_bounds[pool_index], body_bounds)
            },
            geometry_by_resource,
            placement_by_resource,
            body,
            body_bounds,
            member_resources,
        )
        group_resources = {
            resource_path
            for structures in group_by_pool.values()
            for structure in structures
            for resource_path in structure.triangles_by_resource
        }
        record["group_resource_count"] = len(group_resources)
        record["group_structure_count"] = sum(
            len(structures) for structures in group_by_pool.values())
        if not group_resources:
            record["decision"] = (
                "not baked — no partition structure's footprint reaches "
                "this facility body, so there is no seat group")
            continue
        # TWO PITS, ONE RIGID UNIT — reported, never guessed.  The §2.1
        # split makes facility bodies disjoint, so an overlap here means
        # one welded structure (or one shared ``.obj``) reaches into two
        # of them and the two groups are physically the same body with
        # two candidate datums.  Seating it twice would write the file
        # twice and the last writer would silently win, so this facility
        # REFUSES and says so: the correct answer (one merged group, one
        # datum) is a design question for the spec's author, not a
        # tie-break for this pass.
        overlap = sorted(group_resources & claimed_resources)
        if overlap:
            record["decision"] = (
                "not baked — this facility's seat group SHARES "
                f"{len(overlap)} resource(s) with an earlier facility's "
                "group, so one rigid unit reaches two disjoint bodies and "
                "would be seated onto two datums: "
                + ", ".join(overlap[:4]))
            UI.vprint(
                0,
                "  [object-anchor] BASIN GROUP SEAT FINDING: the facility "
                f"at {facility.anchor_longitude_latitude} shares "
                f"{len(overlap)} resource(s) with an earlier facility's "
                "seat group — REFUSED rather than seated onto a second "
                f"datum (first shared: {overlap[0]})",
            )
            continue

        origin_longitude, origin_latitude = (
            facility.anchor_longitude_latitude)
        sample_points, _body_parts = _basin_facility_rim_sample_ring(
            facility.body_rings_longitude_latitude,
            origin_latitude,
            origin_longitude,
        )
        if not sample_points:
            record["decision"] = (
                "not baked — the facility body outline is degenerate, so "
                "no rim band could be built")
            continue

        group_placements = [
            placement_by_resource[resource_path]
            for resource_path in sorted(group_resources)
            if resource_path in placement_by_resource
        ]
        latitudes = [latitude for latitude, _longitude in sample_points]
        longitudes = [longitude for _latitude, longitude in sample_points]
        for placement in group_placements:
            latitudes.append(placement.latitude)
            longitudes.append(placement.longitude)
        bounds = (
            min(longitudes), min(latitudes),
            max(longitudes), max(latitudes),
        )
        try:
            sampler = MeshElevationSampler(mesh_path, bounds)
        except (ValueError, OSError) as error:
            # Invariant I-13: no mesh here means no answer, never a
            # plausible one.
            record["decision"] = (
                f"not baked — no mesh under the facility ({error})")
            continue

        rim_samples = []
        for latitude, longitude in sample_points:
            elevation = sampler.elevation_at_or_none(latitude, longitude)
            if elevation is not None and elevation == elevation:
                rim_samples.append(float(elevation))
        if not rim_samples:
            record["decision"] = (
                "not baked — the built mesh answered nowhere on the rim "
                "band, so G is unmeasured (never guessed)")
            continue
        seat_datum = float(median(rim_samples))
        record["r_mesh_m"] = seat_datum
        record["g_m"] = seat_datum
        record["rim_sample_count"] = len(rim_samples)

        # ── ONE INSTRUMENT (spec §2.3 item 1, trap T7) ────────────
        # Every group anchor's ground is read HERE, by this sampler, in
        # one pass.  The 1.544 m gap the recon measured at LEMD was two
        # instruments answering at one identical point; there is now one.
        anchor_ground_by_resource: dict[str, float] = {}
        anchor_by_resource: dict[str, tuple[float, float, float]] = {}
        unmeasured_anchor = None
        for placement in group_placements:
            anchor_ground = sampler.elevation_at_or_none(
                placement.latitude, placement.longitude
            )
            if anchor_ground is None:
                unmeasured_anchor = placement.resource_path
                break
            # Amendment A18: an OBJECT_AGL placement puts y = 0 at
            # terrain(anchor) + elevation.
            anchor_ground_by_resource[placement.resource_path] = (
                anchor_ground + placement.above_ground_level_metres
            )
            anchor_by_resource[placement.resource_path] = (
                placement.latitude,
                placement.longitude,
                placement.heading_degrees,
            )
        if unmeasured_anchor is not None or not anchor_ground_by_resource:
            record["decision"] = (
                "not baked — a group member's anchor lies outside the "
                f"built mesh ({unmeasured_anchor}); never nearest-vertex "
                "sampled (invariant I-13)")
            continue

        delta_by_resource = {
            resource_path: seat_datum - anchor_ground
            for resource_path, anchor_ground
            in anchor_ground_by_resource.items()
        }
        floor_elevation = min(anchor_ground_by_resource.values())
        record["mesh_at_anchor_m"] = floor_elevation
        record["delta_m"] = seat_datum - floor_elevation
        record["delta_by_resource"] = {
            resource_path: float(delta)
            for resource_path, delta in sorted(delta_by_resource.items())
        }
        record["delta_min_m"] = min(delta_by_resource.values())
        record["delta_max_m"] = max(delta_by_resource.values())

        # ── ITEM 6 AS A THRESHOLD (spec §2.3 item 2) ──────────────
        # The topological "anchor-outside facilities do not bake" retires
        # here: what made the OTHH anchor-outside class right was that
        # its drape was ALREADY correct (≤ 0.4 m), i.e. delta ≈ 0 — a
        # measurement, which this says directly.  No new knob: the
        # existing reseat threshold is the same number the generic law
        # uses to decide that a unit is fine where its author put it.
        worst_delta = max(
            abs(delta) for delta in delta_by_resource.values())
        below_threshold = worst_delta < DSF_OBJECT_BAKE_MIN_DELTA_M
        record["threshold_no_op"] = bool(below_threshold)

        # ── ITEM 7 — CLEARANCE VERIFICATION, NOT HOPE ──
        # Unchanged check, wider membership: the group's G is what the
        # deepest modelled solid must still clear the cut floor from.
        true_minimum_y = float(facility.solid_minimum_y_m)
        deck_clearance_m = float(TUNNEL_FLOOR_BELOW_OBJECT_DECK_M)
        seat_margin_m = float(TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M)
        clearance_metres = (
            seat_datum + true_minimum_y
            - (floor_elevation + deck_clearance_m)
        )
        rim_estimate = (
            floor_elevation
            + deck_clearance_m
            + seat_margin_m
            - true_minimum_y
        )
        record["clearance_m"] = clearance_metres
        record["rim_estimate_m"] = rim_estimate
        record["r_mesh_minus_r_est_m"] = seat_datum - rim_estimate
        record["clearance_finding"] = clearance_metres < -0.01
        if record["clearance_finding"]:
            UI.vprint(
                0,
                "  [object-anchor] BASIN CLEARANCE FINDING "
                f"{sorted(member_resources)}: seating at G "
                f"{seat_datum:.2f} m leaves the deepest solid "
                f"({true_minimum_y:.2f} m) only "
                f"{clearance_metres + float(deck_clearance_m):.2f} m above "
                f"the built floor {floor_elevation:.2f} m — "
                f"{-clearance_metres:.2f} m short of the promised "
                f"{deck_clearance_m:.2f} m.  "
                "Measured R_mesh - R_est = "
                f"{record['r_mesh_minus_r_est_m']:.2f} m against a "
                f"{seat_margin_m:.2f} m "
                "O4_TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M — the margin is too "
                "small for this airport (reported, never re-derived).",
            )

        # THE WIDENING IS ONE STEP (trap T1, the LSGG law): the group is
        # claimed here — withheld from the generic pass by the caller —
        # whatever this law then decides, because "excluded" is never
        # widened without "seated".
        claimed_resources.update(group_resources)

        baked_resources: list[str] = []
        for pool_index, structures in sorted(group_by_pool.items()):
            delta_by_resource_and_vertex: dict[str, dict[int, float]] = {}
            decision_structures = []
            for structure in structures:
                if measure_only or below_threshold:
                    decision_structures.append(
                        replace(
                            structure,
                            skip_reason=(
                                "modify_custom_airports is off — "
                                "measure-only run: the basin_group_seat "
                                "seat was computed and recorded, the "
                                "pack is not modified"
                                if measure_only else
                                "basin_group_seat: every group delta is "
                                "under DSF_OBJECT_BAKE_MIN_DELTA_M — the "
                                "family already drapes on its own datum "
                                "plane, so the bake is a recorded no-op "
                                "(spec §2.3 item 2)"
                            ),
                        )
                    )
                    continue
                decision_structures.append(structure)
                for resource_path, triangles in (
                    structure.triangles_by_resource.items()
                ):
                    if resource_path not in delta_by_resource:
                        continue
                    # ONE DATUM PLANE: each member's own delta measured
                    # from its OWN anchor ground (invariant I-3), so
                    # mesh(anchor) + delta == G for every member — and
                    # the delta is TOTAL for the file (§2.4): no
                    # foot-anchor, no inheritance, no per-cluster fate.
                    delta = delta_by_resource[resource_path]
                    resource_deltas = (
                        delta_by_resource_and_vertex.setdefault(
                            resource_path, {})
                    )
                    for triangle in triangles:
                        for vertex_index in triangle:
                            resource_deltas[vertex_index] = delta
            pool_resources = set(pools[pool_index].resolved_paths)
            decision = object_anchor.RebakeDecision(
                structures=decision_structures,
                delta_by_resource_and_vertex=delta_by_resource_and_vertex,
                # Scoped to THIS pool: ``object_rebake.apply``'s
                # reversion pass un-bakes every resource a decision
                # "knows" but did not write.
                anchor_ground_by_resource={
                    resource_path: ground
                    for resource_path, ground
                    in anchor_ground_by_resource.items()
                    if resource_path in pool_resources
                },
                skipped=[],
                anchor_by_resource={
                    resource_path: anchor
                    for resource_path, anchor
                    in anchor_by_resource.items()
                    if resource_path in pool_resources
                },
                decision_kind_by_resource={
                    resource_path: BASIN_GROUP_SEAT_DECISION_KIND
                    for resource_path in delta_by_resource_and_vertex
                },
                # §2.5 / trap T6: the datum plane travels into the
                # provenance sidecar beside the applied delta, so a
                # restored pack can still answer what the group decided.
                seat_datum_by_resource={
                    resource_path: seat_datum
                    for resource_path in delta_by_resource_and_vertex
                },
            )
            result["decisions"].append((pools[pool_index], decision))
            if write_changes:
                report = object_rebake.apply(decision, pack_root, mesh_path)
                result["objects_written"].extend(report.objects_written)
                result["vertices_offset"] += report.vertices_offset_total
                result["structures_baked"] += report.structures_baked
                result["structures_needing_pad"] += (
                    report.structures_needing_pad
                )
                result["skipped"].extend(report.skipped)
                result["objects_reverted"].extend(report.objects_reverted)
                result["reversions_missing_backup"].extend(
                    report.reversions_missing_backup
                )
                result["partially_baked"].extend(report.partially_baked)
                baked_resources.extend(report.objects_written)
            else:
                result["structures_baked"] += sum(
                    1
                    for structure in decision_structures
                    if structure.skip_reason is None
                )
                baked_resources.extend(
                    sorted(delta_by_resource_and_vertex))
        record["baked"] = bool(baked_resources) and write_changes
        record["dry_run"] = not write_changes
        record["objects_written"] = sorted(set(baked_resources))
        if measure_only:
            record["decision"] = (
                "measure-only (modify_custom_airports off): "
                f"basin_group_seat at G {seat_datum:.2f} m over "
                f"{len(group_resources)} member(s) recorded, NOT written")
        elif below_threshold:
            record["decision"] = (
                "basin_group_seat: recorded NO-OP — every group delta "
                f"(max {worst_delta:.2f} m) "
                f"is under the {DSF_OBJECT_BAKE_MIN_DELTA_M:.2f} m reseat "
                "threshold, so the family already drapes on its datum "
                "plane (spec §2.3 item 2)")
        else:
            record["decision"] = (
                ("basin_group_seat (dry run, nothing written): would seat "
                 if not write_changes else "basin_group_seat: seated ")
                + f"{len(group_resources)} member(s) in "
                f"{record['group_structure_count']} structure(s) on ONE "
                f"datum G {seat_datum:.2f} m, deltas "
                f"{record['delta_min_m']:.2f}..{record['delta_max_m']:.2f} m "
                f"over {len(record['objects_written'])} object file(s)")
        UI.vprint(
            1,
            "  [object-anchor] basin_group_seat "
            f"{sorted(member_resources)}: " + record["decision"],
        )
    return claimed_resources


def _candidate_grade_line_sets(candidate) -> list:
    """Every SET of deck-end lines the seat may sample for a candidate,
    as ``[(label, lines), ...]``.

    A CLASSIFIED candidate has exactly one set — its certified pair, the
    R6-3 instrument, untouched by amendment 3.  A REFUSED viaduct has one
    set PER DECK MEMBER (amendment 3, owner ruling): the merged min-rect
    is retired from this limb, and each member's own deck-face ends are
    real bridge ends that touch the banks."""
    member_records = getattr(candidate, "deck_member_records", ()) or ()
    if member_records:
        return [
            (record["resource_path"],
             record["abutment_points_longitude_latitude"])
            for record in member_records
        ]
    return [(None, candidate.abutment_points_longitude_latitude)]


def _abutment_line_frame_points(candidate, lines=None) -> list:
    """Each abutment line's two endpoints in the candidate anchor's local
    METRE frame, as ``[((start_x, start_z), (end_x, end_z)), ...]``.

    The frame is the candidate anchor's — the same two ``obj8_reader``
    projections every other object-terrain consumer uses, so nothing
    re-derives a frame and the sample density below is metres, not
    degrees.  ``lines`` defaults to the candidate's own family-level
    pair; the refused limb passes one member's pair instead."""
    origin_longitude, origin_latitude = candidate.anchor_longitude_latitude
    if lines is None:
        lines = candidate.abutment_points_longitude_latitude
    out: list = []
    for line in lines:
        if len(line) < 2:
            continue
        (start, end) = [
            obj8_reader.lonlat_to_local_offset(
                origin_latitude, origin_longitude, 0.0, latitude, longitude
            )
            for longitude, latitude in line[:2]
        ]
        out.append((start, end))
    return out


def _abutment_line_frame_samples(start, end, offset=(0.0, 0.0)) -> list:
    """One abutment line's sample points in the metre frame, every
    ``_ABUTMENT_GRADE_SAMPLE_STEP_M`` or finer, shifted by ``offset``."""
    from .object_terrain_assembly import _ABUTMENT_GRADE_SAMPLE_STEP_M

    (start_x, start_z), (end_x, end_z) = start, end
    length = math.hypot(end_x - start_x, end_z - start_z)
    step_count = max(
        2, int(math.ceil(length / _ABUTMENT_GRADE_SAMPLE_STEP_M))
    )
    offset_x, offset_z = offset
    out = []
    for index in range(step_count + 1):
        fraction = index / step_count
        out.append((
            start_x + (end_x - start_x) * fraction + offset_x,
            start_z + (end_z - start_z) * fraction + offset_z,
        ))
    return out


def _abutment_grade_sample_points(candidate) -> list:
    """``(latitude, longitude)`` samples along EVERY deck-end line the
    seat may read for this candidate, every
    ``_ABUTMENT_GRADE_SAMPLE_STEP_M`` or finer — the lines exactly as the
    classifier drew them, with no landward walk.

    Every line set (:func:`_candidate_grade_line_sets`) is included, so
    this is also what the mesh-sampler window must cover; the walk then
    reaches up to :data:`_ABUTMENT_LAND_WALK_MAX_M` beyond it."""
    origin_longitude, origin_latitude = candidate.anchor_longitude_latitude
    out: list = []
    for _label, lines in _candidate_grade_line_sets(candidate):
        for start, end in _abutment_line_frame_points(candidate, lines):
            for frame_x, frame_z in _abutment_line_frame_samples(
                start, end
            ):
                out.append(
                    obj8_reader.local_offset_to_lonlat(
                        origin_latitude, origin_longitude, 0.0,
                        frame_x, frame_z,
                    )
                )
    return out


#: WATER NEVER AUTHORS A BRIDGE DATUM (round-12 amendment 2026-08-11).
#: When a deck-end line loses its samples to the mapped water union, it
#: WALKS LANDWARD along the deck axis — away from the span — in
#: ``_ABUTMENT_GRADE_SAMPLE_STEP_M`` increments up to this cap, until at
#: least ``_ABUTMENT_LAND_MIN_SAMPLES`` non-water samples exist.  60 m is
#: the ruled cap: far enough to clear OTHH's canal bank, short enough
#: that the grade is still the bridge's own shore.
_ABUTMENT_LAND_WALK_MAX_M = 60.0
_ABUTMENT_LAND_MIN_SAMPLES = 4

def agreeing_coalition(member_measurements, window_metres,
                       weight_of=None, tiebreak_of=None):
    """THE AGREEING COALITION (round-12 amendment 4).

    Returns ``(coalition, outliers, refusal_reason)``.  ``coalition`` is
    the LARGEST subset of member measurements whose deltas fit inside one
    ``window_metres`` window; ``outliers`` is everything else, in delta
    order.  ``refusal_reason`` is a string when no coalition may seat and
    ``None`` when one may.

    ``weight_of`` (R19-1, 2026-08-12) makes "largest" mean largest
    SUMMED WEIGHT rather than most members — the pad LEVEL-FAMILY caller
    weights each member by its AREA, so a 181 m² pad can never out-vote
    a 15,298 m² one however many small neighbours it brings.  Omitted,
    every member weighs 1 and this is R12's own reading unchanged: the
    bridge-deck caller passes nothing and reads the coalitions it always
    did.

    ``tiebreak_of`` (R19-1) breaks EQUALLY-WEIGHTED rivals by a second
    quantity before the ambiguity refusal fires — the pad caller scores
    rivals by their HOST weight, because that law has an arbitration
    direction of its own ("the pad adopts FROM the host, never the
    reverse"), so a family split evenly between a pad and the host it
    stands on is not ambiguous: the host wins.  Omitted, an even split
    refuses exactly as R12 rules it.

    WHY A COALITION AND NOT A MEDIAN.  Measured at OTHH (amendment 3):
    the members whose deck-face ends land cleanly on the bank read the
    same grade to the millimetre and their deltas agree within 0.05 m,
    while the members whose end lines still cross the canal — picking up
    0.00 m samples on triangles the mesh does not attribute as water,
    B2's known residual — scatter with no two within 0.25 m of each
    other.  AGREEMENT IS THE SIGNATURE OF A REAL MEASUREMENT and scatter
    the signature of an artifact, so the seat is authored by the members
    that agree, not by a median that lets the artifacts vote.

    Two ways to have no coalition, both genuine ambiguity rather than a
    number to lean on:

    * fewer than two members agree anywhere (every member is its own
      island — nothing has been corroborated);
    * two or more DIFFERENT largest windows tie (the assembly has two
      equally-supported stories about its own level).

    Windows are compared by their member SETS, so the two overlapping
    windows of a smoothly-smeared row do count as rivals: a smear is not
    a coalition."""
    if len(member_measurements) < 2:
        return [], list(member_measurements), (
            f"only {len(member_measurements)} deck member(s) could be "
            "measured, so nothing corroborates a seat level")

    ordered = sorted(member_measurements, key=lambda e: e["delta_m"])
    windows: dict = {}
    for start in range(len(ordered)):
        limit = ordered[start]["delta_m"] + window_metres
        members = tuple(
            index
            for index in range(start, len(ordered))
            if ordered[index]["delta_m"] <= limit
        )
        windows[frozenset(members)] = len(members)

    # WHAT "LARGEST" MEANS: member count by default (R12), summed member
    # WEIGHT when the caller supplies one (R19-1's area weighting).  The
    # ≥2-member rule is the same law in both readings — one member is
    # nobody's corroboration, whatever it weighs.
    if weight_of is not None:
        windows = {
            member_set: sum(float(weight_of(ordered[i]))
                            for i in member_set)
            for member_set in windows
        }
    largest = max(windows.values())
    winners = [
        member_set for member_set, size in windows.items()
        if size == largest
    ]
    if max((len(w) for w in winners), default=0) < 2:
        return [], ordered, (
            f"no two of the {len(ordered)} member deltas lie within "
            f"{window_metres:.2f} m of each other, so no measurement is "
            "corroborated")
    if len(winners) > 1 and tiebreak_of is not None:
        scores = {
            member_set: sum(float(tiebreak_of(ordered[i]))
                            for i in member_set)
            for member_set in winners
        }
        best_score = max(scores.values())
        winners = [ms for ms in winners if scores[ms] == best_score]
    if len(winners) > 1:
        return [], ordered, (
            f"{len(winners)} rival groups of {largest} member(s) each "
            f"agree within {window_metres:.2f} m — the assembly has two "
            "equally supported stories about its own level")

    chosen = winners[0]
    coalition = [ordered[index] for index in sorted(chosen)]
    outliers = [
        entry for index, entry in enumerate(ordered) if index not in chosen
    ]
    return coalition, outliers, None


#: ONE AUTHORED ASSEMBLY MUST AGREE WITH ITSELF (round-12 amendment 3).
#: Each deck member of a refused viaduct implies its own seat delta; a
#: window inside which member deltas COUNT AS AGREEING (amendment 4's
#: coalition).  0.25 m is the ruled tolerance — under a step a viewer can
#: see on a bridge deck, well over the mesh-sampling noise between two
#: ends of one structure (OTHH's clean coalition agrees within 0.05 m).
_MEMBER_DELTA_AGREEMENT_WINDOW_M = 0.25


def _abutment_grade_samples_on_land(candidate, sampler, lines=None) -> tuple:
    """The abutment-grade samples that stand on LAND, per deck end, with
    the landward walk the round-12 amendment rules.

    Returns ``(samples, end_records)``: the pooled elevations that may
    author the grade, and one dict per deck end saying how far it walked,
    how many samples it kept and how many it lost to water.

    Per end: sample the line, DISCARD every sample whose MESH TRIANGLE
    carries the water bits, and — if fewer than
    :data:`_ABUTMENT_LAND_MIN_SAMPLES` remain — shift the whole line
    LANDWARD along the deck axis (directly away from the other end,
    which is the span) by one sample step and try again, up to
    :data:`_ABUTMENT_LAND_WALK_MAX_M`.  An end that never finds its land
    contributes nothing; a family where NEITHER end does has no
    measurable grade and the caller says so.

    THE MESH IS THE WATER AUTHORITY (round-12 amendment 2, B2).  The
    seat samples the built mesh, and that same mesh triangle carries the
    water bits ``O4_DSF_Utils.remap_water_tri_type`` reads — so the
    elevation and "is this water?" come from ONE point-in-triangle scan,
    in one frame, with no projection to get wrong.  The OSM water ∪ sea
    union amendment 1 prescribed could not see OTHH's canal at all (it
    is mapped as coastline, and a single-sided buffer either under-covers
    the canal or over-covers the airport — measured band sweep
    100…2000 m), and elevation is NEVER used as a water proxy."""
    from .object_terrain_assembly import _ABUTMENT_GRADE_SAMPLE_STEP_M

    origin_longitude, origin_latitude = candidate.anchor_longitude_latitude
    lines = _abutment_line_frame_points(candidate, lines)
    midpoints = [
        ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        for start, end in lines
    ]

    def _sample(frame_x, frame_z):
        latitude, longitude = obj8_reader.local_offset_to_lonlat(
            origin_latitude, origin_longitude, 0.0, frame_x, frame_z)
        sample = sampler.sample_at_or_none(latitude, longitude)
        if sample is None or sample.elevation_metres != (
            sample.elevation_metres
        ):
            return None
        if sample.is_water:
            return "water"
        return float(sample.elevation_metres)

    samples: list = []
    end_records: list = []
    for index, (start, end) in enumerate(lines):
        # LANDWARD is away from the span: the direction from the other
        # end's midpoint towards this one.  With one line only (a
        # degenerate record) there is no span to walk away from.
        landward = None
        if len(midpoints) >= 2:
            other = midpoints[1 - index] if len(midpoints) == 2 else (
                midpoints[(index + 1) % len(midpoints)])
            delta_x = midpoints[index][0] - other[0]
            delta_z = midpoints[index][1] - other[1]
            norm = math.hypot(delta_x, delta_z)
            if norm > 1e-6:
                landward = (delta_x / norm, delta_z / norm)

        walk_metres = 0.0
        kept: list = []
        lost_to_water = 0
        while True:
            offset = (
                (landward[0] * walk_metres, landward[1] * walk_metres)
                if landward is not None else (0.0, 0.0)
            )
            kept = []
            lost_to_water = 0
            for frame_x, frame_z in _abutment_line_frame_samples(
                start, end, offset
            ):
                value = _sample(frame_x, frame_z)
                if value == "water":
                    lost_to_water += 1
                elif value is not None:
                    kept.append(value)
            if len(kept) >= _ABUTMENT_LAND_MIN_SAMPLES:
                break
            if landward is None or (
                walk_metres + _ABUTMENT_GRADE_SAMPLE_STEP_M
                > _ABUTMENT_LAND_WALK_MAX_M
            ):
                break
            walk_metres += _ABUTMENT_GRADE_SAMPLE_STEP_M

        found = len(kept) >= _ABUTMENT_LAND_MIN_SAMPLES
        end_records.append({
            "end": "start" if index == 0 else "far",
            "walked_m": float(walk_metres),
            "land_samples": len(kept),
            "samples_over_water": lost_to_water,
            "found_land": bool(found),
        })
        if found:
            samples.extend(kept)
    return samples, end_records


def _mint_seat_fallback(record, result, member_resources, seat_source) -> None:
    """Mint the counted ``bridge_seat_fallback`` finding for a REFUSED
    family whose rigid deck-top seat could not be computed.

    Only the refused-viaduct limb falls back: it is the limb that has a
    generic y-bake to fall back TO (a classified candidate is R4-excluded
    before the mesh is read, so its decline means "stays draped", which
    is R6-3's own answer and not a finding).  The family is left OFF the
    seat's claim set, so the generic pass owns it exactly as it does
    today."""
    from .object_terrain_assembly import (
        BRIDGE_SEAT_FALLBACK_FINDING,
        SEAT_SOURCE_CLASSIFIED,
    )

    if seat_source == SEAT_SOURCE_CLASSIFIED:
        return
    result.setdefault("bridge_findings", []).append({
        "finding": BRIDGE_SEAT_FALLBACK_FINDING,
        "resources": sorted(member_resources),
        "reason": record.get("decision", ""),
    })
    record["seat_fallback"] = True


def _mint_seat_coalition_finding(
    record, result, member_resources, coalition, outliers
) -> None:
    """The INFORMATIONAL finding for a family that seated (amendment 4):
    who authored the level, and who did not agree with it.

    An outlier is not a defect on its own — it is the standing evidence
    trail for the canal-floor residual amendment 2's B2 cannot see, which
    is why its delta AND its end-line sample census travel with it."""
    from .object_terrain_assembly import BRIDGE_SEAT_COALITION_FINDING

    def _census(entry):
        return {
            "member": entry["member"],
            "delta_m": float(entry["delta_m"]),
            "grade_m": float(entry["grade_m"]),
            "crest_effective_m": float(entry["crest_effective_m"]),
            "land_sample_count": int(entry["land_sample_count"]),
            "samples_over_water": int(entry.get("samples_over_water", 0)),
            "walked_m": float(entry.get("walked_m", 0.0)),
        }

    result.setdefault("bridge_findings", []).append({
        "finding": BRIDGE_SEAT_COALITION_FINDING,
        "resources": sorted(member_resources),
        "seat_delta_m": float(record["seat_delta_m"]),
        "coalition": [_census(entry) for entry in coalition],
        "outliers": [_census(entry) for entry in outliers],
        "reason": (
            f"seated by {len(coalition)} agreeing deck member(s) "
            f"(spread {record['coalition_spread_m']:.3f} m); "
            f"{len(outliers)} member(s) did not agree and are recorded "
            "with their end-line sample census"
        ),
    })


#: Elevation materiality floor for the bridge seat's self-checks
#: (convergence guard, owner 2026-08-02): a deck-top residual or an
#: intra-family spread under this is REPORTED and accepted, never
#: iterated on.
_BRIDGE_SEAT_MATERIALITY_M = 0.01


def _bake_bridge_abutment_seats(
    candidates,
    all_placements,
    pack_root: str,
    xplane_root: str | None,
    mesh_path: str,
    *,
    epsilon_metres: float,
    write_changes: bool,
    measure_only: bool,
    result: dict,
) -> None:
    """THE DECK-TOP ABUTMENT SEAT (docs/specs/round6-othh-residuals-
    spec.md R6-3, re-datumed by docs/specs/round12-bridge-deck-datum-
    spec.md R12-1/R12-2; owner in-sim residuals 2026-08-10/11).

    OTHH ``Bridge_01`` is a cosmetic flush deck classified
    TERRAIN_CARRIED, so its resources are R4-EXCLUDED from the Phase 2
    y-bake and it simply drapes.  Its anchor, though, sits OVER WATER —
    the built mesh answers 0.00 m there and at every deck station — while
    its own abutments stand on land ~3.96 m higher.  Draping on water is
    not a seat; it is the absence of one.

    Per candidate, one dedicated law::

        G_abut = median BUILT-MESH elevation sampled along both certified
                 abutment lines, every <= 5 m
        drop   = G_abut - mesh_at_anchor
        seat  <=>  drop > DSF_OBJECT_BAKE_MIN_DELTA_M   (the reseat
                   threshold, 1.0 m — strictly more than, per the spec)
        y0    = G_abut - deck_top_y_m        (R12-1: THE DATUM)

    applied WHOLE-FAMILY-RIGIDLY: one seat plane for every member, each
    member's own delta measured from its OWN anchor's ground (invariant
    I-3).  A candidate whose anchor samples land WITHIN the threshold is
    left exactly as today — excluded and draped — and says so in its
    record.

    **R12-1, THE DATUM IS THE DECK TOP.**  The owner's reading of these
    bridges is that the DECK is what stands at ground level and the
    lower parts are supports descending to the water.  R6-3 landed the
    authored ``y = 0`` plane at the abutment grade, which is the same
    thing ONLY for a flush deck (OTHH Bridge_01, crest −0.31).  A raised
    deck (Bridge_04 / 05, crests +1.067 / +1.187) came out proud, its
    supports hanging 2.28 / 3.27 m above the canal.  The seat now lands
    the DECK TOP at the abutment grade; ``expected_deck_top_m`` is that
    grade, ``achieved_deck_top_m`` is what the produced deltas deliver,
    and the two are asserted equal within
    :data:`_BRIDGE_SEAT_MATERIALITY_M`.  Bridge_01 moves +0.31 m under
    this law and that is correct — its deck sat at 3.544 m, below its
    own 3.851 m abutment grade.

    **R12-2, ONE BRIDGE IS ONE BODY.**  The member set is the whole
    ANCHOR FAMILY (``object_terrain_assembly.anchor_family_resources``),
    not the subset whose geometry the classifier measured the deck on —
    ``OTHH_Bridge_04_LOD0_004`` was R4-excluded from the generic y-bake
    and absent from the seat, and so sat 7.85 m under its own bridge.
    REFUSED piered viaducts join too (``seat_source`` says which limb
    offered the family): refusing them a terrain FEATURE was right,
    handing them to the per-structure y-bake was not — it baked OTHH
    Bridge_02/03/06, one bridge, to three grounds (0.00 / 1.63 /
    3.96 m).  A refused family with no measurable deck keeps the y-bake
    and mints a ``bridge_seat_fallback`` finding instead.

    ``measure_only`` (the tile's ``modify_custom_airports`` switch off)
    is honoured exactly as the generic and basin laws honour it: the
    decision is computed and RECORDED, no delta is produced, nothing is
    written to the pack, and ``object_rebake.apply`` still runs so a
    previously baked pack converges back to its authored bytes.
    """
    if not candidates:
        return

    from dataclasses import replace
    from statistics import median

    from .config import DSF_OBJECT_BAKE_MIN_DELTA_M
    from .object_terrain_assembly import (
        BRIDGE_ABUTMENT_SEAT_DECISION_KIND,
        BRIDGE_SEAT_FALLBACK_FINDING,
        SEAT_SOURCE_CLASSIFIED,
    )

    threshold_metres = float(DSF_OBJECT_BAKE_MIN_DELTA_M)

    placement_count_by_resource: dict[str, int] = {}
    for placement in all_placements:
        placement_count_by_resource[placement.resource_path] = (
            placement_count_by_resource.get(placement.resource_path, 0) + 1
        )

    for candidate in candidates:
        member_resources = set(candidate.object_resources)
        candidate_seat_source = getattr(
            candidate, "seat_source", SEAT_SOURCE_CLASSIFIED)
        record = {
            "resources": sorted(member_resources),
            "anchor_longitude_latitude": list(
                candidate.anchor_longitude_latitude),
            "deck_top_y_m": float(candidate.deck_top_y_m),
            "reseat_threshold_m": threshold_metres,
            "measure_only": bool(measure_only),
            "baked": False,
            "decision_kind": BRIDGE_ABUTMENT_SEAT_DECISION_KIND,
            # R12-2 provenance: which limb offered this family, and the
            # subset of members the deck was actually measured on.  The
            # member set itself is the whole anchor family.
            "seat_source": candidate_seat_source,
            "deck_object_resources": sorted(
                getattr(candidate, "deck_object_resources", ()) or ()),
        }
        result["bridge_abutment_seat"].append(record)

        member_placements = [
            placement
            for placement in all_placements
            if placement.resource_path in member_resources
        ]
        if not member_placements:
            record["decision"] = (
                "not seated — no member placement in this DSF")
            _mint_seat_fallback(
                record, result, member_resources,
                candidate_seat_source)
            continue

        sample_points = _abutment_grade_sample_points(candidate)
        if not sample_points:
            record["decision"] = (
                "not seated — the abutment lines are degenerate, so no "
                "land witness could be sampled")
            _mint_seat_fallback(
                record, result, member_resources,
                candidate_seat_source)
            continue

        skipped: list = []
        (
            resolved_paths,
            geometry_by_resource,
            geometry_source_by_resource,
        ) = _resolve_pack_geometry(
            member_placements,
            placement_count_by_resource,
            pack_root,
            xplane_root,
            skipped,
            # The classifier admitted this bridge; the generic law's size
            # test has nothing to say about it (see the helper).
            apply_reach_floor=False,
        )
        result["skipped"].extend(skipped)
        if not resolved_paths:
            record["decision"] = (
                "not seated — no usable member geometry resolved inside "
                "the pack")
            _mint_seat_fallback(
                record, result, member_resources,
                candidate_seat_source)
            continue

        anchor_longitude, anchor_latitude = (
            candidate.anchor_longitude_latitude)
        latitudes = [latitude for latitude, _longitude in sample_points]
        longitudes = [longitude for _latitude, longitude in sample_points]
        latitudes.append(anchor_latitude)
        longitudes.append(anchor_longitude)
        for placement in member_placements:
            latitudes.append(placement.latitude)
            longitudes.append(placement.longitude)
        # The sampler must reach as far as the R12-A landward walk can
        # take a deck-end line, or the walk would run off its own mesh
        # window and read "no answer" for land it can see.
        latitude_margin = _ABUTMENT_LAND_WALK_MAX_M / 111320.0
        longitude_margin = latitude_margin / max(
            0.01, math.cos(math.radians(anchor_latitude)))
        bounds = (
            min(longitudes) - longitude_margin,
            min(latitudes) - latitude_margin,
            max(longitudes) + longitude_margin,
            max(latitudes) + latitude_margin,
        )
        try:
            sampler = MeshElevationSampler(mesh_path, bounds)
        except (ValueError, OSError) as error:
            # Invariant I-13: no mesh here means no answer, never a
            # plausible one.
            record["decision"] = (
                f"not seated — no mesh under the bridge ({error})")
            _mint_seat_fallback(
                record, result, member_resources,
                candidate_seat_source)
            continue

        # The anchor's own ground first: every delta below is measured
        # from it (amendment 2's B1 frame).
        anchor_elevation = sampler.elevation_at_or_none(
            anchor_latitude, anchor_longitude)
        if anchor_elevation is None or anchor_elevation != anchor_elevation:
            record["decision"] = (
                "not seated — the structure anchor lies outside the built "
                "mesh; never nearest-vertex sampled (invariant I-13)")
            _mint_seat_fallback(
                record, result, member_resources,
                candidate_seat_source)
            continue
        anchor_ground = float(anchor_elevation)
        record["mesh_at_anchor_m"] = anchor_ground

        # WATER NEVER AUTHORS A BRIDGE DATUM (round-12 amendment 1, with
        # amendment 2's B2 authority).  An abutment stands on LAND:
        # samples whose MESH TRIANGLE carries the water bits are
        # discarded, and a deck end that loses its line to water walks
        # landward until it finds its shore.
        #
        # ONE SEAT FOR A CONNECTED ASSEMBLY (amendment 3, owner ruling:
        # "if it's really several bridges connected as one object, then
        # there should be a seat level that works for all of them without
        # splitting").  A CLASSIFIED bridge has ONE certified pair of end
        # lines.  A REFUSED viaduct has one pair PER DECK MEMBER, and
        # each member implies its own delta; the family's delta is their
        # MEDIAN.  Both limbs run the same sampler, the same landward
        # walk and the same >= 4-sample floor — only the number of line
        # sets differs, which is why the merged min-rect could be retired
        # without a second measurement path.
        line_sets = _candidate_grade_line_sets(candidate)
        crest_by_member = {
            member_record["resource_path"]:
                float(member_record["deck_top_y_m"])
            for member_record in (
                getattr(candidate, "deck_member_records", ()) or ())
        }
        member_measurements: list = []
        abutment_samples: list = []
        abutment_end_records: list = []
        for label, member_lines in line_sets:
            samples, end_records = _abutment_grade_samples_on_land(
                candidate, sampler, member_lines)
            for end_record in end_records:
                abutment_end_records.append(
                    dict(end_record, member=label)
                    if label is not None else end_record
                )
            if not samples:
                continue
            abutment_samples.extend(samples)
            member_crest = crest_by_member.get(
                label, float(candidate.deck_top_y_m))
            member_grade = float(median(samples))
            member_measurements.append({
                "member": label,
                "grade_m": member_grade,
                "crest_effective_m": member_crest,
                # B1's frame, per member: its own ends, its own crest.
                "delta_m": member_grade - member_crest - anchor_ground,
                # THE END-LINE SAMPLE CENSUS (amendment 4).  An outlier's
                # census is the evidence trail: a member whose land
                # samples sit on canal-floor triangles the mesh does not
                # attribute as water reads low, and the census is what
                # shows it without this code ever reading elevation as
                # water (B2 forbids that).
                "land_sample_count": len(samples),
                "samples_over_water": sum(
                    end["samples_over_water"] for end in end_records),
                "walked_m": max(
                    [end["walked_m"] for end in end_records] or [0.0]),
            })
        record["abutment_ends"] = abutment_end_records
        record["abutment_walked_m"] = max(
            [end["walked_m"] for end in abutment_end_records] or [0.0])
        if not member_measurements:
            record["decision"] = (
                "not seated — no abutment sample stands on land within "
                f"{_ABUTMENT_LAND_WALK_MAX_M:.0f} m of any deck end "
                f"({sum(end['samples_over_water'] for end in abutment_end_records)}"
                " sample(s) on water-attributed mesh triangles), so the "
                "abutment grade is unmeasured — water never authors a "
                "bridge datum (never guessed)")
            _mint_seat_fallback(
                record, result, member_resources, candidate_seat_source)
            continue
        record["abutment_sample_count"] = len(abutment_samples)
        if line_sets[0][0] is not None:
            # Every REFUSED-limb candidate carries its per-member
            # evidence, seated or not: a reader must not have to
            # reconstruct who measured what from a finding.
            record["deck_member_measurements"] = member_measurements


        anchor_ground_by_resource: dict[str, float] = {}
        anchor_by_resource: dict[str, tuple[float, float, float]] = {}
        unmeasured_anchor = None
        for placement in member_placements:
            if placement.resource_path not in resolved_paths:
                continue
            member_ground = sampler.elevation_at_or_none(
                placement.latitude, placement.longitude
            )
            if member_ground is None:
                unmeasured_anchor = placement.resource_path
                break
            # Amendment A18: an OBJECT_AGL placement puts y = 0 at
            # terrain(anchor) + elevation.
            anchor_ground_by_resource[placement.resource_path] = (
                member_ground + placement.above_ground_level_metres
            )
            anchor_by_resource[placement.resource_path] = (
                placement.latitude,
                placement.longitude,
                placement.heading_degrees,
            )
        if unmeasured_anchor is not None or not anchor_ground_by_resource:
            record["decision"] = (
                "not seated — a member anchor lies outside the built mesh "
                f"({unmeasured_anchor}); never nearest-vertex sampled "
                "(invariant I-13)")
            for placement in member_placements:
                result["skipped"].append(
                    (
                        placement.resource_path,
                        "bridge abutment seat: a member anchor lies "
                        "outside the built mesh — bridge left unseated "
                        "(invariant I-13)",
                    )
                )
            _mint_seat_fallback(
                record, result, member_resources,
                candidate_seat_source)
            continue

        # THE DATUM IS THE DECK TOP (round-12 R12-1, in the frame
        # amendment 2's B1 corrects it to).  The seat lands the authored
        # DECK TOP at the abutment grade.  Landing the y = 0 plane there
        # — the R6-3 delta — is the same thing ONLY for a flush deck, so
        # a raised deck came out proud with its supports clear of the
        # water they descend to (OTHH Bridge_04 / 05: crests +1.067 /
        # +1.187, supports left 2.28 / 3.27 m up).
        #
        # MIND THE TWO FRAMES.  ``deck_top_y_m`` is an EFFECTIVE height
        # (object_terrain_features._build_structure_frame:
        # ``effective_y = above_ground_level_metres + authored_y``) —
        # metres above the ANCHOR'S TERRAIN.  ``anchor_ground_by_resource``
        # is world-frame: ``mesh(anchor) + AGL``, the elevation of the
        # object's authored y = 0 plane.  Subtracting the first from the
        # second double-counts the AGL, and the deck top then lands
        # exactly where the OLD law left the y = 0 plane (verified from
        # pack bytes: Bridge_04_LOD0_001 authored y 4.8255..4.8683 with
        # AGL −3.8009 ⇒ effective 1.0247..1.0675 against a recorded crest
        # of 1.0675).  So the delta is measured in the EFFECTIVE frame:
        #
        #     delta = abutment_grade − deck_top_y_m − mesh_at_anchor
        #
        # and it is ONE number for the whole family (R12-2's "one delta
        # for every member", verbatim): a rigid body has one offset, and
        # the per-member anchor grounds — which is what tore families
        # apart — never enter the arithmetic.
        # ONE SEAT FOR A CONNECTED ASSEMBLY (amendment 3), authored by
        # THE AGREEING COALITION (amendment 4).  Each deck member
        # measured above implies its own delta in B1's effective frame;
        # the members that AGREE — the largest group inside one
        # agreement window — author the family's delta, and the rest are
        # named as outliers with their sample censuses.  A single-set
        # candidate (every classified bridge) has exactly one member
        # measurement and skips the coalition entirely, so the R6-3 limb
        # does not move.
        member_deltas = [entry["delta_m"] for entry in member_measurements]
        record["member_delta_spread_m"] = float(
            max(member_deltas) - min(member_deltas))
        if len(member_measurements) == 1:
            coalition = list(member_measurements)
            outliers: list = []
        else:
            coalition, outliers, coalition_refusal = agreeing_coalition(
                member_measurements, _MEMBER_DELTA_AGREEMENT_WINDOW_M)
            if coalition_refusal is not None:
                record["abutment_grade_m"] = float(
                    median([entry["grade_m"]
                            for entry in member_measurements]))
                record["decision"] = (
                    "not seated — the deck members do not agree about "
                    f"the seat: {coalition_refusal} (R12-2, amendment 4)")
                _mint_seat_fallback(
                    record, result, member_resources,
                    candidate_seat_source)
                UI.vprint(
                    1,
                    "  [object-anchor] bridge_abutment_seat "
                    f"{sorted(member_resources)}: " + record["decision"],
                )
                continue

        # THE GRADE IS THE COALITION'S (amendment 4).  The family median
        # over ALL members would report a level no member stands on —
        # at OTHH 2.49 m, against the 3.96 m bank the seat is actually
        # authored from — and the reseat threshold would be asked about
        # that fiction.  Everything downstream reads the level that
        # authored the seat.
        abutment_grade = float(
            median([entry["grade_m"] for entry in coalition]))
        record["abutment_grade_m"] = abutment_grade
        drop_metres = abutment_grade - anchor_ground
        record["drop_m"] = drop_metres

        seat_delta_metres = float(
            median([entry["delta_m"] for entry in coalition]))
        record["seat_delta_m"] = seat_delta_metres
        record["coalition_members"] = [
            entry["member"] for entry in coalition]
        record["coalition_spread_m"] = float(
            max(entry["delta_m"] for entry in coalition)
            - min(entry["delta_m"] for entry in coalition))
        record["outlier_members"] = [entry["member"] for entry in outliers]
        # The crest the record reports is a MEASURED one — the coalition
        # member sitting at (or nearest) its median — never a number
        # back-derived from the delta, which would make every check below
        # true by construction.
        median_member = min(
            coalition,
            key=lambda entry: abs(entry["delta_m"] - seat_delta_metres),
        )
        deck_top_y_metres = float(median_member["crest_effective_m"])
        # What each COALITION member's own deck top misses its own
        # measured grade by, once the family moves as one body.  Zero for
        # a single-set candidate; bounded by the agreement window
        # otherwise.  Outliers are reported, not held to this.
        record["member_deck_top_residual_m"] = float(
            max(abs(entry["delta_m"] - seat_delta_metres)
                for entry in coalition))
        if len(member_measurements) > 1:
            _mint_seat_coalition_finding(
                record, result, member_resources, coalition, outliers)

        # The seated deck top the law PROMISES for the median member:
        # the family grade, by construction.  ``achieved_deck_top_m`` is
        # what the deltas actually produce, asserted equal below — a
        # record that promises one number and bakes another is how R6-3's
        # flush-deck assumption survived unread.
        record["expected_deck_top_m"] = (
            anchor_ground + seat_delta_metres + deck_top_y_metres)

        # THE REFUSED VIADUCT TAKES THIS SAME SEAT (round-12 R12-2, as
        # amended).  Refusing a piered viaduct a terrain FEATURE was
        # right; handing its family to the generic per-structure y-bake
        # was not — that baked OTHH Bridge_02/03/06, one bridge, to three
        # grounds (0.00 / 1.63 / 3.96 m).  With the amendment's water
        # clause its deck ends now find their shore, so it seats rigidly
        # like any other family.  The one difference is the FALLBACK: a
        # refused family whose seat cannot be computed keeps the generic
        # y-bake it has today (it is never R4-excluded pre-mesh, so the
        # bake is still there to fall back to) and says so as a counted
        # finding.  A CLASSIFIED family's decline means "stays draped",
        # which is R6-3's own answer and not a finding.

        # THE THRESHOLD (spec R6-3): strictly MORE than the reseat
        # threshold below the certified abutment grade.  Anything else —
        # including an anchor ABOVE the abutments — stays excluded and
        # draped, which is the whole of today's behaviour for this class.
        if not drop_metres > threshold_metres:
            record["decision"] = (
                f"not seated — the anchor ground {anchor_ground:.2f} m is "
                f"{drop_metres:.2f} m below the certified abutment grade "
                f"{abutment_grade:.2f} m, within the "
                f"{threshold_metres:.2f} m reseat threshold "
                "(DSF_OBJECT_BAKE_MIN_DELTA_M); the bridge stays "
                "R4-excluded and drapes as authored")
            _mint_seat_fallback(
                record, result, member_resources, candidate_seat_source)
            UI.vprint(
                2,
                "  [object-anchor] bridge_abutment_seat "
                f"{sorted(member_resources)}: " + record["decision"],
            )
            continue

        pools = object_anchor.discover_object_pools(
            [
                placement
                for placement in member_placements
                if placement.resource_path in resolved_paths
            ],
            resolved_paths,
            geometry_by_resource,
            epsilon_metres=epsilon_metres,
        )
        baked_resources: list[str] = []
        seat_delta_by_resource: dict[str, float] = {}
        for pool in pools:
            pool_geometry_by_resource = {
                resource_path: geometry_by_resource[resource_path]
                for resource_path in pool.resolved_paths
            }
            structures = _cached_partition_structures(
                pool,
                pool_geometry_by_resource,
                geometry_source_by_resource,
                pack_root,
                epsilon_metres,
            )
            delta_by_resource_and_vertex: dict[str, dict[int, float]] = {}
            decision_structures = []
            for structure in structures:
                if measure_only:
                    decision_structures.append(
                        replace(
                            structure,
                            skip_reason=(
                                "modify_custom_airports is off — "
                                "measure-only run: the "
                                "bridge_abutment_seat was computed and "
                                "recorded, the pack is not modified"
                            ),
                        )
                    )
                    continue
                decision_structures.append(structure)
                for resource_path, triangles in (
                    structure.triangles_by_resource.items()
                ):
                    if resource_path not in anchor_ground_by_resource:
                        continue
                    # ONE BRIDGE, ONE RIGID SEAT (R12-2): the family's
                    # single delta, for every member of every structure.
                    # Neither the per-structure grounds this loop walks
                    # nor the per-member anchor grounds enter the
                    # arithmetic — which is precisely why the family
                    # cannot tear across either of them.
                    delta = seat_delta_metres
                    seat_delta_by_resource[resource_path] = delta
                    resource_deltas = (
                        delta_by_resource_and_vertex.setdefault(
                            resource_path, {})
                    )
                    for triangle in triangles:
                        for vertex_index in triangle:
                            resource_deltas[vertex_index] = delta
            pool_resources = set(pool.resolved_paths)
            decision = object_anchor.RebakeDecision(
                structures=decision_structures,
                delta_by_resource_and_vertex=delta_by_resource_and_vertex,
                # Scoped to THIS pool: ``object_rebake.apply``'s
                # reversion pass un-bakes every resource a decision
                # "knows" but did not write.
                anchor_ground_by_resource={
                    resource_path: ground
                    for resource_path, ground
                    in anchor_ground_by_resource.items()
                    if resource_path in pool_resources
                },
                skipped=[],
                anchor_by_resource={
                    resource_path: anchor
                    for resource_path, anchor
                    in anchor_by_resource.items()
                    if resource_path in pool_resources
                },
                decision_kind_by_resource={
                    resource_path: BRIDGE_ABUTMENT_SEAT_DECISION_KIND
                    for resource_path in delta_by_resource_and_vertex
                },
            )
            result["decisions"].append((pool, decision))
            if write_changes:
                report = object_rebake.apply(decision, pack_root, mesh_path)
                result["objects_written"].extend(report.objects_written)
                result["vertices_offset"] += report.vertices_offset_total
                result["structures_baked"] += report.structures_baked
                result["structures_needing_pad"] += (
                    report.structures_needing_pad
                )
                result["skipped"].extend(report.skipped)
                result["objects_reverted"].extend(report.objects_reverted)
                result["reversions_missing_backup"].extend(
                    report.reversions_missing_backup
                )
                result["partially_baked"].extend(report.partially_baked)
                baked_resources.extend(report.objects_written)
            else:
                result["structures_baked"] += sum(
                    1
                    for structure in decision_structures
                    if structure.skip_reason is None
                )
                baked_resources.extend(
                    sorted(delta_by_resource_and_vertex))
        # "baked" means the pack was WRITTEN.  A dry run computes the
        # same seat and writes nothing.
        record["baked"] = bool(baked_resources) and write_changes
        record["dry_run"] = not write_changes
        record["objects_written"] = sorted(set(baked_resources))
        # THE CLAIM (round-12 R12-2, as amended).  This family took the
        # seat, so the generic y-bake must not also touch it — the
        # stacked correction ruling R4 forbids.  A CLASSIFIED family is
        # already R4-excluded before the mesh is read and this is a
        # no-op for it; a REFUSED viaduct is not, and this is the only
        # thing that routes it.  The claim is made from what the seat
        # ACTUALLY produced, so a family that fell back is never routed.
        result.setdefault("bridge_seat_claimed_resources", set()).update(
            member_resources)

        # THE ACHIEVED DECK TOP, measured from the deltas actually
        # produced (R12-1: assert the record's promise, materiality
        # 0.01 m; a residual under the floor is reported, never iterated
        # on).  Per member: its own anchor ground + its own delta + the
        # authored crest.  Rigid means these AGREE — the spread across
        # the family is the tear, and it must be zero.
        if seat_delta_by_resource:
            # In the EFFECTIVE frame the crest is measured in (B1): a
            # member's deck top ends up at
            # ``mesh(anchor) + crest + delta``.  Measured from the deltas
            # ACTUALLY produced, so the record's promise is checked
            # against the bake rather than restated.
            achieved_by_resource = {
                resource_path: (
                    anchor_ground + delta + deck_top_y_metres
                )
                for resource_path, delta in seat_delta_by_resource.items()
            }
            achieved_values = sorted(achieved_by_resource.values())
            record["seat_delta_by_resource_m"] = {
                resource_path: float(delta)
                for resource_path, delta
                in sorted(seat_delta_by_resource.items())
            }
            # WHERE EACH MEMBER'S AUTHORED y = 0 PLANE LANDS, per
            # member, because that is the only unambiguous statement:
            # it is ``mesh(anchor_r) + AGL_r + delta`` and the AGL is a
            # PLACEMENT property, so a single scalar for the family
            # would be the same frame mix B1 corrected.  A reader
            # reconstructing world y does ``y0 + authored_y``.
            record["member_world_y0_m"] = {
                resource_path: float(
                    anchor_ground_by_resource[resource_path] + delta)
                for resource_path, delta
                in sorted(seat_delta_by_resource.items())
            }
            record["achieved_deck_top_m"] = float(achieved_values[0])
            record["intra_family_tear_m"] = float(
                achieved_values[-1] - achieved_values[0])
            residual = abs(
                record["achieved_deck_top_m"]
                - record["expected_deck_top_m"]
            )
            record["deck_top_residual_m"] = float(residual)
            if (
                residual > _BRIDGE_SEAT_MATERIALITY_M
                or record["intra_family_tear_m"]
                > _BRIDGE_SEAT_MATERIALITY_M
            ):
                record["datum_finding"] = (
                    "the seated deck top "
                    f"{record['achieved_deck_top_m']:.3f} m misses the "
                    f"abutment grade {record['expected_deck_top_m']:.3f} m "
                    f"by {residual:.3f} m, and the family spans "
                    f"{record['intra_family_tear_m']:.3f} m — over the "
                    f"{_BRIDGE_SEAT_MATERIALITY_M:.2f} m materiality "
                    "floor (R12-1/R12-2)")
                UI.vprint(
                    0,
                    "  [object-anchor] bridge_abutment_seat "
                    f"{sorted(member_resources)}: "
                    + record["datum_finding"],
                )
        if measure_only:
            record["decision"] = (
                "measure-only (modify_custom_airports off): "
                "bridge_abutment_seat at abutment grade "
                f"{abutment_grade:.2f} m recorded, drop "
                f"{drop_metres:.2f} m NOT written")
        else:
            record["decision"] = (
                ("bridge_abutment_seat (dry run, nothing written): would "
                 "seat " if not write_changes
                 else "bridge_abutment_seat: seated ")
                + f"the DECK TOP at abutment grade {abutment_grade:.2f} m "
                f"({len(abutment_samples)} land sample(s), walked "
                f"{record['abutment_walked_m']:.0f} m) — effective crest "
                f"{deck_top_y_metres:+.2f} m over the anchor ground "
                f"{anchor_ground:.2f} m, so ONE family delta of "
                f"{seat_delta_metres:+.3f} m over "
                f"{len(record['objects_written'])} object file(s) "
                + (
                    f", authored by {len(record['coalition_members'])} "
                    f"agreeing deck member(s) (spread "
                    f"{record['coalition_spread_m']:.3f} m) against "
                    f"{len(record['outlier_members'])} outlier(s)"
                    if record.get("outlier_members") else ""
                )
                + f" [{candidate_seat_source}]")
        UI.vprint(
            1,
            "  [object-anchor] bridge_abutment_seat "
            f"{sorted(member_resources)}: " + record["decision"],
        )


def discover_and_rebake_airport(
    dsf_path: str,
    mesh_path: str,
    pack_root: str | None,
    xplane_root: str | None,
    *,
    epsilon_metres: float | None = None,
    write_changes: bool = True,
    excluded_resources: set[tuple[str, str]] | None = None,
    measure_only: bool = False,
    basin_rim_flush_facilities: list | None = None,
    bridge_abutment_seat_candidates: list | None = None,
    airport: str | None = None,
    claims_placement=None,
) -> dict:
    """Run the full Phase 2 discovery pipeline for one airport's DSF.

    Discovery: ``_load_dsf_text`` → ``read_dsf_object_placements``
    (``.obj`` only) → resolve (pack-relative wins) → parse geometry
    (memoized ``dsf_reader._load_object_geometry``) → reach floor
    ``DSF_OBJECT_MIN_REACH_M`` → **exclude any resource with more than
    one terrain-draped placement, skip-and-report (invariant I-4,
    enforced here per amendment A13)** → ``discover_object_pools`` →
    per pool: one :class:`MeshElevationSampler` bounded by the pool's
    world extent plus margin → ``partition_structures`` →
    ``structure_deltas`` → ``object_rebake.apply``.

    Shared by :func:`rebake_dsf_objects` and the command line
    (``tools/reanchor_dsf_objects.py`` mode 2) so the two can never
    drift.  With ``write_changes=False`` nothing on disk is touched; the
    decisions are returned for reporting (the command line's
    ``--dry-run``).

    ``measure_only`` (the tile's ``modify_custom_airports`` switch turned
    off, docs/specs/object-reseat-threshold-spec.md section 2.3) is a
    different thing from a dry run: the pass RUNS, every unit is routed
    as if below the reseat threshold so no bake is ever written, the pad
    requests are still raised — and ``object_rebake.apply`` still runs,
    because its reversion pass is what converges a previously-baked pack
    back to its authored bytes.  The switch gates modification of the
    pack, not the terrain-side answer to it.

    ``excluded_resources`` (ruling R4, object terrain features spec):
    ``(pack_root, resource_path)`` pairs whose terrain was carved or
    seated to match the object (a structure consumed by terrain feature
    A or B).  Terrain-to-object and object-to-terrain corrections must
    never stack, so these placements are dropped BEFORE discovery, each
    with a skip-and-report entry.  ``None`` / empty means no exclusions
    (the pre-change behaviour, and the only behaviour while the
    ``O4_OBJECT_BRIDGE_TERRAIN`` / tunnel gates are off).

    ``airport`` / ``claims_placement`` (round-4 spec R2): the airport
    this run is FOR, and ``claims(latitude, longitude) -> bool`` naming
    the placements of this DSF that belong to it.  A DSF cell carrying
    two airports' objects is processed once per airport over disjoint
    subsets, so a decision, a bake and a run fingerprint all belong to
    the airport whose ground the object stands on.  ``None`` (the
    command line, the unit tests) keeps the whole-cell behaviour.  The
    run fingerprint is keyed by ``airport`` too — without that the
    second airport's run would short-circuit on the FIRST airport's
    record and inherit its pad requests wholesale.

    The invariant-I-4 multi-placement exclusion is counted over the
    WHOLE DSF, never the subset: a resource placed at both airports must
    stay excluded for both, and counting only the subset would let each
    run bake it to a different offset.

    ``basin_rim_flush_facilities``
    (``object_terrain_assembly.BasinRimFlushFacility`` records,
    docs/specs/basin-rim-flush-seating-spec.md section 2.2): the
    dedicated seating class.  Its members stay OUT of the generic
    discovery above — section 2.2 item 5 says the generic
    median/A3/threshold arithmetic does not run for them, and the way to
    guarantee that is for them never to enter it — and are seated
    afterwards by :func:`_bake_basin_rim_flush_facilities` instead.

    Under ``config.BASIN_GROUP_SEAT`` (docket B, the default) those same
    facility records take the GROUP law instead
    (:func:`_bake_basin_group_seat_facilities`): it runs BEFORE the
    generic pass, seats every partition structure whose footprint
    reaches a facility body onto one datum plane, and reports the
    resources it claimed so the generic pass can withhold exactly them —
    seating and withholding in one step (trap T1).  Exactly one of the
    two laws runs; with the gate off the pre-amendment behaviour above
    is reproduced byte-identically.

    ``bridge_abutment_seat_candidates``
    (``object_terrain_assembly.BridgeAbutmentSeatCandidate`` records,
    docs/specs/round6-othh-residuals-spec.md R6-3): TERRAIN_CARRIED
    bridges with certified abutments.  They are already in
    ``excluded_resources`` (ruling R4 consumed them), so the generic pass
    never saw them; here they are ROUTED to
    :func:`_bake_bridge_abutment_seats`, which seats the ones whose
    anchor ground sits more than the reseat threshold below their
    abutment grade and leaves the rest draped exactly as before.

    Returns a dict with ``objects_written`` (resource paths),
    ``vertices_offset``, ``structures_baked``, ``structures_needing_pad``,
    ``skipped`` (``(resource_path_or_dsf, reason)`` tuples, discovery and
    rebake levels merged), and ``decisions``
    (``(ObjectPool, RebakeDecision)`` pairs, for detailed reporting).
    Pure data out — printing is the caller's business.
    """
    from .config import DSF_OBJECT_CONTACT_EPSILON_M

    if epsilon_metres is None:
        epsilon_metres = DSF_OBJECT_CONTACT_EPSILON_M

    result: dict = {
        "objects_written": [],
        "vertices_offset": 0,
        "structures_baked": 0,
        "structures_needing_pad": 0,
        "skipped": [],
        "decisions": [],
        # object_anchor.FootPadRequest instances, all pools merged.
        "foot_pad_requests": [],
        # object_anchor.ClusterPadRequest / ClusterSeam instances, all
        # pools merged (empty unless DSF_OBJECT_CLUSTER_SEATING is on).
        "cluster_pad_requests": [],
        "cluster_seams": [],
        # Objects un-baked because they are excluded from the current
        # decision but still carried a stale live bake (reversion pass).
        "objects_reverted": [],
        "reversions_missing_backup": [],
        # Objects written with SOME structures left unbaked (amendment
        # A21): (resource_path, summary) pairs from the rebake report.
        "partially_baked": [],
        # True when the whole airport was skipped because the pack's
        # recorded run fingerprint still matches every input.
        "short_circuited": False,
        "structures_up_to_date": 0,
        # One dict per basin facility the section-2.2 law considered —
        # baked, out of scope (anchor outside the body) or refused — for
        # the caller's report.  Never empty-because-silent: a facility
        # that could not be measured is in here with its reason.
        "basin_rim_flush": [],
        # One dict per basin facility the docket-B GROUP SEAT considered
        # (``config.BASIN_GROUP_SEAT``, the default): seated, a recorded
        # threshold no-op, or refused with its reason.  The two lists are
        # exclusive — a run takes one law or the other, never both.
        "basin_group_seat": [],
        # One dict per R6-3 bridge abutment-seat CANDIDATE the law
        # considered — seated, within-threshold (left draped) or refused.
        # Same posture as the basin list: a candidate that could not be
        # measured is in here with its reason, never silently absent.
        "bridge_abutment_seat": [],
        # Round-12 counted FINDINGS raised by the seat pass itself
        # (``bridge_seat_fallback``).  The candidacy-time findings travel
        # on the terrain records instead; both are counted the same way.
        "bridge_findings": [],
    }

    # Short-circuit (O4_REANCHOR_SHORT_CIRCUIT, default on).  The pack's
    # provenance sidecar records a fingerprint of EVERY input the last
    # full run read — mesh, DSF, each referenced resource's resolution
    # and bytes, the exclusion set, every config gate, the code version.
    # When they all still match, this run would rewrite the bytes already
    # on disk (the bake is byte-idempotent, invariant I-15), so there is
    # nothing to derive.  Anything else — including any doubt — runs the
    # full pipeline exactly as before.  Dry runs (``write_changes=False``)
    # never short-circuit: their whole purpose is to report the decision.
    if (
        write_changes
        and pack_root is not None
        and not _is_protected_scenery_root(pack_root)
        and object_rebake.short_circuit_enabled()
    ):
        record, reason = object_rebake.matching_run_record(
            pack_root,
            dsf_path,
            mesh_path,
            epsilon_metres=epsilon_metres,
            excluded_resources=excluded_resources,
            resolve_resource=lambda resource_path: (
                obj8_reader.resolve_object_resource(
                    resource_path, pack_root, xplane_root
                )
            ),
            measure_only=measure_only,
            airport=airport,
        )
        if record is not None:
            result["short_circuited"] = True
            result["structures_up_to_date"] = record.get(
                "structures_baked", 0
            )
            result["structures_baked"] = record.get("structures_baked", 0)
            result["structures_needing_pad"] = record.get(
                "structures_needing_pad", 0
            )
            result["foot_pad_requests"] = (
                object_rebake.run_record_foot_pad_requests(record)
            )
            result["cluster_pad_requests"] = (
                object_rebake.run_record_cluster_pad_requests(record)
            )
            return result
        UI.vprint(
            2,
            f"  [object-anchor] full re-anchor run: {reason}",
        )

    lines = dsf_reader._load_dsf_text(dsf_path)
    if not lines:
        result["skipped"].append(
            (dsf_path, "DSF text unavailable (missing file or DSFTool)")
        )
        return result
    placements = obj8_reader.read_dsf_object_placements(
        lines,
        accept_resource=lambda resource: resource.lower().endswith(".obj"),
    )
    if not placements:
        return result
    # Every ``.obj`` the DSF names, captured BEFORE any filtering: the
    # run fingerprint has to notice a resource whose resolution changes
    # even when the current run drops it (ruling R4, the reach floor, …).
    referenced_resources = sorted(
        {placement.resource_path for placement in placements}
    )
    if pack_root is None:
        pack_root = dsf_reader._pack_root_for_dsf(dsf_path)

    # Amendment A15, guard 1: base and global scenery are NEVER rebaked.
    # Small airports resolve to the Global Airports DSF, whose static
    # airliners and library hangars pass the reach floor (a large,
    # correctly anchored object has a large reach — the metric conflates
    # size with mis-anchoring), and on a writable install Phase 2 would
    # modify the base simulator.  Policy, not permission luck.
    if pack_root is None or _is_protected_scenery_root(pack_root):
        result["skipped"].append(
            (
                dsf_path,
                "pack is base or global scenery — never rebaked "
                "(amendment A15)",
            )
        )
        return result

    # The DSF's placements as read, before the ruling-R4 filter below:
    # the section-2.2 basin pass seats members the generic pass drops.
    all_placements = list(placements)

    # THE AIRPORT'S OWN SUBSET (round-4 spec R2).  Containment decides
    # which of a shared cell's placements this run may touch; the
    # invariant-I-4 placement census below still counts over the WHOLE
    # cell, so a resource placed at both airports stays excluded at both.
    placement_count_over_whole_dsf: dict[str, int] = {}
    for placement in all_placements:
        placement_count_over_whole_dsf[placement.resource_path] = (
            placement_count_over_whole_dsf.get(placement.resource_path, 0) + 1
        )
    if claims_placement is not None:
        claimed = [
            placement
            for placement in placements
            if claims_placement(placement.latitude, placement.longitude)
        ]
        if len(claimed) != len(placements):
            UI.vprint(
                2,
                f"  [object-anchor] {airport or '?'}: "
                f"{len(claimed)} of {len(placements)} placement(s) in "
                f"{os.path.basename(dsf_path)} are on this airport's "
                "ground (round-4 spec R2 containment)",
            )
        placements = claimed
        if not placements:
            return result
    basin_member_resources = {
        resource
        for facility in (basin_rim_flush_facilities or [])
        if facility.anchor_inside_body
        for resource in facility.object_resources
    }
    # Filled by the docket-B group seat before the generic pass runs (it
    # is a set the closure below READS at call time, never a snapshot):
    # every resource the group law claimed, seated or no-op'd.  The
    # withholding and the seating are one step — trap T1, the LSGG
    # starvation law — and this is the withholding half.
    basin_group_claimed: set[str] = set()
    # R6-3: the candidates are already R4-excluded, so this set only
    # RE-LABELS their skip lines — "routed to the abutment-seat law",
    # never "terrain adapted to this object, nothing more happens".
    # Routed is true whatever the post-mesh threshold test then decides.
    # R12-2 widened WHO is routed (the whole anchor family, and refused
    # piered viaducts beside the classified bridges), so the label says
    # which limb sent each member here.
    abutment_candidate_source = {}
    for candidate in (bridge_abutment_seat_candidates or []):
        source = getattr(candidate, "seat_source", "classified")
        for resource in candidate.object_resources:
            abutment_candidate_source[resource] = source
    abutment_candidate_resources = set(abutment_candidate_source)

    def _generic_pass() -> None:
        """The generic Phase 2 y-bake, unchanged.  A nested function only
        so its early exits leave the section-2.2 basin pass below still
        to run — an airport whose every generic placement is excluded
        still has basin facilities to seat."""
        nonlocal placements

        # Ruling R4: objects whose terrain was adapted TO them (feature
        # A/B) are excluded from the Phase 2 y-bake — the two
        # corrections must never stack.  Filter before discovery,
        # skip-and-report each drop.
        if excluded_resources:
            dropped = sorted({
                placement.resource_path
                for placement in placements
                if (pack_root or "", placement.resource_path)
                in excluded_resources
            })
            if dropped:
                placements = [
                    placement
                    for placement in placements
                    if (pack_root or "", placement.resource_path)
                    not in excluded_resources
                ]
                for resource_path in dropped:
                    result["skipped"].append(
                        (
                            resource_path,
                            # A basin member is not merely withheld: it
                            # is seated by the dedicated law below, and
                            # a skip line claiming otherwise would send
                            # the next reader hunting the wrong law.
                            # Docket B: the whole seat GROUP is routed to
                            # the group law — its interface members and
                            # the structures around them alike — so its
                            # skip line names that law, not the
                            # pre-amendment one.
                            "basin facility seat-group member — seated "
                            "by the basin_group_seat law on the group's "
                            "own datum plane, not the generic y-bake "
                            "(basin-group-seat spec section 2.2)"
                            if resource_path in basin_group_claimed
                            else
                            "basin facility member — seated by the "
                            "basin_rim_flush law, not the generic "
                            "y-bake (spec section 2.2 item 5)"
                            if resource_path in basin_member_resources
                            else
                            # Likewise: routed to the R6-3 law, which
                            # either seats it at its abutment grade or
                            # leaves it draped — a skip line saying only
                            # "excluded" would send the next reader
                            # hunting the wrong law.
                            f"bridge family member "
                            f"({abutment_candidate_source[resource_path]})"
                            " — routed to the bridge_abutment_seat law, "
                            "not the generic y-bake (round-6 spec R6-3, "
                            "round-12 spec R12-2)"
                            if resource_path in abutment_candidate_resources
                            else
                            "terrain adapted to this object (object "
                            "terrain feature A/B) — excluded from the "
                            "Phase 2 y-bake (ruling R4)",
                        )
                    )
                if not placements:
                    return

        _generic_pass_discovery()

    def _generic_pass_discovery() -> None:
        # Counted over the WHOLE cell, not this airport's subset
        # (round-4 spec R2): invariant I-4's multi-placement exclusion
        # must reach a resource placed once at each of two airports.
        placement_count_by_resource = dict(placement_count_over_whole_dsf)

        (
            resolved_paths,
            geometry_by_resource,
            geometry_source_by_resource,
        ) = _resolve_pack_geometry(
            placements,
            placement_count_by_resource,
            pack_root,
            xplane_root,
            result["skipped"],
        )
        if not resolved_paths:
            return

        candidate_placements = [
            placement
            for placement in placements
            if placement.resource_path in resolved_paths
        ]
        pools = object_anchor.discover_object_pools(
            candidate_placements,
            resolved_paths,
            geometry_by_resource,
            epsilon_metres=epsilon_metres,
        )

        for pool in pools:
            pool_geometry_by_resource = {
                resource_path: geometry_by_resource[resource_path]
                for resource_path in pool.resolved_paths
            }
            bounds = _pool_world_bounds(pool, pool_geometry_by_resource)
            try:
                sampler = MeshElevationSampler(mesh_path, bounds)
            except ValueError as error:
                # No mesh triangles under this pool — a pool that walked off
                # the tile.  Skip-and-report, never guess (invariant I-13).
                for placement in pool.placements:
                    result["skipped"].append(
                        (
                            placement.resource_path,
                            f"no mesh triangles under the pool ({error})",
                        )
                    )
                continue
            structures = _cached_partition_structures(
                pool,
                pool_geometry_by_resource,
                geometry_source_by_resource,
                pack_root,
                epsilon_metres,
            )
            # THE ONE FRAME (R3 step 2).  Pure pack data, so it is the
            # SAME product the pad emitter reads in-run — this call is a
            # disk hit on the pristine key when the emitter already built
            # it, and the build that pays for it pays once either way.
            # The y-bake below keeps only what needs the built mesh.
            pad_frame = cached_pad_frame(
                pool, pool_geometry_by_resource, structures, pack_root
            )
            decision = object_anchor.structure_deltas(
                pool,
                pool_geometry_by_resource,
                structures,
                sampler,
                measure_only=measure_only,
                pad_frame=pad_frame,
            )
            result["decisions"].append((pool, decision))
            result["foot_pad_requests"].extend(decision.foot_pad_requests)
            result["cluster_pad_requests"].extend(
                decision.cluster_pad_requests)
            result["cluster_seams"].extend(decision.cluster_seams)
            if write_changes:
                report = object_rebake.apply(decision, pack_root, mesh_path)
                result["objects_written"].extend(report.objects_written)
                result["vertices_offset"] += report.vertices_offset_total
                result["structures_baked"] += report.structures_baked
                result["structures_needing_pad"] += (
                    report.structures_needing_pad
                )
                result["skipped"].extend(report.skipped)
                result["objects_reverted"].extend(report.objects_reverted)
                result["reversions_missing_backup"].extend(
                    report.reversions_missing_backup
                )
                result["partially_baked"].extend(report.partially_baked)
            else:
                result["structures_baked"] += sum(
                    1
                    for structure in decision.structures
                    if structure.skip_reason is None
                )
                result["structures_needing_pad"] += sum(
                    1 for structure in decision.structures
                    if structure.needs_pad
                )
                result["skipped"].extend(decision.skipped)
                # Amendment A21 parity with the write path: resources that
                # WOULD bake only their passing structures.
                for resource_path in sorted(
                    decision.delta_by_resource_and_vertex
                ):
                    resource_skipped = [
                        structure
                        for structure in decision.structures
                        if structure.skip_reason
                        and resource_path in structure.triangles_by_resource
                    ]
                    if resource_skipped:
                        result["partially_baked"].append(
                            (
                                resource_path,
                                f"{len(resource_skipped)} structure(s) would "
                                "stay at their authored y (skipped), passing "
                                "structures bake; first reason: "
                                + resource_skipped[0].skip_reason,
                            )
                        )

    # THE BRIDGE ABUTMENT SEAT RUNS FIRST (round-6 R6-3, round-12 R12-2
    # as amended).  It used to run last, beside the basin class, because
    # every family it seats was already R4-excluded before the mesh was
    # read.  A REFUSED piered viaduct is not: whether it seats depends on
    # whether its deck ends find land, which only the built mesh can
    # answer.  So the seat runs first and REPORTS what it claimed, and
    # the generic pass excludes exactly that — a family that fell back
    # keeps the generic y-bake, a family that seated never enters it, and
    # no object is ever reached by two laws.  The pass is independent of
    # the generic one (its own geometry, sampler and pools, over
    # ``all_placements``), so the move changes no classified outcome.
    _bake_bridge_abutment_seats(
        bridge_abutment_seat_candidates,
        all_placements,
        pack_root,
        xplane_root,
        mesh_path,
        epsilon_metres=epsilon_metres,
        write_changes=write_changes,
        measure_only=measure_only,
        result=result,
    )
    seat_claimed = result.get("bridge_seat_claimed_resources") or set()
    if seat_claimed:
        excluded_resources = set(excluded_resources or ()) | {
            (pack_root or "", resource) for resource in seat_claimed
        }

    # THE BASIN GROUP SEAT RUNS BEFORE THE GENERIC PASS (docket B,
    # basin-group-seat spec §2.2).  Its group is NOT the R4 exclusion
    # set — it is every structure whose footprint reaches the facility
    # body, most of which the generic pass would otherwise cluster-seat
    # against a second instrument.  Seating and withholding are one step
    # (trap T1), so the law runs first and REPORTS what it claimed, and
    # the generic pass excludes exactly that.
    from .config import BASIN_GROUP_SEAT

    if BASIN_GROUP_SEAT:
        basin_group_claimed.update(
            _bake_basin_group_seat_facilities(
                basin_rim_flush_facilities,
                all_placements,
                pack_root,
                xplane_root,
                mesh_path,
                epsilon_metres=epsilon_metres,
                write_changes=write_changes,
                measure_only=measure_only,
                result=result,
                reserved_resources=seat_claimed,
            )
        )
        if basin_group_claimed:
            excluded_resources = set(excluded_resources or ()) | {
                (pack_root or "", resource)
                for resource in basin_group_claimed
            }

    _generic_pass()

    if not BASIN_GROUP_SEAT:
        # THE PRE-AMENDMENT BASIN CLASS (spec section 2.2, owner's in-sim
        # verdict 2026-08-09), kept byte-identical behind the gate.  It
        # runs AFTER the generic pass and over disjoint resources — its
        # members were filtered out above — so no object can be reached
        # by both laws, which is what "generic median/A3/threshold
        # arithmetic does not run for this class" has to mean in code.
        _bake_basin_rim_flush_facilities(
            basin_rim_flush_facilities,
            all_placements,
            pack_root,
            xplane_root,
            mesh_path,
            epsilon_metres=epsilon_metres,
            write_changes=write_changes,
            measure_only=measure_only,
            result=result,
        )

    # Fingerprint this full run so the NEXT mesh build can skip it.
    # Written last, after ``object_rebake.apply`` has rewritten the pack
    # (the recorded ``.obj`` stats must be the post-write ones).  Dry
    # runs record nothing — they changed nothing.
    if write_changes and object_rebake.short_circuit_enabled():
        object_rebake.store_run_record(
            pack_root,
            dsf_path,
            mesh_path,
            object_rebake.build_run_record(
                # (airport-keyed: see the docstring's R2 note)
                pack_root,
                dsf_path,
                mesh_path,
                epsilon_metres=epsilon_metres,
                excluded_resources=excluded_resources,
                referenced_resources=referenced_resources,
                resolve_resource=lambda resource_path: (
                    obj8_reader.resolve_object_resource(
                        resource_path, pack_root, xplane_root
                    )
                ),
                structures_baked=result["structures_baked"],
                structures_needing_pad=result["structures_needing_pad"],
                foot_pad_requests=result["foot_pad_requests"],
                cluster_pad_requests=result["cluster_pad_requests"],
                cluster_seams=result["cluster_seams"],
                cluster_counts=_merge_cluster_counts(result["decisions"]),
                measure_only=measure_only,
            ),
            airport=airport,
        )
    return result


def _report_bridge_findings(icao: str, findings, counts: dict) -> None:
    """Count and log the round-12 bridge findings for one airport.

    A finding is a RECORD, never a decision: nothing here changes a
    verdict, a member set or a seat.  It is logged at verbosity 1 —
    the frame split and the fallback are both owner-facing questions
    (which frame should source the verdict; why this family has no deck)
    and neither must need a debug flag to be seen."""
    from .object_terrain_assembly import (
        BRIDGE_SEAT_COALITION_FINDING,
        BRIDGE_SEAT_FALLBACK_FINDING,
        BRIDGE_VERDICT_FRAME_SPLIT_FINDING,
    )

    for finding in findings or ():
        kind = finding.get("finding")
        if kind == BRIDGE_SEAT_COALITION_FINDING:
            counts["bridge_seat_coalitions"] += 1
            counts["bridge_seat_coalition_outliers"] += len(
                finding.get("outliers", ()))
            UI.vprint(
                1,
                f"  [object-anchor] {icao}: "
                f"{BRIDGE_SEAT_COALITION_FINDING} "
                f"{[r.split('/')[-1] for r in finding.get('coalition_names', ())] or ''}"
                f"{finding.get('reason', '')} — seat delta "
                f"{finding.get('seat_delta_m', 0.0):+.3f} m; outliers "
                + ", ".join(
                    f"{entry['member'].split('/')[-1]} "
                    f"{entry['delta_m']:+.3f} m "
                    f"({entry['land_sample_count']} land / "
                    f"{entry['samples_over_water']} water sample(s))"
                    for entry in finding.get("outliers", ())
                ),
            )
            continue
        if kind == BRIDGE_SEAT_FALLBACK_FINDING:
            counts["bridge_seat_fallbacks"] += 1
            UI.vprint(
                1,
                f"  [object-anchor] {icao}: {BRIDGE_SEAT_FALLBACK_FINDING} "
                f"{[r.split('/')[-1] for r in finding.get('resources', ())]}"
                f" — {finding.get('reason', '')}",
            )
        elif kind == BRIDGE_VERDICT_FRAME_SPLIT_FINDING:
            counts["bridge_verdict_frame_splits"] += 1
            UI.vprint(
                1,
                f"  [object-anchor] {icao}: "
                f"{BRIDGE_VERDICT_FRAME_SPLIT_FINDING} "
                f"{finding.get('resource', '?').split('/')[-1]}: post-mesh "
                f"{finding.get('post_mesh_contract')} (coverage "
                f"{finding.get('post_mesh_coverage_fraction')}) vs "
                f"pipeline {finding.get('pipeline_contract')} (coverage "
                f"{finding.get('pipeline_coverage_fraction')}) — recorded, "
                "the post-mesh verdict still stands (R12-3)",
            )


def rebake_dsf_objects(tile) -> dict:
    """Run Phase 2 for every airport in ``tile``'s worklist.

    Returns a counts dict (``airports_processed``, ``packs_corrected``,
    ``structures_baked``, ``structures_needing_pad``, ``vertices_offset``,
    ``objects_skipped``, ``airports_failed``) for the caller's summary
    line.  Returns immediately — before reading anything — unless
    ``DSF_OBJECT_REANCHOR`` is on (function-local config import so tests
    can drive the flag) AND the tile's ``modify_custom_airports`` cfg var
    allows touching installed packages.  A missing worklist means nothing
    to do.

    One airport's exception is caught, counted and logged; the loop
    continues.  The function itself also never raises (the hook wraps it
    in try/except anyway — belt and braces).
    """
    from .config import DSF_OBJECT_REANCHOR

    if not DSF_OBJECT_REANCHOR:
        return {}

    # Owner-facing switch ("Modify custom airports" in the front ends):
    # off means installed packages stay as their author shipped them.
    # Default True (getattr: tiles built by tools predating the var keep
    # the historic always-rebake behaviour, per ruling R2).
    #
    # It gates PACK MODIFICATION, not the terrain-side answer to it
    # (docs/specs/object-reseat-threshold-spec.md section 2.3): with it
    # off the pass still RUNS, in measure-only mode — every unit routed
    # as if below the reseat threshold, so no bake is ever written, the
    # pad requests still recorded so terrain can adapt to the objects,
    # and the reversion pass still un-bakes anything an earlier run
    # wrote.  Short-circuiting the whole pass (the pre-2026-08-09
    # behaviour) left a previously-baked pack baked, which is the one
    # state this switch exists to prevent.
    measure_only = not getattr(tile, "modify_custom_airports", True)
    if measure_only:
        UI.vprint(
            1,
            "  [object-anchor] modify_custom_airports is off — "
            "measure-only run: no object is reseated, terrain pad "
            "requests are still recorded, and any earlier bake is "
            "reverted to the pack's authored bytes.",
        )

    counts = {key: 0 for key in _COUNT_KEYS}
    try:
        import O4_File_Names as FNAMES

        worklist_path = object_anchor_worklist_path(tile)
        if not os.path.isfile(worklist_path):
            return {}
        with open(worklist_path) as handle:
            worklist = json.load(handle)

        mesh_path = FNAMES.mesh_file(tile.build_dir, tile.lat, tile.lon)
        if not os.path.isfile(mesh_path):
            UI.vprint(
                1,
                f"  [object-anchor] mesh not found at {mesh_path}; "
                "DSF object re-anchor skipped",
            )
            return counts

        # O3 ordering guard (spec section 7): the Phase 2 y-bake samples the
        # BUILT mesh, which is derived from the ``.alt`` raster written in
        # step 1 (with the airport elevation insets baked in).  If the mesh
        # on disk is OLDER than the newest ``.alt`` for this tile, the mesh
        # predates the current elevation state and sampling it would seat
        # every object against a stale surface -- silently, and wrongly.
        # Fail LOUD and skip rather than bake against a stale mesh.
        if not _mesh_is_newer_than_alt(tile, mesh_path):
            UI.vprint(
                0,
                "  [object-anchor] STALE MESH: "
                f"{os.path.basename(mesh_path)} is older than the tile's "
                ".alt (elevation raster) -- the mesh predates the current "
                "insets/grading.  DSF object re-anchor SKIPPED to avoid "
                "seating objects against a stale surface; rebuild the mesh "
                "(step 2) after the .alt (step 1) and re-run.",
            )
            return counts

        corrected_pack_roots: set[str] = set()
        foot_pad_airports: list[dict] = []
        # Round-4 spec R2: worklist entries are per (airport, pack), and
        # WHO OWNS A PLACEMENT is a question about its coordinates, never
        # about which loop iteration is running.  One assigner answers it
        # for the object subsets AND for each raised request's ``icao``.
        claim_assigner = worklist_claim_assigner(worklist.get("airports", []))
        requests_by_icao: dict[tuple[str, str], list[dict]] = {}
        for airport in worklist.get("airports", []):
            icao = airport.get("icao", "?")
            try:
                dsf_path = airport["dsf_path"]
                pack_root = airport["pack_root"]
                xplane_root = airport.get("xplane_root") or worklist.get(
                    "xplane_root"
                )
                if not os.path.isfile(dsf_path):
                    raise OSError(f"DSF not found: {dsf_path}")
                recorded_mtime = airport.get("dsf_mtime")
                if (
                    recorded_mtime is not None
                    and abs(os.path.getmtime(dsf_path) - recorded_mtime)
                    > 1e-6
                ):
                    # Discovery is authoritative; the worklist is
                    # identification only (amendment A5).  Note it and
                    # proceed against the CURRENT DSF.
                    UI.vprint(
                        2,
                        f"  [object-anchor] {icao}: DSF changed since the "
                        "worklist was written; discovery proceeds against "
                        "the current DSF",
                    )
                # Ruling R4: feature-A/B-consumed objects (terrain
                # adapted TO them) never receive the Phase 2 y-bake —
                # and, from ONE classification, the section-2.2 basin
                # facilities that take the dedicated rim-flush law
                # instead, plus the R6-3 TERRAIN_CARRIED bridges routed
                # to the abutment-grade seat.  Empty — read nothing —
                # while the object-terrain gates are off.
                from .object_terrain_assembly import (
                    post_mesh_object_terrain_records,
                )

                terrain_records = post_mesh_object_terrain_records(
                    dsf_path, xplane_root, pack_root=pack_root
                )
                excluded_resources = terrain_records.exclusions
                _report_bridge_findings(
                    icao, getattr(terrain_records, "bridge_findings", ()),
                    counts,
                )
                airport_result = discover_and_rebake_airport(
                    dsf_path,
                    mesh_path,
                    pack_root,
                    xplane_root,
                    excluded_resources=excluded_resources,
                    measure_only=measure_only,
                    basin_rim_flush_facilities=(
                        terrain_records.basin_rim_flush_facilities
                    ),
                    bridge_abutment_seat_candidates=(
                        terrain_records.bridge_abutment_seat_candidates
                    ),
                    airport=icao,
                    claims_placement=(
                        lambda latitude, longitude, _dsf=dsf_path,
                        _icao=icao: (
                            claim_assigner(_dsf, latitude, longitude) == _icao
                        )
                    ),
                )
            except Exception as exception:
                # Per-airport containment: one broken airport never
                # blocks the next (pure-reporter philosophy,
                # verification.verify_and_log).
                counts["airports_failed"] += 1
                UI.vprint(
                    1,
                    f"  [object-anchor] {icao}: re-anchor failed "
                    f"({exception}); continuing with the next airport",
                )
                continue

            _report_bridge_findings(
                icao, airport_result.get("bridge_findings", ()), counts
            )
            counts["airports_processed"] += 1
            if airport_result.get("short_circuited"):
                counts["airports_up_to_date"] += 1
                UI.vprint(
                    1,
                    f"  [object-anchor] {icao}: re-anchor up to date — "
                    f"skipped {airport_result['structures_up_to_date']} "
                    "structure(s) (mesh, DSF, pack objects and gates all "
                    "unchanged; O4_REANCHOR_SHORT_CIRCUIT=0 to force)",
                )
            counts["structures_baked"] += airport_result["structures_baked"]
            counts["structures_needing_pad"] += airport_result[
                "structures_needing_pad"
            ]
            counts["vertices_offset"] += airport_result["vertices_offset"]
            counts["objects_skipped"] += len(airport_result["skipped"])
            counts["objects_reverted"] += len(
                airport_result["objects_reverted"]
            )
            counts["objects_partially_baked"] += len(
                airport_result["partially_baked"]
            )
            for resource_path, summary in airport_result["partially_baked"]:
                UI.vprint(
                    2,
                    f"  [object-anchor] {icao}: partially baked "
                    f"{resource_path} — {summary}",
                )
            for resource_path in airport_result["objects_reverted"]:
                UI.vprint(
                    1,
                    f"  [object-anchor] {icao}: reverted {resource_path} "
                    "to its authored placement (excluded from the current "
                    "decision; stale live bake removed)",
                )
            for resource_path in airport_result["reversions_missing_backup"]:
                UI.vprint(
                    0,
                    f"  [object-anchor] {icao}: {resource_path} is "
                    "excluded and still carries a stale bake but its "
                    ".anchor_bak is missing — left untouched, NOT reverted",
                )
            # The section-2.2 basin class, per facility, in the tile log
            # the integration report reads: what was seated, where, and
            # every clearance finding (item 7 is a FINDING, so it must
            # be visible without a debug flag).
            basin_records = list(
                airport_result.get("basin_rim_flush", ())
            ) + list(airport_result.get("basin_group_seat", ()))
            if basin_records:
                baked_count = sum(
                    1 for record in basin_records if record.get("baked"))
                finding_count = sum(
                    1 for record in basin_records
                    if record.get("clearance_finding"))
                counts["basin_rim_flush_seated"] += baked_count
                counts["basin_clearance_findings"] += finding_count
                UI.vprint(
                    1,
                    f"  [object-anchor] {icao}: {baked_count} of "
                    f"{len(basin_records)} basin facility(ies) seated by "
                    "the basin seat law, "
                    f"{finding_count} clearance finding(s)",
                )
                for record in basin_records:
                    UI.vprint(
                        2,
                        f"  [object-anchor] {icao}: basin "
                        f"{record['resources']}: {record['decision']}",
                    )
            counts["foot_pad_requests"] += len(
                airport_result["foot_pad_requests"]
            )
            counts["cluster_pad_requests"] += len(
                airport_result.get("cluster_pad_requests", ())
            )
            if (
                airport_result["foot_pad_requests"]
                or airport_result.get("cluster_pad_requests")
            ):
                from . import object_footprints
                from .config import DSF_OBJECT_FOOT_PAD_MARGIN_M

                def _rings(request) -> list:
                    """The request's rings under the footprint-hugging
                    law (object-reseat-threshold-spec section 2.5): its
                    contact-band TRIANGLE hulls dilated by the margin and
                    unioned, one ring per connected component (v2b — per
                    PART hulls were plan boxes, and boxes were the
                    defect).  A request with no grouping (a hand-built
                    one) falls back to its flat point list as a SINGLE
                    part — the single-part case of the same law."""
                    parts = [
                        list(part)
                        for part in (
                            getattr(request, "contact_parts_lonlat", ())
                            or (request.contact_points_lonlat,)
                        )
                    ]
                    rings = object_footprints.foot_pad_rings(
                        parts, DSF_OBJECT_FOOT_PAD_MARGIN_M
                    )
                    # OBSERVABILITY, never refusal (section 2.5 v2b): a
                    # ring component this big is the shape the owner saw
                    # in the sim, so it is named on the build that made
                    # it rather than found later in a patch diff.
                    for ring in rings:
                        area = _ring_area_square_metres(ring)
                        if area > OBJECT_PAD_RING_REPORT_AREA_M2:
                            UI.vprint(
                                1,
                                f"  [object-anchor] {icao}: pad ring "
                                f"component {area:,.0f} m² — "
                                f"{request.resource_path}",
                            )
                    return rings

                requests: list[dict] = [
                    {
                        "kind": "foot",
                        "resource_path": request.resource_path,
                        "latitude": request.latitude,
                        "longitude": request.longitude,
                        "base_y": request.base_y,
                        "residual_metres": request.residual_metres,
                        "target_ground_metres": (
                            request.target_ground_metres
                        ),
                        "rings_lonlat": _rings(request),
                    }
                    for request in airport_result["foot_pad_requests"]
                ]
                # Per-CLUSTER requests (spec section 5.3).  The rings are
                # the same builder over the residual group's contact
                # PARTS — one ring per connected component of their
                # dilated hulls, never one hull over the group
                # (object-reseat-threshold-spec section 2.5); residual
                # accounting is unchanged, so one request record still
                # answers for one residual group and simply carries
                # several rings.  The PAD LAW's clip against graded
                # pavement
                # (spec section 5.1 clause 2) belongs to the pad
                # CONSUMER, which does not exist yet — the ring recorded
                # here is therefore unclipped and flagged as such, and
                # ``object_footprints.clip_pad_ring_against_pavement``
                # is the single function that consumer must clip with.
                # Nothing is emitted into the terrain from this file
                # today, so no pavement can be deformed by it.
                requests.extend(
                    {
                        "kind": "cluster",
                        "cluster_id": request.cluster_id,
                        "structure_index": request.structure_index,
                        "resource_path": request.resource_path,
                        "latitude": request.latitude,
                        "longitude": request.longitude,
                        "base_y": request.base_y,
                        "residual_metres": request.residual_metres,
                        "target_ground_metres": (
                            request.target_ground_metres
                        ),
                        "part_count": request.part_count,
                        "over_relief_cap": request.over_relief_cap,
                        "pavement_clipped": False,
                        "rings_lonlat": _rings(request),
                    }
                    for request in airport_result.get(
                        "cluster_pad_requests", ()
                    )
                )
                # THE REQUEST'S ICAO IS ITS OWN COORDINATES' ANSWER
                # (round-4 spec R2), never the loop label: a request
                # standing on OTHH's ground is filed under OTHH even
                # when the pack it came from was queued for another
                # airport.  Same assigner as the object subsets, so the
                # two can never disagree.
                for request_record in requests:
                    claimed = (
                        claim_assigner(
                            dsf_path,
                            request_record.get("latitude"),
                            request_record.get("longitude"),
                        )
                        or icao
                    )
                    requests_by_icao.setdefault(
                        (claimed, pack_root), []
                    ).append(request_record)
                if airport_result["foot_pad_requests"]:
                    UI.vprint(
                        1,
                        f"  [object-anchor] {icao}: "
                        f"{len(airport_result['foot_pad_requests'])} foot "
                        "pad request(s) — a rigid offset could not seat "
                        "every foot; recorded in "
                        + OBJECT_FOOT_PAD_SIDECAR_FILENAME,
                    )
                cluster_requests = airport_result.get(
                    "cluster_pad_requests", ()
                )
                if cluster_requests:
                    over_cap = sum(
                        1
                        for request in cluster_requests
                        if request.over_relief_cap
                    )
                    UI.vprint(
                        1,
                        f"  [object-anchor] {icao}: "
                        f"{len(cluster_requests)} cluster pad request(s) "
                        "— seated clusters whose residual only terrain "
                        f"can close ({over_cap} over the "
                        "DSF_OBJECT_PAD_MAX_RELIEF_M cap, kept as "
                        "findings); recorded in "
                        + OBJECT_FOOT_PAD_SIDECAR_FILENAME,
                    )
            cluster_seams = airport_result.get("cluster_seams", ())
            bridge_seams = [
                seam for seam in cluster_seams if seam.kind == "bridge"
            ]
            if bridge_seams:
                counts["cluster_bridge_seams"] += len(bridge_seams)
                worst = max(seam.seam_metres for seam in bridge_seams)
                UI.vprint(
                    1,
                    f"  [object-anchor] {icao}: {len(bridge_seams)} bridge "
                    "seam(s) — elevated components spanning two seated "
                    "clusters joined their majority-contact side; worst "
                    f"reported residual {worst:.2f} m (never averaged "
                    "across, spec section 4.2a)",
                )

            for resource_path, reason in airport_result["skipped"]:
                UI.vprint(
                    2,
                    f"  [object-anchor] {icao}: skipped {resource_path}: "
                    f"{reason}",
                )
            had_work = (
                airport_result["objects_written"]
                or airport_result["skipped"]
                or airport_result["decisions"]
            )
            if had_work:
                UI.vprint(
                    1,
                    f"  [object-anchor] {icao}: "
                    f"{airport_result['structures_baked']} structure(s) "
                    f"re-baked across "
                    f"{len(airport_result['objects_written'])} object "
                    f"file(s), {airport_result['vertices_offset']} "
                    f"vertices offset"
                    + (
                        f", {airport_result['structures_needing_pad']} "
                        "structure(s) flagged as needing a pad"
                        if airport_result["structures_needing_pad"]
                        else ""
                    )
                    + (
                        f", {len(airport_result['skipped'])} skipped"
                        if airport_result["skipped"]
                        else ""
                    )
                    + (
                        f", {len(airport_result['partially_baked'])} "
                        "partially baked"
                        if airport_result["partially_baked"]
                        else ""
                    ),
                )
            # The span limit's OWN skips.  A supporter-fate skip quotes
            # its parent's reason verbatim, so it contains the span
            # phrase too — exclude it here and count it on its own line
            # below, or the two summaries double-count each other.
            structures_left_at_authored = sum(
                1
                for _pool, decision in airport_result["decisions"]
                for structure in decision.structures
                if structure.skip_reason
                and object_anchor.GROUND_SPAN_SKIP_REASON_PHRASE
                in structure.skip_reason
                and not structure.skip_reason.startswith(
                    object_anchor.SUPPORTER_FATE_SKIP_REASON_PHRASE
                )
            )
            if structures_left_at_authored:
                UI.vprint(
                    1,
                    f"  [object-anchor] {icao}: "
                    f"{structures_left_at_authored} structure(s) left at "
                    "authored elevations (ground span > limit)",
                )
            # The reseat threshold's OWN population (reseat-threshold
            # spec sections 2.1, 2.3): units the pack was deliberately
            # not modified for.  Never folded into the "left at authored
            # elevations" or refusal counts above — a refusal is a unit
            # nothing could seat, this is a unit that did not need
            # seating.  Two exclusions keep one unit from being counted
            # twice: supporter-fate skips quote their parent's reason
            # verbatim (counted on their own line below, exactly as the
            # span limit's are), and a clustered structure echoes its
            # clusters' reason (counted as CLUSTERS, so only the
            # structure-TAGGED reason counts here).
            structures_below_threshold = sum(
                1
                for _pool, decision in airport_result["decisions"]
                for structure in decision.structures
                if structure.skip_reason
                and object_anchor.BELOW_BAKE_THRESHOLD_STRUCTURE_TAG
                in structure.skip_reason
                and not structure.skip_reason.startswith(
                    object_anchor.SUPPORTER_FATE_SKIP_REASON_PHRASE
                )
            )
            clusters_below_threshold = sum(
                (decision.cluster_counts or {}).get(
                    "clusters_below_threshold", 0
                )
                for _pool, decision in airport_result["decisions"]
            )
            if structures_below_threshold or clusters_below_threshold:
                counts["units_below_bake_threshold"] += (
                    structures_below_threshold + clusters_below_threshold
                )
                UI.vprint(
                    1,
                    f"  [object-anchor] {icao}: "
                    f"{structures_below_threshold} structure(s) and "
                    f"{clusters_below_threshold} cluster(s) under the "
                    "reseat threshold — left exactly as the pack author "
                    "shipped them; the terrain adapts to them instead "
                    "(DSF_OBJECT_BAKE_MIN_DELTA_M; "
                    "O4_DSF_OBJECT_BAKE_MIN_DELTA_M=0 to reseat every "
                    "non-zero deviation)",
                )
            # Supporter fate (DSF_OBJECT_SUPPORTER_FATE): elevated
            # structures left at their authored elevations because the
            # supporter whose ground they inherit did not move.  ONE
            # summary line per airport — HECA alone produces thousands.
            structures_sharing_supporter_fate = sum(
                1
                for _pool, decision in airport_result["decisions"]
                for structure in decision.structures
                if structure.skip_reason
                and structure.skip_reason.startswith(
                    object_anchor.SUPPORTER_FATE_SKIP_REASON_PHRASE
                )
            )
            if structures_sharing_supporter_fate:
                UI.vprint(
                    1,
                    f"  [object-anchor] {icao}: "
                    f"{structures_sharing_supporter_fate} elevated "
                    "structure(s) left at authored elevations because "
                    "their supporter was skipped (they inherit its "
                    "ground and share its fate; O4_SUPPORTER_FATE=0 to "
                    "restore the old split behaviour)",
                )
            if (
                (
                    airport_result["objects_written"]
                    or airport_result["objects_reverted"]
                )
                and pack_root not in corrected_pack_roots
            ):
                corrected_pack_roots.add(pack_root)
                counts["packs_corrected"] += 1
                UI.vprint(
                    1,
                    "  [object-anchor] restart X-Plane (objects are "
                    f"cached): {os.path.basename(pack_root) or pack_root}",
                )

        # Refresh the foot-pad sidecar every run: write it when any
        # request was raised, remove a stale one when none remains.
        #
        # THE ``emitted`` SECTION IS NOT OURS (per-cluster seating spec
        # section 5.2, version 3).  The pad CONSUMER (``object_pads``,
        # auto-patch phase) records there which pads it built and the
        # fingerprint of the seat that produced each.  That section is the
        # whole point of the next-build convergence loop: once terrain
        # meets the feet the residuals fall under
        # DSF_OBJECT_FOOT_PAD_RESIDUAL_M and the REQUESTS vanish — which
        # is exactly when the emitted pads must NOT.  So this refresh
        # rewrites the requests and carries the consumer's section across
        # untouched, and a request-empty sidecar that still holds records
        # is WRITTEN (emptied of requests) rather than removed.  Deleting
        # it would drop every pad on the next build, un-converge the loop,
        # and re-raise the same requests: a permanent oscillation.
        # One block per CLAIMING airport (round-4 spec R2), in a stable
        # order so a converged build stays byte-stable.
        foot_pad_airports = [
            {
                "icao": claimed_icao,
                "pack_root": claimed_pack_root,
                "requests": claimed_requests,
            }
            for (claimed_icao, claimed_pack_root), claimed_requests in sorted(
                requests_by_icao.items(),
                key=lambda item: (str(item[0][0]), str(item[0][1])),
            )
        ]
        sidecar_path = os.path.join(
            os.path.dirname(worklist_path),
            OBJECT_FOOT_PAD_SIDECAR_FILENAME,
        )
        emitted_section = []
        try:
            if os.path.isfile(sidecar_path):
                with open(sidecar_path) as handle:
                    previous = json.load(handle)
                if isinstance(previous, dict):
                    # A section written under an older SIDECAR VERSION is
                    # the retired ring law's geometry (section 2.5): it is
                    # dropped here rather than carried across, and the
                    # convergence loop re-derives from the fresh requests.
                    # The consumer refuses it on read too — this is the
                    # producer half of the same gate.
                    stale = (
                        int(previous.get("version") or 0)
                        < OBJECT_FOOT_PAD_SIDECAR_VERSION
                    )
                    emitted_section = [] if stale else [
                        record
                        for record in (previous.get("emitted") or ())
                        if isinstance(record, dict)
                    ]
                    if stale and previous.get("emitted"):
                        UI.vprint(
                            1,
                            "  [object-anchor] pad sidecar was version "
                            f"{previous.get('version')}; its "
                            f"{len(previous.get('emitted') or ())} emitted "
                            "record(s) predate the footprint-hugging ring "
                            "law and were dropped — the next build "
                            "re-derives them",
                        )
        except (OSError, ValueError, TypeError):
            emitted_section = []
        if foot_pad_airports or emitted_section:
            payload = {
                "version": OBJECT_FOOT_PAD_SIDECAR_VERSION,
                "tile": worklist.get("tile"),
                "airports": foot_pad_airports,
            }
            if emitted_section:
                payload["emitted"] = emitted_section
            with open(sidecar_path, "w") as handle:
                json.dump(payload, handle, indent=1)
        elif os.path.isfile(sidecar_path):
            os.remove(sidecar_path)
    except Exception as exception:
        # Belt and braces: a reporter must never fail the tile.
        try:
            UI.vprint(
                1,
                "  [object-anchor] post-mesh DSF object re-anchor failed: "
                f"{exception}",
            )
        except Exception:
            pass
    return counts
