# surfspec — spec §60: a `.pol` admitted by its own SURFACE is a gap sheet (#337, #333; RULINGS 2026-10-09a)

Lane `surfspec` (Fable, design only), branch `claude/surfspec` off main `7cc787ee`.
Deliverable: `Ortho4XP/docs/specs/auto-patch-v2/design-surface-spec.md` §60 (new,
appended; §56–§59 are on unmerged branches). Probes `docs/briefs/surfspec/`
(`admit_probe.py`, `overlay_probe.py`, `aptclip_probe.py`, `structures_probe.py`;
outputs `docs/briefs/surfspec/out/`); notes `docs/briefs/surfspec-notes.md`.
No engine code edited; no capture taken; no build run.

## The intake rule (§60 (1))

ONE gate, `airport/dsf.pavement_verdict(path, decl) -> "source" | "sheet" | None`
(the branch's widened `is_pavement_def`, re-spelled; `is_pavement_def` =
`== "source"`): stock namespace and `MATERIAL_TOKENS` names are sources as today;
a decorative namespace or a terrain word refuses whatever the file says;
THE FILE (`pol_declaration`, ported from 3936fd94) — a `markings` layer refuses,
`SURFACE asphalt|concrete` admits as a **sheet** (a **source** only when the name
also carries the 04d (2) `conc` word, so SPJC `conc_3` and every id are unchanged);
a soft surface refuses; no file / no surface → the `conc` word alone (04d (2)).
ONE population site, `airport/load.py`: a `"sheet"` page is read from the dump,
takes NO `dsf:pol<i>` index (ids byte-identical), passes the 1,000 m admission,
and is appended to `Airport.gap_sheets` AFTER the object bodies
(`dsf:gapsheet<k>` numbering on from them). The mint (`gap_mint.py:89`) reads it
exactly as it reads HECA's `asphalt.obj` bodies. Log line + two report keys.
Of the branch's 9 tests, 5 port unchanged in meaning (tuple spelling), 3 change
to the `"sheet"` verdict, 1 to `None`; four new load/mint twins.

## The population (§60 (2); `admit_probe.py`, branch gate vs main's over the cached dumps; the REAL `mint_gap_pieces` control/arm on each capture's standing cells)

| ICAO | SURFACE-only polygons / m² | on runway / taxi / apron cells | on pads | on today's sheets | free | mint control → arm | net |
|---|---|---|---|---|---|---|---|
| OTHH | 281 / 5,303,656 (ASPH1/2/3, ASPH1_upper, Stone_Tiles1/2) | 712,279 / 1,880,707 / 822,710 | 654,023 | 0 | 1,417,955 | 0 → **122 pieces / 671,706 m²** (band envelope took 619,500; 318 under floor) | +122 |
| HECA | 2 / 63,173 (`Asphalt_1_NOLINE`) | 0 / 0 / 169 | 16,743 | **15,346** | 45,248 | 38 / 1,001,549 → 38 / 1,031,194 | `gap:0` +19,099, `gap:1` +10,547 (**+29,646 m², no new piece**) |
| SPJC, KCLT, CYXY, KASE, NLWF | 0 | — | — | — | 0 | 0 → 0 | **no-op, provable** (every refused hard-surface file is `markings` or soft-named) |

A sheet over standing airside pavement mints NOTHING there — the mint's own
construction, measured: OTHH 3,480,339 m² of admitted page on standing cells
(712,279 on runways) → 0 m² of piece on any; `unminted_airside` 0.

## OTHH scale and time (§60 (3))

122 pieces (median 1,467 m², max 154,272), 133 km of rim; 39 touch an apron.
§59 class ESTIMATE (readers approximated; reproduces HECA's table to within one
piece): 9 road by evidence (329,259 m²), 24 apron by share ≥ 20 % (56,774),
6 apron with no evidence (7,695) → ≈ 30 stage-1 apron parts / 64,469 m²; 92 late
road pieces / 607,237 m². OTHH is flat: pull expected in centimetres; runway 0 by
construction. Structures: 7 pieces (24,326 m²) overlie the `tunnel1` / `tunnel
south west 2` wall corridors and are cut by them LAST (`structure_approach.
cut_gap_cells`, confirmed); 0 on plateaus / basin ramps / terrace joints; §57 bays
do not meet a piece at OTHH. TIME: sw1041 OTHH 448 s + a late stage of ≈ 130–180 s
(HECA: 120–147 s for 38 pieces / 122 km rim) → **≈ 580–630 s vs the 600 s bar:
at or over.** One replay on a merged-tree capture settles it (not run: machine
held by a sweepwalls replay, disk at 16 GB).

## #333 (§60 (4)) — ruled by intervention, dry on this tree

The #333 admission re-kinds 1,450 m² of `pav6` junction → apron at -12.0159033,
-77.1147723 (450 m from the owner's site, which is junction in both arms), absorbs
four route faces (2,759 m²) into apron and mints two 3 m slivers `dsf:pol50#12/#13`
(972 m²) flipped to apron by §27. CLIPPING pages to their off-apt.dat part: 9 m²
changed — REFUTED. `conc_3` as a GAP SHEET: the exact inverse (5,758 m² of role
change undone) + one piece 505 m². Overlay polygons only (≥ 80 %): the same;
the partial page alone: nothing. → the general rule "an OVERLAY page's remainder
is a gap sheet, never a source piece" (existing witness, one site); population
SPJC 13 / 7,877 m², KASE 4 / 311, OTHH 8 / 812, others 0. Owner Q2; own sub-step.

## Consumer verdict (§60 (5))

Two files change (the gate, the population site); one `[load]` line and two
report keys added; `pavement_admission_report.py` ports with one word; EVERY
downstream reader (classify's eight union consumers, planar, late stage, census
families, sidecar) sees only more / larger §53 pieces — no veto. One-time cost:
`airport.dsf` is in `partition_code.CODE_MODULES`, so the partition cache
re-reads once per airport after the merge (OTHH ≈ 196 s). Load digest unchanged;
classify digest changes at HECA / OTHH only.

## Sub-steps (§60 (6)) — after `claude/gapapron` (§59) merges; ≈ 6 h + the sweep

1 gate + 9 tests (1 h) · 2 load site + twins + CYXY sheet-free replay (1.5 h) ·
3 mint twin (20 min) · 4 port the tool, promote `admit_probe.py` to
`tools/gap_sheet_admission.py`, six `frames.jsonl` rows (1 h) · 5 OTHH capture +
replay: late-stage time, pull, class table, structures (1 h) · 6 closing HECA
build (10 min); OTHH read in the master's sweep · 7 (Q2) overlay remainders as
sheets, SPJC pair + its own sweep (3 h). The three conflict files are re-applied
by hand, never merged. Interface relied on: `Airport.gap_sheets` read at
`gap_mint.py:89`; §59's mint signature untouched.

## Owner questions (§60 (7))

* Q1 — if OTHH's patch build reads 600–630 s, does #337 still ship at OTHH in
  Beta 2? Recommend YES up to 10 % over (≤ 660 s), booked to the profiling round.
* Q2 — may 04d (2) (`conc_3` is pavement) be met like 04e (1): an overlay page's
  remainder as a gap sheet? Recommend YES (undoes #333 exactly at SPJC).
* Q3 — HECA `gap:0` / `gap:1` grow; if a site moves > 0.02 m at the closing
  build, accept the new level? Recommend accept.

## Not settled

OTHH late-stage wall time (estimate); the OTHH apron/taxi pull under §59; the
exact OTHH parts / knives / stations.
