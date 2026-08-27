# Basin founding from unmatched below-grade regions

**Status:** APPROVED (owner 2026-08-26: "spec and implement the follow-up
dockets"). Fable-authored. Follow-up docket A of the basin-region round
(`docs/specs/basin-region-footprint-spec.md`, landed `8cd96e62`).

## 1. Problem

Region extension (the landed round) can only widen an EXISTING basin
record. LEMD got one only because a single member
(`Ground-FSX-LEMD36.obj`) happens to be fully buried and escaped the
358-object shared-anchor mega-pool as its own `BOWL_UNDER_DECK` interface.
A pack whose below-grade members ALL pool into a `FLAT_CONFIRMED`
mega-structure produces ZERO basin records — the region is derived,
matches nothing, and today is only logged. The pit is then never cut and
the below-grade shell is buried: the exact LEMD defect class, minus the
luck.

## 2. Design

All changes in `object_terrain_assembly.basin_trench_structures` (the ONE
producer both the emitter and `basin_rim_flush_facilities` group from —
founding there keeps lockstep by construction), plus one region-side field.

### 2.1 Admission

After region extension, each region that intersects NO record footprint
(basin OR feature-A tunnel — a region under a tunnel record is that
structure's business, never founded twice) founds a new record iff ALL of:

1. **Depth:** region `solid_minimum_y_m` ≤ `−BOWL_MIN_BELOW_GRADE_LEVEL_DEPTH_M`
   (3.0). Founding is inference without an interface; regions in the
   2.5–3.0 m band stay extension-only evidence and are logged, not founded.
2. **Openness (R13):** nothing of the pack's own stands over it. Region
   above-grade coverage — computed with the SAME triangle machinery as the
   region itself, clipping solid triangles to their portion ABOVE
   `+GROUND_CONTACT_BAND_HALF_WIDTH_M`, decal gate identical, intersected
   with the region — must be ≤ `BOWL_MAX_ABOVE_GRADE_AREA_FRACTION` of the
   region area. A covered unmatched region is a bore/tunnel candidate,
   NOT founded; it keeps the loud unmatched log line with its coverage
   fraction so it is attributable.
3. Area ≥ `TRENCH_SPINE_MIN_FOOTPRINT_AREA_M2` (already guaranteed by
   region admission — assert, don't re-derive).

To support (2), `below_grade_regions()` additionally records per region
the above-grade coverage fraction (computed with the same machinery as
the region; one instrument, never a second scan elsewhere). This is a
new defaulted field on `BelowGradeRegion`; `None` reads as "not
computed" and REFUSES founding with a loud log line naming the region —
never a silent guess. Cache version bumps (v22 → v23).

**Amendment 1 (Fable ruling, 2026-08-27 — the coverage pass is LAZY BY
PREMATCH).** Measured: the eager coverage pass cost 33.4 s at LEMD
(12.3 s after an exact bbox pre-filter) against 0.65 s for the region
pass itself — for a number consumed ONLY when a region is unmatched,
which at LEMD (and the common case) is never. The coverage fraction is
computed inside `classify_object_terrain_features` ONLY for regions that
intersect NO ground interface's `below_grade_footprint` (the interfaces
are in hand in the same function; a region intersecting one will match
its record in assembly). Matched-at-classify regions carry `None`, which
founding's None-refusal already handles loudly — the interface-dropped
corner (region prematched but its record never built) therefore degrades
to a REFUSED founding with a log line, never a silent guess or a silent
32 s. The implementer's exact bbox pre-filter (a placement whose whole
geometry misses every candidate region's bbox is skipped) is RATIFIED
and kept for when coverage does run. Expected LEMD cost: the 0.65 s
region pass only.

**Amendment 2 (Fable ruling, 2026-08-27 — the second field is
IN-SPEC).** `contributor_area_m2_by_resource` is ratified: §2.2's tight
contributor list needs per-contributor clipped areas that exist only in
the region pass; re-deriving them in assembly would be a second
instrument over the same geometry (the census-wrapper class). §2.1's
"a new defaulted field" reads as "new defaulted fields".

### 2.2 The founded record

A `TunnelStructure` with:
- `object_resources`: contributing resources whose clipped below-grade
  area within the region is ≥ 5% of the region area or ≥ 100 m²
  (a TIGHT list — this field feeds `basin_rim_flush_facilities` grouping
  and hence seating; sweeping a shared-anchor family's 350 at-grade
  members in would be the LSGG y-bake starvation class. Sorted.)
- `anchor_longitude_latitude`: the region polygon's representative point
  (shapely `representative_point`, guaranteed interior), converted by the
  ONE frame path used in the landed round; `frame_origin_longitude_latitude`
  per the same convention; `heading_degrees` 0.0; `placement_kind` "OBJECT";
  `above_ground_offset_m` 0.0 (regions are already in effective heights).
- `body_depth_m = −solid_minimum_y_m` (the region's thickness-gated min);
  `solid_minimum_y_m` the same value (one instrument — for a founded
  record there is no separate deck-face population, so the §2.2
  disagreement gate is vacuous by construction).
- `deck_footprint = solid_outline_footprint =` the region polygon (frame
  coords via the landed round's converter); `roof_footprint None`;
  `mouth_polygons`/`mouth_depth_samples` empty;
  `terrain_feature = TERRAIN_FEATURE_BASIN`; `cuts_pavement = True`
  (admission (2) is exactly R13's open-pit predicate at region level).

Floor and rim then flow through the existing law
(`basin_trench_floor_elevation_m` with margins) untouched.

### 2.3 What founding does NOT do (deliberate, do not widen)

- NO new ruling-R4 exclusions: exclusions stay interface-driven. Founded
  records change terrain, not the y-bake population. (Seating interplay
  is docket B's design — keep this boundary clean.)
- NO founding from regions overlapping a BRIDGE record's footprint
  (log only): a bridge deck's under-space is the bridge contract's.

### 2.4 Gate

`config.BASIN_REGION_FOUNDING` (env `O4_BASIN_REGION_FOUNDING`, default
ON, `=0` → founding disabled, byte-identical to the landed round).
Document beside `BASIN_REGION_FOOTPRINT`; salt into the classification
cache key exactly as the landed gates are.

## 3. Tests (extend `tests/test_object_basin_trench.py`, synthetic)

1. **Founds:** wall objects forming a −6 m region, no interface record →
   one founded record; floor via the law = rim + (−6) − 1.5; ring ≈ the
   known rectangle; `cuts_pavement` True; contributors list tight (an
   object contributing 2 m² is absent).
2. **Depth refusal:** the same region at −2.8 m → NOT founded, logged.
3. **Openness refusal:** same region with a solid deck spanning it above
   grade → NOT founded, logged with the coverage fraction.
4. **No double-found:** a region intersecting an existing basin record →
   extension only (landed behavior), zero founded records.
5. **Stale-sidecar refusal:** a `BelowGradeRegion` without the coverage
   field → no founding, the stale-sidecar log line fires.
6. **Gate:** `O4_BASIN_REGION_FOUNDING=0` → no founded records,
   extension unchanged.

Run once (ledger): `tests/test_object_basin_trench.py`,
`tests/test_object_tunnel_terrain.py`, `tests/test_object_bridge_terrain.py`,
`tests/test_harness.py`.

## 4. Acceptance

**LEMD is the inertness control, no new build:** at LEMD's thresholds the
T4S region matches the existing record, so founding must be INERT there —
verify on the road-feed-refresh build's log (running as this spec is
written; artifact under `/tmp/harness/`) or an offline classification
probe: zero founded records at LEMD, T4S trench numbers identical to the
landed round (27,346.5 m² / floor 587.75). Materiality floor 0.01 m /
1% area; attempt cap 2; a second miss is STOP-and-report.

Build-time impact: the above-grade coverage pass reuses the loaded
geometry and the same pre-scan skip; estimated ≤ the region pass itself
(~1 s LEMD-class, ~0 where no below-grade geometry). Suspended timing
law — ledger tripwire only.
