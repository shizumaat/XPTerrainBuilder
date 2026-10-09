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

## Next

S6 runs (arm A = rule off via `<scratch>/gapapron4/arm_a.py`, arm B = tree),
S7 suites, S8 build + identity, CYXY no-op.
