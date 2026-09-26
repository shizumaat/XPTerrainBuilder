# Colour harmonization v2 — seam-continuous correction field

Status: DRAFT for owner ratification, 2026-09-21 (lane `harmonizerspec`,
Fable). Supersedes the v1 spec of 2026-07-16 (its §3.1–3.4 are the
"as shipped" algorithm of §1 below). GitHub issue #1 (GEN-2, beta 2
blocker). Instrument: `tools/texture_seam_census.py` (INDEX row; twin
`tests/test_texture_seam_census.py`). Config key: `color_harmonization`.

## 1. As shipped (v1) and what it does at +25+051

Code: `src/O4_Color_Harmonization.py` (pure), wired in
`O4_Imagery_Utils.collect_color_statistics_for_harmonization` (download
worker, JPEG opened with `Image.draft("RGB",(512,512))`),
`compute_color_harmonization_targets` (barrier after the last download,
`O4_Tile_Utils.build_tile`), `convert_texture` (apply).

- Statistic: per texture, the per-channel MEDIAN of a 512×512 BOX thumbnail
  of the WHOLE source JPEG, over pixels whose Rec.601 luminance is in
  (10, 248). Textures with < 20 % such pixels are excluded.
- Target: per (zoomlevel, provider) grid, the median of those medians over
  the 5×5 texture neighbourhood.
- Shift: `clip(strength(ZL) · (target − median), ±20)`, strength 0.7 at
  ZL ≤ 16, 0.4/0.2 at 17/18, 0.1 at ≥ 19 — ONE constant per texture, applied
  through a 256-entry LUT to every pixel, before the mask alpha and DDS.
- Provenance: none. The tile cfg does not record the key (the 1.0.352
  sparse-cfg rule writes only tile-differing keys — VERIFIED: the installed
  +25+051 cfg says `color_harmonization=False` while its build of
  2026-09-18 12:49 ran with the feature OFF, so the memory note's "cfg
  lies" is CURED, but the on-disk state is still inferred, not recorded:
  `Ortho4XP_+25+051_imagery.json` has no harmonization field).

Measured (`texture_seam_census.py --simulate-harmonizer`, 2026-09-21, the
shipped module replayed on the tile's cached source JPEGs, Arc+BI, ZL16+18;
the DDS the owner saw were the BI16 build of 2026-09-18 13:05, since
overwritten by an OFF Arc build whose census is the control: max texture
shift 1.0 count = DXT noise, 0 of 302 land seams over 2 counts):

| | value |
|---|---|
| textures / shifted / at the ±20 cap | 369 / 328 / 50 (7 of them ZL18, strength 0.2) |
| land seams / over the 2-count bar / max / median introduced step | 614 / 314 / 28 / 3 counts |
| textures whose whole-texture median differs from their LAND median by > 10 counts | 66 |
| all-water textures (invisible) that still receive a shift and feed the target field | 6 |

The coast chain 27968_42112 → 42128 → 42144 → 42160 (Arc16, east):

| texture | land | median all | median land | median sea | target | shift |
|---|---|---|---|---|---|---|
| 27968_42112 | 1.00 | 180,170,138 | 180,170,138 | – | 172,163,132 | −6,−5,−4 |
| 27968_42128 | 0.99 | 177,169,138 | 178,170,138 | 35,76,54 | 168,160,130 | −6,−6,−6 |
| 27968_42144 | 0.29 | 38,73,56 | 120,137,110 | 29,62,50 | 137,137,116 | +20,+20,+20 |
| 27968_42160 | 0.00 | 8,38,49 | – | 8,38,49 | 46,80,60 | +20,+20,+8 |

Step introduced across 42128|42144: (+26,+26,+26) counts; BI16 chain: +28.
The neighbouring seam 28000|28016_42144: −28. Two mechanisms, both content:
(1) the Gulf sea here is RGB ≈ (8,38,49), luminance ≈ 31, ABOVE the 10-count
"water-black" gate, so sea pixels are "valid" and the whole-texture median
of a coastal texture is the sea; (2) the 5×5 neighbourhood median mixes sea
and land medians, so land-heavy textures are pulled DOWN (−6) and sea-heavy
ones UP (+20, capped) — opposite signs, one constant each, a hard line at
every coastal edge. Source seams themselves step 1.5 counts (p50) / 5.9
(p90) / 53 (max, 15 seams > 10) on land — that is the real acquisition
patchwork; v1 adds 3 (p50) / 28 (max) on top of it.

## 2. Design v2 — measure at the seams, correct with a continuous field

Principle: adjacent strips on either side of a seam photograph the SAME
ground (≈ 140 m at ZL16), so their difference is acquisition, not content.
The correction is a field over ground position, continuous by
construction, so it can never add a step; the seam step after correction
is bounded by the seam step of the source.

### 2.1 Land, from the builder's own knowledge

Water is excluded by the mask the builder already computes, not by a
luminance gate. Source: `O4_Mask_Utils.needs_mask(tile, x, y, zl)` (the
`Masks/<tile>/<y>_<x>.png` square at `mask_zl`, cropped): returns False for
"no square" (all land) AND for "crop max ≤ 30" (all water); else the crop
(255 land, 0 water, feathered in between over `masks_width` m). v2 splits
the two False cases (a tri-state `land_class ∈ {land, water, mask}`) at
that single derivation point; the census tool mirrors it. A pixel is LAND
for statistics when the mask ≥ 250 (opaque land: the feather band is
shore, wet sand or shallow water — 27968_42144's "land" median 120,137,110
vs its inland neighbour's 178,170,138 is that band). The luminance gate is
kept only for nodata white / cloud cores (upper bound 248) and true black
(lower bound 10). A texture is a WITNESS when ≥ 25 % of its 512² thumbnail
is land; all-water textures are never witnesses and are never shifted.

### 2.2 Seam-strip casts

For every edge-adjacent pair (A,B) of witnesses in one (ZL, provider) grid
(east and south), on the 512 thumbnails: strip width 8 thumb-px (64 px,
≈ 140 m at ZL16), rows where BOTH facing strips are land; require ≥ 10 % of
rows (52). Cast `d_AB = median_rows(mean_B_strip − mean_A_strip)` per
channel, weight `w_AB = land_rows / 512`. Seams with fewer land rows carry
no data. Statistics are collected on the download worker as today (the
draft-512 decode is 0.05 s/texture) — the thumbnail's four edge strips
and land strips replace the whole-texture median in
`tile.color_harmonization_statistics`.

### 2.3 Offset field

Unknowns: one RGB offset `o_i` per texture of the grid (witness or not).
Minimise `Σ_seams w_AB (o_B − o_A + s·d_AB)² + μ Σ_adjacent (o_B − o_A)²
+ λ Σ_i o_i²` with `s = strength(ZL)` (schedule kept, §5 Q1), `μ = 0.05`
(smoothness across non-witness pairs: water and excluded textures inherit
their neighbours' value harmonically), `λ = 0.01` (gauge; the field's
mean over witnesses is then ≈ 0 — no whole-tile hue drift). A sparse
symmetric positive-definite system of ≤ 3·N unknowns (N ≤ ~400 per grid),
`scipy.sparse.linalg.spsolve`, deterministic, < 50 ms. Then
`o_i ← clip(o_i, ±20)` and `o_i ← o_i − mean_witness(o)`. Disconnected
components (grids split by all-water rows) solve independently; a
component with no seam data gets `o = 0`.

### 2.4 Application — bilinear over texture centres

`o_i` is the correction AT THE CENTRE of texture i. The applied field at
pixel `(u,v) ∈ [0,1]²` of texture i is the bilinear interpolation of the
four centre values surrounding that pixel: `o` of i and of the horizontal,
vertical and diagonal neighbour on the pixel's side; a missing neighbour
(tile border, texture absent) clamps to i's own value (Neumann). Two
textures evaluate the SAME interpolant on their shared edge, so the
introduced step is the rounding difference only (< 1 count). The field is
evaluated at 256² (float32), upsampled with `Image.BILINEAR` to the
texture size (0.05 s), added with saturating uint8 arithmetic (≈ 0.1 s),
before the mask alpha and DDS, as today. Pure functions in
`O4_Color_Harmonization`: `seam_strip_statistics(thumb, land)`,
`seam_cast(stats_a, side_a, stats_b, side_b)`, `solve_offset_field(seams,
keys, strength, mu, lambda)`, `bilinear_field(corner_values, size)`,
`apply_color_field(image, field)`. `apply_color_shift` and
`compute_target_field` are DELETED (refuted mechanism, BUILD ECONOMY).

### 2.5 Nested zoom levels (ZL18 islands in ZL16)

Each (ZL, provider) grid is solved on its own seams. The ZL18 zone edge is
a cross-grid seam: the ZL18 texture's outer strip vs the co-located
sub-strip of the covering ZL16 texture (a 4× finer crop of its thumbnail).
Those casts enter the ZL18 system as data terms against the ZL16 field's
value at that point (solve ZL16 first, then ZL18 conditioned on it). §5 Q2.

## 3. Partial tiles, missing neighbours, tile borders

The field is a function of THIS TILE's source imagery and masks ONLY
(cached JPEGs + `Masks/`), never of the built DDS and never of another
tile. Reasons: the DDS is the output being corrected (a feedback loop
would drift on every rebuild); another tile's imagery may not exist yet,
and a neighbour built later must not change this tile's textures. At the
1° border the field clamps (Neumann): the correction adds no step there;
the source's own cross-tile step stays, as in v1 (§5 Q4). Missing
textures (failed downloads) are absent nodes — their neighbours' seams
carry no data and the field passes through harmonically. The solved
field is PERSISTED as `<build_dir>/color_field.json` (keys, `o_i`, the
seam table, the settings hash and the statistics' JPEG mtimes) and
recorded in `<tile>_imagery.json` (`color_harmonization: true|false`,
`color_field: "color_field.json"`); a rerun that converts a SUBSET of
textures (`skip_downloads`, a repaired download) REUSES the persisted
field so the subset matches what was built before — the field only
recomputes when the full statistics pass runs. That closes the "cfg does
not say what ran" gap: the manifest does.

## 4. Acceptance (closing test = rebuild +25+051 textures, same instrument)

Before (v1 simulated, this document): 314 / 614 land seams over 2 counts,
max 28, 50 textures at the cap. Bars on the rebuilt +25+051 (Arc, ZL16+18),
`texture_seam_census.py <build_dir> --bar 2 --fail-over-bar`:

1. `seams_over_bar == 0` (introduced step ≤ 2 counts on EVERY land seam,
   coast seams included; `max_introduced_step ≤ 2`). A seam is JUDGED only
   when ≥ 64 of its 4096 facing rows are land (2026-09-25: the one over-bar
   seam, 27856_42128|27872_42128, is a 2-row coast sliver over the bar in the
   OFF control too — DXT noise, not a cast).
2. `max_texture_shift ≤ 20` and the mean land shift over witnesses within
   ±1 count (no whole-tile hue drift).
3. RESTATED 2026-09-25 (spec author, after the closing arms: the field is
   interpolated between texture centres, so both textures carry the same
   value at a shared edge and the field CANNOT change a seam step — the
   0.6× shrink asked the harmonizer to repair the SOURCE's own patchwork,
   which is not its job and was exactly what v1's discontinuous field did):
   no seam's DDS step exceeds its source step by more than 2 counts, and the
   same-ZL introduced step p90 stays within DXT noise (≤ 0.5 count).
   Measured 2026-09-25: p90 DDS/source 1.00×, same-ZL introduced p90 0.09.
4. All-water textures: shift 0 (`land_fraction == 0` rows).
5. `color_field.json` present, manifest records `color_harmonization`.
Materiality floor 0.5 count; attempt cap 2 (CLAUDE.md convergence guards).
The owner's sim read of the coast north of OTHH is the acceptance.

## 5. Open owner-intent questions (each with the recommended default)

1. Keep the ZL strength schedule (0.7/0.4/0.2/0.1) on the seam casts?
   Default YES — a full-strength correction at ZL18 removes real content
   differences between small textures; the schedule is the only knob.
2. Cross-ZL zone edges (§2.5) in this round or a follow-up? Default THIS
   ROUND — same strip machinery; the census gains `--cross-zl` beside it.
3. Whole-texture cast when a grid has NO usable seam (single-texture
   zone, all seams water)? Default NO correction (o = 0); never the v1
   median path.
4. Cross-tile 1° borders: default UNCHANGED (clamp). Future: read the
   neighbour tile's persisted `color_field.json` as boundary data.
5. Default ON stays? Default YES once bar 1–5 pass on +25+051; the beta-1
   workaround (untick) remains the rollback (`git revert` is the other).
6. Land threshold mask ≥ 250 vs ≥ 128: default 250 (excludes the feather).
7. Combined/composited providers (no source JPEG): stay excluded, default.

## 6. Performance bound (per texture, measured on this machine)

Statistics 0.05 s (draft decode, unchanged, download worker). Solve < 0.05 s
per tile. Apply ≤ 0.15 s (256² field + BILINEAR upsample + uint8 add)
against 0.047 s for the v1 LUT: +0.1 s × 184 textures ≈ 18 s CPU across
16 convert workers ≈ 1.2 s wall — under the 3 s (1 % of 300 s) threshold;
a measured apply above 0.15 s/texture triggers the Fable optimisation
review. Memory: one float32 256²×3 field + the uint8 texture, no second
4096² float array. The download→convert barrier of v1 stays (the field
needs every witness).

## 7. Implementation brief (Opus lane; RULINGS.md binds; deviations stop and report)

Files: `src/O4_Color_Harmonization.py` (pure functions of §2.4; delete
`compute_target_field`, `compute_harmonization_shift`, `apply_color_shift`,
`STRENGTH_SCHEDULE_BY_ZOOMLEVEL` stays); `src/O4_Mask_Utils.py`
(`land_class_for_texture(tile, x, y, zl)` tri-state beside `needs_mask`,
ONE crop code path); `src/O4_Imagery_Utils.py`
(`collect_color_statistics_for_harmonization` → strips + land strips;
`compute_color_harmonization_targets` → `solve_color_field(tile)` writing
`color_field.json`; `convert_texture` → `apply_color_field`, skip all-water
textures); `src/O4_Tile_Utils.py` (`_write_imagery_manifest` fields of §3;
reuse of the persisted field on subset reruns). Run
`venv/bin/python ../tools/blast.py` on each before editing.
Twins: extend `tests/test_color_harmonization.py` (solver on a 3×3 synthetic
grid with one 40-count cast: seam residual ≤ 1, gauge, water node inherits
neighbours; bilinear field equal on the shared edge of two textures to
< 1 count; clip) and `tests/test_color_harmonization_wiring.py`
(tri-state land, manifest fields, subset rerun reuses the field);
`tests/test_texture_seam_census.py` gains the `--cross-zl` case if Q2 is
taken. Closing test: ONE tile, textures only — `tools/harness/build_airport.py
--tile 25 51 --build-dir <lane-local dir>` with a new `--steps "3 masks,4
tile"` selector (thin extension of `run_tile_steps`' existing `skip_steps`
contract, recorded in `frame.json`; never a private wrapper), JPEGs from the
shared `Orthophotos/` cache (no download, no shared-repo write), then
`tools/texture_seam_census.py <build_dir> --bar 2 --fail-over-bar --json`.
Build-time impact statement: §6. Report site numbers first (the 27968 chain
and 28000|28016_42144), then the summary, then the branch + sha.
