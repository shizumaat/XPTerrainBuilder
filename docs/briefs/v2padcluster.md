# Brief pack — lane `v2padcluster`

Base: main `9936aded` · generated 2026-09-14 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§16g (9)–(10) THE PAD IS THE CLUSTER: one population, ground-floor split, pads derived from clusters, pad_cluster_mismatch (RULINGS 14x/14z)

## The brief

You inherit lane v2connector's work (RULINGS 14o/14w/14x/14z; branch merged into main). Implement §16g (9)–(10) — THE PAD IS THE CLUSTER — in this order: (1) DRY READ at HECA: `cluster_pad._touching_component`'s `YIELDED` publication on the registered HECA frames (`frames.py list HECA` — the round-5 null arm `HECA_20260914T104957` and round-6 `HECA_20260914T110528`; the offline reproduction `cfaces.py` is in `…/scratchpad/v2connector/`): what the gate discards for `unit:42#0` (22 pad faces, 29.30 m span) and `unit:43#8` (73 faces, 18.84 m). (2) CONSUMER CENSUS (RULINGS 2026-08-30l) — one table in the §16g (10) MEASURED block BEFORE editing: every reader of `airport.clusters`, `PlanCluster`, `cluster_pad_faces`/`plane_groups`/`cluster_offsets`, and every reader of `building` pad polygons/levels (`constraints/pads.py`, `constraints/cluster_pad.py`, `constraints/pad_frontage_gs` §28, `airport/dsf.py`/`load.py` footprint-cache pads, `planar/` pad readers, the `pad_flat`/`pad_frontage` census families, `verify/pads.py`, `airport/footprint_unit.plan_unit_datums` `pad_plurality`). (3) IMPLEMENT at the derivation: (a) `PlanCluster.floors` → per BODY ground floor (lowest ground-contact component's `base_y`); (b) `plan_clusters` splits a touching chain where the ground-floor levels differ by > `floor_split_m` (0.5, new key in `law/structures.toml` or `emit.toml` — no numeric literal in Python); the `FAMILY_*` gates go; (c) the `building` PAD is derived from the cluster: one pad per cluster, polygon = the cluster's outline union (`Part.rings`), one level — the pad stage reads `airport.clusters` for pad polygons and falls back to the footprint-cache pads only where no cluster covers a resource; (d) `_touching_component`'s one-face yield is replaced (the cluster's pad is its own polygon); the cluster-APRON reach (13ci) stays disarmed; (e) census family `pad_cluster_mismatch` (CRITICAL: a pad spanning two clusters or a cluster spanning two pads) registered in `tools/check_grade.py` LAW_FAMILIES + `law/families.toml`. (4) The (8) offsets become the terrace steps between touching clusters' pads (declared joints). Twins for each. KCLT is the CONTROL: dry from its registered frame — the terminal's cluster pad (13bo, the passengers on the terminal floor at 222.07) and its members' seats unchanged; name any change. Then ONE HECA build. Files: `airport/placement_family.py`, `planar/cluster.py`, `constraints/cluster_pad.py`, `constraints/pads.py`, `airport/footprint_unit.py`, `tools/check_grade.py`, `law/families.toml`, `pipeline/publication.py`, the pad derivation site in `airport/load.py` or `planar/` (find it — the footprint-cache pads enter at `load.py:~389`). NOT yours: `airport/partition_cache.py`, `contact.py`, `pack_partition.py`, `anchor_rule.py` (lane v2cost2 r2), `planar/basins.py`, `structures.py`, `wall_corridor_ramps.py` (v2othhfix). Merge main right before reporting. Promote the scout reader `site.py` (`…/scratchpad/heca/site.py`: coordinate → faces + bodies + unit/datum/float) into `Ortho4XP/tools/` with an INDEX row and twin — it is on its second use — and use it for the per-site bars.

## Bars

- HECA (ONE build): `pad_cluster_mismatch` 0; bodies > 0.02 m off their own pad: count before → after (today 845 in 17 units); the T3 district → N clusters = its distinct ground-floor levels, each on its own derived pad (named with level and area); buildings 138/143/147/153/159/160/170 (by coordinate — the shapeIDs are stale) and the terminal at 30.1279552, 31.403143 each on its pad (zero = pad ± 0.02); terrace steps between touching clusters' pads named; `pad_frontage_gs` rows before → after; airside vertices moved 0.
- KCLT control (dry, registered frame): the terminal cluster pad + members' seats unchanged (13bo, 222.07); any change named.
- SPJC dry: the viaduct at 19.56 (13df) unchanged; OTHH/LEMD unit censuses before → after (clusters up, pads per cluster = 1).
- Plan/constraints stage cost not worse than +10 % (HECA); suite twice.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/placement_family.py`, `Ortho4XP/src/auto_patch_v2/planar/cluster.py`, `Ortho4XP/src/auto_patch_v2/constraints/cluster_pad.py`, `Ortho4XP/src/auto_patch_v2/constraints/pads.py`, `Ortho4XP/src/auto_patch_v2/airport/footprint_unit.py`, `Ortho4XP/tools/check_grade.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/airport/partition_cache.py`, `Ortho4XP/src/auto_patch_v2/airport/contact.py`, `Ortho4XP/src/auto_patch_v2/airport/anchor_rule.py`, `Ortho4XP/src/auto_patch_v2/planar/basins.py`, `Ortho4XP/src/auto_patch_v2/planar/structures.py`

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

## Spec (object-placement) §16g (9)

### §16g (9) ONE POPULATION; (10) THE PAD IS THE CLUSTER (owner RULINGS 2026-09-14x; Fable 2026-09-14) — lane `v2connector`

(9) ONE POPULATION.  The design-surface cluster IS the object-stage unit:
one derivation (`plan_clusters` adopts §16g (7)'s relation, footprint
outlines at `footprint_touch_m`); the FAMILY_* gates go; `cluster_pad_min_m2`
stays only as the threshold for emitting a cluster pad.

(10) THE PAD IS THE CLUSTER.  "Pads must match building clusters … they
should match exactly."
1. A CLUSTER is ONE BUILDING: bodies chain only if their footprints touch
   (7) AND their authored floor levels agree within `floor_split_m` (0.5 m).
   A touching body at a different authored floor is a different building —
   its own cluster, its own pad — and the difference is a declared terrace
   step between the two pads.
2. The design surface's `building` PAD is DERIVED from the cluster: one pad
   per cluster, its footprint = the cluster's outline union, one level.  The
   footprint-cache pads are the fallback only where the plan has no cluster
   (a resource the object stage skips).
3. A pad spanning two clusters, or a cluster spanning two pads, is
   `pad_cluster_mismatch` (CRITICAL): a misidentified shape, never seated
   over.  (8)'s derived offsets within a unit are narrowed to the steps
   between touching clusters' pads.

BARS (HECA, ONE build): `pad_cluster_mismatch` 0; every body within
`hard_tol_m` of its own pad (bodies > 0.02 m off: count before → after); the
T3 district resolved into N clusters = its distinct floor levels, each on its
own pad (named); the seven buildings + the terminal at 30.1279552, 31.403143
on their pads; terrace steps between touching clusters named; KCLT dry:
the terminal's cluster pad and its members' seats unchanged (13bo, the
control); SPJC 19.56 dry; airside 0; suite twice.

## Spec (object-placement) §16g (8)

### §16g (8) THE PADS UNDER A CONNECTED UNIT FOLLOW THE SEATED BODIES (owner RULINGS 2026-09-14u; Fable 2026-09-14) — lane `v2connector`

MEASURED (14o): with true outlines HECA's T3 district still chains across
23 pads spanning 29.99 m because its footprints genuinely touch end to end
— lawful under (7) (1).  One datum for a district whose pads span 30 m
floats its bodies against their own pads.

1. For a unit whose members stand on several `building` pads, each pad's
   level is DERIVED from the unit: pad = unit datum + the authored floor
   offset of the bodies standing on that pad (the cluster pad, §30 (4)–(5),
   is the datum plane at the reference pad — the pad the datum body stands
   on).  The design surface takes the pads from the objects: the pad rows
   for those pads become targets at the derived level (hard, `hard_tol_m`),
   the ground between pads terraces by the ground law (§23, declared
   joints), and no body floats.  The pack author's terracing wins.
2. A pad shared by bodies with DIFFERENT authored floor offsets (a split-
   level building on one pad) takes the LOWEST offset and the census names
   the spread (`pad_offset_spread`).
3. The seat stays 13cb's invariant: unit datum + authored offset per body.

BARS (HECA, the r4 frame): the 17 pad-spanning units → every member body
within `hard_tol_m` of its own pad (bodies > 0.02 m off their pad: count
before → after, per unit); `fu:38:23` (23 pads / 579 bodies) all members on
their pads; the seven buildings + the terminal at 30.1279552, 31.403143 on
their pads; declared terrace joints between derived pads named with their
steps; airside vertices moved 0; SPJC viaduct 19.56 unchanged; ONE HECA build.

## Spec (object-placement) §16g (7)

### §16g (7) UNITS CHAIN BY FOOTPRINT POLYGON, NEVER BY BOX OR PAD; §16g (6) (2) AMENDED — A CONNECTOR IS ITS OWN BODY, SEATED LOW (owner RULINGS 2026-09-14c items 1/3; Fable 2026-09-14) — lane after scout `v2heca331`

1. Two bodies are one unit only if their FOOTPRINT POLYGONS (the refined
   footprint, §16g MEASURED (b) is withdrawn — not the part boxes) touch or
   overlap within `footprint_touch_m`.  A body with a gap all round — even
   1 m — is its own unit, seated on its own pad.  Sharing a pad, a cluster
   pad or an authored DSF origin never chains two bodies (the cluster pad
   is a DATUM for the bodies that touch it, §16f (7)/§30 (4)-(5); `authored_unit`
   stays a census witness).  HECA buildings 138/143/147/153/159/160/170 each
   have their own pad and must sit on it.
2. (6) (2) amended: a body that (6) (1) names a CONNECTOR is REMOVED from the
   unit chain — it is its own body, and neither unit takes its deck as a
   datum.  It is seated to its LOW-end contact (ground or pad at the low
   end) so it disappears into the ground at the high end; the §10 station
   cut, when written, grades it between its two end contacts.  13df's
   high-end seat is withdrawn: at HECA it lifted the T3 terminal complex
   (15,940 bodies) onto `T3_road.obj`'s deck.

BARS: HECA the seven buildings each on its own pad (authored zero = pad
datum ± `hard_tol_m`); the terminal at 30.1279552, 31.403143 on its pad, not
the deck; the elevated rail seated at its low end, named; KCLT/OTHH/LEMD/SPJC
unit censuses before → after (units up, bodies per unit down, every
per-unit zero spread 0.00); the SPJC viaduct (13df) unchanged at 19.56.

## RULINGS

## 2026-09-14z v2connector round 6 MERGED (instrumentation only): `airport.clusters` is NOT empty — the §30 (4) yield gate `_touching_component` collapses each cluster to one pad face; (10)'s floor level = the body's GROUND floor; lane `v2padcluster` takes §16g (9)–(10) from a fresh context

Lane `v2connector` @ f4998176 (HECA build `HECA_20260914T110528`, rc
0, 479 s, cache WROTE — cold, the partition cache not implicated).
`[clusters] 2 terminal cluster(s) (partition units 44, touch 0.5 m,
min 5000.0 m2)`: `unit:42#0` 404,118 m² / 84 members hits 22 pad faces
spanning 29.30 m; `unit:43#8` 929,155 m² / 149 members hits 73 pad
faces spanning 18.84 m — yet `cluster_cross_links = 0`, because
`cluster_pad._touching_component` (13ch/13ci's yield gate) keeps ONE
face per cluster, `plane_groups` never merges, and §16g (8)'s
`cluster_offsets` bails on `len(floor) < 2`. Round 5's "empty
clusters" inference was wrong; the lane's own instrumentation says so.
The (8) plumbing (`PlanCluster.floors`, `cluster_offsets`, the `rel=`
channel) is in place and twinned, inert only because the gate starves
it. The lane is at the end of its useful context and hands over.

* RULING: (10)'s "authored floor level" is the body's GROUND FLOOR —
  the lowest ground-contact component's `base_y` — never per
  component (a cluster's per-component range at HECA is −6.46 … 112.90
  m; a tall building must not split per storey). `PlanCluster.floors`
  becomes per body at that reading.
* RULING: under (10) the yield gate is REPLACED — a cluster no longer
  picks one existing pad face; its pad IS its outline (one pad per
  cluster, and with the floor split a 73-pad cluster becomes N
  clusters each with its own derived pad); 13ci's union gate stays only
  for the cluster-APRON reach, which is disarmed (13ce).
* Lane `v2padcluster` (fresh, brief pack): the handover list — read
  `YIELDED` at HECA dry; the consumer census of every reader of
  `airport.clusters` / `PlanCluster` / `cluster_pad_faces` / `building`
  pads in one table; `floor_split_m`; the pad-from-cluster derivation;
  `pad_cluster_mismatch`; KCLT control; the HECA bars.

## 2026-09-14x Owner: "pads must match building clusters, no building, or cluster can span multiple pads, if it does, it means we didn't identify the building shape or cluster correctly. They should match exactly." — §16g (10) THE PAD IS THE CLUSTER; §16g (8) narrowed

Owner, verbatim: "Agreed, pads must match building clusters, no
building, or cluster can span multiple pads, if it does, it means we
didn't identify the building shape or cluster correctly. They should
match exactly."

* RULING §16g (10): the design surface's `building` PAD IS the
  cluster's footprint — one pad per cluster, exactly its outline
  union, one level; and a cluster is ONE BUILDING: bodies chain into a
  cluster only if their footprints touch (§16g (7)) AND they share one
  authored floor level (within `floor_split_m`, 0.5 m — a body
  touching at a different authored floor is a different building, its
  own cluster, its own pad, joined by a declared terrace step). A pad
  spanning two clusters, or a cluster spanning two pads, is a census
  CRITICAL (`pad_cluster_mismatch`) — a misidentified shape, never
  seated over. §16g (8)'s "derived pads within a unit" is NARROWED to
  this: the offsets between touching clusters ARE the steps between
  their pads. HECA's 23-pad T3 district must resolve into as many
  clusters as it has floor levels, each on its own pad.
* Lane `v2connector` r6 (brief amended): the pad geometry is DERIVED
  from the cluster (the pad stage reads `airport.clusters`; the
  footprint-cache pads are the fallback where no cluster exists);
  consumer census of every pad reader; KCLT control.

## 2026-09-14w v2connector round 5: §16g (8) implemented and INERT at HECA — the design-surface CLUSTER and the object-stage UNIT are two populations; `airport.clusters` is EMPTY at HECA solve time — ruled: one population; lane r6

Lane `v2connector` @ 2e97d822 (HECA build `HECA_20260914T104957`, rc
0, byte-for-byte round 4's pad census). `PlanCluster.floors` (authored
`base_y` per box), `cluster_pad.cluster_offsets` (reference = the
plurality pad, the one `pad_plurality` hands the unit; lowest floor on
a shared pad; `pad_offset_spread`), `pads._pad_rows` folds the offsets
into the existing `rel=` channel (no new row kind), publication
reports `reference_pad` / `derived_pads`. Suite 1,415 twice. BUT
`pad_flats.cluster_cross_links = 0` at HECA — no §30 (4) cluster-pad
group forms, so the derivation is unreachable. Two causes: (a)
`cluster_pad.py`'s docstring ("the same relation the object stage
binds with") is FALSE — `plan_clusters` uses part BOXES at
`contact_eps_m` 0.002 m with the FAMILY_MIN_MEMBERS / FAMILY_SHARE_MIN
/ `cluster_pad_min_m2` gates; the object stage uses footprint OUTLINES
at `footprint_touch_m` 0.5 m with no gates (§16g (7)); (b)
`airport.clusters` is EMPTY at HECA solve time although
`plan_clusters` on the same plan returns 2 clusters (largest 926,525
m²) — a load/planar wiring gap in `planar/cluster.py` / `load.py`
(possibly the partition cache path — v2cost2 merged after the lane's
base). The lane owns the census miss (a docstring read, not a
measurement — `comment-prose-may-describe-unlanded-state`).

* RULING §16g (9): ONE POPULATION. The design-surface cluster IS the
  object-stage unit: `plan_clusters` adopts the §16g (7) relation
  (footprint outlines at `footprint_touch_m`), one derivation for
  both; the family gates go; `cluster_pad_min_m2` (5,000 m²) stays as
  the threshold for emitting a cluster PAD (§30 (4)–(5): the touching
  component's plane, now the reference pad + the §16g (8) derived
  pads). Consumer census of every cluster reader in ONE table first —
  KCLT's load-bearing cluster pad (the passengers on the terminal
  floor, 13bo) is the control that must not move.
* The wiring gap (b) is measured FIRST (why `airport.clusters` is
  empty at HECA — is it the gates, the cache, or the load path) — it
  may alone be why HECA has no cluster pads; lane granted
  `planar/cluster.py` and the cluster wiring in `airport/load.py` /
  `pipeline/build.py` (coordinate with v2cost2 r2 on `load.py`).

## 2026-09-14o v2connector round 4 MERGED (4bb102c1): the true outline, the rail at its north end (76.70), `plan_units_and_connectors` 17.2 s; 17 pad-spanning units are LAWFUL touching chains — an intent question

Lane `v2connector` @ deca6c2f; HECA build `HECA_20260914T093118`
(ledger 9c1ae5a6873e, 598 s); frames registered for r3 and r4. Outline
= union of the component's projected triangles, one ring per blob,
simplified OUTWARD (`OUTLINE_SIMPLIFY_M` 0.05, hull past 4,000 tris);
84.1 % of parts carry rings, the plan SMALLER (17.9 → 17.1 MB). Matched
arms (r4 code, hull plan vs outline plan): `plan_units_and_connectors`
21.7 → 17.2 s; units 304 → 324; bodies at 96.20 0 → 0; the rail
`concrete_3` b1 93.45 → **76.70 at its NORTH end** (own ground ± 0.09;
14g's ~73.4 was the DEM, this is the design surface at its feet); b0
also a connector at 94.55. Suite 1,421 on main. `git merge main`
silently dropped the `pad_span_census` INDEX row — the tool's twin
caught it (INDEX.md loses rows in merges; only per-tool twins notice).

* MISSED and now understood: units whose pads span > 1 m 20 → 17 (845
  bodies); `fu:38:23@cluster_pad` 23 pads / 579 bodies / 29.99 m did NOT
  split because the T3 district's footprints GENUINELY TOUCH,
  transitively, across all 23 pads — under §16g (7) (1) as the owner
  worded it ("only if they're physically touching/overlapping") that
  chain is lawful and no sharper footprint breaks it (next: `fu:43:7386`
  19 pads / 10.3 m, `fu:43:7179` 7 / 9.8, `fu:39:104` 11 / 7.8).
* INTENT QUESTION (owner), three options: (a) the PADS FOLLOW THE UNIT
  — a connected mass is one unit at one datum (13cb's invariant), and
  the design surface's pads under it take their level from the seated
  bodies (pad = datum + the body's authored floor offset), the ground
  terracing between pads by the ground law — no body floats, the pack
  author's terracing wins; (b) per-pad seats WITHIN a unit — the unit
  stays a rigid relation only for bodies sharing a pad (13cb weakened);
  (c) a chaining tolerance smaller than `footprint_touch_m` (0.5 m
  welds a district) — a different law from "touch". Recommended: (a).
* Owed: the seven buildings + the terminal per-site read (the
  airport-wide 96.20 count is 0); SPJC/KCLT/OTHH/LEMD under the outline
  (their plans predate `Part.rings`; the 1.0.333 sweep).

## 2026-09-13ci — v2clusterpad ROUNDS 4–5 MERGED (3849010f + the timing record, lane 72f13a8e): the merge works and is GATED AT THE UNION. 13ch (i)'s derivation (a taxi-coupling gate) is REFUTED by measurement and the lane's deviation ACCEPTED as the law: `building91` shares NO vertex with `building80`, any apron or any taxi face; it fronts nothing (nearest pavement 80.35 m vs `pad_frontage_m` 3.0); the six worst-moved taxi vertices stand 2.19–2.22 km from it and none within 200 m — the 2.07 m was a FIELD-WIDE shift of the solve, not a transmission; `building91` is a SEPARATE BUILDING 65.81 m from the terminal that the cluster's coarse PART-BOX union intersected (§16g (2)'s undone polygon footprints reaching the design surface), and §30 (4) says "one pad over the family's FOOTPRINT UNION" — a pad 66 m outside the union is not in it. THE GATE (`cluster_pad._touching_component`, generator time): of the faces the union intersects, the cluster's plane covers the CONNECTED COMPONENT of pads within `footprint_touch_m` (0.5 m) of each other — the same chain the footprint unit is built on — holding the largest face; every other face keeps its own plane, collected in `cluster_pad.YIELDED` and named per cluster in the sidecar as `yielded_pads`. §30 (4) (5) restated: THE CLUSTER PAD IS THE TOUCHING COMPONENT; a pad the union merely overlaps yields by name. KCLT: PAD-ONLY (`3ad63ed931f6` → gated `bde3f0aff32e`) BYTE-IDENTICAL to DISARM; taxi family 0 moved; `building91` 217.89 (yields, named); the cluster's plane `building80` alone (median 221.46, spread 1.07); §16g (5) rows unchanged — 11,314 multi-anchor rows, 5,263 in a unit, 4,896 `OBJECT_MSL`, 6,336 on ground, 0 dropped; the passengers/seats at 225.46 = 221.46 + 4.00 (on the floor). Round 4's union-spread bar WITHDRAWN (it measured the lift of a building that is not the terminal's). Round 4's `cluster_pairs` (per-face-complete + cross-links) and the shared-face union are kept and twinned (a cluster whose pads touch merges; `padFar` yields) — neither acts at KCLT (one member face). OTHH PLAN STAGE re-timed after the grid deletion: 436.53 s with the cut (ONE run, CONTENDED by v2gradecache's build — an upper bound) vs 249.43 per-unit (1.75×, down from 3.2×); 368.58 s `--no-cut` mean of 3 on a quiet machine (not comparable); the remaining cost is `bodies_of_plan` + the part-box product in `_clusters._bind` — one piece of work with the polygon footprints (owed; the profiling round). Suite 1,348/0 twice on main. The apron reach stays DISARMED. Owner item KCLT 13bj item 1 CLOSED in law (the passengers on the floor; the terminal one unit); the terminal's stands stay graded under their own law (the owner's "if needed" flattening is infeasible with the taxiways at KCLT — reported, not forced).

## 2026-09-13bo — OWNER (verbatim, on 13bn's name family): "Regarding bridge family, we can't rely on naming conventions across all airports. We always want to keep objects covering the same footprint together when changing their seat. Objects separated by lateral space, e.g. separate buildings, can move vertically independent of other buildings. Only time we allow actually cutting objects apart is for things like very long connecting pieces like the elevated rail at HECA which would require two buildings kilometers apart to be at the same elevation. Make sense? Interview me if needed to clarify." — INTERVIEWED: (1) "same footprint" = TOUCH OR OVERLAP within 0.5 m, CHAINED transitively (deck ↔ piers ↔ clutter); a piece touching nothing moves on its own; (2) the unit's datum: DECK, then PAD, then GROUND (a deck's abutment datum leads; else the pad plane of the pad most of the unit stands on; else the median ground under the unit's contacts); (3) a "very long connecting piece" = footprint span ≥ 200 m AND the two ends' ground differing ≥ 0.5 m (`visual_m`) → cut at line stations; everything shorter stays rigid. RULED (Fable, spec §16g THE FOOTPRINT UNIT): this ONE rule replaces every family derivation of the day — §16e (3)'s row / ring / footprint-contact / NAME attempts (13v, 13ae, 13bn: the name family is WITHDRAWN before a line was written; lane `v2bridgename` stood down clean), §16f (1)'s "shared authored datum plane" condition (dropped — overlap alone binds), §16f (4)'s partition by pad (a unit spanning two pads takes ONE datum by the priority rule; the design surface's §30 (4) cluster pad gives a big unit one pad). §16f (7) (a large terminal cluster is one unit on one pad, the apron flattened around it) STANDS as the design-surface side of the same law. Lane `v2clusterpad` (running, owns families and pads) is redirected onto §16g — the cluster IS the footprint unit; `v2spjc`'s §16f (8) (a ramp's ground bound net of authored relief) becomes moot under §16g (a ramp touching its terminal is in the unit; its low end sinks) — told. OTHH's bridges follow without a bridge-specific law: deck ↔ piers ↔ clutter chain by touch, the deck's datum leads.
* THE HECA RAIL CLASS: a body with span ≥ 200 m and ends' ground differing ≥ 0.5 m is cut at §10's line stations (the existing line-class machinery — the elevated rail already is); the census names every cut unit.

## Tool: pad_span_census

| `Ortho4XP/tools/pad_span_census.py` | The question is DOES THIS UNIT'S OWN DATUM FIT ITS BODIES' PADS — *how far apart do the emitted `building` pads one FOOTPRINT UNIT stands on actually stand?* — the single number owner RULINGS 2026-09-14c item 1 is accepted or refused on (spec `object-placement-spec.md` §16g (1)/(7)). No other instrument asks it: `harness/census.py` prices PAIRS OF VALUES, so an object seated 23.70 m above its own pad breaks no grade law and reports ZERO rows; `obj8_split_report.py` prints a body's anchor and its own ground but never asks whether the bodies sharing ONE unit's datum stand on pads that disagree; `role_overlap_read.py` is an AREA sweep and `role_edge_census.py` a boundary-length one. This is the unit-vs-pad reading: per unit, the `building` pads its bodies' FEET fall inside, how many bodies it holds, and the SPAN of those pads' planes, largest first. **It measures no law and counts no defects** — the pads are the emitted design surface's own `building` faces at `median(z)` over the ring, which is the plane `footprint_unit` reads through `anchor_rule.pad_plurality`, and the body→part join is the PART ID, never a proximity match (memory `canonical-identity-join`). `--over` (default 1.0 m) is the listing floor 14g stated its bar in, not a threshold with any standing. It takes either `o4_v2_placement_<ICAO>.json` or an `obj8_split_report --json` dump — both carry the same `splits` body records. Measured basis (scout `v2heca331` on the owner's 1.0.331 HECA): 17 units whose pads span > 1 m over 1,363 bodies, `fu:38:20` alone 978 bodies on 136 pads spanning 34.8 m — the unit chained on PART BOXES, and its DECK member then gave 96.20 to 1,509 bodies. Promoted 2026-09-14 from that scout's scratchpad `padspan.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse) — the 14g attribution, then lane `v2connector` round 3's before/after. Several patches are reported separately; quote it on identical options. Twin: `tests/test_pad_span_census.py` (the span IS the unit's own pads, a non-`building` face is not a pad, a unit on one pad is not a row, a body with no `unit_of` is not counted, the floor both ways, the CLI's JSON IS the library result, and this index row). |

## Tool: obj8_split_report

| `Ortho4XP/tools/obj8_split_report.py` | THE OBJ8 SPLIT, DRY-RUN (spec `object-placement-spec.md` §4 / §6 / §7; owner RULINGS 2026-09-11b) — what a pack's object stage becomes once placements are AGL, objects are cut into their RIGID BODIES and each body carries its own anchor. Reads only a build's own two products — the re-seat plan (`<ICAO>.rebake.json`: the pack read once, its welded parts and the ε-contact graph) and the emitted DESIGN SURFACE (`<ICAO>.graded.json`, whose `building` faces are the object pads and `structure_rim` breaklines the basin walls) — and NEVER opens the pack for writing, never reads the DSF and never builds anything. Prints per placement the bodies, their §6 class, each body's anchor point / reason / authored offset, the files that would be written and the placements KEPT WHOLE with the reason (`one_body`, `anim`, `unparsable`); `--write-into DIR` writes every cut file into a scratch dir and parses each back through `airport/obj8.parse_obj8` (LEMD 13,924 files, OTHH 65,360, all parsing back with the written triangle count, 2026-09-11); and prints §7's CENSUS — the design surface at a body's ANCHOR against the surface under each of its ground-contact FEET, the |Δ| histogram `seat_feet_census.py` prints from a mesh and a seat result, read instead from the plan and the design surface so the two are comparable. A foot or anchor outside every graded face reads `off-surface` and is never guessed at (the DEM governs there and this tool does not open the DEM). `--no-cut` for body counts only, `--filter`, `--json`, `--split-tol` to override `[placement] split_tol_m`. ROUND 2 (owner RULINGS 2026-09-11e, spec §9): the bodies are COARSENED (bodies of one placement whose intended-zero terrain heights agree within `split_tol_m` are one file, the senior body's anchor; an elevated body joins the nearest ground group) and each anchor is the GENERIC one (the footprint point where the design surface equals the body's zero; a body with authored relief beyond its skirt takes its low-side foot and is reported with the residual) — LEMD 302 placements -> 985 files (3.26x), OTHH 954 -> 1,172 (1.23x). §13 (owner RULINGS 2026-09-11r/s): an ELEVATED body — one whose lowest authored vertex, or the `y_zero` of the anchor the generic rule gives it, stands above `[rebake] elevated_base_m` — NEVER has a file of its own; it joins its CARRIER (the same placement's ground body with the largest plan overlap, else the nearest) at its authored offset, and a placement with NO ground body is KEPT WHOLE with reason `footless`. The report prints the two classes by name — `elevated bodies as own files` (BAR 0) and `footless placements kept whole` — because the FEET histogram cannot see this defect: the writer shifts an elevated body so its own lowest vertex lands on the terrain and every foot then reads perfect (LEMD's 218 roofs/decks/tower parts censused green while the sim was broken). Measured on matched pack copies: LEMD own-files 278 -> 0, files 1,099 -> 828, feet > 3 m 1,060 -> 151, worst 34.06 -> 13.75 m; OTHH 1,203 -> 333 files, feet > 3 m 952 -> 6. ROUND 3 (owner RULINGS 2026-09-11f, spec §10): the write half RESTORES every `<obj>.anchor_bak` in the pack before any file is written (counts in the plan's provenance), and a LINE OBJECT authored as one component is cut into SEGMENTS by triangle station (`--line-segment M` overrides `[placement] line_segment_m`; 0 disarms it) — LEMD 897 segments from 271 one-line bodies, 985 -> 1,086 files, census `> 3 m` 30 -> 25; OTHH 1,187 files, `> 3 m` 0. `--write-pack PACK_COPY` runs THE WHOLE WRITE HALF into a pack COPY through `airport/placement_write.apply_plan` (cut files, DSF + backup + provenance, dump-cache refresh, `o4_v2_placement_<ICAO>.json`) and reads the written DSF back; it REFUSES a live X-Plane install. The census also splits the feet over 0.3 m into BURIED (lawful) and FLOATING (the defect the eye reads). `--rows SUBSTR,SUBSTR` (lane `v2canopy4`) prints the PER-BODY rows of the placements named — the body's anchor (point, surface z, `y_zero`, reason), its ground-contact feet, its worst foot signed with |Δ|, and the 0.3 m verdict — for the owner's named sites (`OldTerminal_FSX-LEMD38,-LEMD84,-LEMD60`); it is a PROJECTION of the one census pass, never a second instrument (the bins, feet and worst list are identical with and without it, twinned). §14 (owner RULINGS 2026-09-11u/v, lane `v2carrier`): a FOOTLESS placement is CARRIED — written as a body file at its CARRIER's anchor with the carrier's `y_zero` (the footed body of its UNIT it abuts with the largest contact, else the nearest, else the largest) — a BASIN resource is never split and anchors at a RIM point where the design surface equals its zero (`rims` wired at last), and bodies of one resource that OVERLAP IN PLAN bind whatever the contact graph says. The report prints the four §14 bars (`footless at datum` 0, `footless on ground` 0, `basin bodies split` 0, `spread`) beside §13's, from `airport/placement_carrier.census_v14` — the same call `seat_feet_census --placement-plan` makes over the same plan shape, so the two instruments are one code path. Measured on the app's 1.0.315 LEMD frame: the four footbridge resources at the terminal's zero 616.65 (deck bottom road + 4.4-5.0 m, was ON the road), `Terminal4SAT_pink-LEMD01` at its terminal's 597.43, the basin's three resources one file each on ONE rim vertex (zero spread 7.0 m -> 0.00, parapet +2.99 above the rim), files 828 -> 855, round trip OK, row census `> 3 m` 17. Twin: `tests/auto_patch_v2/test_v2objsplit.py`. §15 (owner RULINGS 2026-09-11ae, lane `v2roofcarrier`): the CARRIER IS WHAT THE BODY STANDS OVER — chosen across the whole UNIT, every resource alike, by largest PLAN OVERLAP beneath, else largest contact, else nearest (§13's same-placement scope and §14's contact-first order are superseded; the pack names its roofs as their own resources, so the walls a roof rides are almost never its own file); the plan-overlap BOND is RE-CUT where a bound group's intended zeros span more than `split_tol_m` (a rigid body is never wider than the terrain it can stand on; BASIN exempt); DUPLICATE ROWS of one resource identical in lon/lat/heading are ONE placement, all of them replaced (`--write-pack` reports `duplicate rows of a SPLIT placement ... surviving after the write`, bar 0); an anchor or foot on no graded face is marked OFF-SHEET and excluded from every comparison and bar; and the report prints §15 (3)'s `stands-over float > 0.5 m` from `airport/placement_carrier.census_v15` — `float = zero - zero_beneath`, the class NEITHER the feet histogram nor §14's bars can see (a carried body has no feet at all), barred at 0 for CARRIED bodies and reported for footed ones. §16 (owner RULINGS 2026-09-11ai, lane `v2skipped`): the report adds the POPULATION census (`placement_carrier.census_population`: `rows on the datum outside the plan` — the resources the SEAT-era thickness gate dropped, which keep the pack's shared-datum row and render where the datum is, bar 0 — beside the lawful skips and the multi-anchor class, reported not barred) and `census_v16`'s `float = zero - ground_under_geometry`: the ground read under the body's OWN parts (`geom_box` / `foot_boxes`, the median of the part-box centres) and never under its carrier's box — `CARRIED bodies whose carrier's zero is over 1 m from the ground under their own geometry` (bar 0; LEMD 39 -> 0 on matched arms) and `files whose own-geometry ground departs over 3 m from the ground at their row` (26, reported). `--admit-skipped PACK_ROOT` puts the thickness-gated resources of a PRE-§16 plan back into the population by reading their rows from the pack's own DSF (one part per component, no contact graph, the member id IS the DSF row index) — what a build's own plan now carries, for replaying a plan written before the switch; LEMD 25 resources / 25 rows, OTHH 99. §16a (owner RULINGS 2026-09-11aj, lane `v2skipped2`): a CARRIED body is cut where its CARRIER is cut (one piece per carrier terrain group its own triangles stand over, each riding that group's zero; never by the ground under itself), the ground check moved to the carrier's OWN feet (`Candidate.ground_off`, `surface(foot) - y_foot` against the body's zero), and `census_v16`'s carried number demoted to INFORMATION — the bar for a carried body is §15 (3)'s `zero - zero_beneath`. The report prints `carried bodies left uncut by the ground` / `cut by their CARRIER into N piece(s)` and, beside the §15 bar, how many of the carried floats stand over a body the law REFUSES as a carrier. LEMD carried float 58 → 4, files 1,591 → 1,328, plan stage 9.9 → 6.3 s; OTHH 7 → 39, 46.4 → 60.2 s (both OTHH bars missed and reported). 11ak (lane `v2skipped3`): the CARRIED bar's `beneath` is the carrier THE LAW CHOSE (`merged_into`, resolved by identity over every row that reads a zero — a carrier written WHOLE names its MEMBER RESOURCE, which is the whole of OTHH's residual), and a body the law REFUSES as a carrier is counted and named as its own class, `carried over a refused body`, with how far its own feet stand off; §16 (2) also cuts BY FOOT (`placement_cut._LineCutter.foot_groups`: the feet grouped by the zero each says the body has, `surface(foot) - y_foot`, each triangle joining the group of the foot nearest it in plan) — the class no ground cut can see, a body whose FEET are authored over metres of relief on terrain that barely moves, which is exactly what §16a (2) refuses. The re-cut line prints the three cuts (terrain / triangle / foot). LEMD carried float 4 → 0, refused carriers 117 → 21 (13 of the residue are rim-anchored BASIN bodies the foot cut is exempt from), files 1,328 → 1,371, plan stage 6.2 → 5.66 s; OTHH carried 42 → 0, refused 55 → 19, files 1,679 → 1,622, plan stage 59 → 31 s (`solid_components` read in one sort instead of a mask per component; `bind_plan_overlaps` swept by the hull's south edge). 11al (lane `v2basincarry`): a BASIN body is EXEMPT from §16a (2)'s ground test — its zero is the RIM (§14 (2)) and its floor feet are authored below it by construction — so it may carry, and the report prints `§16a (2) basin carriers` (how many basins, how many the feet test would have refused) beside the refusal set: LEMD refused carriers 21 → 8, OTHH 19 → 4, carried float 0/0 unchanged. §14a (owner RULINGS 2026-09-11ap item 6, lane `v2basinring`): a BASIN body follows its RING. §24 (1) puts the rim vertices at the APRON's level, so the ring is not level (LEMD's T4 pit 597.68 … 599.52 over 59 nodes) while §14 (2) wrote every basin body at ONE rim point — the owner's "gap between wall and apron", +0.71 / −1.13 m, while the §14 `spread` bar read 0.01 because it measures the pit's bodies against EACH OTHER. `airport/basin_ring.py` (NEW: the whole law — `arcs_of`, `ring_arcs`, `member_kind`, `ring_bar`) cuts the ring into ARCS whose z agrees within `split_tol_m` and cuts each basin body's WALL BAND by them, one piece per arc anchored at that arc's rim point (the interior remainder keeps §14 (2)'s single point: the trench floor is one level); and a member authored AT THE RIM PLANE but standing inside the ring is a FLOOR body that takes §16 (3)'s ground under its own footprint, never the rim, never a carrier. The report prints the RE-DEFINED bar — `§14a spread of a BASIN RING = max |wall base − ring z| over its nodes` (bar ≤ `split_tol_m`), with the nodes on an arc the pit has NO WALL on reported beside it — and the `§14a basin FLOOR members` / `basin bodies cut by the ring's ARCS` counts. It needs the rings WITH their heights (`census_v14(rims=..., arc_cap=..., counts=...)`; `RimRing.z`, and the `basin_arc_wall:<ref>#<k>` counts keys the cut writes are how the bar tells "no wall here" from "the wall is written in the interior piece"). Matched arms on the app's 1.0.319 LEMD frame: the ring bar 1.12 m / 9 nodes over → **0.18 m / 0 over**, `LEMD13__b0` off the rim and onto its own ground, files 1,371 → 1,394, feet > 3 m 518 → 412, floating 9,509 → 9,014; OTHH's 21 basin carriers and its whole foot census byte-identical. §16b (owner RULINGS 2026-09-11ap, lane `v2owncut`): the TERRAIN CUT IS PRIOR AND UNIVERSAL and is read on the body's OWN WRITTEN TRIANGLES — including everything the writer will put in the file (`placement_cut._LineCutter.all_tris`: a placement the plan reads as ONE body is written as the WHOLE object, which is why `green-TEJ3`'s 4-triangle part read 0.22 m of ground while its 2,342 m file stood +16.22 m over it) — so a CARRIED body is divided by the ground under itself first and §16a (1)'s carrier cut runs inside each piece; §9's coarsening additionally requires PLAN CONTIGUITY (`[placement] coarsen_reach_m`, 30 m) and acts WITHIN a terrain group (the pieces carry the ground they stand on, or the very next pass welds them back); each PIECE finds its own carrier, and a FALLBACK candidate (contact / nearest / largest, no plan overlap) is refused unless its zero is within `split_tol_m` of the ground under the piece (`carrier_refused_far_from_carried_ground`). The report prints `census_v16b`'s two bars over the WRITTEN geometry the plan now publishes per body (`geom_pts`, one sample per 10 m cell, thinned to 32 by the farthest-point walk): `carried piece float over its own ground > 0.5 m` and `body wider than its terrain group`, both bar 0, with the BASIN exemptions (§14 (2) / 11al) counted apart and the wide residue split by class. `--coarsen-reach M` overrides the contiguity reach. Measured on the app's 1.0.319 LEMD frame: the owner's item 3 +10.74 → the plate ON the roof beneath it (618.58 vs the group's 618.60), item 5 +16.22 → 620.38 vs 620.27, `Terminal4_48` zero-vs-ground −4.02 → median −0.01, `Taxisigns-SENRG` 38 of 80 bodies over 0.3 m → 12 of 419; files 1,371 → 3,272 at the amended 100 m reach (4,633 at the refuted 30 m), plan stage 5.6 → 10.1 s (bar ≤ 8 s MISSED, reported). §16c (owner RULINGS 2026-09-12b/12d, lane `v2atom`): THE CONNECTED COMPONENT IS THE ATOM — `--torn-seams PACK_ROOT` prints the TORN-SEAM CENSUS over a WRITTEN pack (the plan argument is then the WRITTEN `o4_v2_placement_<ICAO>.json` and `--graded` is not read), and the same census prints automatically after `--write-pack`: sibling files of ONE placement that share an AUTHORED VERTEX (the key `obj8.solid_components` welds on, `round(x, 3)`) are two halves of one connected solid written at two zeros, with the base step per seam, the step histogram, the worst list and the per-class breakdown, and §10's line segments / §14a's basin arcs — the only lawful station cuts — counted APART.  Two bars, both 0: `torn seams outside line/arc pieces` and `single-component resources in >= 2 files`.  The instrument is the scout `v2lemd320`'s `tear.py`, promoted on its second use, and lives in `airport/placement_seams.py` (`census_torn_seams` / `census_torn_seams_lines`, re-exported through `placement_census`).  Measured on the live 1.0.320 LEMD pack it reproduces the owner's four sites exactly (`HANG3` 10 files / 14 seams worst 3.05 m; `green-LEMD50` 7 / 11.12 m; `Bridge2` 8 / 11.72 m; `green-STRT4` 53 files, `__b44` 16.29 m) and the class (2,554 seams, 1,994 over 0.30 m).  On matched replay arms the law takes LEMD 723 -> **0** seams and 128 -> **0** single-component splits (files 3,253 -> 2,804, plan stage 13.5 -> 10.2 s over 3 runs, round trip OK), OTHH 639 -> **1** and 165 -> **1** (files 1,897 -> 1,898). §16c (6) (RULINGS 2026-09-12h, round 2): `--contact-eps M` overrides `[placement] contact_eps_m` (2 mm) — components of ONE resource whose geometry comes within it, or whose parts the rebake plan's ε-contact graph already links, BIND into one rigid body for anchoring (one zero, the senior component's carrier): OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart that the millimetre weld key reads as separate.  LEMD files 2,804 -> 2,776, seams stay 0, `Terminal4_48` zero spread 3.58 -> 0.69 m, plan stage 9.6 s (main 13.5). ROUND 3 (RULINGS 2026-09-12j): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit (a round-2 OTHH `--admit-skipped` run had created `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` in the SHARED repo with both lane-local cache env vars exported and nothing refused it); every run prints `[guard] shared repo UNCHANGED`.  `--rigid-reach M` overrides `[placement] rigid_reach_m` (2.0) — §16c (8): SOLID components of one resource within it chain into ONE rigid cluster, which is the atom of the BODY as well as of the cut (LINE objects excluded).  `carrier_fill_min` is DELETED from carrier candidacy (§16c (7)); the CLASS exclusion stays.  LEMD: `HANG3` 6 files / 1.37 m -> 2 / 0.45, `green-STRT4` 23 -> 15 files (spread 8.90 -> 3.73), files 2,776 -> 2,121, §16b wide 1,405 -> 967, seams 0, round trip OK; five largest rigid clusters are all SINGLE components (5,157 / 2,890 / 2,514 m — fences and VOR markers, not chained) and `green-TEJ3` stays 9 components / 9 clusters. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. **§17 CRITICAL MOTION IS READ** (owner RULINGS 2026-09-12am (2), lane `v2objmotion`): the graded surface's FACE ROLE under every foot (`airport/placement_boxes.GradedRoles` / `graded_roles_from_doc`, built from the SAME parsed `<ICAO>.graded.json` the sampler and the pads are, senior face by `precedence.toml`'s authority order, a 55 m grid over the faces' boxes) joined to §7's own float there (`airport/placement_motion.census_motion`, re-exported through `placement_census`): a body with a foot on a ROLLED-ON face (`law.tables.rolled_on_roles`) is ON PAVEMENT and every such foot is judged at `[cockpit] motion_step_m` 0.05 m, named with resource, foot coordinate, face role and SIGN. The block prints the count of bodies on pavement, the feet over the threshold, the worst ten, and the breakdowns by resource / face role / body class / anchor rule / size band, plus what the EYE reads at those feet (floating vs buried over `visual_m`) and the MEDIAN-anchor arm. BASIN bodies are counted APART (§14 (2) / 11al: a pit's zero is its rim and its floor feet are authored below it — they were LEMD's whole worst ten). Measured on the 1.0.320 LEMD frame: 493 of 2,153 bodies stand on pavement, 7,124 feet on 399 over 0.05 m; after the §17 anchor rule 6,635 on 407 (OTHH 6,234 → 3,877 on 113 → 103). RULINGS 2026-09-12ap (lane `v2pavefeet`): `--motion-rows OUT.json` writes §17's PER-BODY projection — one row per written body with its anchor, class, anchor reason and every ground-contact foot (lat/lon, authored y, surface z, face role, on-pavement, float) — the rows `census_motion` itself reads, never a second census (the scout's scratchpad projection, promoted on its second use). (E) THE SAMPLER HONOURS GRADED HOLES: a Delaunay over the emitted VERTICES spans a hole ring with triangles reaching from an apron vertex to a trench vertex, and LEMD read **592.22 m at a point whose ROLE is apron** six metres outside the hole — 12ap's two worst pavement feet (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` −5.08) were that fabricated ramp, and the anchor correction is 6.91 m. A simplex CROSSING a hole ring with a step over `split_tol_m` is struck and a point inside one reads the nearest vertex of that simplex ON ITS OWN SIDE of the ring; measured narrowings: "centroid on no face" struck 8,689 of 47,287 simplices and cost 421 files / 435 off-sheet bodies, and a strike with no side-aware read cost 160. (B) §17 is judged at the GROUND-CONTACT feet — the in-band feet within `split_tol_m` of the lowest (`placement_motion.ground_contact_feet`); `contact_band_m` is shared law and unchanged, BOTH sets are sampled and the wider reading prints beside the judged one so the report states its own attribution. (A) `bind_ground_m` (`[cockpit] visual_m`) bounds §16c (7): a FOOTED body of ANOTHER member keeps the cluster only while its own zero is within it of the senior's, else it keeps its own anchor and is counted — the report prints `bound refused for ground N` with the worst refused disagreement and the widest RETAINED cluster zero-plane span. Matched arms, LEMD main → branch: CRITICAL MOTION 6,640 → 5,400 feet on 407 → 356 bodies, over 0.5 m FLOATING 663 → 128 and BURIED 1,109 → 808 (of which (B) alone 581 → 128 / 816 → 808), worst pavement foot +7.18 → +2.41 m, 74 binds refused (worst 2.38 m), files 2,107 → 2,149, seams 0/0, round trip OK, plan stage 10.19 → 10.03 s; OTHH 3,891 → 2,822 feet on 103 → 74, floating 332 → 12, §14 footless at datum 5 → 4, files 1,252 → 1,269, plan stage 60.8 → 61.4 s (the ≤ 60 s bar missed on BOTH arms). §16b's carried-piece float and wide counts move the WRONG way at both airports (LEMD 111 → 119 / 967 → 983, OTHH 126 → 135 / 75 → 78) and are named. §16d (owner RULINGS 2026-09-13h, lane `v2unboxed`): THE PLAN BOXES WHAT THE WRITER WRITES — a WRITTEN-FRAME bar beside the torn seams, `§16d bodies with written geometry > 1 m outside their geom_box` (`airport/placement_seams.census_outside_box`, printed after `--write-pack` and by `--torn-seams`, bar 0): `geom_box` was the hull of the ADMITTED PARTS while the writer emitted the source object's triangles regardless, so a component no part named (the FS2XPlane origin plate, an exporter's ground paint, a roof plate over the next hangar) rode a zero the body chose elsewhere and NO instrument read it — LEMD 1.0.325 live pack 378 of 2,109 bodies, 8 over a kilometre. Every connected component the writer will emit — draped ones included — is now PLACED: within `coarsen_reach_m` of a ground group's part hull it joins that group and `geom_box` grows to the hull of what the file will contain; beyond it, it is a FOOTLESS BODY §15's search places, or §16 (3)'s own ground (`--coarsen-reach 0` disarms the reach and the component joins the nearest body, the pre-§16d reading). The nearest-footed fallback is CAPPED at the same reach (`carrier_refused_nearest_beyond_reach`), and the COCKPIT block names the worst row by the centre of the BODY'S OWN written geometry, never the placement row (a shared-datum pack puts 96.5 % of its bodies on two points). `plan stage: N.NN s` is printed after the split — the number a round's budget is quoted in, timed exactly where the shipped engine's own `build_splits` call is, without the graded parse or the census. Matched dry arms on the 1.0.325 LEMD frame (the app's own arm reads a MESH sampler where the tool reads a Delaunay over the graded vertices — the two disagree on every surface-driven refusal and the bars are read dry-to-dry): outside-box 390 → **0**, nearest-footed over 100 m 29 → **0**, the four shadow plates +15.94/+15.73/+5.77/+1.72 → **−5.00 on their own ground**, `Cargo-TEJ1` on `NEWCO__b9` roof base 604.95 (bar 0.3 of 605.04), seams 0/0, §15 carried float 0/0, round trip OK, files 2,141 → 2,279, LEMD plan stage 13.6 → 17.8 s and OTHH ≈83 → 86.1 s (both bars missed on BOTH arms, named). It also fixed a latent WRITER defect: the cut file was named by its index in the LIVE body list while the DSF row is written on the plan's `body_id` name, so a body the cut left with no triangle shifted every later body's file one name down (`OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s object). §16d (4)-(6) (owner RULINGS 2026-09-13m, same lane, second frame KCLT 1.0.324): a CARRIED body's components group BY CARRIER — each ATOM (§16c (1)'s, so a rigid cluster is never divided) asks its own carrier question BEFORE the search, counted as `carried bodies cut by ATOM`, where §16a (1)'s after-the-fact cut could only divide the answer the whole body got (KCLT 5,295 carried bodies left uncut against 3 cut; a native pack's master roof model spans 1,774 m); §16c (7)'s 0.5 m ground bound is MEMBER-AGNOSTIC (12ap tested `member != top.member`, and a native pack's one-model-per-material member spans the airport: KCLT's `005_ALB__b9` sank 5.04 m into its pad on a same-member bind to an apron body 500 m away); and a FOOTED body whose ground contacts lie mostly inside one emitted `building` pad reads only the contacts ON it (`anchor_rule.pad_majority`; the anchor reason then says `on pad <ref>`). Matched dry arms at KCLT: `005_ALB__b9` -5.85 -> **+0.02** against its pad, widest retained cluster zero span 5.69 -> **0.64 m**, 473 carried bodies divided by atom, 61 bodies anchored on their pad, `building80`'s on-pad zero spread 1.03 m (the pad's own relief 1.19), §16d outside-box **0**, §15 carried float **0**, round trip OK 477/477, one new torn seam (+0.16 m, one shared vertex, named), files 473 -> 477, plan stage 8.65 -> 8.3-8.5 s. It also exposed a defect the atom cut made visible: a target group holding BOTH a cut piece and an untouched raw was read for its `tris` alone, leaving 990-3,280 triangles per placement claimed by no body (9 of KCLT's 103) for `obj8_split` to hand to the nearest one — the audit reads 0 of 103 after. **COST: plan stage LEMD 17.8 -> 25-46 s and OTHH 86 -> 136 s** (KCLT flat) — the per-atom carrier search, narrowed by a `coarsen_reach_m` span gate, a 64-atom cap, per-atom pids and a set-intersection contact count, and still needing the owner's approval and a Fable-5 review before it ships. |

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

## Registered frames: SPJC

SPJC  patch    base 95c78040   lane v2spjc327        2026-09-13T15:52:21  /tmp/harness/SPJC_20260913T154126.osm  — scout v2spjc327 SPJC build 2026-09-13, rc0 121.7s, body_sha e61277b2bbbc, artifact 7857e8587009, solve=feasible, guard UNCHANGED; reproduces owner 1.0.327 tile -13-078 structures line exactly
SPJC  graded   base 95c78040   lane v2spjc327        2026-09-13T15:52:21  /tmp/harness/SPJC_20260913T154126.v2/SPJC.graded.json  — scout v2spjc327 SPJC build 2026-09-13, rc0 121.7s, body_sha e61277b2bbbc, artifact 7857e8587009, solve=feasible, guard UNCHANGED; reproduces owner 1.0.327 tile -13-078 structures line exactly
SPJC  rebake   base 95c78040   lane v2spjc327        2026-09-13T15:52:21  /tmp/harness/SPJC_20260913T154126.v2/SPJC.rebake.json  — scout v2spjc327 SPJC build 2026-09-13, rc0 121.7s, body_sha e61277b2bbbc, artifact 7857e8587009, solve=feasible, guard UNCHANGED; reproduces owner 1.0.327 tile -13-078 structures line exactly
SPJC  patch    base 0c86fe2c   lane v2spjc           2026-09-13T17:03:04  /tmp/harness/v2spjc-r2.osm  — lane v2spjc closing SPJC build on claude/v2spjc 1992e754 (base main 0c86fe2c): rc0 111.2s, body_sha 0c903ea7b254, artifact 60993cdd0302, solve=optimal, guard UNCHANGED; structures bores 10 underpasses 0 tunnels 8 decks 0 refused 6 (scout base 95c78040: 59/19/18/4/31)
SPJC  graded   base 0c86fe2c   lane v2spjc           2026-09-13T17:03:04  /tmp/harness/v2spjc-r2.v2/SPJC.graded.json  — lane v2spjc closing SPJC build on claude/v2spjc 1992e754 (base main 0c86fe2c): rc0 111.2s, body_sha 0c903ea7b254, artifact 60993cdd0302, solve=optimal, guard UNCHANGED; structures bores 10 underpasses 0 tunnels 8 decks 0 refused 6 (scout base 95c78040: 59/19/18/4/31)
SPJC  rebake   base 0c86fe2c   lane v2spjc           2026-09-13T17:03:04  /tmp/harness/v2spjc-r2.v2/SPJC.rebake.json  — lane v2spjc closing SPJC build on claude/v2spjc 1992e754 (base main 0c86fe2c): rc0 111.2s, body_sha 0c903ea7b254, artifact 60993cdd0302, solve=optimal, guard UNCHANGED; structures bores 10 underpasses 0 tunnels 8 decks 0 refused 6 (scout base 95c78040: 59/19/18/4/31)
SPJC  patch    base 6ec68b44   lane v2connector      2026-09-13T21:58:13  /tmp/harness/SPJC_20260913T214930.osm  — lane v2connector closing SPJC build on claude/v2connector 9b67e568 (base main 6ec68b44): rc0 110.9s, body_sha 545886ed769d, artifact ledger 5fe4d215e11d, solve optimal, guard UNCHANGED — §16g (6) connector law: xp11_007__b0 / xp11_010__b0 members of fu:0:0@cluster_pad at 19.56, unit_connectors_cut 0, unit_split_authored 0
SPJC  graded   base 6ec68b44   lane v2connector      2026-09-13T21:58:13  /tmp/harness/SPJC_20260913T214930.v2/SPJC.graded.json  — lane v2connector closing SPJC build on claude/v2connector 9b67e568 (base main 6ec68b44): rc0 110.9s, body_sha 545886ed769d, artifact ledger 5fe4d215e11d, solve optimal, guard UNCHANGED — §16g (6) connector law: xp11_007__b0 / xp11_010__b0 members of fu:0:0@cluster_pad at 19.56, unit_connectors_cut 0, unit_split_authored 0
SPJC  rebake   base 6ec68b44   lane v2connector      2026-09-13T21:58:13  /tmp/harness/SPJC_20260913T214930.v2/SPJC.rebake.json  — lane v2connector closing SPJC build on claude/v2connector 9b67e568 (base main 6ec68b44): rc0 110.9s, body_sha 545886ed769d, artifact ledger 5fe4d215e11d, solve optimal, guard UNCHANGED — §16g (6) connector law: xp11_007__b0 / xp11_010__b0 members of fu:0:0@cluster_pad at 19.56, unit_connectors_cut 0, unit_split_authored 0

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

