# pads56 notes — hand-back at the step 3 boundary (Opus implementer, 2026-10-07)

Branch `claude/pads56` (= `origin/claude/padspec2` + two commits). Spec: `tools/docq.py spec '§56'`.
Probe: `docs/briefs/padspec-scratch/pads56/classify_probe.py` (classify only, no solve; ~5 min OTHH,
~3 min HECA): `cd Ortho4XP && venv/bin/python ../docs/briefs/padspec-scratch/pads56/classify_probe.py
ICAO CAPTURE.pkl LAT LON R [cluster id …]`.

## DONE

- **Step 1 corpus proof** (captures `perfA362/OTHH.pkl`, `gaps3/HECA.pkl`): OTHH pads 56 → 52, HECA
  82 → 74, no MultiPolygon, outline vertices 6,133 → 2,424 over 66 outlines (OTHH), 4,943 → 2,921
  over 90 (HECA) — exactly padspec2's landed-rule numbers. `cluster_outlines(stats=)` now names every
  change; sidecar `cluster_pads[].outline_vertices / outline_simplified_from / outline_joined_from`.
- **Step 3** `classify/road_absorb.absorb_near_roads` (+ `structure_keep_out`), ONE call in
  `roles.classify` between `mint_osm_ribbons` and `mint_gap_pieces`; `_cut_back_groundside(only=)`
  re-applied for the changed pads; law key `[building_pad] pad_road_absorb_m = 10.0`
  (`PadOutline.road_absorb_m`); sidecar `cluster_pads[].roads_absorbed / roads_kept_near_pad`.
  Twins `tests/auto_patch_v2/test_padspec_roads.py` (9) + one in `test_padspec_outline.py`.
- OTHH replay `--from classify --emit` with steps 1 + 3 (collars still minted): solve optimal,
  stage 1 settled, 0 hard violated; patch in `<scratch>/pads56/othh_s3/`.

## STOP — for the spec author (padspec2) before step 7's site bar can be met

1. **The road bars miss in BOTH directions** (attempt 1 of 2; no second attempt exists inside the
   frozen rule). OTHH 26 absorbed (bar ≈ 75), site 7 of 17 road CELLS (bar 26 of 29 emitted FACES);
   HECA 37 into 17 pads (bar ≈ 18). Causes, measured:
   (a) the probe counted EMITTED road faces (after the structure / trench / plateau cuts) against the
       10 m band of the UNION of the cluster-unit outlines; the ruled site is the classify CELLS, per
       pad, over every `building` cell (fallback pads included — the cells list cannot tell them
       apart). A cell is larger than the faces it becomes, so fewer pass the 98 % test at OTHH; HECA
       gains the fallback pads' roads.
   (b) §56 (2) 4 (b) keeps **14 `route*` cells at the owner's terminal** (`building6`): `route19, 28,
       29, 30, 36, 38, 39, 40, 42, 43, 44, 45, 48, 52`, wall-extension overlap 0.0–77.8 m² each (0–51 %
       of the cell; table in `<scratch>/pads56/othh_probe.log`). The spec calls a (4) refusal at the
       owner's site a STOP. With them kept the site still carries 10 road cells (bar ≤ 3 faces).
2. **"A pad whose area grows > 5 %" (§56 (8) STOP list) fires on the landed step 1**: OTHH 13 same-id
   cluster pads (e.g. `unit:21#1` +23.7 %, `unit:28#8/1` +11.5 %, `unit:25#4` +10.3 %), HECA 15 (most
   are JOINS: `unit:43#80/2` +975 %); and on step 3 for small pads (HECA `building35` +9.8 %,
   `building192` +9.2 %, `building62` +7.4 %, `building205` +6.8 %, `building7` +5.4 %).
3. **`outline_vertices` at `unit:28#8/0` reads 552, not 650 ± 5 %** (HECA `unit:43#6330/0` 453 vs the
   probe's 472). The landed rule simplifies BEFORE rule 8 / rule 3 as §56 (1) orders; the first-draft
   probe simplified the rule-2 PIECE after them. The pad CELL at classify is 954 vertices (deck-shade
   and fallback-merge vertices come after 2b) and 643 once the absorption re-closes it.
4. **The absorption's re-close runs on the FINAL pad polygon**, i.e. after rule 8 (deck shades) and
   the fallback merge — it can re-fill a deck-shade notch under 6 m on an absorbing pad (OTHH
   `building6` 954 → 643 vertices, +3,260 m²; HECA T3 `building3` 1,020 → 491). Not measured which
   part of the added area is shade; the spec author should say whether the shades are re-subtracted.
5. HECA T3's pad `building3` DOES absorb 3 roads (`route24`, two ribbons) away from the 150 m site
   (0 of 2 at the site, as predicted); HECA gap pieces 375 → 341 airport-wide (25 pieces changed).
6. Exclusion (4) (a): at classify time only the OSM tunnel ways are readable (`deck_signature.
   is_tunnel_way`, buffered by the default carriageway half width + rim). The pack wall corridors,
   door ramps, sunken roads and bridge-seeded underpasses are derived in the planar stage from the
   pack objects and are NOT in the keep-out. 0 roads were kept for this reason at OTHH / HECA.

## NOT DONE (nothing started — step 4 is atomic and must not be left half-way)

Steps 4 (collar deletion), 5 (seat ladder S3/S4 + warning), 6 (object readers), 7 (HECA `--from
constraints --verify`, the closing OTHH harness build), KCLT road count, frames registration.

## Reading already done for step 4 — `planar/platform.py` (695 lines)

Keep: `draped_facade_pads`, `_welded_samples`, `rim_relief_m` (still feeds `Platform.rim_relief` and
`plan_blocks`' caller), the `plan_blocks` call + `BLOCK_PLANS`, `_mint_blocks` (blocks + strips),
the conforming-held loop (:481-499 — after the deletion EVERY welded pad ≥ `min_area_m2` goes through
one path: unit pads lose the erosion gate, so the `cluster_pad_min_m2` branch and the conforming
branch differ only by `plan_blocks`), `landing_regions`, `_merge_group` / `merge_platform_faces`.
Delete: `collar_width_m`, `_eroded`, `_collar_for_pad`, the `cparts` annulus (:409-412, :450-454),
the two `#collar` rename passes (:461-474: with no collar, a 23a rim sliver of a platform ref must
simply stay pad — check HECA T3 `building4`'s eleven slivers, the reason that pass exists), the
`eroded_away` / `under_min_area` refusals (:398-408), `platform_collar_why`, the `keys` collar half
in `merge_platform_faces` (:669). `_mint_blocks` takes `plats` (the eroded pieces) as `inner`: with
no erosion `inner` is the pad polygon itself and `col` (the block's collar) is only the cut STRIP —
the spec keeps the strip ("inter-block terrace strip … KEPT"), so decide its ref: today it is
`<unit>/b<k>#collar`; `constraints/platform.platform_collar_rows` keys on that spelling and is kept
for landings only — the strip needs its own rows or its own ref. That is the first thing to settle.
`Platform` (model/platform) fields `collar_m`, `collar_why`, `platform_m2` go with the sidecar keys.

## Environment notes

- The app was downloading orthophotos during this lane: the suite's session detector then reports
  `THE TEST SUITE WROTE INTO THE SHARED DATA REPO … Orthophotos/+30-120/…` as an ERROR at teardown of
  the last test. Not a test failure (memory `app-builds-cross-attribute-suite-detector`).
- `bash_guard` refuses any venv launch whose FIRST `cd` is not `Ortho4XP/` — edit with
  `cd Ortho4XP && venv/bin/python - <<EOF` rather than from `src/…`.
