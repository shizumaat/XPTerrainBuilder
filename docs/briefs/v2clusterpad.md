# Brief pack — lane `v2clusterpad`

Base: main `6f3f0110` · generated 2026-09-13 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

A large terminal cluster is one unit on one pad; the apron around it may be flattened (owner RULINGS 2026-09-13bj item 1) — object spec §16f (7), design spec §30 (4).

## The brief

Owner (KCLT on 1.0.327, RULINGS 13bj item 1): the terminal cluster still seats at different elevations — passengers and seats at 35.2191877, −80.9426007 sit on the ground under the building instead of on its floor; roofs sank in places. "These large complex structures have to be seated as a unit. As long as it remains feasible with grade laws and taxiways, etc. it's acceptable to flatten large apron areas around big terminals if needed to accommodate a large terminal cluster." This SUPERSEDES 13aq's partition-by-pad (§16f (4)) for clusters: implement object spec §16f (7) (one unit, one plane, one pad; interior furniture on the cluster plane; §16f (5) pavement-is-king yields inside the cluster) and design-surface §30 (4) (the cluster pad: one `building` pad over the family's footprint union, the apron within `cluster_apron_reach_m` targets its plane where the caps allow, the reach stops at any taxiway band). Two stages, one lane: (a) the design surface first — the cluster is known from the object stage's family census, which runs AFTER the planar stage, so the cluster's footprint union must be derivable at planar time from the pack (the same §16f (1) test: members sharing one authored datum plane and forming one connected plan cluster — `airport/placement_family.py` has the derivation; lift the plan-side half into a `planar/`-time reader of the rebake plan / pack members, or publish `cluster_pads` from a pre-pass) and emitted as one pad in `constraints/pads.py` / the pad emitter; (b) the object stage seats the cluster on the sidecar's `cluster_pads` plane. Law keys `[placement] cluster_pad_min_m2 = 5000`, `[design] cluster_apron_reach_m = 60` (design: measure and report; a different number is a deviation to report, not decide). Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before editing — every reader of `building` pads, pad frontages (§28), the pad ceiling (§30), the apron trend, the taxiway bands, §16f's family census.

## Bars

- KCLT terminal cluster: every member on ONE plane (zero spread 0.00; today two pad groups); the passengers/seats at 35.2191877, −80.9426007 with zero = the cluster plane (on the floor); no roof member below its wall top.
- The cluster pad emitted (one `building` pad over the footprint union, one plane at the pad law's level) and published as `cluster_pads` in the sidecar.
- Stands within the reach flat at the cluster level: apron z − pad z ≤ 0.05 m inside `cluster_apron_reach_m`; the taxiway family byte-identical (runway/taxi rows); the apron beyond the reach grades under its own law; the solve's settled lines quoted both arms.
- §17 motion rows on the apron around the terminal not worse than the base; cockpit CRITICAL motion ≤ base.
- LEMD's old terminal and OTHH's clusters re-read under the same law, named (not necessarily byte-identical); airports with no cluster byte-identical (CYXY).
- ONE KCLT build against the shared control (`--base-arm`); suite twice.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/placement_family.py`, `Ortho4XP/src/auto_patch_v2/constraints/pads.py`, `Ortho4XP/src/auto_patch_v2/planar/`, `Ortho4XP/src/auto_patch_v2/pipeline/publication.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/emit/osm_adapter.py`, `Ortho4XP/src/O4_Mesh_Utils.py`, `Ortho4XP/src/O4_Cfg_Vars.py`

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

## Spec (object-placement) §16f

## §16f AN OBJECT FAMILY STAYS TOGETHER (owner RULINGS 2026-09-13af; Fable 2026-09-13) — lane `v2family`

Owner (KCLT 13j item 9): "Many parts of the main terminal building complex are
seated at different heights creating floating or sunken elements by a few
meters"; on the proposal (13ab): "approved, whenever feasible, keep object
families together". Scout `v2roadcapkclt`: KCLT's 27 basin refusals are ALL the
`paredes_*_charlotte` / `techos_*` / `suelos_interiores_charlotte` /
`Charlotte_Airport_00{5,8}_ALB` members, each refused under 09ag rule 5b ("a
slab sitting on datum relief, not a sunken solid"), 4.25–9.54 m under the
local ground and ~0 under their own render datum — the pack authored the whole
complex on one flat datum plane over real relief, and the placement stage seats
each piece to the ground under itself.

1. **A FAMILY** is the pack's set of members that (a) share one authored datum
   plane — the same placement row set at one authored y (the §16c (6)/(7) unit
   is the unit of contact) — AND (b) form ONE connected plan cluster: footprints
   in contact within `[placement] contact_eps_m` or overlapping. Two placement
   rows do not make a family (LEMD's shared-datum pack puts 2,035 of 2,109
   bodies on two rows); the plan cluster does. A family is derived once per
   plan and published per body as `family_of`.
2. **ONE ZERO PLANE.** A family's bodies take one zero: the datum of the
   emitted `building` pad their footprints mostly stand on (§16d (6)'s pad
   majority read over the family's contacts), else the median ground under the
   family's own contacts. Every member anchors on that plane; a member whose
   footprint stands apart from the pad (beyond `contact_eps_m` from every other
   member's footprint) is NOT in the family and is cut to its own ground (§16c).
   Rule 5b's refusal stays for a genuine slab-on-relief SINGLE member; a
   family's slab is the family's floor and is admitted with it.
3. **FEASIBILITY IS MEASURED, NEVER ASSUMED.** A family is held together only
   where (1)(b) holds for ALL its members; a partial cluster (OTHH's bridge
   clutter beside the deck plate, §16e (3) withdrawn) is reported per body and
   not bound. The census prints per family: members, zero spread, members cut
   apart, the pad or ground it seated on.

BARS (KCLT frame, `v2_rebake_replay.py plan --sampler mesh`, matched arms;
then ONE KCLT tile-side object run): the terminal family's per-body zero
spread ≤ 0.3 m (today 4.25–9.54 m under local ground across members); basin
refusals of the family 27 → 0; the family seated at the terminal pad's level
(name the pad and its level); no member floating or sunken > 0.5 m against
the pad (§31 visual); LEMD 1.0.325 and OTHH 1.0.326 frames byte-identical or
every changed placement named with its reason; plan stage not worse than
+10 % (`--runs 3`); suite twice.

### §16f MEASURED (lane `v2family`, 2026-09-13; branch `claude/v2family`)

Implemented in a new `airport/placement_family.py` (mirroring
`bridge_family.py`): `_clusters` (the connected plan cluster over the unit's
footed bodies' PART boxes), `bind_families` (the one zero plane and the
re-anchor), `census_families` / `census_families_lines`.  Wired in
`placement_plan.build_splits` AFTER `_atom.bind_unit`, published as
`Anchor.family` → `placement_record.Body.to_dict()["family_of"]` and
`model/placement.Body.family_of`, re-exported through `placement_census` /
`placement_carrier`, printed by `obj8_split_report.py` and
`seat_feet_census.py`.  One consumer edit: `placement_carrier.carriers_for`'s
`_ok`.

**THE FRAME.**  A KCLT build on the merged tree (`864e7577` + this branch's
WIP), harness tag `v2familyKCLTframe`, rc 0, 389.3 s, `body_sha bb022a77f067`
— taken because RULINGS 2026-09-13ak turned the PAD GROUP LAW back on and
every KCLT capture older than `db5b99ca` is a different frame.  The base arm
is `git archive 864e7577 Ortho4XP/src Ortho4XP/tools`.  LEMD 1.0.325 and OTHH
1.0.326 are the frames the previous lanes used (`v2lemd325o`, `v2othh1o`);
both arms read the same graded document, so the identity reading holds.
**That frame build is CONTAMINATED**: it added one path to the shared repo,
`Airport_mod_cache/Nimbus Simulation - KCLT V1.4 - Charlotte XP12/
+35-081.dsf.anchor_bak.7bf41307.text` (a DSF text dump the mod-cache root
resolved past `O4_AIRPORT_MOD_CACHE_DIR`), so the run was not ledgered.
Every subsequent run in this lane printed `[guard] shared repo UNCHANGED`.

**THE CONSUMER CENSUS (owner RULINGS 2026-08-30l), taken before the edit.**

| pass / reader | what it reads | ruling |
|---|---|---|
| `planar/basins.py` rule 5b (`obj8.ObjReport.datum_relief`) | the basin refusal | UNTOUCHED — a planar-stage product; see "the 27" below |
| `anchor_rule.anchor_for` (`pad_majority`, §16d (6)) | one BODY's contacts vs one pad | UNTOUCHED; §16f re-reads the same function over the FAMILY's contacts and overrides the anchor after it |
| `placement_atom.bind_unit` (§16c (7)) | the unit's ε-contact clusters, re-anchors footed candidates | UNTOUCHED and runs FIRST; §16f is the last word on a footed zero |
| `placement_carrier.carriers_for._ok` (§16a (2) ground test) | `Candidate.ground_off` | **EDITED** — a family-bound body is exempt, as a BASIN is (11al).  Not exempting it sent every KCLT terminal roof past the walls it stands on (files 477 → 609) |
| `placement_carrier.carriers_for` rest-on / fallback ranking | `Candidate.anchor`, boxes | reads the new zero, unchanged code |
| `placement_carrier.group_at_zero` / `merge_rides` / `coarsen` | the zero plane | read the new zero; run BEFORE (coarsen) or AFTER (rides) — no edit |
| `placement_body._raw_bodies` / `is_elevated` | the anchor at body formation | runs BEFORE the family exists — untouched |
| `bridge_family.assign_bodies` / `Body.bridge_of` (§16e (3)) | the deck footprint relation | UNTOUCHED and read-only here; §16f REFUSES any unit carrying a deck member (below) |
| `placement_cut` / `obj8_split` (the writer) | `Anchor.lat/lon/y_zero/offset` | unchanged: a family anchor is an ordinary anchor point with a computed `y_zero`, the shape §16e's `_datum_anchor` already takes |
| `placement_seams`, `census_outside_box`, `census_v15/v16/v16b`, `cockpit_block` | the written bodies | read the new zeros; all re-measured below |
| `placement_write.build_plan` / `engine_v2` | `SplitSet` | additive field `families` only |

**THE LAW AS BUILT, and the two readings that were REFUTED on the way.**

1. `(1)(b)` is read at the BODY footprint, not at the whole member.  A
   member-level cluster joins a member on ONE touching box and drags every
   body of it: KCLT's `Charlotte_Airport_002_ALB__b7` stands 500 m out on the
   apron and came out **−216.89 m**, files 477 → **708**.  DELETED.
2. §16f (3)'s feasibility is a SHARE of the unit (`FAMILY_SHARE_MIN` 0.5): a
   cluster holding half or less of its unit's eligible footed bodies is a
   PARTIAL family, reported and not bound.  Without it KCLT's `unit:3` — eight
   separate hangars — made 26 families of 2–7 bodies and took the airport's
   worst §17 motion row 2.52 → **3.73 m**.
3. **A UNIT CARRYING A DECK MEMBER FORMS NO FAMILY.**  §16f (3) names OTHH's
   bridge clutter as the case; a plan-CONTACT family binds it by another
   route than §16e (3)'s withdrawn footprint family — measured, OTHH `unit:6`
   came out 29 members at one zero with a member **8.20 m** off its own
   ground, and Bridge_01's §16e (6) datum bodies moved.  The test is
   `deck_ring or deck_kind in ("flag", "signature")`; reading `deck_kind`
   at all (the value is `candidate` on 31 KCLT / 39 LEMD / 342 OTHH members)
   disqualified both terminals and is NOT the test.

**BARS — KCLT (`v2familyKCLTframe`, matched dry arms).**

| bar | base `864e7577` | §16f |
|---|---|---|
| terminal family per-body zero spread | `unit:31#0` **9.87 m**, `unit:30#0` 0.62 m | **0.00 / 0.00 m** — MET (bar 0.3) |
| the complex (both rows together) | 9.87 m (213.83 … 223.70) | **0.47 m** (221.31 / 221.78) |
| the pad and its level | — | `unit:30#0` on **`building80` at 221.78**; `unit:31#0` on its MEDIAN GROUND at **221.31** — only 43 of its 129 anchors land on `building80`, so §16d (6)'s MAJORITY declines and §16f (2)'s fallback rules.  The two planes lie 0.47 m apart, inside `building80`'s own 1.19 m of relief (§20) |
| no member floating/sunken > 0.5 m against the pad | — | `unit:30#0` worst **+0.38 m** — MET; `unit:31#0` worst **+4.26 m** — NOT MET, and it is the law working: the north-west wing's feet stand 4 m under the family's plane |
| worst §17 motion row | +1.66 m | **+2.99 m** `paredes_10_charlotte__b35` on apron — WORSE, the same residual read at a foot |
| COCKPIT CRITICAL visual rows | 155 | **140** |
| §15 carried over a REFUSED carrier | 12 | **4** |
| §16b carried piece float > 0.5 m | 45 | **26** |
| §16b body wider than its terrain group | 232 | **228** |
| files / bodies | 487 / 581 | **497 / 615** |
| low-side anchors with a residual | 150 | **128** |
| plan stage, `--runs 3`, graded sampler, foreground | mean **10.80 s** (12.72 / 8.38 / 11.30) | mean **10.36 s** (11.92 / 11.52 / 7.63); `_surface` calls 80,354 → 84,810 — MET (bar +10 %) |

**THE CLOSING RUN** — the write half into an APFS clone of the pack, guard
armed: **497 cut files written, DSF round trip OK, 497/497 new `OBJECT_DEF`s
read back, 0 rows carrying an elevation**; §16d written geometry outside its
own box **0 (bar 0)**; §16c torn seams outside line/arc **1 (bar 0)** —
`paredes_9_charlotte` b8↔b12, ONE shared vertex, step **+0.00 m** (§16d
(4)–(6) MEASURED recorded this same seam at **+0.16 m**: the family plane
closed the step, the topological count stands).  `[guard] shared repo
UNCHANGED`.

**LEMD 1.0.325 IS NOT BYTE-IDENTICAL, AND EVERY CHANGE IS ONE FAMILY.**  The
Aerosoft old terminal is ONE plan cluster of **80 members / 209 bodies** and
takes one zero **602.86** (median ground; no pad holds a majority), worst
member **+8.40 m** off its own ground; 25 members' bodies stand apart and keep
their own ground.  **249 of 2,435 bodies change**; files 2,435 → 2,417.  The
airport's bars are flat: COCKPIT visual 498 → **495**, motion 6,258 feet on
368 bodies → 6,455 on 378, §16b carried float 154 → 156, §16b wider 1,122 →
1,118, §15 carried float **0 → 0**.  This is §16f applied literally to the
pack the ruling named as the trap — and the trap it named (two rows) is NOT
what fires: the PLAN CLUSTER does.  **An owner/Fable ruling is asked for**
(below).

**OTHH 1.0.326: the bridges are out, the rest binds.**  63 families / 652
bodies, per-family spread **0.00** everywhere; `unit:6` (Bridge_01/02/03/06)
forms none.  Bars all better or equal: files 1,831 → **1,757**, COCKPIT motion
3,159 feet on 86 bodies → **2,227 on 98**, visual 309 → **290**, §16b carried
float 159 → **138**.  With the deck exclusion *broadened* to any `deck_kind`
the airport is byte-identical but for **4 bodies** — the `unit:63`
fire-station family, whose zero is unchanged to 1e-15 (3.9599999999999995 →
3.96) — which is what that arm measured; the shipped test is the narrow one.

**THE 27 BASIN REFUSALS ARE NOT AN OBJECT-STAGE NUMBER.**  Rule 5b's refusals
are minted in `planar/basins.py` at the `obj8` witness (`ObjReport.datum_relief`)
and appear in a tile build's basin stats; the rebake plan does not carry them
and the placement path never reads them (`basin_member` comes from the
ADMITTED rings only).  Admitting the terminal's slab AS A BASIN would cut a
4–9 m pit under KCLT's terminal, which is the opposite of the owner's read.
The bar "27 → 0" is therefore **not measurable here and was not moved**: what
§16f (2)'s "a family's slab is the family's floor and is admitted with it"
buys is the family's ZERO PLANE, and the defect the refusals signalled — every
piece seated to the ground under itself — is closed (spread 9.87 → 0.00).

**SUITE**: **1,250 passed, 1 skipped**, twice.  Twins:
`test_16f_1_a_family_is_a_connected_plan_cluster_of_two_members`,
`test_16f_1_two_placement_rows_do_not_make_a_family`,
`test_16f_2_the_family_takes_one_zero_plane_on_its_pad`,
`test_16f_3_a_partial_cluster_is_reported_and_not_bound`.

**INTENT QUESTIONS (measured, for the owner).**

1. **LEMD's old terminal.**  Should §16f bind an 80-member complex whose
   members' own grounds span 8.4 m?  Measured both ways above.  The law as
   written says yes; nobody has read the result in the sim.
2. **`unit:31#0` did not seat on `building80`.**  §16f (2) reuses §16d (6)'s
   MAJORITY and 43 of 129 anchors is not one.  A PLURALITY read (largest pad
   wins) would put both KCLT rows on `building80` and close the 0.47 m
   between them.  Not implemented: it is a different rule from the one the
   spec cites.
3. **A family holds a member 4.26 m (KCLT) / 8.40 m (LEMD) off its own
   ground**, and at KCLT that is a wall standing +2.99 m over the apron the
   aircraft rolls on (§17 motion, worst row).  "Keep families together" and
   "0.05 m at a rolled-on foot" are in direct conflict at that wall; which
   yields is the owner's.

### §16f (4)–(6) THE FAMILY IS PARTITIONED BY PAD; PAVEMENT IS KING (Fable 2026-09-13; RULINGS 2026-09-13aq) — lane `v2family` round 2

Round 1 (a51348e2): one plane per family put KCLT `unit:31#0` on median ground
4.26 m above `building80` (43 of 129 anchors on the pad, so a MAJORITY read
declined), held a wall +2.99 m over rolled-on apron, and gave LEMD's
80-member old terminal one plane across 8.4 m of ground (worst member +8.40 m
off its own ground).

4. **ONE PLANE PER PAD.** A family is partitioned by the emitted `building`
   pads its members stand on: a member joins the pad group of the pad its
   contacts stand on by PLURALITY (largest share wins; §16d (6)'s "mostly" is
   amended to plurality for families); a member on no pad joins the pad group
   it touches (§16c (6) contact); a member touching no pad group is cut to
   its own ground (§16c). Each pad group takes its pad's plane; the steps
   between groups fall at the pad frontages the design surface terraces
   (§28). CYXY's hillside building (one pad) stays one plane.
5. **PAVEMENT IS KING (§17).** A member whose ground contacts are ALL on
   rolled-on pavement (apron / taxi / runway) is cut apart from its family
   and seated on that pavement — an object never moves the aircraft.
6. **RULE 5b MEMBERS.** The bar "basin refusals 27 → 0" is withdrawn (the
   object stage never sees the basin witness); instead every rule-5b-refused
   member of a family is a family body on its pad group's plane, named in
   the census.

BARS (round 2, registered KCLT frame — `tools/harness/frames.py list KCLT`
— and the LEMD 1.0.325 frame; no new build unless the replay cannot state a
bar): KCLT both rows on `building80` (row residual 0.47 → ≤ 0.3 m; member vs
pad +4.26 → ≤ 0.5); worst §17 motion row ≤ +1.66 m (round 1's base) with the
wall named and seated on its apron; LEMD's 80-member family partitioned by
its pads, worst member-off-own-ground 8.40 → ≤ 0.5 m, the 249 changed bodies
each ≤ 0.5 m off its pad plane; OTHH byte-identical; plan stage ≤ 11 s; torn
seams 0; suite twice.

### §16f (4)–(6) MEASURED (lane `v2family` round 2, 2026-09-13; branch `claude/v2family`)

`airport/placement_family.py`: `pad_plurality` (§16f (4), the amended read),
`_all_on_pavement` (§16f (5), through `anchor_rule._all_on_rolled` — one
implementation), `_pad_groups` (the multi-source contact walk out of the pad
seeds), and the pad-plane bound.  `anchor_rule.PadRing` grew `z` — the pad's
OWN graded ring heights — filled in `placement_read.pads_rims_from_graded_doc`
beside the rim's.  Frame: the registered `v2familyKCLTframe` rebake + graded
(`frames.py list KCLT`, base `864e7577`); LEMD 1.0.325 (`v2lemd325o`) and OTHH
1.0.326 (`v2othh1o`).  **No new build.**  `[guard] shared repo UNCHANGED` on
every run.

**BARS (round-1 base `864e7577` → round 2).**

| bar | before | after |
|---|---|---|
| KCLT both rows on `building80` | `unit:31#0` median ground 221.31 / `unit:30#0` pad 221.78 — **0.47 → 0.33 → 0.00 m** | BOTH on **`building80` at 221.49** — MET (≤ 0.3) |
| KCLT member vs pad | +4.26 (round 1: +4.44) | **+0.49** (`unit:31#0`, 18 members / 97 bodies) and **+0.42** (`unit:30#0`, 14 / 14) — MET (≤ 0.5) |
| KCLT worst §17 motion row | +1.66 (base) / +2.99 (round 1) | **+1.66 m**, `Charlotte_Airport_008_ALB__b13` at 35.2125591,−80.9296589 **on apron** — NOT a family body — MET |
| KCLT torn seams (write half) | 1 @ +0.00 m | **0** — MET (bar 0) |
| KCLT §16d written geometry outside its own box | 0 | **2** — NOT MET, named below |
| KCLT visual rows / §16b carried float / files | 155 / 45 / 487 | **128 / 41 / 475** |
| KCLT round trip | — | **475 cut files, OK, 475/475 new `OBJECT_DEF`s, 0 rows carrying an elevation, duplicate rows 0** |
| LEMD family partitioned by its pads | one plane, 80 members, worst **+8.40 m** | one pad group **`building4` at 602.34**, 23 members / 27 bodies, worst **+0.54 m** — PASS-with-residual (0.04 over) |
| LEMD airport | visual 498, motion 6,258 ft / 368 bodies, files 2,435 | **497 / 6,264 ft / 369 / 2,432**; **64 of 2,435 bodies change** (23 placements) |
| OTHH byte-identical | 1,831 bodies | **NOT MET — 233 bodies / 116 placements change**; 16 families / 206 bodies, worst family +1.00 m (`unit:90#0@building20#2`), the other 15 ≤ 0.5.  Airport bars all flat-or-better: visual 309 → **290**, motion 3,159 ft / 86 bodies → 3,153 / 84, §16b carried float 159 → **152**, files 1,831 → 1,788 |
| plan stage, `--runs 3`, graded sampler, foreground | 10.80 s mean | **7.32 s** (7.31 / 7.27 / 7.38) — MET (≤ 11 s) |
| suite | — | **1,259 passed, 1 skipped**, twice |

**THE PAD GROUPS, NAMED.**  KCLT: `unit:31#0@building80` (18 members —
`paredes_1/2/3/4/5/8/9/10`, `Paredes_7`, `techos_1/2`,
`suelos_interiores_charlotte`, `vidrios_paredes_5/8/12` and their `_lit`) and
`unit:30#0@building80` (14 of the `-`-prefixed twins), both at **221.49** —
the median of `building80`'s own 865 graded ring vertices (221.15 … 222.32,
1.17 m of relief, §20).  LEMD: `unit:27#3@building4`, 23 members of the
Aerosoft old terminal at **602.34**; 20 more resources (`LEMD38` ×90,
`LEMD60` ×19, `VRDCH` ×18 …) stand apart and keep their own ground.  OTHH:
16 groups, the largest `unit:15#0@building2` (24 members, 3.91),
`unit:60#0@building12` (15, 3.96), `unit:87#1@building18` (15, 4.03).

**WHAT MADE THE NUMBERS.**  Three readings, in the order they were measured.

1. **THE PAD'S OWN PLANE, not the group's contacts.**  Seating each group at
   the median of ITS OWN on-pad contacts gave KCLT's two rows 221.45 and
   221.78 — 0.33 m apart on ONE pad, the pad's 1.17 m of relief sampled
   twice, and still over the 0.3 bar.  The plane is now `median(pad.z)`:
   order-independent, one pad one plane by construction, row residual 0.00.
2. **THE GROUND BOUND HOLDS AT THE PAD JOIN** (§16d (5) / 12ap (A), applied
   at the new join).  §16f (4)'s contact clause picks up exactly the members
   that stand OFF the pad on real relief — measured, 51 of 91 KCLT family
   bodies have NO pad of their own — and lifting them to the pad's plane put
   them +4.44 (KCLT), +8.92 (LEMD) and +12.21 m (OTHH) above their own
   ground.  A member further than `bind_ground_m` (0.5) from the pad's plane
   is now CUT TO ITS OWN GROUND and counted
   (`family_bodies_off_the_pad_plane`).  This is what turned every
   member-vs-pad bar.
3. **§16a (2)'s FAMILY EXEMPTION IS DELETED.**  Round 1 needed it (a family
   body was up to 4.4 m off its own ground and the carrier test read that as
   mis-anchored, files 477 → 609).  (2)'s bound makes every family body
   lawful to that test by construction, so the special case is gone and the
   ordinary rule passes them.  Measured with and without: files 466 → 475,
   visual 129 → 128, §16b carried float 43 → 41, outside-box 2 either way.

**THE ONE REGRESSION, NAMED.**  §16d (1) written-geometry-outside-its-box
**0 → 2**, both `line_segment` class:
`Terminals/-paredes_7_charlotte__b1` **31.07 m** and `__b2` **6.17 m**,
carried by `-paredes_2_charlotte__b0` / `-paredes_4_charlotte__b1` — two
`unit:30` family members.  A SEGMENT's `geom_box` is its own station span
(§11f (2)) and the family plane changed which member's FILE the segment rides
into; the §16d (1) class `v2unboxed` closed for the un-carried case is
re-exposed for a segment riding another member's file.  Not fixed — the
attempt cap for this round was spent on (1)–(3) above, and it is a
`placement_cut` / `obj8_split` question, not a family one.

**RESIDUALS.**  LEMD's worst member reads **0.54** against the 0.50 bound the
walk enforced: the bound reads the FOOTED body's own contacts and the census
reads `anchor_ground_off` over the WRITTEN group's feet, which by then
includes the carried bodies §15 appended to it.  0.04 m; reported, not
iterated.  OTHH's `unit:90#0@building20#2` reads +1.00 m for the same reason
at a group whose carried population is larger.

**TWINS** (7 in total for §16f):
`test_16f_4_one_plane_per_pad_and_the_pads_own_plane`,
`test_16f_4_the_ground_bound_holds_at_the_pad_join`,
`test_16f_5_pavement_is_king_over_the_family`, beside round 1's four.

**NOT DONE.**  No new build (the registered frame served every bar).  No base
write-pack arm — the outside-box and seam "before" are round 1's own write run
on the same frame.  OTHH byte-identity is NOT achieved and no mechanism was
added to force it: §16f binds 16 real pad groups there and the airport's own
bars improve.  §16f (6)'s "name the rule-5b-refused members" is served by the
census printing every family's members and every member cut apart; the plan
still carries no basin-refusal record and none was added.

### §16f (7) A LARGE TERMINAL CLUSTER IS ONE UNIT ON ONE PAD (owner RULINGS 2026-09-13bj; Fable 2026-09-13) — lane `v2clusterpad`

Owner (KCLT 1.0.327): "Terminal object families still settling at different
elevations resulting in passengers and seat objects … sitting on the ground
under the building instead of on the floor inside the building. Roof
elevations sank in some places as well. These large complex structures have
to be seated as a unit. As long as it remains feasible with grade laws and
taxiways, etc. it's acceptable to flatten large apron areas around big
terminals if needed to accommodate a large terminal cluster." 13aq's
partition by pad (4) put the cluster on several planes; the interior
furniture (passengers, seats — members with no pad of their own, cut to
their own ground under (4)) fell through the floor.

7. **ONE UNIT, ONE PLANE, ONE PAD.** A family (§16f (1): shared authored
   datum plane AND one connected plan cluster) whose footprint union exceeds
   `[placement] cluster_pad_min_m2` (design: 5,000 m²) is a CLUSTER: every
   member — walls, roofs, floors, interior furniture, canopies, the pieces
   standing on the apron — takes ONE zero plane, the cluster's datum, with
   no per-member cut to its own ground and no pad partition. The datum is
   the level of the CLUSTER PAD the design surface emits for it (§30 (4)
   below): the family's footprint union, one plane. A member whose own
   contacts sit more than `visual_m` off that plane is REPORTED (the census
   prints it), never re-seated. §16f (5) (pavement is king) yields inside
   the cluster: a wall standing on apron takes the cluster plane, and the
   apron under it is the design surface's business (§30 (4)).

Design-surface counterpart (written into `design-surface-spec.md` §30 (4)):
the cluster pad is one `building` pad over the family's footprint union;
the apron faces within `cluster_apron_reach_m` (design: 60 m) of it take
the pad's plane as their target where the apron and taxiway grade laws
allow (the pad's 1 % and the apron's caps stand; the taxiway family is
never moved by it — the reach stops at a taxiway's own band), so the
terminal's stands are FLAT at the terminal's level; beyond the reach the
apron grades away under its own law.

BARS (KCLT, the registered frame + ONE build; LEMD / OTHH re-read): every
member of KCLT's terminal cluster on ONE plane (zero spread 0.00; today two
pads → two planes and interior members on their own ground); the passengers
/ seats at 35.2191877, −80.9426007 on the floor (their zero = the cluster
plane, not the ground); roof members on their walls (no roof below its
wall top); the stands within the reach flat at the cluster level (apron
z − pad z ≤ 0.05 m inside the reach); taxiway family unmoved (byte-identical
runway/taxi rows); §17 motion rows on the apron around the terminal not
worse than today's; LEMD's old terminal and OTHH's clusters re-read under
the same law (named, not necessarily byte-identical); suite twice.

## RULINGS

## 2026-09-13bj — OWNER READ OF KCLT ON 1.0.327 (verbatim): "1. Terminal object families still settling at different elevations resulting in passengers and seat objects around here: 35.2191877, -80.9426007 sitting on the ground under the building instead of on the floor inside the building. Roof elevations sank in some places as well. These large complex structures have to be seated as a unit. As long as it remains feasible with grade laws and taxiways, etc. it's acceptable to flatten large apron areas around big terminals if needed to accommodate a large terminal cluster. 2. Something is broken around here: 35.2182788, -80.9323415 causing texture tearing and pulling the apron down dramatically here: 35.2178642, -80.9322262 3. Roads along east edge are much better now! 4. Buildings at these locations still have floating roof planes: 35.2141727, -80.9291957; 35.2142131, -80.9282182; 35.2140873, -80.9306125; 35.212974, -80.9298385 5. There's a cliff and texture tearing occurring here: 35.2007757, -80.9455609"

* Item 3 CLOSED (§37 (6)–(9), 13bf). Item 1 is a RULING that supersedes 13aq's "partition by pad": A LARGE TERMINAL CLUSTER IS SEATED AS ONE UNIT, and the DESIGN SURFACE gives it ONE pad — the apron around a big terminal may be FLATTENED to that plane where the grade laws and the taxiways allow. Spec §16f (7) + design-surface §30 (4) written; lane `v2clusterpad` (pack). Items 2, 4, 5 → scout `v2kclt327` (2 and 5 read as the 13an / seam-tear class — a hairline or sliver at a pad/bank/zone join pulling the mesh; 4 is the §16d roof class on four named buildings — which of §16c/§16d/§16f routes their roofs and why the plane sits above the walls).

## 2026-09-13aq — v2family ROUND 1 REPORTED (lane a51348e2, main 864e7577 merged twice; NOT merged — round 2 first) and RULED (Fable, §16f amended). Landed: `placement_family.py` — the family derived (19 members each on KCLT `unit:30` / `unit:31`: `paredes_*_charlotte`, `techos_*`, `suelos_interiores_charlotte`, `vidrios_*`; 194 bodies bound, 194 of the complex's other bodies cut apart and NAMED), one consumer edited (`placement_carrier.carriers_for._ok`: a family-bound body is exempt from §16a (2)'s carrier ground test as a BASIN is — without it every terminal roof went past its walls, files 477 → 609), consumer census of eleven readers in the MEASURED block. KCLT bars: per-row zero spread 9.87 / 0.62 → 0.00 / 0.00 (MET); the complex's two rows 0.47 m apart; `unit:30#0` on `building80` at 221.78 (+0.38, MET); `unit:31#0` on MEDIAN GROUND 221.31 — only 43 of 129 anchors on the pad, so §16d (6)'s majority declined — member vs pad +4.26 m (NOT MET); worst §17 motion row +1.66 → +2.99 m (WORSE: a wall held up over rolled-on apron); visual rows 155 → 140, §15-over-refused 12 → 4, §16b float 45 → 26; plan stage 10.80 → 10.36 s; write run 497 files, outside-box 0, torn seams 1 at +0.00 (v2unboxed's `paredes_9_charlotte` b8↔b12 +0.16 m seam closed by the plane). Two readings REFUTED and deleted: member-level clustering (`Charlotte_Airport_002_ALB__b7` −216.89 m, files 708) and no feasibility share (KCLT `unit:3`'s eight hangars → 26 families, motion 2.52 → 3.73). The "27 basin refusals → 0" bar is NOT MEASURABLE in the object stage (rule 5b is minted in `planar/basins.py` at the obj8 witness; the plan never carries it; admitting the slab as a basin would cut a 4–9 m pit) — bar withdrawn. LEMD NOT byte-identical: 249 of 2,435 bodies change — ONE family of 80 members / 209 bodies at zero 602.86, worst member +8.40 m off its own ground (airport bars flat). Second CONTAMINATED build of the day (the frame build wrote the same `+35-081.dsf.anchor_bak.7bf41307.text` into the shared repo — the 13ao chip, task_08f9a246; no ledger key).

* FABLE'S RULINGS on the three questions, spec §16f (4)–(6): (i) THE FAMILY IS PARTITIONED BY PAD. A connected complex over several emitted `building` pads is several planes — one per pad — with the steps at the pad frontages the design surface already terraces (§28); a member joins the pad group of the pad its contacts stand on by PLURALITY (the largest pad share wins — the spec's "majority" is amended, answering question 2), a member on no pad joins the pad group it touches by contact (§16c (6)), a member touching none is cut to its own ground. This answers LEMD's 80-member terminal (question 1: its pads, not one plane over 8.4 m of ground) and closes KCLT's 0.47 m (both rows on `building80`). (ii) PAVEMENT IS KING OVER THE FAMILY (question 3, §17): a member whose ground contacts are ALL on rolled-on pavement (apron / taxi / runway) is cut apart from its family and seated on that pavement — an object never moves the aircraft; the +2.99 m wall over the apron is the bar. (iii) The "basin refusals 27 → 0" bar is replaced by: every rule-5b-refused member of the family is a family body seated on its pad group's plane (the refusal record names them; the plan need not carry the basin). Round 2 on the SAME lane (resumed, no respawn — 13ap): bars — KCLT both rows on `building80` (residual 0.47 → ≤ 0.3, member vs pad +4.26 → ≤ 0.5), worst §17 motion row ≤ 1.66 (round 1's base) with the wall named, LEMD's 80-member family partitioned by its pads with worst member-off-own-ground ≤ 0.5 m (today 8.40) and the 249 changed bodies re-read (each ≤ 0.5 m off its pad plane), OTHH byte-identical, plan stage ≤ 11 s, seams 0, suite twice. Round 2 uses the registered KCLT frame (`frames.py list KCLT`) — no new build unless the replay cannot state a bar.

## 2026-09-13ay — v2family MERGED (1155a8fe, lane ebd0ecf0 after two rounds): §16f (1)–(6) — the family derived (`placement_family.py`), PARTITIONED BY PAD (plurality), one plane = `median(pad.z)` of the emitted pad's graded ring (KCLT `building80`: 865 ring vertices 221.15 … 222.32 → 221.49), the ground bound held AT THE PAD JOIN (an off-pad member beyond `bind_ground_m` is cut to its own ground — 51 of 91 KCLT family bodies have no pad of their own; lifting them read +4.44 / +8.92 / +12.21 m), PAVEMENT IS KING (§17: `Charlotte_Airport_008_ALB__b13` on its apron at +1.66, no longer a family body), §16a (2)'s round-1 family exemption deleted (the join bound makes it unnecessary). KCLT (registered frame, no new build): the two terminal rows 221.31 / 221.78 → BOTH 221.49 on `building80` (residual 0.47 → 0.00), member vs pad +4.26 → +0.49 / +0.42, worst §17 motion +2.99 → +1.66 (the base), torn seams 1 → 0, visual rows 155 → 128, §16b float 45 → 41, files 487 → 475 (475/475 round trip); pad groups `unit:31#0@building80` (18 members, 97 bodies) and `unit:30#0@building80` (14). LEMD 1.0.325: the 80-member old terminal → `unit:27#3@building4` at 602.34, 23 members / 27 bodies, worst +0.54 (PASS-with-residual, 0.04 over), 20 resources stand apart, 64 of 2,432 bodies changed (was 249). OTHH 1.0.326 NOT byte-identical and not forced: 16 real pad groups (`unit:15#0@building2` 24 members at 3.91, `unit:60#0@building12`, `unit:87#1@building18`, `unit:90#0@building20#2` the only one over 0.5 at +1.00), 233 bodies / 116 placements, visual 309 → 290, §16b float 159 → 152, files 1,831 → 1,788 — every bar flat or better. Plan stage 10.80 → 7.32 s. Suite 1,409/0 twice on main. OWED, named: §16d written-geometry-outside-its-box 0 → 2, both `line_segment`s (`-paredes_7_charlotte__b1` 31.07 m, `__b2` 6.17 m) riding `unit:30` members' files — a segment's `geom_box` is its own station span (§11f (2)) and the family plane changed which file it rides into: a `placement_cut` / `obj8_split` question for the next object-stage lane; the 0.54 / 1.00 residuals (the bound reads the footed body's own contacts, the census reads the written group's feet). Owner item closed: KCLT 13j item 9. `test_v2objsplit.py` 4,560 lines (split by section owed).

## Tool: seat_feet_census

| `Ortho4XP/tools/seat_feet_census.py` | THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3); the placement reading 11e (3), spec §7/§9) — `--placement-plan o4_v2_placement_<ICAO>.json` with `--mesh` (a built mesh) or `--graded` (the emitted design surface, for a dry run with no tile built): per placement of the plan's own rows, `surface(foot) − (surface(anchor) + y_foot)`, the |Δ| histogram (<0.3 / 0.3-1 / 1-3 / >3 m), the same by class, the worst N with lat/lon, and §13's elevated-body / footless-carrier bars. Feet are read from the AUTHORED pack (`.anchor_bak` when one exists). THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8) — the name is kept because the INDEX row, `obj8_split_report` and the twins address it by it. Writes nothing to the pack. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. CRITICAL MOTION is named as an instrument limit rather than printed as a zero HERE: §17's motion reading needs the graded face ROLE under each foot, and this tool hands the block none — `obj8_split_report.py` is the entry that takes it (owner RULINGS 2026-09-12am (2), lane `v2objmotion`). §16e (owner RULINGS 2026-09-13k, lane `v2othhdatums`): `--placement-plan --mesh` WAS BROKEN — it passed its bbox as `(lat, lon)` to `MeshElevationSampler`, which takes `(min_lon, min_lat, max_lon, max_lat)`, so at OTHH it asked for a box at lon 25.2 / lat 51.6 and the sampler raised `no mesh triangles inside ... — wrong tile?`; the one place the two orders meet is now `plan_bounds()` and a twin holds it end to end over the sampler's own mesh fixture. The report also prints `§16e bodies on a DATUM` (a crest plate / a deck top) as its own class and EXCLUDES them from §13's `elevated bodies as own files` bar: a datum body's `y_zero` is +5 … +10 m by construction, and counting it there reported the law as the defect (OTHH 0 -> 10 -> 0 with the class printed apart). §16e (3) (Fable 2026-09-13, RULINGS 2026-09-13v, lane `v2bridgecontact`): the report also prints THE BRIDGE FAMILY block (`airport/bridge_family.census_bridges` / `census_bridges_lines`, re-exported through `placement_census`, the same call `obj8_split_report` makes over the same plan shape) — per `Bridge_NN` the deck's own body's world DECK TOP against the land under that bridge's own written geometry (`|deck top - highest land|`, bar `[cockpit] visual_m` 0.5 m), the PER-PLACEMENT zero spread (`max - min` of `surface_z - y_zero` over one placement's bodies; `Bridge_02_CLUTTER_007` is six piers of ONE solid), the CROSS-BRIDGE carriers (a body whose `merged_into` names a file of another bridge, bar 0) and how many bodies publish `bridge_of` and agree with the resource's own tag. The `Bridge_NN` axis is the CENSUS's, never the law's — §16e (3) exists because the name does not name a bridge — so the agreement count is the instrument's own check on the derived relation. Measured on the app's 1.0.326 OTHH frame: `Bridge_01` deck top 3.23 -> 3.96 and `Bridge_04`/`Bridge_05` KEPT -> 3.96 (all three |deck top - land| 0.00, PASS), cross-bridge carriers 2 (unchanged — the bind and the filter are refuted and deleted, see `bridge_family`'s module doc). |

## Tool: obj8_split_report

| `Ortho4XP/tools/obj8_split_report.py` | THE OBJ8 SPLIT, DRY-RUN (spec `object-placement-spec.md` §4 / §6 / §7; owner RULINGS 2026-09-11b) — what a pack's object stage becomes once placements are AGL, objects are cut into their RIGID BODIES and each body carries its own anchor. Reads only a build's own two products — the re-seat plan (`<ICAO>.rebake.json`: the pack read once, its welded parts and the ε-contact graph) and the emitted DESIGN SURFACE (`<ICAO>.graded.json`, whose `building` faces are the object pads and `structure_rim` breaklines the basin walls) — and NEVER opens the pack for writing, never reads the DSF and never builds anything. Prints per placement the bodies, their §6 class, each body's anchor point / reason / authored offset, the files that would be written and the placements KEPT WHOLE with the reason (`one_body`, `anim`, `unparsable`); `--write-into DIR` writes every cut file into a scratch dir and parses each back through `airport/obj8.parse_obj8` (LEMD 13,924 files, OTHH 65,360, all parsing back with the written triangle count, 2026-09-11); and prints §7's CENSUS — the design surface at a body's ANCHOR against the surface under each of its ground-contact FEET, the |Δ| histogram `seat_feet_census.py` prints from a mesh and a seat result, read instead from the plan and the design surface so the two are comparable. A foot or anchor outside every graded face reads `off-surface` and is never guessed at (the DEM governs there and this tool does not open the DEM). `--no-cut` for body counts only, `--filter`, `--json`, `--split-tol` to override `[placement] split_tol_m`. ROUND 2 (owner RULINGS 2026-09-11e, spec §9): the bodies are COARSENED (bodies of one placement whose intended-zero terrain heights agree within `split_tol_m` are one file, the senior body's anchor; an elevated body joins the nearest ground group) and each anchor is the GENERIC one (the footprint point where the design surface equals the body's zero; a body with authored relief beyond its skirt takes its low-side foot and is reported with the residual) — LEMD 302 placements -> 985 files (3.26x), OTHH 954 -> 1,172 (1.23x). §13 (owner RULINGS 2026-09-11r/s): an ELEVATED body — one whose lowest authored vertex, or the `y_zero` of the anchor the generic rule gives it, stands above `[rebake] elevated_base_m` — NEVER has a file of its own; it joins its CARRIER (the same placement's ground body with the largest plan overlap, else the nearest) at its authored offset, and a placement with NO ground body is KEPT WHOLE with reason `footless`. The report prints the two classes by name — `elevated bodies as own files` (BAR 0) and `footless placements kept whole` — because the FEET histogram cannot see this defect: the writer shifts an elevated body so its own lowest vertex lands on the terrain and every foot then reads perfect (LEMD's 218 roofs/decks/tower parts censused green while the sim was broken). Measured on matched pack copies: LEMD own-files 278 -> 0, files 1,099 -> 828, feet > 3 m 1,060 -> 151, worst 34.06 -> 13.75 m; OTHH 1,203 -> 333 files, feet > 3 m 952 -> 6. ROUND 3 (owner RULINGS 2026-09-11f, spec §10): the write half RESTORES every `<obj>.anchor_bak` in the pack before any file is written (counts in the plan's provenance), and a LINE OBJECT authored as one component is cut into SEGMENTS by triangle station (`--line-segment M` overrides `[placement] line_segment_m`; 0 disarms it) — LEMD 897 segments from 271 one-line bodies, 985 -> 1,086 files, census `> 3 m` 30 -> 25; OTHH 1,187 files, `> 3 m` 0. `--write-pack PACK_COPY` runs THE WHOLE WRITE HALF into a pack COPY through `airport/placement_write.apply_plan` (cut files, DSF + backup + provenance, dump-cache refresh, `o4_v2_placement_<ICAO>.json`) and reads the written DSF back; it REFUSES a live X-Plane install. The census also splits the feet over 0.3 m into BURIED (lawful) and FLOATING (the defect the eye reads). `--rows SUBSTR,SUBSTR` (lane `v2canopy4`) prints the PER-BODY rows of the placements named — the body's anchor (point, surface z, `y_zero`, reason), its ground-contact feet, its worst foot signed with |Δ|, and the 0.3 m verdict — for the owner's named sites (`OldTerminal_FSX-LEMD38,-LEMD84,-LEMD60`); it is a PROJECTION of the one census pass, never a second instrument (the bins, feet and worst list are identical with and without it, twinned). §14 (owner RULINGS 2026-09-11u/v, lane `v2carrier`): a FOOTLESS placement is CARRIED — written as a body file at its CARRIER's anchor with the carrier's `y_zero` (the footed body of its UNIT it abuts with the largest contact, else the nearest, else the largest) — a BASIN resource is never split and anchors at a RIM point where the design surface equals its zero (`rims` wired at last), and bodies of one resource that OVERLAP IN PLAN bind whatever the contact graph says. The report prints the four §14 bars (`footless at datum` 0, `footless on ground` 0, `basin bodies split` 0, `spread`) beside §13's, from `airport/placement_carrier.census_v14` — the same call `seat_feet_census --placement-plan` makes over the same plan shape, so the two instruments are one code path. Measured on the app's 1.0.315 LEMD frame: the four footbridge resources at the terminal's zero 616.65 (deck bottom road + 4.4-5.0 m, was ON the road), `Terminal4SAT_pink-LEMD01` at its terminal's 597.43, the basin's three resources one file each on ONE rim vertex (zero spread 7.0 m -> 0.00, parapet +2.99 above the rim), files 828 -> 855, round trip OK, row census `> 3 m` 17. Twin: `tests/auto_patch_v2/test_v2objsplit.py`. §15 (owner RULINGS 2026-09-11ae, lane `v2roofcarrier`): the CARRIER IS WHAT THE BODY STANDS OVER — chosen across the whole UNIT, every resource alike, by largest PLAN OVERLAP beneath, else largest contact, else nearest (§13's same-placement scope and §14's contact-first order are superseded; the pack names its roofs as their own resources, so the walls a roof rides are almost never its own file); the plan-overlap BOND is RE-CUT where a bound group's intended zeros span more than `split_tol_m` (a rigid body is never wider than the terrain it can stand on; BASIN exempt); DUPLICATE ROWS of one resource identical in lon/lat/heading are ONE placement, all of them replaced (`--write-pack` reports `duplicate rows of a SPLIT placement ... surviving after the write`, bar 0); an anchor or foot on no graded face is marked OFF-SHEET and excluded from every comparison and bar; and the report prints §15 (3)'s `stands-over float > 0.5 m` from `airport/placement_carrier.census_v15` — `float = zero - zero_beneath`, the class NEITHER the feet histogram nor §14's bars can see (a carried body has no feet at all), barred at 0 for CARRIED bodies and reported for footed ones. §16 (owner RULINGS 2026-09-11ai, lane `v2skipped`): the report adds the POPULATION census (`placement_carrier.census_population`: `rows on the datum outside the plan` — the resources the SEAT-era thickness gate dropped, which keep the pack's shared-datum row and render where the datum is, bar 0 — beside the lawful skips and the multi-anchor class, reported not barred) and `census_v16`'s `float = zero - ground_under_geometry`: the ground read under the body's OWN parts (`geom_box` / `foot_boxes`, the median of the part-box centres) and never under its carrier's box — `CARRIED bodies whose carrier's zero is over 1 m from the ground under their own geometry` (bar 0; LEMD 39 -> 0 on matched arms) and `files whose own-geometry ground departs over 3 m from the ground at their row` (26, reported). `--admit-skipped PACK_ROOT` puts the thickness-gated resources of a PRE-§16 plan back into the population by reading their rows from the pack's own DSF (one part per component, no contact graph, the member id IS the DSF row index) — what a build's own plan now carries, for replaying a plan written before the switch; LEMD 25 resources / 25 rows, OTHH 99. §16a (owner RULINGS 2026-09-11aj, lane `v2skipped2`): a CARRIED body is cut where its CARRIER is cut (one piece per carrier terrain group its own triangles stand over, each riding that group's zero; never by the ground under itself), the ground check moved to the carrier's OWN feet (`Candidate.ground_off`, `surface(foot) - y_foot` against the body's zero), and `census_v16`'s carried number demoted to INFORMATION — the bar for a carried body is §15 (3)'s `zero - zero_beneath`. The report prints `carried bodies left uncut by the ground` / `cut by their CARRIER into N piece(s)` and, beside the §15 bar, how many of the carried floats stand over a body the law REFUSES as a carrier. LEMD carried float 58 → 4, files 1,591 → 1,328, plan stage 9.9 → 6.3 s; OTHH 7 → 39, 46.4 → 60.2 s (both OTHH bars missed and reported). 11ak (lane `v2skipped3`): the CARRIED bar's `beneath` is the carrier THE LAW CHOSE (`merged_into`, resolved by identity over every row that reads a zero — a carrier written WHOLE names its MEMBER RESOURCE, which is the whole of OTHH's residual), and a body the law REFUSES as a carrier is counted and named as its own class, `carried over a refused body`, with how far its own feet stand off; §16 (2) also cuts BY FOOT (`placement_cut._LineCutter.foot_groups`: the feet grouped by the zero each says the body has, `surface(foot) - y_foot`, each triangle joining the group of the foot nearest it in plan) — the class no ground cut can see, a body whose FEET are authored over metres of relief on terrain that barely moves, which is exactly what §16a (2) refuses. The re-cut line prints the three cuts (terrain / triangle / foot). LEMD carried float 4 → 0, refused carriers 117 → 21 (13 of the residue are rim-anchored BASIN bodies the foot cut is exempt from), files 1,328 → 1,371, plan stage 6.2 → 5.66 s; OTHH carried 42 → 0, refused 55 → 19, files 1,679 → 1,622, plan stage 59 → 31 s (`solid_components` read in one sort instead of a mask per component; `bind_plan_overlaps` swept by the hull's south edge). 11al (lane `v2basincarry`): a BASIN body is EXEMPT from §16a (2)'s ground test — its zero is the RIM (§14 (2)) and its floor feet are authored below it by construction — so it may carry, and the report prints `§16a (2) basin carriers` (how many basins, how many the feet test would have refused) beside the refusal set: LEMD refused carriers 21 → 8, OTHH 19 → 4, carried float 0/0 unchanged. §14a (owner RULINGS 2026-09-11ap item 6, lane `v2basinring`): a BASIN body follows its RING. §24 (1) puts the rim vertices at the APRON's level, so the ring is not level (LEMD's T4 pit 597.68 … 599.52 over 59 nodes) while §14 (2) wrote every basin body at ONE rim point — the owner's "gap between wall and apron", +0.71 / −1.13 m, while the §14 `spread` bar read 0.01 because it measures the pit's bodies against EACH OTHER. `airport/basin_ring.py` (NEW: the whole law — `arcs_of`, `ring_arcs`, `member_kind`, `ring_bar`) cuts the ring into ARCS whose z agrees within `split_tol_m` and cuts each basin body's WALL BAND by them, one piece per arc anchored at that arc's rim point (the interior remainder keeps §14 (2)'s single point: the trench floor is one level); and a member authored AT THE RIM PLANE but standing inside the ring is a FLOOR body that takes §16 (3)'s ground under its own footprint, never the rim, never a carrier. The report prints the RE-DEFINED bar — `§14a spread of a BASIN RING = max |wall base − ring z| over its nodes` (bar ≤ `split_tol_m`), with the nodes on an arc the pit has NO WALL on reported beside it — and the `§14a basin FLOOR members` / `basin bodies cut by the ring's ARCS` counts. It needs the rings WITH their heights (`census_v14(rims=..., arc_cap=..., counts=...)`; `RimRing.z`, and the `basin_arc_wall:<ref>#<k>` counts keys the cut writes are how the bar tells "no wall here" from "the wall is written in the interior piece"). Matched arms on the app's 1.0.319 LEMD frame: the ring bar 1.12 m / 9 nodes over → **0.18 m / 0 over**, `LEMD13__b0` off the rim and onto its own ground, files 1,371 → 1,394, feet > 3 m 518 → 412, floating 9,509 → 9,014; OTHH's 21 basin carriers and its whole foot census byte-identical. §16b (owner RULINGS 2026-09-11ap, lane `v2owncut`): the TERRAIN CUT IS PRIOR AND UNIVERSAL and is read on the body's OWN WRITTEN TRIANGLES — including everything the writer will put in the file (`placement_cut._LineCutter.all_tris`: a placement the plan reads as ONE body is written as the WHOLE object, which is why `green-TEJ3`'s 4-triangle part read 0.22 m of ground while its 2,342 m file stood +16.22 m over it) — so a CARRIED body is divided by the ground under itself first and §16a (1)'s carrier cut runs inside each piece; §9's coarsening additionally requires PLAN CONTIGUITY (`[placement] coarsen_reach_m`, 30 m) and acts WITHIN a terrain group (the pieces carry the ground they stand on, or the very next pass welds them back); each PIECE finds its own carrier, and a FALLBACK candidate (contact / nearest / largest, no plan overlap) is refused unless its zero is within `split_tol_m` of the ground under the piece (`carrier_refused_far_from_carried_ground`). The report prints `census_v16b`'s two bars over the WRITTEN geometry the plan now publishes per body (`geom_pts`, one sample per 10 m cell, thinned to 32 by the farthest-point walk): `carried piece float over its own ground > 0.5 m` and `body wider than its terrain group`, both bar 0, with the BASIN exemptions (§14 (2) / 11al) counted apart and the wide residue split by class. `--coarsen-reach M` overrides the contiguity reach. Measured on the app's 1.0.319 LEMD frame: the owner's item 3 +10.74 → the plate ON the roof beneath it (618.58 vs the group's 618.60), item 5 +16.22 → 620.38 vs 620.27, `Terminal4_48` zero-vs-ground −4.02 → median −0.01, `Taxisigns-SENRG` 38 of 80 bodies over 0.3 m → 12 of 419; files 1,371 → 3,272 at the amended 100 m reach (4,633 at the refuted 30 m), plan stage 5.6 → 10.1 s (bar ≤ 8 s MISSED, reported). §16c (owner RULINGS 2026-09-12b/12d, lane `v2atom`): THE CONNECTED COMPONENT IS THE ATOM — `--torn-seams PACK_ROOT` prints the TORN-SEAM CENSUS over a WRITTEN pack (the plan argument is then the WRITTEN `o4_v2_placement_<ICAO>.json` and `--graded` is not read), and the same census prints automatically after `--write-pack`: sibling files of ONE placement that share an AUTHORED VERTEX (the key `obj8.solid_components` welds on, `round(x, 3)`) are two halves of one connected solid written at two zeros, with the base step per seam, the step histogram, the worst list and the per-class breakdown, and §10's line segments / §14a's basin arcs — the only lawful station cuts — counted APART.  Two bars, both 0: `torn seams outside line/arc pieces` and `single-component resources in >= 2 files`.  The instrument is the scout `v2lemd320`'s `tear.py`, promoted on its second use, and lives in `airport/placement_seams.py` (`census_torn_seams` / `census_torn_seams_lines`, re-exported through `placement_census`).  Measured on the live 1.0.320 LEMD pack it reproduces the owner's four sites exactly (`HANG3` 10 files / 14 seams worst 3.05 m; `green-LEMD50` 7 / 11.12 m; `Bridge2` 8 / 11.72 m; `green-STRT4` 53 files, `__b44` 16.29 m) and the class (2,554 seams, 1,994 over 0.30 m).  On matched replay arms the law takes LEMD 723 -> **0** seams and 128 -> **0** single-component splits (files 3,253 -> 2,804, plan stage 13.5 -> 10.2 s over 3 runs, round trip OK), OTHH 639 -> **1** and 165 -> **1** (files 1,897 -> 1,898). §16c (6) (RULINGS 2026-09-12h, round 2): `--contact-eps M` overrides `[placement] contact_eps_m` (2 mm) — components of ONE resource whose geometry comes within it, or whose parts the rebake plan's ε-contact graph already links, BIND into one rigid body for anchoring (one zero, the senior component's carrier): OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart that the millimetre weld key reads as separate.  LEMD files 2,804 -> 2,776, seams stay 0, `Terminal4_48` zero spread 3.58 -> 0.69 m, plan stage 9.6 s (main 13.5). ROUND 3 (RULINGS 2026-09-12j): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit (a round-2 OTHH `--admit-skipped` run had created `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` in the SHARED repo with both lane-local cache env vars exported and nothing refused it); every run prints `[guard] shared repo UNCHANGED`.  `--rigid-reach M` overrides `[placement] rigid_reach_m` (2.0) — §16c (8): SOLID components of one resource within it chain into ONE rigid cluster, which is the atom of the BODY as well as of the cut (LINE objects excluded).  `carrier_fill_min` is DELETED from carrier candidacy (§16c (7)); the CLASS exclusion stays.  LEMD: `HANG3` 6 files / 1.37 m -> 2 / 0.45, `green-STRT4` 23 -> 15 files (spread 8.90 -> 3.73), files 2,776 -> 2,121, §16b wide 1,405 -> 967, seams 0, round trip OK; five largest rigid clusters are all SINGLE components (5,157 / 2,890 / 2,514 m — fences and VOR markers, not chained) and `green-TEJ3` stays 9 components / 9 clusters. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. **§17 CRITICAL MOTION IS READ** (owner RULINGS 2026-09-12am (2), lane `v2objmotion`): the graded surface's FACE ROLE under every foot (`airport/placement_boxes.GradedRoles` / `graded_roles_from_doc`, built from the SAME parsed `<ICAO>.graded.json` the sampler and the pads are, senior face by `precedence.toml`'s authority order, a 55 m grid over the faces' boxes) joined to §7's own float there (`airport/placement_motion.census_motion`, re-exported through `placement_census`): a body with a foot on a ROLLED-ON face (`law.tables.rolled_on_roles`) is ON PAVEMENT and every such foot is judged at `[cockpit] motion_step_m` 0.05 m, named with resource, foot coordinate, face role and SIGN. The block prints the count of bodies on pavement, the feet over the threshold, the worst ten, and the breakdowns by resource / face role / body class / anchor rule / size band, plus what the EYE reads at those feet (floating vs buried over `visual_m`) and the MEDIAN-anchor arm. BASIN bodies are counted APART (§14 (2) / 11al: a pit's zero is its rim and its floor feet are authored below it — they were LEMD's whole worst ten). Measured on the 1.0.320 LEMD frame: 493 of 2,153 bodies stand on pavement, 7,124 feet on 399 over 0.05 m; after the §17 anchor rule 6,635 on 407 (OTHH 6,234 → 3,877 on 113 → 103). RULINGS 2026-09-12ap (lane `v2pavefeet`): `--motion-rows OUT.json` writes §17's PER-BODY projection — one row per written body with its anchor, class, anchor reason and every ground-contact foot (lat/lon, authored y, surface z, face role, on-pavement, float) — the rows `census_motion` itself reads, never a second census (the scout's scratchpad projection, promoted on its second use). (E) THE SAMPLER HONOURS GRADED HOLES: a Delaunay over the emitted VERTICES spans a hole ring with triangles reaching from an apron vertex to a trench vertex, and LEMD read **592.22 m at a point whose ROLE is apron** six metres outside the hole — 12ap's two worst pavement feet (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` −5.08) were that fabricated ramp, and the anchor correction is 6.91 m. A simplex CROSSING a hole ring with a step over `split_tol_m` is struck and a point inside one reads the nearest vertex of that simplex ON ITS OWN SIDE of the ring; measured narrowings: "centroid on no face" struck 8,689 of 47,287 simplices and cost 421 files / 435 off-sheet bodies, and a strike with no side-aware read cost 160. (B) §17 is judged at the GROUND-CONTACT feet — the in-band feet within `split_tol_m` of the lowest (`placement_motion.ground_contact_feet`); `contact_band_m` is shared law and unchanged, BOTH sets are sampled and the wider reading prints beside the judged one so the report states its own attribution. (A) `bind_ground_m` (`[cockpit] visual_m`) bounds §16c (7): a FOOTED body of ANOTHER member keeps the cluster only while its own zero is within it of the senior's, else it keeps its own anchor and is counted — the report prints `bound refused for ground N` with the worst refused disagreement and the widest RETAINED cluster zero-plane span. Matched arms, LEMD main → branch: CRITICAL MOTION 6,640 → 5,400 feet on 407 → 356 bodies, over 0.5 m FLOATING 663 → 128 and BURIED 1,109 → 808 (of which (B) alone 581 → 128 / 816 → 808), worst pavement foot +7.18 → +2.41 m, 74 binds refused (worst 2.38 m), files 2,107 → 2,149, seams 0/0, round trip OK, plan stage 10.19 → 10.03 s; OTHH 3,891 → 2,822 feet on 103 → 74, floating 332 → 12, §14 footless at datum 5 → 4, files 1,252 → 1,269, plan stage 60.8 → 61.4 s (the ≤ 60 s bar missed on BOTH arms). §16b's carried-piece float and wide counts move the WRONG way at both airports (LEMD 111 → 119 / 967 → 983, OTHH 126 → 135 / 75 → 78) and are named. §16d (owner RULINGS 2026-09-13h, lane `v2unboxed`): THE PLAN BOXES WHAT THE WRITER WRITES — a WRITTEN-FRAME bar beside the torn seams, `§16d bodies with written geometry > 1 m outside their geom_box` (`airport/placement_seams.census_outside_box`, printed after `--write-pack` and by `--torn-seams`, bar 0): `geom_box` was the hull of the ADMITTED PARTS while the writer emitted the source object's triangles regardless, so a component no part named (the FS2XPlane origin plate, an exporter's ground paint, a roof plate over the next hangar) rode a zero the body chose elsewhere and NO instrument read it — LEMD 1.0.325 live pack 378 of 2,109 bodies, 8 over a kilometre. Every connected component the writer will emit — draped ones included — is now PLACED: within `coarsen_reach_m` of a ground group's part hull it joins that group and `geom_box` grows to the hull of what the file will contain; beyond it, it is a FOOTLESS BODY §15's search places, or §16 (3)'s own ground (`--coarsen-reach 0` disarms the reach and the component joins the nearest body, the pre-§16d reading). The nearest-footed fallback is CAPPED at the same reach (`carrier_refused_nearest_beyond_reach`), and the COCKPIT block names the worst row by the centre of the BODY'S OWN written geometry, never the placement row (a shared-datum pack puts 96.5 % of its bodies on two points). `plan stage: N.NN s` is printed after the split — the number a round's budget is quoted in, timed exactly where the shipped engine's own `build_splits` call is, without the graded parse or the census. Matched dry arms on the 1.0.325 LEMD frame (the app's own arm reads a MESH sampler where the tool reads a Delaunay over the graded vertices — the two disagree on every surface-driven refusal and the bars are read dry-to-dry): outside-box 390 → **0**, nearest-footed over 100 m 29 → **0**, the four shadow plates +15.94/+15.73/+5.77/+1.72 → **−5.00 on their own ground**, `Cargo-TEJ1` on `NEWCO__b9` roof base 604.95 (bar 0.3 of 605.04), seams 0/0, §15 carried float 0/0, round trip OK, files 2,141 → 2,279, LEMD plan stage 13.6 → 17.8 s and OTHH ≈83 → 86.1 s (both bars missed on BOTH arms, named). It also fixed a latent WRITER defect: the cut file was named by its index in the LIVE body list while the DSF row is written on the plan's `body_id` name, so a body the cut left with no triangle shifted every later body's file one name down (`OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s object). §16d (4)-(6) (owner RULINGS 2026-09-13m, same lane, second frame KCLT 1.0.324): a CARRIED body's components group BY CARRIER — each ATOM (§16c (1)'s, so a rigid cluster is never divided) asks its own carrier question BEFORE the search, counted as `carried bodies cut by ATOM`, where §16a (1)'s after-the-fact cut could only divide the answer the whole body got (KCLT 5,295 carried bodies left uncut against 3 cut; a native pack's master roof model spans 1,774 m); §16c (7)'s 0.5 m ground bound is MEMBER-AGNOSTIC (12ap tested `member != top.member`, and a native pack's one-model-per-material member spans the airport: KCLT's `005_ALB__b9` sank 5.04 m into its pad on a same-member bind to an apron body 500 m away); and a FOOTED body whose ground contacts lie mostly inside one emitted `building` pad reads only the contacts ON it (`anchor_rule.pad_majority`; the anchor reason then says `on pad <ref>`). Matched dry arms at KCLT: `005_ALB__b9` -5.85 -> **+0.02** against its pad, widest retained cluster zero span 5.69 -> **0.64 m**, 473 carried bodies divided by atom, 61 bodies anchored on their pad, `building80`'s on-pad zero spread 1.03 m (the pad's own relief 1.19), §16d outside-box **0**, §15 carried float **0**, round trip OK 477/477, one new torn seam (+0.16 m, one shared vertex, named), files 473 -> 477, plan stage 8.65 -> 8.3-8.5 s. It also exposed a defect the atom cut made visible: a target group holding BOTH a cut piece and an untouched raw was read for its `tris` alone, leaving 990-3,280 triangles per placement claimed by no body (9 of KCLT's 103) for `obj8_split` to hand to the nearest one — the audit reads 0 of 103 after. **COST: plan stage LEMD 17.8 -> 25-46 s and OTHH 86 -> 136 s** (KCLT flat) — the per-atom carrier search, narrowed by a `coarsen_reach_m` span gate, a 64-atom cap, per-atom pids and a set-intersection contact count, and still needing the owner's approval and a Fable-5 review before it ships. |

## Registered frames: KCLT

KCLT  capture  base ec8723e9   lane v2eat            2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2eat/cap  — captures of KCLT/HECA/OTHH/SPJC by lane v2eat; base predates the 13ak pad-law break — valid
KCLT  rebake   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.rebake.json  — v2familyKCLTframe build (rc 0, 389.3 s, body_sha bb022a77f067) on main 864e7577 — POST 13ak pad-law fix; the build was CONTAMINATED (one Airport_mod_cache dump, chip 13ao) so it carries no ledger key
KCLT  graded   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.graded.json  — the design surface of the same v2familyKCLTframe build
KCLT  capture  base 70646dc8   lane v2roadramp       2026-09-13T12:44:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/KCLT.pkl

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; files under 1,000 lines.
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

