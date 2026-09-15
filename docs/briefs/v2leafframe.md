# Brief pack — lane `v2leafframe`

Base: main `81b7596e` · generated 2026-09-14 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

The height_m frame bug (the leaf rule inert) + per-placement rows at their own feet (RULINGS 14bo)

## The brief

Two fixes (RULINGS 14bo has the whole attribution; scout readers in `…/scratchpad/lemd/` — `site.py`, `unit.py`, `msl.py`, `chain.py`, `counterfactual.py`, `float.py` — reuse; promote `site.py` (third use across HECA/LEMD) into `Ortho4XP/tools/` with an INDEX row + twin). (1) `Ortho4XP/src/auto_patch_v2/airport/pack_partition.py:672`: `Part.height_m` = `box_max[1] − box_min[1]` in ONE frame (both placed, or both authored — the authored component extent; say which and why; the comment at :669 claiming `box_max` is authored is wrong — `contact.py:345` places it). Twin: a placed part's `height_m` equals its authored extent regardless of anchor_z. Then §16g (10) (4)'s leaf rule is live in the UNIT derivation (`footprint_unit.py:465-468`, `chain_min_height_m` 2.5) — measure the unit census at LEMD dry (`obj8_split_report --json` on the registered rebake plan / the 1.0.336 products): chaining bodies 9,647 → ~4,958; the three giant units gone; items 2/4/6/9 in their own small clusters. (2) §16g (5) amended: in `airport/placement_plan.py` (the `OBJECT_MSL` row seat, `why="cluster_pad"`), a multi-anchor placement's elevation = the design surface at its OWN feet (its footprint's ground on `graded`) unless its footprint stands ON the unit's pad (then the pad); no graded face → the row stays plain `OBJECT` (AGL, drapes). Twin: a vehicle 44 m off the pad on apron 1 m above the pad datum seats at the apron. Bars: LEMD ONE build (`build_airport.py LEMD --tile 40 -4` — the object stage runs after the mesh; or the rebake replay on the 1.0.336 products for the seat reads + a patch build; say which): items 2 (40.4552413,−3.5687453 — Cargo-NEWCO/VRDCH/TEJ1 + 19 MSL rows), 4 (40.4981624,−3.5595534 — Runway ILS 1/2.obj, Taxisigns b266, wigwags), 6 (40.4980571,−3.5829243 — Terminal4_green-FT1T2), 9 (40.4841856,−3.5854064 — CNTRL b0/b1 + TEJ3 carried) each within 0.3 m of own ground; item 3's 7 rows (40.461514,−3.5732897) within 0.3 m of the apron; `OBJECT_MSL` rows > 0.5 m off 677 → ≤ 20 (named); bodies > 0.5 m off own ground 1,132 → by class before → after; largest unit span 2,855 → named; the SPJC viaduct 19.56 unchanged (dry); HECA/OTHH/KCLT unit censuses dry before → after. NOT yours: `constraints/`, `classify/`, `planar/`, `solve/`; lane v2padjoin is in constraints/cluster_pad.py + pads.py + footprint_unit.py's datum — coordinate: your `footprint_unit.py` edit is none (the leaf rule reads height_m; no change there); merge main before reporting.

## Bars

- `Part.height_m` = the authored extent (twin); LEMD chaining bodies 9,647 → ~4,958; the three 2–2.9 km units gone (largest unit span named).
- LEMD items 2/4/6/9: every body at the four coordinates within 0.3 m of its own ground; item 3's 7 `OBJECT_MSL` rows within 0.3 m of the apron.
- `OBJECT_MSL` rows > 0.5 m off the surface at their feet: 677 → ≤ 20 (named); bodies > 0.5 m off own ground 1,132 → by class before → after.
- HECA/OTHH/KCLT unit censuses dry before → after; SPJC viaduct 19.56 unchanged; suite twice; ONE LEMD build.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/pack_partition.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_plan.py`, `Ortho4XP/src/auto_patch_v2/airport/contact.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/constraints/`, `Ortho4XP/src/auto_patch_v2/classify/`, `Ortho4XP/src/auto_patch_v2/planar/`, `Ortho4XP/src/auto_patch_v2/solve/`

## Spec (object-placement) §16g (5)

### §16g (5) PER-PLACEMENT ELEVATION — `OBJECT_MSL` (Fable 2026-09-13; RULINGS 2026-09-13bw; owner 2026-09-11a/b) — lane `v2clusterpad` round 2

KCLT's passengers and seats (owner 13bj item 1) are among 205 multi-anchor
placements the plan DROPS ("one file cannot carry per-placement offsets");
no family law reaches them. The owner's 11a/11b instruction was the answer:
"if you're modifying the DSF, you can just change the elevation of each
placement."

5. A multi-anchor resource — one file, N placements needing N seats — is
   seated PER PLACEMENT by its DSF row: `OBJECT_MSL lat lon heading elev`,
   the elevation being the unit plane (or the body's own anchor) at that
   placement. No file copy, no per-file offset. The writer's round trip
   proves the rows parse; the census counts placements seated by row.

Round 2 also: §16g (1) derived PLAN-WIDE (after PASS 1 over all units,
before the carrier pool — the per-unit derivation left OTHH's bridges at
1.52 / 1.93 m spread); (2) polygon footprints, not part boxes.

BARS: KCLT passengers/seats at 35.2191877, −80.9426007 seated at the
cluster plane 222.28 ± 0.05 by `OBJECT_MSL`; dropped multi-anchor placements
205 → 0 at KCLT (count per airport); OTHH every `Bridge_NN` one unit, spread
0.00 (today 1.52 / 1.93); a MATCHED KCLT design base build — taxi family
byte-identical, pad flatness before → after; suite twice.

### §16g (5) AMENDED — THE FAMILY RELATION IS THE INVARIANT (owner RULINGS 2026-09-13cb; Fable 2026-09-13) — lane `v2clusterpad` round 2

Owner: placements grouped with a terminal "have to stay relative to the
object family they're grouped with, otherwise they are back to being on the
actual ground, rather than 'floating' on the second floor of the terminal
where the author placed them."

5. A placement in a footprint unit is seated at the UNIT'S DATUM plus its
   authored offset, wherever its anchor falls. "On ground" is only the case
   where the terrain at the anchor already equals the unit datum (within
   `hard_tol_m`) — then the row is left alone. Otherwise the row is written
   `OBJECT_MSL` = unit datum + authored offset. A pack's own `OBJECT_MSL` /
   `OBJECT_AGL` is read as the authored offset relative to the pack's
   authored ground, never kept as an absolute (the 11b conversion). Counted
   per airport: in a unit / left on ground / written MSL / converted.

BARS: KCLT's passengers/seats at 35.2191877, −80.9426007 at the cluster plane
+ their authored offset (on the floor the author placed them); a twin with an
anchor over apron beside the pad proves the `OBJECT_MSL` branch; dropped
multi-anchor placements 205 → 0.

### §16g (5) AMENDED — A PER-PLACEMENT ROW IS SEATED AT ITS OWN FEET (Fable 2026-09-14; RULINGS 2026-09-14bo) — lane `v2leafframe`

MEASURED (LEMD 1.0.336): 1,462 of 1,481 `OBJECT_MSL` rows sit at three
elevations — the datums of three airport-wide units welded by zero-height
quads that §16g (10) (4) should have made leaves but could not, because
`Part.height_m` mixed a placed maximum with an authored minimum.
1. `Part.height_m` is the authored extent in one frame.
2. A multi-anchor placement's `OBJECT_MSL` elevation is the design surface
   at that placement's own feet (its footprint's ground on the graded
   surface), unless its footprint stands on the unit's pad — then the pad.
   Where no graded face covers it, the row stays plain `OBJECT` (AGL).
BARS (LEMD, ONE build): items 2/4/6/9 each on their own ground (bodies
within 0.3 m of own ground at 40.4552413,−3.5687453; 40.4981624,−3.5595534;
40.4980571,−3.5829243; 40.4841856,−3.5854064); item 3's seven rows at their
apron level (40.461514,−3.5732897); `OBJECT_MSL` rows > 0.5 m off 677 → ≤
20 named; largest unit span 2,855 m → named; HECA/OTHH/KCLT unit censuses
dry before → after (the leaf rule live).

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

## 2026-09-14bo LEMD items 2/3/4/6/9 attributed (scout `v2lemd336o`): ONE mechanism — `Part.height_m` is computed in TWO FRAMES (placed max − authored min = an MSL number), so §16g (10) (4)'s leaf rule is INERT and three giant units (1,673 / 3,073 / 3,301 bodies, 2–2.9 km) weld the airport to three pad planes; item 3 = §16g (5) seating a vehicle at the unit datum — lane `v2leafframe`

`pack_partition.py:672` `round(box_max[1] − base_y)`: `box_max` is the
PLACED maximum (`contact.py:345`), `base_y` the AUTHORED minimum
(`:344`) — at LEMD `height_m` reads 580–646 m over all 29,684 parts,
so `chain_min_height_m` 2.5 passes 9,647 of 9,647 bodies and the leaf
rule removes NOTHING. The edge-carriers are the AESlite VOR quads
(4 vertices, authored extent 0.000 m, 2–2.6 M m², 3,300 edges each)
and the yellow carpets (0.8 m). Result: `fu:1:1@cluster_pad` 602.42
(`building4`, 2,855 m span), `fu:16:124` 597.08, `fu:10:47` 616.36;
1,462 of 1,481 `OBJECT_MSL` rows sit at exactly those three
elevations. Item 2 (cargo, 40.4552): +3.7 … +6.0 m on a pad 766 m
away; item 4 (ILS shacks/barriers, 40.4982): +4.3 … +5.5 (pad 647 m
away; the neighbours that fell OUT of the unit sit at −0.01); item 6
(blast shield): +4.3; item 9 (40.4842): 11ai's roof is FIXED (rides
its own walls at −0.02) — the CARRIER floats +3.5 on `building12` 439
m away. Item 3 (40.4615): 7 `OBJECT_MSL` vehicle rows −0.75 … −1.14 —
the SAME 602.42 plane with the apron 1 m above it; as plain `OBJECT`
they would drape right. Counterfactual with one frame: chaining
bodies 9,647 → 4,958; items 2/4/6/9 → clusters of 1/1/1/2 bodies;
item 3's Old Terminal district stays a genuine 524-body walled chain.
Census: `OBJECT_MSL` rows > 0.5 m off 677 of 1,481 (460 > 1 m); bodies
> 0.5 m off own ground 1,132 (663 > 1 m); skipped 73 (72 multi-anchor
+ the stock car); 564 pack rows still on their authored AGL row.

* RULING: (1) `Part.height_m` = the authored extent (`box_max[1] −
  box_min[1]` in ONE frame) — a one-expression fix that arms §16g (10)
  (4) at every airport (`pad_from_cluster` stays OFF; the leaf rule is
  the UNIT derivation's, live today). (2) §16g (5) AMENDED: a
  per-placement `OBJECT_MSL` row takes the DESIGN SURFACE AT ITS OWN
  FEET unless the placement's footprint stands on the unit's pad —
  a vehicle, loader, marker or sign on open apron 44 m from the pad
  is on the apron; where the surface is not graded there, the row
  stays plain `OBJECT` (AGL). Lane `v2leafframe`: ONE LEMD build;
  bars per site + the census (MSL rows off > 0.5 m 677 → ≤ 20, named;
  bodies off own ground 1,132 → named by class); HECA/OTHH/KCLT unit
  censuses dry (the leaf rule now live — the T3 district, `unit:43`).

## 2026-09-14bl Owner read of 1.0.336 LEMD ("very close, good work") — ten items; scouts `v2lemd336s` (structures) and `v2lemd336o` (objects)

Owner, verbatim: "LEMD is looking very close, good work. Bug reports:
1. There's a tunnel mouth here: 40.4614416, -3.5447633 that we are
not emitting, but looks correct because the DEM is already low there
and we are correctly setting the taxiway elevation on this side.
However the otherside where we do create a tunnel ramp it's cutting
deep into the taxiway and also distorting it. The mouth should stop
back about here: 40.4609913, -3.5445335 2. The buildings and various
cargo objects are floating here: 40.4552413, -3.5687453. They should
be separate buildings each seating on the ground. 3. In this area:
40.461514, -3.5732897 there's some object submerged about 1m
underground. 4. Barriers and small buildings around these two runway
ends are floating: 40.4981624, -3.5595534 5. The basin edge here:
40.4910254, -3.5681642 is allow a small gap between the outside wall
and the apron leaving a narrow visible canyon 6. The blast shield
object here 40.4980571, -3.5829243 is floating 7. The tunnel here is
placed way short of the mouth for some reason: 40.4987722, -3.584993.
The mouth should be here: 40.4980461, -3.5850118 8. The other side of
that tunnel's mouth should be between 40.4960195, -3.585058 and
40.4960167, -3.5849289 9. Building over here 40.4841856, -3.5854064 is
floating again 10. The bridge deck here: 40.4835044, -3.5801638 should
be a single smooth bridge, no small gap here, and it's two end points
are: 40.4835967, -3.580923 and 40.4835412, -3.5799114, that's bridge
extent to cover the terrain cutting down to the road running under it."

* Scout `v2lemd336s`: items 1, 5, 7, 8, 10 (the tunnel at 40.4614 —
  its ramp cutting into the taxiway, the mouth station vs the owner's
  40.4609913; the basin edge gap at 40.4910; the tunnel at 40.4988
  placed short of its mouth and the far mouth between the owner's two
  points; the bridge deck at 40.4835 — the gap, the two end points as
  the deck extent). Scout `v2lemd336o`: items 2, 3, 4, 6, 9 (units /
  pads / seats at each coordinate — separate buildings each on the
  ground = §16g (10)'s line; the submerged object; the barriers and
  small buildings at the runway ends; the blast shield; the building
  at 40.4842 "floating again" — 11ah's site).

## 2026-09-14ah v2padcluster round 1–2 STOPPED, NOT merged: derived pads as hard flat regions moved 13,637 airside vertices and made the terminal WORSE; the T3 district stays ONE 9,334-body cluster — the chain runs through SLABS; §16g (10) (4) written; round 3

Lane `v2padcluster` @ 6fdcb593 (HECA matched pair, law-value disarm:
`v2padclusterHECAdisarm` vs `v2padclusterHECA2`, ledger beb3e32ab119).
`geom/cluster_outline.py` (one outline derivation shared by classify
and constraints), `pad_from_cluster`, `floor_split_m`,
`pad_cluster_mismatch` family, `obj8_split_report --rows-near`.
Numbers: `pad_cluster_mismatch` 369 (r1) → 44 (41 clusters in > 1
piece, 3 pads spanning clusters); clusters on exactly one pad 206 →
322 of 1,400; building pad area 867 k → 1,370 k m² (652 faces);
**airside vertices moved > 0.02 m: 13,637 of 21,534, worst 10.14 m;
the runway itself 1,110 of 3,426, worst 4.38 m**; the terminal at
30.1279552, 31.403143 72.07 → 82.90 (+10.83; `T3_49.obj b4` 7.66 m
above its feet); constraints +57 %. Mechanism: 502,561 m² of new hard
flat pad (94,795 m² from apron, ~370,000 m² from faceless ground)
welded to the apron by 09-01g — the solve, not the map. Refuted by
measurement: (i) the T3 district does NOT resolve by floor level — its
footed bodies stand at 0.00 and −1.00 and genuinely touch → ONE
cluster of 9,334 bodies / 541,200 m²; (ii) reading the floor per
component splits tall buildings per storey (2,677 → 20,203). KCLT
control unchanged BY CONSTRUCTION (its plan carries no outlines).

* RULING §16g (10) (4) — WHAT CHAINS: a cluster chains only through
  bodies that have WALLS. A thin body — a floor slab, plate, deck,
  canopy, road, apron object, anything whose solid height is under
  `chain_min_height_m` (2.5 m) or that the object stage already
  classes as a deck/plate/pavement — is a LEAF: it is seated (on its
  own ground or its carrier) but is never a link between two walled
  bodies. HECA's T3 district chains through its authored ground
  slabs (`floor_more_yellow`, `T3_concrete_Yellow`, the 1,144 m
  "body" of 13cs); with slabs as leaves the district resolves into
  its buildings.
* RULING §16g (10) (5) — A DERIVED PAD NEVER TAKES AIRSIDE GROUND: the
  pad polygon is the cluster's outline CLIPPED by every airside face
  (runway family, taxi family, apron): airside is king, §30 (4)'s own
  clause. A cluster whose outline lies wholly on airside pavement gets
  no pad (its bodies seat on the pavement).
* Round 3 (RESUME): (4) and (5) at the derivation; bars: HECA airside
  vertices moved 0; the terminal at 72.50; `pad_cluster_mismatch`
  → 0 (a cluster in > 1 piece splits at its outline's connected
  components — the named lever, now ARMED); the seven buildings by
  coordinate (14g's table: 138 ≈ `building_texture_4 b7`, etc. — the
  lane reads `site.py`); constraints ≤ +10 %; KCLT: a BUILD carrying
  outlines is owed (dry is inert); SPJC 19.56 dry.

## 2026-09-13cb — OWNER (verbatim, on 13by): "Ahh, but like with the people on the ground problem, many placements of the same object can't just be set to 'on ground' because they have to stay relative to the object family they're grouped with, otherwise they are back to being on the actual ground, rather than 'floating' on the second floor of the terminal where the author placed them. Right?" — RIGHT. 13by stated the case, not the rule. §16g (5) AMENDED (the third time; this is the law): THE FAMILY RELATION IS THE INVARIANT — a placement in a footprint unit is seated at the UNIT'S DATUM plus its authored offset (its `OBJECT_AGL` / MSL offset, or the height its geometry is authored at above the row), wherever its anchor falls; "on ground" is only the CASE where the terrain at the anchor already equals the unit datum (to `hard_tol_m`, 0.02 m) — the cluster pad under the terminal — and there the row is left alone because rewriting it would change nothing. Everywhere else — an anchor over apron, a road, a sunken pier area, a deck, a terraced pad, any spot where the terrain at the anchor is not the unit's plane — the row is written `OBJECT_MSL` = unit datum + authored offset, so the piece floats on the second floor where the author put it, never dropped to the actual ground. A pack's own `OBJECT_MSL` / `OBJECT_AGL` rows are read as the authored offset RELATIVE to the pack's authored ground (the flat datum the pack was built on), not as absolute elevations to keep — that is the 11b conversion. The writer counts, per airport: placements in a unit / left on ground (terrain = datum) / written `OBJECT_MSL` / converted from the pack's MSL. Told to lane `v2clusterpad` (round 2): the passengers/seats bar is "seated at the cluster plane + their authored offset — on the floor where the author placed them — by whichever row form the terrain at the anchor requires", and a twin with an anchor over apron beside the pad proves the `OBJECT_MSL` branch.

## Tool: obj8_split_report

| `Ortho4XP/tools/obj8_split_report.py` | THE OBJ8 SPLIT, DRY-RUN (spec `object-placement-spec.md` §4 / §6 / §7; owner RULINGS 2026-09-11b) — what a pack's object stage becomes once placements are AGL, objects are cut into their RIGID BODIES and each body carries its own anchor. Reads only a build's own two products — the re-seat plan (`<ICAO>.rebake.json`: the pack read once, its welded parts and the ε-contact graph) and the emitted DESIGN SURFACE (`<ICAO>.graded.json`, whose `building` faces are the object pads and `structure_rim` breaklines the basin walls) — and NEVER opens the pack for writing, never reads the DSF and never builds anything. Prints per placement the bodies, their §6 class, each body's anchor point / reason / authored offset, the files that would be written and the placements KEPT WHOLE with the reason (`one_body`, `anim`, `unparsable`); `--write-into DIR` writes every cut file into a scratch dir and parses each back through `airport/obj8.parse_obj8` (LEMD 13,924 files, OTHH 65,360, all parsing back with the written triangle count, 2026-09-11); and prints §7's CENSUS — the design surface at a body's ANCHOR against the surface under each of its ground-contact FEET, the |Δ| histogram `seat_feet_census.py` prints from a mesh and a seat result, read instead from the plan and the design surface so the two are comparable. A foot or anchor outside every graded face reads `off-surface` and is never guessed at (the DEM governs there and this tool does not open the DEM). `--no-cut` for body counts only, `--filter`, `--json`, `--split-tol` to override `[placement] split_tol_m`. ROUND 2 (owner RULINGS 2026-09-11e, spec §9): the bodies are COARSENED (bodies of one placement whose intended-zero terrain heights agree within `split_tol_m` are one file, the senior body's anchor; an elevated body joins the nearest ground group) and each anchor is the GENERIC one (the footprint point where the design surface equals the body's zero; a body with authored relief beyond its skirt takes its low-side foot and is reported with the residual) — LEMD 302 placements -> 985 files (3.26x), OTHH 954 -> 1,172 (1.23x). §13 (owner RULINGS 2026-09-11r/s): an ELEVATED body — one whose lowest authored vertex, or the `y_zero` of the anchor the generic rule gives it, stands above `[rebake] elevated_base_m` — NEVER has a file of its own; it joins its CARRIER (the same placement's ground body with the largest plan overlap, else the nearest) at its authored offset, and a placement with NO ground body is KEPT WHOLE with reason `footless`. The report prints the two classes by name — `elevated bodies as own files` (BAR 0) and `footless placements kept whole` — because the FEET histogram cannot see this defect: the writer shifts an elevated body so its own lowest vertex lands on the terrain and every foot then reads perfect (LEMD's 218 roofs/decks/tower parts censused green while the sim was broken). Measured on matched pack copies: LEMD own-files 278 -> 0, files 1,099 -> 828, feet > 3 m 1,060 -> 151, worst 34.06 -> 13.75 m; OTHH 1,203 -> 333 files, feet > 3 m 952 -> 6. ROUND 3 (owner RULINGS 2026-09-11f, spec §10): the write half RESTORES every `<obj>.anchor_bak` in the pack before any file is written (counts in the plan's provenance), and a LINE OBJECT authored as one component is cut into SEGMENTS by triangle station (`--line-segment M` overrides `[placement] line_segment_m`; 0 disarms it) — LEMD 897 segments from 271 one-line bodies, 985 -> 1,086 files, census `> 3 m` 30 -> 25; OTHH 1,187 files, `> 3 m` 0. `--write-pack PACK_COPY` runs THE WHOLE WRITE HALF into a pack COPY through `airport/placement_write.apply_plan` (cut files, DSF + backup + provenance, dump-cache refresh, `o4_v2_placement_<ICAO>.json`) and reads the written DSF back; it REFUSES a live X-Plane install. The census also splits the feet over 0.3 m into BURIED (lawful) and FLOATING (the defect the eye reads). `--rows-near LAT,LON[,R]` (lane `v2padcluster`, 2026-09-14) is that SAME projection selected BY PLACE — every body whose ANCHOR is within R metres (default 40) of the coordinate, nearest first, each row carrying its `site_m` — because the owner names a defect by coordinate and the shapeIDs in a report go stale between builds while a coordinate does not; `osm_site --at/--contains` answers the other half of a site question (which emitted FACES cover the point) and is not re-spelled here. Promoted from the scout `v2heca331`'s scratchpad `site.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse): the 14g attribution, then §16g (10)'s per-site bars; its graded-face half was already `osm_site`'s and was NOT copied. Twin: `tests/auto_patch_v2/test_v2objsplit.py::test_rows_near_selects_the_same_rows_BY_PLACE`. `--rows SUBSTR,SUBSTR` (lane `v2canopy4`) prints the PER-BODY rows of the placements named — the body's anchor (point, surface z, `y_zero`, reason), its ground-contact feet, its worst foot signed with |Δ|, and the 0.3 m verdict — for the owner's named sites (`OldTerminal_FSX-LEMD38,-LEMD84,-LEMD60`); it is a PROJECTION of the one census pass, never a second instrument (the bins, feet and worst list are identical with and without it, twinned). §14 (owner RULINGS 2026-09-11u/v, lane `v2carrier`): a FOOTLESS placement is CARRIED — written as a body file at its CARRIER's anchor with the carrier's `y_zero` (the footed body of its UNIT it abuts with the largest contact, else the nearest, else the largest) — a BASIN resource is never split and anchors at a RIM point where the design surface equals its zero (`rims` wired at last), and bodies of one resource that OVERLAP IN PLAN bind whatever the contact graph says. The report prints the four §14 bars (`footless at datum` 0, `footless on ground` 0, `basin bodies split` 0, `spread`) beside §13's, from `airport/placement_carrier.census_v14` — the same call `seat_feet_census --placement-plan` makes over the same plan shape, so the two instruments are one code path. Measured on the app's 1.0.315 LEMD frame: the four footbridge resources at the terminal's zero 616.65 (deck bottom road + 4.4-5.0 m, was ON the road), `Terminal4SAT_pink-LEMD01` at its terminal's 597.43, the basin's three resources one file each on ONE rim vertex (zero spread 7.0 m -> 0.00, parapet +2.99 above the rim), files 828 -> 855, round trip OK, row census `> 3 m` 17. Twin: `tests/auto_patch_v2/test_v2objsplit.py`. §15 (owner RULINGS 2026-09-11ae, lane `v2roofcarrier`): the CARRIER IS WHAT THE BODY STANDS OVER — chosen across the whole UNIT, every resource alike, by largest PLAN OVERLAP beneath, else largest contact, else nearest (§13's same-placement scope and §14's contact-first order are superseded; the pack names its roofs as their own resources, so the walls a roof rides are almost never its own file); the plan-overlap BOND is RE-CUT where a bound group's intended zeros span more than `split_tol_m` (a rigid body is never wider than the terrain it can stand on; BASIN exempt); DUPLICATE ROWS of one resource identical in lon/lat/heading are ONE placement, all of them replaced (`--write-pack` reports `duplicate rows of a SPLIT placement ... surviving after the write`, bar 0); an anchor or foot on no graded face is marked OFF-SHEET and excluded from every comparison and bar; and the report prints §15 (3)'s `stands-over float > 0.5 m` from `airport/placement_carrier.census_v15` — `float = zero - zero_beneath`, the class NEITHER the feet histogram nor §14's bars can see (a carried body has no feet at all), barred at 0 for CARRIED bodies and reported for footed ones. §16 (owner RULINGS 2026-09-11ai, lane `v2skipped`): the report adds the POPULATION census (`placement_carrier.census_population`: `rows on the datum outside the plan` — the resources the SEAT-era thickness gate dropped, which keep the pack's shared-datum row and render where the datum is, bar 0 — beside the lawful skips and the multi-anchor class, reported not barred) and `census_v16`'s `float = zero - ground_under_geometry`: the ground read under the body's OWN parts (`geom_box` / `foot_boxes`, the median of the part-box centres) and never under its carrier's box — `CARRIED bodies whose carrier's zero is over 1 m from the ground under their own geometry` (bar 0; LEMD 39 -> 0 on matched arms) and `files whose own-geometry ground departs over 3 m from the ground at their row` (26, reported). `--admit-skipped PACK_ROOT` puts the thickness-gated resources of a PRE-§16 plan back into the population by reading their rows from the pack's own DSF (one part per component, no contact graph, the member id IS the DSF row index) — what a build's own plan now carries, for replaying a plan written before the switch; LEMD 25 resources / 25 rows, OTHH 99. §16a (owner RULINGS 2026-09-11aj, lane `v2skipped2`): a CARRIED body is cut where its CARRIER is cut (one piece per carrier terrain group its own triangles stand over, each riding that group's zero; never by the ground under itself), the ground check moved to the carrier's OWN feet (`Candidate.ground_off`, `surface(foot) - y_foot` against the body's zero), and `census_v16`'s carried number demoted to INFORMATION — the bar for a carried body is §15 (3)'s `zero - zero_beneath`. The report prints `carried bodies left uncut by the ground` / `cut by their CARRIER into N piece(s)` and, beside the §15 bar, how many of the carried floats stand over a body the law REFUSES as a carrier. LEMD carried float 58 → 4, files 1,591 → 1,328, plan stage 9.9 → 6.3 s; OTHH 7 → 39, 46.4 → 60.2 s (both OTHH bars missed and reported). 11ak (lane `v2skipped3`): the CARRIED bar's `beneath` is the carrier THE LAW CHOSE (`merged_into`, resolved by identity over every row that reads a zero — a carrier written WHOLE names its MEMBER RESOURCE, which is the whole of OTHH's residual), and a body the law REFUSES as a carrier is counted and named as its own class, `carried over a refused body`, with how far its own feet stand off; §16 (2) also cuts BY FOOT (`placement_cut._LineCutter.foot_groups`: the feet grouped by the zero each says the body has, `surface(foot) - y_foot`, each triangle joining the group of the foot nearest it in plan) — the class no ground cut can see, a body whose FEET are authored over metres of relief on terrain that barely moves, which is exactly what §16a (2) refuses. The re-cut line prints the three cuts (terrain / triangle / foot). LEMD carried float 4 → 0, refused carriers 117 → 21 (13 of the residue are rim-anchored BASIN bodies the foot cut is exempt from), files 1,328 → 1,371, plan stage 6.2 → 5.66 s; OTHH carried 42 → 0, refused 55 → 19, files 1,679 → 1,622, plan stage 59 → 31 s (`solid_components` read in one sort instead of a mask per component; `bind_plan_overlaps` swept by the hull's south edge). 11al (lane `v2basincarry`): a BASIN body is EXEMPT from §16a (2)'s ground test — its zero is the RIM (§14 (2)) and its floor feet are authored below it by construction — so it may carry, and the report prints `§16a (2) basin carriers` (how many basins, how many the feet test would have refused) beside the refusal set: LEMD refused carriers 21 → 8, OTHH 19 → 4, carried float 0/0 unchanged. §14a (owner RULINGS 2026-09-11ap item 6, lane `v2basinring`): a BASIN body follows its RING. §24 (1) puts the rim vertices at the APRON's level, so the ring is not level (LEMD's T4 pit 597.68 … 599.52 over 59 nodes) while §14 (2) wrote every basin body at ONE rim point — the owner's "gap between wall and apron", +0.71 / −1.13 m, while the §14 `spread` bar read 0.01 because it measures the pit's bodies against EACH OTHER. `airport/basin_ring.py` (NEW: the whole law — `arcs_of`, `ring_arcs`, `member_kind`, `ring_bar`) cuts the ring into ARCS whose z agrees within `split_tol_m` and cuts each basin body's WALL BAND by them, one piece per arc anchored at that arc's rim point (the interior remainder keeps §14 (2)'s single point: the trench floor is one level); and a member authored AT THE RIM PLANE but standing inside the ring is a FLOOR body that takes §16 (3)'s ground under its own footprint, never the rim, never a carrier. The report prints the RE-DEFINED bar — `§14a spread of a BASIN RING = max |wall base − ring z| over its nodes` (bar ≤ `split_tol_m`), with the nodes on an arc the pit has NO WALL on reported beside it — and the `§14a basin FLOOR members` / `basin bodies cut by the ring's ARCS` counts. It needs the rings WITH their heights (`census_v14(rims=..., arc_cap=..., counts=...)`; `RimRing.z`, and the `basin_arc_wall:<ref>#<k>` counts keys the cut writes are how the bar tells "no wall here" from "the wall is written in the interior piece"). Matched arms on the app's 1.0.319 LEMD frame: the ring bar 1.12 m / 9 nodes over → **0.18 m / 0 over**, `LEMD13__b0` off the rim and onto its own ground, files 1,371 → 1,394, feet > 3 m 518 → 412, floating 9,509 → 9,014; OTHH's 21 basin carriers and its whole foot census byte-identical. §16b (owner RULINGS 2026-09-11ap, lane `v2owncut`): the TERRAIN CUT IS PRIOR AND UNIVERSAL and is read on the body's OWN WRITTEN TRIANGLES — including everything the writer will put in the file (`placement_cut._LineCutter.all_tris`: a placement the plan reads as ONE body is written as the WHOLE object, which is why `green-TEJ3`'s 4-triangle part read 0.22 m of ground while its 2,342 m file stood +16.22 m over it) — so a CARRIED body is divided by the ground under itself first and §16a (1)'s carrier cut runs inside each piece; §9's coarsening additionally requires PLAN CONTIGUITY (`[placement] coarsen_reach_m`, 30 m) and acts WITHIN a terrain group (the pieces carry the ground they stand on, or the very next pass welds them back); each PIECE finds its own carrier, and a FALLBACK candidate (contact / nearest / largest, no plan overlap) is refused unless its zero is within `split_tol_m` of the ground under the piece (`carrier_refused_far_from_carried_ground`). The report prints `census_v16b`'s two bars over the WRITTEN geometry the plan now publishes per body (`geom_pts`, one sample per 10 m cell, thinned to 32 by the farthest-point walk): `carried piece float over its own ground > 0.5 m` and `body wider than its terrain group`, both bar 0, with the BASIN exemptions (§14 (2) / 11al) counted apart and the wide residue split by class. `--coarsen-reach M` overrides the contiguity reach. Measured on the app's 1.0.319 LEMD frame: the owner's item 3 +10.74 → the plate ON the roof beneath it (618.58 vs the group's 618.60), item 5 +16.22 → 620.38 vs 620.27, `Terminal4_48` zero-vs-ground −4.02 → median −0.01, `Taxisigns-SENRG` 38 of 80 bodies over 0.3 m → 12 of 419; files 1,371 → 3,272 at the amended 100 m reach (4,633 at the refuted 30 m), plan stage 5.6 → 10.1 s (bar ≤ 8 s MISSED, reported). §16c (owner RULINGS 2026-09-12b/12d, lane `v2atom`): THE CONNECTED COMPONENT IS THE ATOM — `--torn-seams PACK_ROOT` prints the TORN-SEAM CENSUS over a WRITTEN pack (the plan argument is then the WRITTEN `o4_v2_placement_<ICAO>.json` and `--graded` is not read), and the same census prints automatically after `--write-pack`: sibling files of ONE placement that share an AUTHORED VERTEX (the key `obj8.solid_components` welds on, `round(x, 3)`) are two halves of one connected solid written at two zeros, with the base step per seam, the step histogram, the worst list and the per-class breakdown, and §10's line segments / §14a's basin arcs — the only lawful station cuts — counted APART.  Two bars, both 0: `torn seams outside line/arc pieces` and `single-component resources in >= 2 files`.  The instrument is the scout `v2lemd320`'s `tear.py`, promoted on its second use, and lives in `airport/placement_seams.py` (`census_torn_seams` / `census_torn_seams_lines`, re-exported through `placement_census`).  Measured on the live 1.0.320 LEMD pack it reproduces the owner's four sites exactly (`HANG3` 10 files / 14 seams worst 3.05 m; `green-LEMD50` 7 / 11.12 m; `Bridge2` 8 / 11.72 m; `green-STRT4` 53 files, `__b44` 16.29 m) and the class (2,554 seams, 1,994 over 0.30 m).  On matched replay arms the law takes LEMD 723 -> **0** seams and 128 -> **0** single-component splits (files 3,253 -> 2,804, plan stage 13.5 -> 10.2 s over 3 runs, round trip OK), OTHH 639 -> **1** and 165 -> **1** (files 1,897 -> 1,898). §16c (6) (RULINGS 2026-09-12h, round 2): `--contact-eps M` overrides `[placement] contact_eps_m` (2 mm) — components of ONE resource whose geometry comes within it, or whose parts the rebake plan's ε-contact graph already links, BIND into one rigid body for anchoring (one zero, the senior component's carrier): OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart that the millimetre weld key reads as separate.  LEMD files 2,804 -> 2,776, seams stay 0, `Terminal4_48` zero spread 3.58 -> 0.69 m, plan stage 9.6 s (main 13.5). ROUND 3 (RULINGS 2026-09-12j): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit (a round-2 OTHH `--admit-skipped` run had created `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` in the SHARED repo with both lane-local cache env vars exported and nothing refused it); every run prints `[guard] shared repo UNCHANGED`.  `--rigid-reach M` overrides `[placement] rigid_reach_m` (2.0) — §16c (8): SOLID components of one resource within it chain into ONE rigid cluster, which is the atom of the BODY as well as of the cut (LINE objects excluded).  `carrier_fill_min` is DELETED from carrier candidacy (§16c (7)); the CLASS exclusion stays.  LEMD: `HANG3` 6 files / 1.37 m -> 2 / 0.45, `green-STRT4` 23 -> 15 files (spread 8.90 -> 3.73), files 2,776 -> 2,121, §16b wide 1,405 -> 967, seams 0, round trip OK; five largest rigid clusters are all SINGLE components (5,157 / 2,890 / 2,514 m — fences and VOR markers, not chained) and `green-TEJ3` stays 9 components / 9 clusters. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. **§17 CRITICAL MOTION IS READ** (owner RULINGS 2026-09-12am (2), lane `v2objmotion`): the graded surface's FACE ROLE under every foot (`airport/placement_boxes.GradedRoles` / `graded_roles_from_doc`, built from the SAME parsed `<ICAO>.graded.json` the sampler and the pads are, senior face by `precedence.toml`'s authority order, a 55 m grid over the faces' boxes) joined to §7's own float there (`airport/placement_motion.census_motion`, re-exported through `placement_census`): a body with a foot on a ROLLED-ON face (`law.tables.rolled_on_roles`) is ON PAVEMENT and every such foot is judged at `[cockpit] motion_step_m` 0.05 m, named with resource, foot coordinate, face role and SIGN. The block prints the count of bodies on pavement, the feet over the threshold, the worst ten, and the breakdowns by resource / face role / body class / anchor rule / size band, plus what the EYE reads at those feet (floating vs buried over `visual_m`) and the MEDIAN-anchor arm. BASIN bodies are counted APART (§14 (2) / 11al: a pit's zero is its rim and its floor feet are authored below it — they were LEMD's whole worst ten). Measured on the 1.0.320 LEMD frame: 493 of 2,153 bodies stand on pavement, 7,124 feet on 399 over 0.05 m; after the §17 anchor rule 6,635 on 407 (OTHH 6,234 → 3,877 on 113 → 103). RULINGS 2026-09-12ap (lane `v2pavefeet`): `--motion-rows OUT.json` writes §17's PER-BODY projection — one row per written body with its anchor, class, anchor reason and every ground-contact foot (lat/lon, authored y, surface z, face role, on-pavement, float) — the rows `census_motion` itself reads, never a second census (the scout's scratchpad projection, promoted on its second use). (E) THE SAMPLER HONOURS GRADED HOLES: a Delaunay over the emitted VERTICES spans a hole ring with triangles reaching from an apron vertex to a trench vertex, and LEMD read **592.22 m at a point whose ROLE is apron** six metres outside the hole — 12ap's two worst pavement feet (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` −5.08) were that fabricated ramp, and the anchor correction is 6.91 m. A simplex CROSSING a hole ring with a step over `split_tol_m` is struck and a point inside one reads the nearest vertex of that simplex ON ITS OWN SIDE of the ring; measured narrowings: "centroid on no face" struck 8,689 of 47,287 simplices and cost 421 files / 435 off-sheet bodies, and a strike with no side-aware read cost 160. (B) §17 is judged at the GROUND-CONTACT feet — the in-band feet within `split_tol_m` of the lowest (`placement_motion.ground_contact_feet`); `contact_band_m` is shared law and unchanged, BOTH sets are sampled and the wider reading prints beside the judged one so the report states its own attribution. (A) `bind_ground_m` (`[cockpit] visual_m`) bounds §16c (7): a FOOTED body of ANOTHER member keeps the cluster only while its own zero is within it of the senior's, else it keeps its own anchor and is counted — the report prints `bound refused for ground N` with the worst refused disagreement and the widest RETAINED cluster zero-plane span. Matched arms, LEMD main → branch: CRITICAL MOTION 6,640 → 5,400 feet on 407 → 356 bodies, over 0.5 m FLOATING 663 → 128 and BURIED 1,109 → 808 (of which (B) alone 581 → 128 / 816 → 808), worst pavement foot +7.18 → +2.41 m, 74 binds refused (worst 2.38 m), files 2,107 → 2,149, seams 0/0, round trip OK, plan stage 10.19 → 10.03 s; OTHH 3,891 → 2,822 feet on 103 → 74, floating 332 → 12, §14 footless at datum 5 → 4, files 1,252 → 1,269, plan stage 60.8 → 61.4 s (the ≤ 60 s bar missed on BOTH arms). §16b's carried-piece float and wide counts move the WRONG way at both airports (LEMD 111 → 119 / 967 → 983, OTHH 126 → 135 / 75 → 78) and are named. §16d (owner RULINGS 2026-09-13h, lane `v2unboxed`): THE PLAN BOXES WHAT THE WRITER WRITES — a WRITTEN-FRAME bar beside the torn seams, `§16d bodies with written geometry > 1 m outside their geom_box` (`airport/placement_seams.census_outside_box`, printed after `--write-pack` and by `--torn-seams`, bar 0): `geom_box` was the hull of the ADMITTED PARTS while the writer emitted the source object's triangles regardless, so a component no part named (the FS2XPlane origin plate, an exporter's ground paint, a roof plate over the next hangar) rode a zero the body chose elsewhere and NO instrument read it — LEMD 1.0.325 live pack 378 of 2,109 bodies, 8 over a kilometre. Every connected component the writer will emit — draped ones included — is now PLACED: within `coarsen_reach_m` of a ground group's part hull it joins that group and `geom_box` grows to the hull of what the file will contain; beyond it, it is a FOOTLESS BODY §15's search places, or §16 (3)'s own ground (`--coarsen-reach 0` disarms the reach and the component joins the nearest body, the pre-§16d reading). The nearest-footed fallback is CAPPED at the same reach (`carrier_refused_nearest_beyond_reach`), and the COCKPIT block names the worst row by the centre of the BODY'S OWN written geometry, never the placement row (a shared-datum pack puts 96.5 % of its bodies on two points). `plan stage: N.NN s` is printed after the split — the number a round's budget is quoted in, timed exactly where the shipped engine's own `build_splits` call is, without the graded parse or the census. Matched dry arms on the 1.0.325 LEMD frame (the app's own arm reads a MESH sampler where the tool reads a Delaunay over the graded vertices — the two disagree on every surface-driven refusal and the bars are read dry-to-dry): outside-box 390 → **0**, nearest-footed over 100 m 29 → **0**, the four shadow plates +15.94/+15.73/+5.77/+1.72 → **−5.00 on their own ground**, `Cargo-TEJ1` on `NEWCO__b9` roof base 604.95 (bar 0.3 of 605.04), seams 0/0, §15 carried float 0/0, round trip OK, files 2,141 → 2,279, LEMD plan stage 13.6 → 17.8 s and OTHH ≈83 → 86.1 s (both bars missed on BOTH arms, named). It also fixed a latent WRITER defect: the cut file was named by its index in the LIVE body list while the DSF row is written on the plan's `body_id` name, so a body the cut left with no triangle shifted every later body's file one name down (`OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s object). §16d (4)-(6) (owner RULINGS 2026-09-13m, same lane, second frame KCLT 1.0.324): a CARRIED body's components group BY CARRIER — each ATOM (§16c (1)'s, so a rigid cluster is never divided) asks its own carrier question BEFORE the search, counted as `carried bodies cut by ATOM`, where §16a (1)'s after-the-fact cut could only divide the answer the whole body got (KCLT 5,295 carried bodies left uncut against 3 cut; a native pack's master roof model spans 1,774 m); §16c (7)'s 0.5 m ground bound is MEMBER-AGNOSTIC (12ap tested `member != top.member`, and a native pack's one-model-per-material member spans the airport: KCLT's `005_ALB__b9` sank 5.04 m into its pad on a same-member bind to an apron body 500 m away); and a FOOTED body whose ground contacts lie mostly inside one emitted `building` pad reads only the contacts ON it (`anchor_rule.pad_majority`; the anchor reason then says `on pad <ref>`). Matched dry arms at KCLT: `005_ALB__b9` -5.85 -> **+0.02** against its pad, widest retained cluster zero span 5.69 -> **0.64 m**, 473 carried bodies divided by atom, 61 bodies anchored on their pad, `building80`'s on-pad zero spread 1.03 m (the pad's own relief 1.19), §16d outside-box **0**, §15 carried float **0**, round trip OK 477/477, one new torn seam (+0.16 m, one shared vertex, named), files 473 -> 477, plan stage 8.65 -> 8.3-8.5 s. It also exposed a defect the atom cut made visible: a target group holding BOTH a cut piece and an untouched raw was read for its `tris` alone, leaving 990-3,280 triangles per placement claimed by no body (9 of KCLT's 103) for `obj8_split` to hand to the nearest one — the audit reads 0 of 103 after. **COST: plan stage LEMD 17.8 -> 25-46 s and OTHH 86 -> 136 s** (KCLT flat) — the per-atom carrier search, narrowed by a `coarsen_reach_m` span gate, a 64-atom cap, per-atom pids and a set-intersection contact count, and still needing the owner's approval and a Fable-5 review before it ships. |

## Tool: seat_feet_census

| `Ortho4XP/tools/seat_feet_census.py` | THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3); the placement reading 11e (3), spec §7/§9) — `--placement-plan o4_v2_placement_<ICAO>.json` with `--mesh` (a built mesh) or `--graded` (the emitted design surface, for a dry run with no tile built): per placement of the plan's own rows, `surface(foot) − (surface(anchor) + y_foot)`, the |Δ| histogram (<0.3 / 0.3-1 / 1-3 / >3 m), the same by class, the worst N with lat/lon, and §13's elevated-body / footless-carrier bars. Feet are read from the AUTHORED pack (`.anchor_bak` when one exists). THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8) — the name is kept because the INDEX row, `obj8_split_report` and the twins address it by it. Writes nothing to the pack. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. CRITICAL MOTION is named as an instrument limit rather than printed as a zero HERE: §17's motion reading needs the graded face ROLE under each foot, and this tool hands the block none — `obj8_split_report.py` is the entry that takes it (owner RULINGS 2026-09-12am (2), lane `v2objmotion`). §16e (owner RULINGS 2026-09-13k, lane `v2othhdatums`): `--placement-plan --mesh` WAS BROKEN — it passed its bbox as `(lat, lon)` to `MeshElevationSampler`, which takes `(min_lon, min_lat, max_lon, max_lat)`, so at OTHH it asked for a box at lon 25.2 / lat 51.6 and the sampler raised `no mesh triangles inside ... — wrong tile?`; the one place the two orders meet is now `plan_bounds()` and a twin holds it end to end over the sampler's own mesh fixture. The report also prints `§16e bodies on a DATUM` (a crest plate / a deck top) as its own class and EXCLUDES them from §13's `elevated bodies as own files` bar: a datum body's `y_zero` is +5 … +10 m by construction, and counting it there reported the law as the defect (OTHH 0 -> 10 -> 0 with the class printed apart). §16e (3) (Fable 2026-09-13, RULINGS 2026-09-13v, lane `v2bridgecontact`): the report also prints THE BRIDGE FAMILY block (`airport/bridge_family.census_bridges` / `census_bridges_lines`, re-exported through `placement_census`, the same call `obj8_split_report` makes over the same plan shape) — per `Bridge_NN` the deck's own body's world DECK TOP against the land under that bridge's own written geometry (`|deck top - highest land|`, bar `[cockpit] visual_m` 0.5 m), the PER-PLACEMENT zero spread (`max - min` of `surface_z - y_zero` over one placement's bodies; `Bridge_02_CLUTTER_007` is six piers of ONE solid), the CROSS-BRIDGE carriers (a body whose `merged_into` names a file of another bridge, bar 0) and how many bodies publish `bridge_of` and agree with the resource's own tag. The `Bridge_NN` axis is the CENSUS's, never the law's — §16e (3) exists because the name does not name a bridge — so the agreement count is the instrument's own check on the derived relation. Measured on the app's 1.0.326 OTHH frame: `Bridge_01` deck top 3.23 -> 3.96 and `Bridge_04`/`Bridge_05` KEPT -> 3.96 (all three |deck top - land| 0.00, PASS), cross-bridge carriers 2 (unchanged — the bind and the filter are refuted and deleted, see `bridge_family`'s module doc). |

## Tool: pad_span_census

| `Ortho4XP/tools/pad_span_census.py` | The question is DOES THIS UNIT'S OWN DATUM FIT ITS BODIES' PADS — *how far apart do the emitted `building` pads one FOOTPRINT UNIT stands on actually stand?* — the single number owner RULINGS 2026-09-14c item 1 is accepted or refused on (spec `object-placement-spec.md` §16g (1)/(7)). No other instrument asks it: `harness/census.py` prices PAIRS OF VALUES, so an object seated 23.70 m above its own pad breaks no grade law and reports ZERO rows; `obj8_split_report.py` prints a body's anchor and its own ground but never asks whether the bodies sharing ONE unit's datum stand on pads that disagree; `role_overlap_read.py` is an AREA sweep and `role_edge_census.py` a boundary-length one. This is the unit-vs-pad reading: per unit, the `building` pads its bodies' FEET fall inside, how many bodies it holds, and the SPAN of those pads' planes, largest first. **It measures no law and counts no defects** — the pads are the emitted design surface's own `building` faces at `median(z)` over the ring, which is the plane `footprint_unit` reads through `anchor_rule.pad_plurality`, and the body→part join is the PART ID, never a proximity match (memory `canonical-identity-join`). `--over` (default 1.0 m) is the listing floor 14g stated its bar in, not a threshold with any standing. It takes either `o4_v2_placement_<ICAO>.json` or an `obj8_split_report --json` dump — both carry the same `splits` body records. Measured basis (scout `v2heca331` on the owner's 1.0.331 HECA): 17 units whose pads span > 1 m over 1,363 bodies, `fu:38:20` alone 978 bodies on 136 pads spanning 34.8 m — the unit chained on PART BOXES, and its DECK member then gave 96.20 to 1,509 bodies. Promoted 2026-09-14 from that scout's scratchpad `padspan.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse) — the 14g attribution, then lane `v2connector` round 3's before/after. Several patches are reported separately; quote it on identical options. Twin: `tests/test_pad_span_census.py` (the span IS the unit's own pads, a non-`building` face is not a pad, a unit on one pad is not a row, a body with no `unit_of` is not counted, the floor both ways, the CLI's JSON IS the library result, and this index row). |

## Registered frames: LEMD

LEMD  capture  base ec8723e9   lane v2roadcap        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/rw/cap/LEMD.pkl  — the v2roadcap-era LEMD capture used by scout v2unsettled2
LEMD  capture  base 864e7577   lane v2settle         2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle  — fresh main capture + per-law arms + logs (13ak)
LEMD  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_LEMD/structures.json  — LEMD planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_LEMD: every basin rim_ll/region_ll/floor_z/ramp_rings_ll/area/notes and every basin refusal BYTE-IDENTICAL; only covered_fraction moves 0.22750697->0.22750614 at the 1 cm plane quantum
LEMD  mesh     base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /tmp/harness/tile_v2hairline_arm3/Data+40-004.mesh  — §39 ARM: shore weld ON, metric split ON, vector weld OFF — sub-0.1 m2 in bbox 1,641, aspect p50 1.61, 2,734,780 tris
LEMD  patch    base df67b414   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/control.osm  — §39 CONTROL patch (harness tag v2hairline_control) with shore_edges injected from the same TileWater witness — hairline_pair 29 adjudicated
LEMD  capture  base 32c78eaf   lane v2lemd329        2026-09-13T20:49:45  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/LEMD.pkl  — fresh LEMD v2_solve_replay capture on main 32c78eaf (22158 vertices, 1119 faces, 353 s) — for the sunken-road round
LEMD  mesh     base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /tmp/harness/tile_v2hairline_r2cp/Data+40-004.mesh  — §39 round 2 FINAL arm: one witness + project + merge + crossing dedupe + 13cp z carry — 1,617 sub-0.1 m2 in bbox, aspect p50 1.65, 2,745,864 tris, pre-flight 7 UNMESHABLE (all non-patch markers)
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/fix/Data+40-004.mesh  — FIX ARM (13cp): bank rings CLOSED again, open runs wear PATCH_RING_MARKER, ribbon belt — annulus 39,105 of 58,555 valued, harmonic moved 491, isolated components 0, 111 closed bank_foot ways / 0 open; owner site 40.465414,-3.5531888 median 589.00 (1.0.329: 568.3); attr-8 nodes over 2 m = 3 of 275,861
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/omit/Data+40-004.mesh  — OMIT ARM (owner request): [design] bank_omit=true, NO bank_foot emitted — ribbons restored too (attr-8 over 2 m = 4), but patch edge step median 0.740 / p95 5.680 / >3 m 2,584 vs the fix arm's 0.415 / 4.944 / 1,924

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
HECA  patch    base 092b3983   lane v2padjoin        2026-09-14T20:06:08  /tmp/harness/v2padjoinHECAbase.osm  — BASE ARM of the v2padjoin matched HECA pair (branch claude/v2padjoin, base main 092b3983 + the re-landed v2padvert clip): pad_from_cluster=true, pad_airside_clip=true, staged_solve=true, cluster_apron_reach_m=0. rc 0, 457.9 s, ways 1904, nodes 31924, body_sha 3a2d1507c31a, v2-verify 31042, solve feasible, guard shared repo UNCHANGED (1 external-candidate OTHH mod-cache delta named, another lane's; no artifact ledger key for that reason). REPRODUCES v2padvert's registered pads-ON frame EXACTLY: stage 2 1,201/189,405 hard violated, 151 an INFEASIBLE SET (178.7207 m over 705 free columns); stage 1 4/148,256 worst 0.0329 m
HECA  patch    base 092b3983   lane v2padjoin        2026-09-14T20:06:08  /tmp/harness/v2padjoinHECAjoin.osm  — JOIN ARM of the same pair, the ONLY variable cluster_apron_reach_m 0 -> 40 with the §30 (4) apron reach minted as RULINGS 2026-09-14bf's PLANE JOIN (each collar vertex bound into the pad's plate: cap-0 pad_flat + the hard 1 % ceiling). rc 0, 449.9 s, body_sha c76d6b9759f7, guard shared repo UNCHANGED. THE JOIN IS REFUTED: 24,202 join rows take stage 2 from 1,201 to 3,322/204,943 violated and the INFEASIBLE SET from 151/178.7207 m to 1,114/2,312.4274 m over 1,009 columns; stage 1 (the AIRSIDE) 4 -> 8 rows, worst 0.0329 -> 0.1080 m. Mechanism: under §20b the collar is airside, stage 1 fixes it without the pad and substitutes it as a constant, so the plate must equal an already-solved collar (worst join ceiling rows 5.89 m); the all-airside collar pairs leak into stage 1 and move the airside. The join code is DELETED on the branch
HECA  patch    base 0c72919a   lane v2padjoin        2026-09-14T20:49:33  /tmp/harness/v2padjoinHECAr2base.osm  — ROUND 2 BASE ARM (branch claude/v2padjoin 747eaf91, base main 0c72919a): pad_from_cluster + pad_airside_clip + staged_solve ON, cluster_apron_reach_m 0. rc 0, 473.5 s, body_sha 3a2d1507c31a — BYTE-IDENTICAL to round 1's base arm, which proves everything merged into main since 092b3983 changes nothing at HECA in this configuration. Stage 2 1,201/189,405 hard violated, 151 an INFEASIBLE SET (178.7207 m over 705 columns); stage 1 4/148,256 worst 0.0329 m; census pad_airside_weld 42, pad_cluster_mismatch 12, ADJUDICATED 26,708; terminal 30.1279552,31.403143 at 72.62
HECA  patch    base 0c72919a   lane v2padjoin        2026-09-14T20:49:33  /tmp/harness/v2padjoinHECAr2collar2.osm  — ROUND 2 COLLAR ARM, RULINGS 2026-09-14bk's form: the apron within cluster_apron_reach_m (40 m) of a cluster outline is ONE PLANE among itself in §20b STAGE 1 (apron-law heads zones.apron cluster_collar_plane[ ceiling], in no conforming register, no pad vertex in any row) and the pad's plate equals that fixed collar in stage 2; other building pads' welded vertices struck from the collar. rc 0, 368.3 s, body_sha 77e8a3aa20cb, guard shared repo UNCHANGED. STAGE 1 IS FEASIBLE (min shortfall 0.0000 m) — the collar plane is lawful — but THE ACCEPTANCE IS MISSED: airside moved vs the base 11,847 vertices worst 9.45 m (RUNWAY 837, worst 1.23) against a collar of 266 vertices / 12 at the plane, the terminal 72.62 -> 75.92 (bar 72.50), stage-2 infeasible 151 rows / 178.72 m -> 1,318 / 3,074.92 m. The worst stage-2 rows are structures.building_pad airside skirt (7.07 -> 8.58 m) — the skirt law 14ay withdraws and this round did not. Its unstruck twin is v2padjoinHECAr2collar (b6443b925086: 1,626 / 3,644.17 m, stage 1 44 unsettled). Ships DISARMED

## Registered frames: OTHH

OTHH  rebake   base 05050624   lane v2unboxed        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/unboxed  — KCLT 1.0.324 / LEMD 1.0.325 / OTHH 1.0.326 rebake frames + dry arms
OTHH  capture  base 7949757a   lane v2othh327        2026-09-13T16:30:07  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othh327/OTHH.pkl  — v2_solve_replay --capture OTHH on main 7949757a (402 s); solved arms beside it: OTHH.solved.pkl (base) and OTHH.nofeet.pkl (--drop-generator foot_rows)
OTHH  patch    base a0f65165   lane v2cutfeet        2026-09-13T17:37:22  /tmp/harness/OTHH_20260913T171324.osm  — closing build of lane v2cutfeet (§11b (7) cut foot verdicts), rc 0, 968.0 s, ways 1097, body_sha 0ff85d1a7bff, artifact ledger 86493fdab68b; matched replay arms on the v2othh327 capture live in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cutfeet/out (OTHH.base.pkl / OTHH.cut.pkl / othh.base.json / othh.cut.json / *.log), KCLT arms beside them
OTHH  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_OTHH/structures.json  — OTHH planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_OTHH: basins array BYTE-IDENTICAL; only one sunken_refused message rounds 50%->49% roofed, same verdict
OTHH  capture  base cf87c942   lane v2unionsweep     2026-09-14T07:40:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2unionsweep/othh.lane.json  — DRY replay dump (NOT a capture: the plan_clusters reading OFF the registered OTHH capture 7949757a, via scratchpad/v2unionsweep/cluster_arm.py). MATCHED PAIR: othh.base.json = main cf87c942 (666.07 s, machine contended; scout v2partcost read 299.8 s uncontended at 628cca80), othh.lane.json = claude/v2unionsweep 99cf52ba (16.60 s). 44 clusters both arms, all 44 area_m2 BIT-IDENTICAL (struct.pack '<d' hex).
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/base/OTHH_base.osm/v2cost2base.osm  — BASE ARM of the v2cost2 matched triple (own ritual worktree v2cost2base at main 4c6f467c): rc 0, harness wall 631.7 s, staged total 592.86, body_sha 72d4ec0e08f2, ways 1000 nodes 25387, guard UNCHANGED. wall_s load 7.63 / partition 313.57 / classify 7.87 / planar 67.13 / constraints 94.43 / solve 23.34 / emit 9.00 / rebake_plan 5.49 / verify 63.50 (the second Patch.of + road_law_caps + apron_over_preference ran OUTSIDE this clock). obj8_split_report on its own products: plan stage 223.13 s
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_cold.osm/v2cost2cold.osm  — LANE COLD arm (claude/v2cost2 3eeccf13, partition cache EMPTY -> WROTE 1.05 GB): rc 0, wall 615.1 s, body_sha 72d4ec0e08f2 — BYTE-IDENTICAL to the base arm (patch, OTHH.rebake.json and OTHH.graded.json all sha-equal). wall_s partition 288.87 (313.57 base: the per-axis contact screens), constraints 85.32 (94.43), verify 121.85 (63.50 + the 45.6 s that used to run unclocked), total 612.71, unclocked 1.24
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_warm.osm/v2cost2warm.osm  — LANE WARM arm (claude/v2cost2 12b29e6c, partition cache HIT): rc 0, harness wall 328.1 s vs the base arm's 631.7; body_sha 72d4ec0e08f2 BYTE-IDENTICAL, guard shared repo UNCHANGED. wall_s partition 313.57 -> 8.40, classify 7.87 -> 75.79 (the ResourceCache is cold on a hit, so the pack parse moves here: partition+classify 321.5 -> 84.2), constraints 94.43 -> 73.48, verify 63.50+45.6-unclocked -> 62.43, total 592.86 -> 325.17. verify.wall_s per family published (within_shape 50.94, taxi_box 8.72)
OTHH  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_r2c2.osm/v2c2r2c2.osm  — ROUND 2 COLD arm (claude/v2cost2 7bc09ea7, RULINGS 14v; cache EMPTY -> WROTE 31.3 MB, was 1,047 MB): rc 0, body_sha 72d4ec0e08f2, patch/rebake/graded sha-equal to the 4c6f467c base arm, guard UNCHANGED. wall_s partition 283.70 classify 8.90 planar 63.17 constraints 80.17 verify 67.25 total 547.67 unclocked 1.28
OTHH  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_r2w2.osm/v2c2r2w2.osm  — ROUND 2 WARM arm (claude/v2cost2 7bc09ea7): cache HIT, 2,259 resource readings restored; rc 0 harness wall 298.6 s (base arm 631.7), body_sha 72d4ec0e08f2 BYTE-IDENTICAL (patch, rebake plan and graded surface), guard UNCHANGED. wall_s partition 8.07 classify 10.21 (partition+classify 321.5 -> 18.3 on the base arm's frame; bar <= 40 MET) planar 84.43 (55 cold: the pack parse the cache no longer pre-pays lands here) constraints 78.67 verify 69.06 total 296.22 unclocked 1.28
OTHH  patch    base 8e92e26a   lane v2othhfix        2026-09-14T11:37:09  /tmp/harness/v2othhfix2.osm  — closing OTHH patch build of lane v2othhfix on claude/v2othhfix (§24 (7)/(8), §34 (7)/(8) as amended by 14u): rc 0, 614.3 s, ways 1012, nodes 23724, body_sha 44208e4fdd65, artifact ledger 20d817adcf38, shared repo UNCHANGED; report /tmp/harness/v2othhfix2.v2/OTHH.report.json; census A/B vs the owner's 1.0.332 patch ADJUDICATED 1764 -> 1766 (+2)
OTHH  rebake   base 908895cd   lane v2othhfix        2026-09-14T11:37:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix  — dry planar --stage structures arms on the lane-local overlay: base_OTHH (main 908895cd), a5_OTHH (the branch, final law); bars.py / inner.py / prof.py read floor-per-region, floor vs rim-minus-standoff and the §34 (7) profile identity; dry.sh / dry2.sh are the arm runners
OTHH  patch    base ed971ccd   lane v2othhfix        2026-09-14T14:56:25  /tmp/harness/v2othhfix_r2.osm  — ROUND 2 closing OTHH build (§34 (9) the pinched ramp, RULINGS 2026-09-14ak) on claude/v2othhfix: rc 0, 511.5 s, ways 1010, nodes 23607, body_sha ba3354ce693f, artifact ledger 3060701734b4, shared repo UNCHANGED; verify DEFECT families EMPTY (rows 2190 -> 2214, the +24 all within_shape on the two pinched ramps); census vs the owner's 1.0.333 patch ADJUDICATED 3206 -> 3223, road_cross_section 6 -> 6, transverse/airside_no_step/zone_on_pavement unchanged; shared AIRSIDE vertices moved > 0.1 m = 0 of 16,810
OTHH  rebake   base ed971ccd   lane v2othhfix        2026-09-14T14:56:25  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix  — ROUND 2 dry --stage structures matched pair: r2_base (main 9a8b253b = the 1.0.333 code) vs r2_fix (§34 (9)); corridors 40 -> 40, refusals 50 -> 50, 2 pinched_ramps (Terminal_Base_2_1@2 vs route9 12.6 m at 11.05 %; Terminal_Base_2_5@0/a vs route7 5.1 m at 36.98 %)
OTHH  patch    base 298b6ac8   lane v2liftedcap      2026-09-14T15:43:25  /tmp/harness/v2liftedcap.osm  — §34 (9) the census takes the LIFTED pinched-ramp cap (RULINGS 14am): rc 0, 494.9 s, ways 1010, nodes 23607, body_sha bdd053b93bbf, artifact ledger 5c0c2ded14c5, shared repo UNCHANGED. MATCHED PAIR: the same patch with the two o4_grade_law_cap_lifted tags stripped is /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2liftedcap/arms/nolift.osm (ADJUDICATED 3223 / law-true 4526 = the v2othhfix_r2 numbers exactly); as built 3204 / 4507. census_rows_diff EXACT 4507 MOVED 0 NEW 0 GONE 19 (all within_shape tunnel_ramp|tunnel_ramp on shapes 828/831). Census json/rows arms in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2liftedcap
OTHH  patch    base a4b7801d   lane v2othhfix        2026-09-14T17:31:46  /tmp/harness/v2othhfix_r3b.osm  — ROUND 3 closing OTHH build (§34 (9) (4)-(5), RULINGS 2026-09-14aq) on claude/v2othhfix: rc 0, 262.3 s (warm), ways 1010, nodes 23615, body_sha a3c64e4a261c, artifact ledger 4afb62b3f6a1, shared repo UNCHANGED; verify DEFECT families EMPTY, rows 2189 -> 2146; census vs the owner's 1.0.334 patch ADJUDICATED 3204 -> 3174 (within_shape -35, road_cross_section +8 away from both pinched roads); route7 road levels byte-identical, route9 within 0.02 m, 0 of 118 service-road vertices moved > 0.1 m, 2 of 16,810 airside (0.10/0.12 m, apron|building corners)
OTHH  rebake   base a4b7801d   lane v2othhfix        2026-09-14T17:31:46  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix/r3_base2/structures.json  — ROUND 3 dry --stage structures (§34 (9) (4)-(5)) vs the lane's round-2 arm r2_fix: corridors 40 -> 40, refusals 50 -> 50; Terminal_Base_2_5@0/a climb_from 38.89 -> 36.50 (+2.4 m), pinched grade 36.98 % -> 25.18 %; Terminal_Base_2_1@2 6.30 -> 6.00, 11.05 % -> 10.80 %; mouth_z unchanged both; both pinched ramps report 'the road face edge (the pack paints no line here)' — OTHH carries NO road-edge marking (marks.py/marks2.py/marks3.py/pol.py beside it)
OTHH  rebake   base 9a49f136   lane v2splitname      2026-09-14T18:03:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2splitname/out/othh.lane.json  — 14at THE SPLIT FILE IS KEYED ON THE OFFSET IT BAKES — MATCHED PAIR of v2_rebake_replay plan --sampler mesh --runs 3 on the 1.0.334 OTHH products (o4_v2_rebake_OTHH.json + OTHH.graded.json + the installed Data+25+051.mesh, --dsf-dump the shared mod cache's +25+051.dsf.55d38455.text). othh.base.json = main 9a49f136 cut with git archive (145.99 s mean); othh.lane.json = claude/v2splitname 4b13e977 (140.26 s mean). Collisions (one file written by >1 placement with distinct offsets) 1 -> 0; distinct body files 1856 -> 1857; splits 705 bodies 1857 both arms; every row byte-identical bar the name (and the 531 anchor_reason/merged_into strings that quote a carrier's file name) — 0 differences beyond the tag. tunnel1 b0: idx 14052 -> __b0_8b16464a baking its own [9.0486,9.5497,-50.1039], idx 14051 -> __b0_c057eb1e baking [-8.8848,9.5497,-84.4220]. guard shared repo UNCHANGED both arms.
OTHH  rebake   base fe0a5b33   lane v2othhfix        2026-09-14T19:34:56  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix/r4b/structures.json  — ROUND 4 dry --stage structures (§34 (9) (6) the half-width margin) vs r3_base2: corridors 40 -> 40, none lost; Terminal_Base_2_5@0/a top_s 44.0 -> 40.0 (IN 4.00 m) grade 25.18 -> 53.95 %; Terminal_Base_2_1@2 top_s 18.9 -> 14.0 (IN 4.89 m) grade 10.80 -> 17.39 %; route7 half-width 3.32 m / route9 3.00 m; mouth_z unchanged. NO BUILD — the 54 % east ramp needs 14be's plate-edge full-depth point (not landed) to give the run back; ramp_in_road measured 0 in BOTH the owner's 1.0.335 patch and the lane's r3b build
OTHH  patch    base 88de7fec   lane v2othhramp       2026-09-14T20:43:50  /tmp/harness/v2othhramp.osm  — CLOSING OTHH build of lane v2othhramp (claude/v2othhramp caf7b9cc; the three coupled items of RULINGS 14bi): rc 0, 649.9 s, ways 1015, nodes 23714, body_sha 87ba777c8a94, shared repo UNCHANGED, verify defects {} (rows 7877). MATCHED CONTROL at the same tree = /tmp/harness/v2othhrampBASE.osm (worktree v2othhrampbase at bdd28759 = main 88de7fec + the v2othhfix half-width merge, rc 0, 511.9 s, body_sha b60c2dd4502b, artifact ledger cc0ead55f1f2 — a later --base-arm at that tree is served from it). A/B: law-true 8939 -> 8957, airside 8854 -> 8851, ADJUDICATED 7623 -> 7620; ramp_in_road 0 -> 0; hairline_pair 1316 -> 1337; airside vertices 22 of 20,001 moved > 0.02 m worst 0.060 m and 0 over 0.1 m; service-road vertices 0 of 116 moved > 0.02 m worst 0.010 m. Pinched grades east route7 53.95 -> 17.17 %, west route9 17.39 -> 18.06 %
OTHH  patch    base bdd28759   lane v2othhramp       2026-09-14T20:44:05  /tmp/harness/v2othhrampBASE.osm  — MATCHED CONTROL for lane v2othhramp: main 88de7fec + the claude/v2othhfix half-width merge, NONE of the three 14bi items. rc 0, 511.9 s, ways 1010, nodes 23605, body_sha b60c2dd4502b, artifact ledger cc0ead55f1f2, shared repo UNCHANGED, verify defects {} (rows 7881). Built in ritual worktree v2othhrampbase
OTHH  rebake   base bdd28759   lane v2othhramp       2026-09-14T20:44:06  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhramp  — MATCHED dry --stage structures TRIPLE for RULINGS 14bi: r0_base (bdd28759 = the half-width margin alone), r1_plate (the plate edge alone), r2_all (all three). tunnels 40 -> 42, wall corridors 25 -> 27, refusals 26 -> 26. EAST MOUTH Terminal_Base_2_5@0/a along the axis: wall-band end 38.89, PAD edge 36.50 (14at's reading), COVERING-PLATE edge 29.00, ramp top 40.00 with the half-width margin (44.00 without) — 9.9 m of uncovered corridor is ramp, grade 53.95 -> 17.17 %. WEST Terminal_Base_2_1@2: the plate covers the whole corridor so climb_from stands at the wall end 6.30 (the pad read 6.00), 17.39 -> 18.06 %. r1 and r2 are BYTE-IDENTICAL: §34 (10)'s generalisation changes nothing at OTHH beyond the §34 (9) pinch. dry.sh is the arm runner; basetree/ is the git-archive base tree

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
SPJC  patch    base a1d0edfa   lane v2padcluster     2026-09-14T14:21:30  /tmp/harness/v2padclusterSPJC4.osm  — v2padcluster ROUND 4 SPJC build — the FIRST SPJC frame carrying Part.height_m (claude/v2padcluster 9a4bd0e3): rc 0, 82.1 s, ways 431, body_sha 7f9b9659d13c, solve optimal, guard shared repo UNCHANGED (23 EXTERNAL-CANDIDATE deltas in the window, another lane's — NO ledger key). The viaduct xp11_007__b0 is on pad building7 at 20.07 in unit fu:0:3@cluster_pad of 6 members; 13df read 19.5604 in fu:0:0@cluster_pad of 24 — the leaf rule split the unit and the derived pad stands 0.51 m above the bar. pad_airside_weld 7, worst building7 -> pav46 0.970 m over 20.0 m
SPJC  graded   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:30  /tmp/harness/v2padclusterSPJC4.v2/SPJC.graded.json  — v2padcluster ROUND 4 SPJC build — the FIRST SPJC frame carrying Part.height_m (claude/v2padcluster 9a4bd0e3): rc 0, 82.1 s, ways 431, body_sha 7f9b9659d13c, solve optimal, guard shared repo UNCHANGED (23 EXTERNAL-CANDIDATE deltas in the window, another lane's — NO ledger key). The viaduct xp11_007__b0 is on pad building7 at 20.07 in unit fu:0:3@cluster_pad of 6 members; 13df read 19.5604 in fu:0:0@cluster_pad of 24 — the leaf rule split the unit and the derived pad stands 0.51 m above the bar. pad_airside_weld 7, worst building7 -> pav46 0.970 m over 20.0 m
SPJC  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:30  /tmp/harness/v2padclusterSPJC4.v2/SPJC.rebake.json  — v2padcluster ROUND 4 SPJC build — the FIRST SPJC frame carrying Part.height_m (claude/v2padcluster 9a4bd0e3): rc 0, 82.1 s, ways 431, body_sha 7f9b9659d13c, solve optimal, guard shared repo UNCHANGED (23 EXTERNAL-CANDIDATE deltas in the window, another lane's — NO ledger key). The viaduct xp11_007__b0 is on pad building7 at 20.07 in unit fu:0:3@cluster_pad of 6 members; 13df read 19.5604 in fu:0:0@cluster_pad of 24 — the leaf rule split the unit and the derived pad stands 0.51 m above the bar. pad_airside_weld 7, worst building7 -> pav46 0.970 m over 20.0 m

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

