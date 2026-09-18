# Scout `hecat3split` — HECA Terminal 3 "separating vertically in pieces"

Base main `ef8377a0`. Read-only: no build, no tree edit, no shared-repo write.
Products read: `/Users/noah/XPTerrainBuilderData/Patches/+30+030/+30+031/`
(`o4_v2_placement_HECA.json` 09-17 19:39, `o4_v2_rebake_HECA.json` 19:37,
`HECA.graded.json` 19:37, `HECA_auto.patch.osm` 19:36) and the mod-cache DSF
text dumps in `/Users/noah/XPTerrainBuilderData/Airport_mod_cache/c_EGY - 100_airport - HECA Cairo (Tai Models)/`.
Offline replays used only `RebakePlan` + `footprint_unit.plan_units_and_connectors`
in-process; they reproduce the shipped counts EXACTLY (`unit_chain_bodies` 7,264 /
`unit_leaf_bodies` 16,901 / `unit_chain_no_polygon` 1,152 — identical to
`provenance.counts`), so the unit derivation replayed here IS the shipped one.

## HEADLINE

The T3 shell is not "placed six times". It is **ONE placement** (`o4_v2_placement_HECA.json`,
placement index 230, `Airport/T23/T3_brick_clean.obj`, lon 31.412026019 lat 30.112118049,
heading 0.0) that the object stage cuts into **30 written bodies on 28 distinct datums
spanning 6.61 m**; six of them fall within 60 m of the owner's point.

The discriminator that keeps them out of the terminal's unit is **§16g (10) (4)
`chain_min_height_m = 2.5`** (`Ortho4XP/src/auto_patch_v2/law/structures.toml:889`)
acting on a **material-sliced, shared-datum pack** (RULINGS 2026-09-17o; spec §48):
every ground-contact component of the T3 shell is a **0.49 m plinth**, i.e. a LEAF that
links nothing; the shell's real walls are **elevated** components (base_y 10.66 m, no
feet) which are not candidates at all. A candidate whose own footed parts are all leaves
**names no unit** at the pid join (`airport/footprint_unit.py:636-641`) and falls
through to `anchor_rule.anchor_for`, which seats it on its own plinths' ground — and
that ground is a lawfully sloping apron spanning 5.43 m.

It is **not new in 1.0.348**: the per-body split has been written into the DSF since
2026-09-12 at the latest.

---

## Q1 — THE T3 CENSUS

**Scope.** `Airport/T23/*` is 98 placements / 2,167 written bodies of 417 splits
(`o4_v2_placement_HECA.json`); ONE placement per resource — the pack is one `.obj` per
MATERIAL (RULINGS 2026-09-17o names HECA T23 as the material-sliced class), so a
"resource" is a texture, not a building, and its components are scattered over the whole
T2/T3 district.

Airport-wide T23: `surface_z` 80.593 … 124.601, **386 distinct datums** at 1 cm.
Seat reasons over the 2,167 bodies:

| reason class | bodies |
|---|---|
| `footless_own_ground` | 1,178 |
| `carried by …` | 367 |
| `§16c (7) bound to …` | 284 |
| `§16g unit …` | 245 |
| `surface at the body's zero` | 45 |
| `low-side foot …` | 24 |
| `median foot … rolled-on pavement (§17)` | 12 |
| line-segment stations / basin rim | 14 |

**At the owner's point (30.1080544, 31.3958302), radius 60 m: 98 bodies, ALL `Airport/T23/*`.**
Datums: **18 distinct at 1 cm — 97.54, 97.81, 97.99, 98.66, 99.08, 99.15, 99.18, 99.27,
99.28, 99.29, 99.32, 99.37, 99.40, 99.59, 99.66, 99.72, 99.79, 100.16 — span 2.62 m.**
Seat classes there: carried 58, §16c (7) bound 25, §16g unit 10, §17 median foot 3,
"surface at the body's zero" 2. Units: `fu:42:4016@cluster_pad` 6, `fu:42:4016/c0@pad` 1,
`None` 91.

**Grouped by carrier** (the datum each group inherits; full table at
`…/scratchpad/t3/site_table.txt`):

| carrier file | bodies | datum |
|---|---|---|
| `T3_brick_clean__b5_df2ff10b.obj` | 28 | 99.315 |
| `T3_brick_clean__b12_8ca4707a.obj` | 11 | 99.793 |
| `T3_brick_clean__b5.obj` | 8 | 99.315 |
| `T3_brick_clean__b4_a8051aef.obj` | 8 | 98.656 |
| `titles_1__b4.obj` | 7 | 97.991 |
| `T3_concrete__b0_7c9c77aa.obj` | 5 | 97.536 |
| `T3_brick_clean__b10_e6d7ad3e.obj` | 4 | 99.151 |
| `T3_brick_clean__b13_8613214c.obj` | 3 | 100.155 |
| `T3_brick_clean__b10.obj` / `__b12.obj` / `__b4.obj` | 2 / 1 / 1 | 99.151 / 99.793 / 98.656 |
| `AC_Electronics__b1_1d93c846.obj` | 2 | 99.271 |
| `door__b1_2944bbbc.obj` / `titles_1__b4_0f584e39.obj` | 1 / 1 | 99.276 / 97.991 |

The six `T3_brick_clean` bodies at the site, verbatim:

| body | surface_z | y_zero | feet | anchor_reason |
|---|---|---|---|---|
| b4  | 98.656 | −0.196 | 4  | `surface at the body's zero` |
| b5  | 99.315 | −0.196 | 36 | `surface at the body's zero` |
| b10 | 99.151 | −0.196 | 4  | `median foot: every foot on rolled-on pavement (§17, motion; terrain spread 0.63 m)` |
| b12 | 99.793 | +0.290 | 4  | `median foot: … (terrain spread 0.33 m)` |
| b13 | 100.155 | −0.196 | 8 | `median foot: … (terrain spread 0.35 m)` |
| b14 | 99.315 | −0.196 | 16 | `§16c (7) bound to Airport/T23/T3_brick_clean__b5.obj (…senior by feet then footprint; own ground +0.30 m)` |

plus `T3_brick_clean b0` 97.812 (`§16g unit fu:42:4016/c0@pad of 2 member(s) on pad
building9 at 97.19`, a §16g (6)/(7) CONNECTOR) and `T3_concrete b0` 97.536
(`§16g unit fu:42:4016@cluster_pad of 50 member(s) on pad building9 at 96.24`).
NONE of the six carries the ` on pad …` suffix `anchor_rule.py:696-703` appends, so
`pad_majority` found no pad under their feet — they stand on bare apron.

**Max vertical offset between two pieces AUTHORED IN CONTACT.** Joining the rebake
plan's own ε-contact graph (`o4_v2_rebake_HECA.json` `contacts`, 120,159 pid pairs;
`[placement] contact_eps_m = 0.002` m, `law/structures.toml:754`) to the written bodies:

* whole `Airport/T23/*`: **21,202** contact pairs cross a written-body boundary —
  8,229 carry > 0.05 m, 2,032 carry > 0.5 m, median 0.000, p99 2.01 m, **max 11.84 m**
  (`palm.obj:b139` 108.57 ↔ `metal.obj:b496` 96.73).
* within 60 m of the owner's point: **1,473** cross-body contact pairs — 435 > 0.05 m,
  190 > 0.5 m, **max 2.343 m** (`T3_brick_clean:b0` 97.81 ↔ `black_plastic:b20` 100.16).
* within 150 m: 2,021 pairs, max **2.732 m** (`T3_concrete:b0` 97.54 ↔ `T3_brick_clean:b17` 100.27).

That is the owner's read quantified: pieces the pack welded to each other at 2 mm are
written up to 2.34 m apart at his viewpoint.

## Q2 — WHAT THE PACK AUTHORED

Pristine dump `+30+031.dsf.anchor_bak.a636e364.text` (09-13 14:57; `dsf_write.pristine_dsf_path`):

* 529 `OBJECT_DEF`, **3,220 plain `OBJECT` + 216 `OBJECT_AGL`, ZERO `OBJECT_MSL`.**
* 111 `Airport/T23/*` defs carrying **236 `OBJECT` + 7 `OBJECT_AGL`** rows — no MSL.
* **382 rows sit at ONE coordinate, `31.412026017 30.112118048`** (199 `OBJECT`,
  183 `OBJECT_AGL`), heading `0.000000`, elevation field `0.000000`.
  `T3_brick_clean` (def 224), `T3_4` (229), `ceiling_2` (283), `titles_1` (214),
  `T3_concrete` (220), `floor` (274) are each exactly one such row.

So **yes — this is a SHARED-DATUM pack of the LSGG class**: one anchor, drape-on-terrain
(AGL), every object's world position carried inside its own geometry. The pack intends
ONE datum for the whole terminal. (Matches RULINGS 2026-09-17o: "zero `OBJECT_MSL` rows
in all four packs".)

**Is the split written into the DSF?** Yes — but not as MSL. The written dump
`+30+031.dsf.773d33f0.text` (09-17 19:39) carries 5,387 defs, of which **2,278 are
`Airport/T23/*`** and **31 are `T3_brick_clean*`** (the original def plus 30
`__bN_<hash>.obj` bodies). Each body's row is a **plain `OBJECT` at the body's OWN
lat/lon with elevation `0.000000`** — the seat is baked into the new `.obj`'s geometry
(`authored_offset` / `y_zero` in the placement record), not written as an elevation.
The airport's only 29 `OBJECT_MSL` rows are OURS (§16g (5) `footprint_unit.msl_seat_rows`,
`msl_seats: 29` in the placement record); 6 of them are T23 (`flag.obj`), none is a T3
shell. `o4_v2_rebake_HECA.json` `counts.msl = 0`; `counts.conversions_msl = 0`,
`conversions_agl = 3`.

## Q3 — WHY NOT ONE UNIT (the load-bearing question)

**It is §16g (10) (4), the LEAF rule — not the contact test, not the pad partition, not
§17 (3), not §46.**

The mechanism, in order:

1. **The plan's own parts.** `Airport/T23/T3_brick_clean.obj` has 138 parts
   (`o4_v2_rebake_HECA.json`, plan unit 43 member 131). Their solid heights
   (`Part.height_m`, `model/rebake.py:105-120`) come in two families:
   * **elevated façade panels** — `height_m` 5.49 / 2.56 / 2.11, `base_y` 10.66 / 15.73 /
     18.46, **`feet` EMPTY** (the plan judged them ELEVATED, `model/rebake.py:75-79`);
   * **ground plinths** — `height_m` **0.49**, `base_y` −0.20, `feet` = 4, areas 2 – 54 m².

2. **§16g (10) (4): only a WALLED body links a unit** (`law/structures.toml:883-889`,
   `chain_min_height_m = 2.5`; implemented at `airport/footprint_unit.py:462-473` and
   `airport/placement_family.py:460-467`). A body whose tallest component is under 2.5 m
   is a LEAF: "it is seated, but it never links two walled bodies". Every 0.49 m plinth
   is a leaf; airport-wide `unit_leaf_bodies` = 16,901 against `unit_chain_bodies` 7,264.

3. **Candidates are the FOOTED, NON-ELEVATED groups only.**
   `airport/placement_plan.py:616-618` builds the groups with
   `coarsen(..., st.elevated, ..., attach_elevated=False)`, and
   `placement_plan.py:643-645` makes the candidate's `pids` out of exactly those raw
   bodies. So for `T3_brick_clean` the candidate of each group is **the plinths**; the
   façade panels are placed later by §15's carrier search
   (`counts.elevated_ride_other_file = 12,078`) and only then merged into the same file,
   which is why the written body's `components` list mixes both.

4. **The pid join then names no unit.** `_bind_plan_wide`
   (`airport/footprint_unit.py:632-645`) counts, per candidate, the parts that map to a
   plan-wide unit; `if not hit: continue`. Measured per body:

   | body | footed comps (height_m, plan-wide unit) | outcome |
   |---|---|---|
   | b2  | (17.33, `fu:42:4016`) | `§16g unit fu:42:4016@cluster_pad … at 96.24` |
   | b4  | (0.49, None) | default anchor 98.656 |
   | b5  | 9 × (0.49, None) | default anchor 99.315 |
   | b10 | (0.49, None) | default anchor 99.151 |
   | b12 | (0.49, None) | default anchor 99.793 |
   | b13 | 2 × (0.49, None) | default anchor 100.155 |
   | b14 | 4 × (0.49, None) | §16c (7) bound to b5 |

   Validated over the whole airport: predicting "§16g-seated ⇔ some FOOTED part lies in
   a plan-wide unit" gives **702 true positives, 2 seated-without (the connector path),
   116 not-seated-with (the per-pass skips: `len(per) < 2`, `unit_all_on_pavement` = 3,
   §16c (7) pre-binding), 4,038 true negatives** — the condition is necessary.

5. **Counterfactual (dry replay, same plan, both arms in one process).** With
   `chain_min_height_m` disarmed (0.0) the same plinths land in **`fu:38:23`** — units
   180 → 323, `unit_chain_bodies` 7,264 → 24,165, `unit_leaf_bodies` 16,901 → 0. That is
   verbatim the pathology the rule was written against (`footprint_unit.py:441-447`:
   "the T3 terminal stayed in `fu:38:23@cluster_pad` — 52 members on one datum — and its
   body sat 7.50 m above its own ground"). **The rule cannot simply be disarmed.**

6. **What the unit does cover.** The plan-wide unit `fu:42:4016` is the whole T2/T3
   district: **3,190 plan bodies, 78 member resources, 544,302 m²** (the seat reason's
   "50 member(s)" is the count present in that pass). Of the **627 written bodies with a
   part in it, only 248 (39.6 %) carry a `§16g unit` seat**; their `surface_z` spans
   91.71 … 108.57 (16.86 m), the seated subset 91.71 … 101.33. The 379 unseated are
   carried bodies (`carried by T3_brick_clean__*` 64, `titles_1__b18` 15, …) and
   `footless_own_ground` 35.

**The candidates the brief listed, ruled out:**

* **§16c (6) contact (2 mm)** — not it. It did fire where it could: b14 is bound to b5
  by `§16c (7)`. It cannot reach across the district.
* **§16f (4)–(6) partition by pad** — not it; §16g replaced that derivation entirely
  (`footprint_unit.py:76-80`), and `pad_majority` finds no pad under these feet at all.
* **§17 (3) / the pavement-foot class** — **not the discriminator.** It only chooses
  median-foot vs low-side-foot INSIDE the default rule once §16g has already left the
  body alone (`airport/anchor_rule.py:723-748`). The per-unit pavement-is-king veto
  (`placement_family.py:823`) is on the OTHER path (`_bind_families`), which is not taken
  here; the plan-wide path's pavement veto is all-or-nothing per unit and fired 3 times
  airport-wide (`unit_all_on_pavement = 3`), not on `fu:42:4016`.
* **§46 (the 1.0.348 input quantum)** — not it. §46 quantises the LOAD stage's projected
  inputs to 1 mm for cross-platform determinism (`docq spec '§46'`); these bodies are
  207–258 m from the nearest pad edge, not 1 mm.

## Q4 — THE GROUND

`tools/site_read.py --graded …/HECA.graded.json 30.1080544 31.3958302`:

* The **only** graded face within **120 m** of the owner's point is
  **shape 156, `apron` `pav1`, airside, inside=True, z 95.99 … 101.42 (median 98.90),
  n = 390.** There is **no step, no terrace, no second face** under the terminal: the
  5.43 m is the span of ONE continuous apron face over its whole 390-node extent.
* The apron there is **lawful**. From the law-true census
  (`tools/harness/census.py …/HECA_auto.patch.osm --rows-json`, 64,480 rows;
  the plain run was a CENSUS CACHE HIT, key `eb3cab254134b9c4`): **0 rows within 100 m**
  of the site, **18 within 200 m** (16 `hairline_pair`, 2 `frontage_near_miss`), 88 within
  300 m (worst `within_shape cross_connector|cross_connector` 1.66 % against a 1.50 % cap,
  |de| 2.53 m, at 30.10577,31.39614). FRAME CAVEAT (the `arm_site_read` rule): a
  within-shape row's lat/lon is the PAIR's position, so a radius selects rows near the
  pair, not every shape touching the site.
* **Pad `building9` is 257.9 m away.** It is graded shape 229, role `building`, airside,
  **z 96.24 … 99.45, median 97.19, n = 359, 62 holes**. That is the "two values":
  **96.24 is the pad's LOW SIDE and 97.19 its MEDIAN, of the same pad.**
  * 96.24 is taken by the cluster seat under §16g (10) (9) (2)
    (`[placement] pad_between_aprons = true`, `law/structures.toml:809-819`,
    `plan_unit_datums(..., low_side=low_side)` at `footprint_unit.py:816-817`);
  * 97.19 is taken by the CONNECTOR-end datum at `footprint_unit.py:866-869`, which calls
    `plan_unit_datums` **without** `low_side` and therefore gets the median.
    That is a latent inconsistency worth naming: two seats on ONE pad, 0.95 m apart,
    both at the owner's site (`T3_brick_clean b0` at 97.81 vs `T3_concrete b0` at 97.54).
* **Why the pad does not cover the terminal footprint.** With `pad_from_cluster = true`
  (`law/structures.toml:821`) the `building` pad is DERIVED from the cluster outline —
  and **§16g (10) (5): a derived pad never takes airside ground.** The clip is at the one
  derivation site, `classify/evidence.py:570-581`
  (`_cluster_pads(airport, law, _airside)` with `_airside = runway_union ∪ pavement_union`).
  The T3 terminal at the owner's point stands ON apron `pav1`, which is airside apt.dat
  pavement, so the cluster's pad is clipped away there; `building9` is the remnant of the
  same cluster outline that survives outside airside pavement, 258 m north-east.
  CAVEAT (measured): one `building9` face, id 232 (12 nodes, a long out-and-back hairline
  strip) contains the point under a shapely `buffer(0)` repair but NOT under the even-odd
  rule `site_read.point_in_ring` uses (`tools/site_read.py:60-68`); the harness reading is
  "no pad covers the site", and face 232 is a degenerate sliver, not pad cover.

## Q5 — HISTORY: the split is NOT new in 1.0.348

`T3_brick_clean__b*` defs in each dated mod-cache DSF text dump:

| dump | mtime | defs | `/T23/` defs | `T3_brick_clean__b*` | T23 rows |
|---|---|---|---|---|---|
| `…f5431248.text` | 08-29 09:51 | 529 | 111 | **0** | 3,220 OBJECT + 216 AGL |
| `…dsf.text` | 09-10 07:40 | 529 | 111 | **0** | same (pristine) |
| `…9f4ae2dc.text` | 09-12 22:16 | 3,724 | 767 | **8** | 6,217 OBJECT |
| `…anchor_bak.a636e364.text` | 09-13 14:57 | 529 | 111 | 0 | pristine backup |
| `…b3c17d88.text` | 09-13 15:04 | 3,990 | 859 | **5** | 6,478 OBJECT |
| `…d279dccd.text` | 09-14 07:09 | 11,771 | 7,658 | **42** | 13,580 OBJECT + 679 MSL |
| `…5bc01282.text` | 09-15 07:26 | 6,407 | 3,043 | **27** | 8,867 OBJECT + 29 MSL |
| `…773d33f0.text` | 09-17 19:39 | 5,387 | 2,278 | **30** | 7,848 OBJECT + 29 MSL |

The per-body cut and re-anchoring of the shared-datum T3 shell has existed since at least
**2026-09-12** and was at its widest on 09-14 (42 bodies). The 09-15 dump (27 bodies) is
the 1.0.341-era state. **The owner may simply not have looked at this spot before.**

What I could NOT recover: the per-body ZEROS of the earlier arms. The seat is baked into
the `.obj` geometry and the rows all carry elevation `0.000000`, and no earlier placement
product survives — **every registered HECA frame in `docs/frames.jsonl` prints
`[MISSING]`** (`tools/harness/frames.py list HECA`: 20+ entries, all session scratchpads).
`o4_v2_rebake_result_HECA.json` (09-10) is an artefact of the DELETED v1 seat mechanism
(RULINGS 2026-09-12s, spec §8) and is not comparable; for the record it already carried
`T3_brick_clean` across **17 clusters whose zeros spanned 13.71 m** (78.47 … 92.18).

## Q6 — THE SMALLEST FIX SHAPE (described, NOT implemented)

The defect is that a **material slice's ground-contact geometry is a set of decorative
plinths**, so the law's proxy for "is this a wall" (`Part.height_m` of the body's OWN
components) reads the slice as clutter, while the body it belongs to is a terminal.
Three candidate shapes, narrowest first:

**A. The leaf's CARRIER decides its unit (amends §16g (10) (4)).** A LEAF is still never
a LINK, but a leaf body whose own elevated components (the ones §15 will make ride it)
belong to a walled body's unit **joins that unit for SEATING**. This is the smallest
change that fixes the site: it touches only the pid join in
`_bind_plan_wide` (`airport/footprint_unit.py:632-645`) — the candidate's `hit` map would
be built over the group's parts INCLUDING the elevated members that will be merged into
its file, instead of only the footed ones. The chain (`plan_units_and_connectors`) is
untouched, so the `fu:38:23` collapse measured above cannot return.
Amends: object-placement spec **§16g (10) (4)** (a leaf's SEAT, not the chain) — leave
§16g (1)/(2) and §16c alone.

**B. One unit's members take one plane even where the pad is clipped away (§16f (7) /
§16g (2)).** Today the cluster's seat exists (96.24) but 60 % of the bodies standing on
the cluster never reach it. A rule "a body whose plan footprint is inside a seated unit's
footprint union takes that unit's zero" would seat all 627. Bigger blast radius and it
re-opens §16f (5) pavement-is-king on the apron — the owner already ruled that yields
inside a cluster (§16f (7)), so it is lawful, but it moves 379 bodies at HECA alone.

**C. Extend the pad instead (§16g (10) (5) / §30 (4)).** Let the cluster pad survive
under the terminal's own footprint where it stands on apron, rather than being clipped by
the airside union at `classify/evidence.py:570-581`. This is the one shape that would
also flatten the apron under the terminal (which §16f (7)/§30 (4) explicitly allows) —
but it is an AIRSIDE-touching change and collides head-on with RULINGS 2026-09-14ah/14as;
**not recommended without an owner ruling.**

**Blast radius** (`tools/blast.py`, index `ab87932` / `51dce31`):
* `airport/footprint_unit.py` — imported by 3 src (`placement_plan.py`,
  `placement_record.py`, `placement_write.py`), 3 tests
  (`test_v2connector.py`, `test_v2leafframe.py`, `test_v2objsplit.py`), 1 tool;
  17 tests reachable via conftest fixtures (`cached_airport_layout` → 14 files,
  `_build_cached` → `test_harness.py`, `stricter_lot_cap` → 2).
* `airport/placement_plan.py` — imported by `engine_v2.py`, `placement_family.py`,
  `placement_write.py`; direct test `test_v2objsplit.py`; same 17 fixture-reached tests.

**The fastest replay to measure it** (INDEX tool, no build):
`cd Ortho4XP && venv/bin/python tools/v2_rebake_replay.py plan
/Users/noah/XPTerrainBuilderData/Patches/+30+030/+30+031/o4_v2_rebake_HECA.json <MESH>
--graded /Users/noah/XPTerrainBuilderData/Patches/+30+030/+30+031/HECA.graded.json
--src <git archive of the base sha>` — the auto-patch-v2 OBJECT STAGE replayed offline
over the sampler the app calls; it arms `harness/shared_repo_guard` and prints
`[guard] shared repo UNCHANGED`. Base sha for the arms: main **`ef8377a0`** (this
session's base); cut the base arm with `git archive <sha> src | tar -x -C <scratch>` and
point `--src` at it — never at a live checkout (the `v2bridgecontact` precedent).
The pair to quote: the six shells' `surface_z` spread at the site (today **2.62 m over 18
datums**), the cross-body contact offsets within 60 m (today **max 2.343 m / 190 pairs
over 0.5 m**), `bodies_bound_to_unit` (today 706), `unit_leaf_bodies` (16,901, must not
move), and `fu:38:23` must NOT appear.
Read-back instrument: `tools/site_read.py --patch-dir … --graded …/HECA.graded.json
30.1080544 31.3958302 60`.

## Q7 — SOURCES I COULD NOT VERIFY

1. **Every registered HECA frame is `[MISSING]`** (`docs/frames.jsonl`, 20+ entries, all
   session-local scratchpads). No 1.0.340/1.0.341 placement or graded product survives, so
   the HISTORICAL vertical spread (Q5) is inferred from the DSF def counts only.
2. **The census rows near the site** were produced with `--rows-json`, which forced a
   recompute; the plain run served a CACHE HIT. I did not run `--sites` or
   `arm_site_read.py --profile` (no second arm exists to compare against).
3. **The per-pass residual in Q3 step 4** — the 116 bodies that have a footed part in a
   unit and are still not §16g-seated — is not decomposed. Static reading is not decisive
   between `len(per) < 2`, `unit_all_on_pavement` and §16c (7) pre-binding; the
   `v2_rebake_replay.py plan` instrument with a counter per skip branch decides it.
4. **`building9` face 232** containment is ambiguous between the even-odd rule and a
   shapely repair (named above). I report the harness tool's reading.
5. I did **not** re-measure the interior-object class — cross-referenced to scout
   `interiors` / RULINGS 2026-09-17o / spec §48 (`docs/briefs/interiors.md`), which names
   HECA T23 as the material-sliced false-positive class.
6. `o4_object_foot_pads.json` (09-03) and `auto_patch_verify_debug.log` were not read.
