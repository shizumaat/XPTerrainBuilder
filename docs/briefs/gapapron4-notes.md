# gapapron4 — notes (continues gapapron3; spec §59, RULINGS 2026-10-08c (6) / 08g / 09b)

Branch `claude/gapapron`, worktree `.claude/worktrees/gapapron`, scratch `<scratch>/gapapron4/`.

RUNWAY (owner RULINGS 2026-10-09b, relayed by the master mid-lane): a runway
shift up to 0.1 m caused by gap pieces joining the apron is ACCEPTED; the
second stage-one assembly is NOT built; the zone-claim trim stays. The runway
line is an acceptance bar: movers <= 0.1 m (count, worst unrounded, where).

## Done

* S4 THE MINT (`classify/gap_mint.py`, new `classify/gap_apron.py`):
  * `gap_apron.judge` — road evidence by `roles._road_evidence` (one more
    `evidence._osm_roads` call over the sheet union; `touch_tol_m` = stand-off
    + weld, `touch_roles` = the `road_cross_section` family), the class by
    `airside_edge_flip(road_class=)`. A no-evidence touching part is APRON
    even where §27 would not flip it (the ruling's words; §59 (2) 2 reads
    otherwise — FOR THE SPEC AUTHOR; no such part at HECA).
  * `gap_apron.close_rim` — DEVIATION from §59 (2) 4's formula, for the spec
    author: the literal `part ∪ (part.buffer(weld) ∩ apron.buffer(weld))`
    (a) grows a 1 m EAR round the apron's corner at every contact end and
    (b) leaves SLITS along both rims where the gap is 1–2 m wide (measured at
    the spec's own site: gap 1.26 m at 30.1278346, 31.4046247 — the band
    absorbed stood 0.13 m off each rim). Built instead: the morphological
    CLOSING of part ∪ apron at `weld_m` (mitre), less both, less the mint's
    own knife (standing cells with their stand-off, the band envelope, the
    other pieces); only a body that reaches BOTH rims is absorbed. Same
    extent as the spec's words ("within weld_m of BOTH"), no ear, no slit.
  * spelling: `apron` / `gapapron:<j>` / kind `gap_apron`, evidence
    `gap_apron, gap_ref, area_m2, apron_shared_m, airside_edge_m,
    road_evidence`. `gap:<k>` keeps the part's ordinal among ALL minted
    parts (a road piece keeps today's ref; `gap_ref` is the ref the apron
    part would have carried) — §59 (2) 3's "separate counters" read this way
    because the class table and the sites name today's refs.
  * `APRON_TOUCH_ROLE` deleted; stats `gap_pieces_apron` (apron-classed),
    `gap_pieces_road` (touching, road-classed); one note per apron part.
  * HECA frame twin (`test_gap_apron.py::test_the_class_table_read_on_a_real_map`,
    capture `frames/gapapron3/HECA.pkl`, 81 s): 38 pieces; ROAD 8 = gap:0, 2,
    4, 7, 11, 12, 28, 29; APRON no-evidence gap:22, 24, 35; by share gap:13,
    15, 16, 17, 20, 30, 33, 36 — THE REAL READERS GIVE THE PROBE'S TABLE. Rim
    closure: unwelded part|apron ground < 1 m2 on all 11 (was 26.1 m2 gap:15,
    20.6 m2 gap:30, 14.1 m2 gap:24 — the last is band-envelope ground and
    stays); areas: gap:15 3,014 -> 3,040 m2, gap:30 427 -> 448 m2; gap:30 |
    pav39 coincident rim 29.3 -> 40.1 m; the census's sliver site
    30.1278259, 31.4046286 is inside the part.
* S5 `publication.gap_pieces(cut, cells)` — apron records; published also
  when no last stage ran. Build + replay call it.
* S6 `tools/v2_solve_replay.py --gap-free` (the build's base map; arm table
  `tools/replay_arms.py`, INDEX row, twins in `test_v2_solve_replay_arms.py`).

## S6 — the like-for-like pair (capture `frames/gapapron3/HECA.pkl`, this tree)

Arms under `<frames>/gapapron4/`: `A` (rule OFF: `docs/briefs/gapapron4/arm_a.py`
replaces `gap_mint.judge` so every touching piece is ROAD; base = the shared
control `gapapron3/B0/solved.pkl`, late = `A/`), `BBASE` (`--from classify
--gap-free --emit --verify --solved-out`), `B` (`--from classify --late-from
BBASE/solved.pkl ...`). All EXIT 0. Reads: `late_{A,B}.txt`, `site_{A,B}.txt`,
`avd_A_B.txt`, `census_A_B.txt`, `pieces.json` (probes in `docs/briefs/gapapron4/`).

* OWNER SITES (A / B): #430 `gap:7/lot` 97.64 / 97.64; #292 `gap:7/ramp0`
  98.46 / 98.47; #358 `gap:0/s4/lot` 90.25 / 90.25.
* RUNWAY (bar: <= 0.1 m, RULINGS 09b): `airside_value_delta` A->B 32 nodes
  > 0.01 m, worst 0.020 m at 30.12519288, 31.38877602; UNROUNDED (B0 vs
  BBASE, `zdiff.py`) `05L/23R` worst 0.0172 m at v4219 30.12519288,
  31.38877602, 5 nodes > 0.01 m, 93 > 0.005; `05C/23C` 0.0027 m; `05R/23L`
  0. Nothing over 0.1 m. Chain (S0's interventions): gap:13 -> `pav53` /
  `route11` -> `pav39` -> `dsf:objpav115` -> runway (the v4219 group);
  the 0.010 m group at 30.1283, 31.3922 stays with gap:13 / gap:17 out.
* STANDING MOVES (B0 -> BBASE, unrounded): apron 1,814 nodes > 0.01, worst
  2.468 m `pav6` 30.1046762, 31.3964588 (100.80 -> 103.27) — the ruled 2.47;
  taxi 2,767 nodes, worst 1.375 m `pav111` 30.1044822, 31.3958726 — the
  ruled 1.38; nothing above either. Pads worst 0.30 m (`building142`).
* base stage: hard_conflict 244 -> 244; taxi-tier relaxed 63 / 61 = 63 / 61
  (S0's +2 is GONE with the rim closure); the 4 sliver-site rows on
  `small_roads:-3929` are gone; 2 pad-tier `frontage_hold` rows moved from
  `building91` to `building93` (same 0.078 / 0.071 m). Shapes 52 -> 53, 2
  contour joints (`apron_terrace`, 0.051 m over 7.0 m at 30.1046581,
  31.3957662; 0.050 m over 3.1 m at 30.1045342, 31.3966481, shapes 14 | 25).
* late stage A -> B: pieces 38 -> 27, parts 82 -> 67, knives 33 -> 33 (worst
  7.93 m both); movers 0 of 34,569 -> 0 of 34,737; foreign 0 -> 0; follow
  misses 84 (DECLARED 44 + OWN-GROUP 40, worst 2.04) -> 70 (40 + 30, 2.03);
  lot rows 195 / 9 missed -> 186 / 5; stepping pairs 82 / 66 / 18 -> 61 / 56 /
  15; ribbons grown 9 -> 9; feasibility relaxed 67 (groundside 63, taxi 4)
  -> 50 (groundside 50, taxi 0); follow conflicts 14 -> 9 named.
* census A -> B: ADJUDICATED 14,389 -> 14,403 (airside 12,181 -> 12,195,
  groundside 2,196 -> 2,199); CRITICAL motion 3 -> 2 (gone: 0.523 m over
  0.98 m `vertex_to_edge_step apron|junction` at 30.1090081, 31.4039576; no
  apron|apron sliver row); CRITICAL visual 1,910 -> 1,910; hard_conflict 311
  -> 294; airside_no_step 4,021 -> 4,026; mid_edge_step 54 -> 54;
  vertex_to_edge_step 15 -> 14; terrace_actual_step 42 -> 39; transverse 928
  -> 947; taxi_box 2,437 -> 2,452; within_shape 45,652 -> 45,665.

## Next

S6 runs (arm A = rule off via `<scratch>/gapapron4/arm_a.py`, arm B = tree),
S7 suites, S8 build + identity, CYXY no-op.
