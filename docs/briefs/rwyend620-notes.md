# rwyend620 — the ground beyond a runway end (#620; RULINGS 2026-10-12q (1); master note on (c))

Branch `claude/rwyend620` from origin/main 04a4f5992. Worktree
`.claude/worktrees/rwyend620`. Scratch
`/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/466e18b3-e03c-471f-b042-c64d8df4e04d/scratchpad/rwyend620`.

## Step 0 — read (done)
Audit `docs/findings/runway-end-law-audit-20261012.md` verified against the code it cites:
`constraints/strips.py` end rows are two-sided 5 % from 0 m (`end_corridor_longitudinal` + `_end_foot_rows`),
the strip cap reads `rings[0]` only, `end_skirt.rate` / `faa.end_skirt.near_max_down_grade` have no reader,
`verify/runway.py:runway_end_skirt` reads `ref == "runway_end_skirt"` (v2 emits none; `check_grade.py:2946` the same).
`[icao.eat]/[faa.eat]` (`slope`, `setback_m`) + `constraints/eat.eat_ceiling_offset` exist and bind taxi pavement only.

## FAA text — CONFIRMED (primary, 2026-10-12)
`AC-150-5300-13B-Airport-Design-Chg1-w-errata.pdf` fetched from faa.gov (curl; WebFetch was 403), text via pdftotext
(scratch `faa_ac/ac13b.txt`). §3.16.5 "RSA Grades", Standards items 2–5 (page 3-62, dated 3/31/2022) and Figure 3-35
"RSA Grade Limitations Beyond 200 feet (61 m) from the Runway End" (page 3-63):
2. first 200 ft (61 m) beyond the runway ends: longitudinal grade between 0 and 3.0 percent, any slope DOWNWARD from the ends;
3. beyond 200 ft: max positive grade such that no part of the RSA penetrates any applicable approach surface or clearway plane;
4. max negative grade 5.0 percent; 5. grade changes ±2.0 percent per 100 ft (30.5 m).
The repo's transcription (`config.py:4915-4934`, `rulesets.toml [faa.end_skirt]`) is exact; `rate_provisional = false` stands.

## DESIGN DECISION (point 1) — pushed before code
THE LAW AS ONE PROFILE, keyed by distance `d` beyond the pavement end along the extended centreline, in `law/tables.py`
(`runway_end_profile(law, code, letter)` — one derivation for the zones, the generator, the verify reader and the census):
* FALL allowance F(d) = ∫ cap_down: first segment `(L1, c1)` then `(∞, end_skirt.max_down_grade)` where
  `(L1, c1) = (strip.end_length_m, strip.longitudinal)` when the ruleset states a strip end length (ICAO: 60 m code 2–4,
  30 m code 1 — Doc 9157 §5.3.2 / CS ADR-DSN.B.155(a): the non-instrument figure, the engine has no instrument witness),
  else `(end_skirt.near_zone_m, end_skirt.near_max_down_grade)` (FAA: 61 m, 3 %).
* RISE allowance R(d) = 0 for d ≤ hold (FAA near zone "any slope downward"; ICAO: none), else
  `max(0, d − eat.setback_m) · eat.slope` (the take-off climb / departure surface, NO tail height — the master's note).
  ICAO's `[icao.eat]` carries the code 3/4 figure only (2 % from 60 m); codes 1/2 are a TABLE GAP (reported, not invented) —
  immaterial inside any band: a code-1 band is 30 m, a code-2 band 40 m, both inside the 60 m setback.
* Rows (`constraints/strips.py`): ring pairs along the axis in the end rects:
  `−(R(d_out) − R(d_in)) − q ≤ z_in − z_out ≤ F(d_out) − F(d_in) + q`; the chord from the end edge (`_end_foot_rows`):
  `−F(d) − q ≤ z_v − z_foot ≤ R(d) + q`, `follows = v` (one-way: the runway leads, the ground follows — head added to
  `one_way_rulings`). FAA only (`rate_provisional == false`): the ±2 %/30.5 m rate as three-station rows over the end
  runs (the `strip_arc` form) and the end-edge change as the chord parabola `|z_v − z_f − g_end·d| ≤ ½·rate·d² + q`
  against the runway's own last chord (runway vertices lead). ICAO: no rate number invented (point 3).
* BREAKLINE at L1: the end band today is ONE plane from the end edge to the outer ring at the zone-2 half-width; a plane
  cannot be 1.75 % for 60 m and 5 % for 15 m. `planar/zones.py` splits each runway's zone-2 end band by the line
  perpendicular to the runway axis at `L1` beyond each pavement end (and before each start) — AFTER the shore / terrain-edge
  decisions, so every trim is untouched and the pieces inherit the part's verdict. Consumer census: every reader of zone 2
  selects faces by role `graded_strip` / per vertex (`constraints/zones.py` bands, `water.py`, `runway_chord.py`,
  `road_ramp.py`, `design_ground.py`, `verify/strips.py`); none assumes one zone-2 face per group; the sliver rule
  (`strip_min_m2` 50 / `strip_min_width_m` 3) does not fire on a 15 × 150 m piece; `strip_seam_tear` reads 0 across a
  shared noded ring. The outer ring keeps its DEM datum (weight 3) and yields to the law (300): fill at the band's end,
  the bank beyond it (2026-10-09d (1)).
* Tier (point 2): priced law rows (300) as today, never hard; the chords one-way. Runway movers must read 0.
* Transverse untouched (point 4). Band length untouched (not ruled).
* Census (d): family `runway_end_skirt` is RE-POINTED at the ground v2 emits (`graded_strip` rings in the end rects) in
  `verify/strips.py` (verify/census registers it; `families.toml` roles → graded_strip); `check_grade.py` keeps the
  family name and calls the same reader (one code path).

## Captures
* CYCG: `/Users/noah/XPTerrainBuilderData/.harness/frames/rwyend620/CYCG.pkl` (base 04a4f5992, 15 s, 1,010 V / 60 F).
* SPJC / NLWF / HECA / KASE: lane pads67 captures (base 4b433195); KPDX: kpdx559 (4869d1e94); KBFI: none registered.

## Built (sha below) — what landed
* `law/model.py` `StripLaw.end_length_m`; `rulesets.toml` `[icao.strip] end_length_m` 30/60/60/60 by code; FAA `[faa.end_skirt]`
  comment now cites §3.16.5 items 2-5 + Fig 3-35 (confirmed); ICAO `end_skirt.rate` stays provisional and unread.
* `law/tables.py` `EndProfile` + `runway_end_profile(law, code, letter)` — the one derivation (fall_m / rise_m / rate / break_m).
* `geom/rotated_rect.long_axis` (shared by `planar/strip_keepout` and the new `planar/zones.runway_end_breaks`): the zone-2 end
  band is cut at `break_m` beyond each pavement end after every trim / shore decision (`_break_pieces`).
* `constraints/strips.py`: `end_corridor_longitudinal` = ring pairs + TRANSECT pairs (`end_transect_pairs`: nearest vertex inward on
  the same line — the break vertex and the outer ring are not ring-consecutive) + the end-edge chords (`_end_foot_rows`, one-way
  `follows=v`, head `rulesets.end_skirt runway-end profile` in `one_way_rulings`); `end_corridor_rate` (FAA only): three-station
  rate over the corridor runs + the end-edge parabola `|z_v − z_f − g_end·d| ≤ ½·rate·d² + q` against the runway's own last chord
  (one-way). `solve/project.py` `CORRIDOR_RULINGS`: the chords join the post-solve zone projection (a 3 m fill at CYCG's band corner
  shipped a 3 cm residual the census read as a row; clamped now).
* Census (d): `verify/strips.runway_end_skirt` (pairs, transects, chords, FAA rate; `end_excess_m` / `end_chord_foot`), registered in
  `verify/census.READERS`; `verify/runway.runway_end_skirt` (the vacuous ring reader) deleted; `families.toml` roles → graded_strip;
  `tools/check_grade._check_runway_end_skirt_edges` rewritten on the same helpers + `_runway_end_profile_law`.
* `tools/runway_end_ground.py --profile` (INDEX row): the end-profile reader used for every number below.
* Twins: `tests/auto_patch_v2/test_runway_end_profile.py` (a)(b)(c)(d) + breakline; `test_v2rwycorner.py` updated to the profile;
  `test_harness.py` rate-span count 3 → 4.

## Measured (replays from planar, base = main 04a4f5992 tree, arm = this branch; runway/airside movers 0 everywhere)
| end | before: first-60 m grade / dz at break / dz at band end | after | fill(+)/cut(−) at break, at band end | census rows base → arm |
|---|---|---|---|---|
| CYCG 15 (icao 3E) | −2.75 % / −1.65 / −2.06 @74.9 | −1.99 % then −4.87 % / −1.20 / −1.93 | +0.45, +0.13 (centreline vertex sits 0.24 above DEM; band CORNER at t=−48.7 lifted 1.96 m → 2.93 m bank) | 5 → 0 |
| CYCG 33 | −2.24 / −1.34 / −1.69 @75.4 | −1.73 then −1.97 / −1.04 / −1.34 | +0.30, +0.35 (outer ring now ON the DEM: base was 0.34 m under it) | (same patch) |
| SPJC 16R (icao 4D) | −3.55 / −2.13 / −2.67 @75.3 | −1.73 then −4.90 / −1.04 / −1.78 | +1.09, +0.89 | 11 → 0 (whole patch) |
| SPJC 34L | −3.69 / −2.22 / −2.78 | −1.73 then −4.97 / −1.04 / −1.79 | +1.18, +0.99 | |
| SPJC 16L / 34R | −1.74 / −1.39 (lawful) | −1.73 / −1.73 then 0.0 | ≤ 0.03 | |
| NLWF 25 (icao 2C, band 39.6 m) | +4.44 % rising / +1.76 at band end | +0.30 % / +0.12 | −1.64 cut at the band's end (ceiling = level with the end + q inside the 60 m setback) | 4 → 3 (a 2.8 % pair off-axis, 0.15 m) |
| NLWF 07 | +0.42 / +0.17 | +0.22 / +0.09 | −0.08 | |
| KASE 15 (faa 4D) | −2.34 / −1.43 / −1.79 @76.6 | −1.01 then **−9.23 %** / −0.62 / −2.05 | UNRESOLVED — see open | 9 → 15 |
| KASE 33 | −0.16 / −0.10 / −0.12 | −0.34 then +0.61 / −0.21 / −0.12 | ~0 | |
| KPDX 3 (faa 4D) | −1.61 / −0.98 / −1.23 | −1.69 then −1.22 / −1.03 / −1.22 | ~0 | 6 → 2 (whole patch) |
| KPDX 10L/10R/28L/28R/21 | ≤ 0.66 % | ≤ 0.66 %; 28R a +3.4 % kink 60.8→65.8 (the FAA ceiling jumps from 0 to 0.025·d past 61 m) | ≤ 0.12 | |
| HECA (icao 4F; arm1 = before transects) | 05L −1.07 → −1.41 then +0.21; 23R −2.02 → −1.90 then −2.42; others chained taxi/road ground | | | 38 → 44 |
Movers (strip only, airside 0): CYCG 11 (1.96), SPJC 23 (1.74), NLWF 11 (1.64), KASE 11 (0.26), KPDX 39 (0.34), HECA 511 (0.46; arm1).
Closing harness builds (this tree): CYCG 19.2 s body aaa947ae4a79, census runway_end_skirt 0, LAW-TRUE 57; SPJC 81.1 s body c24798c27bf5,
runway_end_skirt 0, LAW-TRUE 3439 (vs the base REPLAY patch 293 strip / 177 airside ≤ 0.08 m movers — a capture-vs-fresh-build difference,
not this change: the matched replay pair reads 0 airside movers).

## OPEN
* KASE 15: the far piece's centreline pair (61.1 → 76.6 m) reads −9.23 % (verify: a −17 % transect pair 15 m, 1.69 m) with the pair
  row priced at 300 and nothing named by `--why-at` ("the objective holds it"); dropping `end_corridor_longitudinal`, `end_corridor_rate`,
  `resa_transverse`, `zone_bands`, `strip_transverse`, bend_strip=0 and zone_projection=0 ALL leave it unchanged — the profile there is
  not set by any strip row. Base already read 9 rows at KASE under the new reader. Needs an attribution lane (candidates: a pad plateau /
  platform collar or a road terrace reaching the end band; a hard row on the outer vertex).
* ICAO `[icao.eat]` carries the code 3/4 climb surface only (2 %/60 m); codes 1/2 (Annex 14 Table 4-1: 5 %/30 m, 4 %/60 m) are a table
  gap — immaterial inside any band (code-1 band 30 m, code-2 band 40 m ≤ the setback).
* The generator's slack q (strip_edge_noise 0.15 − 0.01) is consumed by the solve: the achieved first-segment grade reads 1.99 % at
  CYCG 15 against the 1.75 % cap (+0.14 m over 60 m); the census allows the same q.
