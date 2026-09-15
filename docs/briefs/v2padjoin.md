# Brief pack — lane `v2padjoin`

Base: main `403c562d` · generated 2026-09-14 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

The apron reach is a PLANE JOIN; the skirt withdrawn; the pad between aprons at ≤ 1 %; datum at the low side (RULINGS 14bf/14az/14ay) — re-land v2padvert first

## The brief

You inherit lane v2padvert (branch `claude/v2padvert`: c9787d1e = the arrangement-level clip + the HECA build pair; HEAD 99d795ef = 14ay/az built, 20 twins red). Its c9787d1e merge into main was REVERTED (14bg): on main it fails 14 twins (the list is in RULINGS 14bg). FIRST: cut your worktree from MAIN (`lane_worktree.sh up v2padjoin <main sha>`), then `git merge claude/v2padvert` at c9787d1e (NOT 99d795ef) into it and run the suite — attribute the 14 failures (which are the clip's, which the pads-ON default in a twin, which main's later merges) and make them green with the law as merged (no test deleted; a twin that encodes a withdrawn rule is re-founded and named). That is bar 0. THEN the ruling (14bf; `tools/docq.py spec '§30 (4)'`, `tools/docq.py spec --object '§16g (10)'`, `tools/docq.py ruling 14bf 14az 14ay 14au 14as`): the cluster-pad APRON REACH is a PLANE JOIN — within `cluster_apron_reach_m` (40 m) of a touching pad, the apron's vertices are BOUND INTO the pad's plate (equality rows at hard weight, the same plate rows the pad's own vertices carry), bounded to the touching component (§30 (5)) and never across a taxi-family face; beyond the reach the apron returns to its own law within 1 %; the skirt (`pad_skirt_m`, `pad_skirt_max_slope`) is withdrawn; (9)(2): a pad between two aprons is a plane at ≤ 1 % taking each apron's level at each shared edge; the cluster datum = the pad's LOWEST shared-edge level (`footprint_unit.plan_unit_datums` / `cluster_pad.plane_groups`). Site: `constraints/cluster_pad.py` (`cluster_apron_level`, `cluster_apron_faces`, the row form) + `constraints/pads.py`. Consumer census of every reader of the cluster-pad rows and the apron rows within the reach (the apron's own within-shape/tier rows on collar vertices — do they conflict with the join? name them) BEFORE editing. Measure on v2settle's registered KCLT and HECA captures under `staged_solve = true` with `pad_from_cluster = true` (the certificate line, `v2_solve_replay --why-hard-stage`); NOTE the capture gap (chip `capclusters` — `airport.clusters` absent from captures; if the chip has not landed, the pads-ON arm needs a BUILD: the pair `/tmp/harness/v2padvertHECAon.osm` / `HECAoff.osm` exists — register them). Bars: KCLT 1,308 → 0 / HECA 794 → 0 infeasible rows (each pad named with its collar area), airside moved vs pads-OFF = the collar only (name the m² and the max move inside it; 0 beyond the reach), the reach never crosses a taxiway (twin + census), the terminal at 30.1279552, 31.403143 on its pad (name the level), KCLT `building80` and its members' seats named, the 9 "no pad law" twins green AS WRITTEN or re-founded with the reason; suite twice ON THE MERGED TREE. Both flags stay OFF on main; the arms arm them. ONE HECA build.

## Bars

- Bar 0: main + claude/v2padvert@c9787d1e merged → suite green (the 14 of RULINGS 14bg attributed and fixed, none deleted).
- KCLT 1,308 → 0 and HECA 794 → 0 stage-2 infeasible rows under §20b with pads ON (v2settle captures; each pad named with its collar area).
- Airside moved vs pads-OFF: only inside the collars (m² and max move named); 0 beyond the reach; the reach never crosses a taxi-family face.
- The terminal at 30.1279552, 31.403143 on its pad (level named); KCLT `building80` + members' seats named.
- Suite twice on the merged tree; flags OFF on the shipped law.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/constraints/cluster_pad.py`, `Ortho4XP/src/auto_patch_v2/constraints/pads.py`, `Ortho4XP/src/auto_patch_v2/airport/footprint_unit.py`, `Ortho4XP/src/auto_patch_v2/planar/overlay.py`, `Ortho4XP/src/auto_patch_v2/classify/evidence.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/solve/`, `Ortho4XP/src/auto_patch_v2/planar/wall_corridor_ramps.py`, `Ortho4XP/src/auto_patch_v2/planar/structures.py`, `Ortho4XP/src/auto_patch_v2/classify/roles.py`

## Spec (design-surface) §30 (4)

### §30 (4) THE CLUSTER PAD (owner RULINGS 2026-09-13bj; Fable 2026-09-13) — lane `v2clusterpad`

Owner: "it's acceptable to flatten large apron areas around big terminals if
needed to accommodate a large terminal cluster", as long as the grade laws
and the taxiways stay feasible.

4. **ONE PAD UNDER A TERMINAL CLUSTER.** Where the object stage's family
   census names a cluster (object spec §16f (7): footprint union over
   `cluster_pad_min_m2`), the design surface emits ONE `building` pad over
   the footprint union — one plane (the pad law, 1 %) — and the apron faces
   within `cluster_apron_reach_m` of it take that plane as their target
   where the apron caps allow; the reach stops at any taxiway family band
   (never moved). The pad's level is the pad law's (the median ground under
   the union, then the plane), published in the sidecar (`cluster_pads`) so
   the object stage seats the cluster on it. Feasibility is the solve's:
   where the reach cannot be met under the caps the report names the apron
   faces that stayed graded.

### §30 (4) MEASURED (lane `v2clusterpad`, 2026-09-13; branch `claude/v2clusterpad`)

**THE CONSUMER CENSUS (owner RULINGS 2026-08-30l), taken BEFORE any
consumer was edited.**  The change introduces ONE new region into the
layout — the CLUSTER, a set of emitted `building` faces priced as one
pad — and one new row family, the apron reach.  Every reader of a
`building` pad, of a pad frontage (§28), of the pad ceiling (§30), of
the apron trend, of the taxiway bands and of §16f's family census:

| pass / reader | what it reads | ruling |
|---|---|---|
| `pads._pad_groups` (per FACE: id, ref, rim) | the pad's vertex set | UNTOUCHED — it stays the per-face derivation every geometric reader below needs.  The cluster is a SECOND grouping, `pads._plane_groups`, read only by the rows that price a PLANE |
| `pads._pad_rows` → `pad_flats` / `pad_slope_ceiling` | the priced pairs | **EDITED** — priced over `_plane_groups`, so a cluster's faces are ONE plate and ONE hard 1 % ceiling.  This is §30 (4)'s "one plane" and the only place it is stated |
| `pads.pad_frontage_level` | the pad's own mean vs its frontage's leaders | **EDITED** — the LEVEL row is minted over the cluster's whole rim (one plane, one level fit); the frontage read itself (`_fronting`, `pad_frontage_leaders`) is per FACE and unchanged, so a cluster fits to every frontage its faces have, seniority unchanged |
| `pads._fronting` / `pad_frontage` / `pad_frontage_leaders` / `pad_shared` / `pad_fronts_airside` | per-face frontage relation | UNTOUCHED — a cluster fronts what its faces front |
| `pads.pad_datum_withdrawn` (§9b) | per-face fronting test | UNTOUCHED — per face; a cluster face that fronts nothing keeps its DEM datum, and the plate then carries it into the plane, which is what makes a cluster with one fronting face level to that frontage |
| `pads.frontage_near_miss` / `frontage_contacts` | pad polygons | UNTOUCHED — per face, geometric |
| `pad_frontage_gs.groundside_frontage_level` (§28) | `_pad_polys` + `pad_fronts_airside` | UNTOUCHED — per face; §28 states the face-follows-pad direction and the cluster does not change which pad a lot fronts |
| `pad_relief.pad_relief_offsets` (§11a (2)) | pad polygons + the groups' feet | UNTOUCHED — a per-VERTEX offset on the level plane; a cluster's plate carries it exactly as one pad's did |
| `no_step.pad_pavement_edges` / `pad_contacts` | pad-to-pavement edges | UNTOUCHED — per face and per edge |
| `constraints.ceiling` (`CEILING_RULING`, `LEVEL_RULING`) | the ruling HEADS | UNTOUCHED — the cluster's rows carry the same heads, so the hard set and the `[design] hard_rulings` / `pad_flat_rulings` pricing are unchanged.  The apron-reach row carries its OWN head and is named in NEITHER, so it is priced at the law's weight |
| `verify/pads.pad_flat` (`plane_residual`) | per-FACE flatness | UNTOUCHED, and it is the instrument that reports the cost: a cluster whose faces cannot make one plane reports its residual per face, exactly as §30 (4) asks ("the report names the apron faces that stayed graded") |
| `solve/design` §9b (`pad_datum_withdrawn`) | the withdrawn vertex set | UNTOUCHED (same call) |
| `apron.apron_within_shape` / `apron_edge_portions`, the apron caps | the apron's own hard rows | UNTOUCHED — the reach row is a TARGET at the law weight and every apron cap outranks it; where they disagree the apron stays graded and the residual is the report |
| the TAXIWAY family (`taxi_chain`, `taxi_centerlines`, `triangle_planes`, `taxi_box`, `junction_mesh`) | the taxi rows | UNTOUCHED and NEVER a follower of the reach: the reach's population excludes every vertex of a taxi- or runway-family face outright (§30 (4) "the reach stops at any taxiway family band") |
| `pipeline/publication` | the sidecar | **EDITED** — additive key `cluster_pads` (id, members, pad refs, level, area, the reach's population) |
| §16f's family census (`airport/placement_family`) | the object stage's own clusters | **EDITED** — `plan_clusters` is the SAME `_clusters` law read off the plan, so the design surface and the object stage cannot disagree about what one terminal is |

**THE DEVIATION, NAMED (§30 (4) says "one `building` pad over the
family's footprint union").**  What is emitted is the cluster's OWN pad
faces priced as one plane, not a new polygon over the union: no new face,
no new ref, no new shape class.  The union of the authored footprints is
already covered by those faces, and minting a synthetic outline would put
a new region into the planar map that every §28 / §30 / §20 consumer in
the table above would have to be censused against again.  Reported, not
decided.

### §30 (4) ROUND 2: THE MATCHED BASE BUILD (lane `v2clusterpad`, RULINGS 13bw (d))

Round 1's "before" was the registered `v2familyKCLTframe` graded document
and a full day of main lay between the arms.  Round 2 built the pair: ONE
TREE, ONE MAIN, ONE LAW VALUE — the base arm is this same branch with
`[placement] cluster_pad_min_m2 = 0` and `[design] cluster_apron_reach_m
= 0`, which is exactly what those keys' "0 disarms" clauses are for, and
is a stronger interventional arm than two checkouts.  Both foreground
through the harness, both `[guard] shared repo UNCHANGED`.

* DISARM — `v2cpKCLTdisarm`, rc 0, **491.7 s**, `body_sha 6cc83db0aa06`,
  ways 1,336, v2-verify rows **4,096**
* CLUSTER — `v2cpKCLTr2`, rc 0, **493.0 s**, `body_sha 5fb560ae50d0`,
  ways 1,335, v2-verify rows **4,033**

| bar | DISARM | CLUSTER |
|---|---|---|
| `building80` | 865 verts, 221.13 … 222.19, spread **1.06** | 221.09 … 222.17, spread **1.08** — the pad is NOT made less flat by the cluster (round 1's "+0.29 m worse" was the unmatched frame) |
| `building91` | **217.89** (flat) | **221.32** — LIFTED 3.43 m onto the terminal's plane |
| the cluster pad's union spread | **4.30 m** | **1.08 m** — MET |
| apron within the 60 m reach (70 vertices) | median \|apron − pad\| **0.25 m**, max 1.18, **0** within 0.05 | median **0.07 m**, max 1.18, **1** within 0.05 |
| **the TAXIWAY family, byte-identical** | 6,453 vertices | **NOT MET — 2,815 moved, worst 1.88 m, 1,320 over 0.05 m** |

**THE TAXI BAR IS MISSED AND THE MECHANISM IS NAMED.**  No taxi- or
runway-family vertex is ever a FOLLOWER of a reach row and none is in the
reach's population — both twinned, both exact.  The movement is the JOINT
SOLVE's: the reach lifts apron the taxi family is welded to through
§20's own no-step and trend rows, and those rows are senior to the
reach's.  1.88 m at a taxiway vertex is not a residual, it is the thing
the owner's own condition forbids ("as long as it remains feasible with
grade laws and taxiways"), so this is a STOP-and-report: the reach as
specified (60 m, at the law's weight, bounded only by the taxi band's own
vertices and its catchment) cannot hold the taxiways still, and what
gives — a shorter reach, a HARD ceiling on taxi movement, or the apron
between pad and taxiway staying graded — is the owner's to rule.

### §30 (4) ROUND 3 MEASURED (lane `v2clusterpad`; RULINGS 13cc) — THE REACH STILL MISSES, AND THE PLANE MERGE IS INERT

13cc's two amendments landed: (i) the reach's population now also strikes
every apron vertex a taxi-family NO-STEP row couples to a taxi vertex
(`no_step.no_step_edges`, the one derivation of that coupling), and (ii)
the reach's rows are priced at `[design] apron_trend` (30) through a new
`cluster_reach_rulings` weight class, an order below `law` (300).

THREE MATCHED KCLT ARMS, one tree, law values only, all `[guard] shared
repo UNCHANGED`:

| arm | law | wall | `body_sha` | verify rows |
|---|---|---|---|---|
| DISARM | pad 0, reach 0 | 374.7 s | `4da4d2811eee` | 4,066 |
| PAD-ONLY | pad 5000, reach 0 | 354.9 s | **`4da4d2811eee`** | 4,066 |
| CLUSTER | pad 5000, reach 60 | 407.3 s | `0b2caa790b47` | 4,001 |

| bar | DISARM | CLUSTER (13cc) | round 2 (at `law`) |
|---|---|---|---|
| taxi vertices moved (of 6,453) | — | **2,651** | 2,815 |
| worst taxi move | — | **1.45 m** | 1.88 m |
| taxi over 0.05 m | — | **1,133** | 1,320 |
| taxi over `hard_tol_m` 0.02 (the bar: 0) | — | **1,607 — MISSED** | — |
| cluster union spread (bar ≤ 1.5) | 4.30 m | **2.81 m — MISSED** | 1.08 m |
| `building91` | 217.89 | **219.37** | 221.32 |
| apron median \|dz\| in the reach | 0.24 | **0.25** | 0.07 |

**THE ATTRIBUTION, AND IT IS NOT WHAT THE SPEC ASSUMED.**  PAD-ONLY is
**byte-identical to DISARM** — the same graded document
(`bde3f0aff32e`) and the same patch (`47c91c99b599`).  So §30 (4)'s
PLANE MERGE, the thing the section is named for, changes NOTHING at KCLT
on its own: every metre of `building91`'s lift, every metre of apron
flattening AND every one of the 2,651 moved taxi vertices comes from the
APRON REACH alone.

**WHY THE MERGE IS INERT, MEASURED STATICALLY.**  `pads._pairs`
decimates a rim over `_MAX_PAIRWISE` (40) to `group[::step]` plus the
consecutive pairs.  For the merged cluster group (865 + 18 = 883
vertices, step 23) that prices **1,624 pairs of which only 40 CROSS
between the two faces** — and it costs `building91` its own plate,
whose 18 vertices go from 153 pairwise cap-0 rows to **17** consecutive
ones.  The merge therefore hands the small pad 40 weak cross links while
taking away nine tenths of its own rigidity.  That is a defect in the
merge, not in the ruling: `_pairs` must be per-FACE-complete and then
cross-linked, or the cluster must be priced by an explicit inter-face
basis.  NOT FIXED — the attempt cap for this round was spent on 13cc's
two amendments, and the fix needs its own arm.

**SO THE TAXI BAR IS STILL MISSED, AND THE LEVER IS NAMED.**  Weakening
the reach (13cc (ii)) moved the taxi numbers only 2,815 → 2,651 / 1.88 →
1.45 m while giving back most of the cluster pad's effect (union 1.08 →
2.81 m).  The reach is doing ALL the work and ALL the damage; the plane
merge is doing none of either.  A reach that cannot be weakened enough to
hold the taxiways without also giving up the terminal is the wrong lever,
and the right one is the merge the measurement above says is broken.

### §30 (4) ROUND 4 MEASURED — THE MERGE NOW WORKS, AND IT IS THE MERGE THAT MOVES THE TAXIWAYS

Two things landed, and only the second one mattered.

1. **`cluster_pairs`: per-face-complete plus cross-links.**  Each member
   face keeps exactly the pairs it would have alone (`_pairs`, per face)
   and the faces are tied by links from every decimated vertex of each
   junior face to its NEAREST vertex in the senior rim.  KCLT 865 + 18:
   `building91` gets its whole 153-pair plate back (was 17 under the
   concatenated rim) and **18 CROSS-LINKS** (was 40 weak crossings).
2. **CLUSTERS SHARING A FACE ARE ONE PLANE — this was the real defect.**
   `plane_groups` gave a face to whichever cluster `setdefault` saw
   first.  KCLT's two terminal rows BOTH stand on `building80`, so
   `unit:30#0` took it whole and `unit:31#0` was left holding
   `building91`'s 18 vertices ALONE — a "cluster" of one face with
   nothing to cross-link to.  **The built sidecar said so all along**:
   `cluster_pads` read `unit:31#0 pads [building80, building91] rim 18`.
   That, and not the `_pairs` decimation, is why the PAD-ONLY arm came
   out byte-identical to DISARM twice.  Clusters are now unioned over
   the faces they share.

**THE THREE ARMS** (one tree, law values only; the reach is DISARMED at 0
in both, RULINGS 13ce).  DISARM `v2cpKCLTd4` (`bde3f0aff32e`) against
PAD-ONLY `v2cpKCLTp5` (`3ad63ed931f6`) — the graded documents now DIFFER,
which is the round's first bar:

| bar | DISARM | PAD-ONLY (round 4) | round 3 |
|---|---|---|---|
| the merge does work | — | **graded docs differ** — MET | byte-identical |
| `building91` | 217.89 | **221.52** (bar 221.3) — MET | 217.89 |
| cluster union spread (bar ≤ 1.5) | 4.30 m | **1.07 m** — MET | 4.30 |
| `building80` flatness (bar ≤ 1.08) | 1.07 m | **1.07 m** — MET | 1.07 |
| apron median \|dz\| in 60 m, reach OFF | 0.24 | **0.25** (max 1.18, 0 of 70 within 0.05) | 0.24 |
| **taxi family (bar ≤ 0.02, 0 over 0.05)** | — | **2,406 moved, worst 2.07 m, 1,525 over 0.02, 1,074 over 0.05 — MISSED** | 0 |

**THE CONFLICT, NAMED.**  The reach is off in both arms, so this taxi
movement is the MERGE's own: lifting `building91` 3.63 m onto the
terminal plane propagates through the pad's frontage and no-step welds
into the taxi family, worst 2.07 m.  The owner's two conditions — "these
large complex structures have to be seated as a unit" and "as long as it
remains feasible with grade laws and taxiways" — are in direct conflict
at KCLT, and the thing they meet on is a 20 x 25 m pad inside the
terminal footprint standing 3.6 m below its floor.  Round 3 read this as
the reach's fault; with the reach disarmed and the merge working, it is
the cluster plane itself.  **STOP-and-report: nothing further is armed,
and the branch should not merge on the taxi numbers alone.**

**THE APRON, WITH THE REACH OFF.**  Median \|dz\| 0.25 m, 0 of 70
vertices within 0.05 — the merge alone does NOT flatten the stands, so
the "if needed" clause is still unmet.  A SHORT reach (≤ 20 m at
`apron_trend`) is the obvious next lever and is deliberately NOT armed:
the taxi family already misses its bar without it.
### §30 (4) (5) THE CLUSTER PAD YIELDS TO THE TAXIWAY (Fable 2026-09-13; RULINGS 2026-09-13ch, owner 13bj) — lane `v2clusterpad` round 5

Round 4 (eb169be7) made the merge work and measured its price: lifting KCLT's
`building91` 3.63 m onto the terminal floor moves 2,406 taxi-family vertices
(worst 2.07 m) through the pad's frontage and no-step welds, with the apron
reach off. The owner's own clause decides it.

5. A member pad whose merge onto the cluster plane would move any
   taxi-family vertex by more than `hard_tol_m` KEEPS ITS OWN PLANE
   (reported with the pad, the taxi vertices and the metres); the cluster
   plane is the plurality pad's, the unit datum is unchanged, and every
   object on the yielding pad is still seated on the floor by §16g (5). The
   gate is decided at generator time from the pad's coupling to the taxi
   family (the lane measures which coupling carries the movement), never by
   a post-hoc revert. The apron reach stays disarmed.

BARS: KCLT PAD-ONLY == DISARM by the GATE (the report names `building91`
as yielding, the taxi vertices and 2.07 m); taxi family byte-identical;
`building91` 217.89; passengers on the floor (§16g (5) rows unchanged); a
synthetic twin where a cluster with no taxi coupling merges (union spread →
0) and one where it yields; OTHH plan stage re-timed (`--runs 3`, quiet
machine); suite twice.

### §30 (4) (5) MEASURED (lane `v2clusterpad` round 5; RULINGS 13ch)

**13ch (i)'s PREMISE IS REFUTED, AND THE GATE MOVED TO WHERE THE DEFECT
IS.**  The ruling asked the lane to measure which coupling carries round
4's 2.07 m and to gate on it.  Measured, on the round-4 arms:

* `building91` shares **NO vertex** with `building80`, with any apron
  face or with any taxi face — its 18 vertices belong to its own face and
  nothing else;
* it fronts nothing: the nearest pavement of any kind is **80.35 m** away
  against a `[design] pad_frontage_m` of **3.0 m**;
* the taxi vertices that move are not near it — the six worst stand
  **2,192 … 2,218 m** from it (1,816 … 1,841 m from `building80`); the
  nearest moved taxi vertex is 431 m away and **none** is within 200 m.

There is no coupling to gate on: the movement is a field-wide shift of
the solve, not a local transmission.  What `building91` IS, is a separate
building **65.81 m from the terminal** that the cluster's coarse PART-BOX
union happened to intersect — §16g (2)'s undone item (b), the
box-versus-polygon reading, reaching the design surface.  §30 (4)'s own
words are "one pad over the family's FOOTPRINT UNION", and a pad 66 m
outside the union is not in it.

**THE GATE AS BUILT** (`cluster_pad._touching_component`, generator time,
no post-hoc revert): of the faces the footprint union intersects, the
cluster's plane covers the CONNECTED COMPONENT — pads within
`[placement] footprint_touch_m` (0.5 m) of each other, the same chain the
footprint unit itself is built on — that holds the largest face.  Every
other intersected face KEEPS ITS OWN PLANE, is collected in
`cluster_pad.YIELDED` and named per cluster in the sidecar's
`cluster_pads` as `yielded_pads`.

**THE THREE ARMS** (one tree, law values only; the reach disarmed in both):

| bar | DISARM `v2cpKCLTd4` | PAD-ONLY `v2cpKCLTp6` |
|---|---|---|
| graded document | `bde3f0aff32e` | **`bde3f0aff32e` — BYTE-IDENTICAL, MET** |
| taxi family | 6,453 verts | **0 moved, worst 0.0000 m — MET** |
| `building91` | 217.89 | **217.89 — MET** (it yields; the report names it) |
| the cluster's plane | — | `building80` alone, median 221.46, spread 1.07 |
| union spread | 4.30 m | 4.30 m — by the GATE, not by failure |
| §16g (5) rows | — | **unchanged**: 11,314 multi-anchor rows, 5,263 in a unit, 4,896 `OBJECT_MSL`, 6,336 on ground, **0 dropped**; the passengers and seats at 35.2191877, −80.9426007 at **225.46** = `building80`'s 221.46 + their authored 4.00 m — on the floor |

**WHAT THE GATE COSTS, NAMED.**  KCLT's cluster now has ONE member face,
so round 4's `cluster_pairs` (per-face-complete + cross-links) and the
shared-face union have NO effect at this airport — they are exercised by
the twins and will act at an airport whose terminal really does span two
touching pads.  Round 4's union-spread bar (4.30 → 1.07) is therefore
WITHDRAWN here: it was measuring the lift of a building that does not
belong to the terminal.

### §30 (4) THE CLUSTER PAD (owner RULINGS 2026-09-13bj; Fable 2026-09-13) — lane `v2clusterpad`

Owner: "it's acceptable to flatten large apron areas around big terminals if
needed to accommodate a large terminal cluster", as long as the grade laws
and the taxiways stay feasible.

4. **ONE PAD UNDER A TERMINAL CLUSTER.** Where the object stage's family
   census names a cluster (object spec §16f (7): footprint union over
   `cluster_pad_min_m2`), the design surface emits ONE `building` pad over
   the footprint union — one plane (the pad law, 1 %) — and the apron faces
   within `cluster_apron_reach_m` of it take that plane as their target
   where the apron caps allow; the reach stops at any taxiway family band
   (never moved). The pad's level is the pad law's (the median ground under
   the union, then the plane), published in the sidecar (`cluster_pads`) so
   the object stage seats the cluster on it. Feasibility is the solve's:
   where the reach cannot be met under the caps the report names the apron
   faces that stayed graded.

### §30 (4) MEASURED (lane `v2clusterpad`, 2026-09-13; branch `claude/v2clusterpad`)

**THE CONSUMER CENSUS (owner RULINGS 2026-08-30l), taken BEFORE any
consumer was edited.**  The change introduces ONE new region into the
layout — the CLUSTER, a set of emitted `building` faces priced as one
pad — and one new row family, the apron reach.  Every reader of a
`building` pad, of a pad frontage (§28), of the pad ceiling (§30), of
the apron trend, of the taxiway bands and of §16f's family census:

| pass / reader | what it reads | ruling |
|---|---|---|
| `pads._pad_groups` (per FACE: id, ref, rim) | the pad's vertex set | UNTOUCHED — it stays the per-face derivation every geometric reader below needs.  The cluster is a SECOND grouping, `pads._plane_groups`, read only by the rows that price a PLANE |
| `pads._pad_rows` → `pad_flats` / `pad_slope_ceiling` | the priced pairs | **EDITED** — priced over `_plane_groups`, so a cluster's faces are ONE plate and ONE hard 1 % ceiling.  This is §30 (4)'s "one plane" and the only place it is stated |
| `pads.pad_frontage_level` | the pad's own mean vs its frontage's leaders | **EDITED** — the LEVEL row is minted over the cluster's whole rim (one plane, one level fit); the frontage read itself (`_fronting`, `pad_frontage_leaders`) is per FACE and unchanged, so a cluster fits to every frontage its faces have, seniority unchanged |
| `pads._fronting` / `pad_frontage` / `pad_frontage_leaders` / `pad_shared` / `pad_fronts_airside` | per-face frontage relation | UNTOUCHED — a cluster fronts what its faces front |
| `pads.pad_datum_withdrawn` (§9b) | per-face fronting test | UNTOUCHED — per face; a cluster face that fronts nothing keeps its DEM datum, and the plate then carries it into the plane, which is what makes a cluster with one fronting face level to that frontage |
| `pads.frontage_near_miss` / `frontage_contacts` | pad polygons | UNTOUCHED — per face, geometric |
| `pad_frontage_gs.groundside_frontage_level` (§28) | `_pad_polys` + `pad_fronts_airside` | UNTOUCHED — per face; §28 states the face-follows-pad direction and the cluster does not change which pad a lot fronts |
| `pad_relief.pad_relief_offsets` (§11a (2)) | pad polygons + the groups' feet | UNTOUCHED — a per-VERTEX offset on the level plane; a cluster's plate carries it exactly as one pad's did |
| `no_step.pad_pavement_edges` / `pad_contacts` | pad-to-pavement edges | UNTOUCHED — per face and per edge |
| `constraints.ceiling` (`CEILING_RULING`, `LEVEL_RULING`) | the ruling HEADS | UNTOUCHED — the cluster's rows carry the same heads, so the hard set and the `[design] hard_rulings` / `pad_flat_rulings` pricing are unchanged.  The apron-reach row carries its OWN head and is named in NEITHER, so it is priced at the law's weight |
| `verify/pads.pad_flat` (`plane_residual`) | per-FACE flatness | UNTOUCHED, and it is the instrument that reports the cost: a cluster whose faces cannot make one plane reports its residual per face, exactly as §30 (4) asks ("the report names the apron faces that stayed graded") |
| `solve/design` §9b (`pad_datum_withdrawn`) | the withdrawn vertex set | UNTOUCHED (same call) |
| `apron.apron_within_shape` / `apron_edge_portions`, the apron caps | the apron's own hard rows | UNTOUCHED — the reach row is a TARGET at the law weight and every apron cap outranks it; where they disagree the apron stays graded and the residual is the report |
| the TAXIWAY family (`taxi_chain`, `taxi_centerlines`, `triangle_planes`, `taxi_box`, `junction_mesh`) | the taxi rows | UNTOUCHED and NEVER a follower of the reach: the reach's population excludes every vertex of a taxi- or runway-family face outright (§30 (4) "the reach stops at any taxiway family band") |
| `pipeline/publication` | the sidecar | **EDITED** — additive key `cluster_pads` (id, members, pad refs, level, area, the reach's population) |
| §16f's family census (`airport/placement_family`) | the object stage's own clusters | **EDITED** — `plan_clusters` is the SAME `_clusters` law read off the plan, so the design surface and the object stage cannot disagree about what one terminal is |

**THE DEVIATION, NAMED (§30 (4) says "one `building` pad over the
family's footprint union").**  What is emitted is the cluster's OWN pad
faces priced as one plane, not a new polygon over the union: no new face,
no new ref, no new shape class.  The union of the authored footprints is
already covered by those faces, and minting a synthetic outline would put
a new region into the planar map that every §28 / §30 / §20 consumer in
the table above would have to be censused against again.  Reported, not
decided.

### §30 (4) ROUND 2: THE MATCHED BASE BUILD (lane `v2clusterpad`, RULINGS 13bw (d))

Round 1's "before" was the registered `v2familyKCLTframe` graded document
and a full day of main lay between the arms.  Round 2 built the pair: ONE
TREE, ONE MAIN, ONE LAW VALUE — the base arm is this same branch with
`[placement] cluster_pad_min_m2 = 0` and `[design] cluster_apron_reach_m
= 0`, which is exactly what those keys' "0 disarms" clauses are for, and
is a stronger interventional arm than two checkouts.  Both foreground
through the harness, both `[guard] shared repo UNCHANGED`.

* DISARM — `v2cpKCLTdisarm`, rc 0, **491.7 s**, `body_sha 6cc83db0aa06`,
  ways 1,336, v2-verify rows **4,096**
* CLUSTER — `v2cpKCLTr2`, rc 0, **493.0 s**, `body_sha 5fb560ae50d0`,
  ways 1,335, v2-verify rows **4,033**

| bar | DISARM | CLUSTER |
|---|---|---|
| `building80` | 865 verts, 221.13 … 222.19, spread **1.06** | 221.09 … 222.17, spread **1.08** — the pad is NOT made less flat by the cluster (round 1's "+0.29 m worse" was the unmatched frame) |
| `building91` | **217.89** (flat) | **221.32** — LIFTED 3.43 m onto the terminal's plane |
| the cluster pad's union spread | **4.30 m** | **1.08 m** — MET |
| apron within the 60 m reach (70 vertices) | median \|apron − pad\| **0.25 m**, max 1.18, **0** within 0.05 | median **0.07 m**, max 1.18, **1** within 0.05 |
| **the TAXIWAY family, byte-identical** | 6,453 vertices | **NOT MET — 2,815 moved, worst 1.88 m, 1,320 over 0.05 m** |

**THE TAXI BAR IS MISSED AND THE MECHANISM IS NAMED.**  No taxi- or
runway-family vertex is ever a FOLLOWER of a reach row and none is in the
reach's population — both twinned, both exact.  The movement is the JOINT
SOLVE's: the reach lifts apron the taxi family is welded to through
§20's own no-step and trend rows, and those rows are senior to the
reach's.  1.88 m at a taxiway vertex is not a residual, it is the thing
the owner's own condition forbids ("as long as it remains feasible with
grade laws and taxiways"), so this is a STOP-and-report: the reach as
specified (60 m, at the law's weight, bounded only by the taxi band's own
vertices and its catchment) cannot hold the taxiways still, and what
gives — a shorter reach, a HARD ceiling on taxi movement, or the apron
between pad and taxiway staying graded — is the owner's to rule.

### §30 (4) ROUND 3 MEASURED (lane `v2clusterpad`; RULINGS 13cc) — THE REACH STILL MISSES, AND THE PLANE MERGE IS INERT

13cc's two amendments landed: (i) the reach's population now also strikes
every apron vertex a taxi-family NO-STEP row couples to a taxi vertex
(`no_step.no_step_edges`, the one derivation of that coupling), and (ii)
the reach's rows are priced at `[design] apron_trend` (30) through a new
`cluster_reach_rulings` weight class, an order below `law` (300).

THREE MATCHED KCLT ARMS, one tree, law values only, all `[guard] shared
repo UNCHANGED`:

| arm | law | wall | `body_sha` | verify rows |
|---|---|---|---|---|
| DISARM | pad 0, reach 0 | 374.7 s | `4da4d2811eee` | 4,066 |
| PAD-ONLY | pad 5000, reach 0 | 354.9 s | **`4da4d2811eee`** | 4,066 |
| CLUSTER | pad 5000, reach 60 | 407.3 s | `0b2caa790b47` | 4,001 |

| bar | DISARM | CLUSTER (13cc) | round 2 (at `law`) |
|---|---|---|---|
| taxi vertices moved (of 6,453) | — | **2,651** | 2,815 |
| worst taxi move | — | **1.45 m** | 1.88 m |
| taxi over 0.05 m | — | **1,133** | 1,320 |
| taxi over `hard_tol_m` 0.02 (the bar: 0) | — | **1,607 — MISSED** | — |
| cluster union spread (bar ≤ 1.5) | 4.30 m | **2.81 m — MISSED** | 1.08 m |
| `building91` | 217.89 | **219.37** | 221.32 |
| apron median \|dz\| in the reach | 0.24 | **0.25** | 0.07 |

**THE ATTRIBUTION, AND IT IS NOT WHAT THE SPEC ASSUMED.**  PAD-ONLY is
**byte-identical to DISARM** — the same graded document
(`bde3f0aff32e`) and the same patch (`47c91c99b599`).  So §30 (4)'s
PLANE MERGE, the thing the section is named for, changes NOTHING at KCLT
on its own: every metre of `building91`'s lift, every metre of apron
flattening AND every one of the 2,651 moved taxi vertices comes from the
APRON REACH alone.

**WHY THE MERGE IS INERT, MEASURED STATICALLY.**  `pads._pairs`
decimates a rim over `_MAX_PAIRWISE` (40) to `group[::step]` plus the
consecutive pairs.  For the merged cluster group (865 + 18 = 883
vertices, step 23) that prices **1,624 pairs of which only 40 CROSS
between the two faces** — and it costs `building91` its own plate,
whose 18 vertices go from 153 pairwise cap-0 rows to **17** consecutive
ones.  The merge therefore hands the small pad 40 weak cross links while
taking away nine tenths of its own rigidity.  That is a defect in the
merge, not in the ruling: `_pairs` must be per-FACE-complete and then
cross-linked, or the cluster must be priced by an explicit inter-face
basis.  NOT FIXED — the attempt cap for this round was spent on 13cc's
two amendments, and the fix needs its own arm.

**SO THE TAXI BAR IS STILL MISSED, AND THE LEVER IS NAMED.**  Weakening
the reach (13cc (ii)) moved the taxi numbers only 2,815 → 2,651 / 1.88 →
1.45 m while giving back most of the cluster pad's effect (union 1.08 →
2.81 m).  The reach is doing ALL the work and ALL the damage; the plane
merge is doing none of either.  A reach that cannot be weakened enough to
hold the taxiways without also giving up the terminal is the wrong lever,
and the right one is the merge the measurement above says is broken.

### §30 (4) ROUND 4 MEASURED — THE MERGE NOW WORKS, AND IT IS THE MERGE THAT MOVES THE TAXIWAYS

Two things landed, and only the second one mattered.

1. **`cluster_pairs`: per-face-complete plus cross-links.**  Each member
   face keeps exactly the pairs it would have alone (`_pairs`, per face)
   and the faces are tied by links from every decimated vertex of each
   junior face to its NEAREST vertex in the senior rim.  KCLT 865 + 18:
   `building91` gets its whole 153-pair plate back (was 17 under the
   concatenated rim) and **18 CROSS-LINKS** (was 40 weak crossings).
2. **CLUSTERS SHARING A FACE ARE ONE PLANE — this was the real defect.**
   `plane_groups` gave a face to whichever cluster `setdefault` saw
   first.  KCLT's two terminal rows BOTH stand on `building80`, so
   `unit:30#0` took it whole and `unit:31#0` was left holding
   `building91`'s 18 vertices ALONE — a "cluster" of one face with
   nothing to cross-link to.  **The built sidecar said so all along**:
   `cluster_pads` read `unit:31#0 pads [building80, building91] rim 18`.
   That, and not the `_pairs` decimation, is why the PAD-ONLY arm came
   out byte-identical to DISARM twice.  Clusters are now unioned over
   the faces they share.

**THE THREE ARMS** (one tree, law values only; the reach is DISARMED at 0
in both, RULINGS 13ce).  DISARM `v2cpKCLTd4` (`bde3f0aff32e`) against
PAD-ONLY `v2cpKCLTp5` (`3ad63ed931f6`) — the graded documents now DIFFER,
which is the round's first bar:

| bar | DISARM | PAD-ONLY (round 4) | round 3 |
|---|---|---|---|
| the merge does work | — | **graded docs differ** — MET | byte-identical |
| `building91` | 217.89 | **221.52** (bar 221.3) — MET | 217.89 |
| cluster union spread (bar ≤ 1.5) | 4.30 m | **1.07 m** — MET | 4.30 |
| `building80` flatness (bar ≤ 1.08) | 1.07 m | **1.07 m** — MET | 1.07 |
| apron median \|dz\| in 60 m, reach OFF | 0.24 | **0.25** (max 1.18, 0 of 70 within 0.05) | 0.24 |
| **taxi family (bar ≤ 0.02, 0 over 0.05)** | — | **2,406 moved, worst 2.07 m, 1,525 over 0.02, 1,074 over 0.05 — MISSED** | 0 |

**THE CONFLICT, NAMED.**  The reach is off in both arms, so this taxi
movement is the MERGE's own: lifting `building91` 3.63 m onto the
terminal plane propagates through the pad's frontage and no-step welds
into the taxi family, worst 2.07 m.  The owner's two conditions — "these
large complex structures have to be seated as a unit" and "as long as it
remains feasible with grade laws and taxiways" — are in direct conflict
at KCLT, and the thing they meet on is a 20 x 25 m pad inside the
terminal footprint standing 3.6 m below its floor.  Round 3 read this as
the reach's fault; with the reach disarmed and the merge working, it is
the cluster plane itself.  **STOP-and-report: nothing further is armed,
and the branch should not merge on the taxi numbers alone.**

**THE APRON, WITH THE REACH OFF.**  Median \|dz\| 0.25 m, 0 of 70
vertices within 0.05 — the merge alone does NOT flatten the stands, so
the "if needed" clause is still unmet.  A SHORT reach (≤ 20 m at
`apron_trend`) is the obvious next lever and is deliberately NOT armed:
the taxi family already misses its bar without it.
### §30 (4) (5) THE CLUSTER PAD YIELDS TO THE TAXIWAY (Fable 2026-09-13; RULINGS 2026-09-13ch, owner 13bj) — lane `v2clusterpad` round 5

Round 4 (eb169be7) made the merge work and measured its price: lifting KCLT's
`building91` 3.63 m onto the terminal floor moves 2,406 taxi-family vertices
(worst 2.07 m) through the pad's frontage and no-step welds, with the apron
reach off. The owner's own clause decides it.

5. A member pad whose merge onto the cluster plane would move any
   taxi-family vertex by more than `hard_tol_m` KEEPS ITS OWN PLANE
   (reported with the pad, the taxi vertices and the metres); the cluster
   plane is the plurality pad's, the unit datum is unchanged, and every
   object on the yielding pad is still seated on the floor by §16g (5). The
   gate is decided at generator time from the pad's coupling to the taxi
   family (the lane measures which coupling carries the movement), never by
   a post-hoc revert. The apron reach stays disarmed.

BARS: KCLT PAD-ONLY == DISARM by the GATE (the report names `building91`
as yielding, the taxi vertices and 2.07 m); taxi family byte-identical;
`building91` 217.89; passengers on the floor (§16g (5) rows unchanged); a
synthetic twin where a cluster with no taxi coupling merges (union spread →
0) and one where it yields; OTHH plan stage re-timed (`--runs 3`, quiet
machine); suite twice.

### §30 (4) (5) MEASURED (lane `v2clusterpad` round 5; RULINGS 13ch)

**13ch (i)'s PREMISE IS REFUTED, AND THE GATE MOVED TO WHERE THE DEFECT
IS.**  The ruling asked the lane to measure which coupling carries round
4's 2.07 m and to gate on it.  Measured, on the round-4 arms:

* `building91` shares **NO vertex** with `building80`, with any apron
  face or with any taxi face — its 18 vertices belong to its own face and
  nothing else;
* it fronts nothing: the nearest pavement of any kind is **80.35 m** away
  against a `[design] pad_frontage_m` of **3.0 m**;
* the taxi vertices that move are not near it — the six worst stand
  **2,192 … 2,218 m** from it (1,816 … 1,841 m from `building80`); the
  nearest moved taxi vertex is 431 m away and **none** is within 200 m.

There is no coupling to gate on: the movement is a field-wide shift of
the solve, not a local transmission.  What `building91` IS, is a separate
building **65.81 m from the terminal** that the cluster's coarse PART-BOX
union happened to intersect — §16g (2)'s undone item (b), the
box-versus-polygon reading, reaching the design surface.  §30 (4)'s own
words are "one pad over the family's FOOTPRINT UNION", and a pad 66 m
outside the union is not in it.

**THE GATE AS BUILT** (`cluster_pad._touching_component`, generator time,
no post-hoc revert): of the faces the footprint union intersects, the
cluster's plane covers the CONNECTED COMPONENT — pads within
`[placement] footprint_touch_m` (0.5 m) of each other, the same chain the
footprint unit itself is built on — that holds the largest face.  Every
other intersected face KEEPS ITS OWN PLANE, is collected in
`cluster_pad.YIELDED` and named per cluster in the sidecar's
`cluster_pads` as `yielded_pads`.

**THE THREE ARMS** (one tree, law values only; the reach disarmed in both):

| bar | DISARM `v2cpKCLTd4` | PAD-ONLY `v2cpKCLTp6` |
|---|---|---|
| graded document | `bde3f0aff32e` | **`bde3f0aff32e` — BYTE-IDENTICAL, MET** |
| taxi family | 6,453 verts | **0 moved, worst 0.0000 m — MET** |
| `building91` | 217.89 | **217.89 — MET** (it yields; the report names it) |
| the cluster's plane | — | `building80` alone, median 221.46, spread 1.07 |
| union spread | 4.30 m | 4.30 m — by the GATE, not by failure |
| §16g (5) rows | — | **unchanged**: 11,314 multi-anchor rows, 5,263 in a unit, 4,896 `OBJECT_MSL`, 6,336 on ground, **0 dropped**; the passengers and seats at 35.2191877, −80.9426007 at **225.46** = `building80`'s 221.46 + their authored 4.00 m — on the floor |

**WHAT THE GATE COSTS, NAMED.**  KCLT's cluster now has ONE member face,
so round 4's `cluster_pairs` (per-face-complete + cross-links) and the
shared-face union have NO effect at this airport — they are exercised by
the twins and will act at an airport whose terminal really does span two
touching pads.  Round 4's union-spread bar (4.30 → 1.07) is therefore
WITHDRAWN here: it was measuring the lift of a building that does not
belong to the terminal.

## Spec (object-placement) §16g (10)

### §16g (10) (4)–(5) WHAT CHAINS, AND A DERIVED PAD NEVER TAKES AIRSIDE GROUND (Fable 2026-09-14; RULINGS 2026-09-14ah) — lane `v2padcluster`

MEASURED (lane r2, HECA): with pads derived from clusters as hard flat
regions, 502,561 m² of new pad (94,795 m² from apron) moved 13,637 of
21,534 airside vertices (runway 1,110, worst 4.38 m) and put the terminal at
+10.83 m; the T3 district stayed ONE cluster of 9,334 bodies / 541,200 m²
because its footed bodies genuinely touch through the authored ground
slabs.

4. WHAT CHAINS.  Only WALLED bodies link a cluster.  A thin body — floor
   slab, plate, deck, canopy, road, apron object; solid height <
   `chain_min_height_m` (2.5 m), or classed deck/plate/pavement by the
   object stage — is a LEAF: seated on its own ground or carrier, never a
   link between two walled bodies.
5. A DERIVED PAD NEVER TAKES AIRSIDE GROUND.  The pad polygon is the
   cluster's outline clipped by every airside face; a cluster wholly on
   airside pavement gets no pad.  A cluster whose outline is in more than
   one piece is SPLIT at the pieces (each a cluster with its own pad).

BARS: HECA airside vertices moved > 0.02 m = 0; the terminal at 30.1279552,
31.403143 at its pad 72.50; `pad_cluster_mismatch` 0; the T3 district
resolved into its buildings (count, largest cluster's area named);
constraints ≤ +10 %; KCLT BUILD with outlines — `building80` 221.44 ± 0.02
and the terminal's members' seats unchanged; SPJC 19.56 dry.

### §16g (10) (6) A PAD SHARING AN EDGE WITH AIRSIDE WELDS TO IT (owner RULINGS 2026-09-14ai) — lane `v2padcluster`

A `building` pad that shares an edge with an airside face takes the airside
face's solved level along that edge — no step — and its plane meets it
within the pad's own slope cap; the airside is the datum (airside is king),
the pad never pulls it.  A pad that cannot meet its airside edge within cap
is `pad_airside_weld` (CRITICAL), never a terrace step.  The cluster seated
on such a pad follows the welded level.  BAR: every airside-sharing pad at
HECA and KCLT welded (step along the shared edge ≤ `hard_tol_m`), named with
its airside face.

### §16g (10) (7)–(8) LEAVES GET NO PAD; A PAD BENDS TO THE AIRSIDE AT ITS RIM (Fable 2026-09-14; RULINGS 2026-09-14aj) — lane `v2padcluster`

MEASURED (r3): (4)/(5) hold, yet 345,016 m² of new hard-flat pad beside the
apron moved 17,482 airside vertices — a shared vertex is one unknown.  A
derived pad cannot be (a) one hard plane, (b) welded to the apron along its
rim and (c) forbidden to move the apron all at once.
7. A derived pad is minted for a WALLED cluster only; a leaf (slab, plate,
   deck, canopy, road; §16g (10) (4)) seats on its own ground and mints no
   pad.
8. (a) is dropped AT THE RIM: a pad is flat (cap 0) across its interior and
   non-airside rim; along an airside-sharing edge its rim vertices are
   one-way followers of the airside (airside leads), and the plate meets
   them within the pad's slope ceiling (1 %) — a bent skirt, never a step.
   Twins asserting a two-sided cap-0 plate at an airside edge are re-founded.
BARS: HECA airside moved 0; the terminal body on its walled cluster's pad
within 0.02 m, the pad within 1 % of the airside it touches, its cut/fill vs
the disarmed ground named; `pad_cluster_mismatch` 0; `pad_airside_weld` 0;
constraints ≤ +10 %; KCLT build at the final tree (the terminal pad's weld
named); SPJC build carrying heights (19.56 ± 0.02).

### §16g (10) (8) REFINED — RIGID CORE, ONE-WAY SKIRT (Fable 2026-09-14; RULINGS 2026-09-14al) — lane `v2padcluster`

MEASURED (r4): a whole-plate one-way form leaves the plate no rigid
relation and it collapses; a two-sided ceiling row on the airside-sharing
pairs holds the plate but still pulls 14,263 airside vertices (worst 4.55
m).  So: the pad's vertices farther than `pad_skirt_m` (25 m) from any
airside-sharing edge form a cap-0 RIGID CORE; the SKIRT BAND within
`pad_skirt_m` follows the airside ONE-WAY within the pad slope ceiling —
the airside leads and is never pulled; the core stays a plate.  BARS: HECA
airside moved > 0.02 m = 0; the terminal at its pad (72.60); `pad_airside_
weld` 0 or each named; KCLT `building80` weld re-read; SPJC viaduct re-read.

### §16g (10) (4)–(6) MEASURED, ROUND 3 (lane `v2padcluster`, 2026-09-14; branch `claude/v2padcluster`)

**WHAT CARRIES THE T3 CHAIN, MEASURED FIRST (the round's first order).**
Per body of the largest cluster (`unit:43`, 9,334 bodies / 9,333 touch
edges), how many cluster edges pass through it:

| resource | edges | parts | solid extent | `base_y` | area |
|---|---|---|---|---|---|
| `T3_4.obj` | **1,822** | 1 | **0.00 m** | 15.73 | 1,161 m² |
| `T3_4.obj` | **1,772** | 1 | **0.00 m** | 15.73 | 1,161 m² |
| `metal_titles.obj` | 1,531 | 58 | 23.51 m | 3.73 | 25,477 m² |
| `Plastic.obj` | 1,165 | 238 | 22.07 m | 6.09 | 18,553 m² |
| `floor.obj` | 996 | 12 | 6.53 m | −0.63 | 14,415 m² |
| `door.obj` | 468 | 1 | 0.00 m | −0.46 | 589 m² |
| `concrete_3.obj` | 219 | 1 | 0.00 m | −1.84 | 17,383 m² |
| `strip_concrete.obj` | 41 | 1 | 0.00 m | −0.17 | 1,289 m² |

Two single-component CEILING PLATES carry **3,594 of the district's
9,333 edges** between them; six `T3_4.obj` bodies carry 3,598 endpoints,
`black_glass.obj` contributes 366 bodies all at extent 0.00, and
`concrete_3.obj` is 13cs's 17,383 m² ground slab.  **The district is held
together by its floor and its ceiling**, exactly as 14ah read it.

**THE ARMS.**  DISARM `v2padclusterHECAdisarm` (`97a2267cfc28`, 462.1 s)
against LANE `v2padclusterHECA4` (`cbefb8edcacb`, 384.4 s, ledger
`72fb36419b42`), both `[guard] shared repo UNCHANGED`.  `v2padclusterHECA3`
is byte-identical in its design surface (same `body_sha`) — the object-
stage half of (4) moves no vertex, which is itself the proof that the
unit rule and the cluster rule are separable.

| bar | DISARM | round 2 | round 3 | verdict |
|---|---|---|---|---|
| clusters | — | 1,954 | **4,278** | — |
| largest cluster over the pad threshold | — | 541,200 m² / 9,334 bodies | **171,086 m² / 1 body** | **(4) MET — the T3 district is resolved** |
| `pad_cluster_mismatch` (bar 0) | 33 | 44 | **27** | MISSED |
| `pad_airside_weld` (bar 0, new) | 16 | — | **24** | MISSED, and WORSE |
| **airside vertices moved > 0.02 m (bar 0)** | — | 13,637 of 21,534 | **17,482 of 29,465, worst 12.15 m; the runway 856 of 3,426, worst 3.14 m** | **MISSED** |
| `building` pad area | 867,173 m² | 1,369,935 | **1,212,189** | the clip gave 157,746 m² back |
| apron area | 2,935,484 m² | 2,841,363 | **3,012,902** | **(5) MET — the pads no longer eat the apron** |
| the terminal 30.1279552 31.403143, SURFACE (bar 72.50) | 72.07 | 82.90 | **80.94** | MISSED |
| the terminal's BODY off its own ground | — | `T3_49 b4` +7.66 m | **`T3_49 b3` +0.15 m, WITHIN 0.3** | **MET — it left the 52-member unit** |
| constraints stage (bar ≤ +10 %) | 83.46 s | +57 % | **129.67 s, +55 %** | MISSED |
| law-true census total | 62,116 | — | **77,288** | reported |
| suite | | | 1,475 passed, twice | MET |

**(5) WORKS ON THE MAP AND NOT ON THE SOLVE, AND THAT IS THE ROUND'S
FINDING.**  Clipping the pads out of airside did what it says: the apron
GAINS 77,418 m² instead of losing 94,795, and no pad overlaps a runway or
a taxiway.  The airside still moves 17,482 vertices.  The mechanism is
not overlap — it is the WELD: 345,016 m² of new hard-flat pad now sits
BESIDE the apron along its whole perimeter, and a shared vertex is ONE
unknown (09-01g, contact = value), so the pad's flat rows and the apron's
own rows are peers at every boundary node.  Clipping moved the conflict
from the interior to the edge; it did not remove it.

**(6) AS A CONSTRAINT WAS ATTEMPTED TWICE AND BOTH FORMS ARE REFUTED BY
MEASUREMENT.**  14ai's sentence — "the airside is the datum, the pad
never pulls it" — has two implementations and this lane measured both:

1. WITHDRAW the shared vertices from the pad's flat plate.  The pad then
   has no plate at its rim and loses its own law: the §30 twin's pad
   tilted to **2.6 % against a 1 % HARD ceiling**, and a pad between two
   pavements half a percent apart stopped being flat.  Narrowing the
   withdrawal to the cap-0 target and leaving the 1 % ceiling the whole
   rim did not save it (4 ruled twins still red).
2. Make those rows ONE-WAY with the airside vertex as LEADER (09-10l's
   own shape, a new head in `one_way_rulings` + `pad_flat_rulings`).
   **13 ruled twins go red**, including the plate's own two-sidedness
   (§30 "every rim pair priced, contacts included") and §28's frontage
   direction.

Both are rewrites of laws this lane does not own, so NEITHER SHIPPED.
What shipped is (6)'s CENSUS — `pad_airside_weld`, CRITICAL, computed
from the patch by node identity — and it reads **16 pads at DISARM and 24
with the derived pads**.  The step ACROSS a welded edge is 0 by
construction and is not what it measures; what it measures is the pad
pulled out of plane at the edge, which is the thing the owner's sentence
forbids and which is now visible for the first time.

**THE CONFLICT, STATED ONCE.**  A derived pad is (a) one hard plane, (b)
welded to the apron along its whole rim, and (c) forbidden to move the
apron.  Any two of the three can hold; all three cannot, and the three
are §30's pad law, 09-01g's weld and 14ai's airside datum respectively.
**STOP-and-report: nothing further is armed.**  The lever the owner must
choose among: drop (a) for pads that share an airside edge (the pad
becomes a level, not a plane, at that edge — and its 1 % ceiling with
it); drop (b) (a derived pad stands OFF the apron by a declared joint,
§23, and shares no vertex); or drop (c) and accept a bounded airside
movement with a stated cap.

**KCLT, AND THE REF IS NOT A HANDLE.**  `v2padclusterKCLT3` (rc 0,
274.2 s, `d19ae4797bc4`, guard UNCHANGED; no ledger key — the tree moved
during the run).  Read BY COORDINATE at 13bo's own site (35.2191877,
−80.9426007), because `building{N}` is an ORDINAL and the derived pads
renumber every later one: the terminal pad is **221.46 → 220.56 m**
(−0.90), 865 → 483 vertices, spread 1.07 → 0.51.  The bar was unchanged
within `hard_tol_m`: **MISSED by 0.90 m**, and the members' seats follow
it.  `building80` as a REF now names a 16-vertex pad elsewhere — quoting
it across these arms would have reported 3.77 m of pure renumbering.

**SPJC IS INERT AND SAYS SO.**  The registered frame
(`SPJC_20260913T214930`) carries no `Part.height_m`, so (4) stands down
by its own clause and the units are byte-identical — 4 units, `fu:0:0`
with 484 bodies / 24 members including `xp11_007` and `xp11_010`.  The
19.56 viaduct is untouched BY CONSTRUCTION, not by measurement; an SPJC
build carrying heights is OWED, as is a KCLT one at the final tree.

### §16g (10) (7)–(8) MEASURED, ROUND 4 (lane `v2padcluster`, 2026-09-14; branch `claude/v2padcluster`)

**THE ARMS.**  DISARM `v2padclusterHECAdisarm` (`97a2267cfc28`) against
LANE `v2padclusterHECA5` (rc 0, 420.6 s, `1112755a1db9`, ledger
`85c18b3071e6`); KCLT `v2padclusterKCLT4` (rc 0, 259.0 s, `2fa924a012cc`,
ledger `dca6d7449633`); SPJC `v2padclusterSPJC4` (rc 0, 82.1 s,
`7f9b9659d13c`, no ledger — 23 external-candidate deltas in the window,
another lane's).  All four `[guard] shared repo UNCHANGED`.  Suite
**1,474 passed / 1 skipped, twice**.

**(7) LEAVES GET NO PAD, MEASURED.**  Of HECA's 1,380,739 m² of cluster
outline, **359,152 m² in 1,518 pads are LEAVES** (no walled body) and
**175,708 m² in 821 more are walled but under `cluster_pad_min_m2`** —
together **39 %** of the pad area that sat beside the apron.  The emitted
pad area falls 1,212,189 → **1,091,467 m²** (DISARM 867,173).  The same
population is used by `classify` (which mints) and by the census (which
judges), so the mismatch family can never report a cluster that was never
given a pad.

| bar | DISARM | round 3 | **round 4** | verdict |
|---|---|---|---|---|
| **airside moved > 0.02 m (bar 0)** | — | 17,482 of 29,465, worst 12.15 m | **14,263 of 29,783, worst 4.55 m** | MISSED, worst −63 % |
| the RUNWAY alone | — | 856 of 3,426, worst 3.14 m | **1,021 of 3,426, worst 0.41 m** | worst −87 % |
| terminal 30.1279552 31.403143, SURFACE (bar 72.50) | 72.07 | 80.94 | **72.60** | **MET (+0.10)** |
| the terminal BODY | — | on `building11`, own ground +7.50 m | **`T3_concrete_white b4` on WALLED cluster pad `building298` at 72.62 via `fu:38:96@cluster_pad` (18 members), own ground +0.08 m; `metal b8` +0.05, worst foot +0.21 WITHIN 0.3** | ~MET (0.08 vs the 0.02 bar) |
| the terminal pad's CUT/FILL vs the DISARM ground | 72.07 | +8.87 | **+0.55 m of FILL**, cluster `fu:38:96@cluster_pad`, pad `building298` | named |
| `pad_cluster_mismatch` (bar 0) | 33 | 27 | **14** | MISSED |
| `pad_airside_weld` (bar 0) | **3** (worst 0.085 m) | — | **16** (worst 1.135 m, `building4 → pav1` over 51.5 m) | MISSED |
| constraints (bar ≤ +10 %) | 83.46 s | +55 % | **96.57 s, +15.7 %** | MISSED |
| law-true census total | 62,103 | 77,288 (+24 %) | **63,904 (+2.9 %)** | reported |

**WHERE THE CONSTRAINT COST GOES.**  `pad_flats` itself is 10.6 → **2.5
s** (the skirt prices fewer cap-0 pairs), and the LP is SMALLER than
round 3's (245,680 → 212,368 rows, 34,448 → 32,872 columns).  What
remains is the pad population: 823,018 → **838,816** `diffs`, i.e. 15,798
more difference rows over 1,091,467 m² of pad against 867,173.  The
residual +15.7 % is the price of the pads themselves, not of (8).

**(8)'s ONE-WAY CLAUSE IS REFUTED BY MEASUREMENT, AND ONLY THAT CLAUSE.**
14aj asks for the airside-sharing rim vertices to be ONE-WAY FOLLOWERS.
Built that way, a plate whose every binding is one-way has no rigid
relation to anything in the first lag round and does not chase back: the
§30 twin's pad collapsed from **703.56 to 640.89 m**.  09-10l's one-way
precedent is a LEVEL row — a mean against a leader band — which leaves
the PLATE holding the pad rigid; a whole plate one-way leaves nothing.
What shipped is the rest of (8): a pair with an end the pad shares with
airside is priced at the pad's own **slope ceiling** instead of the cap-0
flat target, so the pad is flat across its interior and its non-airside
rim and BENDS to meet the pavement it touches.  HECA: **8,967 skirt
rows**, 0 pairs dropped, **30 pads wholly inside pavement** kept their
two-sided plate (the OSM pad-in-an-apron class, which the skirt would
leave with no law at all).  That alone took the airside's worst move from
12.15 m to 4.55 m and the runway's from 3.14 to 0.41.

**THE TWINS, RE-FOUNDED AND NAMED (14aj's own instruction).**

| twin | asserted | now asserts |
|---|---|---|
| `test_constraints::test_strip_families_and_pads` | a cap-0 `Diff` over EVERY rim pair at `pad_flat` | the cap set is `{0, pad_slope_max}`; every ceiling-capped FLAT row has an airside end and every cap-0 row has none; the ceiling pass is still one row per pair over the whole rim (the ROW SET is unchanged) |
| `test_v2padlevel::test_a_pad_between_two_pavements_..._tiers_neither` | the pad's MEAN lies between its two frontages | the pad MEETS each frontage (a shared vertex IS that pavement's vertex, 09-01g) and its tilt stays inside the 1 % ceiling.  The bracket only ever held because a flat plate pinned at both edges must sit between them |
| `test_v2frontage::test_the_only_channel_left_is_the_two_way_apron_edge_ramp_law` | the two-way apron-edge ramp moves the pad < 0.05 m | the same claim, re-measured at **0.172 m**: a looser pad, the same channel, still downward, still the ramp's |
| `test_v2clusterpad` / `test_v2padcluster` fixtures | a cluster with no `walled` count | `_Cl` / `_Cluster` carry `walled`, because (7) drops a leaf |
| `verify.census.NOT_IMPLEMENTED` | — | gains `pad_cluster_mismatch` / `pad_airside_weld`: both are the CENSUS's and `verify` has no reader, so the lockstep twin must not expect one (CYXY v1 read 7 weld rows against v2's 0) |
| `test_v2padcluster::…pad_airside_weld…` | a least-squares plane residual against `hard_tol_m` | the SHARED vertex against its own pad's other vertices at `pad_slope_max·d`.  The first reading measured the bend (8) ALLOWS — HECA read 16 rows at DISARM and 36 with the skirt, the instrument counting the law working.  At the cap: DISARM **3**, LANE **16** |

**KCLT, AND THE −0.53 m IS THE WELD, NAMED.**  The terminal pad at
13bo's own coordinate (35.2191877, −80.9426007) is `building80`, 850
vertices, median **221.46 → 220.93** (round 3: 220.56), spread 1.07 →
**3.77**.  It shares **743 nodes with the apron `pav14`** (z 220.04 …
223.81) and 51 more with `pav118` — so the step across the weld is 0 by
construction and the pad's 3.77 m spread IS the apron's own fall across
the edge it is welded to.  The bar (unchanged within `hard_tol_m`) is
MISSED by 0.53 m and the movement is the weld's, which is what 14aj said
would make it lawful — **the owner's read is the acceptance.**  `pad_
airside_weld` 25 rows, worst `building80 → pav14` **1.384 m over 11.6 m**:
the pad could not reach that edge even bending at 1 %.

**SPJC, BUILT WITH HEIGHTS, AND THE VIADUCT MOVES.**  `xp11_007__b0` is
on pad `building7` at **20.07** in unit `fu:0:3@cluster_pad` of **6
members** — 13df's reading was **19.5604** in `fu:0:0@cluster_pad` of 24.
The leaf rule split the 24-member unit into 6 and the derived pad stands
0.51 m above it: **MISSED by 0.51 m**, and `building7` is also SPJC's
worst weld row (0.970 m over 20.0 m against `pav46`).

**THE SEVEN HECA BUILDINGS, AS FAR AS THE IDENTITIES REACH.**  A body
INDEX is as unstable as a pad ref — the cut renumbers bodies exactly as
the derived pads renumber `building{N}` — so only the bodies whose index
survived both arms can be quoted: `T3_38 b1` (14g's 160) `fu:43:7386@
cluster_pad` of 20 members on `building53` at 98.02, own ground **−6.70 →
+0.04 m** on `building160` in a 2-member unit; `T3_38 b4` (170) own
ground −0.02 → **−0.02**, WITHIN 0.3 both arms; `T3_38 b3` (147) median
ground 93.18 worst −2.45 → `building168` at 90.62, own ground −0.01,
worst **−0.33**.  `building_texture_4 b7/b8` and `building_texture_3
b29/b31` do not exist under those indices in either arm and were NOT
read.

**STOP-and-report.**  Three bars moved a long way (the terminal is MET,
the runway's worst move is 0.41 m, the cost is +15.7 %) and three are
still missed — airside 14,263, `pad_cluster_mismatch` 14,
`pad_airside_weld` 16.  The remaining airside movement is no longer the
pad pulling its own edge: it is the pad's SKIRT, bending at up to 1 %
over hundreds of metres, plus the 30 pads that keep a two-sided plate.
The lever the owner must choose among is now narrow: (i) a skirt WIDTH —
the bend is allowed only within N metres of the shared edge and the pad
is flat beyond it; (ii) the one-way form with a RIGID SEED (the plate
keeps a cap-0 core over its non-airside vertices and only the skirt band
follows), which is the form that did not collapse in the twin; or (iii)
accept a bounded airside movement with the 0.41 m runway figure as the
stated cap.

### §16g (10) (8) REFINED — MEASURED, ROUND 5 (lane `v2padcluster`, 2026-09-14; branch `claude/v2padcluster`)

**THREE ARMS, ONE TREE, LAW VALUES ONLY**, all against DISARM
`v2padclusterHECAdisarm`, all `[guard] shared repo UNCHANGED`:

| arm | `pad_skirt_m` | wall | `body_sha` | ledger |
|---|---|---|---|---|
| round 4's scope (the shared vertices) | — | 420.6 s | `1112755a1db9` | `85c18b3071e6` |
| **the 25 m BAND** | 25.0 | 433.5 s | `ee7d0f56911c` | `b63e49fd65b0` |
| **SHIPPED** (band 0 = the shared vertices, + 14al's withdrawal) | 0.0 | 451.5 s | `18e51b7d084e` | `a602bba1b858` |

| bar | DISARM | r4 scope | 25 m BAND | **SHIPPED** |
|---|---|---|---|---|
| airside moved > 0.02 m, of 21,523 (bar 0) | — | 10,048 | 10,683 | **9,573** |
| worst airside move | — | 4.55 m | 4.52 m | 4.55 m |
| **the RUNWAY** | — | 1,021, worst 0.410 | 1,394, worst 0.570 | **885, worst 0.390** |
| `pad_airside_weld` (bar 0) | 3 (worst 0.085) | 16 (worst 1.135) | 21 (worst 2.42) | **29 (worst 1.135)** |
| `pad_cluster_mismatch` (bar 0) | 33 | 14 | 14 | **14** |
| law-true census | 62,103 | 63,904 | 66,771 | **64,844** |
| the terminal body on `building298` | — | 72.62, +0.08 m | 72.62, +0.00 m | **72.60, +0.07 m** |
| constraints (bar ≤ +20 %) | 83.46 s | 96.57 (+15.7 %) | 102.43 (+22.7 %) | **109.69 (+31.4 %)** |

**14al's ONE-WAY CLAUSE IS REFUTED FOR THE THIRD TIME, ON A THIRD
SCOPE.**  14al adds the cap-0 rigid core precisely so round 4's collapse
cannot recur, and it does not recur — with a core the pad holds.  It is
still not STABLE: built with the band following the airside one-way,
§28's own frontage row — which its twin proves moves NOTHING — moved the
pad **0.12 m**, and at CYXY the census and the engine's verify came apart
on `mid_edge_step` (**77 against 14**), i.e. the lag leaves residuals the
two readers do not share.  A one-way row is LAGGED; a pad bound to the
airside only by lagged rows has nothing holding it inside a round.
09-10l's precedent is ONE level row per pad against a leader band, with
the plate still rigid underneath — a whole band of them is a different
thing.  The band therefore ships TWO-SIDED at the pad's slope ceiling.

**AND THE 25 m WIDTH IS REFUTED BY MEASUREMENT TOO.**  It is WORSE on
every airside bar — airside 10,048 → 10,683, the runway 1,021 → 1,394 and
its worst 0.410 → 0.570 m, `pad_airside_weld` 16 → 21 and its worst 1.135
→ 2.42 m, law-true 63,904 → 66,771 — and buys only the terminal body
+0.08 → +0.00 m.  A wider band softens more of the pad, and a softer pad
moves more of the apron inside the same ceiling.  `pad_skirt_m` keeps
25.0 as its documented design value and **ships at 0**, which is NOT "no
skirt" but the airside-SHARED vertices alone.

**WHAT 14al DID BUY, AND IT IS THE BEST ARM.**  Its other half — WITHDRAW
the two-sided ceiling row over a pair of two airside-shared vertices —
is what the shipped arm adds to round 4, and it is worth **4,008 dropped
pairs**: airside 10,048 → **9,573**, the runway 1,021 → **885** and its
worst 0.410 → **0.390 m**, law-true 66,771 → 64,844.  The pad no longer
has any two-sided row between two vertices the airside already owns.
Counters published per build: `pad_flats.airside_skirt_rows` 4,959,
`both_skirt_dropped` 4,008, `pads_core_only` 74, `pads_wholly_in_the_band`
**30** — those 30 are the pads with no plate left (the OSM
pad-in-an-apron class), which keep their two-sided plate; at the 25 m
band that count is 55 and is the answer to "how many pads are skirt
only".

**THE 14 `pad_cluster_mismatch` ROWS, ATTRIBUTED — ONE CLASS.**  12
`cluster_spans_pads` + 2 `pad_spans_clusters`, and every one is the SAME
defect: **the cluster piece and the emitted pad ref are cut in different
places.**  The cluster is cut by `geom.cluster_outlines` (the closed
outline's connected components, then the airside clip — which is why the
ids carry `/k`: `unit:43#16/0`, `/1`, `/3`), and the pad ref is cut again
downstream by `classify/evidence._pads` (the runway difference, the
boundary gate, `min_area`, §22.2's skirt drop, and the separately-unioned
FALLBACK footprints, one of which landing inside a cluster piece splits
it).  `building19` is claimed by `unit:43#16/0` AND `/1` — two pieces of
ONE cluster over one pad, the two cutters disagreeing about where the cut
is.  TO REACH 0: a cluster piece must be minted as ONE part and never
re-cut — `_pads` must not subdivide it, and a fallback footprint landing
inside one must be absorbed rather than mint its own ref.  NOT ARMED
(the round's attempts are spent).

**THE COST, NAMED.**  Constraints 83.46 → **109.69 s (+31.4 %)**, over
the +20 % the round accepted.  It is not the skirt: `pad_flats` runs in
2.6 s and the LP is SMALLER than round 3's (222,546 rows against
245,680).  It is the PAD POPULATION — 823,018 → **830,023** `diffs` over
1,091,467 m² of derived pad against DISARM's 867,173 — plus the per-pad
band walk, which is O(rim × shared) per pad and is the one piece of this
round's own work in the number.

**KCLT AND SPJC STAND ON THEIR ROUND-4 FRAMES.**  The one-way skirt is
not in the shipped law, so nothing it would have changed there was built;
the two-sided withdrawal changes the design surface, so the KCLT weld
(the terminal pad 221.46 → 220.93, 743 nodes shared with apron `pav14`)
and the SPJC viaduct (20.07 on `building7` in a 6-member unit against
13df's 19.56) are as round 4 measured them and were NOT re-built this
round — **owed**.

### §16g (10) (8) AMENDED — THE SKIRT YIELDS, NEVER THE AIRSIDE (Fable 2026-09-14; RULINGS 2026-09-14au)

MEASURED (lane v2settle): with the airside fixed, 143 `building_pad airside
skirt` rows at KCLT (26.4 m of shortfall) and 1,428 conforming rows at HECA
under §20b are INFEASIBLE BY LAW — a welded pad's 1 % ceiling and a fixed
apron rim cannot both hold.  RULING: the pad's skirt band takes whatever
slope the weld requires up to `pad_skirt_max_slope` (5 %) — a slope, never a
step; the core stays a cap-0 plate; the airside never moves.  Beyond 5 % the
pad is `pad_airside_weld` (CRITICAL).  BAR: KCLT's 143 infeasible skirt rows
→ 0 with each pad's skirt slope named; HECA's certificate re-read.

### §16g (10) (9) A PAD BETWEEN APRONS SLOPES WITH THEM; THE BUILDING SEATS AT THE LOW SIDE (owner RULINGS 2026-09-14ay/az; supersedes (8))

1. A pad touching an apron takes the apron's level along the shared edge;
   the apron within `cluster_apron_reach_m` (40 m, re-armed, bounded to the
   touching component, never across a taxi-family face) joins the pad's
   plane (§30 (4)); no skirt.
2. A pad sharing edges with apron on more than one side is a plane sloping
   up to 1 % between them (the apron law's own cap — always feasible, since
   the aprons across that span hold it); the cluster's datum is the pad's
   LOWEST shared-edge level: nothing floats, the high side is buried by at
   most 1 % × the span.
3. `pad_airside_weld` (CRITICAL) fires only for a shared edge with a
   non-apron airside face that cannot be met.
BARS: KCLT 143 / HECA 124 infeasible skirt rows → 0 (each pad named: the
apron area flattened within the reach, or its slope and low-side seat);
the reach never crosses a taxiway; airside moved vs pads-OFF = the
flattened apron area only.

## RULINGS

## 2026-09-14bg The v2padvert c9787d1e merge REVERTED (d21b407c): on main it fails 14 twins — the very set the lane reported red only at its HEAD (skirt withdrawal collateral: `test_v2smooth`, `test_why`, chord/ridge/shapes/ground/frontage/padlevel, `test_v2bank` pad twins, `test_m3b`, `taxi_route_pairs`, `test_v2clusterpad` §30 (4))

The lane reported c9787d1e green 1,524 twice; merged into main
11f373f0 the suite reads 14 failed / 1,503 passed. Either the shas
were mislabeled in the report or the lane's suite ran on a different
tree; not attributed — the merge is reverted and main is green again
(1,516). `suite-failure-named-by-narrative` applies: a merge is
proved by the suite ON MAIN before the RULINGS entry, never by the
lane's number. The clip work (14bf) is on `claude/v2padvert` and
re-lands through lane `v2padjoin`, whose FIRST bar is the suite green
on a merge of main.

## 2026-09-14bf v2padvert round 2: the arrangement-level clip MERGED (c9787d1e, ships OFF: HECA 280/88 → 44/26, KCLT 0/3); the re-armed reach as a weak preference REGRESSES (KCLT 313 → 1,308 infeasible) — ruled: the reach is a PLANE JOIN; lane `v2padjoin`

Lane `v2padvert` @ 99d795ef (HEAD not mergeable — 20 twins red; the
mergeable state c9787d1e merged). `planar/overlay.airside_clip` clips
every rigid region out of the `rolled_on_roles` faces (runway + taxi
+ airside apron; a groundside lot never clips a pad) with the rim
snap; `classify/roles` no longer differences the airside region by
the pad union at all. HECA gone/new 280/88 → 44/26 (the 26 new are
0.02–0.36 m off the boundary — the identity grid's snap-rounding; the
un-tried lever: the rim carries the CELL boundary, not the breakline
sources noded into airside edges), KCLT 0/3, apron faces equal; the
two ruled twins green with no exemption; a pad wholly on airside is
KEPT (§30 / 14ai's class). HECA build pair (pads+staged+clip ON vs
OFF): airside nodes 39 gone / 27 new, 2,978 of 16,058 moved > 0.02
(worst 3.88 m apron; runway 358, worst 0.27) — the vertex SET fixed,
the VALUES still move because the pad's rows pull the apron. 14ay/az
built: the skirt withdrawn, `cluster_apron_reach_m` 40 re-armed with
the touching-component bound, (9)(2) behind `pad_between_aprons`
(off): the certificate WORSENS (KCLT 313 → 1,308 rows / 732 m; HECA
124 → 794 / 571) — the reach is a ONE-WAY TARGET at law weight: the
apron PREFERS the pad's plane and yields to every hard cap before it;
the pad's cap-0 plate is welded to an apron that never came. 20
twins red: 10 encode the withdrawn skirt, 9 assert no pad law
(`test_v2smooth` active set, `test_why` relax arms, chord/ridge/
shapes/ground) — the collateral the skirt was holding back.

* RULING §30 (4) row form: within the reach the apron vertices are
  BOUND INTO the pad's plate (a plane JOIN — equality rows at hard
  weight, the same plate rows the pad's own vertices carry), not a
  preference; bounded to the touching component, never across a
  taxi-family face; beyond the reach the apron returns to its own law.
  With the join the pad and its apron collar are ONE plate and the
  skirt is unnecessary by construction. (9)(2)'s two-run plane and
  the low-side datum stay as ruled.
* Lane `v2padjoin` (fresh): the join at `constraints/cluster_pad.py`
  (§30 (4)'s row site), the datum at the pad's lowest shared edge,
  the 9 no-pad-law twins re-read (which encode the skirt's
  collateral, which a real regression); bars: KCLT/HECA certificate
  → 0 infeasible (each pad named with its collar area), airside moved
  vs OFF = the collar only, the terminal at its pad, suite green.
* The two HECA builds `/tmp/harness/v2padvertHECAon/off.osm` are
  registered by the next lane as the pair.

## 2026-09-14az Owner: a pad between aprons at different levels slopes at ≤ 1 % to match them, and the building seats at the LOW side — §16g (10) (9)

Owner, verbatim: "If two sides of a pad are legitimately surrounded by
apron at different levels, it can't be more than 1%, since that's
apron law, so we allow the pad to slope at 1% to match the apron, and
seat the building level at the low side so nothing floats and the
high side is slightly buried. Make sense?"

* RULING §16g (10) (9): a `building` pad sharing edges with apron on
  more than one side takes each apron's level along each shared edge
  (step 0) and is a plane SLOPING up to 1 % between them — the apron
  law's own cap, which the aprons across that span already satisfy,
  so the pad plane is always feasible at 1 % (a difference larger than
  1 % across the pad is an APRON violation, priced on the aprons, never
  a pad step). The cluster seated on that pad takes its datum at the
  pad's LOWEST shared-edge level: nothing floats, the high side is
  slightly buried (≤ 1 % × the pad's span). `pad_airside_weld` fires
  only where a shared edge cannot be met at all (a non-apron airside
  step). This closes 14ay's "pad between two aprons" CRITICAL case.
* Lane `v2padvert` r2 amended: the pad plane between apron edges at
  ≤ 1 %; the cluster datum = the pad's lowest edge; bar: the KCLT/HECA
  pads between two aprons named with slope and the low-side seat;
  `pad_airside_weld` 0 except a non-apron airside step.

## 2026-09-14ay Owner: "If a pad is close enough to touch an apron, then it should be set at the same elevation, therefore it should not require more than even 1% slope right?" — right; the 5 % skirt is an artefact of a rigid plane meeting a CURVED apron edge; the mechanism is the cluster pad's APRON REACH (re-armed), not a skirt

Why 5 % appeared: a `building` pad is ONE PLANE (cap 0 inside its 1 %
ceiling) while a long apron edge under 1 % still CURVES with the
terrain — KCLT `building80` shares 743 nodes with `pav14` over 3.77 m
of fall; no tilted plane can meet a curved edge exactly, so the
difference had to go somewhere: a skirt (14al/14au) or an infeasible
row (v2settle's certificate). The owner is right that touching means
the same elevation. Then the APRON must be planar where it meets the
pad — which is exactly §30 (4)'s cluster-pad APRON REACH ("it's
acceptable to flatten large apron areas around big terminals", owner
2026-09-13 KCLT item 1) that 13ce DISARMED (`cluster_apron_reach_m =
0.0`) when the reach was measured swallowing whole aprons.

* RULING §16g (10) (8) SUPERSEDED — NO SKIRT: a pad sharing an edge
  with an apron takes the apron's level along the shared edge (step
  0) and stays one plane within its 1 % ceiling; the APRON within
  `cluster_apron_reach_m` of that pad joins the pad's plane (the
  cluster pad reach, RE-ARMED at 40 m, bounded to the touching
  component §30 (5) and never crossing a taxi-family face); beyond the
  reach the apron returns to its own law within its 1 % cap. Airside
  is king stands: the reach is the APRON LAW's own flattening at a
  terminal, ruled by the owner on 2026-09-13, not a pull by the pad.
  `pad_skirt_max_slope` is WITHDRAWN (5 % skirts never ship);
  `pad_airside_weld` fires where even the reach cannot meet (a pad
  between two aprons at different levels — a real step, CRITICAL).
* Lane `v2padvert` r2 amended: arm the reach at 40 m in the pads-ON
  arm; bar: KCLT's 143 / HECA's 124 infeasible skirt rows → 0 with the
  apron re-flattened within the reach, named per pad; the reach never
  crosses a taxiway.

## 2026-09-14au v2settle MERGED: the "unsettled hard set" was mostly CONSTANT rows (footed on pins, no column) and the projection's own 0.02 bar; the real residual is 6 rows / 0.0445 m, NAMED and certified FEASIBLE; shipped patches byte-identical; the stage-2 certificate PROVES the conforming side infeasible by law — ruled: the pad's skirt yields

Lane `v2settle` @ b129f97d (fresh HECA + KCLT captures registered;
suite 1,515 twice). HECA stage 1's 33 unsettled rows: 9 `road_ramp`
ceilings footed on a `Pin` with NO column (constants — `assemble`
tested only `dem_fixed`; 142 such rows; phase C pinned `best_worst`
on a constant it could never beat and RETURNED ROUND 1's ITERATE), 6
`runway_profile` at 0.0200000 (the projection's own held bar), 18
real (`pavement_ceiling` 11, `pads` 7, worst 0.1025). Fixed:
`_carries_a_column` on the REDUCED row; one settle derivation
(`hard_exceeds`/`HARD_READ_EPS`); §20a's named hard failure with a
min-Σ-slack FEASIBILITY CERTIFICATE (`read_hard_failure`); `v2_solve_
replay --why-hard-stage`. After: HECA stage 1 6 rows / 0.0445 m, all
named, certificate FEASIBLE (a solve residual, not the law); shipped
single-solve patches BYTE-IDENTICAL at HECA and KCLT; KCLT's 406
survivors: 143 PROVED an infeasible set (26.4 m over 179 columns, all
`building_pad airside skirt` at 35.2097, −80.9327); §20b stage 2 at
HECA: 1,428 of 2,548 survivors proved infeasible, 1,015.6 m. 13db's
shared `shift` REFUTED as the limit (0 rows both hard and one-way).
Not met: the last 6 rows (both levers refuted, 12u/13ac; the
un-built candidate is a per-family post-solve projection for
`pavement_ceiling`, §30 (3)'s pattern); KCLT's lag 0.317 m.

* RULING (the intent question "which row yields when a welded pad's
  1 % ceiling and a fixed apron rim cannot both hold"): the AIRSIDE
  never yields; the PAD's flatness yields — its skirt band's slope
  ceiling relaxes from 1 % up to `pad_skirt_max_slope` (5 %) as the
  weld requires (a slope, never a step: the owner's "weld smoothly");
  only beyond 5 % is it `pad_airside_weld` CRITICAL. §16g (10) (8)
  amended accordingly; lane `v2padvert`'s successor (or the same
  lane) applies it in `constraints/pads.py` with the KCLT 143-row set
  as the bar (→ 0 infeasible, each pad's skirt slope named).

## 2026-09-14as v2staged + v2padcluster MERGED with BOTH mechanisms OFF (`pad_from_cluster = false`, `staged_solve = false`): main's surface is byte-unchanged; the airside is not yet invariant under pads — two prerequisites named

Lane `v2staged` @ 65351424 (on `claude/v2padcluster` a3185dbb; HECA
arms `v2stagedHECAoff` = r5's shipped `18e51b7d084e` and the staged
FINAL `266b56b5a358`; suite 1,502 twice on the branch, 1,495 on main
with the three padcluster twins arming the flag themselves). §20b
built: stage 1 = the airside pavement problem alone (runway/taxi/apron
from the law, its own polish and projections), stage 2 = everything
with every airside column SUBSTITUTED as a constant (a ±tol box would
mint ~40 k hard rows); (1b) a row with a `follows` or a conformance
head is never stage 1's even when all-airside (a welded pad's skirt
rows between two apron vertices — 9,936 moved with the rule as
written); (1c) a stage triangulates only its own faces (the bending
stencil never leaves the stage). Measured: airside moved vs DISARM
8,976 (OFF) → 10,371 (staged) — NOT the coupling: 405 moved vertices
over a kilometre from any pad; (a) the pad derivation CHANGES THE
AIRSIDE PROBLEM (268 airside vertices gone, 93 new, 844 → 841 apron
faces; the body datum and 2-D trend refit) and (b) the airside solve
is UNSETTLED (stage 1 alone: 42 of 161,690 hard rows, max 0.18 m — 13y
(B)/13ab), so a perturbed problem lands on a different optimum. The
conforming side pays (`pads` 4 → 199, `road_ramp` 15 → 48) because
airside cannot yield a centimetre — which §20b forbids. Stage clocks
90.3 + 5.5 = 95.8 s vs 117.9 single (0.81×). Terminal 72.60 → 73.05.

* RULING: both ship OFF. The airside becomes invariant under pads
  only when (i) THE PAD DERIVATION LEAVES THE AIRSIDE VERTEX SET ALONE
  — a pad clipped by airside shares the airside's EXISTING vertices
  and adds none; the body datum / 2-D trend are fitted on airside
  alone (the pads never enter the fit) — and (ii) the airside solve
  SETTLES (13y (B)/13ab — the standing first-ranked debt: 42 unsettled
  hard rows at HECA). Then staged ON gives identity by construction.
  Two lanes, in that order, before 1.0.335 arms pads at HECA.
* Deviations recorded for the spec author: §23.3 (the airside sheet
  borrowing the ground's datum across the stencil) is false under §20b
  at the sheet's edge (valley fixture +2.68 → −3.92; HECA inert); a
  welded pad's 1 % ceiling is unreachable under §20b (the two-sided
  row 14al withdrew can return, since under §20b it cannot pull).
* The OTHH customer line is untouched: OTHH on main = 1.0.334's
  surface (both flags off).

## 2026-09-13ce — v2clusterpad ROUND 3 MERGED (273ce491, lane 04c4bfa6) WITH THE REACH DISARMED: the taxi bar MISSED again under 13cc's two amendments (the no-step-coupled apron excluded from the population; the rows at `apron_trend` 30 via a new `cluster_reach_rulings` weight class): taxi vertices moved 2,815 → 2,651, worst 1.88 → 1.45 m, 1,607 over `hard_tol_m` (bar 0); cluster union spread 1.08 → 2.81 (bar ≤ 1.5 MISSED); `building91` 219.37; apron median |dz| 0.25. THE ATTRIBUTION (three matched one-tree KCLT arms): PAD-ONLY (pad 5,000, reach 0) is BYTE-IDENTICAL to DISARM (`4da4d2811eee` both, graded `bde3f0aff32e`, patch `47c91c99b599`) — THE PLANE MERGE CHANGES NOTHING AT KCLT ON ITS OWN; every metre of flattening and every moved taxi vertex is the REACH's. Why the merge is inert (static): `pads._pairs` decimates a rim over `_MAX_PAIRWISE` (40) — the merged 883-vertex cluster group prices 1,624 pairs of which only 40 CROSS the two faces, and `building91` LOSES ITS OWN PLATE (153 pairwise cap-0 rows → 17 consecutive ones): the merge hands the small pad 40 weak cross links while removing nine tenths of its rigidity — a defect in the merge, not in the ruling. So the reach is the WRONG LEVER and the right one is broken. RULED (Fable): 1.0.328 ships with `cluster_apron_reach_m = 0.0` (DISARMED by law value — PAD-ONLY == DISARM byte-identical, so no taxi movement and no regression) and carries the passengers fix (§16g (5)); ROUND 4 on the same lane: fix `_pairs` for a cluster group (per-face-complete pairs + explicit cross-links between the faces), re-measure the three arms; if the merge then does the work (union spread ≤ 1.5, `building91` on the plane, taxi ≤ 0.02) the reach stays off or comes back short; `building91`'s lift is then the merge's. ALSO LANDED: `obj8_split_report --write-pack` built its OWN `PlacementPlan` and never called `msl_seats_for_dump` — the write half was silently DROPPING every §16g (5) row (first run: "0 rows still carry an elevation" on a run that owed 4,846); fixed to make the same call `build_plan` makes; KCLT round trip: 640 cut files, DSF rewritten, round trip OK, torn seams 0, duplicate rows 0, 11,992 placements read back, 4,872 rows carry an elevation — all written by §16g (5), the terminal's `sala_*` rows at 225.44 / 225.64 (`cluster_pad` + offset). THE PLAN-WIDE GRID REFUTED AND DELETED (OTHH `plan_units` grid 557.5 s vs sweep 485.7 s, identical clusters; the cost is `bodies_of_plan` and the part-box product in `_bind`, not the pairing) — OTHH's plan stage stands at ~809 s vs 249 pre-plan-wide: OWED to round 4 with the `_pairs` fix (the profiling-round item). `Bridge_02` / `Bridge_03` 1.52 / 1.93 named. Suite: next line. `docs/frames.jsonl` committed from the main tree again (lanes' `frames.py register` writes the repo-root registry — by design).

## 2026-09-13ci — v2clusterpad ROUNDS 4–5 MERGED (3849010f + the timing record, lane 72f13a8e): the merge works and is GATED AT THE UNION. 13ch (i)'s derivation (a taxi-coupling gate) is REFUTED by measurement and the lane's deviation ACCEPTED as the law: `building91` shares NO vertex with `building80`, any apron or any taxi face; it fronts nothing (nearest pavement 80.35 m vs `pad_frontage_m` 3.0); the six worst-moved taxi vertices stand 2.19–2.22 km from it and none within 200 m — the 2.07 m was a FIELD-WIDE shift of the solve, not a transmission; `building91` is a SEPARATE BUILDING 65.81 m from the terminal that the cluster's coarse PART-BOX union intersected (§16g (2)'s undone polygon footprints reaching the design surface), and §30 (4) says "one pad over the family's FOOTPRINT UNION" — a pad 66 m outside the union is not in it. THE GATE (`cluster_pad._touching_component`, generator time): of the faces the union intersects, the cluster's plane covers the CONNECTED COMPONENT of pads within `footprint_touch_m` (0.5 m) of each other — the same chain the footprint unit is built on — holding the largest face; every other face keeps its own plane, collected in `cluster_pad.YIELDED` and named per cluster in the sidecar as `yielded_pads`. §30 (4) (5) restated: THE CLUSTER PAD IS THE TOUCHING COMPONENT; a pad the union merely overlaps yields by name. KCLT: PAD-ONLY (`3ad63ed931f6` → gated `bde3f0aff32e`) BYTE-IDENTICAL to DISARM; taxi family 0 moved; `building91` 217.89 (yields, named); the cluster's plane `building80` alone (median 221.46, spread 1.07); §16g (5) rows unchanged — 11,314 multi-anchor rows, 5,263 in a unit, 4,896 `OBJECT_MSL`, 6,336 on ground, 0 dropped; the passengers/seats at 225.46 = 221.46 + 4.00 (on the floor). Round 4's union-spread bar WITHDRAWN (it measured the lift of a building that is not the terminal's). Round 4's `cluster_pairs` (per-face-complete + cross-links) and the shared-face union are kept and twinned (a cluster whose pads touch merges; `padFar` yields) — neither acts at KCLT (one member face). OTHH PLAN STAGE re-timed after the grid deletion: 436.53 s with the cut (ONE run, CONTENDED by v2gradecache's build — an upper bound) vs 249.43 per-unit (1.75×, down from 3.2×); 368.58 s `--no-cut` mean of 3 on a quiet machine (not comparable); the remaining cost is `bodies_of_plan` + the part-box product in `_clusters._bind` — one piece of work with the polygon footprints (owed; the profiling round). Suite 1,348/0 twice on main. The apron reach stays DISARMED. Owner item KCLT 13bj item 1 CLOSED in law (the passengers on the floor; the terminal one unit); the terminal's stands stay graded under their own law (the owner's "if needed" flattening is infeasible with the taxiways at KCLT — reported, not forced).

## Tool: pad_airside_arm

| `Ortho4XP/tools/pad_airside_arm.py` | **THE PAD/AIRSIDE INVARIANCE ARM** (RULINGS 2026-09-14as (i), lane `v2padvert`; promoted from that lane's scratchpad on its eighth use per RULINGS `7e90032`). `V2PADVERT_ENGINE=<engine tree> venv/bin/python tools/pad_airside_arm.py ICAO OUT.json` — ONE load, then classify+planar TWICE (`[placement] pad_from_cluster` OFF then ON) and a diff of §20b stage 1's OWN airside vertex population (`solve/design_roles.airside_stage_vertices`, never a hand list) and the apron face list between the arms. It answers "does deriving the pads change the AIRSIDE PROBLEM" — 14as (i)'s prerequisite — in ~3 min at HECA against a ~450 s build, and it is a READER: no solve, no emit, nothing written but its own JSON. The shared-repo write guard and the lane-local cache redirects come from `harness/build_airport.arm_shared_repo_protection` (the ONE arming composition) and every run prints `[guard] shared repo UNCHANGED`. It also prints `classify/evidence.PAD_AIRSIDE` (what the airside clip and the rim snap did, with every refusal by reason) and, per NEW airside vertex, its distance to the other arm's nearest airside VERTEX and to its airside BOUNDARY — the two readings that separate a clip crossing point from an identity-grid artefact. MEASURED at HECA, gone/new: main 280/88; the clip alone 59/79; clip + vertex snap 28/35; clip + snap + the never-delete exemption 41/151. Twin: `tests/auto_patch_v2/test_v2padvert.py`. |

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Tool: pad_span_census

| `Ortho4XP/tools/pad_span_census.py` | The question is DOES THIS UNIT'S OWN DATUM FIT ITS BODIES' PADS — *how far apart do the emitted `building` pads one FOOTPRINT UNIT stands on actually stand?* — the single number owner RULINGS 2026-09-14c item 1 is accepted or refused on (spec `object-placement-spec.md` §16g (1)/(7)). No other instrument asks it: `harness/census.py` prices PAIRS OF VALUES, so an object seated 23.70 m above its own pad breaks no grade law and reports ZERO rows; `obj8_split_report.py` prints a body's anchor and its own ground but never asks whether the bodies sharing ONE unit's datum stand on pads that disagree; `role_overlap_read.py` is an AREA sweep and `role_edge_census.py` a boundary-length one. This is the unit-vs-pad reading: per unit, the `building` pads its bodies' FEET fall inside, how many bodies it holds, and the SPAN of those pads' planes, largest first. **It measures no law and counts no defects** — the pads are the emitted design surface's own `building` faces at `median(z)` over the ring, which is the plane `footprint_unit` reads through `anchor_rule.pad_plurality`, and the body→part join is the PART ID, never a proximity match (memory `canonical-identity-join`). `--over` (default 1.0 m) is the listing floor 14g stated its bar in, not a threshold with any standing. It takes either `o4_v2_placement_<ICAO>.json` or an `obj8_split_report --json` dump — both carry the same `splits` body records. Measured basis (scout `v2heca331` on the owner's 1.0.331 HECA): 17 units whose pads span > 1 m over 1,363 bodies, `fu:38:20` alone 978 bodies on 136 pads spanning 34.8 m — the unit chained on PART BOXES, and its DECK member then gave 96.20 to 1,509 bodies. Promoted 2026-09-14 from that scout's scratchpad `padspan.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse) — the 14g attribution, then lane `v2connector` round 3's before/after. Several patches are reported separately; quote it on identical options. Twin: `tests/test_pad_span_census.py` (the span IS the unit's own pads, a non-`building` face is not a pad, a unit on one pad is not a row, a body with no `unit_of` is not counted, the floor both ways, the CLI's JSON IS the library result, and this index row). |

## Registered frames: HECA

HECA  patch    base 13431931   lane v2zonehole       2026-09-13T22:35:13  /tmp/harness/v2zonehole_heca3.osm  — closing arm of claude/v2zonehole (rc 0, 410.3 s, body_sha 6cc8952ff963, ledger 3b32f2bd74f7, shared repo UNCHANGED) — §41 (1) absorption: containment census 39 -> 4 contained faces (33 notches absorbed, 65,772 -> 245 m2), cross_connector:pav77 absorbed into primary_parallel:pav73 at the owner's site, law-true 40,067 -> 38,151, rows within 100 m of the site 615 -> 551; residual zone_on_pavement 3 / 52.3 m2
HECA  capture  base 1a7a7158   lane v2roadcontact    2026-09-13T22:42:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/roadcontact/cap/HECA.pkl  — the FIRST registered HECA capture (v2_solve_replay --capture, 156 s, 17,408 vertices / 762 faces, 59 shapes) on main 1a7a7158; carries the road_contact_edge channel
HECA  patch    base 1a7a7158   lane v2roadcontact    2026-09-13T22:42:26  /tmp/harness/v2roadcontactHECA2.osm  — closing build of claude/v2roadcontact 9ac0fac2 (rc 0, 337.6 s, body_sha 38465d2dfd2a, ledger 96f569b01af9, shared repo UNCHANGED) — §37 (10): route0 end +0.054 m over pav74 edge, item-4 pair 1.6 % over 3.05 m; census law-true 38,441 adjudicated 12,771
HECA  patch    base 1a7a7158   lane v2roles          2026-09-13T22:45:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build/v2roles_HECA.osm  — closing HECA build of lane v2roles at claude/v2roles f19e2226 (§40): rc 0, 439.8 s, ways 1383, body_sha 8b2ca256f237, artifact ledger 9441f61e86fb, solve feasible, guard UNCHANGED. Shape 44 -> runway shoulder of 05L/23R, shape 93 -> apron, taxi zone strips on shape 44's ground 5 -> 0. RESIDUAL: v2-verify DEFECT runway_transverse 0 -> 2 (1.5287/1.5233 % vs the 1.50 % cap = 3.1/4.8 cm excess at 108.7/204.9 m from the ridge)
HECA  graded   base 1a7a7158   lane v2roles          2026-09-13T22:45:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build/v2roles_HECA.v2/HECA.graded.json  — design surface of the same v2roles_HECA build; HECA.report.json beside it carries verify.rows per family
HECA  patch    base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.osm  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  graded   base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.v2/HECA.graded.json  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  rebake   base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.v2/HECA.rebake.json  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  patch    base a5bb6be3   lane v2roles          2026-09-13T23:17:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build_r2/v2roles_HECA_r2b.osm  — ROUND 2 closing HECA build, claude/v2roles a33197a5 (§40 as amended by RULINGS 2026-09-13dd, main merged at 76108185): rc 0, 352.7 s, ways 1142, nodes 22040, body_sha 907d90dfc271, artifact ledger 09ca36ca6c1a, solve feasible, guard shared repo UNCHANGED. v2-verify runway_transverse 2 -> 0 (the two shoulder rows pass at the 2.5 % shoulder cap); NO DEFECT family. Matched census A/B vs the 1a7a7158 base arm: law-true 38,612 -> 33,265, ADJUDICATED 12,844 -> 14,870 (+2,026; round 1 was +2,511)
HECA  graded   base a5bb6be3   lane v2roles          2026-09-13T23:17:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build_r2/v2roles_HECA_r2b.v2/HECA.graded.json  — design surface of the round-2 v2roles_HECA_r2b build; report.json beside it, and the A/B rows dumps in scratchpad/v2roles/rows_r2.*.json
HECA  patch    base 38dd98be   lane v2roadcontact    2026-09-13T23:36:37  /tmp/harness/v2roadcontactHECA3.osm  — CLOSING build of claude/v2roadcontact 9eaebbf8 (rc 0, 332.5 s, body_sha 8bbae5f33254, artifact ledger 5e3f94ef2db6, shared repo UNCHANGED) on merged main 38dd98be — §37 (10) as ruled 13dh: route0 end +0.023 m over pav74's edge (4.34 m away), item-4 pair 0.05 m over 3.05 m (1.6 %); census law-true 33,242 adjudicated 14,850 (airside 14,506 / gs 300), road_cross_section 27, transverse 1,575, road_coverage_join 0; v2 verify 21,797 rows, verify_defects {}
HECA  patch    base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/l2/v2ds_lane38.osm  — lane v2drapedsrc round 2 (§42 (2) amended, RULINGS 13dc) on claude/v2drapedsrc 8994391f; MATCHED PAIR with the base arm cut at main 38dd98be (both carry §40). rc 0, 540.9 s, ways 1783, body_sha c16719e90795, artifact ledger 3eec5bf2bd6a, shared repo UNCHANGED. The owner's site 30.1235047,31.4160956 is INSIDE its OWN apron face apron:dsf:objpav33 (base: 0 rings); census law-true adjudicated 14,870 -> 24,338
HECA  graded   base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/l2/v2ds_lane38.v2/HECA.graded.json  — lane v2drapedsrc round 2 (§42 (2) amended, RULINGS 13dc) on claude/v2drapedsrc 8994391f; MATCHED PAIR with the base arm cut at main 38dd98be (both carry §40). rc 0, 540.9 s, ways 1783, body_sha c16719e90795, artifact ledger 3eec5bf2bd6a, shared repo UNCHANGED. The owner's site 30.1235047,31.4160956 is INSIDE its OWN apron face apron:dsf:objpav33 (base: 0 rings); census law-true adjudicated 14,870 -> 24,338
HECA  patch    base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/b2/v2ds_base38.osm  — BASE ARM of the v2drapedsrc round-2 pair: main 38dd98be cut with git archive into a ritual worktree (src byte-identical to the archive), rc 0, 342.7 s, ways 1142, body_sha 907d90dfc271, artifact ledger 85edce09e12a, shared repo UNCHANGED
HECA  graded   base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/b2/v2ds_base38.v2/HECA.graded.json  — the design surface of the same v2ds_base38 base arm
HECA  capture  base cf87c942   lane v2unionsweep     2026-09-14T07:40:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2unionsweep/heca.lane.json  — DRY replay dump (NOT a capture: plan_clusters OFF the registered HECA capture 1a7a7158, via cluster_arm.py). MATCHED PAIR: heca.base.json = main cf87c942 (67.52 s, contended; scout read 28.7 s), heca.lane.json = claude/v2unionsweep 99cf52ba (2.24 s). 2 clusters both arms, both areas bit-identical (unit:42#0 404117.7954653089 / unit:43#8 915741.4253155532).
HECA  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/heca/v2sl_heca2.osm  — CLOSING build of claude/v2slivers 88dfed33 (base main fef82b29): rc 0, 549.5 s, ways 1720, nodes 31441, body_sha 1c7f2be7abae, solve feasible, shared repo UNCHANGED (2 EXTERNAL-CANDIDATE VHHH deltas outside this build's input set) - 41(4) zone slivers 57/1647 m2 -> 1/188 m2 (55 dissolved, 0 dropped), owner shape 1035 gone (no vertex within 12 m of 30.1110526,31.4061994; base carried four at 105.86-106.01 against neighbours 104.32-104.71); gap_interior_ring 57 -> 49 (3 covered + 5 hairline gone incl way -10231, 0 minted, all 49 real voids). Census A/B vs v2sl_heca_base: law-true 54018 -> 53806, ADJUDICATED 24305 -> 24375, cockpit CRITICAL motion 14 -> 17, visual 1568 -> 1518
HECA  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/heca_base/v2sl_heca_base.osm  — BASE ARM of the v2slivers matched pair: main fef82b29 (src restored clean in the lane worktree), rc 0, 521.5 s, ways 1783, body_sha c07206902a0b, artifact ledger dc1d00dd83ca, shared repo UNCHANGED. Reproduces the owner's 1.0.331 numbers exactly: 338 graded_strip faces, 57 slivers / 1647 m2, 57 gap_interior_ring rings
HECA  patch    base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/build/v2apronneck_HECA.osm  — lane v2apronneck CLOSING HECA build on claude/v2apronneck 5340dcd7 (base main 2a4abb10) — §43 the neck cut: rc 0, 544.5 s, ways 1822, nodes 31613, body_sha d47263b02287, artifact ledger d53f79789526, solve feasible, guard shared repo UNCHANGED, v2-verify DEFECTS {}. HECA 10 necks; the owner's shape-344 apron (79,658 m2, z span 21.77 m) is gone — the neck A->B is secondary_parallel carrying -2.18 % where the apron carried -1.51 %, the new apron beyond spans 2.51 m. MATCHED PAIR with v2apronneck_HECAbase.
HECA  graded   base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/build/v2apronneck_HECA.v2/HECA.graded.json  — lane v2apronneck CLOSING HECA build on claude/v2apronneck 5340dcd7 (base main 2a4abb10) — §43 the neck cut: rc 0, 544.5 s, ways 1822, nodes 31613, body_sha d47263b02287, artifact ledger d53f79789526, solve feasible, guard shared repo UNCHANGED, v2-verify DEFECTS {}. HECA 10 necks; the owner's shape-344 apron (79,658 m2, z span 21.77 m) is gone — the neck A->B is secondary_parallel carrying -2.18 % where the apron carried -1.51 %, the new apron beyond spans 2.51 m. MATCHED PAIR with v2apronneck_HECAbase.
HECA  patch    base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/base_build/v2apronneck_HECAbase.osm  — BASE ARM of the v2apronneck matched pair: main 2a4abb10 in its own ritual worktree (v2apronneckbase), rc 0, 550.6 s, shared repo UNCHANGED (2 external-candidate deltas named, another lane's VHHH mod-cache), NOT ledger-stored. Census law-true 54,018 adjudicated 24,305
HECA  patch    base 22134e4f   lane zonemint         2026-09-14T09:26:56  /tmp/harness/zonemint_heca.osm  — closing build of claude/zonemint f35d3ee9 (rc 0, 664.5 s, ways 1783, nodes 31514, body_sha c07206902a0b, solve feasible, shared repo UNCHANGED; artifact ledger not stored: an external .DS_Store delta in the window) — sidecar face_holes now derived from the EMITTED surface (546 sub-spacing merges this build): zone_on_pavement 0 (the v2zonehole 13431931 frame: 3 / 52.3 m2; that frame REPLAYED with re-derived holes: 0, no other family moved). Base 22134e4f carries §40/§42, so its 54,012 rows / adjudicated 23,523 are NOT comparable with the 13431931 frame's 38,044 / 12,166
HECA  patch    base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.osm  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  graded   base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.v2/HECA.graded.json  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  rebake   base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.v2/HECA.rebake.json  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  patch    base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.osm  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  graded   base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.v2/HECA.graded.json  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  rebake   base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.v2/HECA.rebake.json  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  patch    base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.osm  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  graded   base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.v2/HECA.graded.json  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  rebake   base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.v2/HECA.rebake.json  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  capture  base 22134e4f   lane rwyholes         2026-09-14T09:25:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-dreamy-maxwell-b04861/a16ebd19-720d-4bda-a609-9334a87ca57c/scratchpad/rwyholes/cap/HECA.pkl  — the FIRST HECA capture carrying §40 (v2_solve_replay --capture from a ritual-mounted control worktree at main 22134e4f, 151 s, guard blocked [], lane-local DSF dump + mod-cache overlays; 25,358 vertices / 1,307 faces): 43 runway-family faces, 4 with holes, 308 hole vertices — the rwyholes dry pair (crown_drops 3419 -> 3727, runway_crown 2441 -> 2749, runway_transverse 2441 -> 2749 rows) was read off it
HECA  patch    base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.osm  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  patch    base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.osm  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  graded   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.v2/HECA.graded.json  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  graded   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.v2/HECA.graded.json  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  rebake   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.v2/HECA.rebake.json  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  rebake   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.v2/HECA.rebake.json  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  patch    base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.osm  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  graded   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.v2/HECA.graded.json  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.v2/HECA.rebake.json  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  patch    base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.osm  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  graded   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.v2/HECA.graded.json  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.v2/HECA.rebake.json  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  patch    base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.osm  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  patch    base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.osm  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  graded   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.v2/HECA.graded.json  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  graded   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.v2/HECA.graded.json  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  rebake   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.v2/HECA.rebake.json  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  rebake   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.v2/HECA.rebake.json  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  patch    base 18cc0ecb   lane v2staged         2026-09-14T16:41:01  /tmp/harness/v2stagedHECA3.osm  — §20b THE STAGED SOLVE, FINAL FORM, staged_solve=true arm (branch claude/v2staged): rc 0, 416.0 s, ways 1916, body_sha 266b56b5a358, v2-verify 33955, shared repo UNCHANGED. Stage 1 AIRSIDE 19,034 unknowns / 128,949 rows, 42/161,690 hard violated max 0.1794 NOT SETTLED, 0 one-way rows, runway projection 0.1155 -> 0.020000 m with 0 elastic; stage 2 13,838 unknowns / 180,591 rows in 11.2 s. vs its OFF twin v2stagedHECAoff (= r5 shipped body 18e51b7d084e): airside moved vs DISARM 8,976 -> 10,371 (BAR 0 MISSED; runway 885/0.390 -> 477/1.560), adjudicated 28,413 -> 29,018, airside_no_step 7,919 -> 6,801, taxi_box 3,429 -> 2,854, pad_airside_weld 29 -> 33, pad_cluster_mismatch 14 -> 14, terminal building298 72.60 -> 73.05. SHIPS OFF
HECA  patch    base 18cc0ecb   lane v2staged         2026-09-14T16:41:01  /tmp/harness/v2stagedHECAoff.osm  — §20b's DISARM twin (staged_solve=false) on claude/v2staged: rc 0, 476.3 s, body_sha 18e51b7d084e — BYTE-IDENTICAL to v2padcluster r5's shipped arm (ledger a602bba1b858), which proves everything merged since a3185dbb changes nothing at HECA and makes the r5/DISARM frames lawful controls for this lane. v2-verify 33,397; 1,021/365,395 hard rows violated max 2.984 m
HECA  capture  base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  — v2_solve_replay --capture on main b1b7704c (158 s, 31,820 vertices / 1,684 faces, pack partition 101 s: bodies 24,655 groups 22,049 relief 3,938 infeasible 2,546, 63 shapes); guard shared repo UNCHANGED, lane-local DSF + mod-cache overlays. The first HECA capture carrying the merged §20b staged solve (flag OFF by default; arm with --design-weight staged_solve=1). Stage-1 airside hard set read off it with the new --why-hard-stage 1.
HECA  graded   base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/emit_laneB/HECA.graded.json  — LANE arm of the v2settle matched pair (single solve = the shipped configuration), claude/v2settle b1a93a9a off main b1b7704c: dry --emit replay off cap/HECA.pkl. BYTE-IDENTICAL to the base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/base/emit_baseA/ (main b1b7704c) — the constant hard rows never reached the matrix. Hard set READ 281 -> 263 violated, worst 1.2595 m unchanged. Census law-true 64,716 ADJUDICATED 27,695.
HECA  capture  base b1b7704c   lane v2padvert        2026-09-14T18:19:02  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  — RE-READ by lane v2padvert (claude/v2padvert 4ec750f9): v2settle's HECA capture replayed under §20b (--design-weight staged_solve=1) with 14au's relaxed skirt ceiling (5 %). Stage 1 AIRSIDE 6/161,638 hard over 0.02 m, worst 0.0445 m — UNCHANGED from v2settle's post-fix reading (the airside did not move). Stage 2 770/163,847 violated, worst 4.4241 m, of which 124 a PROVED INFEASIBLE SET (90.4386 m over 544 free columns) against v2settle's 1,428 of 2,548 / 1,015.6 m: -91 % rows, -91 % shortfall. Pads-ON was NOT measurable off this capture — v2_solve_replay.capture sets no airport.clusters, so pad_from_cluster is inert in any replay of it; a pads-ON HECA reading needs a fresh capture or a build. guard shared repo UNCHANGED.

## Registered frames: KCLT

KCLT  capture  base ec8723e9   lane v2eat            2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2eat/cap  — captures of KCLT/HECA/OTHH/SPJC by lane v2eat; base predates the 13ak pad-law break — valid
KCLT  rebake   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.rebake.json  — v2familyKCLTframe build (rc 0, 389.3 s, body_sha bb022a77f067) on main 864e7577 — POST 13ak pad-law fix; the build was CONTAMINATED (one Airport_mod_cache dump, chip 13ao) so it carries no ledger key
KCLT  graded   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.graded.json  — the design surface of the same v2familyKCLTframe build
KCLT  capture  base 70646dc8   lane v2roadramp       2026-09-13T12:44:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/KCLT.pkl
KCLT  rebake   base 0c86fe2c   lane v2clusterpad     2026-09-13T17:03:58  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/laneKCLT/v2clusterpadKCLT2.v2/KCLT.rebake.json  — v2clusterpadKCLT2 build (rc 0, 477.2 s, body_sha 9f056cce3dc3, shared repo UNCHANGED) on claude/v2clusterpad over main 0c86fe2c — the FIRST KCLT frame carrying the §30 (4) CLUSTER PAD and its apron reach; no ledger key (the tree moved between key and store time)
KCLT  graded   base 0c86fe2c   lane v2clusterpad     2026-09-13T17:03:58  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/laneKCLT/v2clusterpadKCLT2.v2/KCLT.graded.json  — the design surface of the same v2clusterpadKCLT2 build: building80+building91 are ONE plane (union spread 4.43 -> 1.46 m) and 38 of 90 apron vertices within 60 m sit at the pad's level
KCLT  patch    base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /tmp/harness/KCLT_20260913T172152.osm  — closing build of claude/v2zonebank cde84e27 (rc 0, 492.4 s, body_sha 9113da337600, ledger 6486660716cc, shared repo UNCHANGED) — §37 (3) as amended: bank 134 rings / 1,311 foot nodes, bank_foot at both owner sites (38.3 m and 10.2 m) and at the 13ax lip; census law-true 13,416
KCLT  graded   base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/zonebank/KCLT.solved.pkl  — v2_solve_replay --solved-out off cap/KCLT.pkl on BASE ce203b29 — the fixed upstream for 'v2_solve_replay --bank-from PKL --bank-walk' (2.5 s per bank-stage arm)
KCLT  graded   base 880a9293   lane v2clusterpad     2026-09-13T17:50:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/r2/v2cpKCLTr2.v2/KCLT.graded.json  — v2cpKCLTr2 (rc 0, 493.0 s, 5fb560ae50d0) — the CLUSTER arm of the matched pair; its DISARM twin (cluster_pad_min_m2=0, cluster_apron_reach_m=0) is v2cpKCLTdisarm at .../disarmOUT/v2cpKCLTdisarm.v2/
KCLT  rebake   base 880a9293   lane v2clusterpad     2026-09-13T17:50:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/r2/v2cpKCLTr2.v2/KCLT.rebake.json  — the rebake plan of the same v2cpKCLTr2 build
KCLT  graded   base 952924e9   lane v2clusterpad     2026-09-13T18:15:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/c3/v2cpKCLTc3.v2/KCLT.graded.json  — round-3 CLUSTER arm (13cc reach: population minus no-step-coupled apron, priced at apron_trend); its matched DISARM twin is .../d3/v2cpKCLTd3.v2 and the PAD-ONLY attribution arm .../padonly/ is BYTE-IDENTICAL to the disarm
KCLT  patch    base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/kclt_arm.osm  — §39 ARM patch (harness tag v2hairline_kclt_patch): shore weld dropped 2 bank nodes, worst 0.0198 mm at 35.2031709,-80.9454997 (the 723,015-sliver site)
KCLT  graded   base e88ed84b   lane v2clusterpad     2026-09-13T18:41:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/p5/v2cpKCLTp5.v2/KCLT.graded.json  — round-4 PAD-ONLY arm (reach 0, merge EFFECTIVE: building91 221.52, union spread 1.07); its matched DISARM twin is .../d4/v2cpKCLTd4.v2 (bde3f0aff32e). Taxi family 2,406 moved worst 2.07 m between the two — the merge's own, the reach is off in both
KCLT  graded   base 8841c106   lane v2clusterpad     2026-09-13T18:58:24  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/p6/v2cpKCLTp6.v2/KCLT.graded.json  — round-5 PAD-ONLY arm under the §30 (4) (5) GATE — BYTE-IDENTICAL to its DISARM twin .../d4/v2cpKCLTd4.v2 (both bde3f0aff32e): building91 yields (65.81 m from the terminal, a part-box artefact), taxi family 0 moved
KCLT  patch    base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/kclt_r2.osm  — §39 round 2 arm patch: hairline_pair adjudicated 0, emitted sub-spacing segments 799 -> 11 (all the deliberate triangle floor)
KCLT  patch    base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterKCLT3.osm  — lane v2padcluster ROUND 3 KCLT build (claude/v2padcluster at 01724ef4 — carries (4) on the DESIGN cluster, (5) and (6); the object-stage half of (4) landed after and moves no vertex, proven by HECA3/HECA4 sharing body_sha cbefb8edcacb): rc 0, 274.2 s, ways 1189, body_sha d19ae4797bc4, solve feasible, guard shared repo UNCHANGED; NO ledger key (the tree moved during the run). THE CONTROL, read BY COORDINATE at 13bo's site 35.2191877,-80.9426007 because the derived pads RENUMBER every building{N}: the terminal pad 221.46 -> 220.56 m (-0.90), 865 -> 483 vertices, spread 1.07 -> 0.51 — the bar (unchanged within hard_tol_m) is MISSED
KCLT  graded   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterKCLT3.v2/KCLT.graded.json  — lane v2padcluster ROUND 3 KCLT build (claude/v2padcluster at 01724ef4 — carries (4) on the DESIGN cluster, (5) and (6); the object-stage half of (4) landed after and moves no vertex, proven by HECA3/HECA4 sharing body_sha cbefb8edcacb): rc 0, 274.2 s, ways 1189, body_sha d19ae4797bc4, solve feasible, guard shared repo UNCHANGED; NO ledger key (the tree moved during the run). THE CONTROL, read BY COORDINATE at 13bo's site 35.2191877,-80.9426007 because the derived pads RENUMBER every building{N}: the terminal pad 221.46 -> 220.56 m (-0.90), 865 -> 483 vertices, spread 1.07 -> 0.51 — the bar (unchanged within hard_tol_m) is MISSED
KCLT  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterKCLT3.v2/KCLT.rebake.json  — lane v2padcluster ROUND 3 KCLT build (claude/v2padcluster at 01724ef4 — carries (4) on the DESIGN cluster, (5) and (6); the object-stage half of (4) landed after and moves no vertex, proven by HECA3/HECA4 sharing body_sha cbefb8edcacb): rc 0, 274.2 s, ways 1189, body_sha d19ae4797bc4, solve feasible, guard shared repo UNCHANGED; NO ledger key (the tree moved during the run). THE CONTROL, read BY COORDINATE at 13bo's site 35.2191877,-80.9426007 because the derived pads RENUMBER every building{N}: the terminal pad 221.46 -> 220.56 m (-0.90), 865 -> 483 vertices, spread 1.07 -> 0.51 — the bar (unchanged within hard_tol_m) is MISSED
KCLT  patch    base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterKCLT4.osm  — v2padcluster ROUND 4 KCLT build at the final tree (claude/v2padcluster 9a4bd0e3): rc 0, 259.0 s, ways 1070, body_sha 2fa924a012cc, artifact ledger dca6d7449633, solve feasible, guard shared repo UNCHANGED. THE CONTROL at 13bo's coordinate 35.2191877,-80.9426007: the terminal pad building80 (850 verts) median 221.46 -> 220.93 (-0.53), spread 1.07 -> 3.77 — and the movement IS THE WELD: the pad shares 743 nodes with the apron pav14 (z 220.04..223.81) and 51 with pav118, so the step across the weld is 0 by construction. pad_airside_weld 25, worst building80 -> pav14 1.384 m over 11.6 m (the pad cannot reach that edge even bending at 1 %)
KCLT  graded   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterKCLT4.v2/KCLT.graded.json  — v2padcluster ROUND 4 KCLT build at the final tree (claude/v2padcluster 9a4bd0e3): rc 0, 259.0 s, ways 1070, body_sha 2fa924a012cc, artifact ledger dca6d7449633, solve feasible, guard shared repo UNCHANGED. THE CONTROL at 13bo's coordinate 35.2191877,-80.9426007: the terminal pad building80 (850 verts) median 221.46 -> 220.93 (-0.53), spread 1.07 -> 3.77 — and the movement IS THE WELD: the pad shares 743 nodes with the apron pav14 (z 220.04..223.81) and 51 with pav118, so the step across the weld is 0 by construction. pad_airside_weld 25, worst building80 -> pav14 1.384 m over 11.6 m (the pad cannot reach that edge even bending at 1 %)
KCLT  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:30  /tmp/harness/v2padclusterKCLT4.v2/KCLT.rebake.json  — v2padcluster ROUND 4 KCLT build at the final tree (claude/v2padcluster 9a4bd0e3): rc 0, 259.0 s, ways 1070, body_sha 2fa924a012cc, artifact ledger dca6d7449633, solve feasible, guard shared repo UNCHANGED. THE CONTROL at 13bo's coordinate 35.2191877,-80.9426007: the terminal pad building80 (850 verts) median 221.46 -> 220.93 (-0.53), spread 1.07 -> 3.77 — and the movement IS THE WELD: the pad shares 743 nodes with the apron pav14 (z 220.04..223.81) and 51 with pav118, so the step across the weld is 0 by construction. pad_airside_weld 25, worst building80 -> pav14 1.384 m over 11.6 m (the pad cannot reach that edge even bending at 1 %)
KCLT  capture  base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/KCLT.pkl  — v2_solve_replay --capture on main b1b7704c (79 s, 21,683 vertices / 1,007 faces, pack partition 45 s: bodies 7,163 groups 7,007 relief 1,261 infeasible 1,032); guard shared repo UNCHANGED. KCLT captures and replays under the harness (13w's fresh_pack_dump). Base arm 408/227,135 hard violated max 0.5040 m, lag NOT SETTLED 0.3174 m.
KCLT  graded   base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/emit_kcltB/KCLT.graded.json  — LANE arm of the v2settle KCLT matched pair (single solve), claude/v2settle b1a93a9a. BYTE-IDENTICAL to the base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/base/emit_kcltA/. Hard set 408 -> 406 violated, worst 0.5040 m unchanged, and 143 of the 406 NAMED as a proven INFEASIBLE SET (26.3994 m over 179 free columns), all structures.building_pad airside skirt at 35.2096,-80.9327. Census law-true 18,193 ADJUDICATED 6,874.
KCLT  capture  base b1b7704c   lane v2padvert        2026-09-14T18:18:51  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/KCLT.pkl  — RE-READ by lane v2padvert (branch claude/v2padvert 4ec750f9) — v2settle's own KCLT capture replayed as a MATCHED PAIR under §20b (--design-weight staged_solve=1), the ONLY variable emit.within_shape.pad_skirt_max_slope (14au). BASE 1 %: stage 1 airside 1/121,520 hard violated worst 0.0241 m; stage 2 4,431/105,498 violated worst 3.3606 m, of which 2,410 a PROVED INFEASIBLE SET (1,389.70 m over 697 free columns). LANE 5 %: stage 1 IDENTICAL (1/121,520, 0.0241 — the airside did not move); stage 2 937 violated worst 2.3622, INFEASIBLE SET 313 rows / 128.20 m over 392 columns (-87 % rows, -91 % shortfall). The 14au bar (143 -> 0) is MISSED: 313 remain and they are the pads that cannot reach even bending at 5 % — pad_airside_weld CRITICAL by 14au's own clause. Single-solve arm (relaxation ungated) read 406 -> 74 violated and 143 -> 19 infeasible, but cost CYXY 2 runway_transverse rows and is NOT the shipped form. guard shared repo UNCHANGED.

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

