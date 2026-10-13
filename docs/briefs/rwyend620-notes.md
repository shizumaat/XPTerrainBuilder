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
