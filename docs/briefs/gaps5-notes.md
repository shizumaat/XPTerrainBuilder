# gaps5 notes — spec §55 implementation, STOPPED at S2 on a spec claim (2026-10-06)

Lane `gaps5`, branch `feature/pavement-gaps`. Main `a262e5e6` merged first
(`26bdbddc`). The lane stopped BEFORE the first replay: a dry read of the cut
on HECA (classify of `gaps3/HECA.pkl` + the levels of `gaps3/BASE/solved.pkl`,
no solve) shows §55 (1)-(2) does not produce the picture §55 (7) expects.
The decision is the spec author's; nothing was decided here.

## State by step

| step | state |
|---|---|
| S0 read | PARTIAL. Done: violated rows of `gaps3/ARM` by head (below). NOT done: the per-row classing of the +104 / +32 / +4 / +164 / −57 census rows; `--why-vertex` on the two §53 (16) vertices. |
| S1 `classify/gap_terrace.py` | COMPLETE as specified, twinned (`tests/auto_patch_v2/test_gap_terrace.py`, 8 tests), law key `[terrace] gap_cut_sample_m = 2.0`. Commit `d99c8a8d` + the lot-sliver repair in the S2 commit. |
| S2 `pipeline/late_stage.py` | PARTIAL. Written: `late_stations`, `cut_classification`, `run_late_stage`. NOT wired into `tools/v2_solve_replay.py --late-from`; no replay run; `test_late_stage.py` not extended; rows 3 and 10 of §55 (6) not seam-probed. `run_late_stage` has never executed. |
| S3 – S9 | NOT STARTED. No HECA build, no CYXY identity, no census, no suites beyond the two twin files. |

## S0: violated rows of the ARM by head (`gaps3/ARM/solved.pkl`, > 0.02 m)

| rows | worst | both ends unknown / one a constant | generator, head |
|---|---|---|---|
| 475 | 5.22 m | 437 / 38 | `roads`, `common.roles longitudinal` (the piece's own all-pairs cap) |
| 201 | 7.47 m | 201 / 0 | `road_ramp`, `roads.groundside_road ramp to the DEM` |
| 165 | 5.23 m | 165 / 0 | `gap_follow` (hard) |
| 76 + 66 | 2.08 / 3.55 m | 0 / 142 | `groundside_frontage` (+ junior) |
| 35 | 0.75 m | 0 / 35 | `road_ramp`, airside contact |
| 14 | 1.14 m | 0 / 14 | `pavement_ceiling` (hard) |
| 12 | 0.42 m | 8 / 4 | `roads`, `road_cross_section` (hard) |
| 7, 5, 2, 2 | ≤ 1.12 m | — | `wall_terrace` lot level, ribbon airside follower, `plane_gradient`, taxi transverse |

`solve/feasibility.ConflictReport.by_head` ALREADY EXISTS (count per head);
§55 (5) asks only for the worst metre and the print on the LAST STAGE line.

## THE STOP: the dry cut on HECA (39 pieces, 2,834 stations; 8–10 s)

| reading of `cap_s` | parts | knives | stations merged by the floors | kinds |
|---|---|---|---|---|
| §55 (1) literal: the tighter of the piece's cap and the ring's (apron and pad rings 1.5 %) | 335 | 405 | 889 | step 298, lot 15, ramp 2, uncut 20 |
| measurement arm only: the piece's 8 % on every station | 176 | 139 | 437 | step 113, lot 27, ramp 14, uncut 22 |

§55 (7) expects merged stations ≤ 10 and the owner's lot cut into a lot and
a ramp on one breakline.

Owner sites (which part holds the point):

| site | literal | 8 % arm | §55 (7) expects |
|---|---|---|---|
| #430 30.1154841, 31.4105884 | `gap:7/s0/lot` | `gap:7/s0/lot` | a `lot` part |
| #292 30.1159784, 31.4106264 | `gap:7/s1` (a step part) | `gap:7/s0/lot` (the lot; no ramp part exists in `gap:7`) | the `ramp` part, continuous with the lot |
| #358 30.1193169, 31.4085087 | `gap:0/s160` | `gap:0/s5/lot` | unchanged from the arm |

`gap:7` (10,653 m², 50 stations: road 37, apron 13):

* literal: 10 level groups, 4 knives, 15 merged. Inconsistent pairs: apron–road 431, road–road 32, apron–apron 10 (the apron against itself at 1.5 %: 0.56 m over 37.5 m).
* 8 % arm: 5 groups, 5 knives, 8 merged; parts `s0/lot` 7,878 m², `s1` 1,845, `s2/lot` 332, `s3` 254, `s4/lot` 236. Inconsistent pairs: apron–road 33 (worst `pav37` 92.56 against `route3` 99.69, 7.13 m over 87.7 m), road–road 32.

Two mechanisms, both read off the pairs:

1. THE RING'S OWN CAP IN THE PAIR TEST. With `min(cap_s, cap_t)`, any pair
   holding an apron or pad station is tested at 1.5 %. All pieces:
   pad–pad 145,795 inconsistent pairs, apron–pad 71,546, lot–pad 39,324,
   pad–road 29,203, apron–lot 15,241, apron–road 6,929, apron–apron 5,909.
   At 8 % throughout: pad–pad 2,001, lot–pad 705, pad–structure 321,
   apron–road 187, road–road 162, apron–pad 132, pad–road 112.
2. A ROAD IS INCONSISTENT WITH ITSELF ACROSS THE PIECE IT WRAPS. `route3`
   climbs 92.05 → 100.47 along `gap:7` and bends round it: two of its own
   stations stand 6.78 m apart in level over 84.7 m straight across the
   piece (road–road 32 pairs in `gap:7`; 130 in `gap:8`, worst 96.31 against
   105.01 over 46 m). The straight chord lies INSIDE the piece, so §55 (1)'s
   "a concave piece's chord is priced by neither" does not excuse it. The
   greedy groups then split the road's own stations (`gap:7` groups 1–4 are
   road only; `gap:8` six road-only groups) and a knife stands between two
   stretches of one lawful road. This is independent of mechanism 1.

Consequence for 06d's picture: in `gap:7` the apron stations (92.1–92.8) and
the upper road stations (to 99.95) fail the pair test under either reading
(7.13 m over 87.7 m needs 89 m at 8 %), so the apron side and the road side
are separate level groups and a KNIFE stands between them — a step, where
06d rules a lot terrace and a capped ramp with no step.

## Questions for the spec author (yes / no)

* Q-A: should the pair test use the PIECE's cap for every pair (a ring's own
  cap binds only inside the 1.95 m follow reach)? Recommend yes; it is
  necessary and not sufficient (176 parts, 437 merged remain).
* Q-B: should stations of ONE standing ring (or one road) never open a level
  group against each other — the ring is lawful along itself? Not
  recommended without a measurement: it does not answer the apron–road pairs.
* Q-C: for a part that holds a road and an apron, should the lot cut run
  BEFORE (or instead of) the step cut between those two classes, so that an
  apron–road pair the cap cannot join over the straight chord becomes a ramp
  band and not a knife? This is the case 06d rules.

## Next command (after the ruling)

Scratch, first use, in `<scratchpad>/gaps5/`: `dry_cut.py` (classify the
capture once, write `cl.pkl` / `base_small.pkl`), `dry_cut2.py <dir>
[spec|piececap]` (the cut table and the three sites, 10 s), `dry_groups.py`
(pairs by class, the groups of `gap:7` / `gap:8`). Any change to the pair
test is re-read with them before a replay is spent.

Then S2 as planned: wrap the tail of `replay_problem` (from the planar build
to the return) in a local `_rest(cl)`, hand `run_late_stage` a `derive` that
calls it, skip `stage_one_problem` on a `--late-from` arm (unused by the
last stage, ~110 s), replace the inline block of `replay()` at
`# spec §53 (9) THE LAST STAGE`, and run

    venv/bin/python tools/v2_solve_replay.py --replay <frames>/gaps3/HECA.pkl --from classify \
        --late-from <frames>/gaps3/BASE/solved.pkl --emit ARM5 --verify --solved-out ARM5/solved.pkl

## Interpretations made where §55 is silent (for review)

* REFS COMPOSE: a step part that is lot-cut is `gap:<k>/s<j>/lot`,
  `gap:<k>/s<j>/ramp<i>`; several lot components are `lot`, `lot1`, …. §55
  names `gap:<k>/lot` only, which collides when two step parts each hold a
  lot. `gap_part_kind` (not yet written) would read the LAST path segment.
* A part left under the mint's floors BY THE KNIFE is dropped to ground and
  its area reported (`knife_dropped_m2`; 1,507 m² in `gap:0`, literal).
* The knife strip is `knife_m + 2 × snap grid` wide so the two rims stand
  `knife_m` apart after the snap.
* `terrace_cut` takes a keyword `cap` (the piece's own cap) beside the four
  arguments §55 (4) names.
* A follower ribbon is recognised BEFORE the full map exists as a mapped-road
  ribbon whose base ring comes within 0.3 m of a piece.
* Two stations at one point keep the class road < apron < pad < lot < band <
  structure.
