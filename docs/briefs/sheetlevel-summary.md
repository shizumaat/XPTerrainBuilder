# sheetlevel summary — the apron sheet's LEVEL under spec §62 R-E (Fable attribution, 2026-10-09)

Branch `claude/sheetlevel` (docs only) off `origin/claude/seat2-re` f3596b84. Frame: seat2's late pairs of
`frames/pads67/HECA.pkl` / `KCLT.pkl` — `m` (merged tree, no R-E = main's surface + seat2 a–d) and `e` (R-E) — read with
`--why-from` on their solved pickles, plus two new arms on the R-E tree (chain 3). Notes: `docs/briefs/sheetlevel-notes.md`;
probes `<scratch>/sheetlevel/` (`why/`, `movers.py`, `movers_hist.py`, `trend_at.py`, `pin_rw.py`, `read_arm.sh`).

## 1. The sheet's level field and why (HECA `apron:dsf:objpav402`, 613 vertices, 21 pad holes)

* `--why-vertex 11597` (sheet, 6 m from building100's rim) on BOTH arms: 11 hops to a taxiway junction 1.3 km away held
  by a `no_step` REACH BAND (m v10665 77.21; e v10670 75.29). Σdz +16.3 / +18.5 m, of which **`apron_preference`
  (the 1 % preferred tier) +13.7 / +14.0 m**, hard `no_step` route pairs +1.6 / +4.1, `junction_mesh` +0.7. Every hop runs
  at 1.19–1.34 %: above the 1 % preference (binding, dual 33), under the 1.5 % hard cap (slack, dual ≤ 3.3).
* The LAW band at the rims (1.5 % on the pair graph from the runway anchors): building101 [86.1, 99.5], building100
  [86.5, **100.2**], building117 [84.4, 101.1], building98 [83.1, 102.4]. The pads' object / DEM levels 101.25 / 101.74 /
  103.50 are 1.0 / 0.7 / 1.1 m ABOVE their own rims' lawful ceiling; ~102 is inside only at building98. The §8.7
  trend target (`apron_trend_z`) at those rims is 100.0–100.3 — at the band's top.
* So 93.8 is a PREFERENCE outcome: the 1 % tier priced at `law` 300 per pair (185,033 preference rows) over a 1.2 km
  chain out-prices the §8.7 trend at 30 per vertex (stage-1 `apron_trend` term 1.6 M → 2.1 M). The rows a sheet at the
  pads' level (101.25) would violate: the hard 1.5 % `no_step` / `junction_mesh` / apron ring-edge rows along that chain,
  by 0.7–1.1 m. A sheet at 99.5–100.2 violates nothing.

## 2. Which side is wrong

Under 09i / 08c (4) the pads are wrong where they stand above the band (they cannot be reached at 1.5 % from the
taxiway), and the apron is lawful at 93.8 — but 93.8 is not law's level, it is the 1 % preference's. The existing rule
that says where the sheet SITS is §8.7's apron trend (RULINGS 2026-09-10ar, `[design] apron_trend` = 30, 359 rows on
this face), and it is out-priced 10:1 by the preference. Probe W (`--design-weight apron_trend=300`): see 6.

## 3. The −9.48 / −6.88 m apron movers

Top 12: pad-rim vertices of building99 / 98 / 108 (103.4–103.5 → 93.9–94.4, DEM 102.8–106.6), the old value held by the
pad's hard `flat` / `pad_slope_max` rows and its `frontage_hold` at an unreached DEM datum — the old KINK relaxing. But
the sheet also sinks: non-pad apron vertices 60–200 m from any rim 810 movers (172 > 0.3 m, worst −6.88), > 200 m 1,723
(398 > 0.3, worst −2.58): the high pads no longer lift the sheet locally, and R-E adds 5,695 preference-carrying chords.

## 4. The runway and the null-change

Final-surface why on the worst runway mover: held at its own pass-1a value (`runway_flex` beta_R 0); the 0.14 m is pass
1a's. e's null-change: pass 1 worst −0.914 m at building88's rim ON objpav402; pass 2's 164 movers are objpav402's own
junction cells beside building104. In pass 1a a pad-rim vertex has no value row (holds dropped, no trend row for a
`pad_follow` vertex, §61 names taxi faces only) and under R-E its ring is tied to the sheet by one-sided rows only: the
§61 valley re-opened on the apron's HOLE RINGS. Arm P (runway pinned at the base): see 6.

## 5. KCLT

pav14's pads UP 221.03 → 222.44 (band [220.4, 227.2], `datum_chosen` 220.88; sheet rims z−trend +0.35 → +1.76); runway 0.
Why-read: chain 4 (pending at the time of writing; see notes).

## 6. The arms (chain 3) and the recommendation

(filled from arms P and W below)
