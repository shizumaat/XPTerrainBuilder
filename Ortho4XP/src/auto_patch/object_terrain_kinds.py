"""The decision kinds, findings and sampling steps the POST-MESH pass and the
object-terrain assembly share — ONE spelling, in a module the v1 deletion does
not take (seam S3, RULINGS 2026-09-13aw, lane ``v1retire`` round 1, 2026-09-17).

`post_mesh` is a KEEP module and imported nine of these names out of
`object_terrain_assembly` at eight sites; that single edge re-admitted the
whole v1 tree into the production import closure.  The values are MOVED here
unchanged and `object_terrain_assembly` re-exports them, so for the one round
the two coexist there is no second copy — and the tests that reach them as
``assembly.BASIN_GROUP_SEAT_DECISION_KIND`` keep working.

They are strings recorded in the rebake provenance and two sampling densities;
no law value lives here (those are `config.py` / `auto_patch_v2/law/*.toml`).
"""

from __future__ import annotations

# ── Trench / basin geometry sampling ──────────────────────────────────

# Width of the flat datum band beyond the flush-wall setback (user
# screenshots 2026-07-18c).  Its two companions —
# ``_TUNNEL_WALL_SETBACK_M`` and ``_TUNNEL_FLOOR_OWNED_CLEARANCE_M`` —
# are read only inside ``object_terrain_assembly`` and stay there.
_TUNNEL_RIM_BAND_WIDTH_M = 0.6

# Basin rim sampling density: samples whose MEDIAN becomes ``R_est``.
# The spec's bound is "every <= 10 m"; a 50 x 50 m OTHH bowl therefore
# contributes ~20 samples and the whole airport ~tens — the per-facility
# cost is O(perimeter / 10) point DEM reads, which is nothing beside the
# union work already in that pass (the build-time tripwire is stated in
# the spec section 3 item 4).
_BASIN_RIM_SAMPLE_STEP_M = 10.0

# R6-3 abutment-grade sampling density.  The abutment LINE is the land
# witness the classifier certified (``abutment_reaches_grade``), and its
# median built-mesh elevation is the seat target, so the samples must
# resolve the ground the abutment actually stands on — an abutment is
# tens of metres long, not hundreds.  Half the basin rim step: the rim
# band is a long closed outline where 10 m is plenty; two short lines
# want a denser median.
_ABUTMENT_GRADE_SAMPLE_STEP_M = 5.0


# ── Seat decision kinds ───────────────────────────────────────────────

#: Decision kind recorded in the rebake provenance for a basin facility
#: seated by the section-2.2 rim-flush law.  ONE spelling, read by the
#: post-mesh pass, the provenance writer and the tests.
BASIN_RIM_FLUSH_DECISION_KIND = "basin_rim_flush"

#: Decision kind recorded in the rebake provenance for a basin facility
#: seated RIGIDLY AS A GROUP (docket B, docs/specs/basin-group-seat-spec.md
#: §2.3 item 3).  ONE spelling, read by the post-mesh pass, the
#: provenance writer and the tests.  A record carrying this kind was
#: seated onto the group's single datum plane ``G``; a record carrying
#: :data:`BASIN_RIM_FLUSH_DECISION_KIND` was seated by the
#: pre-amendment interface-member law (``O4_BASIN_GROUP_SEAT=0``).
BASIN_GROUP_SEAT_DECISION_KIND = "basin_group_seat"

#: Decision kind recorded in the rebake provenance for a TERRAIN_CARRIED
#: bridge seated by the R6-3 abutment-grade law.  ONE spelling, read by
#: the post-mesh pass, the provenance writer and the tests.
BRIDGE_ABUTMENT_SEAT_DECISION_KIND = "bridge_abutment_seat"

#: Which limb produced a seat candidate (round-12 R12-2).  ONE spelling
#: each, read by the post-mesh records, the findings and the tests.
SEAT_SOURCE_CLASSIFIED = "classified"
SEAT_SOURCE_REFUSED_VIADUCT = "refused_viaduct"


# ── Counted findings the post-mesh pass reports ───────────────────────

#: ``bridge_seat_fallback`` (R12-2): a REFUSED family that has no
#: measurable deck, so it keeps today's generic y-bake instead of the
#: rigid deck-top seat.  ``bridge_verdict_frame_split`` (R12-3): the
#: post-mesh classification derived a different contract for a resource
#: than the pipeline-time classification cached for the same pack — two
#: frames, two verdicts, one pack.  Both are RECORDED; neither changes
#: which verdict is used.
BRIDGE_SEAT_FALLBACK_FINDING = "bridge_seat_fallback"
#: ``bridge_seat_coalition`` (amendment 4): a family that DID seat, and
#: which of its deck members authored the level.  Informational, not a
#: defect — but counted, because its OUTLIERS are the standing evidence
#: trail for the canal-floor residual B2 cannot see (a member whose end
#: lines cross unattributed water reads low and lands here).
BRIDGE_SEAT_COALITION_FINDING = "bridge_seat_coalition"
BRIDGE_VERDICT_FRAME_SPLIT_FINDING = "bridge_verdict_frame_split"
