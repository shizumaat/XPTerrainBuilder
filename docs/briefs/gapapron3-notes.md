# gapapron3 — notes (lane resumes gapapron2; spec §59, RULINGS 2026-10-08c (6) / 08g)

Branch `claude/gapapron`, worktree `.claude/worktrees/gapapron`. Scratch
`<scratch>/gapapron3/`. Kept current after every step: done / partial / next
command / numbers.

## State

* DONE — main `d0b2f0f4` (walls branch) merged into the branch (`183edd34`;
  `docs/frames.jsonl` conflict resolved as the union).
* DONE — the dead lane's scratch read (`<scratch>/gapapron2/`), old tree
  (pre-walls), capture `gaps3/HECA.pkl`:
  * its arms, all stage-1-only ("base" mode: the late pieces dropped), all EXIT 0:
    `X0` = no piece apron (control), `X1` = 10 apron (gap:13 taken out of the
    class; its `solved.pkl` is gone, never compared), `X2` = 11 apron + its
    CANDIDATE RULE (`PROTO`: pass 1a solved without the rows that touch a
    gap-apron part's OWN vertices; pass 1b carries them under pass 1a's runway
    Bands).
  * `rw_dz.json` (unrounded, `gaps6/BASE` vs `gapapron/ARMBASE`): `05L/23R`
    worst 0.0172 m at v4219 30.12519288, 31.38877602; 4 nodes > 0.01, 88 > 0.005;
    `05C/23C` worst 0.0027 m; `05R/23L` 0.
  * read by this lane: `X0` vs `X2` (the PROTO): `05L/23R` worst 0.0081 m at
    30.12830117, 31.39221539, 0 nodes > 0.01, 40 > 0.005; `05C/23C` 0.0022;
    `05R/23L` 0. So the candidate halves the move and does NOT give 0 on the
    cm-rounded patch.
* DONE — fresh capture on this tree (137 s, 43,009 vertices / 1,999 faces):
  `/Users/noah/XPTerrainBuilderData/.harness/frames/gapapron3/HECA.pkl`
  (to register at handover). Scratch drivers: `<scratch>/gapapron3/s0_driver.py`
  (the dead lane's), `planar_arms.py`, `region_arms.py`, `zdiff.py`, `rw_nodes.py`.

## S0 (reads; fresh capture, tree = main d0b2f0f4 + this branch)

### The class table re-derived (`docs/briefs/gapapron/evidence_read.py`)

38 pieces, 19 apron-touching (832,167 m2). The walls merge removed one road
piece and renumbered two:

| class | spec (gaps3 capture) | fresh capture |
|---|---|---|
| ROAD | gap:0, 2, 4, 7, 11, 12, 28, 29, 34 | gap:0, 2, 4, 7, 11, 12, 28, 29 (old gap:34, 258 m2, is no longer minted) |
| APRON, no evidence | gap:22, 24, 36 | gap:22, 24, **35** (= old 36, 249 m2) |
| APRON by share | gap:13, 15, 16, 17, 20, 30, 33, 37 | gap:13, 15, 16, 17, 20, 30, 33, **36** (= old 37, 242 m2) |

### (a) THE RUNWAY — two mechanisms, both attributed by intervention

Arms (stage base only, the late pieces dropped; `s0_driver.py base`):
`B0` no piece apron; `B1` the 11 apron-classed pieces as `apron` /
`gapapron:<k>`. `B0 -> B1`, `airside_value_delta`: runway **74 nodes > 0.01 m,
worst 0.05 m** at 30.12116239, 31.42625284; unrounded (`zdiff.py`): `05C/23C`
worst 0.0539 m (10 nodes > 0.01), `05L/23R` 0.0172 m at 30.12519288,
31.38877602 (4 nodes > 0.01), `05R/23L` 0.0036 m. AND the runway's VERTEX SET
changed: `05C/23C` +143 / -3 vertices (2,610 -> 2,750), the nearest piece
1.6 km away.

1. PLANAR (the 05C/23C half): `planar/zones.zone_regions` unions EVERY cell
   into the claim the zone bands are differenced against. The 11 extra apron
   polygons re-node that union, and beside 05C/23C a hairline of the runway's
   own lip — `adjacent_ground:runway:4:zone1#5`, 1.31 m2, 1,689 m x 0.8 mm —
   passes the 1 m2 part floor (two other zone-1 parts grow 970 m / 1,471 m
   whiskers). Its ring nodes the runway edge: 143 new runway vertices.
   Interventions (`planar_arms.py`, planar stage only): each of the 11 pieces
   alone 0 / 0 runway vertices changed; either half (5 / 6 pieces) 0 / 0; all
   11: +143 / -3 — chaotic in the union, not a property of one piece. The
   standing regions handed to pass A are otherwise identical and in the same
   order (`region_arms.py`). FIX TRIED: the gap-apron cells are left OUT of
   the claim (the mint already cuts every piece out of the band envelope with
   the stand-off) and subtracted from a band only where they reach one: all
   11 -> 0 / 0 runway vertices changed.
2. SOLVE (what is left once 1 is trimmed — exactly the spec's probe number).
   `B2` = B1 + the zone trim: runway vertex set identical to B0 (2,610, 0 / 0);
   `airside_value_delta` runway **30 nodes, worst 0.02 m** (spec: 29 / 0.02);
   unrounded `05L/23R` 0.0172 m at v4219 30.12519288, 31.38877602 (4 nodes
   > 0.01, 91 > 0.005), `05C/23C` 0.0027, `05R/23L` 0.
   * `--why-vertex 4219` on B2 (`<scratch>/gapapron3/why4219.txt`): the vertex
     is bound by `runway_crown` (`common.runway_crown_transverse`, to v3368)
     and by `runway_flex BAND hi=58.742052 rulesets.runway.flex_budget … beta_R
     0.000 m, no pulling pad: held at its pass-1a value`. So NO runway row was
     relaxed, no soft runway row gave, no vertex is shared: the runway's
     stage-1 level IS pass 1a's level by definition (flat-pad spec v2 §1, the
     "unpulled profile"), pass 1b bands it there — and pass 1a carries every
     stage-1 row, the gap-apron cells' too. The cells perturb pass 1a's joint
     least-squares solve and the band then holds the runway at the NEW value.
   * the chain at v4219 (`near2.py`, B0 -> B2, max |dz| per face within 450 m):
     `gapapron:0` (gap:13) 0.41 -> aprons `pav53` / `route11` 0.16 -> `pav39`
     junction 0.11 / apron 0.09 -> apron `dsf:objpav115` (welded to the runway)
     0.059 -> runway `05L/23R` 0.017.
   * INTERVENTION, pieces: `B3` = B2 without gap:13 and gap:17 (9 pieces): the
     v4219 group is gone, but `05L/23R` still moves 0.0082 m at 30.13103052,
     31.39585741 (75 nodes > 0.005) and the instrument still reads runway
     **20 nodes, worst 0.010 m** (one-centimetre flips, `05C/23C` among them at
     30.0998502, 31.3975386). NO piece, removed from the class, restores 0: every
     stage-1 apron cell moves the joint solve by millimetres everywhere.
   * INTERVENTION, rows: `B4` = B2 + the dead lane's candidate (pass 1a solved
     without the rows that touch a gap-apron part's own 116 vertices — 2,527 /
     4,896 rows withheld to pass 1b): unrounded `05L/23R` 0.0081 m at
     30.12830117, 31.39221539 (0 nodes > 0.01, 45 > 0.005); instrument runway
     **20 nodes, worst 0.010 m**. (The prototype also drops the rows from the
     stage-2 restatement — `other` 664 nodes worst 13.17 m — it is a probe, not
     a candidate build.)

   | arm | runway nodes > 0.01 m (`airside_value_delta`) | worst | unrounded worst (`zdiff`) | runway vertices +/- |
   |---|---|---|---|---|
   | B1 (11 apron cells, tree as specced) | 74 | 0.05 m | 0.0539 m (`05C/23C`) | +143 / -3 |
   | B2 (+ zone trim) — attempt 1 | 30 | 0.02 m | 0.0172 m (`05L/23R`) | 0 / 0 |
   | B3 (B2 less gap:13, gap:17) | 20 | 0.010 m | 0.0082 m | 0 / 0 |
   | B4 (B2 + pass-1a row withholding) — attempt 2 | 20 | 0.010 m | 0.0081 m | 0 / 0 |

   THE GENERAL RULE THAT WOULD GIVE ZERO (stated, NOT built — it is outside
   §59's design, which names no consumer change in the solve): "a gap-apron
   cell is a PULL, as a held pad's frontage hold is: the runway's unpulled
   profile is solved WITHOUT the cells and pass 1b, with them, holds every
   runway column at that value." Row withholding inside one map cannot make
   pass 1a the cell-free problem (the standing rims carry the cells' weld
   vertices, the shapes are merged: 0.0081 m is what is left), so the profile
   has to come from the stage-one problem assembled on the map WITHOUT the
   cells (`stage_one_map.stage_one_problem`'s own transform, the canonical
   join) and be handed to pass 1b as the Bands' centre. Cost on a gap-apron
   airport: one more stage-one assembly (66 s at HECA, measured in B1's log)
   — the map's own pass 1a (37-52 s) can be replaced by it; a Band at beta 0
   is two one-sided rows in the active set, not a pin, so "zero" also needs
   the band to be exact (a `Pin`, or the 09y runway projection re-run).
   Touches `solve/flex.stage_one`, `constraints/no_step.HoldPass`,
   `pipeline/stage_one_map`, `pipeline/build`, `tools/v2_solve_replay`.

   VERDICT (attempt cap 2 reached on the runway bar): NOTHING INSIDE §59's
   DESIGN GIVES 0. STOP — S4 (the mint, which would ship the mover) is not
   built. S1-S3 and the zone trim are neutral (no cell carries the ref).

### (b) the other reads (B0 vs B1)

* stage-2 feasibility relaxations: B0 227 / 213 (taxi 63 / 61) -> B1 231 / 217
  (taxi 65 / 63): +2 taxi-tier, +2 groundside. `hard_conflict` records
  244 -> 248, 0 only in B0, 4 only in B1, ALL at one site — the mapped-road
  ribbon `small_roads:-3929` between `gapapron:7` (gap:30) and
  `pav39#plateau:building147`:
  * taxi, stage 2, `pavement_max_grade ceiling`, 0.210 m at 30.1278606, 31.4045803 (`face:261`, `gapapron:7`)
  * taxi, stage 2, `pavement_max_grade ceiling`, 0.112 m at 30.1278944, 31.4045569 (`face:262`, `pav39#plateau:building147`)
  * groundside, stage 2, `road_cross_section`, 0.029 m at 30.1278674, 31.4045777
  * groundside, stage 2, `groundside_road ramp ceiling`, 0.035 m at 30.1278651, 31.4045751
  (the spec's sliver site, §59 (2) 4: the part and `pav39` are not one rim there).
* base shapes 52 -> 53, contour joints 0 -> 2 (10 m, max step 0.05 m), both
  between shape 14 (`gapapron:1` = gap:15 with `pav6`) and shape 25
  (`dsf:objpav106#2`, `route22`): 7.0 m `apron|graded_strip` at 30.1046581,
  31.3957662 and 3.1 m `apron|service_road` at 30.1045342, 31.3966481 — the
  two ends of the part's contact with `objpav106#2`'s body (where the 2.47 m /
  1.68 m pull is).
* structures: Tunnel 11 = 11.

## Done on the branch (all neutral: no caller, no cell with the ref)

* `c26baece` S1 `model/planar` `GAP_APRON_PREFIX`, `is_gap_apron_ref` + the
  zone trim (`planar/zones`: a gap-apron cell is not in the zone claim) —
  a DEVIATION from §59 (4) row 10, for the spec author.
* `f1ee9fcc` S2 `roles._road_evidence(touch_tol_m=, touch_roles=)`, S3
  `airside_edge_flip(road_class=)`; twins in `tests/auto_patch_v2/test_gap_apron.py`.

## Not done

S4 (the mint: evidence -> class -> spelling -> rim closure, the sheet-union
`_osm_roads` call, `APRON_TOUCH_ROLE` deleted, the frame twin), S5
(publication), S6 (the like-for-like pair, `v2_late_read`, the sites, the
census), S8 (the closing build). The class table to pin at S4 is the fresh
one above (ROAD 8, APRON 3 + 8).

## Next (for the lane that resumes)

1. The runway rule needs its design (above) — the spec author's.
2. S4 as specced; note for it: the replay needs a base WITH the gap-apron
   cells and WITHOUT the gap pieces (`stage_one_map.gap_free` after classify —
   what `pipeline/build` does); `v2_solve_replay` has no flag for it (earlier
   lanes replayed a sheet-free capture, which would drop the gap-apron cells
   too). `<scratch>/gapapron3/s0_driver.py base` does it by wrapping classify.
3. The four `hard_conflict` rows of (b) sit at the spec's sliver site: read
   them again after the rim closure.

## Frames and probes

* captures: `<frames>/gapapron3/HECA.pkl`, `<frames>/gapapron3/CYXY.pkl`;
  arms `<frames>/gapapron3/{B0,B1,B2}/` (patch + sidecar + `solved.pkl` +
  log), registered in `docs/frames.jsonl`. `B3` / `B4` are in the scratch only.
* probes (scratch scripts, kept for the record, no tool): `docs/briefs/gapapron3/`
  — `s0_driver.py` (the arms), `planar_arms.py` / `region_arms.py` (the planar
  interventions), `zdiff.py` (unrounded per-vertex delta of two `--solved-out`
  pickles), `rw_nodes.py`, `near2.py`, `hc.py`, `evidence.json` (the fresh
  class table), `why4219.txt`.

## No-op proof for what is committed

CYXY, fresh capture on `f1ee9fcc`, `--from classify --emit`: body
`cf8e9e89ec62` = main's `sw6_CYXY`. HECA and every other airport: no cell is
spelled `gapapron:` and no caller passes the new keywords, so the build is
main's by construction (not re-run).
