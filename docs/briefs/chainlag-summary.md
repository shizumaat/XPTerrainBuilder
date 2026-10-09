# chainlag — summary (Fable spec author, 2026-10-09; spec §63 on `claude/chainlag`)

Brief: §62 R-C (a landside-only pad follows its senior touching pavement, a road before a lot) failed at implementation
(lane seat2): class C rose 570 → 963 m and the one-way lag did not carry the chain road → pad → lot. Design the order,
the sloping leader, the per-ref record split, the landing witness, the no-vertex road page. MID-LANE the owner ruled
2026-10-09j: pads are SENIOR to roads; a road touching a pad (overlap or no gap, read on the SOURCE geometry) is welded
to it; a road with any gap is free and the step is a wall/embankment, not a defect. §63 is 09j on the engine's geometry.

## What was measured (replays of `frames/pads67/{HECA,KCLT}.pkl`, base = seat2's merged-tree pairs `m` / `km`)

* `p0` (seat2-rc's R-C as found, on the merged tree): C 15 / 564 → 17 / 957 m, lag 845 rows unsettled (1.544 m),
  pad conflicts 104 → 15, airside 0. Reproduces seat2.
* `p1` (the one-way lag solved in LEADER ORDER — rows enabled at their depth, undamped there, pad-level rows read once):
  C 18 / 766 m, 764 rows unsettled, `building12` | `pav57` 5.74 m over 386 m. THE ORDER WAS NOT THE DEFECT — refuted.
* THE FINDING (`gapread.py`: classify with the engine's pad set-back knife OFF, raw cells against the pad rim):
  of the 36 class C/B runs at HECA / KCLT / SPJC, **24 (627 of 749 m) OVERLAP the pad in the source** — HECA 15 of 18
  (`building12` | `pav57` 5,927 m², `building15` | `objpav394` 516 m², `route3` 1.4 / 0.2 m²), KCLT 7 of 13, SPJC 2 of
  5 (`building24` | `pol36/37`, 09f's open site). The "gap" the engine then seats across is its OWN:
  `classify/roles._cut_back_groundside` cuts every groundside cell 0.954 m back from every pad (09-01g/i, 04u). The
  12 gapped runs (HECA `building164` 1.23 m — §62's R-B case; KCLT `pol48`; SPJC's three) are FREE under 09j (2).
* `q1` (09j's order in ROW form: no groundside seat, every pad leads its frontage by §28 rows): the pads rise to their
  DEM datum (`building12` 96.2 → 103.9, KCLT `building73` +6.94) and the roads do NOT follow a soft row against their
  own hard law — HECA C 12 / 1,040 m, apron 7 movers 0.28 m; KCLT C 8 / 128, ARMED 4 / 54. The row form is ruled out.

## The design (§63): rules T, W, S, B′, P, L

* T — the TOUCH WITNESS at the one site (`_cut_back_groundside`, before the knife): `d ≤ emit.identity
  .min_distinct_spacing_m` (0.5 m — the only tolerance: a smaller gap cannot stand in the planar map, 04u) ⇒ touching,
  else gapped with `d` published per cell and in the sidecar.
* W — a touching cell is clipped at the footprint and WELDED to the pad's rim by `planar/weld`'s own two halves with
  the pad frozen (shared vertices; no sliver, no T-vertex); the shared vertices are PAD columns (the plane governs,
  the road's rows conform, the tier ladder already ranks pad > groundside road); no §20/§28 row, no lag; a gapped cell
  is left as drawn — no knife, no row (09j's wall). §28 (6) held terraces keep the knife (09f).
* S — a pad's seat is airside (§20) or its §9b DEM datum; never groundside pavement. `pad_seat.py` / R-C deleted.
* B′ — R-B reduced to the SHARED vertex (no ramp row / join pin there; the ramp starts at the first road vertex off the
  rim); `building164`'s no-vertex road page is a 1.23 m gap: free, dissolved. Noding = the weld's insert half.
* P — records and the edge read per FACE id (`building15` | `objpav394` classes per face).
* L — the landing witness is the hard register (`pad_has_fixed_level`: a deck row, a held datum, a pin), not `LANDINGS`.

Sub-steps (11): S 2 h → T 3 h → W 8 h (needs its own capture: the planar map changes) → B′ 3 h → P/L 2 h → HECA once.
Unproven (12): the weld itself (no replay knob reaches the planar stage), Q-B's ramp feasibility, the 7 apron movers
of `q1`, the other four airports' touch census, `p1` as a general lag improvement.

## Owner questions (yes/no)

* Q-A: a touching pair whose DEM step > 2.4 m stays a HELD terrace (09f) — the one exception to "no gap ⇒ welded".
  YES recommended.
* Q-B: a landside pad keeps its DEM datum and the touching road climbs to it: HECA `building12` | `route3` rises ~8 m
  along 98 m of contact (the road today 10 m under the terrain, chained to the apron at 92) and ramps ≤ 10 % to the
  apron. YES recommended (09j literal; the alternative is the cutting).

Branch `claude/chainlag` (spec §63 + notes + this file); probe tree `claude/chainlag-probe` cce61d26 (never merges).
