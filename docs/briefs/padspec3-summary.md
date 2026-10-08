# padspec3 summary (Fable, 2026-10-07) — §56 revised on the REAL classify after PR #463's STOPs

Branch `claude/padspec3` (= `origin/claude/pads56` 46b5dd9e + this). Design only; no engine
code touched. Spec: `tools/docq.py spec '§56'`. Probes: `docs/briefs/padspec-scratch/padspec3/`
(`classify_probe3.py` extends the implementer's `pads56/classify_probe.py` and runs the landed
`roles.classify` with one monkeypatch per arm; `replay_absorb_all.py` wraps `v2_solve_replay`;
`struct_faces.py`, `gap_diff.py` read products). Logs `<scratch>/padspec3/*.log`; the absorb-all
replay is registered (`frames.py list OTHH`, lane padspec3). Captures: `perfA362/cap/OTHH.pkl`,
`gaps3/HECA.pkl`, `conc333/KCLT_main28500ecf.pkl`. 11 engine runs: 7 classify arms, 1 rule-2
arm, 1 replay (the first replay attempt died in the spawn guard and was rerun), 1 outline check.

## Rulings (each with its probe numbers)

1. **§56 (2) 4 (b) DELETED — the wall-extended route is absorbed like any near road.** The 14
   `route*` cells kept at `building6` are "retained" by the TERMINAL'S OWN BASE
   (`OTHH_Terminal_Base_10_4.obj` 10.8 m, `_8` 20.3 m, `_2_1` 5.7 m, 1–9 m from the road): §47's
   wall-class classifier runs the road up to the building's face — the owner's case exactly.
   07b (2) sizes the corridor ramp off the WALLS now (`full_wall_ramp`, PR #460), never a road;
   every pack structure cuts the pad with its walls' hull (`hull_knives`), a door ramp's host pad
   is not a stop, and the only structure that STOPS at a pad is an OSM bore — (4) (a)'s keep-out,
   already complete. "Absorb outside the extension, keep the strip" refuted: 14 stubs of 0–78 m².
   Real classify, absorb-all: OTHH **40 roads into 7 pads** (26 with 4 (b)), site road cells
   **17 → 2** (`route37`, `small_roads:-8407`); HECA 39 into 18 (37 / 17); KCLT 58 into 25.
   Absorb-all REPLAY (`--from classify --emit --verify`): structure faces IDENTICAL to the sweep
   base airport-wide (tunnel_ramp 9 / 24,292 m², wall_corridor_ramp 14 / 2,630, door_ramp 4 / 21,
   tunnel_trench 43 / 9,814) and at the site (5 / 171); the same 28 pre-existing hard rows over
   0.02 m (max 0.0653, the base's `pad_slope_max` rows at 25.2542, 51.6205); verify 422 rows.
2. **§56 (2) rule 8 NEW — the re-close takes no airside and no deck shade** (doubt 4, measured).
   The absorption's close on the final pad cell re-fills shade and bridges apron: `building6`
   +7,153 m² = 3,845 road / **159 shade** / **516 airside** / 2,633 fill; HECA T3 `building3`
   +1,982 = 69 / **999 shade** / **691 airside** / 223; `building14` 136, `building17` 168,
   KCLT `building2` 162 m² of apron. The arrangement would then cut the apron back to it
   (09-23a, a footprint rule). RULE: `g − (deck_shades ∪ airside cells)` after the re-close;
   sidecar `absorb_growth_m2 = {road, shade_clipped, airside_clipped, fill}`; twins named.
3. **Growth bar replaced (§56 (1) 10).** Growth is NAMED, not capped: (i) join, (ii) light-well
   fill, (iii) closing fill, (iv) chord residue ≤ `outline_chord_m` × ring length, (v) a thin
   remainder rule 6 would have dropped, kept because the close joined it first (KCLT `unit:3#514`
   +85 % = 187 m², ring 191 → 331 m; `unit:30#0` 344 of 352 m²). Every one of the 13 OTHH + 15
   HECA + 5 HECA-absorption pads is explained (OTHH `unit:21#1` 932 = 649 well / 189 close / 94
   chord; `unit:28#8/1` +11.5 % = 18 m²; HECA `unit:43#80/2` +975 % = the renumbered `/3`;
   `unit:43#744/0` 2,204 = 1,348 / 138 / 717); over another unit **0 m²** (OTHH) / ≤ 2.9 m²
   (HECA) except named joins. STOP only for growth over another unit or airside after the
   arrangement, or chord residue over the bound. Sidecar `outline_growth_m2` = the five classes.
4. **Doubt 5 (structures derived after classify): no later site, no un-absorb.** Proven by the
   hull-knife reading + the replay's identical structure faces; the one real change is the ramp's
   TOP edge now shared with a pad vertex (DEM top vs pad plane) → the host-pad demotion already
   measured at `Terminal_Base_2_1`; bar: `|ramp top − pad plane|` quoted, `hard_conflict` 0.
5. **Vertex bar restated (§56 (8) step 1 / bar 1):** `outline_vertices` **552** at `unit:28#8/0`
   (rule-2b ring; the 650 was a probe that simplified after rules 8/3 — withdrawn), HECA
   `unit:43#6330/0` 453, KCLT `unit:31#0/0` 314; the site pad CELL after absorption **611 ± 5 %**.
6. **HECA gap pieces 93 → 91 ACCEPTED, each named.** 93 → 92: `gap:25` loses 54.5 m² to T3's
   closed outline, `gap:0` 42.7 / 57.5 / 20.0 to `building16/116/38`, and `gap:38` (201 m², a
   26.6 × 8.2 m strip 1.45 m from `building147`) is no longer minted: the closed outline touches
   it and, stood off, it holds no one-lane disc (§53 (13)) — bare ground, terraced as before §55.
   92 → 91: `gap:0/s0/ramp2` merges into its lot once `route24` beside `building3` is pad. No
   guard; one WATCH line (a kerb cliff there is the §55 floor's knob).
7. **Step 4 split (§56 (8)):** 4A ref hygiene (`#strip` for the inter-block strip + `block_strip_
   rows` split out of `platform_collar_rows`, `landing_bank_rows`, `platform_ref_of` joins,
   `connector_step_max_m`; z byte-identical) → 4B = old step 5 FIRST (seat ladder S3 + warning,
   collars still minted; HECA `--from constraints`) → 4C deletion core (8 readers that BREAK
   without a collar face: planar/platform, overlay, constraints/platform `platform_contacts` →
   the conforming branch's own-rim read, pads.py, placement_read, pad_block_seat,
   datum_vertices, Platform fields) → 4D dead-code removal (12 skip/special-case readers,
   byte-identical) → 4E sidecar + object readers. 4C+4D+4E are one merged batch / one sim read;
   1, 3, 4A, 4B may merge alone.

## New bars (OTHH site, after 4C): collar faces 0; road faces ≤ 3; faces ≤ 27; ring vertices
≤ 1,400 (replay 31 / 1,879 less collar 4 / 489); apron cut at the site ≤ base; pads 1 piece.

## Owner questions: none new (Q4 / Q5 stand). Finding for §47: the wall-class classifier admits
a building's own base walls as retaining pieces (3 OTHH resources, 14 routes).

## Not done / not settled
- The ramp-top-vs-pad-plane residual at the three wall-corridor ramps bordering a pad is not
  measured (no ramp is at the owner's site; the replay has no per-vertex diff) — step 4C's bar.
- The growth classes are measured against the rule-2 PIECE; class (v) is inferred from the ring
  getting longer, not re-derived from `u_in` (that read is the implementer's sidecar).
- The late-stage HECA frame twin was not re-run (the implementer re-recorded it); the gap
  attribution is at classify.
- No closing build; the replay keeps the collars (step 4C is design).
