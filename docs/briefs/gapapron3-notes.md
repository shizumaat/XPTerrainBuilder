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
2. SOLVE (the 05L/23R half): to be isolated by the arms running now.

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

## Next

Arms `B2` (B1 + zone trim), `B4` (B2 + the dead lane's pass-1a withholding),
`B3` (B2 without gap:13 / gap:17) are running:
`venv/bin/python <scratch>/gapapron3/s0_driver.py base <scratch>/gapapron3/evidence.json <EXCLUDE|-> <PROTO 0|1> --replay <frames>/gapapron3/HECA.pkl --from classify --emit DIR --solved-out DIR/solved.pkl`
then `zdiff.py B0/solved.pkl BX/solved.pkl runway`.
