"""THE RETIRED v1 PHASE 2 — the tile-level object y-bake (``rebake_dsf_objects``)
and its findings reporter.

MOVED here out of ``post_mesh.py`` on 2026-09-17 (lane ``v1retire`` round 1,
seam S3 of RULINGS 2026-09-13aw).  Stage A (RULINGS 2026-09-13az) stopped
calling it — ``O4_Mesh_Utils``' post-mesh dispatch is
``engine_v2.rebake_after_mesh`` and nothing else — but it stayed inside
``post_mesh``, a KEEP module, where its ONE call to
``object_terrain_assembly.post_mesh_object_terrain_records`` re-admitted the
whole v1 tree into the production import closure.

This module is a DELETE module: round 2 removes it with the rest of v1.  Its
bodies are byte-identical to what shipped; only the names it used to read
off its own module (``post_mesh``'s helpers, the count keys, the sidecar
constants) are imported at the top now.
"""

from __future__ import annotations

import json
import os

import O4_UI_Utils as UI

from . import object_anchor
from .post_mesh import (
    OBJECT_FOOT_PAD_SIDECAR_FILENAME,
    OBJECT_FOOT_PAD_SIDECAR_VERSION,
    OBJECT_PAD_RING_REPORT_AREA_M2,
    _COUNT_KEYS,
    _mesh_is_newer_than_alt,
    _ring_area_square_metres,
    discover_and_rebake_airport,
    object_anchor_worklist_path,
    worklist_claim_assigner,
)


def _report_bridge_findings(icao: str, findings, counts: dict) -> None:
    """Count and log the round-12 bridge findings for one airport.

    A finding is a RECORD, never a decision: nothing here changes a
    verdict, a member set or a seat.  It is logged at verbosity 1 —
    the frame split and the fallback are both owner-facing questions
    (which frame should source the verdict; why this family has no deck)
    and neither must need a debug flag to be seen."""
    from .object_terrain_kinds import (
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
