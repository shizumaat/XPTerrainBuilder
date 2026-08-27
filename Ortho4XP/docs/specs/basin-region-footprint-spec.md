# Basin region footprint + solid-witness floor key

**Status:** APPROVED (owner rulings 2026-08-26, docs/RULINGS.md "LEMD T4S
basin"). Fable-authored. One implementation round.

**Ground truth for every number here:** the pack's own shipped mesh patch
`Aerosoft - LEMD Madrid - 2 - Mesh/Patches/+40-010/+40-004/LEMD.patch.osm`
— T4S pit ring 87 verts, 27,612 m², rim flush at the pack's flat 594.625
datum, floor at datum −18.0 (a ~10.9 m overcut past the family's deepest
genuine solid, −7.09 m). Reference point 40.492365, −3.569554.

## 1. Problem (measured 2026-08-26, engine 1.50.1703 build)

1. **Footprint.** LEMD's T4S family is 358 objects stacked on ONE placement
   anchor (40.4927644, −3.5647884). The mega-pool classifies
   `FLAT_CONFIRMED`; only the fully-buried `LEMD_OBJ-Ground-FSX-LEMD36.obj`
   escapes as `BOWL_UNDER_DECK`, so the basin record's footprint is that one
   member (12,434 m² = 44.9% of the authored ring). The below-grade walls of
   LEMD37/85/03 (−7.09/−7.03/−6.75) and Terminal4sBlue-LEMD35 (−5.86) are
   invisible inside the mega-structure. Emitted trench: 10,065 m² = 36.5%.
2. **Seniority.** `building8` (the terminal shell, 33,471 m² computed
   footprint) CONTAINS the whole authored pit; the pad-authority
   interaction left 63.5% of the pit uncut — 100% of the shortfall.
3. **Depth.** Amendment 3's open-pit deck-face key (no margins) cut the
   floor at 586.01 = R_est 593.03 − 7.016 — **0.07 m above** the family's
   deepest genuine solid (−7.087). The reference pack floor is 576.62.

## 2. Design

### 2.1 The region instrument (new, `object_terrain_features`)

New pure function (name indicative, follow module conventions):

    below_grade_regions(placements, geometry_by_resource) -> list[BelowGradeRegion]

For every placement (stock-library resources excluded, as classify already
does): for every solid triangle of its geometry, EXCLUDING triangles of
decal components — a connected solid component whose own vertical extent
(max_y − min_y) is `< config.MIN_SOLID_PART_THICKNESS_M` (§2.1 of the
tunnel-trench spec; ONE notion, reuse the constant, never a new one) — take
the sub-polygon where the interpolated vertex height is below
`−TRENCH_SPINE_MIN_DEPTH_M` (2.5; clip the triangle against the plane, do
NOT keep whole triangles on a min-vertex test — a long ramp panel must
contribute only its below-threshold portion). Transform by placement
(heading + anchor) into the classification's horizontal frame. Union all
sub-polygons, morphologically close at `AT_GRADE_FOOTPRINT_CLOSE_M` (2.0,
buffer out/in), split into connected regions, fill interior holes (exterior
ring only), drop regions below `TRENCH_SPINE_MIN_FOOTPRINT_AREA_M2`
(1000 m²).

Each `BelowGradeRegion` carries: the region polygon, the thickness-gated
minimum solid y over the placements' clipped geometry inside it
(`solid_minimum_y_m`; LEMD: −7.087), and the contributing resource names
(logging only).

Perf guard: pre-scan per-resource solid min y once (cheap); a resource with
min y ≥ −2.5 contributes nothing and is skipped before any triangle work.
Compute once per classification, only when `config.OBJECT_BASIN_TRENCH` and
the new gate (§2.4) are on; store on `ClassificationResult` as a new
defaulted field so old cached/hand-built results read as "no regions".
**Cache: the classification sidecar (`o4_object_terrain_classification_*`)
must version-bump so stale sidecars without regions are rebuilt.**

Validated: this exact recipe reproduces the authored T4S ring at
92.7–93.0% IoU for thresholds 1.5–3.0 m (insensitive), 27.6–28.2k m².
The two `AESlite-LEMD-VOR-15-T4S-*.obj` −50 m decals are excluded by the
thickness gate (without it the union is 2.08M m²).

### 2.2 Region extension of basin records (`object_terrain_assembly.basin_trench_structures`)

After building the records as today: for each record whose footprint
intersects a region, replace `deck_footprint` and
`solid_outline_footprint` with (region ∪ existing footprint) and set
`solid_minimum_y_m = min(existing, region.solid_minimum_y_m)`. All other
record fields — `object_resources`, `cuts_pavement`, anchor, depth bound —
are UNTOUCHED (membership drives R4 exclusions and rim-flush seating
grouping; widening it is out of scope). A region intersecting NO record is
NOT founded as a new basin this round: log it loudly (area, centroid) and
move on — founding is a follow-up docket.

`basin_trench_structures` is the ONE producer both
`build_tunnel_layout_shapes` and `basin_rim_flush_facilities` group from,
so extending here keeps emitter and rim-flush seating in lockstep by
construction. Frame conversion of the region ring goes through the same
path as `_tunnel_footprint_longitude_latitude_parts` — never a second
projection.

### 2.3 Floor key (ruling 1: solid witness + margins, open pits included)

`basin_facility_deck_reference_y`: the `open_pit=True` deck-face clause is
RETIRED-KEPT-GATED behind `O4_BASIN_OPEN_PIT_DECK_KEY` (default off = new
law). Under the new law open pits take the same path as bores: the deeper
of body depth and the (thickness-gated) solid witness, §2.2 disagreement
gate unchanged. In `grade_law.basin_trench_floor_elevation_m`, the
`bore_class=False` zero-margin arm likewise retires behind the same gate:
margins (`TUNNEL_FLOOR_BELOW_OBJECT_DECK_M` 0.5 +
`TUNNEL_BASIN_FLOOR_SEAT_MARGIN_M` 1.0) apply to every basin. Update the
two docstrings' law text (they currently teach Amendment 3).

**Floor prediction — CORRECTED post-implementation (Fable, 2026-08-26).**
The original text here predicted 584.44 = 593.03 + (−7.087) − 1.5, pairing
the OLD narrow ring's R_est with the new witness — a hybrid no lawful
build produces. R_est is by law the DEM median around the facility's OWN
outline; with the full ring it is 596.30, the thickness-gated witness is
−7.048 (the −7.087 figure predated the decal gate), and the lawful floor
is 596.30 − 7.048 − 1.5 = **587.75**, which clears the seated solid bottom
(588.95) by 1.20 m. The acceptance criterion is the invariant in §4, not
an absolute altitude. OTHH Drainage
floors lawfully deepen by the restored margins ("err deep" — see RULINGS
2026-08-26; update any test pinning Amendment-3 numbers by importing the
law function, never by hand-typing a constant).

### 2.4 Seniority (ruling 2) + gate

The Amendment-3 pad authority-yield must cover the FULL extended footprint
(it keys on the facility geometry, so extension should carry it — the
implementer verifies `authority_yield_pad_ids` fires for `building8` over
the full ring and that no OTHER clip (pavement, tile, coverage predicate)
shrinks the emitted trench below the region; the 12,434→10,065 m² gap in
the current build must be attributed and closed or explained in the
report). New config gate for the whole region feature:
`BASIN_REGION_FOOTPRINT` (env `O4_BASIN_REGION_FOOTPRINT`, default ON,
`=0` → byte-identical patch, same pattern as `BASIN_POOL_SCOPING`).

## 3. Tests (headless, synthetic; extend `tests/test_object_basin_trench.py`)

1. **Region recipe:** synthetic T4S pattern — one shared-anchor pool of
   at-grade boxes + two "wall" objects with solids to −7 spanning a known
   rectangle + one fully-buried box + one 0-thickness quad at −50. Assert:
   region ≈ the known rectangle (area tolerance), decal contributes
   nothing, region `solid_minimum_y_m` = −7.
2. **Triangle clip:** a ramp triangle from +1 to −6 contributes only its
   below-−2.5 portion (area assertion), never its full projection.
3. **Record extension:** a basin record overlapping the region gets the
   union footprint and the deeper solid min; a disjoint region extends
   nothing and is reported; `object_resources` unchanged.
4. **Floor law:** open-pit facility floor = R_est + solid_min − 1.5 under
   the new default; `O4_BASIN_OPEN_PIT_DECK_KEY=1` reproduces the
   Amendment-3 value (both asserted through the ONE law function).
5. **Gate:** `O4_BASIN_REGION_FOOTPRINT=0` → records byte-identical to
   pre-change (footprint object equality on the synthetic fixture).

Run once (pre-ship mode): `tests/test_object_basin_trench.py`,
`tests/test_object_tunnel_terrain.py`, `tests/test_object_bridge_terrain.py`,
`tests/test_round12_bridge_deck_datum.py`, `tests/test_kdfw_bridge_refusal.py`,
`tests/test_harness.py`.

## 4. Acceptance (ONE harness LEMD build, `tools/harness/build_airport.py LEMD`)

On the emitted `LEMD_auto.patch.osm`:
* union area of `ref=object_basin_trench` ways ≥ **26,200 m²** (95% of the
  authored 27,612; current 10,065),
* trench floor = the law's own value (R_est(full outline) + thickness-gated
  witness − 1.5) AND at least 1.0 m below the facility's seated solid
  bottom — measured 587.75 vs seated bottom 588.95: **PASS** (the
  original 584.44 ± 0.30 target was a spec arithmetic error, corrected in
  §2.3),
* trench bbox ⊇ lat 40.49110..40.49235, lon −3.57046..−3.56822 (authored
  floor ring bbox, ±10 m),
* the build log shows the pad authority yield naming `building8` and NO
  unmatched-region warning for T4S.

Materiality floor 0.01 m / 1% area; attempt cap 2 per target, then
STOP-and-report. Build-time impact statement: region derivation is
O(below-grade triangles) + one `unary_union` (~4.2k polygons at LEMD),
estimated ≤ 1–2 s on LEMD-class packs and ~0 on packs with no below-grade
geometry (per-resource pre-scan skips them); suspended timing law — ledger
tripwire only.

## 5. Out of scope (follow-up dockets, do not implement)

* Founding basin records from unmatched regions (no interface record).
* Membership/R4-exclusion widening; rigid group seating of shared-anchor
  families (relationship preservation) — separate design.
* Reading pack-shipped mesh patches as an input (validation-only artifact).
