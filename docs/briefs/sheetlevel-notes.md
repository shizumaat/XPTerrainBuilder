# sheetlevel notes — attribution of the apron sheet's LEVEL under spec §62 R-E (Fable, attribution only)

Lane `sheetlevel`. Worktree `.claude/worktrees/sheetlevel`, branch `claude/sheetlevel` off `origin/claude/seat2-re`
f3596b84 (= main 1e524b12 incl. §61 + R-D rule 1 + R-E). Scratch `<scratch>/sheetlevel/` (`.progress`, `why/`).
NO engine code lands here; every probe is a read of a solved pickle or a scratch arm.

## Frame (reused, not re-solved)

seat2's late pairs on `frames/pads67/HECA.pkl` (`<scratch>/seat2/pair.sh`: `--from classify --gap-free --workers 9
--solved-out base_gf.pkl`, then `--late-from base_gf.pkl --emit`):

* `m/` = merged tree 67e7f587 (main 1e524b12 + seat2 steps a–d, NO R-E) — "main's surface today" for this question
  (67e7f587 contains both bcbfcede §61 and 1e524b12).
* `e/` = f3596b84 = m + R-E (`apron.py` +26 lines: cross-ring pairs under the ring-edge head inside the body gate).
* `nm/` = m re-run with `--null-change`; KCLT: `km/`, `ke/`.

## Step 0 — what the two solves already say (read off the sidecars, no new solve)

Owner-site pads (`platforms[]`, `axes.json`), HECA, m → e:

| pad | datum m → e | reach_band m | reach_band e | datum_chosen e (band median) | datum − chosen |
|---|---|---|---|---|---|
| building100 | 101.25 → 93.79 | [None, None] (12 of 12 contacts UNREACHED) | **[86.48, 100.21]** (lo anchor 05C/23C 27 hops) | 98.26 | −4.46 |
| building98 | 103.50 → 94.43 | [None, None] | **[83.12, 102.39]** | 100.79 | −6.36 |
| building117 | 101.74 → 95.12 | [None, None] | **[84.42, 101.09]** | 99.53 | −4.40 |
| building101 | 93.39 → 93.62 | [85.73, 99.37] | [86.06, 99.45] | 97.88 | −4.25 |
| building104 | 92.42 → 92.61 | [89.56, 97.42] | [89.70, 97.64] | 95.18 | −2.56 |

READING. R-E does what it says: the hole rings join the pair graph (unreached 12 → 0) and each pad gets a lawful reach
band from the runway anchors. The bands' TOPS are 100.2–102.4 m — the pads' object/DEM levels (101.25 / 103.50 /
101.74) are inside or within 1.1 m of the band. The solve then seats the sheet at 93.6–95.1, 4.3–6.4 m UNDER the band's
own median (`datum_chosen`), i.e. deep inside the band, NOT at a law edge. So on the sidecar alone: the apron's level at
the pads is a PREFERENCE / trend outcome, not a law outcome — the law would admit a sheet 5–8 m higher. Which rows hold it
there is the `--why` read below (step 1).

NULL-CHANGE: m `pass1a 7/0/0.136 pass1b 9/0/0.148 stage2 9/0/0.148`; e `pass1 13/1/0.914 pass2 164/0/0.107 pass3
13/0/0.159 stage2 15/0/0.159 BAR MISSED` — and e's pass 1a records `weld_rewidened: 15`, `weld_seal contacts 22` (m: 7),
`qp_exits optimal x3` (m: `no_descent 1, optimal 2`): the arm has a third stage-1 pass (the re-widened weld) the base
does not take.

Stage-1 hard set: m 30 rows over 0.02 m (worst 0.0999, apron ring edge v11207–v11208); e 74 rows (worst 0.1345, the
SAME ring edge) — the apron tier is less settled under R-E, same site.

## Step 1 — WHY the sheet stands at 93.6–93.8 (`--why-from` on the two solved pickles; `<scratch>/sheetlevel/why/`)

`--why-at` building100's contact v11868 (e: z 93.79, DEM 102.52) and `--why-vertex 11597` (the sheet 6 m off, m: 93.56
/ e: 93.79, DEM 102.39). Both arms give the SAME chain, 11 hops, to a junction vertex 1.3 km away held by a REACH BAND
(`no_step` "threshold values along taxi routes at the path caps", 04o): m v10665 z 77.21 (Σdz +16.34 m), e v10670 z
75.29 (Σdz +18.50 m). By family along the chain: **`apron_preference` +13.7 / +14.0 m** (the 1 % preferred tier, soft,
over ~1,250 m of apron body / frontage chords), `no_step_pairs` +1.6 / +4.1 (hard 1.5 %), `junction_mesh` +0.7,
`pad_frontage_level` +0.3. The steps along the chain run at 1.19–1.34 % — ABOVE the 1 % preference and UNDER the 1.5 %
cap — so the preference row is the binding one (dual 33) and the hard `apron_within_shape` 1.5 % row is slack (dual
0.01–3.3) on every hop. Binding on v11597 in m: `pad_frontage_level` dual 1,797 (building101's seat holding its contacts),
`pads` near-miss 121, `apron_preference` 33.

The §8.7 trend target (`PlanarMap.apron_trend_z`, priced at `[design] apron_trend` = 30 / vertex): v11868 **100.26**,
v11597 **100.10**, v11603 100.00, v11639 99.10 — the long-wave ground trend is ~2.2 m under the DEM there and AT the law
band's top (building100 `reach_band` hi 100.21). Face 372 (objpav402, 613 vertices, 21 holes, 359 trend rows): z−trend
mean on the pad rims −2.36 (m) → **−6.74** (e), on the other vertices −1.76 → −5.05, on its own junction cells −4.39 →
−4.19; z−DEM rims −3.03 → −7.41. Stage-1 objective: `apron_trend` term 1.60 M (m) → 2.08 M (e) at weight 30 — the sheet
pays ~53,000 → 69,000 m² of trend residual rather than ~1 % relief on the preference rows (priced at `law` 300 per pair).

READING (Q1). The apron's level around the pads is a PREFERENCE outcome: the 1 % preferred tier on the body chords from
the taxiway junction's reach band, out-pricing the §8.7 trend (30 vs 300 per row, and the chain is 1.2 km long). The LAW
band at the rims — 1.5 % along the pair graph from the runway anchors — is building101 [86.1, 99.5], building100 [86.5,
**100.2**], building117 [84.4, 101.1], building98 [83.1, 102.4]: the DEM / object level 101.25 / 101.74 / 103.50 is 1.0
/ 0.7 / 1.1 m ABOVE the lawful ceiling at building100 / 117 / 98's own rims (101.25 > 100.21; 101.74 > 101.09; 103.50 >
102.39), and ~102 is inside only at building98. A sheet at the pads' level would violate the hard 1.5 % `no_step` route
pairs / `junction_mesh` / apron ring-edge rows along the chain to the junction band by 0.7–1.1 m — but a sheet at
~99.5–100.2 (the trend's own value) violates nothing.

## Step 2 — the −9.48 / −6.88 m apron movers (Q3; `movers.py`, `movers_hist.py` on the m → e emit join)

Top 12 apron movers are ALL rim vertices shared with building99 / building98 / building108 (pad-rim distance 0.0–4.5 m):
e.g. v11852 103.40 → 93.92 (DEM 102.82), v11860 103.47 → 94.00 (DEM 103.11), v11851 / 11850 / 11845 / 11844 / 11843 /
11842 103.50 → 94.43 (DEM 104.6–106.6). The rows holding the OLD value: `structures.building_pad flat` (cap 0, hard) and
`pad_slope_max ceiling` ×8–15, `frontage_level` / `frontage_hold` (the pad's own hold at its unreached DEM datum), plus the
apron ring edge / frontage chord 1.5 % and the 5 % ceiling climbing to meet it. So the top movers are the old KINK (the
sheet's rim pulled up to a pad seated alone at its DEM) relaxing to the sheet. BUT the sheet itself also sinks: non-pad
apron vertices by distance to the nearest pad rim, m → e (n / movers / >0.3 m / worst): <2 m 59 / 46 / 32 / −9.08;
2–10 m 237 / 194 / 103 / −9.08; 10–30 m 641 / 484 / 223 / −8.61; 30–60 m 694 / 350 / 113 / −7.53; **60–200 m 1,776 /
810 / 172 / −6.88; >200 m 5,326 / 1,723 / 398 / −2.58**. Two mechanisms, same sign: (i) the high pads no longer lift the
sheet locally (their hold rows, dual ~1,800, now follow the sheet instead of pulling it), (ii) R-E adds cross-ring body
chords inside the 60 m gate and each carries the 1 % preference row — more preference rows, the same trend weight — so
the 1 %-vs-trend balance tips further toward the ramp from the junction. KCLT the same read, opposite sign: pav14's pads
UP 221.03 → 222.44 with the sheet (+1.41 at the rim, worst +1.89 at 2–10 m; >200 m 445 movers worst −1.78).

## Step 3 — the null-change and the runway (Q4, first read; the pinned arm P is chain 3)

`--why-at` the worst runway mover (v3701, 05L/23R, 59.85, +0.14 m m → e): held by `runway_flex` Band hi = its OWN
pass-1a value (beta_R 0) and the strip's `zone_bands`; nothing on the final surface names the sheet — the 0.14 m is
pass 1a's, where the runway is a free column under its chord target (300) in one QP with the sheet.

The null-change record of e (`base_gf.json/null_change`): pass 1 worst **−0.914 m at building88's rim vertex
(30.12101,31.41755)** — a pad ON objpav402; pass 2's 164 movers (worst −0.107) are objpav402's own junction cells and
their graded strip at 30.1220–30.1225, 31.4152–31.4161 (beside building104). In the base (nm) the same vertex moves
−0.136 in pass 1a and the worst pass-1b movers are `gapapron:1` (0.149). So R-E's instability is ON THE SHEET, not at the
runway: in pass 1a the hold rows are dropped, a pad-rim vertex carries no value row (no trend row — `pad_follow` is
dropped from the trend at the row site; no datum; the §61 cross-section / membrane name taxi faces only), and under R-E
its ring is now tied into the sheet by one-sided cap rows and the 1 % preference only — a bending-only column, the §61
valley, re-opened on the apron's hole rings. §61 (1) named the taxiway edge; it did not name the apron hole ring whose
hold is dropped in pass 1a. The runway's 0.14 m 1.7 km away is the same QP's exit moving with that valley (the §61 (0)
signature: a satisfied constraint elsewhere moves the far field), not a law chain — arm P tests it.

KCLT (ke vs km; `trend_at.py pav14`): the pav14 sheet ROSE — face 195 (178 v, 6 holes) pad rims z−trend +0.35 → +1.76,
face 197 (453 v, 15 holes) rims −0.13 → +0.15; building75 / 83 221.03 → 222.44 with `datum_chosen` 220.88 and band
[220.42, 227.16] — the pads stand 1.56 m ABOVE their chosen datum, inside the band; runway 0. Why-read queued (chain 4).
