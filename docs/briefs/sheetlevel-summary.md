# sheetlevel summary — the apron sheet's LEVEL under spec §62 R-E (Fable attribution, 2026-10-09)

Branch `claude/sheetlevel` (docs only; no engine code) off `origin/claude/seat2-re` f3596b84. Frame: seat2's late pairs
of `frames/pads67/HECA.pkl` / `KCLT.pkl` — `m` (merged tree 67e7f587 = main 1e524b12 + seat2 a–d, no R-E) and `e`
(R-E) — read with `--why-from` on their solved pickles, plus three arms on the R-E tree (registered: `frames.py list
HECA`, lane sheetlevel). Notes: `docs/briefs/sheetlevel-notes.md`; probes `<scratch>/sheetlevel/`.

## 1. The sheet's level field and why (HECA `apron:dsf:objpav402`, 613 vertices, 21 pad holes)

* `--why-vertex 11597` (sheet, 6 m from building100's rim) on BOTH arms: 11 hops to a taxiway junction 1.3 km away held
  by a `no_step` REACH BAND (m v10665 77.21; e v10670 75.29). Σdz +16.3 / +18.5 m, of which **`apron_preference`
  (the 1 % preferred tier) +13.7 / +14.0 m**, hard `no_step` route pairs +1.6 / +4.1, `junction_mesh` +0.7. Every hop runs
  at 1.19–1.34 %: above the 1 % preference (binding, dual 33), under the 1.5 % hard cap (slack, dual ≤ 3.3). The
  preference row is a one-sided row priced at `[design] law` = 300 (`design.py:524`), like the hard row.
* The LAW band at the rims (1.5 % on the pair graph from the runway anchors; `platforms[].reach_band` under R-E):
  building101 [86.1, 99.5], building100 [86.5, **100.2**], building117 [84.4, 101.1], building98 [83.1, 102.4]. The
  pads' object / DEM levels 101.25 / 101.74 / 103.50 are 1.0 / 0.7 / 1.1 m ABOVE their own rims' lawful ceiling; ~102
  is inside only at building98. The §8.7 trend target (`apron_trend_z`) at those rims is 100.0–100.3 — the band's top.
* So 93.8 is a PREFERENCE outcome, not a law outcome: the 1 % tier over a 1.2 km chain (185,033 preference rows) out-
  prices the §8.7 trend (`apron_trend` 30 / vertex; stage-1 term 1.6 M → 2.1 M). A sheet at the pads' level would
  violate the hard 1.5 % `no_step` / `junction_mesh` / apron ring-edge rows along the chain by 0.7–1.1 m; a sheet at
  99.5–100.2 violates nothing. The sheet sits 6.4 m under what law allows and the trend asks.

## 2. Which side is wrong

Under 09i / 08c (4): the pads are wrong where they stand above the band (101.25 is not reachable at 1.5 % from the
taxiway; 100.2 is), and the apron at 93.8 is LAWFUL but is the preference's level, not law's. The existing rule that
says where the sheet sits is §8.7's apron trend (RULINGS 2026-09-10ar; 359 rows on this face, weight 30), out-priced
10:1 per row. Arm W (`--design-weight apron_trend=300`): the pads rise to 96.98 / 97.66 / 98.25 (still 3 m under the
trend), AIR-TOUCH 1 / 4 m — and the runway moves 430 nodes, worst **+0.56 m**, pad hard conflicts 104 → 367, null-change
missed. The trend at the law's price fights the law airport-wide, as `emit.toml` warns. Not a change; the attribution.

## 3. The −9.48 / −6.88 m apron movers

Top 12: pad-rim vertices of building99 / 98 / 108 (103.4–103.5 → 93.9–94.4; DEM 102.8–106.6), the old value held by the
pad's hard `flat` / `pad_slope_max` rows and `frontage_hold` at its unreached DEM datum — the old KINK relaxing. The
sheet also sinks: non-pad apron vertices 60–200 m from any rim 810 movers (172 > 0.3 m, worst −6.88), > 200 m 1,723
(398 > 0.3, worst −2.58). Arm N (R-E's cross-ring pairs hard-only, no preference row) is identical to e within 0.16 m,
0 datums moved: the sinking is NOT the new rows — it is the high pads no longer lifting the sheet (their hold rows,
dual ~1,800 in m, now follow it) on the chain that was already there.

## 4. The runway and the null-change

Arm P (R-E + 2,610 `Pin` rows holding the runway at m's values): runway 0; the sheet's pads 93.75 / 94.39 / 95.09 (e
93.79 / 94.43 / 95.12) — the sheet does not depend on the runway (its chain ends at a reach BAND, a number). But holding
the runway 0.14 m differently re-levels 7,826 taxi vertices (worst 1.53 m) and gapapron sheets 2 km away by 1.8 m: the
§61 (0) class — one stage-1 QP exiting on objective gain, path-dependent. e's null-change: pass 1 worst −0.914 m at
building88's rim ON objpav402, pass 2's 164 movers objpav402's own junction cells; under P pass 2 / stage 2 go to 0 and
pass 1 keeps 0.51 m (building68's rim); N 0.56 (building65). What §61 missed: the apron HOLE RING in pass 1a (holds
dropped, no trend row for a `pad_follow` vertex) — the membrane already ties it to its neighbours (`membrane_rows`,
airside stage), but the one-sided 1 % rows at 300 switch with the active set and move the tied block between stops.
Not a law coupling; a solver-stability defect R-E's rows re-open on the pad rims.

## 5. KCLT

pav14's pads 221.03 → 222.44, runway 0. `--why-at` building75's contact: held in both arms by the pad's `frontage_hold
datum` = the median of its contacts' PASS-1A value (02ah (1)), one hop. Pass 1a under R-E put the rim 1.41 m higher
(sheet z−trend +0.35 → +1.76); the datum followed. Same mechanism as HECA, opposite sign: the apron's pass-1a level
seats the pad; the pad never pulls the apron.

## 6. Minimal change / owner question

No change to R-E or to what it stands on meets all four bars within current law: P / W / N each fail runway ≤ 0.1 or
null-change, and the two failing bars are pass 1a's path dependence (09d (3), unruled), not the seat. R-E itself
delivers the seat bars (AIR-TOUCH 0, pads follow). The sheet's level — 6–8 m under the DEM at the terminal row, 6.4 m
under the law band's top and the §8.7 trend — is a preference outcome the owner has ruled stands (09i: "the apron's
level is the airside solve's").

OWNER QUESTION (yes / no): where the 1.5 % law band admits it, should the apron sheet follow its §8.7 ground trend in
preference to the 1 % tier (today the 1 % tier is priced at the law's 300 and the trend at 30; at HECA that puts the
terminal row 8.5 m into a cutting the law does not require)? RECOMMENDATION: YES — but as its own spec (price the
preference below the trend, or cap the trend residual), with a seven-airport sweep, because W shows the balance is
airport-wide and moves the runway; NOT inside R-E. For R-E now: land it with the runway 0.14 m and the null-change miss
reported as §61 class, or hold it until 09d (3) is ruled — the master's call.

Unproven: a row-level fix of the pass-1a valley; R-E at OTHH / SPJC; the W arm at KCLT (not run).
