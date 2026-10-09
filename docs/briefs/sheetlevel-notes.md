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
