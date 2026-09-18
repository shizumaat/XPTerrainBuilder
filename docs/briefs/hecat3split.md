# Brief pack — lane `hecat3split`

Base: main `7fc99f6d` · generated 2026-09-17 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Scout hecat3split: HECA Terminal 3 seated in pieces (owner's 1.0.348 read)

## The brief

# Scout `hecat3split` — HECA Terminal 3 "separating vertically in pieces" (owner's 1.0.348 sim read)

## The owner's read (2026-09-17, app 1.0.348, HECA tile +30+031 built 19:36)
> "the largest terminal building separating a bit vertically in pieces … around here: 30.1080544, 31.3958302"

## What the session already measured (read-only, the shipped products)
`tools/site_read.py --patch-dir /Users/noah/XPTerrainBuilderData/Patches/+30+030/+30+031 --graded …/HECA.graded.json 30.1080544 31.3958302 60 --max 80`
(NOTE: without `--graded`, site_read picked `HEAZ.graded.json` from the shared patch dir — 0 faces; pass HECA's explicitly.)

- Graded face under the point: `apron pav1` (shape 156, airside, z 95.99..101.42, median 98.90, n=390) —
  the apron under the terminal spans 5.4 m of height.
- 99 plan bodies within 60 m, ALL from the Tai Models pack's `Airport/T23/*` (Terminal 3). Units:
  `fu:42:4016@cluster_pad` 9 bodies (on pad building9 at 96.24), `fu:42:4016/c0@pad` 1 body (pad building9 at
  97.19), `None` 89 bodies.
- The terminal shell `T3_brick_clean.obj` is placed SIX times and each placement is seated SEPARATELY:
  b4 surf 98.66 (zero −0.20, "surface at the body's zero"), b5 surf 99.32 (zero −0.20, "surface at the body's
  zero"), b10 surf 99.15, b12 surf 99.79 (zero 0.29, "median foot: every foot on rolled-on pavement (§17,
  motion; terrain spread 0.33 m)"), b13 surf 100.16, b14 surf 99.32 ("§16c (7) bound to T3_brick_clean__b5.obj").
  `T3_brick_clean b0` sits in unit `fu:42:4016/c0@pad` at surf 97.81; `T3_concrete b0` in `fu:42:4016@cluster_pad`
  at surf 97.54 (zero 1.30, "on pad building9 at 96.24 (own ground +1.49 m)").
- The 89 `None` bodies are each "carried by" one of those shells (T3_4, T3_8, T2_glass, floor*, ceiling*,
  celling, black_plastic, green_glass, metal, wood, doors, signs, palm …) and inherit its surface — so the
  interior/façade pieces of ONE building are distributed over datums 97.54 / 97.81 / 97.99 / 98.66 / 99.15 /
  99.28 / 99.32 / 99.79 / 100.16 — a 2.6 m spread inside one terminal. That is the "separating in pieces".
- LAW: object-spec §16f (7) "A LARGE TERMINAL CLUSTER IS ONE UNIT ON ONE PAD" (owner RULINGS 2026-09-13bj);
  §16c (6)–(9) components in contact BIND; §16g units on pads; §17 (2)/(3) the pavement-foot class and the
  median foot. Read them with `tools/docq.py spec --object '§16f (7)'`, `'§16c'`, `'§16g'`, `'§17'`.
- Many of these bodies are INTERIOR clutter (ceiling_2, celling, floor_*, wood, plastic): RULINGS 2026-09-17n
  (owner) defines the interior object class; scout `interiors` (brief `docs/briefs/interiors.md`) is measuring
  it NOW in a peer session — cross-reference, do not duplicate its census.

## Questions (answer each with file:line and exact numbers; no edits, no builds)
1. THE T3 CENSUS: every `Airport/T23/*` placement in `o4_v2_placement_HECA.json` — resource, body id, unit, pad,
   seat reason (verbatim), surface z, zero. Group by carrier. How many distinct datums does the terminal end up
   on, and what is the max vertical offset between two pieces that are authored in contact?
2. WHAT THE PACK AUTHORED: from the pristine DSF text (`…/Airport_mod_cache/c_EGY - 100_airport - HECA Cairo
   (Tai Models)/+30+031.dsf…text`, the `.anchor_bak` if present), are the T3 pieces OBJECT (AGL) or OBJECT_MSL
   rows, and at what authored elevations? Does the pack intend one datum for the whole terminal (a shared-datum
   pack — see memory precedent LSGG: one anchor for all objects)? Does `o4_v2_rebake_HECA.json` rewrite them
   as OBJECT_MSL at the per-body surfaces above (i.e. is the split WRITTEN into the DSF)?
3. WHY NOT ONE UNIT: §16f (7) says a large terminal cluster is one unit on one pad. Here 9 bodies are in
   `fu:42:4016@cluster_pad` on pad building9 and 89 are `None`. Which discriminator excludes the six
   `T3_brick_clean` shells and their carried bodies from the unit — the contact test (§16c (6)), the pad
   membership (§16f (4)–(6) partition by pad), the pavement-foot class (§17 (3): "every foot on rolled-on
   pavement" seats a body on the apron instead of the pad), or the 1.0.348 §46 quantum moving a foot across a
   pad edge? Cite the code path (`src/auto_patch_v2/objects/…`) with file:line.
4. THE GROUND: the apron `pav1` under the terminal spans 95.99–101.42. Is the terminal footprint on a lawful
   apron slope (census families there), or does the apron itself carry a step/terrace under the building? What
   does pad building9 (96.24 / 97.19 — two values reported: which is which) cover, and why does it not cover
   the whole terminal footprint?
5. HISTORY: is this split NEW in 1.0.348 (the owner's previous HECA tile was 1.0.340)? Compare against any
   registered HECA placement product (`tools/harness/frames.py list HECA`, the v2padclip/v2stagepop patches in
   the session scratchpads if they still exist, `o4_v2_rebake_result_HECA.json` dated 09-10). If the same
   split existed at 1.0.340, say so — the owner may simply not have noticed before.
6. THE SMALLEST FIX SHAPE (describe, do NOT implement; blast radius via `tools/blast.py`): e.g. the
   terminal's `T3_brick_clean` shells bind by contact into ONE unit under §16f (7) and the unit seats on ONE
   pad datum; or pad building9 extends to the full terminal footprint. Name the spec clause each amends and
   the fastest replay to measure (an object-stage replay on the HECA capture — name it, its base sha, and the
   INDEX tool).
7. Every source you could not verify.

Report as a cited markdown file in your scratchpad AND in your final message (the session relays it).

## Spec (object-placement) §16f (7)

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

## Spec (object-placement) §16c

## §16c THE CONNECTED COMPONENT IS THE ATOM (Fable, 2026-09-12; RULINGS 2026-09-12b/12d)

The owner's read of 1.0.320 (12b) found hangar vaults sliced, a canopy building in
seven pieces over 11 m, the T4 approach deck in 39 pieces (worst seam 16.29 m), and
the old terminal's roofs 0.57–0.70 m below their walls. Scout `v2lemd320`: §16b (1)'s
cut has the authored TRIANGLE as its atom (`obj8_split.BodyCut`, `tri_owner` senior
to the vertex vote, unowned triangles to the nearest body), so a terrain-group
boundary falls INSIDE a connected solid and the halves are written at two zeros.
Written-frame census: 2,554 seams where two sibling files share an authored vertex,
1,994 with a step > 0.30 m, 2,275 of 3,561 bodies (63.9 %) on a torn seam; 19
single-component resources written as ≥ 2 files. §16b's own MEASURED block refuted
the finer footed triangle cut for "tearing rigid solids" and kept the same atom.

1. **NO CUT CROSSES A CONNECTED COMPONENT.** Every group §9, §16 (2), §16a (1) and
   §16b (1) form — terrain, foot, carrier — is formed over COMPONENTS
   (`obj8.solid_components`), never over triangles: a component is keyed by the
   design surface under its OWN geometry and joins ONE group whole. A component
   wider than its terrain stays whole (a vault, a deck slab, a canopy) — one file,
   one zero. The only station cuts are §10's line segments and §14a's basin arcs
   (drape-class by ruling), and those pieces are the only sibling files allowed to
   share an authored vertex. `split_obj8` never assigns a triangle to a body that
   does not own its component.
2. **THE CARRIER QUESTION IS ASKED ONCE PER COMPONENT** (§16b (2) read on
   components), and the bounded fallback §16b (3) reads the ground under the
   component's CONTACT — its feet, or where it stands over the candidate — never
   the median of its footprint (the deck slab's median ground was the underpass
   floor 15 m below its pier feet).
3. **A FOOT OVER A STRUCTURE CUT IS NOT A GROUND FOOT.** §9's low-side rule and
   §16a (2)'s carrier ground test ignore feet whose surface sample lands on a
   `tunnel_ramp` / tunnel floor / basin-interior face: the body spans the cut. The
   lane MEASURES this first — whether `PKT4__b0`'s zero 611 is a trench foot — and
   implements it only if so; otherwise reports the refutation.
4. **THE CARRIER IS WHAT THE BODY RESTS ON** (§15 (1)(a) amended; amended again
   2026-09-12n): among the candidates a body plan-overlaps, the carrier is the one
   whose TOP surface under the overlap lies NEAREST the body's base plane in
   absolute distance — above or below: a roof let into a parapet rests on walls
   whose top stands above its base, and "nearest below" (the first wording) sent
   the T2 roofs to bodies 6 m off. Largest overlap breaks ties only. A 158 m² wall whose top meets the roof beats a 129,113 m² floor slab
   17 m below it. (`LEMD41__b1` on `LEMD52__b0` reads 0.01 m today; every other T2
   roof rode `LEMD38`'s floor pieces.)
5. **THE BAR INSTRUMENT IS THE WRITTEN FRAME**: `obj8_split_report` (and the
   `--write-pack` census) print the TORN-SEAM census — sibling files of one
   placement sharing an authored vertex, the base step per seam, by class — from
   the written files (the scout's `tear.py`, promoted on this second use). Bars,
   LEMD 1.0.320 frame + OTHH: torn seams outside line/arc pieces **0**; single-
   component resources in ≥ 2 files **0**; the four sites — `HANG3` vault one file
   per component, seams 0; `green-LEMD50` ≤ 2 files; `green-STRT4` deck components
   c0/c2/c3/c41/c42 one file each, no piece more than `split_tol_m` below its pier
   feet; T2 roofs `TEJ3/tej2_teilb/LEMD58/LEMD50/T2CSG` within 0.3 m of the wall
   tops (`LEMD52/53/59/T2BCK/LEMD54`, today 0.57–0.70 m low), skylight strips in
   ONE file; §15 carried float 0; the 11at sites held (green-TEJ3 0.02/0.04, gate-5
   sign −0.15, T4 deck −0.05); files ≈ 900–1,400 (counterfactual estimate 899);
   plan stage on the GRADED sampler ≤ main's and the `_surface` call count quoted
   (the mesh-sampler cost is 12a's, measured separately); round trip OK; suite.

**MEASURED (lane `v2atom`, 2026-09-12; branch `claude/v2atom`).**
Implemented in `airport/obj8_split.py` (§16c (1)'s writer half: the
triangle goes to the body owning ITS COMPONENT, an unowned component
goes WHOLE to the nearest body, and the vertex vote and per-triangle
nearest fallback are DELETED), `airport/placement_cut.py` (§16c (1)'s
cut half: `_LineCutter.comp_of` / `_comp_blocks` — the vectorised
triangle→component map every cut now groups by; `terrain_groups`,
`foot_groups` and `carrier_groups` place WHOLE components;
`carrier_groups` takes the piece's own written triangles; `part_tops`),
`airport/placement_body.py` (the footed triangle cut reads the same
`own_tris` its pre-test measured), `airport/placement_boxes.py`
(§16c (2)'s `contact_ground`, `foot_box_index`, `CONTACT_PTS_MAX`),
`airport/placement_carrier.py` (§16c (4)'s rest-on ranking and
`Candidate.top_y` / `part_tops`), `airport/placement_plan.py` (the
wiring) and `airport/placement_seams.py` (NEW: §16c (5)'s torn-seam
census, the scout `v2lemd320`'s `tear.py` promoted).

* **THE FOUR SITES AND THE CLASS REPRODUCED** on the live 1.0.320
  written pack, read-only, by the promoted census: `HANG3` 10 files /
  **14 torn seams** worst 3.05 m; `green-LEMD50` 7 files / spread
  11.12 m; `Bridge2` 8 files / 11.72 m; `green-STRT4` **53 files**,
  `__b44` seams up to **16.29 m**; whole plan **2,554 seams, 1,994 over
  0.30 m** (974 + 1,580 line/arc, 790 + 1,204 over) — the scout's
  figures to the unit.
* **§16c (3) IS REFUTED AND IS NOT IMPLEMENTED.**  `PKT4__b0`'s zero is
  611.00 on the 1.0.320 frame (611.23 was 1.0.319's) and its anchor
  reason is its own: `low-side foot (no point within 0.3 m of the body's
  zero plane: authored relief 0.95 m)`.  NOTHING of it stands on a
  structure cut: all 8 of its foot boxes and all 32 of its written
  geometry samples lie on NO graded face at all (`tunnel_ramp` ×17 and
  `tunnel_trench` ×1 are the only structure roles `LEMD.graded.json`
  carries; the nearest is 65 m away in latitude), and 0 of 32 samples
  and 0 of 8 foot boxes fall inside any of the 19 structure RIM rings.
  "A foot over a structure cut is not a ground foot" has no instance
  here; the deck slab's real mechanism is §16c (2)'s, which is
  implemented.
* **THE BARS**, matched replay arms on the 1.0.320 LEMD rebake plan +
  `LEMD.graded.json`, `--admit-skipped` on the live pack, the write half
  into APFS clones (BEFORE is this lane's instrument commit `3dff7879`
  on main's law, so both arms are read by one instrument):

  | bar | 1.0.320 written | before | after |
  |---|---|---|---|
  | torn seams outside line/arc pieces (bar 0) | 974 (790 > 0.3 m) | 723 (575 > 0.3 m) | **0 — MET** |
  | single-component resources in >= 2 files (bar 0) | 131 | 128 | **0 — MET** |
  | bodies on a torn seam | 1,011 | 816 | **0** |
  | line/arc station seams (lawful, apart) | 1,580 | 1,446 | 891 |
  | §15 carried `stands-over float > 0.5 m` (bar 0) | — | 0 | **0 — MET** |
  | §14 `footless at datum` / `on ground` / `basin split` | — | 0 / 0 / 0 | **0 / 0 / 0** |
  | §16 `rows on the datum outside the plan` | — | 0 | **0** |
  | §14a basin ring bar (<= 0.3 m) | — | 0.18 m, 0 over | **0.18 m, 0 over** |
  | §16b carried piece float > 0.5 m (bar 0) | — | 120 | 124 |
  | §16b body wider than its terrain group (bar 0) | — | 1,532 | **1,417** |
  | files | 3,561 | 3,253 | **2,804** |
  | round trip (write half into a pack COPY) | — | OK | **OK**, 2,804 files, 2,804/2,804 new `OBJECT_DEF`s, 0 rows carrying an elevation, duplicate rows surviving 0 |
  | plan stage, graded sampler, 3 runs | — | 13.53 / 13.52 / 13.53 s | **9.84 / 10.48 / 10.32 s — MET (<= main's)** |
  | `_surface` calls | — | 194,853 (+104,091 vectorised points) | **186,263 (+104,619)** |

  OTHH, same arms: torn seams **639 (342 > 0.3 m) -> 1**, single-
  component resources in >= 2 files **165 -> 1**, §15 carried float
  **0 -> 0**, `footless at datum` 0, files 1,897 -> 1,898, §16b carried
  piece float **200 -> 172** and wide **144 -> 85**, round trip **OK**
  (1,897/1,897 new `OBJECT_DEF`s, 0 rows carrying an elevation), the
  §16a (2) refusal set 21 -> 57.  The ONE
  residue is `Buildings/Fire Fuel/OTHH_Fuel_02_LOD0_007.obj`
  b0<->b1, step +2.70 m: two components `obj8.solid_components`
  reports as SEPARATE share an authored vertex POSITION to the
  millimetre (vertex ids 378/399 and 379/411).  Named, not closed.
* **THE FOUR SITES AFTER** (files / written base spread; live 1.0.320 ->
  before -> after): `HANG3` **10 / 3.51 m -> 6 / 1.90 -> 6 / 1.37**, and
  every file is now a whole number of components (seams 14 -> 0);
  `green-LEMD50` **7 / 11.12 -> 4 / 2.73 -> 1 / 0.00 (bar <= 2 files
  MET)**; `green-STRT4` **53 / 16.29 -> 31 / 10.13 -> 24 / 8.90**;
  `Bridge2` **8 / 11.72 -> 6 / 1.66 -> 5 / 1.73**.
* **THE 11at SITES HELD, AND TWO MOVED THE WRONG WAY** (zero minus the
  design surface under the body's own written geometry, before ->
  after): item 3 `green-TEJ3` **+0.44 -> +0.18**, item 5 **-0.40 ->
  -0.29**, the gate-5 sign **-0.02 -> -0.02**; but the T4 landside deck
  `green-STRT4` **+0.90 -> +1.11** and the T4 roof `Terminal4_48`
  **+1.81 -> +3.26**.  Both are the atom's own cost: those pieces were
  carried bodies the old cut divided THROUGH a welded slab, and a slab
  that stays whole takes one zero over ground that moves under it.
  §16c (5)'s "no piece more than `split_tol_m` below its pier feet" is
  therefore **MISSED** and named.
* **§16c (4) IMPROVED THE WORST CASE AND MISSED THE BAR.**  T2 roofs
  (`TEJ3`/`tej2`/`tej2_teilb`/`LEMD58`/`LEMD50`/`T2CSG`) against the top
  of the named wall geometry directly under them, read in WORLD
  coordinates from the written files: live 1.0.320 **7 of 9 over 0.3 m,
  worst 2.80 m**; before **5 of 7, worst 6.56 m**; after **5 of 7, worst
  0.97 m**.  148 bodies take the new `rests on it` reason.  The bar
  ("within 0.3 m") is MISSED.
* **THE COST OF THE ATOM, NAMED.**  §16a (2)'s refusal set at LEMD goes
  **37 -> 157** footed bodies (20 carried bodies stand over one, was 0),
  because 11ak (2)'s FOOT cut can no longer divide a body authored as
  ONE welded component: such a body's feet genuinely disagree and it is
  honestly mis-anchored.  11ak's twin is AMENDED to read both halves —
  three treads in three components are still cut by their feet, the same
  ribbon welded is written whole and refused.  HANG3's four vault arcs
  are four separate components written at four zeros 1.37 m apart: no
  seam, but adjacent rigid pieces of one resource at different zeros are
  a class §16c does not reach (they do not overlap in plan, so §14 (3)
  never binds them).  Reported for the owner.
* **TWO READINGS CORRECTED IN PASSING** (both §16b (1)'s own sentence,
  both forced by the twins): the FOOTED triangle cut and the CARRIER cut
  now read the same `own_tris` their pre-test measures — a member the
  plan records as ONE part is WRITTEN as the whole object, so a cut over
  the parts' components measured a span it could not act on.
* **SPEED.**  §16c (2)'s first form was two thirds of the plan stage
  (154 M box comparisons in `contact_ground`); bounded to the piece's
  `foot_boxes`, candidates whose hull box it meets, and
  `CONTACT_PTS_MAX` samples, the whole stage came out FASTER than main's
  (13.5 -> 10.2 s).  `comp_of` is a packed-key `searchsorted`, not a
  Python dict.
* **Twins:** `test_no_cut_crosses_a_connected_component`,
  `test_split_obj8_never_assigns_a_triangle_across_a_component`,
  `test_the_carrier_is_what_the_body_rests_on`,
  `test_the_bounded_fallback_reads_the_contact_ground_not_the_median`,
  `test_the_torn_seam_census_reads_the_written_files`; four twins
  AMENDED where §16c supersedes them (the scattered roof, the carried
  roof over two buildings, the carried roof re-cut by its walls, and
  11ak (2)'s foot re-cut — each now authored in SEPARATE components,
  with the welded case asserting the new law).  Suite **1,127 passed /
  1 skipped** (main 1,122 / 1).  `_Staged` moved to
  `airport/placement_record.py` for the 1,000-line law.
* **NOT DONE:** no airport build (§16c needs none); §16c (3) refuted and
  left out; the `--write-pack` arms are pack COPIES and the live pack was
  read-only throughout.

### §16c (6) COMPONENTS IN CONTACT BIND (owner RULINGS 2026-09-12h)

§16c (1) made the connected COMPONENT the atom of every group.  An
exporter's "one solid" is often several components that TOUCH, and
written at two zeros they read as a break: OTHH's
`OTHH_Fuel_02_LOD0_007` carries two components **0.4 mm** apart — under
the millimetre key `obj8.solid_components` welds on (`np.round(v, 3)`)
they are two — and round 1 wrote them 2.70 m apart, the airport's last
seam.

Components of ONE resource bind into ONE RIGID BODY for anchoring —
one zero, the senior component's carrier — when they share a vertex
position within `[placement] contact_eps_m` (2 mm), OR when the REBAKE
PLAN's own ε-contact graph already links their parts.  A bound cluster
is the atom every §16c (1) group is formed over.

**MEASURED (lane `v2atom` round 2, 2026-09-12; branch `claude/v2atom`).**
`_LineCutter.comp_cluster` (union-find over the plan's intra-member
contact pairs and a box-rejected KD-tree pair count), `_comp_blocks`
grouping by cluster, `[placement] contact_eps_m` in
`law/structures.toml` + `law/rebake_schema.py`, wired through
`placement_plan.build_splits` / `placement_write` / `engine_v2` and
`obj8_split_report --contact-eps`.

* **THE BAR, LEMD** (same matched frame; round 1 -> round 2): torn seams
  outside line/arc **0 -> 0**, single-component resources in >= 2 files
  **0 -> 0**, files **2,804 -> 2,776**, §15 carried float **0**, round
  trip **OK** (2,776 files, 2,776/2,776 new `OBJECT_DEF`s, 0 rows
  carrying an elevation, duplicate rows surviving 0), plan stage on the
  graded sampler **8.86 / 9.28 / 9.37 s** (main 13.53), `_surface` calls
  186,263 -> **184,219**, §16b carried piece float 124 -> **122** and
  wide 1,417 -> **1,405**, §16a (2) refusal set 157 -> **169**.  Suite
  **1,129 / 1 skipped**.  The distance test is ONE labelled radius pair
  query over the member's vertices: the first form (a KD-tree per
  component and an n^2 pair loop) was quadratic in a clutter object's
  thousands of components and did not finish OTHH's plan stage in ten
  minutes.
* **THE BAR, OTHH** (round 1 -> round 2): torn seams outside line/arc
  **1 -> 0 — MET**, single-component resources in >= 2 files **1 -> 0 —
  MET**, files 1,898 -> **1,891**, §16b carried piece float 172 -> 175
  and wide 85 -> **76**, §15 carried float **0**, round trip **OK**
  (1,890/1,890 new `OBJECT_DEF`s, 0 rows carrying an elevation).  The
  airport's LAST seam — `OTHH_Fuel_02_LOD0_007` b0<->b1, +2.70 m — is
  exactly the two components 0.4 mm apart, and it is closed.
* **`Terminal4_48` FIXED BY IT.**  Its zero spread **3.58 -> 0.69 m**
  and the owner-site reading `zero - ground under its own geometry`
  **+3.26 -> +0.04 m** (1.0.319 read +1.81): the piece that rode
  `green-STRT4__b11` at a top 3.38 m below it is now bound to its own
  neighbours and takes their zero.  The other 11at sites are byte-equal
  (item 3 +0.18, item 5 -0.29, gate-5 sign -0.02).
* **`HANG3`'s FOUR VAULT ARCS ARE NOT REACHED, AND THE BAR IS REFUTED AS
  WRITTEN.**  Measured pairwise minimum vertex distance between its 7
  components: the arcs stand **1.507-1.853 m** from the two spine
  components and 9.65-65.31 m from each other; and the rebake plan
  records **ZERO** intra-member ε-contacts for this resource (the
  airport has 37,324 contacts in all).  Neither half of §16c (6)
  can bind them: a 2 mm contact tolerance does not reach 1.5 m, and the
  plan's graph has no edge.  Binding them needs `contact_eps_m` >= 1.86
  m, which is a REACH and not a contact — it would weld anything
  standing within two metres across every resource of the pack.  The
  vault stays 6 files at 6 zeros spanning 1.37 m.  NOT FIXED; the
  question is the owner's (a "one resource, one rigid object" rule is a
  different law from contact).
* **THE T2 ROOFS ARE NOT §16c (4)'s TO FIX.**  Attribution: the named
  wall bodies DO plan-overlap every roof and are NOT refused by
  §16a (2) (`ground_off` 0.00-0.08) — they are removed by §16 (3)'s
  FILL gate before the rest-on ranking ever sees them.  `LEMD54`'s
  bodies under the roofs carry `fill` **0.005 / 0.010 / 0.031** and
  `LEMD59`'s **0.031**, against `[placement] carrier_fill_min` **0.2**:
  a terminal's wall RING is a thin loop, and its parts-hull over its
  plan box is one to three per cent.  What the rest-on rule is then left
  to choose between are bodies whose top under the overlap is +2.46,
  +7.93, +8.39, +14.63 m below the roof's base — it picks the nearest
  below, which is what it is for.  Raising or qualifying the fill gate
  is a RULING (it exists so a fence's box cannot carry a zero); not
  changed here.
* **THE `green-STRT4` DECK IS AN INSTRUMENT ARTEFACT, NOT A FLOAT.**  The
  +1.11 m body is FOOTED (6 feet, fill 1.000, not carried, not
  elevated), and its `y_zero` is **-1.668**: its anchor vertex is a
  SKIRT 1.67 m below the object's zero plane.  `zero - ground under the
  geometry` therefore reads the skirt depth, not a float — the body's
  own lowest vertex lands on the design surface at its anchor
  (616.449).  Its real residual is §7's, `ground_off` **0.397 m** over
  0.43 m of authored foot relief: 11ak (2)'s class, which §16c (1) can
  no longer foot-cut because the deck is one welded component.  Not a
  defect to fix here; the §16b `carried piece float` bar should not
  count a footed skirted body at all, which is a census question.
* **THE §16a (2) REFUSAL SET, NAMED** (LEMD round 2, 169 candidate
  bodies; over WRITTEN files with `ground_off > 0.3 m`, basins exempt,
  524 files of which 353 are line segments that §16 (3) bars from
  carrying anyway): **other 97, skirted 69, building 5**.  Worst-off:
  `green-STRT4__b0` 7.16 m (building, 4 feet), `LEMDblast__b1` 7.14
  (line), `Munoza-LEMD50__b2` 5.96 (line), `Terminal4sBlue-STRT4__b1`
  5.08, `green-PKT4__b0` 4.50 (skirted), `Munoza-TWY__b1` 4.16,
  `Cargo-NEWCO__b0` 3.35, `P2CNX__b4` 3.19.  Every one is the same
  class: a body whose FEET are authored over metres of relief on ground
  that barely moves, which 11ak (2)'s foot cut used to divide and §16c
  (1) forbids dividing.
* **THE FILE COUNT, EXPLAINED.**  2,776 files by §6 class: **line_segment
  1,141**, other 1,232, skirted 246, building 166, basin 19.  By
  resource the top two are `grass_FSX-LEMDgrass` **894 files** and
  `Taxisigns-SENRG` **310** — 1,204 files, 43 % of the airport, from two
  line/clutter resources cut by §10's 100 m station law.  The 899
  counterfactual counted SOLID bodies only; the solid half here is
  **1,663**.  Nothing in §16c makes line files: round 1 took them 1,446
  -> 891 seams and the count is §10's, not the atom's.
* **Twins:** `test_components_in_contact_are_one_rigid_body`,
  `test_the_plans_contact_graph_binds_components_whatever_the_distance`.

### §16c (7)-(9) THE FILL GATE GOES, THE RIGID REACH CHAINS, A SKIRT IS NOT A FLOAT (owner RULINGS 2026-09-12j)

**(7) THE FILL FRACTION LEAVES CARRIER CANDIDACY.** §16 (3)'s "a carrier
is a SOLID" stays as a CLASS rule — a line segment, a grass strip, a sign
never carry — and `[placement] carrier_fill_min` is DELETED, not gated.
It was the wrong instrument for that rule: a terminal's wall RING is a
thin loop, and `LEMD54` / `LEMD59` — the walls the T2 roofs rest on,
which overlap every roof and pass §16a (2)'s ground test — fill
0.005-0.031 of their boxes and were struck as carriers before §16c (4)
ranked anything.

**(8) THE RIGID REACH** (`[placement] rigid_reach_m` 2.0).  SOLID
components of one resource whose geometry comes within the reach CHAIN
into one rigid cluster; the cluster is the atom of every group and of the
BODY.  Line objects are excluded (§10 cuts a fence into stations on
purpose).

**(9) A SKIRT IS NOT A FLOAT.** §16b's carried-float bar reads only a
carried body WITH NO FEET OF ITS OWN; a footed body's number is
`ground_off`.

**MEASURED (lane `v2atom` round 3, 2026-09-12; branch `claude/v2atom`).**
Implemented in `law/structures.toml` + `law/rebake_schema.py`
(`carrier_fill_min` deleted, `rigid_reach_m` added),
`airport/placement_carrier.py` (the fill test gone from `carriers_for`),
`airport/placement_census.py` (the fill test gone from the §15 census
population; the §16b float bar skips a footed body),
`airport/placement_cut.py` (`comp_cluster` at the reach, line objects
excluded), `airport/placement_body.py` (THE CLUSTER IS ONE BODY: the
`_bodies_of` groups are unioned by cluster and the PART cut may not
divide one) and `airport/placement_plan.py` / `placement_write.py` /
`auto_patch/engine_v2.py` / `tools/obj8_split_report.py --rigid-reach`.

* **THE SHARED-REPO WRITE, CLOSED FIRST.**  `obj8_split_report.py` armed
  nothing, and round 2's OTHH `--admit-skipped` run created
  `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` (3.25 MB)
  and rewrote `o4_dsf_object_positions_+25+051.cache` in the shared repo
  with both lane-local cache env vars exported.  The entry now runs
  inside `harness/shared_repo_guard`'s guard and its before/after audit —
  the ONE implementation `build_airport.py` arms — and every round-3 run
  prints `[guard] shared repo UNCHANGED by this build (full-surface
  before/after snapshot)`.  Proven independently: a file list of
  `/Users/noah/XPTerrainBuilderData/Airport_mod_cache/` (1,523 files,
  name+size+mtime) taken before and after a full guarded OTHH
  `--admit-skipped --write-pack` run is **byte-identical**.  The env
  redirect itself was measured and HOLDS (`airport_mod_cache_root()`
  returns the lane-local dir before and after every engine import); what
  failed was that nothing refused or reported the write, which is what
  the guard now does.  Twin:
  `test_the_report_tool_arms_the_shared_repo_write_guard`.
* **THE BARS, LEMD** (matched frame, round 2 -> round 3):

  | bar | round 2 | round 3 |
  |---|---|---|
  | torn seams outside line/arc (0) | 0 | **0 — MET** |
  | single-component resources in >= 2 files (0) | 0 | **0 — MET** |
  | `HANG3` — the (8) bar | 6 files, zeros spanning **1.37 m** | **3 files, 1.12 m** (the vault arcs and the spines bind; the bar "one zero" is NOT met) |
  | nothing new rides a fence | 0 | **0 — MET** |
  | 11at item 3 / item 5 / gate-5 sign | +0.18 / -0.29 / -0.02 | **+0.06 / -0.29 / -0.02 — HELD** |
  | 12h `Terminal4_48` | +0.04 | **+0.49** (spread 0.69 -> 0.86) |
  | `green-STRT4` deck | +1.11 (23 files) | **+0.14 (19 files, spread 8.90 -> 6.09)** |
  | §15 carried float > 0.5 m (0) | 0 | **0 — MET** |
  | §16b carried piece float (0) | 122 | **107** |
  | §16b wider than its terrain group (0) | 1,405 | **979** |
  | files | 2,776 | **2,174** |
  | round trip | OK | **OK**, 2,174/2,174 new `OBJECT_DEF`s, 0 rows carrying an elevation |
  | §16a (2) refusal set | 169 | **244** |
  | plan stage, graded, 3 runs | 9.3 s | **9.92 / 9.96 / 9.85 s** (main 13.53) |

* **THE RIGID CLUSTERS DO NOT RUN AWAY.**  Five largest cluster plan
  extents at LEMD: **5,157 m / 2,890 m / 2,514 m / 2,271 m / 2,234 m —
  every one of them a SINGLE component** (`Munoza-LEMDzaun`,
  `North_FSX-LEMDzaun`, three `AESlite-LEMD-VOR` markers), i.e. authored
  that way and not chained by the reach.  129 of 7,816 clusters exceed
  300 m, all of that class.  `Terminal4SAT_green-TEJ3`: **9 components ->
  9 clusters** — its panels do NOT chain, which is the bar.
* **THE COST, NAMED.**  `grass_FSX-LEMDgrass` goes 894 -> 458 files: the
  reach chains grass tufts within 2 m into rigid mats.  Reported, not
  judged — the resource reads as a line object per component in places
  and not in others.
* **(9) IS A NO-OP AT LEMD AND IS STILL RIGHT.**  `footed_carried_excluded`
  is **0**: no carried body at LEMD publishes feet, so the bar never
  counted one.  The `green-STRT4` +1.11 m round 2 reported was never in
  the §16b census at all — it was this lane's own site probe reading
  `zero - ground` on a FOOTED body with `y_zero` -1.668.  The census now
  cannot make that mistake, and the probe's number for that body is
  +0.14 m after (8).
* **THE BARS, OTHH** (matched frame, round 2 -> round 3): torn seams
  outside line/arc **1 -> 0 — MET**, single-component resources in >= 2
  files **1 -> 0 — MET**, files 1,891 -> **1,362**, §16b carried piece
  float 172 -> 177, wide 85 -> **74**, §16a (2) refusal set 57 -> 99,
  round trip **OK** (1,361/1,361 new `OBJECT_DEF`s, 0 rows carrying an
  elevation), `[guard] shared repo UNCHANGED`.  The arm is SLOW — the
  three refuted forms did not finish it at all (45 min and counting) and
  the shipped one takes tens of minutes against round 2's ~10; the reach
  costs OTHH more than it costs LEMD, and that cost is not measured as a
  stage time this round.  Owed.
* **THE T2 ROOFS ARE STILL MISSED, AND THE ATTRIBUTION HAS MOVED.**  5 of
  7 over 0.3 m, worst 6.12 m (round 2: 5 of 7, worst 0.97; live 1.0.320:
  7 of 9, worst 2.80) — and it MOVES with every change to the carrier
  set, which is itself the finding: the choice is not pinned by the law.  With the fill gate gone the `LEMD54` bodies ARE
  candidates (`ground_off` 0.08-0.11, overlapping every roof) — and
  §16c (4) still does not pick them, because their top under the overlap
  stands ABOVE the roof's own base plane and "nearest BELOW the base" is
  category 1 for anything above it.  These walls are parapets and upper
  storeys: the roof is let INTO them, not laid on top.  The §16c (5) bar
  (roof base within 0.3 m of the wall TOP) and the §16c (4) rule
  (carrier top nearest below the roof base) are asking for two different
  geometries.  Not guessed at: it is a ruling.
* **THE REACH'S COST, MEASURED AND THEN BOUNDED.**  A radius pair query
  over every vertex of a member returns MILLIONS of pairs at 2 m: the
  LEMD plan stage went **9.3 -> 108-126 s** over 3 runs.  A KD-tree per
  component with an n^2 loop is quadratic in a clutter object's
  thousands of components (it did not finish OTHH in ten minutes).  What
  ships is a SWEEP: the components sorted by the low corner of their
  box, the pairs whose boxes come within the reach walked once, anything
  already unioned skipped, and the trees asked only then
  (`airport/placement_atom.py`, NEW — the §16c atom law lifted out of
  `placement_cut` for the 1,000-line law), and the pair TEST is a
  nearest-neighbour query with an upper bound, not `count_neighbors`:
  counting EVERY pair within 2 m between two dense clouds is billions,
  and it is what left OTHH's plan stage unfinished after 45 minutes and
  LEMD's at 26.3 s.  FOUR forms measured — all-pairs `query_pairs`
  (**108-126 s**), the same vectorised (**~117 s**), a box SWEEP with
  `count_neighbors` (**26.3 s**, OTHH unfinished at 45 min), and the
  sweep with a bounded nearest-neighbour query: **9.92 / 9.96 / 9.85 s**
  over 3 runs against main's 13.53 — the "plan stage <= main's" bar
  **MET**.  `_surface` calls 184,219 -> **141,466**.  A member with more
  than `placement_atom.RIGID_REACH_COMPONENTS_MAX` (64) components keeps
  §16c (6)'s contact binding only — an affordability bound, named.
* **Twins:** `test_the_rigid_reach_chains_solids_and_never_a_line_object`,
  `test_the_16b_float_bar_excludes_a_footed_body`,
  `test_the_report_tool_arms_the_shared_repo_write_guard`; the fence
  twin AMENDED (the fill fraction gone, the CLASS rule kept), and two
  cut twins amended where §16c (6)/(8) supersede them — a contact-bound
  ribbon is ONE rigid body and 11ak (2)'s foot cut can no longer divide
  it, which the twin now reads from both sides.

**MEASURED (lane `v2atom` round 4, 2026-09-12; branch `claude/v2atom`; RULINGS 2026-09-12n).**

* **§16c (4) IS NOW ABSOLUTE DISTANCE** (`placement_carrier._rest_key`):
  the overlapping candidate whose top under the overlap is nearest the
  body's base plane, above or below.  Five of the nine T2 roof bodies
  now rest within 0.36 m of their chosen carrier's top (−0.03, −0.18,
  −0.24, −0.36); four still take one 2.5–14.6 m away.
* **THE T2 BAR IS STILL MISSED: 7 of 8 over 0.3 m, worst 6.12 m**
  (round 3: 6 of 7, worst 6.12; live 1.0.320: 7 of 9, worst 2.80).  The
  rule is satisfied — each roof rests on the nearest-top candidate it
  overlaps — so the residue is the CANDIDATE SET, not the ranking: the
  wall body the eye reads as "under" those four roofs is not one they
  plan-overlap in `stands_over_rank`.
* **ONE MECHANISM TESTED AND REFUTED, REVERTED:** that the wall rings
  were outside the stands-over set because only a body's eight largest
  part boxes are published (`FOOT_BOXES_MAX`).  Raised to 32 the bar
  moved 7 of 8 → 6 of 7 with the worst unchanged at 6.12 m, for a
  larger plan; not kept.
* **THE 11at / 12h SITES ALL HOLD:** item 3 **+0.06**, item 5 **−0.29**,
  gate-5 sign **−0.02**, `green-STRT4` deck **+0.14**, `Terminal4_48`
  **+0.49**; `HANG3` **3 files / 1.12 m**, `green-LEMD50` 1 file,
  `Bridge2` 5 files, nothing rides a fence (**0**).
* **§16c (8) IS BOUNDED BY A CLUSTER SPAN CAP**
  (`placement_atom.RIGID_CLUSTER_SPAN_MAX_M` 1,200 m): a cluster is one
  rigid body no cut may divide, so a chain of 2 m hops that walks a
  terminal makes a body wider than any terrain it can stand on —
  unbounded, the reach chains `OTHH_Terminal_Base_*` into clusters
  spanning 1,042–1,175 m over 3–15 components.  A 100 m cap was measured
  and REJECTED: it broke the sites the reach exists for (`Terminal4_48`
  +0.49 → +3.26, `HANG3` 3 → 5 files).
* **THE REACH IS NOT WHAT COSTS OTHH, MEASURED ON MATCHED ARMS.**  OTHH
  plan stage, same code, graded sampler: **64.33 s** at the 1,200 m cap,
  **64.45 s** at 100 m, **63.46 s with the reach DISARMED**.  The reach
  accounts for **0.9 s**; deleting it would not bring OTHH under the
  45 s bar, so it is KEPT.  The **≤ 45 s bar is MISSED at 64 s** and the
  cost is elsewhere in the stage (344,838 `_surface` calls at OTHH
  against LEMD's 141,306).
* **LEMD plan stage 10.31 s** against main's 13.53 — MET.
* **OTHH, MEASURED TO COMPLETION UNDER THE GUARD** (round 3 -> round 4):
  torn seams outside line/arc **0 — MET**, single-component resources in
  >= 2 files **0 — MET**, §15 carried float **0 — MET**, files 1,362 ->
  **1,376**, §16b carried piece float 177 -> 183, wide 74 -> **70**,
  round trip **OK** (1,375/1,375 new `OBJECT_DEF`s, 0 rows carrying an
  elevation), `[guard] shared repo UNCHANGED`.
* **LEMD, ROUND 4**: files **2,171**, seams **0**, single-component
  **0**, §15 carried float **0**, round trip **OK** (2,171/2,171),
  guard **UNCHANGED**.
* **THE §16a (2) REFUSAL SET (244), BY CLASS**, read over the written
  files (`ground_off` > 0.3 m, basins exempt; 358 files, of which 114
  are line segments §16 (3) bars from carrying anyway): **other 158,
  skirted 76, building 10**.  Worst-off: `LEMDblast__b1` 7.14 m (line),
  `Terminal4sBlue-STRT4__b1` 5.08, `LEMD03__b6` 4.98, `Munoza-LEMD50__b1`
  4.92 (line), `green-PKT4__b0` 4.50, `Munoza-TWY__b1` 4.16,
  `Munoza-LEMD69__b12` 3.95 (140 feet), `Cargo-NEWCO__b0` 3.35,
  `Munoza-LEMD03__b5` 3.32, `P2CNX__b3` 3.19 — every one the same class:
  feet authored over metres of relief on ground that barely moves, which
  §16c (1) forbids foot-cutting.
* **Merged main `30a61c9f`** (§27, the mesh-sampler grid, `v2_rebake_replay
  plan`); `tools/INDEX.md` resolved keeping BOTH rows.  Full twin set
  **1,169 passed / 1 skipped**.

### §16c (7)–(8) The unit binds by contact; the rest-on carrier is not refused for its own ground (Fable, 2026-09-12; RULINGS 2026-09-12q)

Scout `v2t2roofs` on main `fe5d7a87`: the four T2 roofs that miss are NOT a plan-overlap
predicate (widening it — "inside the hull box" 72 carriers changed, "any hull-box
overlap" 121 — fixes none of them). Three causes: `tej2__b0/b1` rest on `P2PK__b0`
(|Δ| 1.45 m against 14.64 for the runner-up, only two candidates overlap) and §16a
(2) REFUSES it for its own `ground_off` 0.42 > 0.30 — the ranking runs before the
refusal, so the body it rests on is dropped and the next one taken; `LEMD48__b0` /
`LEMD47__b1` have NO candidate at their height because `LEMD47`/`LEMD48` are one
thing (114 ε-contacts between them in the rebake plan) and §16c (6) binds only
within one member, with elevated bodies excluded from their member's coarsening;
and the block's separation is the SPREAD — the T2 walls are separate footed bodies
each at its own low-side ground (building bodies 602.89 … 603.35, `LEMD47` alone at
three zeros 1.19 m apart), and every roof inherits whichever the ranking hands it.
The plan records 175 cross-member ε-contacts among the T2 resources.

7. **THE UNIT BINDS BY CONTACT.** §16c (6)'s contact binding is unit-wide: bodies
   of one UNIT in ε-contact (the rebake plan's cross-member contact pairs, and the
   rigid reach within `rigid_reach_m`) form ONE rigid cluster, and an elevated body
   joins its own member's footed cluster. The cluster's zero is its senior FOOTED
   body's anchor (largest footprint; §9 low side); every member rides it at the
   authored offset. `RIGID_CLUSTER_SPAN_MAX_M` (1,200) bounds the chain. A terminal
   authored as walls + roofs + skylights in contact is one building.
8. **THE REST-ON CARRIER IS NOT REFUSED FOR ITS OWN GROUND.** §16a (2)'s refusal
   yields when the candidate's top under the overlap meets the carried body's base
   within `split_tol_m`: it is what the body rests on, and its mis-anchoring is its
   own residual (reported under the refusal set), not a reason to hand the body to
   something 14 m away. Refusal stays for every other candidate.
9. **BARS (lane `v2unitbind`)**: T2 building bodies within 150 m of 40.4660017,
   −3.5694045 at ONE zero (spread ≤ 0.3, today 0.46; `LEMD47` one zero, today 1.19
   apart); every T2 roof within 0.3 m of the wall it rests on (today 4 of 9 at
   2.85–20.6 m); `tej2` on `P2PK`; the 11at / 12h / 12o sites held (green-TEJ3,
   gate-5, `Terminal4_48`, the deck, `HANG3`); torn seams 0; §15 carried float 0;
   OTHH seams 0 and its plan stage not worse than 64 s; collateral quoted airport-
   wide (carriers changed, zeros moved, largest move, cluster count and the five
   largest spans); files; round trip; suite.

**MEASURED (lane `v2unitbind`, 2026-09-12; branch `claude/v2unitbind` from main
`be882755`).**  Implemented in `airport/placement_atom.py` (`RigidNode`,
`unit_clusters`, `unit_rigid`, `bind_unit` and `UNIT_CLUSTER_SPAN_MAX_M`),
`airport/placement_carrier.py` (§16c (8)'s `_rests_on` / `_admit` inside
`carriers_for`) and `airport/placement_plan.py` (the unit's own ε-contact pairs;
pass 3 takes the cluster's senior INSTEAD of the carrier search for a bound
body).  Matched arms on the 1.0.320 rebake plan + `LEMD.graded.json`,
`--admit-skipped` on the live pack read-only, the write half into APFS clones,
`[guard] shared repo UNCHANGED` on every run.

* **§16c (8) ALONE FIXES NOTHING AT `tej2`, AND IS KEPT.**  `P2PK__b0`'s top
  stands **1.45 m** from `tej2`'s base, not within `split_tol_m` 0.3, so the
  yield never reaches it; what carries `tej2` onto `P2PK` is (7).  The rule
  still fires **129 searches** at LEMD on its own (106 in the shipped
  combination, 88 at OTHH) and takes files 2,171 → 2,160; the yield is counted
  as `carrier_refused_zero_off_ground_yielded_rest_on` beside the refusal it
  relieves.
* **THE SITE, REPRODUCED** (main `be882755`, this instrument): `tej2__b0`
  **+2.85** on `LEMD03__b0`, `tej2__b1` **+14.64** on `LEMD38__b27` (both with
  `P2PK__b0` refused at `ground_off` **0.42**), `LEMD48__b0` **−3.90**,
  `LEMD47__b1` **+20.57**; `LEMD47` at three zeros **1.19 m** apart; the T2
  named block within 150 m of 40.4660017, −3.5694045 spread **1.365 m** over 12
  bodies (building class 0.325 over 8); `LEMD47`/`LEMD48` **228** cross-member
  ε-contacts, **164** among the named T2 resources, 12,408 cross-member in the
  plan.
* **THE BARS, LEMD** (before → after): torn seams outside line/arc **0 → 0 —
  MET**; single-component resources in ≥ 2 files **0 → 0 — MET**; §15 carried
  float **0 → 0 — MET**; §14 footless at datum / on ground / basin split
  **0/0/0 → 0/0/0**; §16 rows on the datum **0 → 0**; round trip **OK**
  (2,148/2,148 new `OBJECT_DEF`s, 0 rows carrying an elevation); files
  **2,171 → 2,148**; §16b carried piece float **108 → 117** (worse, named),
  wider than its terrain group **982 → 973**; plan stage on the graded sampler
  **9.70 / 9.75 / 9.93 s** against main's **10.09 / 11.12 / 24.63 — MET**.
* **THE T2 BLOCK, AND WHAT IS STILL MISSED.**  Named-block spread
  **1.365 → 0.537 m** (bar ≤ 0.3, **MISSED**); building class 0.325 → **0.312**;
  `LEMD48` **one zero — MET**; `LEMD47` three zeros → **two, 0.804 m apart**
  (**MISSED**); `tej2`'s contacting piece rides **`P2PK__b0`** — the bar's own
  sentence — while its two other terrain pieces, which the plan records no
  contact for, keep `LEMD03` (+2.86) and `LEMD38` (+14.64).  Roof bodies whose
  reason is still `rests on it` and whose authored gap exceeds 0.3 m: **7 of 12
  → 5 of 7** (worst 20.57 → 15.96).  NAMED FOR THE OWNER: the "within 0.3 m of
  the wall it rests on" reading is an AUTHORED number for `LEMD47`/`LEMD48` —
  their roofs are authored 5–9 m above the top of the only wall geometry under
  them (`LEMD47__b0` top 4.66 against a roof base of 9.62), so no carrier
  choice can make it 0.3; what (7) can do, and does, is put the roof and the
  walls at ONE zero.
* **THE 11at / 12h / 12o SITES HELD**: item 3 **+0.06 → +0.05**, item 5
  **−0.29 → −0.27**, gate-5 sign **−0.02**, the T4 deck **+0.14**, `HANG3`
  **−0.81** (7 → 6 files), and `Terminal4_48` **+0.49 → −0.11** — improved by
  the senior rule below.
* **THE CLUSTERS, AND THEIR BOUNDS.**  LEMD **136** clusters of more than one
  body, five largest plan spans **298.9 / 295.7 / 293.0 / 292.0 / 289.4 m**
  (28 / 22 / 8 / 176 / 14 bodies); non-senior bodies bound: **168 footed, 733
  elevated**.  OTHH **187** clusters, largest spans **299.7 / 299.7 / 299.5 /
  299.4 / 299.0 m**; **386 footed, 10,119 elevated**.  `UNIT_CLUSTER_SPAN_MAX_M`
  is **300 m** and is a measured constant, not a ruled key: at
  `RIGID_CLUSTER_SPAN_MAX_M` (1,200) the unit graph made clusters **1,190 m**
  wide that collapsed **10.46 m** of honest terrain reading onto one zero
  (`LEMDzaun` stations, `LEMDgrass` mats), and at **100 m** the whole T2 fix is
  lost (`LEMD47__b1` back to +20.57, `tej2__b1` to +14.64) exactly as 12o's
  100 m cap broke `Terminal4_48`.
* **THE SENIOR IS §9's, THEN THE FOOTPRINT.**  Three rules measured: the hull
  BOX area gave the T2 block 0.568 m and `Terminal4_48` **+0.75** (a KIOSK whose
  parts are scattered over the terminal took the cluster); the true FOOTPRINT
  (part-box area) gave `Terminal4_48` −0.11 and the block **1.200**; the most
  GROUND-CONTACT VERTICES then footprint — which is `senior_of`'s own seniority
  — gives the block **0.537** and every named site held.  That is what ships.
* **THREE MECHANISMS REFUTED AND DELETED.**  (i) Restricting an elevated body's
  candidate set to the candidates it TOUCHES: `tej2_teilb` −0.24 → **−11.46**,
  `LEMD58` −0.18 → **−11.79** — a body touches things it does not rest on.
  (ii) A contact TIER ahead of §16c (4)'s rest-on ranking: the same class of
  regression.  (iii) Ranking a body's own member's candidates first inside
  `carriers_for`: superseded by the cluster, which answers "what is it part
  of" instead of "what does it stand over".  All three are gone from the tree.
* **TWO GUARDS THE MEASUREMENT FORCED.**  A cluster senior must READ A SURFACE
  (an off-sheet anchor put `Cargo-EAT` 599 m down onto its authored row), and
  a LINE object or a BASIN body never binds (§10's stations each read their own
  ground; §14 (2) makes a pit's zero its rim — bound, LEMD03/36/85 split into
  **8 torn seams and 3 basin splits**).  Two FOOTED bodies of one member are
  never unioned by the member rule either: they were cut apart because the
  ground under them differs, and unioning them moved `Terminal4-LEMD01`'s two
  bodies **20.5 m** onto one zero.
* **THE COLLATERAL, AIRPORT-WIDE** (keyed by part ids, never by file name — a
  file's index is reassigned when the body count moves): **175 carriers
  changed, 187 zeros moved**, largest real move **7.93 m**
  (`Terminal4_green-PKT4`'s elevated body from `LEMD02__b6` to `STRT4__b8`),
  then 4.28 / 3.88 / 2.09 m; two bodies moved **+565 m** OFF their authored
  datum onto real ground (`Munoza-LEMD78` / `-LEMD76`, an improvement).
* **THE BARS, OTHH** (matched before/after arms, both under the guard): torn
  seams **0 → 0 — MET**, single-component resources in ≥ 2 files **0 → 0 —
  MET**, §15 carried float **0 → 0 — MET**, files **1,376 → 1,337**, §14
  footless at datum **5 → 4** and basin split **1 → 1** (both PRE-EXISTING,
  neither made worse), §16b carried piece float **183 → 163**, wider **70 →
  65**, round trip **OK** (1,336/1,336 new `OBJECT_DEF`s), `[guard] shared repo
  UNCHANGED`.  Plan stage on the graded sampler, matched arms on this machine:
  **73.2 / 83.4 / 84.2 s** against main's **68.6 / 77.2 / 82.4** — the cluster
  pass costs OTHH a few seconds inside the noise, and BOTH arms are over 12o's
  64 s figure today, so the ≤ 64 s bar is **MISSED on both sides** and the
  regression is not this round's.  The unit pass was bounded once for cost: a
  member with ONE footed body unions its elevated bodies without the
  plan-overlap loop (OTHH publishes 49,793 elevated bodies), which took it from
  87–93 s to 73–84 with the plan byte-identical.
* **Twins:** `test_the_unit_binds_by_contact`,
  `test_a_cluster_never_grows_wider_than_a_building`,
  `test_a_line_object_and_a_basin_never_join_a_unit_cluster`,
  `test_the_rest_on_carrier_is_not_refused_for_its_own_ground`; the footless-deck
  twin AMENDED (the deck and the terminal are in ε-contact, so the reason is now
  §16c (7)'s binding onto the same carrier at the same zero).  Suite **1,173
  passed / 1 skipped** (main 1,169 / 1).
* **NOT DONE:** no airport build (§16c needs none); the ≤ 0.3 m block-spread and
  `LEMD47`-one-zero bars are MISSED and named above; `tej2`'s non-contacting
  pieces are unchanged; the rigid REACH is NOT extended across members (only the
  plan's ε-contact graph and the member rule bind a unit — the cross-member
  reach was not measured and is owed); no `tools/INDEX.md` row changed (no tool
  gained or lost a flag).

**MEASURED (lane `v2reach`, 2026-09-12; branch `claude/v2reach` from main
`5a7b325d`; owner RULINGS 2026-09-12am (1)).**  Matched arms on the 1.0.320
rebake plan + `LEMD.graded.json`, `--admit-skipped` on the live pack read-only,
the write half into APFS clones, `[guard] shared repo UNCHANGED` on every run.

* **THE SITE, ATTRIBUTED — AND IT IS NOT THE REACH.**  `LEMD47` is written at
  two zeros because §16c (7)'s rule (a) — an ELEVATED body joins its own
  member's footed cluster — **never fired at all**.  `bind_unit` built every
  `RigidNode` POSITIONALLY and the dataclass declares `footprint_m2` BEFORE
  `footed`, so every node read `footprint_m2` **True** and `footed` its own
  area: a member's `feet_i` held all 114 of `LEMD47`'s bodies, not one was
  "not footed", and no union was ever made by (a).  Only the ε-contact graph
  bound anything, and `LEMD47`'s footed walls (parts 929/931/961/964, 16 feet)
  carry **ZERO** recorded contacts — all 114 with `LEMD48` are on its ELEVATED
  parts.  Measured plan distance from those walls to the nearest other body of
  the unit: **0.000 m** (its own elevated parts, `LEMD48`, `LEMD49`,
  `LEMD38__b27` all overlap it in plan), so no reach length was ever the
  question.  The seniority tie-break was inert for the same reason
  (`_area` returned 1.0 for every footed candidate): what shipped at 12z was
  "most feet, then the low side", not "then the footprint".
* **THE FIX IS THE FIELD ORDER PLUS THE RULE'S OWN DISTANCE TEST, AND IT
  MEETS THE OWNER'S BAR.**  Every field is named at both construction sites,
  and rule (a) picks the footed body of the member the elevated body STANDS
  OVER (largest plan overlap), else the NEAREST within `coarsen_reach_m`
  (100 m).  Both halves of that are measured: 12z's one-footed FAST PATH
  unioned with no test at all — dead while the field order was wrong, and the
  moment (a) lived it broke §15 (1)'s own twin
  (`test_a_roof_resource_rides_the_walls_of_ANOTHER_resource`: a member's
  ground body 250 m from its roof, LEMD's `LEMD38` +6.11 m) — while a strict
  OVERLAP test left `LEMD47` at **two zeros 0.491 m apart**, because its roof
  pieces stand BESIDE its walls (0-12 m), not over them.
* **THE BARS, LEMD** (main `5a7b325d` → this branch): `LEMD47`
  **two zeros 0.804 m apart → ONE (603.619) — MET**; `LEMD48` one zero, now
  the SAME one; T2 named-block spread **0.537 → 0.474 m — MET** (bar ≤ 0.5),
  building-class spread 0.474 → **0.385**; the 11at / 12h / 12o / 12z sites
  HELD (item 3 **+0.05**, item 5 **−0.27**, gate-5 sign −0.02 → **+0.04**,
  T4 deck **+0.14**, `Terminal4_48` **−0.11**, `HANG3` **−0.81** / 2 files,
  `Bridge2` 6 files, `green-LEMD50` 1 file, and
  `Terminal4SAT_green-TEJ3` **5 files / 5 zeros, byte-equal — its panels do
  not chain**); torn seams outside line/arc **0 → 0 — MET**;
  single-component resources in ≥ 2 files **0 → 0 — MET**; §15 carried float
  **0 → 0 — MET**; §14 footless at datum / on ground / basin split
  **0/0/0 → 0/0/0**; §16 rows on the datum **0 → 0**; §16b carried piece
  float **117 → 101**, wider than its terrain group **973 → 980** (worse by
  7, named); files **2,148 → 2,114**; round trip **OK** (2,114/2,114 new
  `OBJECT_DEF`s, 0 rows carrying an elevation); plan stage on the graded
  sampler **9.22 / 9.29 / 9.30 s** against main's **9.81 / 9.86 / 9.85 —
  MET** (bar ≤ 10.3).  `[guard] shared repo UNCHANGED` on every run.
* **THE CLUSTERS.**  LEMD **211** clusters of more than one body (12z: 136),
  five largest plan spans **299.3 / 298.9 / 298.4 / 297.8 / 297.3 m** — every
  one inside `UNIT_CLUSTER_SPAN_MAX_M`; non-senior bodies bound **192 footed,
  1,329 elevated** (12z: 168 / 733 — the difference is rule (a) working).
  OTHH **215** clusters, five largest **300.0 m** ×5 (164 / 221 / 1,541 /
  1,161 / 111 bodies), **403 footed, 22,932 elevated**.
* **THE COLLATERAL, AIRPORT-WIDE** (keyed by part ids, never file name):
  **93 carriers changed, 91 zeros moved**, largest real move **1.367 m**
  (`OldTerminal_FSX-TECH`, 601.308 → 602.676), then 1.148 / 1.148 / 1.137 ×3
  / 1.124 / 1.074; one body moved **+602 m** off its authored datum onto real
  ground (`Cargo-LEMD64`, an improvement).
* **THE BARS, OTHH** (matched arms under the guard, main → this branch): torn
  seams **0 → 0 — MET**, single-component **0 → 0 — MET**, §15 carried float
  **0 → 0 — MET**, files **1,337 → 1,252**, §16b carried piece float
  **163 → 126**, wider **65 → 75** (worse by 10, named), §14 basin split
  **1 → 1**, §14 footless at datum **4 → 5** — one WORSE on a bar already
  violated, named: an elevated body that used to take a carrier now takes
  neither a cluster nor one.  Round trip **OK** (1,251/1,251 new
  `OBJECT_DEF`s), `[guard] shared repo UNCHANGED`.  Plan stage on the graded
  sampler, this machine, same hour: **57.6 / 58.0 / 58.3 s** against main's
  **61.5 / 59.9 / 60.0** — MET.
* **THE CROSS-MEMBER RIGID REACH IS REFUTED AND DELETED** (the code is in
  `claude/v2reach` `70776af7` and its revert; the record is here).  Solid
  bodies of different members chaining within `rigid_reach_m` was implemented
  twice and measured three ways on the same frame:

  | arm | T2 block spread | carriers changed | LEMD plan stage |
  |---|---|---|---|
  | main `5a7b325d` | 0.537 | — | 9.8-9.9 s |
  | field order + (a)'s distance test (SHIPPED) | **0.474** | 93 | **9.2-9.3 s** |
  | field order + reach, PART BOXES | 1.548 | 254 | — |
  | field order + reach, AUTHORED VERTICES | 1.949 | 137 | — |
  | ... and no footed↔footed union | 0.875 | 100 | **67.1-67.9 s** |

  (the three reach arms were measured against the FAST-PATH form of rule (a),
  whose own numbers are `LEMD47` one zero, block 0.537, 66 carriers — the
  arm the twin above then refuted)

  The mechanism, named: a 2 m chain walks a terminal's APRON.  At LEMD it put
  `AES_SAFE09__b16/17/19/20`, `PLANK__b3`, `TECH__b9/10/11`, `YETWY__b9/10`,
  `TWY__b3`, `LEMD60__b15` and the terminal bodies beside them onto ONE zero
  **1.24 m below the block** — eleven FOOTED bodies, each of which had read
  its own ground, collapsed onto the one with the most feet.  Forbidding
  footed↔footed unions (12z's within-member veto, extended) halves the damage
  and does not remove it, and the reach still costs the LEMD plan stage
  **6.8x** (67 s against 9.9, bar 10.3).  Both halves of the bar — "T2 block
  spread ≤ 0.5" and "nothing else worse than 0.5 m that was under it" — are
  MISSED by every arm of the reach and MET without it (0.474).  A
  cross-member reach therefore needs a rule that is not distance: what §16c
  (7) is FOR is a body with no ground of its own, and the ε-contact graph plus
  rule (a) already reach that class.  The owner's call.
* **Twins:** `test_an_elevated_body_joins_its_own_members_footed_cluster`
  (both halves: `unit_rigid` directly, and one member with a footed part and
  an elevated part over it through `build_splits` — it FAILS on main
  `5a7b325d` and passes here); the four §16c (7)/(8) twins AMENDED to name
  every `RigidNode` field, since building them positionally is what let the
  defect through; and §15 (1)'s
  `test_a_roof_resource_rides_the_walls_of_ANOTHER_resource` is what caught
  the fast path — it is the distance test's own witness and is unchanged.
  Suite **1,207 passed / 1 skipped**, twice (main 1,206 / 1).
* **NOT DONE:** no airport build (§16c needs none);
  `tej2`'s non-contacting pieces are unchanged; the T2 roofs' authored 5-9 m
  gap is unchanged (12z's reading stands); no `tools/INDEX.md` row changed (no
  tool gained or lost a flag).

## Spec (object-placement) §16g

## §16g THE FOOTPRINT UNIT (owner RULINGS 2026-09-13bo, interviewed; Fable 2026-09-13) — lane `v2clusterpad`

Owner: "We always want to keep objects covering the same footprint together
when changing their seat. Objects separated by lateral space, e.g. separate
buildings, can move vertically independent of other buildings. Only time we
allow actually cutting objects apart is for things like very long connecting
pieces like the elevated rail at HECA." This ONE rule replaces every family
derivation tried today: §16e (3) by row, ring, footprint contact or NAME
(all withdrawn), §16f (1)'s shared-authored-datum condition, §16f (4)'s
partition by pad. §16f (7) (a large cluster is one unit on one pad, the
apron flattened around it — design §30 (4)) is this law's design-surface
side and stands.

1. **THE UNIT.** Two bodies whose plan footprints (their written triangles
   projected, `geom_box` hull refined by the actual polygon) overlap or
   touch within 0.5 m are one unit; units chain transitively (deck ↔ piers
   ↔ clutter ↔ …). A body touching nothing is its own unit and seats alone
   (§16c). Derived once per plan, at the end of PASS 1 (before the carrier
   pool), published per body as `unit_of`; the census prints each unit's
   members, spread and datum source.
2. **ONE ZERO PER UNIT.** Every member of a unit takes one rigid zero — no
   per-member cut, no carrier search, no ground test between members. The
   datum, in priority: a DECK member's abutment datum (§16e (2)/(6)); else
   the plane of the emitted `building` pad most of the unit's contacts
   stand on (§16f (2), the cluster pad §30 (4) for a large unit); else the
   median ground under the unit's contacts. A member whose own contacts sit
   more than `visual_m` off the unit plane is REPORTED, never re-seated.
   Pavement is king (§16f (5)) only for a unit standing ENTIRELY on
   rolled-on pavement; inside a mixed unit the datum rule wins.
3. **THE ONLY CUT.** A body whose footprint span is ≥ 200 m AND whose two
   ends' ground differs by ≥ `visual_m` is a CONNECTOR (the HECA elevated
   rail class) and is cut at §10's line stations; everything else stays
   rigid. The census names every cut connector.

BARS: OTHH every `Bridge_NN` deck ↔ piers ↔ clutter one unit (per-unit spread
0.00; today 4.97 m on `Bridge_02_CLUTTER_007`; the deck tops 3.96 held);
KCLT's terminal one unit on its cluster pad (the passengers on the floor);
LEMD's old terminal one unit per touching cluster (named); HECA's elevated
rail cut at stations (dry, named); plan stage not worse than +10 %; the
family censuses of §16f re-read under §16g; suite twice.

### §16g MEASURED (lane `v2clusterpad`, 2026-09-13; branch `claude/v2clusterpad`)

**WHAT LANDED.**  `airport/footprint_unit.py` (NEW) holds the whole law:
`bind_footprint_units` (the unit, its one zero and the priority datum) and
`cluster_zero_allowed` (§16g (4)'s bound on §16c (7)'s short-circuit).  The
DERIVATION is `placement_family._clusters` asked at `[placement]
footprint_touch_m` (0.5 m) with `min_members=1` — ONE derivation, three
readers: this law, `planar/cluster.plan_clusters` (the design surface's
cluster, read off the pack partition at LOAD so §30 (4)'s pad exists before
the object stage does) and §16f's own census.  `placement_plan.build_splits`
calls `bind_footprint_units` where it called `bind_families`; §16f's bind is
no longer on the shipped path and its law and twins stand where they are.
`unit_of` is published beside `family_of` (`placement_record`,
`model/placement.Body`).  New law keys: `[placement] footprint_touch_m =
0.5`, `[placement] connector_span_m = 200.0`, `[placement]
cluster_pad_min_m2 = 5000.0`, `[design] cluster_apron_reach_m = 60.0`.

**A DEFECT IN THE SWEEP, FOUND BY THE NEW TOLERANCE.**  `_clusters`'s
south-edge sweep broke on `hull[b][0] > hull[a][2]` — no slack for `eps_m`.
At §16f's millimetres that rounds away; at 0.5 m it BREAKS ON THE VERY PAIR
THE LAW BINDS (a pier 0.3 m north of its deck starts past the deck's north
edge).  The sweep now carries the tolerance; the §16g twin holds it.

**THE FRAME.**  The registered KCLT rebake + graded pair
(`frames.py list KCLT`, the `v2familyKCLTframe` build, base `864e7577`), the
OTHH 1.0.326 frame (`v2othh1o`), matched dry arms through
`tools/obj8_split_report.py`; base arm `git archive 0c86fe2c src tools`.
**EVERY OBJECT-STAGE NUMBER BELOW IS READ AGAINST A DESIGN SURFACE THAT
CARRIES NO CLUSTER PAD** — the graded document is the base build's — so a
member the unit holds UP over its own ground is the design surface's job,
not yet done in these arms.  That is the whole reason §16f (7) and §30 (4)
are one ruling.

| bar | base `0c86fe2c` | §16g |
|---|---|---|
| KCLT units | §16f: 2 families, 191 bodies | **50 units, 399 bodies; per-unit zero spread 0.00 everywhere** |
| KCLT the terminal | two rows, both `building80` 221.49 | **`unit:31#0` (19 members, 163 bodies) and `unit:30#0` (19, 29) both on `building80` at 221.49** |
| KCLT datum sources | — | `cluster_pad` (the two terminal units + 30 more over 5,000 m²), `pad`, `ground` — counted per unit in `unit_datum_*` |
| KCLT plan stage (with the OBJ8 cut) | 14.39 s | **12.61 s** |
| KCLT §17 CRITICAL MOTION | 910 feet / 73 bodies | **1,171 / 68** — WORSE in feet, and expected: the unit holds members level over ground the design surface has not yet lifted |
| KCLT §16b carried float / wider | 41 / 232 | **32 / 249** |
| KCLT §15 carried over a refused body | 7 | **7** (the coordinator's 8 → 0 bar is against another base; NOT met) |
| KCLT §16a (2) refusal set | 80 | **161** — the same reading: a unit member standing on real relief |
| OTHH plan stage | 237.66 s | **200.30 s** |
| OTHH files | 1,788 | **2,478** (695 placements split, bodies 2,136 → 2,836) |
| OTHH low-side anchors with a residual | 199 | **69** |

**§16g (4) COMPONENTS APART (RULINGS 2026-09-13bu item 4).**  Two edits:
`placement_body._atom_targets` no longer applies the `coarsen_reach_m`
AFFORDABILITY bound to a FOOTLESS member (a footless body has no ground of
its own to fall back on, so its components apart in plan must each ask what
they stand over), and `footprint_unit.cluster_zero_allowed` withdraws §16c
(7)'s short-circuit from every footless member and from any cluster member
standing further than `coarsen_reach_m` away.  Measured on the same frame:
`Charlotte_Airport_001_ALB` **29 bodies → 82**, and the owner's four roof
sites (13bj item 4) each acquire a roof body of their own —
35.2141727,−80.9291957 had its nearest at **68.6 m** (zero 214.79) and now
has one at **42.1 m** (216.16); 35.2142131,−80.9282182 **52.6 m → 37.1 m**;
35.2140873,−80.9306125 **106.5 m → 20.6 m**; and 35.212974,−80.9298385 had
**NO body within 120 m at all** and now has one at **50.2 m** (217.36).  The
resource's whole-resource zero spread stays 20.29 → 21.43 m, which is the
1.7 km hangar district's real relief and NOT the bar; the per-building bar
and the roof-base-vs-wall-top reading need the built surface and are in the
closing build's numbers.

**NOT DONE, NAMED.**  (a) §16g (1) is derived per PLAN UNIT, not
plan-wide: PASS 1's staged bodies exist one unit at a time, so two
touching bodies on different placement rows in different `Unit`s do not
bind.  At KCLT that costs nothing (both terminal rows land on one pad
plane anyway) but it is a deviation from "overlap alone binds".
(b) The footprint test is the PART BOXES, not the refined polygon
(`_clusters`'s own reading, kept).  (c) §16g (3)'s connector is
IDENTIFIED and left out of its unit's rigid bind, and §10's station cut
and §16b's terrain cut divide it as they already do — no new cut was
written.  (d) LINE segments and BASIN bodies keep §16f's exclusions.

**THE UNIT CENSUS, PER AIRPORT (final tree, matched dry arms).**

KCLT, on the lane build's OWN frame (`v2clusterpadKCLT2`, the first frame
carrying the cluster pad) — base `0c86fe2c` against the branch, the SAME
two documents both arms:

| bar | base | §16g |
|---|---|---|
| units | 1 family / 84 bodies | **58 units / 367 bodies**, per-unit zero spread **0.00** everywhere |
| datum source | — | `cluster_pad` **25**, `pad` **12**, `ground` **21**; 8 connectors named and left out; 87 members reported off their unit's plane |
| the terminal | `unit:31#0@building80`, 16 members / 84 bodies, 222.07 | **`unit:31#0@cluster_pad`, 19 members / 165 bodies, 222.07** |
| the owner's site 35.2191877,−80.9426007 | 3 bodies, all 222.07 | **3 bodies, all 222.07** — already on the terminal's floor in BOTH arms on this frame; the passengers and seats themselves are among the **205 multi-anchor placements the plan drops** and the object stage never seats them (see the intent question) |
| plan stage | 15.72 s | **14.10 s** |
| §17 CRITICAL MOTION | 971 feet / 75 bodies | **1,049 / 72** |
| §15 footed float > 0.5 m | 75 | **123** |
| §15 carried over a refused body | 13 | **8** |
| §16b carried float / wider | 57 / 246 | **50 / 257** |
| files | 518 | **648** |

OTHH 1.0.326 (`v2othh1o`), the same two documents both arms:

| bar | base | §16g |
|---|---|---|
| units | 16 families / 206 bodies | **85 units / 1,173 bodies**, spread 0.00; datum `ground` 54, `pad` 15, `cluster_pad` 15, **`deck` 1**; 27 connectors; 8 units entirely on pavement |
| `Bridge_01 / 02 / 03 / 04 / 06` zero spread | 1.95 / **9.71** / **9.18** / 0.00 / **9.67** m | 1.95 / **1.52** / **1.93** / 0.00 / **0.00** m — the bar (0.00 per bridge) is MET for 04 and 06 and NOT for 01/02/03 |
| plan stage | 237.66 s | **249.43 s** |
| files | 1,788 | **2,541** |

The bridges are NOT one unit each, and the reason is named above: §16g (1)
is derived per PLAN UNIT and the footprint test is the PART BOXES.  Where
the chain reaches, it reaches all the way (Bridge_06 9.67 → 0.00 with no
bridge-specific law anywhere in the code, which is 13bo's own test).

### §16g (4) COMPONENTS APART ARE SEPARATE BODIES (Fable 2026-09-13; RULINGS 2026-09-13bu item 4) — lane `v2clusterpad`

KCLT's `Charlotte_Airport_001_ALB.obj` is a pure roof resource over the whole
1.7 km hangar district, split into 28 footless bodies with boxes up to
1,747 m wide; the §16c (7) short-circuit handed each a carrier from anywhere
in its rigid cluster (+4.76 m over one hangar, −6.42 under another).

4. The footprint unit applies at the COMPONENT level: a body whose own
   connected components do not touch in plan (beyond the 0.5 m spacing) is
   split into one body per plan cluster BEFORE the unit derivation, each
   seated by the unit it touches. A footless body never inherits a cluster
   zero chosen more than `coarsen_reach_m` away — the §16c (7) short-circuit
   does not apply to footless members.

BAR: `001_ALB` 28 bodies → one per hangar; zero spread 20.99 → ≤ 0.3 m per
building; the four owner sites' roof base within 0.3 m of the wall tops
beneath; `§15 carried over a refused carrier` 8 → 0.

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

### §16g ROUND 2 MEASURED (lane `v2clusterpad`, 2026-09-13; RULINGS 13bw/13by)

**(a) THE UNIT IS DERIVED PLAN-WIDE.**  `footprint_unit.plan_units` /
`plan_unit_datums` / `plan_wide_seats`: the relation is read off the PLAN
before any unit is staged (`bodies_of_plan` + `_clusters`, the same two
derivations), its datum settled per unit (DECK from `Member.deck_datum_z`,
else the pad plurality's own plane, else the median ground under the part
centres), and a staged candidate LOOKS UP the seat by PART ID.  One zero
across placement rows by construction.  OTHH, matched dry arms on the
1.0.326 frame:

| bar | base | round 1 (per-unit) | round 2 (plan-wide) |
|---|---|---|---|
| `Bridge_01` zero spread | 1.95 m | 1.95 | **0.00** |
| `Bridge_02` | 9.71 | **1.52** | 1.52 |
| `Bridge_03` | 9.18 | **1.93** | 1.93 |
| `Bridge_04` / `Bridge_06` | 0.00 / 9.67 | 0.00 / **0.00** | 0.00 / **0.00** |
| units on a DECK datum | — | 1 | **4** |
| plan-wide units / seated | — | — | 185 / 173 |

`Bridge_02` and `Bridge_03` are the bar still MISSED, and the cause is
(b): their remaining pieces stand more than 0.5 m from every PART BOX of
the rest, which the refined polygon would close and the box does not.

**THE COST, AND THE GRID THAT PAID IT.**  Asked plan-wide, `_clusters`'s
south-edge sweep is O(n·k) in the bodies whose latitude bands overlap —
at one unit a handful, over a whole plan most of the airport: OTHH's plan
stage went 249 → **808.61 s** on the first plan-wide arm.  `_clusters`
now indexes by a plan GRID above `_GRID_ABOVE` (2,000 live bodies), each
hull grown by the tolerance so a pair within it necessarily shares a
cell.  The two paths return IDENTICAL clusters at KCLT (114 units either
way, asserted vertex-for-vertex) — and the first grid attempt did NOT:
reading metres-per-degree at each body's own latitude shifts two
neighbours a full cell apart over an airport's easting and found 127
clusters.  One `m_per_deg` for the whole grid fixed it.

**(b) POLYGON FOOTPRINTS: NOT DONE.**  The plan-wide derivation is
PLAN-SIDE and the plan carries only `Part.box`; the polygon needs every
member's OBJ8 parsed, which is what the plan stage costs.  Named as the
cause of the `Bridge_02` / `Bridge_03` residual above.

**(c) §16g (5), AS AMENDED BY THE OWNER (13by).**  The first
implementation wrote `OBJECT_MSL lat lon heading elev` for every dropped
multi-anchor placement; the owner then answered his own question — ON
GROUND SUFFICES AND IS THE BETTER DEFAULT, because inside an airport the
mesh terrain IS our design surface, and under a terminal cluster that is
the cluster pad, i.e. the floor.  So `msl_seats_for_dump` now returns a
row ONLY for a unit whose datum is a DECK (on-ground there would put the
piece on the road under the deck); everything else is left alone, and
`multi_anchor_census` counts how each is seated.  KCLT, on the pack's
pristine dump against the round-2 plan:

| class | KCLT |
|---|---|
| multi-anchor rows the plan holds no member for | **11,314** (205 RESOURCES) |
| left ON GROUND | **8,979** |
| converted from `OBJECT_MSL` / `OBJECT_AGL` to on-ground | **2,335** |
| written as `OBJECT_MSL` (a deck datum) | **0** |
| DROPPED | **0** — the bar |

**THE OWNER'S SITE, MEASURED.**  The passengers and seats at
35.2191877, −80.9426007 are `sala_sillas_4x2.obj`,
`sala_personas_4x1_a.obj` and `sala_maletas_4x1_a.obj`, 4.8–7.8 m away,
authored as **`OBJECT_AGL`** rows — which the conversions pass ALREADY
turns into on-ground rows, on main as on this branch.  The graded surface
at that point is `building80`'s pad plane: **221.47 (disarm) / 221.44
(cluster)** — the floor, and the SAME in both arms, because the cluster
pad's effect there is on `building91` (+3.43 m), not on `building80`.
The bar as written ("222.28 ± 0.05") was a number from the earlier
UNMATCHED frame; on the matched pair the terminal floor is 221.44.  An
intent question follows from that and is in the report.

**(c) FINAL — §16g (5) AS RULED IN 13cb: THE FAMILY RELATION IS THE
INVARIANT.**  13by's "on ground for everything" was corrected: a
placement standing in a footprint unit is seated at THE UNIT'S DATUM PLUS
ITS AUTHORED OFFSET wherever its anchor falls, so a second-floor
passenger floats where the author put them.  "On ground" survives only
where the terrain at the anchor ALREADY equals the datum within
`[design] hard_tol_m` (0.02 m) AND the row asks for no offset — there the
row is left exactly as it is.  `authored_offset` reads an `OBJECT_AGL`
row's column as the offset and an `OBJECT_MSL` row's as an ABSOLUTE
against the ground the pack was authored on (the plan's flat datum
`z0_m`; with none known the offset cannot be recovered and the row is
left alone rather than guessed at).

KCLT, the pack's pristine dump against the round-2 plan and its graded
surface (flat datum `z0_m` 223.876):

| class | KCLT |
|---|---|
| multi-anchor rows the plan holds no member for | **11,314** (205 resources) |
| standing INSIDE a footprint unit | **5,263** |
| written `OBJECT_MSL` = unit datum + authored offset | **4,846** |
| left ON GROUND (no unit, or the terrain already IS the datum) | **6,386** |
| converted from the pack's own `OBJECT_MSL` | **82** |
| **DROPPED** | **0** — the bar, MET |

**THE OWNER'S SITE, FINAL.**  The three resources at 4.8–7.8 m from
35.2191877, −80.9426007 — `sala_sillas_4x2.obj` (seats),
`sala_personas_4x1_a.obj` (passengers) and `sala_maletas_4x1_a.obj` — are
`OBJECT_AGL` rows authored **+4.00 m**, and they are now written
`OBJECT_MSL` at **225.44** = the cluster pad's plane **221.44** plus that
offset: the second-floor concourse floor, which is exactly the relation
13cb makes the invariant.  Ground-level neighbours in the same unit
(`showel.obj`, `water_tank.obj`) are written at **221.44**, the pad
plane itself.  Under 13by's earlier reading all of them would have been
left to the drape and the +4.00 m would have been lost.

**§16g (1) PLAN-WIDE, THE OTHH PLAN STAGE RE-TIMED (lane `v2clusterpad`
round 5, owed since round 2).**  The grid was deleted as refuted in round
3 (`plan_units` grid 557.5 s against the sweep's 485.7 s for identical
clusters); this is what the shipped sweep costs.

| arm | OTHH plan stage |
|---|---|
| §16f, per-unit (round 2 base) | 237.66 s (with the OBJ8 cut) |
| §16g per-unit (round 2) | 249.43 s (with the cut) |
| §16g PLAN-WIDE, first arm (round 2) | 808.61 s (with the cut) |
| **§16g plan-wide, grid deleted (round 5)** | **436.53 s (with the cut)** — ONE run, and CONTENDED (another lane's build started inside it), so it is an upper bound, not a timing |
| the same, `--no-cut`, quiet machine, 3 runs | **367.87 / 371.73 / 366.13 — mean 368.58 s**, spread 1.5 % |

So plan-wide costs OTHH roughly **1.75x** the per-unit reading (436.5
against 249.4), down from the 3.2x the first arm measured.  The cost is
`bodies_of_plan` and the PART-BOX product inside `_clusters._bind`, not
the pairing sweep — which is also where §16g (2)'s undone polygon
footprints would have to be paid for, so the two are one piece of work.
A clean exclusive with-cut `--runs 3` is still owed.

### §16g (6) A CONNECTOR JOINS TWO UNITS; AN IDENTIFIED CONNECTOR KEEPS ITS DATUM (Fable 2026-09-13; RULINGS 2026-09-13cn; owner 2026-09-13 "only … very long connecting pieces like the elevated rail at HECA") — lane `v2connector`

**THE DEFECT (scout `v2spjcramp`, SPJC 1.0.329).**  `SPJC_LIMANUEVA_xp11_007__b0`,
the access-road viaduct at −12.0322, −77.1170407: span 549 m, end-ground spread
11.58 m → (3) names it a CONNECTOR, `_bind_plan_wide` drops it out of the
terminal unit `fu:0:0@cluster_pad` (datum `building6` 19.5604) and writes NO
cut, so it falls to §16c's low-side foot, which pins its −8.308 m footing
bottom to the mesh: authored zero at 27.366 against the unit datum 19.560 —
**7.81 m high**, the deck 18 m over the apron, "sitting on top of the terrain".
`xp11_010__b0` (span 1,030 m) is expelled the same way and lands 0.99 m LOW.
All eleven LIMANUEVA placements share ONE DSF origin in the source pack: they
are one authored unit.  Nine chain into the terminal unit; the two longest
are thrown out by the very rule that exists for a kilometre of elevated rail.

**THE LAW.**
1. A CONNECTOR is a body that CONNECTS: its span is ≥ `connector_span_m`,
   its end ground differs by ≥ `visual_m`, AND its two ends touch (≤
   `footprint_touch_m`) TWO DIFFERENT plan-wide units, or one unit and open
   ground beyond `connector_span_m` of it.  A body whose every contact
   chains into ONE unit is a MEMBER of that unit however long it is and
   however much the ground under it varies — the elevated viaduct inside a
   terminal is the terminal's.  "Long and sloping" alone identifies nothing.
2. A body that (1) DOES name a connector is still chained for the purpose of
   the unit census, and until §10's station cut is actually written for it,
   it is seated on the datum of the unit its HIGH end touches (the deck-side
   unit; DECK > PAD > GROUND between the two).  An identified connector
   never falls to §16c's low-side foot: the exclusion in `_bind_plan_wide`
   is replaced by that seat.  When the station cut lands, each piece keeps
   its unit's datum at its unit end and grades between (the §10 line).
3. Provenance is a witness, not a rule: bodies whose source-pack placements
   share one DSF origin and heading (the shared-datum pack, `-13-078.dsf`
   LIMANUEVA rows) are recorded in the census as `authored_unit`; a unit
   partition that separates two `authored_unit` siblings is reported as
   `unit_split_authored` in the cockpit (WARN) — the measurement that would
   have named this defect at plan time.

BARS: SPJC `xp11_007__b0` and `xp11_010__b0` members of `fu:0:0@cluster_pad`,
authored zero at the unit datum (19.56 ± `hard_tol_m`), `unit_connectors_cut`
0 at SPJC; HECA's elevated rail still identified as a connector (its ends in
two units or open ground) and seated on its high-end unit's datum, named;
KCLT / OTHH / LEMD unit censuses re-read: connectors before → after with each
one's two end units named; `unit_split_authored` 0 at SPJC after; plan stage
not worse than +5 %; suite twice.

### §16g (6) MEASURED — THE ARTICULATION-POINT READING (lane `v2connector`, 2026-09-13; RULINGS 2026-09-13df)

"Hold the long body out and see what its ends touch" holds TERMINALS out at
200 m; a unit built without them is not the unit.  What ships: the partition
is §16g (1)'s byte-for-byte, and each long body is asked *remove me and see
what my unit falls into* — ends in two different components → connector;
one component and nothing within `connector_span_m` of the free end →
connector to open ground; every contact into one component → MEMBER however
long.  A topology-connector is seated on its high end's component only when
the ground-step test ALSO fires (round 1 expelled the 8 of LEMD's 9 and 12 of
HECA's 26 topology-connectors that do not step).  `Body.unit_of` was declared
and never filled — every written plan carried null while the unit law ran;
filled, with `connector_of`.  `unit_connectors_cut` 0 at every airport;
`bodies_bound_to_unit` rose everywhere.  SPJC `xp11_007__b0` 27.41 → 19.56,
`xp11_010__b0` 18.57 → 19.56 (unit datum 19.560).  HECA's longest connector
`concrete_3.obj` b1 (1,149 m, terminal complex ↔ a 1,469-body group) 73.83 →
95.55 on the `T3_road.obj` deck.  `connector_of` propagates onto carried
bodies (a carried body takes its carrier's anchor, as `family_of` does): the
census counts SEATS, bearers are report-only (RULINGS 13df).  The §10 station
cut is still not written; `connector_of` records both ends for it.

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

### §16g (9)–(10) MEASURED (lane `v2padcluster`, 2026-09-14; branch `claude/v2padcluster`)

**THE DRY READ FIRST (the handover's item 1), off the registered HECA
round-6 frame `HECA_20260914T110528` (rebake plan + graded document).**

*(a) WHAT THE §30 (4) (5) YIELD GATE DISCARDS.*  `cluster_pad
._touching_component` keeps ONE pad face per cluster and yields the rest:

| cluster | union | pad faces hit | KEPT | area kept |
|---|---|---|---|---|
| `unit:42#0` | 404,117 m² / 84 members | 22 (204,419 m²) | 1 — `building7` | 52,330 m² = **25.6 %** |
| `unit:43#8` | 929,154 m² / 149 members | 73 (294,461 m²) | 1 — `building1` | 63,356 m² = **21.5 %** |

So 14z's reading is exact: the gate starves everything downstream —
`plane_groups` never merges, `cluster_pairs` counts 0 cross-links and
`cluster_offsets` bails on `len(floor) < 2`.  Three quarters of the pad
area a cluster stands on yields to the box-versus-polygon artefact the
gate was written for.

*(b) THE POPULATION, and (10) (1)'s premise is REFUTED at HECA.*
24,165 plan bodies in 324 units; **8,290 carry a ground-contact
component** (a `Part` with `feet`) and 15,875 do not — they are ELEVATED
and have no ground floor of their own.

| population | clusters | largest |
|---|---|---|
| today (part BOXES, `FAMILY_*` + `min_m2` on) | **2** | `unit:43#8` 929,154 m² / 12,198 bodies |
| (9): outlines at `footprint_touch_m`, gates OFF | **1,251** (444 of ≥ 2 bodies) | 569,608 m² / 9,892 bodies |
| (10): + floor split over EVERY body's `base_y` | **20,203** | — |
| (10): + floor split over FOOTED bodies only (14z's GROUND FLOOR) | **2,677** | 541,200 m² / 9,334 bodies |

Splitting on every body's lowest component shatters a tall building per
storey (20,203 clusters) — exactly what 14z forbids, so the split is
taken between two GROUND-CONTACT bodies only and an elevated body chains
by touch alone.  **And the T3 district still does not resolve**: its
footed bodies stand at 0.00 and −1.00 m and genuinely touch, so at
`floor_split_m` 0.5 the district stays ONE cluster of 9,334 bodies /
541,200 m².  14x's "HECA's 23-pad T3 district must resolve into as many
clusters as it has floor levels" is a premise the plan does not carry:
the 23-pad span is the emitted PADS' own relief, not an authored floor
disagreement.  Reported, not decided.

*(c) THE MISMATCH, TAKEN DRY.*  414 emitted `building` pad faces,
870,563 m².  Against the (9) population: 85 pads span more than one
cluster (worst 5), 64 clusters span more than one pad (worst 18), and
**918 of 1,251 clusters cover no pad at all**.  Under (10): 91 / 65 /
2,118 of 2,524 — the floor split makes the pad↔cluster mismatch WORSE
(worst pad 5 → 37 clusters), because the pads were never derived from
the clusters.  The owner's "they should match exactly" is unreachable by
matching the two populations; only (10) (2)'s derivation reaches it.

*(d) AND IT IS EMITTABLE.*  At the pad law's own floor
(`[building_pad] min_area_m2` 250) the cluster outlines are **401** pads
(9: 370) against **414** today — the pad COUNT is unchanged; the covered
area is 1,541,286 m² against 870,563 m² (1.77×), which is the pack's
true footprints replacing the footprint cache's.

**THE CONSUMER CENSUS (owner RULINGS 2026-08-30l), taken BEFORE any
consumer was edited.**  The change does NOT introduce a new shape class,
role or accessor: what changes is (i) the POPULATION on
`Airport.clusters` (2 → ~2,677) and (ii) the DERIVATION of the `building`
pad polygons (the cluster outline union replacing the footprint-cache
ring).  Every reader of `Airport.clusters` / `PlanCluster`, of the pad
polygons and of the pad levels:

| pass / reader | what it reads | ruling |
|---|---|---|
| `planar/cluster.clusters` | `Airport.partition` + `[placement] footprint_touch_m` / `cluster_pad_min_m2` | **EDITED** — the derivation itself: gates off, outlines, floor split.  `cluster_pad_min_m2` stops filtering the POPULATION and keeps its one remaining job, the threshold a cluster gets a §30 (4) cluster PAD PLANE at |
| `pipeline/build.py` `[clusters]` say-line + `partition_cache` payload | `len(_clusters)`, `WHY` | UNTOUCHED in contract — the tuple is longer and the cache entry is a pure function of the same fingerprint (the payload's 4th element is the cluster tuple; a stale entry is keyed out by the code fingerprint) |
| `airport/partition_cache.py` (lane `v2cost2`) | stores/loads the cluster tuple | NOT EDITED — opaque payload; the fingerprint covers the code |
| `classify/evidence._pads` (the ONE pad derivation site) | `airport.buildings` + `[building_pad] min_area_m2` / boundary / runway / skirt | **EDITED** — one pad per CLUSTER (its outline union), then the SAME four gates unchanged; the admitted footprints NO cluster covers keep today's `unary_union` reading, which is (10) (2)'s "fallback where the plan has no cluster".  `[placement] pad_from_cluster = false` restores today's derivation exactly and is the matched base arm |
| `classify/evidence._drop_skirted` (§22.2) | the pads + skirted placement footprints | UNTOUCHED — per pad, geometric; a cluster-derived pad is judged by the same cover fraction |
| `classify/roles.classify` (`pad_union`, :168 / :315) | the pads as ONE union | UNTOUCHED — the union is larger (1.77×), which is the change's intent: the ground under a pack building is a pad, not apron |
| `airport/load.py` §42 `pad_union` (object pavement) | `dsf:object*` footprints | UNTOUCHED and NAMED AS A DEVIATION — §42 runs at LOAD, before the pack is partitioned, so it cannot see the clusters.  It keeps gating draped object pavement on the footprint-cache polygons; where a cluster pad now covers a §42 body, classify's own pad-over-pavement precedence governs, as it does for a `.pol` page |
| `pads._pad_groups` / `_pad_polys` (per FACE) | the pad's vertex set / polygon | UNTOUCHED — per face, and a cluster pad IS one face |
| `pads._pad_rows` → `pad_flats` / `pad_slope_ceiling` | the priced pairs over `plane_groups` | UNTOUCHED in code — under (10) a cluster covers exactly its own pad face, so the merge is the identity and `cluster_pairs`' cross-links are exercised only where classify SPLIT one cluster outline (a runway difference, a multipolygon) |
| `pads.pad_frontage_level` / `_fronting` / `pad_frontage*` / `pad_shared` / `pad_fronts_airside` / `pad_datum_withdrawn` / `frontage_near_miss` | per-face frontage relation | UNTOUCHED — per face; the pads are bigger, so a cluster fronts what its own outline fronts, which is the correction |
| `pad_frontage_gs.groundside_frontage_level` (§28) | `_pad_polys` + `pad_fronts_airside` | UNTOUCHED — per face; §28's direction is unchanged |
| `pad_relief.pad_relief_offsets` (§11a (2)) | pad polygons + the groups' feet | UNTOUCHED — per vertex on the level plane |
| `no_step.pad_pavement_edges` / `pad_contacts` | pad-to-pavement edges | UNTOUCHED — per face and per edge |
| `constraints.ceiling` (`CEILING_RULING`, `LEVEL_RULING`) | the ruling HEADS | UNTOUCHED — same heads, same hard set |
| `constraints/foot_rows.py` (§11b (2)) | `rigid_roles` under a body's feet | UNTOUCHED in code; a body whose ground is now a PAD takes the pad's plane instead of foot rows, which is (10)'s own intent |
| `verify/pads.pad_flat` (`plane_residual`) | per-FACE flatness | UNTOUCHED — and it is the instrument that reports the cost |
| `cluster_pad.cluster_polys` | `PlanCluster.boxes` | **EDITED** — reads `PlanCluster.rings` (the true outline), never the part boxes: the box union is the artefact 13ci's yield gate was written to undo |
| `cluster_pad.cluster_pad_faces` / `_touching_component` | the faces a union intersects | **EDITED** — asked only of clusters over `cluster_pad_min_m2`, and the one-face yield is REPLACED: a cluster's faces are the pad faces its own outline covers.  13ci's union gate survives only for the cluster-APRON reach, which stays DISARMED (13ce) |
| `cluster_pad.cluster_apron_faces` / `cluster_apron_level` (the reach) | apron vertices near a cluster pad | UNTOUCHED — `[design] cluster_apron_reach_m` is 0 (13ce) |
| `cluster_pad.cluster_offsets` (§16g (8)) | `PlanCluster.floors` per box, the plurality pad | **EDITED and NARROWED by 14x** — (8)'s within-a-unit derived pads are withdrawn: under (10) each cluster IS one pad at one level, so what remains is the STEP between two TOUCHING clusters' pads, published as a declared joint (§23) and minting no row |
| `airport/footprint_unit.plan_unit_datums` / `anchor_rule.pad_plurality` (lane `v2cost2` owns `anchor_rule.py`) | the emitted pads under a unit | UNTOUCHED in code — the pad SET changes and a unit's plurality pad is now its own cluster's pad, which is the defect §16g (8) was raised for |
| `pipeline/publication` | the sidecar `cluster_pads` | **EDITED** — additive: `floor`, `rings_area_m2`, `touching_steps`; `yielded_pads` keeps its key and goes empty |
| `tools/check_grade.py` `LAW_FAMILIES` + `law/families.toml` | the census families | **EDITED** — new CRITICAL family `pad_cluster_mismatch` |
| `tools/pad_span_census.py` | a unit's bodies' pads and their span | UNTOUCHED — it reads the emitted pads and the plan, and is the before/after instrument |

**THE DEVIATION, NAMED.**  §42's object-pavement `pad_union` is read at
LOAD, one stage before the pack partition exists, so it cannot be the
cluster pads.  Moving the pack partition ahead of `load`'s §42 block is a
pipeline re-ordering this lane did not take; the interaction is left to
classify's existing pad-over-pavement precedence and reported here.

### §16g (9)–(10) MEASURED, ROUNDS 1–2 — THE LAW IS IMPLEMENTED AND IT BREAKS THE AIRSIDE: STOP-AND-REPORT (lane `v2padcluster`, 2026-09-14; branch `claude/v2padcluster`)

**THE ARMS.**  ONE TREE, ONE MAIN, LAW VALUES ONLY — the base arm is this
same branch with `[placement] pad_from_cluster = false`, `floor_split_m =
0` and `cluster_pad_min_m2 = 0`, which is exactly what those keys' disarm
clauses are for and is a stronger interventional arm than two checkouts.
Both foreground through the harness, both `[guard] shared repo UNCHANGED`.

* DISARM — `v2padclusterHECAdisarm`, rc 0, **462.1 s**, `body_sha
  97a2267cfc28`, ways 1,741, v2-verify rows 30,543
* LANE — `v2padclusterHECA2`, rc 0, **394.8 s**, `body_sha c83dfe27b38d`,
  ways 2,079, v2-verify rows 60,812, artifact ledger `beb3e32ab119`
* (round 1, superseded: `v2padclusterHECA`, rc 0, 809.3 s, `body_sha
  b4bfc32f437d` — `pad_cluster_mismatch` **369**)

**WHAT LANDED.**  (9): `plan_clusters` has no `FAMILY_*` and no area gate,
chains on `Part.rings` and splits at the ground floor — HECA 2 → **1,954
clusters** (`[clusters]` say-line names the population).  (10) (1): the
floor is the body's GROUND FLOOR and the split is taken between two
FOOTED bodies only (per-component: 20,203 clusters, a tall building per
storey — refuted).  (10) (2): the `building` pad is the cluster's outline
union, closed at `footprint_touch_m` and offered LOWEST FLOOR FIRST with
each overlap subtracted (the ONE derivation, `geom/cluster_outline.py`,
shared by `classify` which mints the pad and `constraints` which censuses
it).  13ci's touching-component yield gate is DELETED.  (10) (3):
`pad_cluster_mismatch`, CRITICAL, registered in both registers.  §16g (8)
is narrowed to the DECLARED TERRACE STEPS between touching clusters
(`TOUCHING_STEPS`, published; **128** at HECA, e.g. `unit:38#25 <->
unit:43#6330 +6.469 m`), minting no row.

| bar | DISARM | LANE | verdict |
|---|---|---|---|
| `pad_cluster_mismatch` (bar 0) | 34 (33 + 1) | **44** (41 `cluster_spans_pads` + 3 `pad_spans_clusters`) | **MISSED** (369 at round 1) |
| clusters claiming EXACTLY ONE pad, of 1,400 | 206 | **322** | improved, not met |
| clusters claiming NO pad | 1,161 | 1,037 | — |
| `building` pad area | 867,374 m² / 414 faces | **1,369,935 m² / 652 faces** (+58 %) | the pack's true footprints |
| **airside vertices moved (bar 0)** | — | **13,637 of 21,534 taxi/runway-family vertices over `hard_tol_m` 0.02, worst 10.14 m; the RUNWAY itself 1,110 of 3,426, worst 4.38 m** | **MISSED — AIRSIDE IS KING** |
| the owner's terminal, 30.1279552 31.403143 | surface 72.07 | **82.90** (+10.83 m); `T3_49.obj b4` seated on `building11` at 90.60, **7.66 m above its own feet** | **MISSED — worse at the named site** |
| constraints stage (bar ≤ +10 %) | 83.46 s | **131.42 s (+57 %)** | **MISSED** |
| planar stage | 50.25 s | 53.57 s (+6.6 %) | met |
| v2-verify `pad_flat` / `frontage_near_miss` | 94 / 34 | 251 / 166 | reported |
| suite | 1,468 passed, 1 skipped, twice | | met |

**THE ATTRIBUTION, AND IT IS THE LAW'S OWN PREMISE.**  The airside map
barely moves — runway, `primary_parallel`, `stub` and
`secondary_parallel` AREAS are unchanged to the square metre and
`graded_strip` loses 741 m² — so this is not a classification shift.  It
is the SOLVE: 502,561 m² of NEW hard-flat pad, of which 94,795 m² came
out of the apron and ~370,000 m² out of ground that carried no face at
all, and the apron shares vertices with those pads by 09-01g's weld.  The
pad law is hard; the apron and the taxi family are welded to it; so a pad
set that grows 58 % moves the field.  §30 (4)'s own owner clause — "as
long as it remains feasible with grade laws and taxiways" — and the
standing "airside is king" both refuse this.

**THE RESIDUAL MISMATCH, ATTRIBUTED.**  Round 1's 369 was two mechanisms,
both measured and both closed: 107 of 2,485 cluster outlines were
DISJOINT in plan (the largest in TEN pieces over 259,443 m²) because the
bodies chain within `footprint_touch_m` while their simplified rings need
not overlap; and **519 PAIRS of clusters OVERLAP in plan**, because the
floor split cuts a building into its storeys and two regions cannot
occupy the same ground.  After the close and the ground-floor rule: 0
overlapping pad polygons, `pad_spans_clusters` 257 → 3.  The 41 that
remain are `cluster_spans_pads` — **172 clusters are still in more than
one piece after the close**, and each piece mints its own `buildingN`.
THE NEXT LEVER, NAMED AND NOT ARMED (the attempt cap is spent): split a
cluster at the CONNECTED COMPONENTS of its closed outline, after which a
cluster is one region by construction and `cluster_spans_pads` can only
come from classify cutting one region in two.

**AND ONE PREMISE OF 14x IS REFUTED AT HECA.**  "HECA's 23-pad T3
district must resolve into as many clusters as it has floor levels": its
FOOTED bodies stand at 0.00 and −1.00 m and genuinely touch, so at
`floor_split_m` 0.5 the district stays ONE cluster of 9,334 bodies /
541,200 m².  The 23-pad span is the emitted PADS' own relief, not an
authored floor disagreement.  48 of 1,954 clusters still hold bodies
whose ground floors differ by more than `floor_split_m` — the split is
PAIRWISE over the touch adjacency and a ladder of sub-tolerance steps
drifts; named, not fixed.

**THE KCLT CONTROL IS UNCHANGED, AND THE REASON IS NAMED.**  On the
registered frame (`v2cpKCLTr2`, base `880a9293`) all 355 clusters carry
NO footprint outline — the plan predates §16g (7) (1)'s ring field — so
`cluster_outlines` yields **0 pad polygons**, `_pads` falls back to the
pre-14x derivation exactly, `cluster_pad_faces` is empty, and
`building80` (865 verts, median 221.44, spread 1.08) and `building91`
stand as they did.  A box union is deliberately NOT a fallback: 13ci
measured what pricing one costs.  The control is therefore unchanged BY
CONSTRUCTION and not by measurement — **a KCLT build carrying the
outlines is OWED and was not run.**

**THE INTENT QUESTION (owner).**  §16g (10) (2) is implemented as ruled
and the price is 13,637 moved taxi/runway vertices and the owner's own
terminal 7.66 m off its feet.  Three ways out, none of them this lane's
to choose: (a) the derived pad is a LEVEL for the object stage only and
never a hard flat region in the planar map (the pads stay the footprint
cache's, `cluster_pads` carries the cluster's level); (b) the derived pad
is minted only where it takes NO airside face's ground (a pad that would
eat apron keeps the cache's smaller polygon); (c) the pad rows are
demoted below the taxi family's, and the report names the buildings that
stayed graded.  **Nothing further is armed and the branch should not
merge on the airside numbers.**

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

### §16g (10) (11) THE PAD COVERS EVERY SEATED MEMBER — RE-ARMED UNDER THE CONVERGED SOLVER (Fable 2026-09-15; RULINGS 2026-09-15h) — lane `v2padqp`

**The reading (LEMD 1.0.340, owner 15e item 2).**  The T4 garage
`LEMD_OBJ-Airport_Terminal4_green-PKT4.obj` b0 (H 12.5 m, bbox 667 × 118 m)
is seated by unit membership (`fu:25:983@cluster_pad`, 8 members) on pad
`building12` at 616.10, but that pad's POLYGON (way −10157) ends 55.28 m
short of the garage; its own ground is 612.47 → **3.63 m of air over raw
DEM** (no graded face within 45 m).  Both other pad-minting paths refuse
on the pack's flat render datum (no crest plate; basin depth 0.58 m <
2.5).  This is exactly the mismatch (10) forbids — "no building or
cluster can span multiple pads … they should match exactly" (14x) — and
the mechanism that closes it, `pad_from_cluster`, ships OFF because its
far field moved under the non-converging fixed point (14bk).  §20c now
converges (the one-vertex probe: nothing beyond 4.3 mm).

**RULED.**  (a) A unit member seated on a pad whose polygon does not
contain the member's footprint is the `pad_cluster_mismatch` defect at
that member — never a silent seat over air.  (b) `pad_from_cluster =
true` and `pad_airside_clip = true` are RE-MEASURED under `solver =
"qp"` on ONE tree: the owner's site (the garage) and HECA's 14 mismatch
residual, with (4)–(9) unchanged (leaves get no pad; the skirt yields,
never the airside; between aprons ≤ 1 %, low side).  (c) The pad under
the garage is the cluster outline through PKT4 b0/b1 at the terminal's
datum (616.10, one plane per (9) unless an apron on the far side says
otherwise); the terrain rises to it through the one-way skirt, and
`cluster_apron_reach_m` stays 0 (14bk).  (d) If the far field still
moves with the converged solver, the probe names WHERE and the flag
stays OFF with that number — the mechanism is not re-litigated by
narrative.

### §16g (10) (11) MEASURED (lane `v2padqp`, 2026-09-15; branch `claude/v2padqp`)

**THE OWNER'S SITE IS FIXED, AND IT IS THE FIRST NUMBER.**  The T4
garage `LEMD_OBJ-Airport_Terminal4_green-PKT4.obj` at 40.4892214,
−3.5944287 stands, pads OFF (the shipped law, = 1.0.340), 55.3 m OUTSIDE
the nearest `building` pad — `building12`, 581 nodes, median 616.35 —
which reproduces 15h's "the pad polygon ends 55.28 m short" exactly.
With `pad_from_cluster` + `pad_airside_clip` armed the garage point is
INSIDE its pad: in the closing build `building45`, a 93-node face of a
ref whose EVERY face reads median **615.35** (spread 0.05 within the
containing face), i.e. ONE level over the terminal and the garage
together.  PKT4 is a member of the walled cluster `unit:25#843` (421,940
m², 761 walled bodies, 23 resources incl. `Airport_Terminal4-LEMD01`) —
so the chain rule of (6)–(8) already reaches the terminal and **was not
widened**; the pad is that cluster's own outline.  The terrain under the
garage is now the pad, not raw DEM: z − DEM at the site **+5.14 → +4.33
m of FILL** (replay arms), no step over a short edge (0.0 m) either arm.
The `float` bar (body zero vs its own ground) is the OBJECT stage's
reading and is NOT measured here — a harness patch build emits the
design surface only; it is owed to an app build.  What is measured is
the thing 15h attributed: the seat's pad now CONTAINS the member.

**THE ONE-VERTEX PROBE — AND (11) (d) FIRES.**  Registered HECA
stability frame, `v2_solve_replay --why-from … --probe-site
30.1279552,31.403143 --probe-arm solver=qp`, one 0.30 m ceiling row:

| pads-ON arm | moved > 0.02 m | ≥ 250 m | ≥ 500 m | worst | hard under the probe |
|---|---|---|---|---|---|
| clip at MINT (14ah's pre-split) | **0** / 32,262 | 0 | 0 | 0.0192 m (whole field) | 27 → 27 |
| clip at the ARRANGEMENT (this lane's (a)) | **16** / 32,182 | 16 | **16** | **0.1031 m** | 27 → 27 |

14bk's far-field mover is GONE under the converged solver with the pads
armed as `v2padcluster` r5 left them — nothing moves anywhere by more
than 4.3 cm, under the elevation materiality.  It COMES BACK, 16
vertices ALL beyond 500 m and worst 0.1031 m, when the mint stops
pre-splitting the outline and the arrangement's clip alone shapes the
pad — an interventional attribution of the residual far field to the
PAD/AIRSIDE RIM GEOMETRY, not to the solver.  Per (11) (d) the flag
stays OFF with that number.

**`pad_cluster_mismatch`, ATTRIBUTED AND PART-CLOSED.**  r5 left 14 and
named the cause ("the cluster piece and the emitted pad ref are cut in
different places").  Matched replay arms on ONE tree (census by
`harness/census.py`): HECA **16 → 10**, LEMD **1 → 1** (direct read of
`constraints.cluster_pad.pad_cluster_mismatch`: HECA 12 → 10, LEMD 3 →
2), and the owner's own T4 cluster LEFT the list — it was
`cluster_spans_pads unit:25#843/0 → building34/35/36`.  Three causes,
all at their single derivation site:

1. `_pads` cut the cluster polygon a SECOND time (the runway difference,
   `polygon_parts`) and gave each piece its own `building{N}`.  A part
   now takes ONE ref, its surplus pieces the tree's own `ref#k`.
2. `_face_map` joined on the RAW ref, so `building38` and `building38#1`
   — one pad to `publication` :597/:672 and `constraints/structures` —
   counted as two (LEMD `unit:25#1581`).  It joins on the base ref now.
3. The MINT pre-split the outline at the apt.dat airside union while the
   CENSUS split it at the PLANAR role faces — two cutters, and LEMD's T4
   cluster read as ONE 94,301 m² census piece against three minted refs.
   RULINGS 14ax already ruled the clip is `planar/overlay.airside_clip`'s;
   with that clip armed neither side pre-cuts now (with it disarmed both
   still do — 14ah's guard stands).  A piece under `[building_pad]
   min_area_m2` is also no longer judged: the mint drops it, so LEMD's 7
   m² and 3 m² slivers cannot make their building's ref a row.

**THE 10 HECA SURVIVORS ARE ONE CLASS, NAMED.**  Every one is
`cluster_spans_pads` over a NEIGHBOURING pad, and the instrument's own
per-FACE test is why: `_OWN_FACE_SHARE` asks whether a FACE is mostly
inside the cluster, so one sliver face of a big neighbouring pad puts
that whole ref on the list.  Measured: `unit:43#204` holds 94 % of
`building254`'s area and **2 %** of `building253`'s (8 faces, 4,373 m²);
`unit:43#612/0` 96 % of `building110` and **8 %** of `building107`;
`unit:43#844` 100 % of `building75` and 48 % of `building73`.  The
un-tried lever, named (the round's attempts are spent): weigh the REF's
own area inside the cluster, not one face's.  Survivors:
`unit:42#515/0`, `/2`, `unit:43#204`, `#267/0`, `#447/0`, `#612/0`,
`#687/1`, `#784/3`, `#844` and `pad_spans_clusters building281`; LEMD:
`unit:27#341/8` and `building25`.

**THE CENSUS PAIRS (matched replay arms, ONE tree, the only variable the
two `[placement]` keys).**

| | HECA OFF → ON | LEMD OFF → ON |
|---|---|---|
| ADJUDICATED | 26,608 → **26,285** (−1.2 %) | 1,371 → **1,376** (+0.4 %) |
| law-true total | 63,829 → 63,456 | 6,187 → 5,683 |
| `airside_no_step` | 7,747 → **7,487** | 455 → **445** |
| `within_shape` | 47,927 → **47,836** | 3,441 → 3,443 |
| `taxi_box` | 3,411 → **3,358** | 182 → 183 |
| `hairline_pair` | 2,749 → 2,795 (+1.7 %) | 1,882 → **1,388** |
| `pad_cluster_mismatch` | 16 → **10** | 1 → 1 |
| `pad_airside_weld` | 2 → **7** | 1 → **2** |
| `zone_on_pavement` | 0 → **0** | 0 → **0** |

WORSE BY MORE THAN 5 %, each named: HECA `pad_airside_weld` 2 → 7 and
`plane_gradient` 8 → 13 and `strip_seam_tear` 28 → 30; LEMD
`pad_airside_weld` 1 → 2, `strip_longitudinal` 4 → 5 and
`strip_transverse` 83 → 87.  `pad_airside_weld` is the bar's own
"0 new" clause and it is MISSED on both airports.

**THE AIRSIDE STILL MOVES, AND BY HOW MUCH.**  `airside_value_delta`
(canonical identity join, solve-owned frame, roles ∩
`law.tables.rolled_on_roles`) between the two HECA arms: **5,915**
airside vertices moved > 0.02 m, worst **3.61 m**; the RUNWAY **231**,
worst **0.140 m** (r5's shipped arm, a different frame: 9,573 and 885 /
0.390 m).  §16g (10) (5)'s bar is 0 and is MISSED; the runway is within
a tenth of a metre of quiet.

**THE CLOSING BUILD** — `build_airport.py LEMD --tag v2padqpLEMD2` with
both keys armed, on merged main: rc 0, **346.3 s**, ways 1,048, nodes
20,304, status `optimal`, `body_sha e5d30cf207a8`, artifact ledger
`50546224d866`, v2-verify 1,633 rows, and verbatim `[harness] shared
repo UNCHANGED by this build (full-surface before/after snapshot) — no
side-effect mutation`.  Its object stage reports the pad law defeating a
spurious pit at the garage: `refused basin:1 … 96 % under its own
objects' solids … a BASEMENT, not a pit: the terrain there is the
building's pad (building45) under the pad law`.  Suite **1,579 passed /
1 skipped** by FAILED lines.

**SHIPS OFF: `pad_from_cluster = false`, `pad_airside_clip = false`.**
Bar 6 is "flipped only if EVERY bar holds".  Three do not: the airside
moves (5,915 / 3.61 m), `pad_airside_weld` gains 5 rows at HECA and 1 at
LEMD, and `pad_cluster_mismatch` is 10 / 1 rather than 0.  The probe —
the reason 14bk shipped it OFF — is the bar that MOVED: under the
converged solver the pads-ON far field is nothing at all, or 16 vertices
at 0.10 m once the clip moves to the arrangement.  The owner's site is
fixed on the armed arm and the numbers above are the read it is
adjudicated on.

### §16g (10) (11) RULED ON THE MEASUREMENT (lane v2padqp r1 2039b3c0; Fable 2026-09-15; RULINGS 2026-09-15z) — the garage seats on its cluster's pad; the keys stay OFF until the AIRSIDE MOVEMENT is attributed

The garage (40.4892214, −3.5944287) with the keys armed: INSIDE
`building45` (the walled cluster `unit:25#843`'s own outline — 421,940
m², 761 walled bodies; the chain rule was never widened), one level
615.35 over the terminal and garage together, z − DEM +4.33 m of fill,
no short-edge step; the spurious basement pit refused as "a BASEMENT,
not a pit".  Three defects fixed at their derivation sites: `_pads`
re-cutting one cluster piece into separate `building{N}` refs (one ref
+ `ref#k` now); `_face_map` joining on the raw ref (`building38` vs
`building38#1`); the mint (apt.dat union) and the census (planar role
faces) cutting the airside differently.  `pad_cluster_mismatch` HECA
16 → 10, LEMD 1 → 1; the ten survivors are ONE class — `_OWN_FACE_SHARE`
is a per-FACE test, one sliver face of a neighbour lists the whole ref
(2 % / 8 % shares) — the untried lever: weigh the REF's area.  The one-
vertex probe with the pads as r5 left them: 0 of 32,262 moved > 0.02 m
— 14bk's far-field mover is GONE under §20c; with the clip moved to the
arrangement 16 vertices beyond 500 m, worst 0.103 m — the residual far
field is the pad/airside rim geometry, not the solver.

**MISSED, and why the keys stay OFF:** the AIRSIDE moved between the
OFF and ON arms — 5,915 vertices > 0.02 m, worst 3.61 m; runway 231,
worst 0.140 m (§16g (10) (5): a derived pad never takes airside ground;
airside is king) — r5's arm read 9,573 / 885 at 0.390 m, so this lane
halved it and did not close it; `pad_airside_weld` 2 → 7 HECA, 1 → 2
LEMD; HECA `plane_gradient` 8 → 13, `strip_seam_tear` 28 → 30; LEMD
`strip_transverse` 83 → 87.  RULED (r2): (a) ATTRIBUTE the airside
movement interventionally — `--why-at` on the worst airside mover
(3.61 m) and on the worst runway mover (0.140 m): which row set on the
ON arm reaches the airside (a pad weld row with the wrong direction? a
zone re-cut? the arrangement clip changing airside cells?) — the pad's
rows must be ONE-WAY toward the pad; an airside vertex that moves
because a pad exists is a defect at the row that moved it; (b) the
ref-area lever for the ten survivors; (c) the seven welds named.  The
keys flip ON only when airside movement is 0 (> 0.02 m) and the welds
are 0 new; the object-stage FLOAT at the garage (body zero vs its own
ground) is read on the next app build, not in the harness.

### §16g (10) (11) MEASURED, ROUND 2 (lane `v2padqp` r2, 2026-09-15; branch `claude/v2padqp`)

**(1) THE AIRSIDE MOVEMENT IS ATTRIBUTED, AND IT IS NOT A ROW OF THE PAD
LAW.**  `--why-at` on HECA's worst airside mover between the pads-OFF and
pads-ON arms (+3.610 m at 30.11038632205, 31.39574702991, roles `apron` +
`building`) named exactly ONE binding row on it: **the pad's own cap-0
plate**, `pads cap 0.00 % × 8.7 m`, dual **3.61**, over a vertex the
apron owns.  So the plate was pointed the one lawful way (below) and the
site re-read: the new worst mover (+3.28 m) carries **no binding pad row
at all** — its chain ends on an apron vertex `FREE: no binding row blocks
it … held by bending alone`.  The decisive count, by node identity
between the two emitted patches: of the **5,868** airside vertices that
moved, only **268** are SHARED with a pad at all; **5,600 touch no pad**
and still move up to 2.77 m.

**THE CHANNEL IS THE ARRANGEMENT CLIP, MEASURED INTERVENTIONALLY.**  A
third arm with `pad_airside_clip = true` and `pad_from_cluster = FALSE` —
the clip alone, no derived pad anywhere — against the same OFF arm:

| arm (vs pads-OFF) | airside moved > 0.02 m | worst | runway | runway worst |
|---|---|---|---|---|
| **clip ALONE** | **4,474** | **1.39 m** | 17 | 0.100 m |
| clip + derived pads | 5,973 | 3.28 m | 189 | 0.200 m |

Three quarters of the moved vertices and nearly half the worst move are
bought by the CLIP, which re-cuts the airside faces around every pad
(1,082 solve-owned airside vertices gone, 235 new) — a different
arrangement, a different triangulation, a different smoothness optimum
over the whole field.  14as (i) armed the clip to make the airside
REGION independent of the pads (area-null, and it is); the airside
VERTEX SET is not, and that is what moves the surface.  §16g (10) (5)'s
bar of 0 cannot be reached at the pad's rows: it is a question about
whether the airside may be re-noded by a pad at all, and that is the
spec's to rule, not this lane's.

**WHAT THE ROW-LEVEL FIX DID BUY, ON THE SHIPPED SURFACE.**  A plate pair
with ONE end on airside is now priced ONE-WAY toward the pad (new head
`structures.building_pad flat airside-led`, in `one_way_rulings` and
`pad_flat_rulings` — same plate, same price, one lawful direction); a
pair the airside owns at BOTH ends is withdrawn; a pad with fewer than
three vertices of its OWN keeps its two-sided plate (three points make a
plane — the pad-in-an-apron class, measured on the §30 (4) twin at 0.86 m
when the pairs were withdrawn anyway), and a cluster's cross-links are
built from own vertices.  Measured on the PADS-OFF arm, the same capture,
the only variable this code: ADJUDICATED **26,608 → 25,521 (−4.1 %)**,
`airside_no_step` 7,747 → **7,344**, `taxi_box` 3,411 → **3,169**,
`within_shape` 47,927 → **47,201**, `transverse` −5 — the shipped
fallback pads stop dragging the apron too.  The price is
`pad_airside_weld` **2 → 8**: where the pad now yields instead of pulling,
the census says so, which is the family's whole job (14ai).

**(2) `pad_airside_weld`: NO NEW ROW.**  HECA OFF → ON **8 → 7**
(r1: 2 → 7); LEMD **2 → 3**.  The bar's "0 new" holds at HECA; LEMD's one
row is `building7`-class (a pad that cannot reach its non-apron airside
edge) and is named in the census rows.

**(3) THE REF-AREA LEVER CLOSES THE MISMATCH.**  `_OWN_FACE_SHARE` now
asks the share of the REF's whole area, not one face's — a pad IS a ref,
and asked per face one sliver face of a neighbour listed the whole ref.
**HECA `pad_cluster_mismatch` 10 → 0** (pads OFF, the shipped fallback
derivation: **15**), LEMD 2 → **1** (`unit:27#341/8` over `building25` /
`building26`, the OldTerminal chain).  (10)'s own bar — "pads must match
building clusters … exactly" — is MET at HECA with the pads derived and
MISSED by the shipped derivation.

**(4) THE CENSUS PAIRS (matched replay arms, one tree, final code).**

| | HECA OFF → ON | LEMD OFF → ON |
|---|---|---|
| ADJUDICATED | 25,521 → 25,612 (+0.4 %) | 2,118 → **1,377** (−35 %) |
| law-true | 62,456 → 62,592 | 6,911 → **5,606** |
| `pad_cluster_mismatch` | 15 → **0** | 0 → 1 |
| `pad_airside_weld` | 8 → **7** | 2 → 3 |
| `airside_no_step` | 7,344 → **7,280** | 444 → **440** |
| `transverse` | 1,315 → **1,277** | 117 → **109** |
| `frontage_near_miss` | 28 → **20** | 8 → **2** |
| `plane_gradient` | 8 → 12 | 0 → 0 |
| `strip_seam_tear` | 28 → **28** | 0 → 0 |
| `hairline_pair` | 2,749 → 2,795 | 1,882 → **1,388** |

`strip_seam_tear` is CLOSED (r1's 28 → 30 is gone: +0).  `plane_gradient`
8 → 12 is the residual, named: four more rows on the derived pads'
own planes, the class r1 also carried.  LEMD `strip_longitudinal` 4 → 5,
`strip_arc` 7 → 8 and `strip_transverse` 84 → 87 are the same order.

**(5) THE KEYS STAY FALSE.**  Deliverable (1)'s bar — airside movement 0
— is MISSED (HECA 5,973 / 3.28 m, runway 189 / 0.200 m; LEMD 1,651 /
2.36 m, runway 43 / 0.070 m) and the attribution says why it cannot be
met by a pad row: three quarters of it is the arrangement clip's own
re-noding.  Deliverable (2) is MET at HECA and +1 at LEMD; (3) is MET at
HECA.  Suite **1,613 passed / 1 skipped**, 0 FAILED.  No closing build:
the keys did not flip.  The owner's garage still seats on `building45`
(93-node face, median **615.09**, z − DEM **+4.06 m** of fill) on the
armed arm.

### §16g (10) (12) THE ARRANGEMENT CLIP PRESERVES THE AIRSIDE VERTEX SET — A PAD IS CLIPPED BY THE AIRSIDE CELLS, THE AIRSIDE CELLS ARE NEVER RE-CUT BY A PAD (Fable 2026-09-16; RULINGS 2026-09-16b) — lane `v2padclip`

**The measurement (v2padqp r2, RULINGS 15ah).**  With `pad_airside_clip`
alone (no derived pads) the airside moved 4,474 vertices (worst 1.39 m,
runway 17 / 0.100 m) against the pads-OFF arm — three quarters of the
movement the pad line was held for: the arrangement clip DELETES 1,082
solve-owned airside vertices and MINTS 235, i.e. it re-nodes the
airside faces.  14as (i) made the airside REGION pad-independent; its
VERTEX SET is not.  The one binding pad row found (the cap-0 plate over
an apron vertex) was pointed one-way in r2 and is not the cause.

**RULED.**  (1) The airside cells' geometry and vertex set are computed
BEFORE any pad exists and are NEVER modified by the pad stage: a pad
polygon is the cluster outline MINUS the airside union, clipped BY the
airside cells (their existing edges become the pad's boundary where
they touch), and the pad's own vertices are new vertices on the
pad's side of that boundary; where a pad edge meets an airside edge
the pad takes the airside's existing boundary vertices (shared by
identity, §16g (10) (6) the weld) and adds none to the airside cell.
(2) An airside vertex present in the pads-OFF arm is present, with the
same id/position, in the pads-ON arm; the census family
`pad_airside_renode` counts airside vertices deleted or minted by the
pad stage (bar 0).  (3) With (1)–(2) in force the flag is re-measured
(the v2padqp bars): airside moved > 0.02 m between the OFF and ON arms
→ 0 at HECA and LEMD (named survivors), `pad_airside_weld` 0 new,
mismatch HECA 0 (ref-area share), LEMD 1 named, the far-field probe ≤
0.02 m; then `pad_from_cluster` + `pad_airside_clip` ship TRUE and the
T4 garage (40.4892214, −3.5944287) seats on `building45` at one level
with the fill under it (r2: 615.09, +4.06 m).  Consumer census first
(every reader of the arrangement / the airside cells / the pad polygon
/ `_face_map` / the census cutters — the two cutters r1 aligned).

### §16g (10) (12) MEASURED (lane `v2padclip`, 2026-09-16; branch `claude/v2padclip`, base main `7f80dc71`)

**THE CONSUMER CENSUS (RULINGS 2026-08-30l), BEFORE ANY CONSUMER IS
EDITED.**  The affected geometry is THE ARRANGEMENT'S NODED VERTEX SET —
not a new region, an exemption or a claim, which is why the table below
is short and its rows are all one seam: `planar/overlay.build_arrangement`
is the ONLY producer of it (`grep build_arrangement src` = one call site,
`planar/build.build`:161) and every other pass in the engine reads it
THROUGH `PlanarMap`.  So the census asks, per reader: *what does this
pass read that a change to WHICH VERTICES EXIST can move?*

| # | reader | what it reads of the arrangement | ruled interaction |
|---|---|---|---|
| 1 | `planar/build.build` :198-240 | `arr.faces` → `Face.ring/holes`, `vertex()` (exact-XY dedupe → the WELD: one coordinate = one unknown), `arr.regions` → `edge_kind_of_ref` / `quay_refs`, `arr.sources` → `_breaklines`, `arr.seam_bands` → `_seam_vertices` | THE one consumer. The airside faces it is handed must be the pad-free ones; the pad faces are additional faces that SHARE the airside's own coordinates and mint none of their own inside the airside union. Nothing else in the file changes. |
| 2 | `solve/design_roles.airside_stage_vertices` (§20b stage 1) | every vertex of an `airside_stage_roles` face | the stage-1 column set. A minted airside vertex is a NEW UNKNOWN in the airside problem and a deleted one removes a row — this is the channel 15ah attributed the 4,474-vertex far field to. Bar `pad_airside_renode` = 0 closes it BY CONSTRUCTION, not by a veto here. |
| 3 | `constraints/pads._pad_polys` / `_pad_groups` / `pad_flats` / `pad_shared` / `frontage_contacts` | pad FACE rings out of `PlanarMap` (`vw.rings`, `vw.holes`) | reads the pad's own face, never the airside's. The one-way plate at airside pairs (r2) is priced on SHARED vertices — preserved: the pad still takes the airside's own boundary vertices by identity (12) (1). UNCHANGED. |
| 4 | `constraints/pads._pavement_geoms` / `_pavement_faces` | airside pavement face rings | reads airside face geometry. It gets FEWER vertices (the pad-minted ones stop existing) and the same polygon: the clip is area-null (14as (i)), so every proximity read it does is unchanged in kind. |
| 5 | `constraints/cluster_pad._face_map` :227 / `plane_groups` / `pad_cluster_mismatch` | pad faces by `_base_ref` (r2's join) + `rolled_on_roles` faces for the cluster/apron reach | the CENSUS CUTTER. r1 aligned it with the mint (one ref per cluster piece, `ref#k` for the surplus); r2 made its share test the REF's own area. (12) does not move either cutter — it moves WHICH VERTICES the faces carry. UNCHANGED. |
| 6 | `constraints/pad_relief` / `pad_frontage_gs` | `_pad_polys` + `_pavement_geoms` | as 3 / 4. UNCHANGED. |
| 7 | `classify/roles.classify` :244-251 | subtracts the pad union from the airside REGION when `pad_airside_clip` is OFF | region-level, pre-arrangement. (12) changes nothing here; the key still selects the region-level behaviour. |
| 8 | `classify/evidence._pads` / `_cluster_pads` :499-518 | mints the pad polygons; pre-splits the outline at the apt.dat airside union only when the arrangement clip is DISARMED | THE MINT. (12) does not re-cut it. The guard at `_mint_airside` stands. |
| 9 | `planar/shapes.build_shapes`, `planar/zones.zone_regions`, `emit/*`, `verify/*` | `PlanarMap` faces/vertices | all downstream of 1; they read whatever the arrangement produced. None of them can distinguish a pad-minted airside vertex from a real one, which is exactly why the trim belongs at the single derivation site (CLAUDE.md's own preference) and not in any of them. |
| 10 | `tools/check_grade.py` / `harness/census.py` | the EMITTED patch | the instrument. `pad_airside_renode` is a SIDECAR-DECLARED family (the `eat_ceiling` / `seam_pins` pattern): the arrangement publishes what the pad stage did to the airside vertex set and the census reads it. A patch with no key reads exactly as before. |

NO consumer is vetoed and no consumer is edited: the whole change is at
`planar/overlay.build_arrangement`, the single derivation site.

**THE DEFECT REPRODUCED AND ATTRIBUTED (`tools/pad_airside_arm.py`, HECA,
one tree, ONE variable `[placement] pad_airside_clip`, `pad_from_cluster`
FALSE on both arms — the clip-alone arm of 15ah).**  `[guard] shared repo
UNCHANGED`.  Airside vertices (`solve/design_roles.airside_stage_vertices`,
never a hand list): OFF **19,435** → clip ON **18,710**, **GONE 1,008,
NEW 283** (15ah's build-frame reading: 1,082 / 235).

*THE 1,008 GONE ARE NOT DELETIONS — THEY ARE MINTS THE OFF ARM MAKES.*
Every one of the leading classes is a vertex incident to an APRON AND A
BUILDING PAD at once on the OFF arm — `apron:pav1 + building:building1`
116, `apron:pav132 + building:building289` 83, `apron:pav1 +
building:building7` 67, `…building4` 67, `…building6` 63 — i.e. the
UNCLIPPED pad ring crossing the apron, which splits the apron's own
edges.  With the clip armed the pad is differenced out of the apron and
those nodes have no reason to exist.  So §16g (10) (12) (2)'s frame as
written ("an airside vertex present in the pads-OFF arm is present in the
pads-ON arm") would score the pad stage's own pollution as the defect: the
OFF arm is the POLLUTED one.  **The frame that survives measurement is the
invariance frame: the airside vertex set must be the SAME on every pad
arm, because it is a function of the airside alone** — which is (12) (1)'s
own sentence, and (2) read as a bar on either direction.  `pad_airside_
renode` is therefore counted as DELETED ∪ MINTED against the pad-free
airside, on each arm, and its bar 0 subsumes (2).

*THE 283 MINTS ARE TWO CLASSES, BOTH THE NODING'S.*  `PAD_AIRSIDE` on the
clip arm: `pads 384, clipped 59, snapped_pads 58, snapped_vertices 419,
snap_max_m 4.8, snap_too_far 75 (max 70.76 m), snap_refused_overlap 2,
snap_refused_invalid 1, kept_wholly_on_airside 8`.
(a) THE UNSNAPPED CROSSING POINT — 75 of the clip's own crossing points
stand further from a rim NODE than `pad_airside_snap_max_m`, so they split
a rim edge and mint an airside vertex that exists only because the pad
does.  The rim they snap to is `AirsideRim(air, …)`, built from the airside
REGION rings — NOT from the arrangement's own node set, which also carries
every crossing the runway sources, the zone edges and the seam bands mint
INSIDE the airside.  A pad vertex near one of those can never snap.
(b) THE GLOBAL SNAP-ROUND — the whole line set is noded in ONE
`shapely.unary_union(…, grid_size=min_distinct_spacing_m)`, and
snap-rounding is a GLOBAL operation: adding or removing ANY line can move
an unrelated vertex by up to half a cell.  Measured directly in the pair:
`NEW vertex → nearest OFF-arm airside vertex` has **min 0.500 m**, p50
2.55 m, and the matching GONE/NEW couples read as one vertex MOVED — e.g.
`apron:pav1 + service_road:route0` at (30.10639358515, 31.38950704486) on
the OFF arm and (30.10639809557, 31.38950704376) on the ON arm, the same
node 0.5 m apart.  228 of the 283 stand over 1 m from any OFF-arm airside
vertex and 106 over 5 m; only **4 of 283** lie on the OFF arm's airside
boundary at all.  **No amount of rim snapping can fix (b): while the pads
are noded in the same pass as the airside, the airside vertex set is a
function of the pad set.**  That is the mechanism (12) (1) names, and the
fix is structural — the airside is noded BEFORE the pads exist and the pad
stage may only ADD vertices outside the airside union.

**WHAT SHIPPED (12) (1), AT THE ONE DERIVATION SITE.**
`planar/overlay.build_arrangement` is now TWO PASSES over one line set,
and that split IS the rule:

* PASS A nodes everything the airside is made of — every non-pad region
  ring, the runway-profile stations, the taxi/road cut lines, the zone
  rings and the seam bands — in the same single `unary_union(...,
  grid_size=min_distinct_spacing_m)` as before.  Its node set IS the
  airside cells' vertex set, and it is a function of the airside alone.
* PASS B adds the PADS to that result.  Each pad is differenced by pass
  A's own grid-snapped airside union (`airside_union`, ONE derivation,
  read by the clip and by the re-node census alike), and the rim its
  crossing points quantise to is built over PASS A'S OWN NODES
  (`AirsideRim(..., nodes=)`), not the region ring's — measured at HECA,
  6,272 ring nodes against **8,775** arrangement ones, which is why 75
  crossing points had nothing to reach (`snap_too_far_max_m` 70.76 m).
* THE DENSIFIER MAY NOT NODE THE RIM EITHER (`_drop_rim_midpoints`):
  `ring_lines` densifies every ring at its OWN role's chord cap, so the
  `building` cap's midpoints landed on airside edges the airside cap had
  spaced differently and split them.  A pad coordinate on the rim that is
  neither one of pass A's nodes nor a vertex of the pad's own polygon is
  dropped — 24…37 per HECA arm.  The `own` test is load-bearing: dropping
  pad CORNERS collapsed the three `test_v2padlevel` fixtures whose pad
  merely touches its apron along a straight edge.
* A PAD WHOLLY ON AIRSIDE IS DROPPED, not kept.  (12) (1)'s own sentence
  is "a pad polygon is the cluster outline MINUS the airside union" and
  §16g (10) (5) already said a cluster wholly on airside pavement gets no
  pad.  It was KEPT as the §30 / 14ai pad-in-an-apron class, and MEASURED
  it was the ONLY re-node class left once the airside was noded first:
  HECA **548 of 553** minted nodes, every one STRICTLY INSIDE the airside
  union.  The four ruled twins that encoded the class are RE-FOUNDED, not
  weakened — a building that really does stand in an apron IS A HOLE in
  that apron, so `test_v2bank`'s `pad_map` and `test_constraints`'s
  `synthetic` now carry the pad as the apron cell's own hole and every
  claim they make (the weld by identity, the flat target, the 1 % hard
  ceiling, the pure-hole pad minting no level row) reads exactly as
  before.  `test_v2bank`'s pad is 40 m on a side rather than 60 because
  the HOLE ring is densified at the APRON's chord cap and a 60 m edge came
  back split at its midpoint, which cost the pin twin its own premise.

(12) (2) SHIPS AS A CENSUS FAMILY, `pad_airside_renode`, sidecar-declared
in the `eat_ceiling` / `seam_pins` shape: the arrangement publishes
`[lat, lon, "minted"|"deleted"]` per node (`pipeline/publication.
_renode_rows` off `planar/overlay.PAD_AIRSIDE`) and `check_grade` emits
one row each.  An ABSENT key means NOT MEASURED and an EMPTY list means
MEASURED ZERO — publishing `[]` either way made all four of this lane's
matched REPLAY arms read a perfect family, because a replay resumes from
a captured planar map and never builds an arrangement; `v2_solve_replay
--capture` therefore carries the arrangement's own reading in the pickle
and `--replay` restores and prints it.

### §16g (10) (12) THE NUMBERS

**(a) THE RE-NODE IS CLOSED — `renode_deleted` 0 ON EVERY ARM.**
`tools/pad_airside_arm.py` (ONE load, classify+planar twice, the airside
population read from `solve/design_roles.airside_stage_vertices`), one
tree, `[guard] shared repo UNCHANGED`:

| airport / arm | deleted | minted | on the rim | inside airside |
|---|---|---|---|---|
| HECA, shipped law (both keys false) | **0** | 40 | 5 | 35 |
| HECA, clip alone | **0** | 40 | 5 | 35 |
| HECA, clip + derived pads | **0** | 43 | 4 | 39 |
| LEMD, shipped law | **0** | 150 | 85 | 65 |
| LEMD, clip + derived pads | **0** | **32** | 9 | 23 |

Before the rule, the clip alone at HECA read **1,008 deleted / 283
minted** against the shipped arm (15ah's build frame: 1,082 / 235), and
the pad-in-an-apron class alone accounted for 553 → 40 of the minted.
THE RESIDUAL IS ONE CLASS AND IT IS NAMED: an unsnappable CROSSING POINT
(`snap_too_far`, 68 at HECA) standing on a rim segment, plus the 2–3
`snap_refused_overlap` pads whose snap is withdrawn and whose clip
polygon keeps a sliver inside the union.  The second attempt on it —
making such a crossing RETREAT off the rim by the hot-pixel band instead
of standing on it — IS REFUTED: it takes the WELD with it (09-01g /
§16g (10) (6)), and `test_v2padlevel::test_a_pad_between_two_pavements_
half_a_percent_apart_stays_flat_and_tiers_neither` read **ZERO shared
vertices** on both its frontages.  The attempts are spent.  The un-tried
lever, named: the law value `pad_airside_snap_max_m` (5.0 m), which
trades pad distortion along the rim for these nodes.

**(b) AND THE AIRSIDE STILL MOVES, WHICH IS THE ROUND'S FINDING.**
`tools/airside_value_delta.py`, HECA, solve-owned frame, the `building`
(pad) vertices excluded so the number is airside and not the pad:

| pair | moved > 0.02 m | worst | runway | runway worst |
|---|---|---|---|---|
| pads OFF → pads ON (the bar) | **6,031** | 3.09 m | 180 | 0.130 m |
| OFF → the CLIP ALONE | 4,787 | 2.06 m | 19 | 0.070 m |
| clip → clip + derived pads | 3,875 | 3.14 m | 157 | 0.110 m |
| the same pair under §20b `staged_solve` | **2,018** | 2.69 m | **3** | **0.020 m** |

15ah read OFF → ON 5,973 / 3.28 m and the clip alone 4,474 / 1.39 m on
its own tree.  **So the airside vertex set is now invariant and the
airside VALUE moves as much as it ever did** — which REFUTES 15ah's
attribution as a complete explanation.  A re-noded arrangement was real
and is now gone; it was not what moved the surface.  The interventional
arm above names what does: with the vertex set held fixed and the ONLY
variable §20b's `staged_solve`, the runway's moved set falls from **157
vertices / 0.110 m to 3 / 0.020 m** — at the elevation materiality.  The
pads' own rows reach the airside because the design problem is solved
JOINTLY; §20b stage 1 solving the airside alone and substituting it is
what freezes it.  §16g (10) (5)'s bar of 0 is therefore a question for
§20b, not for the pad law, and this lane does not re-litigate it by
narrative.

**(c) THE OWNER'S SITE IS FIXED AND READS AS r2 LEFT IT.**  The LEMD T4
garage `LEMD_OBJ-Airport_Terminal4_green-PKT4.obj` at 40.4892214,
−3.5944287, pads ON: INSIDE **`building45`**, a **93-node** face, way
−10991, altitudes **615.05 … 615.11** — ONE LEVEL, spread 0.06 m — with
no step over a short edge.  Pads OFF, the shipped law: **0 ring groups
cover the point** (15h's "the pad polygon ends 55.28 m short").

**(d) THE CENSUS PAIRS (matched replay arms, ONE tree, the only variable
the two `[placement]` keys; `harness/census.py`).**

| | HECA OFF → ON | LEMD OFF → ON |
|---|---|---|
| ADJUDICATED | 19,456 → **18,686** (−4.0 %) | 2,121 → **1,004** (−53 %) |
| law-true | 61,185 → 59,755 | 6,479 → 4,865 |
| `pad_cluster_mismatch` | 15 → **0** | 0 → 1 |
| `pad_airside_weld` | 9 → **8** | 2 → 3 |
| `airside_no_step` | 5,457 → **5,172** | 335 → **320** |
| `within_shape` | 48,707 → **47,901** | 4,253 → **3,025** |
| `taxi_box` | 2,679 → **2,481** | 135 → **131** |
| `mid_edge_step` | 21 → **2** | — |
| `vertex_to_edge_step` | 7 → **0** | — |
| `frontage_near_miss` | 47 → **21** | 14 → **3** |
| `hairline_pair` | 2,836 → **2,792** | 1,642 → **1,287** |
| `transverse` | 1,002 → **978** | 39 → **34** |

WORSE BY MORE THAN 5 %, each named: HECA `plane_gradient` 9 → 14 and
`strip_seam_tear` 28 → 33 and `strip_longitudinal` 3 → 4; LEMD
`pad_cluster_mismatch` 0 → 1 (`unit:27#341/8`-class, r2's own named
survivor), `pad_airside_weld` 2 → 3, `strip_longitudinal` 1 → 2 and
`raoa` 0 → 1.  `pad_airside_weld` HECA 9 → 8 MEETS the "0 new" clause;
LEMD's +1 is the `building7` class r2 named.

**SHIPS OFF: `pad_from_cluster = false`, `pad_airside_clip = false`.**
Bar 6 is "flipped only if EVERY bar holds".  The re-node bar HOLDS on
`deleted` and is missed on `minted` by one named class (HECA 40/43, LEMD
32); the AIRSIDE MOVEMENT bar is missed by 6,031 vertices and is now
attributed, interventionally, to §20b rather than to the pad law.  No
closing airport build: the keys did not flip.
### §16g (10) (12) MEASURED AND AMENDED (lane v2padclip r1 104c7b43; Fable 2026-09-16; RULINGS 2026-09-16r) — the vertex set is invariant now; the VALUE still moves because the problem is solved jointly → §20b staged solve ON under §20c; (2) reworded to the invariance reading

**Measured.**  `build_arrangement` in two passes (A: every non-pad line;
B: pads on that result), `airside_clip` un-gated and dropping a pad
wholly on airside, `AirsideRim` noded on the arrangement (HECA 6,272
ring nodes → 8,775): `pad_airside_renode` deleted **0** on every arm
(was 1,008 at HECA with the clip alone), minted 40–43 HECA / 32 LEMD
(one class: an unsnappable crossing, `snap_too_far` 68 — the untried
lever is `pad_airside_snap_max_m` 5.0; RETREATING the point took the
weld with it and is refuted).  The owner's garage: inside `building45`,
615.05…615.11, one level.  `pad_cluster_mismatch` HECA 15 → 0;
`pad_airside_weld` HECA 9 → 8.  AND the airside VALUE still moves OFF →
ON: HECA 6,031 vertices, worst 3.09 m, runway 180 / 0.130 m — as much
as 15ah read.  The interventional arm (clip+pads, the ONLY variable
`staged_solve`): runway 157 / 0.110 m → **3 / 0.020 m**, airside 3,875
→ 2,018.  The pads' rows reach the airside because the design problem
is solved JOINTLY; the re-noding of 15ah was real, is closed, and was
not what moved the surface.

**RULED.**  (a) (12) (2) is reworded to the invariance reading the
lane implemented: airside vertices deleted ∪ minted by the pad stage,
measured against the pad-free airside per arm, = 0 — the OFF arm was
the polluted one and cannot be the reference.  (b) §16g (10) (5)'s
bar (a derived pad never takes airside ground) is met by §20b, not by a
pad row: `staged_solve = true` ships with `solver = "qp"` — stage 1
(AIRSIDE) SETTLES under §20c (15b: 0 / 174,500 hard, worst 0.0200 m),
stage 2 conforms with the airside FIXED.  r2 measures the remaining
2,018 movers under the staged solve interventionally (`--why-at`: which
stage, which rows — a stage-2 substitution touching a shared weld
vertex is a §20b (2) defect) with the bar 0 > 0.02 m on solve-owned
airside, HECA and LEMD; then `pad_from_cluster`, `pad_airside_clip` and
`staged_solve` ship TRUE together if every bar holds.  (c) The last
piece of (12) (1): `classify/roles.classify` (:244–251) still subtracts
the pad union from the airside REGION when the clip is off — the `if`
goes (v2shoulderband r2 is merged; the file is free).  (d) Before the
merge of r1, the SHIPPED arm's identity: the two-pass arrangement and
the un-gated clip run on the OFF arm too — HECA and LEMD OFF-arm replay
pairs main-before vs branch must be byte-identical or each difference
named (the lane reported OFF → ON pairs only).

### §16g (10) (12) MEASURED, ROUND 2 (lane `v2padclip` r2, 2026-09-16; branch `claude/v2padclip`, base main `1bc93833` then `782a50d6`)

**(1) THE SHIPPED ARM IS NOT BYTE-IDENTICAL, AND r1 ALONE MADE IT WORSE —
WHICH IS WHY (12) (1) (c) IS NOT OPTIONAL.**  OFF-arm (both keys false)
matched replay pairs, base main `1bc93833` cut into its own ritual
worktree against the branch, one variable (the lane's code):

| | HECA base → r1 | HECA base → r1+(c) | LEMD base → r1 | LEMD base → r1+(c) |
|---|---|---|---|---|
| ADJUDICATED | 19,032 → **19,826** (+4.2 %) | 19,032 → **19,076** (+0.2 %) | 1,749 → **2,159** (+23 %) | 1,749 → **986** (−44 %) |
| law-true | 59,215 → 60,506 | 59,215 → **59,114** | 6,257 → 6,630 | 6,257 → **4,850** |
| `airside_no_step` | 5,171 → 5,421 | 5,171 → **5,138** | 322 → 334 | 322 → **321** |
| `hairline_pair` | 2,767 → 2,808 | 2,767 → **2,230** | 1,819 → 1,670 | 1,819 → **1,272** |
| `taxi_box` | 2,511 → 2,654 | 2,511 → **2,511** | 119 → 127 | 119 → 122 |
| `frontage_near_miss` | 29 → 47 | 29 → **27** | 8 → 14 | 8 → **0** |
| `pad_airside_weld` | 8 → 9 | 8 → **8** | 2 → 2 | 2 → **1** |

THE MECHANISM, NAMED: with the arrangement clip un-gated (r1) and
`classify/roles`'s `if` still standing, the pad was CUT TWICE on the
shipped arm — once out of the airside REGION at classify, then again at
the arrangement, where the rim snap moved **1,700 pad vertices** (HECA,
`snapped_vertices`).  Neither cut is wrong; making both is.  With (12)
(1) (c) landed there is ONE cutter and it is the arrangement's, and the
shipped arm comes back to parity at HECA and materially better at LEMD.
The surface still CHANGES — the airside value moves 5,961 (HECA, worst
2.42 m, runway 60 / 0.090 m) and 1,286 (LEMD, worst 2.22 m, runway 1 /
0.020 m) — because the airside region is no longer a function of the
pads, which is a DEFECT FIXED and not a free change: it is the last
clause of (12) (1).  `pad_cluster_mismatch` and `strip_seam_tear` are
unmoved; the named regressions are HECA `within_shape` +479,
`mid_edge_step` 13 → 21, `road_cross_section` +11, `vertex_to_edge_step`
2 → 4 and LEMD `taxi_box` +3, `strip_longitudinal` 1 → 2.

**(2) (12) (1) (c) CLOSES THE AIRSIDE REGION.**  `classify/roles.classify`
no longer differences the airside region by `ev.pad_union` at all (the
key kept its other job, the mint's pre-split guard).  MEASURED at LEMD
(`tools/pad_airside_arm.py`, OFF vs ON): **apron faces 106 on BOTH arms**
(before: 180 vs 106); the OFF arm's `renode_minted` **150 → 12**; the
cross-arm airside vertex set GONE/NEW **1,484 / 254 → 23 / 43**.

**(3) §20b UNDER §20c — THE STAGED ARMS, AND THE BAR IS STILL MISSED.**
`solver = "qp"` (the shipped default since 15b) with `--design-weight
staged_solve=1`, OFF → ON, solve-owned frame, pad vertices excluded:

| | moved > 0.02 m | worst | runway | runway worst |
|---|---|---|---|---|
| HECA unstaged | 2,230 … (r1 frame 3,875) | — | — | — |
| **HECA staged** | **2,230** | 2.68 m | **2** | **0.020 m** |
| **LEMD staged** | **485** | 0.36 m | **0** | — |

The RUNWAY bar is MET (LEMD 0; HECA 2 vertices AT the 0.02 m elevation
materiality — PASS-with-residual, CLAUDE.md convergence guard (a)).  The
solve-owned bar of 0 is MISSED on both.

**AND IT IS NOT A §20b (2) DEFECT — THE INTERVENTIONAL ARM SAYS SO.**
`--why-at` on HECA's worst staged mover (+2.68 m at 30.12612886558,
31.41825773893, `v13336[apron#511,building#547]`) names `pads` (7 rows,
Σ|dual| 112.54) and `pad_frontage_level` (1 row) as its binding rows and
a 15-hop chain to the 23R threshold pin whose dz is dominated by
`apron_preference +17.81`, `apron_edge_portion +3.85`, `no_step_pairs
+3.46` and `apron_within_shape +2.18` — the airside's OWN families —
against `pads +0.04` and `pad_frontage_level +0.84`.  So the third arm:
the SAME staged pair with EVERY pad generator dropped (`--drop-generator
pads --drop-generator pad_level --drop-generator pad_frontage_level`),
which is a problem with no pad row anywhere:

| HECA staged, OFF → ON | moved | worst | runway |
|---|---|---|---|
| all rows | 2,230 | 2.68 m | 2 / 0.020 m |
| **every pad generator dropped** | **1,544** | **2.00 m** | **0** |

**69 % of the movement survives the deletion of every pad row**, at the
same coordinate.  The pads' ROWS are 31 % of it; the rest is the pads'
PRESENCE — extra faces in the sheet, extra columns in one problem, and
the ground the pad occupies no longer carrying the zone/strip rows it
would otherwise carry.  §20b (1b) is doing its job (`conforming_rulings`
already refuses every pad ruling in stage 1 even where every column is
airside), stage 2 substitutes the airside as constants, and NO stage-2
substitution touches a shared weld vertex it should not.  There is no
defect at the substitution site, `solve/design*.py` is untouched, and
the remaining movement is not reachable by a row-level fix.

**(4) THE STAGED SOLVE ALONE CHANGES THE SHIPPED SURFACE, NAMED.**
OFF arm, the only variable `staged_solve`: HECA ADJUDICATED 19,076 →
**18,346** (−3.8 %), law-true −1,081, `pad_airside_weld` 8 → **18**;
LEMD ADJUDICATED 986 → **1,005** (+1.9 %), law-true +266,
`airside_no_step` 321 → **292**.

**(5) THE REMAINING BARS.**  Staged OFF → ON census: HECA ADJUDICATED
18,346 → 19,026 (+3.7 %), `pad_cluster_mismatch` **15 → 0** (MET),
`pad_airside_weld` 18 → 19 (+1, MISSED), `hairline_pair` 2,230 → 2,781;
LEMD 1,005 → 1,053 (+4.8 %), mismatch 0 → 1 (`unit:27#341/8`, r2's own
named survivor), weld 2 → 2 (MET).  THE ONE-VERTEX PROBE IS MET AND IS
THE ROUND'S BEST NUMBER: on the pads-ON staged arm, one 0.30 m ceiling at
30.1279552,31.403143 moves **0 of 32,575 vertices by more than 0.02 m**,
max 0.0167 m over the whole field, **nothing beyond 250 m**, the hard set
27 → 27 under the perturbation.

**SHIPS OFF: `pad_from_cluster = false`, `pad_airside_clip = false`,
`staged_solve = false`.**  16r (b) flips the three together only if every
bar holds; the solve-owned airside bar is missed at both airports and the
weld gains one row at HECA.  No LEMD airport-path build.  Suite **1,787
passed / 1 skipped / 1 xpassed**, 0 FAILED, after merging the peer's
§45 channel work (`782a50d6`; both census families kept, additively).

## Spec (object-placement) §17

## §17 THE COCKPIT FRAME, object stage (owner RULINGS 2026-09-12x/12y; design-surface-spec §31)

A body's float, burial, seam or step is CRITICAL when it exceeds 0.5 m (`[cockpit]
visual_m`) and stands where a pilot looks — inside the boundary at taxi scale, or in
the approach corridor; under 0.5 m it is a REPORT. An object never moves the aircraft
(RULINGS 2026-09-12ao): a body standing ON rolled-on pavement is judged at the VISUAL
threshold 0.5 m at its feet — a pilot taxis past it at metres — and its 0.05 m
reading is a REPORT (the first wording put it at the motion threshold; measured on
the 1.0.320 frame that priced 7,124 feet, 6× `split_tol_m`'s own admission). The torn-seam census, the §15/§16 floats and the refusal set
are printed in that frame first (lane `v2cockpit`): CRITICAL by count and worst
coordinate, then REPORT. `split_tol_m` 0.3 stays the CUT tolerance (a partition
choice), not an acceptance.

### §17 (2) THE MOTION READING, and the median foot on pavement (owner RULINGS 2026-09-12am (2); lane `v2objmotion`)

12ad/12ak said the object stage "cannot read motion — no pavement role per body".
That was one missing reading, and it is now taken.

1. **THE ROLE UNDER A FOOT.** The design surface answers `surface(lat, lon)`; a
   SIBLING of it, built from the SAME parsed `<ICAO>.graded.json`, answers what the
   face there IS — `airport/placement_boxes.GradedRoles` /
   `graded_roles_from_doc`, the senior face at the point by `precedence.toml`'s
   authority order (12ak's own answer for a value two faces share), over a 55 m grid
   of the faces' boxes. Never a second parser: `pads_rims_from_graded_doc` reads the
   same dict, and the caller parses once. It rides the SAMPLER
   (`surface.roles` / `surface.rolled_on`, beside `surface.many`), so the shipped
   engine path (`engine_v2._place_objects`), the dry run
   (`tools/obj8_split_report.py`) and the timing replay all attach the same pair and
   no pass between them grows an argument.
2. **CRITICAL MOTION.** For every WRITTEN body, over its ground-contact feet in the
   foot band (§7's own scope): a body with at least one foot on a ROLLED-ON face
   (`law.tables.rolled_on_roles`) is ON PAVEMENT, and at each such foot
   `surface(foot) − (surface(anchor) + y_foot − y_zero)` — §7's own expression,
   `placement_motion.foot_float`, ONE implementation for both instruments — over
   `[cockpit] motion_step_m` 0.05 m is CRITICAL MOTION, named with resource, foot
   coordinate, face role and SIGN. The count of bodies on pavement is printed with
   it. A BASIN body is EXEMPT and counted apart (§14 (2) / 11al: its zero is the rim
   and its floor feet are authored below it by construction — read as motion they
   were LEMD's entire worst ten, +7.69 m "on the apron").
3. **A BODY WHOSE EVERY FOOT STANDS ON ROLLED-ON PAVEMENT KEEPS THE MEDIAN.** 11e
   (2)'s low-side foot buys zero float at the low corner and pays the body's whole
   relief as float at the high one. Where the aircraft rolls the bar is 0.05 m and
   the pavement is graded flat to 1.5 %, so the relief is small and is SHARED. Off
   pavement 11e (2) stands unchanged, and a body with no roles reading takes the low
   side (no reading is no evidence). §10's line-object stations keep their own
   mid-foot anchor.

**MEASURED** (the 1.0.320 LEMD frame — rebake plan + `LEMD.graded.json`,
`--admit-skipped` on the live pack read-only, write half into an APFS clone, the
shared-repo guard armed and `shared repo UNCHANGED` on every run; OTHH the same).

*The cockpit block, LEMD, before the anchor rule*: 493 of 2,153 written bodies stand
on rolled-on pavement (11,540 of 65,460 feet); CRITICAL MOTION **7,124 feet on 399
bodies** (4,265 buried / 2,859 floating; by size 1,792 in 0.05–0.1, 2,620 in 0.1–0.3,
2,347 in 0.3–1, **365 over 1 m**; by role apron 6,009, cross_connector 622, junction
246, secondary_parallel 131, stub 91, primary_parallel 25; what the EYE reads at those
feet, over 0.5 m: floating 613, buried 1,318). ATTRIBUTION of the mass, in one table:
**4,454 feet** on bodies anchored at the LOW-SIDE foot, 1,478 on §16c-bound bodies,
1,127 on bodies already at the generic median (`split_tol_m` 0.3 admits six times the
motion threshold), 66 on §10 line-object stations. The worst ten before the basin
exemption were ten pit bodies (`Ground-FSX-LEMD85/LEMD03`, +7.69 … +6.71 m) — the law,
not the defect; after it they are `Terminal4sBlue-LEMDblast__b1` (a blast-fence
segment, +7.18 / +7.14), `Terminal4sBlue-STRT4__b1` (+5.08), `OldTerminal_FSX-LEMD54__b0`
(+2.41), `Terminal4SAT_green-STRT4__b1` (a line station, −2.01).

*After §17 (3)*, matched arms on that frame: CRITICAL MOTION **7,124 → 6,635 feet**
(399 → 407 bodies: the median spreads a body's excursion, so more feet cross 0.05 while
the peak halves), **over 1 m 365 → 264**, over 0.5 m FLOATING 613 → 561 and BURIED
1,318 → 1,067 — both signs improve, so the rule does not buy a motion count with a
visible hovering object. §7's whole-pack histogram: `< 0.3 m` 44,926 → 45,176,
`0.3–1` 16,592 → 16,365, `1–3` 3,329 → 3,231, `> 3` 577 → 575. Low-side anchors 700 →
547. **Bars**: torn seams outside line/arc pieces **0**, single-component resources in
≥ 2 files **0**, §15 carried float **0**, round trip OK, files 2,148 → **2,142**, plan
stage (graded, 3 runs) 9.75 / 9.82 / 9.75 → 10.24 / 10.26 / 10.31 s, mean **10.27 s**
(bar ≤ 10.3). The named sites HOLD: `green-TEJ3` (all five placements), `green-STRT4`
(the deck, all 19 bodies), `HANG3` (b0 +1.29, b1 +1.45, low-side kept — its feet are
not all on pavement) byte-identical between the arms; `Terminal4_48` same three bodies
on the same carriers, b0's zero 616.46 → 616.48; the gate-5 `Taxisigns-SENRG` bodies
unchanged in worst foot. MISSED and reported: §16b's carried-piece own-ground float
**117 → 123** (a carrier's zero moved under six carried pieces) — a bar already red on
this frame (117 on main), moved 5 % the wrong way.

*OTHH*, same instrument under the guard: 188 of 1,671 bodies on pavement; CRITICAL
MOTION **6,234 → 3,877 feet** on **113 → 103** bodies (buried 1,279 → 1,512, floating
4,955 → 2,365; over 1 m 24 → 26); §15 carried float 0, §16b own-ground 163 unchanged,
files 1,337 → 1,341, `shared repo UNCHANGED`.

*Refuted here, deleted*: nothing — the one mechanism this round tested (the median
foot) is adopted on the numbers above. Two INSTRUMENT defects found and fixed in
passing: `tools/v2_rebake_replay.py plan` had been dead since 12j/12s (it imported
`RebakePlan` from `emit.rebake` and read the deleted `carrier_fill_min` before its own
signature dropper ran), so no lane could have timed the plan stage with it.

### §17 (3) / §16c (7) THE PAVEMENT-FOOT CLASS: the instrument, the ground-contact feet, and the bind's own ground (owner RULINGS 2026-09-12ap (A)/(B)/(C)/(E); lane `v2pavefeet`)

12ap attributed §17's > 0.5 m pavement-foot class and ruled four things.  Three
are here; the fourth is refuted below.

**(E) THE REPLAY SAMPLER HONOURS GRADED HOLES.**  A face with a HOLE says, in
the emitted document itself, that the ground inside that ring is not its own.
The dry run's design surface is a Delaunay over the emitted VERTICES and knows
none of that: it spans the ring with triangles reaching from an apron vertex
down to a trench vertex.  LEMD's apron `pav16` is cut by a hole standing at
597.7-599.5 with the `tunnel_trench` floor (590.8-594.5) inside it, and the
sampler read **592.22 m at a point whose ROLE is apron**, six metres OUTSIDE
the hole.  A simplex that CROSSES a hole ring with a step over `split_tol_m` is
now struck, and a point inside one reads the nearest vertex of that simplex ON
ITS OWN SIDE of the ring — never an interpolation across it, never a height
nothing published.  `GradedRoles` already honoured holes and is unchanged.

**(B) §17 JUDGES A BODY AT ITS GROUND-CONTACT FEET** — the in-band feet within
`[placement] split_tol_m` of its lowest (`placement_motion.ground_contact_feet`).
`[basin] contact_band_m` is shared law and does not move; a metre is a storey of
authored model, and what touches the ground is the narrower set.  BOTH sets are
sampled and the wider reading is printed beside the judged one, so the report
states its own attribution instead of a lane taking it by hand.

**(A) A §16c (7) BIND ACROSS MEMBERS HOLDS ONLY WHILE THE BOUND BODY'S OWN
GROUND AGREES.**  A FOOTED body of ANOTHER MEMBER keeps the cluster only while
its own zero stands within `bind_ground_m` (`[cockpit] visual_m` 0.5) of the
senior's; beyond it the body keeps its own anchor and is COUNTED (`bound refused
for ground N`, with the worst refused disagreement and the widest RETAINED
cluster zero-plane span).  Cross-member by construction: a refused bind is a
seam between two RESOURCES, never a cut inside a solid, and within one member
12z's veto already stands.  An ELEVATED body has no zero to test and is never
refused — it is the class (7) exists for.  The bound body's reason names ITSELF
("bound to X ... own ground +N.NN m"), and the generic rule's residual is
printed as TERRAIN SPREAD, not "authored relief": a body authored dead flat on
a 5.56 m slope carried "authored relief 5.56 m", and 12ao's own attribution
table was built on that field.

**MEASURED** (the 1.0.320 LEMD frame — rebake plan + `LEMD.graded.json`,
`--admit-skipped` on the live pack read-only, the write half into APFS clones,
`[guard] shared repo UNCHANGED` on every run; OTHH the same; main `9258a6cc`
against branch `claude/v2pavefeet`).

* **12ap's POPULATION, REPRODUCED** with the scout's per-body projection
  promoted as `obj8_split_report --motion-rows` (its second use).  On the
  POST-12aq frame the class is **247 bodies / 1,772 pavement feet over 0.5 m**
  (12ap, pre-12aq: 240 / 1,628), **96 SUNK** bodies (12ap: 76) of which **47**
  are anchored more than 2 m from their own feet (12ap: 41), median **64.9 m**,
  max **269.7 m**, **46 of the 47 by reason `§16c`** — the `TABOX`/`TABOXzwei`/
  `TAPSL` row among them.  By 12ap's own mechanism buckets the frame has
  MOVED since 12aq: whole-body OFFSET 38 bodies / 321 feet, AUTHORED foot
  relief 174 / 1,280, TERRAIN 35 / 171 — the authored-relief bucket, which is
  (B)'s, is now the mass.
* **THE TWO WORST WERE THE INSTRUMENT.**  `Terminal4sBlue-LEMDblast__b1`
  (+7.18) and `Terminal4sBlue-STRT4__b1` (−5.08) are 81 m LINE bodies whose
  ANCHORS sat in the fabricated ramp: `LEMDblast__b1`'s anchor read **592.22 m**
  on the apron and now reads **599.13**, a 6.91 m correction, and the pair is
  gone from the census.  LEMD's worst pavement foot after (E) is
  **+2.41 m** (`OldTerminal_FSX-LEMD54__b0`) and after (A) the row below it is
  the `TABOX` class at +1.88.  There is NO object rule owed for the trench
  straddlers: they were never real.
* **THE BARS, LEMD** (main → this branch): torn seams outside line/arc
  **0 → 0 — MET**; single-component resources in ≥ 2 files **0 → 0 — MET**;
  §15 carried body floating over its carrier **0 → 0 — MET**; §14 footless at
  datum / on ground / basin split **0/0/0 → 0/0/0**; §16 rows on the datum
  **0 → 0**; duplicate rows surviving the write **0**; round trip **OK**
  (2,149/2,149 new `OBJECT_DEF`s, 0 rows carrying an elevation); files
  **2,107 → 2,149**; §16b carried piece float **111 → 119** and wider than its
  terrain group **967 → 983** (both WORSE, named — more bodies keep their own
  zero and are read on their own ground); §16a (2) refusal set **215 → 164**.
  Plan stage on the graded sampler, 3 runs, `v2_rebake_replay.py plan
  --sampler graded`: **10.17 / 10.22 / 10.20** → **9.95 / 10.06 / 10.08 s**,
  mean 10.19 → **10.03 — MET** (bar ≤ 10.3).
* **THE COCKPIT BLOCK, LEMD.**  Bodies on pavement 499 → 515; CRITICAL MOTION
  **6,640 → 5,400 feet** on 407 → **356 bodies** (buried 3,566 → 3,032,
  floating 3,074 → 2,368).  What the EYE reads at those feet over 0.5 m:
  **FLOATING 663 → 128**, **BURIED 1,109 → 808**.  The two rules separate
  cleanly, because the report now prints both readings: over the WHOLE band the
  same arm gives floating 663 → **581** and buried 1,109 → **816**, so (E)+(A)
  take floating 663 → 581 and buried 1,109 → 816, and (B) alone takes them
  **581 → 128** and **816 → 808**.  Off-sheet stays where it was (feet 36 → 43,
  bodies whose anchor reads no surface 26 → 27): the side-aware read is what
  keeps it there — the first two forms of (E) cost 435 and then 160 bodies.
* **(A)'s OWN NUMBERS.**  LEMD **74 binds refused for ground**, worst refused
  own-ground disagreement **2.38 m**, widest RETAINED cluster zero-plane span
  **1.89 m** (over 0.5: the cap is asked cross-member, and a same-member pair
  the ε-contact graph unions is not refused — named, not fixed).  The `TABOX`
  row: **9 of the 12 boxes released** to their own ground and now read +0.57 …
  +0.70 (from +1.68 … +1.88); the three still bound (`TABOX__b2/__b3`,
  `TABOXzwei__b4`) have own-ground disagreements of **+0.45 / +0.13 / +0.13 m**
  — inside the bar — and their residual +1.82/+1.88 is the ground spanning
  1.75 m under one 7 m box plus `TAPSL__b0`'s own low-side anchor, which is
  11e (2), not §16c.  **The bar "each box within 0.5 m of its own ground" is
  MET.**
* **THE NAMED SITES HOLD, byte-identical**: `LEMD47` ONE zero **603.619** and
  `LEMD48` the same; T2 building-class spread **0.385 m** both arms; item 3
  **+0.05**, item 5 **−0.27**, gate-5 sign **−0.02**, T4 deck **+0.14**,
  `Terminal4_48` **−0.09**, `HANG3` **−0.81**; `green-TEJ3` and the T4S deck
  unchanged.  One T2 roof moved: `LEMD41__b4` (−0.14 on `T2SL3__b0`) is no
  longer a rest-on row, so the roof list reads 2 of 4 over 0.3 m instead of 2
  of 5, worst 14.64 either way (12z's authored 5-9 m gap, unchanged).
* **THE BARS, OTHH** (matched arms under the guard): torn seams **0 → 0 —
  MET**, single-component **0 → 0 — MET**, §15 carried float **0 → 0 — MET**,
  duplicates 0, round trip **OK** (1,268/1,268), files **1,252 → 1,269**;
  **§14 footless at datum 5 → 4** — and the body 12aq's 4 → 5 left UNNAMED and
  owed is `Buildings/Terminal/OTHH_TerminalRoads_CLUTTER_02_001__b2.obj`, which
  (A) takes back out; §14 basin split **1 → 1**; §16b carried piece float
  **126 → 135** and wider **75 → 78** (both worse, named).  CRITICAL MOTION
  **3,891 → 2,822 feet** on 103 → **74 bodies**; over 0.5 m FLOATING
  **332 → 12**, BURIED **0 → 0**.  (A): **54 binds refused**, worst **5.92 m**,
  widest retained span 2.70 m.  Plan stage, 3 runs, same hour, same machine:
  **60.36 / 60.97 / 61.04** → **61.24 / 61.69 / 61.38 s** — the ≤ 60 s bar is
  **MISSED ON BOTH ARMS** (main is already over it), and (A) costs **+0.65 s,
  1.1 %**, inside the noise floor.
* **(C) IS REFUTED AND DELETED** (the code is in this branch's history; the
  record is here).  "A LINE station is cut where the surface under it spans
  more than `split_tol_m`" was implemented twice.  The first form fired on
  NOTHING — `terrain_groups` places WHOLE COMPONENTS (§16c (1), 12d's torn
  vault) and a fence is one welded component, so every station read one group.
  The second gave the line class its own triangle-atom mode, which §10 (2)
  already licenses (the torn-seam census excludes line and arc pieces for
  exactly that reason), and it FIRED: **572 stations cut into 2,926 pieces**.
  It buys nothing and costs a third of the pack: files **2,149 → 2,854**
  (+33 %); §16b line-class wider than its terrain group **531 → 713** (WORSE —
  more bodies, each still read against `split_tol_m` and still capped at
  `line_object_stations_max`); §16b carried piece float **119 → 125** (worse);
  CRITICAL MOTION **5,400 → 5,406**, floating **128 → 129**, buried
  **808 → 802** — flat.  NO bar improved.  This is §16b MEASURED's own earlier
  refutation ("cutting each station again by the ground took LEMD's fence and
  grass files 2,227 → 7,722 for a class the eye does not read") reproduced with
  a smaller blast radius and the same verdict, and (C)'s motivating site — the
  trench straddlers — was dissolved by (E) before the rule was asked.  §10's
  station law stands.
* **Twins:** `test_a_bind_across_members_holds_only_while_the_ground_agrees`
  (armed and unarmed; cross-member refused, same-member never, elevated never;
  the counts), `test_section_17_judges_at_the_ground_contact_feet_not_the_whole_band`
  (the narrow set, the band as the outer scope, and both readings out of ONE
  census pass), `test_the_replay_sampler_never_reads_across_a_graded_hole` (an
  apron with a hole and a floor in it: the apron reads 600 outside, the floor
  590 inside, and nothing in between), and
  `test_anchor_with_no_point_at_its_zero_takes_the_low_side_foot` AMENDED — its
  body is authored dead FLAT and it is the witness for the naming defect.
  Suite **1,226 passed / 1 skipped**, twice (main 1,223 / 1).
* **NOT DONE:** no airport build (§17 needs none); (C) deleted, above; the
  same-member cluster zero-plane span (1.89 m LEMD, 2.70 m OTHH) is REPORTED,
  not capped — the ruling's test is cross-member and capping inside a member
  would be a cut inside a solid; §16b's two counts move the wrong way at both
  airports and are named; OTHH's plan-stage bar stays missed on both arms.

## RULINGS

## 2026-09-13bj — OWNER READ OF KCLT ON 1.0.327 (verbatim): "1. Terminal object families still settling at different elevations resulting in passengers and seat objects around here: 35.2191877, -80.9426007 sitting on the ground under the building instead of on the floor inside the building. Roof elevations sank in some places as well. These large complex structures have to be seated as a unit. As long as it remains feasible with grade laws and taxiways, etc. it's acceptable to flatten large apron areas around big terminals if needed to accommodate a large terminal cluster. 2. Something is broken around here: 35.2182788, -80.9323415 causing texture tearing and pulling the apron down dramatically here: 35.2178642, -80.9322262 3. Roads along east edge are much better now! 4. Buildings at these locations still have floating roof planes: 35.2141727, -80.9291957; 35.2142131, -80.9282182; 35.2140873, -80.9306125; 35.212974, -80.9298385 5. There's a cliff and texture tearing occurring here: 35.2007757, -80.9455609"

* Item 3 CLOSED (§37 (6)–(9), 13bf). Item 1 is a RULING that supersedes 13aq's "partition by pad": A LARGE TERMINAL CLUSTER IS SEATED AS ONE UNIT, and the DESIGN SURFACE gives it ONE pad — the apron around a big terminal may be FLATTENED to that plane where the grade laws and the taxiways allow. Spec §16f (7) + design-surface §30 (4) written; lane `v2clusterpad` (pack). Items 2, 4, 5 → scout `v2kclt327` (2 and 5 read as the 13an / seam-tear class — a hairline or sliver at a pad/bank/zone join pulling the mesh; 4 is the §16d roof class on four named buildings — which of §16c/§16d/§16f routes their roofs and why the plane sits above the walls).

## 2026-09-17n OWNER: THE INTERIOR OBJECT CLASS — "we should be able to gain efficiency by identifying object interiors, as we should never need or want to do anything with them, they simply stay bundled with their object group/cluster and move with it like a roof. They are not applicable to anything we build in the patch. I guess if they were placed with an explicit MSL altitude, we might have to modify that..." — scout `interiors` measures the discriminator, the removed share, the MSL carry and the consumer census before spec §48

* Context: lane `v2doorwellperf` (in flight) attributed the new OTHH pack's 25–28 GB / 40–55 min planar stage to two per-placement whole-mesh reads (door wells, basin cover) and windowed both; the ten heaviest resources are terminal INTERIOR clutter (536,802 / 412,049 / 319,514 / 216,538 / 210,905 solid triangles; one file 141 MB). The owner's law removes interiors from every planar read AND from mesh loading — the class rides its cluster's seat (§16a carried bodies, §30 (4), the anchor-family model); an `OBJECT_MSL` interior is the one case that may need its own delta when the host re-seats.
* Session: the discriminator must be MECHANICAL (containment in a host's roofed above-grade footprint + no at-grade witness of its own reaching the host's exterior), never the resource name; a jetway, a canopy, a car-park deck, a pad-bearing object inside a larger footprint and every §33 (6) / Law B / Law C class are the false positives to exclude by construction; ONE derivation site at the placement read (30l). Brief `docs/briefs/interiors.md`.

## 2026-09-11ai — ATTRIBUTED (scout `v2lemd317`): (A) 40.4841738, −3.5854522 is NOT a library object (the DSF's only `lib/` def is a static car): `green-TEJ3`, a roof-panel RESOURCE scattered over 1 × 2 km of the terminal, is ONE carried body at ONE zero (carrier `NAVEATR4`, 518 m away) — panels +3.06 m over `CNTRL`'s 6 m roof; ground under its own geometry spans 5.02 m. (C) The T4 garage loses no geometry (vertex sums authored ≤ written for every resource; duplicate-row deletion keys on the DEF): its roof-top pavilions `green-TEJ1` (y 8.2–12.0) are SKIPPED by the rebake plan — "no genuine solid component: nothing to seat" (the seat-era THICKNESS GATE, 08-26 §2.1) — so the resource is not in the plan population at all and still sits on the pack's shared-datum row, rendering 15.8 m BELOW the slab; `PKT4__b1` (120 roof verts) is carried by a FENCE segment (`LEMDzaun__b5`, chosen by axis-aligned plan box) at −6 m; `PKT4__b0` is one skirted body 667 m long on one zero (ground under it spans 8.30 m). (D) 40.4858658, −3.5676751: `T4SAT_green-TEJ3` is SKIPPED the same way — datum row 595.81, panels +5.78 / +3.44 m over their buildings. (B) `building4` / 83 is ONE flat pad (66,207 m², z 602.28–602.47, no stacked faces): the "layers" are its boundary STEPS against parking/road neighbours (`pav124` +2.63, `pav137` +1.80, `route6` +1.80, `pav146` −1.01; the apron joints are 0.00 since 11af) — five levels around one plateau, because `classify/evidence._pads` unions every touching OSM footprint into one part at one level.

CLASS: 25 placements skipped as "no genuine solid" (roofs; 20 span ≥ 50 m; worst `Munoza-LEMD77` 30.07 m, `green-TEJ1` 24.57 off their own ground); 138 written files whose own geometry's ground departs > 3 m from the row's; 54 carried bodies whose carrier zero is > 1 m off the ground under them (worst `green-rada__b1` +13.18 on a fence at "0 m²"); pad terracing 10 pads > 0.5 m.

THE LAW (Fable, spec §16): (1) THE THICKNESS GATE IS SEAT-ERA — under `placement = agl` EVERY object row of the pack is in the plan population; a resource with no solid component is a FOOTLESS body and is carried (§14/§15), never left on the datum; the census counts `rows on the datum outside the plan` (bar 0). (2) EVERY BODY IS RE-CUT BY TERRAIN — carried, footless or skirted alike: a body whose own geometry's ground spans more than `split_tol_m` is cut into terrain groups (§9's rule over its own feet or, footless, over the ground under its footprint), each group carried by what IT stands over / anchored on its own low side; the census reads the ground under the carried GEOMETRY, never the carrier's box. (3) A CARRIER IS A SOLID — line segments, grass, signs and any body whose footprint fill (parts hull area / plan box area) is under `carrier_fill_min` (0.2) never carry; "stands over" is measured on the parts hull, not the axis-aligned box; and a carrier whose zero is more than `split_tol_m` off the ground under the carried body is refused — the search continues, and with no carrier the footless body anchors at the ground under its OWN footprint centroid (its authored y kept). Lane `v2skipped`.
* (B) is an OWNER INTENT question 11ai-1: a 66,000 m² union of touching OSM buildings is one flat plateau; its groundside neighbours (car parks, service road) terrace 1–2.6 m against it, lawful under the groundside terrace law but read as "layers". Options: (a) extend 10l to parking/service-road frontages (the SENIOR frontage sets the level; the others blend as banks); (b) split a unioned pad by terrain into several levels at the OSM footprint seams (buildings at different ground levels get their own pads); (c) leave. Recommendation (b)+(a).

## Tool: site_read

| `Ortho4XP/tools/site_read.py` | You have a coordinate from an owner's sim read and the question is WHAT THE OBJECT STAGE MADE OF IT — not what the OSM patch says there (`osm_site.py`, the emitted ways) and not one law's defect count (`harness/census.py`). Three products of ONE build, read at ONE point in one process: the emitted DESIGN SURFACE's faces containing or near it (role, ref, side, z min/med/max, node count — a CONTAINING face reads 0.0 m, never the distance to its nearest vertex, which is `osm_site --at`'s own trap); the DSF ROWS standing on it (`OBJECT` / `OBJECT_MSL` / `OBJECT_AGL` with the resource and, where it has one, the written elevation — `None` for a plain `OBJECT`, never 0.0); and the PLAN BODIES whose plan box reaches it, each with its §6 class, its FOOTPRINT UNIT, its surface z and zero and the stage's own ANCHOR REASON verbatim, which is the line that says WHY a body is where the owner saw it. `--patch-dir DIR` resolves `<ICAO>.graded.json` and `o4_v2_placement_<ICAO>.json` by glob (an `obj8_split_report --json` dump works as `--plan`: the same `splits` records), `--dsf-dump` takes a DSFTool TEXT dump — pass the PRISTINE `<dsf>.anchor_bak...text` (`dsf_write.pristine_dsf_path`) when you want the pack as INSTALLED rather than as this repo last wrote it. `--show`, `--max`, `--json`. **It measures nothing and derives no law**: every value is read verbatim out of a product and nothing is written. Promoted 2026-09-14 (RULINGS `7e90032`, promote-on-reuse) from the scratchpad reader of the 14g HECA attribution, re-written for the 14bl LEMD one (scouts `v2heca331` / `v2lemd336o`) and used a THIRD time by lane `v2leafframe` — three copies of one question, already drifted in their hard-coded LEMD paths. Twin: `tests/auto_patch_v2/test_v2leafframe.py`. |

| `Ortho4XP/tools/arm_site_read.py` | The question is about a PLACE across two arms — "is the wall at 35.2077303,-80.9290869 still there, and did anything near it get worse?" — which an A/B leaves open: `census.py --rows-json` itemises rows and `census_rows_diff.py` joins two dumps class by class, but neither can be asked about a coordinate, and `osm_site.py` reads geometry without law rows or pad seats. This is the join: per named `--site`, per arm, the law-true rows within `--radius` with their worst grade and |de|; with `--seats`, the BUILDING PAD seats that moved between the arms — the channel this repo's HECA airside attribution ran through (a pad seat welds into the apron ring, so a seat that moves moves airside; measured 2026-08-12b: 92 of 215 pads, median 0.32 m, and building211's +0.88 m carried +203 apron rows). **It measures no law and counts no defects**: rows are read verbatim out of census `--rows-json` dumps and geometry/altitudes through the harness library's own `check_grade._parse_osm`, so this tool and the census read one file one way; a missing input reports SKIPPED, never zero. FRAMES, both printed: rows are located by the census's own row lat/lon, which for a within-shape pair is the PAIR's position (a 400 m apron chord's row sits far from either endpoint's geometry), so a radius selects rows near the PAIR, not shapes touching the site; seats join by the building's `ref` tag, never by way id or shapeID (both arm-dependent). Promoted 2026-08-12b from the service-corridor lane's `measure_arms.py` on its SECOND use — the named-site table and then the airside attribution. `--welds` (added 2026-08-12c, the corridor-joins round's ruling-4(a) instrument) answers the other question a place can be asked — IS THIS SEAM JOINED? Per site, per arm: the node ids SHARED between the road family (`check_grade._ROAD_FAMILY_ROLES`, read from the census library) and the airside ways, the max |Δalt| two ways carry at a shared node (0.00 is the construction — production values sit on the NODE, so a weld is single-valued; the delta is the torn-weld guard for way-valued rings), the NEAREST UNWELDED approach when nothing is shared (0.999 m at both KCLT mouths, against a 0.5 m weld tolerance), and the `retaining_wall` ways standing at the site with their ids. `--profile` / `--line` (added 2026-08-25, the HECA apron round-2 acceptance) answer the THIRD question a place can be asked — WHAT SHAPE IS THE SURFACE HERE? `--profile` walks every ring of `--profile-roles` (default `apron,graded_strip`) reaching a site and reports its worst consecutive EDGE and its RIPPLE AMPLITUDE, the peak-to-peak inside a 50 m run ALONG THE RING — the same window `apron_drape_read` calls `amp50`, so the two tools spell the ripple one way. `--line NAME=LAT,LON:LAT,LON` orders every emitted vertex in a corridor about an owner-named segment by its station along it, with the step between consecutive stations: the reading an acceptance written as "no unlawful step along the owner line" is stated in, AND the reading that shows a NODELESS VOID, because there an EMPTY STATION LIST IS ITSELF THE FINDING (a region with no emitted vertices contributes no census row however wrong its surface is — the blind spot `nodeless_interiors` counts). Neither prices a law; quote them ARM TO ARM on identical options, never as a verdict. Reach for it whenever an acceptance claim is about a join: **row absence cannot answer it** — a census row exists only between PAIRED geometry, so an unwelded road↔taxiway seam is silent in every census, which is exactly how two 1.0.244 acceptance claims passed over a gap no node could bridge. Twin: `tests/test_corridor_axis_coverage.py`.  **`--behind NAME=LAT,LON:LAT,LON` is the WALL scope** (added 2026-08-29, scorer-v2 round, spec `scorer-v2-class-boundary-spec.md`): the owner states a wall as two coordinates and asks that no airside pavement cross it — `--line` answers what the emitted elevation does ALONG it and `osm_site --line` answers what covers each station ON it, but neither answers the quantitative half, the SQUARE METRES of airside-role pavement sitting on the groundside, which is the number a boundary-cut round moves and therefore the number its acceptance is written in. Per crossing ring it reports the area behind, the node split either side and each side's altitude range — the shape of a wall buried inside one apron (HECA apron 584: 48 nodes at 97.22-104.69 m in front, 95 at 90.77-102.71 m behind). TWO FRAME RULES, both load-bearing: the band is the line's OWN SPAN by `--behind-depth-m` (default 150 m) deep, never a half-plane — unbounded, the far side sweeps in the whole airport and reports 634,371 m² where the local answer is 25,900 (measured at HECA); and the GROUNDSIDE side is decided by the patch — the side carrying less airside pavement — so reversing the two coordinates cannot change the answer and a caller cannot pick it. The closed-ring repeat is dropped before the node split (counting it double reports one extra node on whichever side the ring starts). It prices no law and counts no defects. **THE SEAT JOIN IS NOT FREE (2026-08-31, the buildings round).** `building{N}` is an ORDINAL identifier, so an arm that ADDS or DROPS a pad renumbers every later one and the ref join reports the RENUMBERING as seat motion: measured on the buildings-round HECA arms (pad count 175 -> 176) the ref join said 85 of 174 pads moved, median 2.72 m, max 33.65 m, where the population had barely moved. The tool now DETECTS it — a common ref whose pad centroid is more than `--seat-radius` (15 m) away is named as RENUMBERED, with the advice to re-run — and `--seat-join location` pairs pads by centroid instead (closest pair first, each pad used once; a pad with no partner within the radius is reported as added/dropped, NEVER as a move), which on the same arms reads 28 of 174 moved, median 0.07 m, max 2.32 m. Quote a pad-population round's seat movements under the location join.  **`--airside-near-cuts M` (2026-09-15, lane `v2shellwall`)** answers the question spec §33 (6) B AMENDED is written in — *did airside beside the pack's structure-object cuts move?* (owner RULINGS 2026-09-15bh: "airside beside a shell never moves", bar 0.02 m).  The region is the SIDECAR'S OWN `object_cuts` `outline_ll` (the arm's, else the control's — a cut that did not exist in the control is precisely the case asked about), never a radius the caller typed, so this read and the `object_cut_offset` family are priced against one geometry; the join is the canonical 11-dp lat/lon identity join, never proximity; a vertex present in one arm only is reported as UNJOINED and named, never as zero motion. Reports the joined population, the movers over `--airside-move-floor-m` (0.02 m, §16g (10) (5)'s own bar), the worst mover with its coordinate, both altitudes and its ways' roles, and the movers by role.  Measured on the registered VHHH pair (`VHHH_20260915T120714` → `VHHH_20260915T122604`): joined 1,079, MOVED 633, unjoined 223, worst −6.460 m at 22.30772370921,113.92337437951 (7.31 → 0.85, junction/primary_parallel).  It measures no law and counts no defects. |

## Tool: frames

| `tools/harness/frames.py` | THE FRAMES REGISTRY (owner 2026-09-13): `register --icao KCLT --kind capture|rebake|patch|graded|mesh --path P --base SHA --lane L [--note]`, `list [ICAO] [--kind K]`, `latest ICAO --kind K` (newest EXISTING entry; a vanished path prints `[MISSING]` and is never served). Append-only JSONL at `docs/frames.jsonl` (merge-friendly across lane branches). A lane registers its capture / rebake plan / closing products at the end so the next lane does not hunt scratchpads. Twin in `Ortho4XP/tests/test_docq.py`. |

## Tool: blast

| `tools/blast.py` | **Before editing anything under `Ortho4XP/src/` or `Sources/`.** Direct importers, tests to run, role-literal / env-flag / wire-protocol hazards, co-change neighbours. `--audit` checks its own recall. **`--tests-for FILE [FILE...]` (2026-08-12, BS1) is the SWEEP SELECTOR:** it reads the diff (`--since REF`, default HEAD), works out which top-level symbols actually moved (AST before/after, so a reformat or a comment edit selects nothing) and prints the test files whose recorded symbol USE intersects them — measured on `auto_patch/layout.py` with a one-symbol change: **6 test files against the 113-file full direct-importer sweep**. With no FILE it selects for every `.py` the diff touched. The law is a UNION of four clauses and RECALL OVER PRECISION: symbol-attributed tests, ∪ ALL direct-importer tests of a changed file with at most `--cheap-ceiling` (15) of them, ∪ ALL of them for any symbol the index cannot attribute (dynamic use, a re-export, `__all__`, a module-level edit — the fallback is named on stderr, never a silent narrowing), ∪ changed test files. STDOUT is the pipeable list (`| xargs venv/bin/python -m pytest`), the stamped header and every fallback go to STDERR. `--audit --mutations N` is the twin that keeps it honest: it deletes one hot symbol per run AT RUNTIME (a pytest plugin — no source file is ever rewritten, because lanes build against this same tree), runs the sample's FULL sweep, discounts the unmutated baseline and requires every failing file to be IN the selection; recall 100 % is the acceptance and precision is printed beside it, plus what clause 1 alone would have caught. A mutation set with NO failing test is a FAIL, not a pass. Index shards are v3: v2 added `symbol_tests` / `symbols_attributed`; **v3 (2026-08-21) adds `tests_via_fixture` — FIXTURE-MEDIATED reach.** pytest wires tests to conftest by NAME, not import: `conftest.cached_airport_layout` imports `auto_patch.pipeline` inside its body, and a test that says `from conftest import cached_airport_layout` (or takes a fixture parameter, or `getfixturevalue`s it) never appears as an importer of anything pipeline transitively imports. On 2026-08-20 a lane editing `runway_segments.py` + `gap_fill.py` ran the listed sweep (472 passed) and skipped `test_pavement_grade.py` / `test_single_graph_acceptance.py` that way. The card now carries a separate `TESTS VIA CONFTEST FIXTURE` line (grouped by helper, not truncated), `--tests-for` adds a 5th union clause (`via-fixture=N`, the files named on stderr), and `--audit` carries two via-fixture canaries (`FIXTURE_CANARIES`). Src->src edges only (a tool importing a module is not a fixture path); helper->helper calls and fixture->fixture params are closed over. Rebuild stays ~2.1 s. An older index on disk rebuilds itself. |

## Registered frames: HECA

HECA  patch    base 13431931   lane v2zonehole       2026-09-13T22:35:13  /tmp/harness/v2zonehole_heca3.osm  [MISSING]  — closing arm of claude/v2zonehole (rc 0, 410.3 s, body_sha 6cc8952ff963, ledger 3b32f2bd74f7, shared repo UNCHANGED) — §41 (1) absorption: containment census 39 -> 4 contained faces (33 notches absorbed, 65,772 -> 245 m2), cross_connector:pav77 absorbed into primary_parallel:pav73 at the owner's site, law-true 40,067 -> 38,151, rows within 100 m of the site 615 -> 551; residual zone_on_pavement 3 / 52.3 m2
HECA  capture  base 1a7a7158   lane v2roadcontact    2026-09-13T22:42:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/roadcontact/cap/HECA.pkl  [MISSING]  — the FIRST registered HECA capture (v2_solve_replay --capture, 156 s, 17,408 vertices / 762 faces, 59 shapes) on main 1a7a7158; carries the road_contact_edge channel
HECA  patch    base 1a7a7158   lane v2roadcontact    2026-09-13T22:42:26  /tmp/harness/v2roadcontactHECA2.osm  [MISSING]  — closing build of claude/v2roadcontact 9ac0fac2 (rc 0, 337.6 s, body_sha 38465d2dfd2a, ledger 96f569b01af9, shared repo UNCHANGED) — §37 (10): route0 end +0.054 m over pav74 edge, item-4 pair 1.6 % over 3.05 m; census law-true 38,441 adjudicated 12,771
HECA  patch    base 1a7a7158   lane v2roles          2026-09-13T22:45:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build/v2roles_HECA.osm  [MISSING]  — closing HECA build of lane v2roles at claude/v2roles f19e2226 (§40): rc 0, 439.8 s, ways 1383, body_sha 8b2ca256f237, artifact ledger 9441f61e86fb, solve feasible, guard UNCHANGED. Shape 44 -> runway shoulder of 05L/23R, shape 93 -> apron, taxi zone strips on shape 44's ground 5 -> 0. RESIDUAL: v2-verify DEFECT runway_transverse 0 -> 2 (1.5287/1.5233 % vs the 1.50 % cap = 3.1/4.8 cm excess at 108.7/204.9 m from the ridge)
HECA  graded   base 1a7a7158   lane v2roles          2026-09-13T22:45:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build/v2roles_HECA.v2/HECA.graded.json  [MISSING]  — design surface of the same v2roles_HECA build; HECA.report.json beside it carries verify.rows per family
HECA  patch    base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.osm  [MISSING]  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  graded   base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.v2/HECA.graded.json  [MISSING]  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  rebake   base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.v2/HECA.rebake.json  [MISSING]  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  patch    base a5bb6be3   lane v2roles          2026-09-13T23:17:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build_r2/v2roles_HECA_r2b.osm  [MISSING]  — ROUND 2 closing HECA build, claude/v2roles a33197a5 (§40 as amended by RULINGS 2026-09-13dd, main merged at 76108185): rc 0, 352.7 s, ways 1142, nodes 22040, body_sha 907d90dfc271, artifact ledger 09ca36ca6c1a, solve feasible, guard shared repo UNCHANGED. v2-verify runway_transverse 2 -> 0 (the two shoulder rows pass at the 2.5 % shoulder cap); NO DEFECT family. Matched census A/B vs the 1a7a7158 base arm: law-true 38,612 -> 33,265, ADJUDICATED 12,844 -> 14,870 (+2,026; round 1 was +2,511)
HECA  graded   base a5bb6be3   lane v2roles          2026-09-13T23:17:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build_r2/v2roles_HECA_r2b.v2/HECA.graded.json  [MISSING]  — design surface of the round-2 v2roles_HECA_r2b build; report.json beside it, and the A/B rows dumps in scratchpad/v2roles/rows_r2.*.json
HECA  patch    base 38dd98be   lane v2roadcontact    2026-09-13T23:36:37  /tmp/harness/v2roadcontactHECA3.osm  [MISSING]  — CLOSING build of claude/v2roadcontact 9eaebbf8 (rc 0, 332.5 s, body_sha 8bbae5f33254, artifact ledger 5e3f94ef2db6, shared repo UNCHANGED) on merged main 38dd98be — §37 (10) as ruled 13dh: route0 end +0.023 m over pav74's edge (4.34 m away), item-4 pair 0.05 m over 3.05 m (1.6 %); census law-true 33,242 adjudicated 14,850 (airside 14,506 / gs 300), road_cross_section 27, transverse 1,575, road_coverage_join 0; v2 verify 21,797 rows, verify_defects {}
HECA  patch    base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/l2/v2ds_lane38.osm  [MISSING]  — lane v2drapedsrc round 2 (§42 (2) amended, RULINGS 13dc) on claude/v2drapedsrc 8994391f; MATCHED PAIR with the base arm cut at main 38dd98be (both carry §40). rc 0, 540.9 s, ways 1783, body_sha c16719e90795, artifact ledger 3eec5bf2bd6a, shared repo UNCHANGED. The owner's site 30.1235047,31.4160956 is INSIDE its OWN apron face apron:dsf:objpav33 (base: 0 rings); census law-true adjudicated 14,870 -> 24,338
HECA  graded   base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/l2/v2ds_lane38.v2/HECA.graded.json  [MISSING]  — lane v2drapedsrc round 2 (§42 (2) amended, RULINGS 13dc) on claude/v2drapedsrc 8994391f; MATCHED PAIR with the base arm cut at main 38dd98be (both carry §40). rc 0, 540.9 s, ways 1783, body_sha c16719e90795, artifact ledger 3eec5bf2bd6a, shared repo UNCHANGED. The owner's site 30.1235047,31.4160956 is INSIDE its OWN apron face apron:dsf:objpav33 (base: 0 rings); census law-true adjudicated 14,870 -> 24,338
HECA  patch    base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/b2/v2ds_base38.osm  [MISSING]  — BASE ARM of the v2drapedsrc round-2 pair: main 38dd98be cut with git archive into a ritual worktree (src byte-identical to the archive), rc 0, 342.7 s, ways 1142, body_sha 907d90dfc271, artifact ledger 85edce09e12a, shared repo UNCHANGED
HECA  graded   base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/b2/v2ds_base38.v2/HECA.graded.json  [MISSING]  — the design surface of the same v2ds_base38 base arm
HECA  capture  base cf87c942   lane v2unionsweep     2026-09-14T07:40:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2unionsweep/heca.lane.json  [MISSING]  — DRY replay dump (NOT a capture: plan_clusters OFF the registered HECA capture 1a7a7158, via cluster_arm.py). MATCHED PAIR: heca.base.json = main cf87c942 (67.52 s, contended; scout read 28.7 s), heca.lane.json = claude/v2unionsweep 99cf52ba (2.24 s). 2 clusters both arms, both areas bit-identical (unit:42#0 404117.7954653089 / unit:43#8 915741.4253155532).
HECA  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/heca/v2sl_heca2.osm  [MISSING]  — CLOSING build of claude/v2slivers 88dfed33 (base main fef82b29): rc 0, 549.5 s, ways 1720, nodes 31441, body_sha 1c7f2be7abae, solve feasible, shared repo UNCHANGED (2 EXTERNAL-CANDIDATE VHHH deltas outside this build's input set) - 41(4) zone slivers 57/1647 m2 -> 1/188 m2 (55 dissolved, 0 dropped), owner shape 1035 gone (no vertex within 12 m of 30.1110526,31.4061994; base carried four at 105.86-106.01 against neighbours 104.32-104.71); gap_interior_ring 57 -> 49 (3 covered + 5 hairline gone incl way -10231, 0 minted, all 49 real voids). Census A/B vs v2sl_heca_base: law-true 54018 -> 53806, ADJUDICATED 24305 -> 24375, cockpit CRITICAL motion 14 -> 17, visual 1568 -> 1518
HECA  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/heca_base/v2sl_heca_base.osm  [MISSING]  — BASE ARM of the v2slivers matched pair: main fef82b29 (src restored clean in the lane worktree), rc 0, 521.5 s, ways 1783, body_sha c07206902a0b, artifact ledger dc1d00dd83ca, shared repo UNCHANGED. Reproduces the owner's 1.0.331 numbers exactly: 338 graded_strip faces, 57 slivers / 1647 m2, 57 gap_interior_ring rings
HECA  patch    base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/build/v2apronneck_HECA.osm  [MISSING]  — lane v2apronneck CLOSING HECA build on claude/v2apronneck 5340dcd7 (base main 2a4abb10) — §43 the neck cut: rc 0, 544.5 s, ways 1822, nodes 31613, body_sha d47263b02287, artifact ledger d53f79789526, solve feasible, guard shared repo UNCHANGED, v2-verify DEFECTS {}. HECA 10 necks; the owner's shape-344 apron (79,658 m2, z span 21.77 m) is gone — the neck A->B is secondary_parallel carrying -2.18 % where the apron carried -1.51 %, the new apron beyond spans 2.51 m. MATCHED PAIR with v2apronneck_HECAbase.
HECA  graded   base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/build/v2apronneck_HECA.v2/HECA.graded.json  [MISSING]  — lane v2apronneck CLOSING HECA build on claude/v2apronneck 5340dcd7 (base main 2a4abb10) — §43 the neck cut: rc 0, 544.5 s, ways 1822, nodes 31613, body_sha d47263b02287, artifact ledger d53f79789526, solve feasible, guard shared repo UNCHANGED, v2-verify DEFECTS {}. HECA 10 necks; the owner's shape-344 apron (79,658 m2, z span 21.77 m) is gone — the neck A->B is secondary_parallel carrying -2.18 % where the apron carried -1.51 %, the new apron beyond spans 2.51 m. MATCHED PAIR with v2apronneck_HECAbase.
HECA  patch    base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/base_build/v2apronneck_HECAbase.osm  [MISSING]  — BASE ARM of the v2apronneck matched pair: main 2a4abb10 in its own ritual worktree (v2apronneckbase), rc 0, 550.6 s, shared repo UNCHANGED (2 external-candidate deltas named, another lane's VHHH mod-cache), NOT ledger-stored. Census law-true 54,018 adjudicated 24,305
HECA  patch    base 22134e4f   lane zonemint         2026-09-14T09:26:56  /tmp/harness/zonemint_heca.osm  [MISSING]  — closing build of claude/zonemint f35d3ee9 (rc 0, 664.5 s, ways 1783, nodes 31514, body_sha c07206902a0b, solve feasible, shared repo UNCHANGED; artifact ledger not stored: an external .DS_Store delta in the window) — sidecar face_holes now derived from the EMITTED surface (546 sub-spacing merges this build): zone_on_pavement 0 (the v2zonehole 13431931 frame: 3 / 52.3 m2; that frame REPLAYED with re-derived holes: 0, no other family moved). Base 22134e4f carries §40/§42, so its 54,012 rows / adjudicated 23,523 are NOT comparable with the 13431931 frame's 38,044 / 12,166
HECA  patch    base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.osm  [MISSING]  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  graded   base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.v2/HECA.graded.json  [MISSING]  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  rebake   base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.v2/HECA.rebake.json  [MISSING]  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  patch    base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.osm  [MISSING]  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  graded   base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.v2/HECA.graded.json  [MISSING]  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  rebake   base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.v2/HECA.rebake.json  [MISSING]  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  patch    base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.osm  [MISSING]  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  graded   base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.v2/HECA.graded.json  [MISSING]  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  rebake   base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.v2/HECA.rebake.json  [MISSING]  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  capture  base 22134e4f   lane rwyholes         2026-09-14T09:25:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-dreamy-maxwell-b04861/a16ebd19-720d-4bda-a609-9334a87ca57c/scratchpad/rwyholes/cap/HECA.pkl  [MISSING]  — the FIRST HECA capture carrying §40 (v2_solve_replay --capture from a ritual-mounted control worktree at main 22134e4f, 151 s, guard blocked [], lane-local DSF dump + mod-cache overlays; 25,358 vertices / 1,307 faces): 43 runway-family faces, 4 with holes, 308 hole vertices — the rwyholes dry pair (crown_drops 3419 -> 3727, runway_crown 2441 -> 2749, runway_transverse 2441 -> 2749 rows) was read off it
HECA  patch    base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.osm  [MISSING]  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  patch    base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.osm  [MISSING]  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  graded   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.v2/HECA.graded.json  [MISSING]  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  graded   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.v2/HECA.graded.json  [MISSING]  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  rebake   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.v2/HECA.rebake.json  [MISSING]  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  rebake   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.v2/HECA.rebake.json  [MISSING]  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  patch    base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.osm  [MISSING]  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  graded   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.v2/HECA.graded.json  [MISSING]  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.v2/HECA.rebake.json  [MISSING]  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  patch    base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.osm  [MISSING]  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  graded   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.v2/HECA.graded.json  [MISSING]  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.v2/HECA.rebake.json  [MISSING]  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  patch    base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.osm  [MISSING]  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  patch    base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.osm  [MISSING]  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  graded   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.v2/HECA.graded.json  [MISSING]  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  graded   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.v2/HECA.graded.json  [MISSING]  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  rebake   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.v2/HECA.rebake.json  [MISSING]  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  rebake   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.v2/HECA.rebake.json  [MISSING]  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  patch    base 18cc0ecb   lane v2staged         2026-09-14T16:41:01  /tmp/harness/v2stagedHECA3.osm  [MISSING]  — §20b THE STAGED SOLVE, FINAL FORM, staged_solve=true arm (branch claude/v2staged): rc 0, 416.0 s, ways 1916, body_sha 266b56b5a358, v2-verify 33955, shared repo UNCHANGED. Stage 1 AIRSIDE 19,034 unknowns / 128,949 rows, 42/161,690 hard violated max 0.1794 NOT SETTLED, 0 one-way rows, runway projection 0.1155 -> 0.020000 m with 0 elastic; stage 2 13,838 unknowns / 180,591 rows in 11.2 s. vs its OFF twin v2stagedHECAoff (= r5 shipped body 18e51b7d084e): airside moved vs DISARM 8,976 -> 10,371 (BAR 0 MISSED; runway 885/0.390 -> 477/1.560), adjudicated 28,413 -> 29,018, airside_no_step 7,919 -> 6,801, taxi_box 3,429 -> 2,854, pad_airside_weld 29 -> 33, pad_cluster_mismatch 14 -> 14, terminal building298 72.60 -> 73.05. SHIPS OFF
HECA  patch    base 18cc0ecb   lane v2staged         2026-09-14T16:41:01  /tmp/harness/v2stagedHECAoff.osm  [MISSING]  — §20b's DISARM twin (staged_solve=false) on claude/v2staged: rc 0, 476.3 s, body_sha 18e51b7d084e — BYTE-IDENTICAL to v2padcluster r5's shipped arm (ledger a602bba1b858), which proves everything merged since a3185dbb changes nothing at HECA and makes the r5/DISARM frames lawful controls for this lane. v2-verify 33,397; 1,021/365,395 hard rows violated max 2.984 m
HECA  capture  base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  [MISSING]  — v2_solve_replay --capture on main b1b7704c (158 s, 31,820 vertices / 1,684 faces, pack partition 101 s: bodies 24,655 groups 22,049 relief 3,938 infeasible 2,546, 63 shapes); guard shared repo UNCHANGED, lane-local DSF + mod-cache overlays. The first HECA capture carrying the merged §20b staged solve (flag OFF by default; arm with --design-weight staged_solve=1). Stage-1 airside hard set read off it with the new --why-hard-stage 1.
HECA  graded   base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/emit_laneB/HECA.graded.json  [MISSING]  — LANE arm of the v2settle matched pair (single solve = the shipped configuration), claude/v2settle b1a93a9a off main b1b7704c: dry --emit replay off cap/HECA.pkl. BYTE-IDENTICAL to the base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/base/emit_baseA/ (main b1b7704c) — the constant hard rows never reached the matrix. Hard set READ 281 -> 263 violated, worst 1.2595 m unchanged. Census law-true 64,716 ADJUDICATED 27,695.
HECA  capture  base b1b7704c   lane v2padvert        2026-09-14T18:19:02  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  [MISSING]  — RE-READ by lane v2padvert (claude/v2padvert 4ec750f9): v2settle's HECA capture replayed under §20b (--design-weight staged_solve=1) with 14au's relaxed skirt ceiling (5 %). Stage 1 AIRSIDE 6/161,638 hard over 0.02 m, worst 0.0445 m — UNCHANGED from v2settle's post-fix reading (the airside did not move). Stage 2 770/163,847 violated, worst 4.4241 m, of which 124 a PROVED INFEASIBLE SET (90.4386 m over 544 free columns) against v2settle's 1,428 of 2,548 / 1,015.6 m: -91 % rows, -91 % shortfall. Pads-ON was NOT measurable off this capture — v2_solve_replay.capture sets no airport.clusters, so pad_from_cluster is inert in any replay of it; a pads-ON HECA reading needs a fresh capture or a build. guard shared repo UNCHANGED.
HECA  patch    base 092b3983   lane v2padjoin        2026-09-14T20:06:08  /tmp/harness/v2padjoinHECAbase.osm  [MISSING]  — BASE ARM of the v2padjoin matched HECA pair (branch claude/v2padjoin, base main 092b3983 + the re-landed v2padvert clip): pad_from_cluster=true, pad_airside_clip=true, staged_solve=true, cluster_apron_reach_m=0. rc 0, 457.9 s, ways 1904, nodes 31924, body_sha 3a2d1507c31a, v2-verify 31042, solve feasible, guard shared repo UNCHANGED (1 external-candidate OTHH mod-cache delta named, another lane's; no artifact ledger key for that reason). REPRODUCES v2padvert's registered pads-ON frame EXACTLY: stage 2 1,201/189,405 hard violated, 151 an INFEASIBLE SET (178.7207 m over 705 free columns); stage 1 4/148,256 worst 0.0329 m
HECA  patch    base 092b3983   lane v2padjoin        2026-09-14T20:06:08  /tmp/harness/v2padjoinHECAjoin.osm  [MISSING]  — JOIN ARM of the same pair, the ONLY variable cluster_apron_reach_m 0 -> 40 with the §30 (4) apron reach minted as RULINGS 2026-09-14bf's PLANE JOIN (each collar vertex bound into the pad's plate: cap-0 pad_flat + the hard 1 % ceiling). rc 0, 449.9 s, body_sha c76d6b9759f7, guard shared repo UNCHANGED. THE JOIN IS REFUTED: 24,202 join rows take stage 2 from 1,201 to 3,322/204,943 violated and the INFEASIBLE SET from 151/178.7207 m to 1,114/2,312.4274 m over 1,009 columns; stage 1 (the AIRSIDE) 4 -> 8 rows, worst 0.0329 -> 0.1080 m. Mechanism: under §20b the collar is airside, stage 1 fixes it without the pad and substitutes it as a constant, so the plate must equal an already-solved collar (worst join ceiling rows 5.89 m); the all-airside collar pairs leak into stage 1 and move the airside. The join code is DELETED on the branch
HECA  patch    base 0c72919a   lane v2padjoin        2026-09-14T20:49:33  /tmp/harness/v2padjoinHECAr2base.osm  [MISSING]  — ROUND 2 BASE ARM (branch claude/v2padjoin 747eaf91, base main 0c72919a): pad_from_cluster + pad_airside_clip + staged_solve ON, cluster_apron_reach_m 0. rc 0, 473.5 s, body_sha 3a2d1507c31a — BYTE-IDENTICAL to round 1's base arm, which proves everything merged into main since 092b3983 changes nothing at HECA in this configuration. Stage 2 1,201/189,405 hard violated, 151 an INFEASIBLE SET (178.7207 m over 705 columns); stage 1 4/148,256 worst 0.0329 m; census pad_airside_weld 42, pad_cluster_mismatch 12, ADJUDICATED 26,708; terminal 30.1279552,31.403143 at 72.62
HECA  patch    base 0c72919a   lane v2padjoin        2026-09-14T20:49:33  /tmp/harness/v2padjoinHECAr2collar2.osm  [MISSING]  — ROUND 2 COLLAR ARM, RULINGS 2026-09-14bk's form: the apron within cluster_apron_reach_m (40 m) of a cluster outline is ONE PLANE among itself in §20b STAGE 1 (apron-law heads zones.apron cluster_collar_plane[ ceiling], in no conforming register, no pad vertex in any row) and the pad's plate equals that fixed collar in stage 2; other building pads' welded vertices struck from the collar. rc 0, 368.3 s, body_sha 77e8a3aa20cb, guard shared repo UNCHANGED. STAGE 1 IS FEASIBLE (min shortfall 0.0000 m) — the collar plane is lawful — but THE ACCEPTANCE IS MISSED: airside moved vs the base 11,847 vertices worst 9.45 m (RUNWAY 837, worst 1.23) against a collar of 266 vertices / 12 at the plane, the terminal 72.62 -> 75.92 (bar 72.50), stage-2 infeasible 151 rows / 178.72 m -> 1,318 / 3,074.92 m. The worst stage-2 rows are structures.building_pad airside skirt (7.07 -> 8.58 m) — the skirt law 14ay withdraws and this round did not. Its unstruck twin is v2padjoinHECAr2collar (b6443b925086: 1,626 / 3,644.17 m, stage 1 44 unsettled). Ships DISARMED
HECA  patch    base 7fe1ee9e   lane v2padjoin        2026-09-14T21:30:17  /tmp/harness/v2padjoinHECAr3base.osm  [MISSING]  — ROUND 3 BASE ARM (claude/v2padjoin, the SKIRT WITHDRAWN + the low-side datum; pads + clip + staged ON, cluster_apron_reach_m 0): rc 0, 446.1 s, body_sha 43b8ad21d290, v2-verify 28,801, guard shared repo UNCHANGED. THE SKIRT WITHDRAWAL ALONE, against round 2's base 3a2d1507c31a in the same configuration: stage-2 infeasible 151 rows / 178.7207 m -> 92 / 138.7410 m, violated 1,201 -> 555, worst 7.0692 -> 6.4143 m, pad_airside_weld 42 -> 18, pad_cluster_mismatch 12, ADJUDICATED 26,708 -> 24,770; stage 1 5/153,340 worst 0.0329. Terminal surface at 30.1279552,31.403143 72.92, the terminal cluster's plane 72.478
HECA  patch    base 7fe1ee9e   lane v2padjoin        2026-09-14T21:30:17  /tmp/harness/v2padjoinHECAr3collar.osm  [MISSING]  — ROUND 3 COLLAR ARM (the only variable cluster_apron_reach_m 0 -> 40): rc 0, 512.4 s, body_sha 8cb776c1d044, guard shared repo UNCHANGED. MISSES: stage-2 infeasible 92 -> 1,511 rows / 138.74 -> 3,148.2532 m, airside moved 11,001 worst 9.27 m (runway 849 worst 1.62), terminal cluster plane 72.478 -> 75.497, surface 72.92 -> 75.90, pad_airside_weld 18 -> 19, ADJUDICATED 24,770 -> 25,983. Stage 1 stays FEASIBLE (11 unsettled rows, min shortfall 0.0000 m) — the collar plane is lawful law. THE RESIDUAL IS NOT LOCAL: of 11,363 moved vertices only 3,202 are within 40 m of a cluster pad, 3,776 within 100 m, 2,211 beyond 500 m — a field-wide shift of an unsettled stage-1 optimum (14as (ii), 13y (B)/13ab). Collar 266 vertices, 8 at the plane. Ships DISARMED
HECA  capture  base 12400580   lane v2settle         2026-09-14T23:01:33  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  [MISSING]  — RE-READ at main 12400580 (round 2): the same b1b7704c capture replays under the merged tree. THE STABILITY PROBE FRAME — scratchpad/v2settle/probe3.py + probe4.py perturb ONE apron vertex (v9968 at 30.12795521596,31.4031429808) with a ceiling 0.30 m under the base surface and bin the moved set by distance: main moves 959 vertices > 0.02 m, 953 BEYOND 500 m, 0 within 100 m, worst 0.5206 m. Reproduces RULINGS 14br's collar signature with the pad law inert. Stage 1 here: 35/174,500 hard over 0.02 m, worst 0.0828 m, certificate FEASIBLE.
HECA  graded   base 12400580   lane v2settle         2026-09-14T23:01:33  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/r2/emit_final/HECA.graded.json  [MISSING]  — lane v2settle ROUND 2 arm (claude/v2settle 16725245) off the b1b7704c HECA capture at main 12400580: BYTE-IDENTICAL to the base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/base2/ equivalents and to the pre-change arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/r2/emit_off/. 39/329,775 hard rows violated, worst 1.2595 m, active-set exits objective_stalled x6 (NONE at same_set).
HECA  patch    base 63258868   lane v2qp             2026-09-15T00:29:54  /tmp/harness/v2qpHECA.osm  [MISSING]  — CLOSING build of claude/v2qp 682d1810 with [design] solver="qp" (§20c; the branch SHIPS fixed_point — this is the QP ARM): rc 0, 449.1 s, ways 1741, nodes 31261, body_sha 73b5bdecfd98, artifact ledger 2f4e1c4f8717, status optimal, shared repo UNCHANGED, v2-verify 30592 rows. design line: QP (§20c) 6 exact solves optimal x6, 197 rounds / 358 linear solves, 50.09 s, worst |grad| 537.7; 18/329337 hard rows over 0.02 m (3 a proved INFEASIBLE SET, 3.1661 m) vs the fixed point's 39. Census law-true 61845 ADJUDICATED 26348
HECA  graded   base 63258868   lane v2qp             2026-09-15T00:29:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2qp/emit_heca_qp/HECA.graded.json  [MISSING]  — QP ARM of the v2qp matched HECA replay pair off the registered v2settle capture (cap/HECA.pkl, base b1b7704c), --design-weight solver=qp: solve 131.0 s (fixed point 127.4 s = 1.03x), hard rows over 0.02 m 39 -> 18, worst 1.2595 unchanged, infeasible set 4 -> 3. Its BASE ARM (fixed_point, same tree) is /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2qp/emit_heca_fp/HECA.graded.json, which reproduces v2settle r2's registered reading exactly (39/329775, objective_stalled x6). Census A/B ADJUDICATED 26634 -> 26607, no family worse by > 5 %
HECA  capture  base 12400580   lane v2qp             2026-09-15T00:29:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/r2/heca.solved.pkl  [MISSING]  — RE-READ by lane v2qp as the §20c STABILITY PROBE frame, through the promoted instrument 'v2_solve_replay --why-from PKL --probe-site 30.1279552,31.403143 --probe-arm solver=fixed_point --probe-arm solver=qp'. fixed_point reproduces 14bw exactly: 959 of 31820 moved > 0.02 m, 959 beyond 250 m, 953 beyond 500 m, ZERO within 100 m, worst 0.5206 m, hard 39 -> 25 under the probe. qp: 0 moved anywhere, max |dz| 0.0043 m field-wide, hard 18 -> 18. Same capture solved twice is BITWISE identical on both arms (sha cef4f5c8a773 / 01c2f08e40b1)
HECA  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/HECA.on3.pkl  [MISSING]  — HECA PADS-ON capture (--placement pad_from_cluster=true pad_airside_clip=true), 170 s, 32,182 vertices / 1,811 faces, guard UNCHANGED. Its solved pickle h2.on.pkl is the §16g (10) (11) probe frame: one 0.30 m ceiling at 30.1279552,31.403143 moves 16 of 32,182 vertices, ALL beyond 500 m, worst 0.1031 m (the same capture with the clip left at the MINT moved 0, max 0.0192 m). Matched OFF arm cap/HECA.off3.pkl
HECA  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/HECA.off3.pkl  [MISSING]  — HECA PADS-OFF capture (the shipped law), 186 s, 31,820 vertices / 1,684 faces, guard UNCHANGED - BASE ARM of the v2padqp HECA pair (census ADJUDICATED 26,608; pad_cluster_mismatch 16)
HECA  patch    base f32fb08c   lane v2channel        2026-09-15T10:23:51  /tmp/v2channel/r3/br_HECA/structures.json  [MISSING]  — v2channel round-3 DRY structure replay (branch), paired with base HECA at main 46b219d8 in /tmp/v2channel/r3/base_HECA
HECA  capture  base 5144df7d   lane v2padqp          2026-09-15T10:51:20  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/HECA.clip.pkl  [MISSING]  — THE CLIP-ONLY ARM (--placement pad_airside_clip=true pad_from_cluster=false), 209 s, 30,980 vertices / 1,665 faces, guard shared repo UNCHANGED. §16g (10) (11) r2's interventional attribution: against the pads-OFF arm this arm ALONE moves 4,474 airside vertices worst 1.39 m (runway 17 / 0.100) of the full pads-ON arm's 5,973 / 3.28 m -- three quarters of the airside movement is the ARRANGEMENT CLIP re-noding the airside faces, not any pad row
HECA  capture  base 848bf35e   lane v2lemdstruct2    2026-09-15T11:36:11  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/heca_on.pkl  [MISSING]  — r4 CONTROL, flip ON arm (solved pickle off the registered v2padqp HECA.off3 capture): verify 30,500 rows. Its matched OFF arm is heca_off2.pkl beside it - ONE variable, the emit.toml one_way_rulings entry for structures.placement foot_row. Delta: verify 30,459 -> 30,500 (+41), airside_no_step 7,794 -> 7,823, 8 of 3,753 runway-family vertices moved > 0.02 m (worst 0.064 m), whole surface max 0.822 m. Only 3 of HECA's 4 foot targets touch airside pavement - the flip is nearly inert here, so LEMD's 5 m is a SITE property
HECA  patch    base 395bd09a   lane v2channel        2026-09-15T10:52:05  /tmp/v2channel/r4/br_HECA/structures.json  [MISSING]  — v2channel round-4 DRY structure replay (branch, §45 (13)); base arm at main in /tmp/v2channel/r4/base_HECA
HECA  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/HECA.off.pkl  [MISSING]  — HECA PADS-OFF capture (--placement pad_from_cluster=false pad_airside_clip=false = the shipped law) on claude/v2padclip, 186 s, 32,589 vertices / 1,738 faces, guard shared repo UNCHANGED. The FIRST HECA capture carrying §16g (10) (12) (the two-pass arrangement: the airside is noded before any pad exists) AND the arrangement's own re-node reading (deleted 0 / minted 40). BASE ARM of the v2padclip HECA triple; census ADJUDICATED 19,456, pad_cluster_mismatch 15, pad_airside_weld 9.
HECA  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/HECA.clip.pkl  [MISSING]  — HECA CLIP-ONLY capture (--placement pad_from_cluster=false pad_airside_clip=true), 162 s, 31,576 vertices / 1,708 faces, guard UNCHANGED. The 15ah attribution arm re-cut under §16g (10) (12): re-node deleted 0 / minted 40 (before the rule the same arm read 1,008 deleted / 283 minted). Against the OFF arm the airside VALUE still moves 4,787 non-pad solve-owned vertices, worst 2.06 m, runway 19 / 0.070 m.
HECA  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/HECA.on.pkl  [MISSING]  — HECA PADS-ON capture (--placement pad_from_cluster=true pad_airside_clip=true), 187 s, 32,769 vertices / 1,850 faces, guard UNCHANGED. re-node deleted 0 / minted 43. Census vs the OFF arm: ADJUDICATED 19,456 -> 18,686, pad_cluster_mismatch 15 -> 0, pad_airside_weld 9 -> 8. Airside moved (non-pad, solve-owned) 6,031 worst 3.09 m, runway 180 / 0.130 m -- attributed to the JOINT solve: the same pair under --design-weight staged_solve=1 reads runway 3 / 0.020 m.
HECA  patch    base 7f80dc71   lane v2padclip        2026-09-16T09:49:15  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/emit_heca_clip/HECA_auto.patch.osm  [MISSING]  — HECA clip-only replay EMIT - the FIRST patch whose sidecar carries pad_airside_renode (40 rows, all 'minted'); census law-true 59,808 ADJUDICATED 18,759, pad_airside_renode 40.
HECA  capture  base 782a50d6   lane v2padclip        2026-09-16T10:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/r2/cap/HECA.lane2.pkl  [MISSING]  — r2 HECA PADS-OFF (shipped law) capture with §16g (10) (12) (1) (c) landed: 164 s, 31,383 vertices / 1,695 faces, guard UNCHANGED. Its matched BASE ARM is cap/HECA.base.pkl (main 1bc93833, own ritual worktree). OFF-arm identity: census ADJUDICATED 19,032 -> 19,076 (+0.2%), law-true 59,215 -> 59,114; hairline_pair -537, taxi_box +0, pad_airside_weld +0. Its staged emit is emit_heca_off_st.
HECA  capture  base 782a50d6   lane v2padclip        2026-09-16T10:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/r2/cap/HECA.on2.pkl  [MISSING]  — r2 HECA PADS-ON capture (pad_from_cluster+pad_airside_clip true). Staged OFF->ON (solve-owned, non-pad): 2,230 moved worst 2.68 m, RUNWAY 2 at 0.020 m. THE PROBE on its staged solve (heca_on_st.pkl): one 0.30 m ceiling moves 0 of 32,575 > 0.02 m, max 0.0167 m, nothing beyond 250 m. Third arm with every pad generator dropped still moves 1,544 / 2.00 m -- the movement is NOT a pad row.
HECA  patch    base 8fe85a0f   lane v2stagepop       2026-09-16T11:39:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2stagepop/emit_full_off/HECA_auto.patch.osm  [MISSING]  — §20b (3) r1 BAR ARM: HECA staged (--design-weight staged_solve=1) PADS-OFF replay emit off the registered v2padclip r2 capture cap/HECA.lane2.pkl, on claude/v2stagepop c4c6a8a6 (stage 1 triangulates only its own roles). Its matched ON arm is emit_full_on beside it: non-pad solve-owned airside moved >0.02 m 2077, worst 2.40 m, RUNWAY 2 at 0.020 m (r2's frame, no stage-role rule: 2230 / 2.68 / 2).
HECA  patch    base 8fe85a0f   lane v2stagepop       2026-09-16T11:39:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2stagepop/emit_full_on/HECA_auto.patch.osm  [MISSING]  — §20b (3) r1 BAR ARM: HECA staged PADS-ON (pad_from_cluster+pad_airside_clip true, capture cap/HECA.on2.pkl) replay emit on claude/v2stagepop c4c6a8a6. Matched OFF arm emit_full_off beside it.
HECA  patch    base 8fe85a0f   lane v2stagepop       2026-09-16T11:39:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2stagepop/emit_base_off/HECA_auto.patch.osm  [MISSING]  — §20b (3) r1 CONTROL: HECA staged, every pad generator dropped (pads/pad_level/pad_frontage_level), pads-OFF, WITHOUT the stage-role rule (design.py stashed) — reproduces v2padclip r2's own 1,544 / 2.00 m survivors EXACTLY on this tree. Arms beside it: emit_base_on, emit_fix_off, emit_fix_on (the rule armed: 1,470 / 1.82 m).
HECA  patch    base ed7cedab   lane v2hecastep       2026-09-16T18:18:31  /tmp/harness/v2hecastep2.osm  [MISSING]  — CLOSING build of claude/v2hecastep 24887320 (the same-region HAIRLINE merge): rc 0, 562.0 s, ways 1954, nodes 32314, body_sha 0696f7810bf4, artifact ledger d18af0a0dd17, status optimal, shared repo UNCHANGED. v2-verify 29391 rows, runway_step 4 -> 1 (the app-1.0.344 report's 3 face-37 rows 0.6845/0.5715/0.3422 m are GONE; the survivor is 0.1693 m over 0.992 m at 30.1076486,31.4083338, faces 32|14 sharing vertex 1748 = a 17 % SLOPE, not a step). Runway faces 37 -> 34. Every other family vs the 1.0.344 report: within_shape 16310->16301, taxi_box 4366->4358, airside_no_step 6867->6846, pad_flat 237->233, plane_gradient 5->3, strip_transverse 310->313, transverse 1082->1081, runway_crown 95, adjacent_ground_step 13, strip_seam_tear 29.
HECA  graded   base ed7cedab   lane v2hecastep       2026-09-16T18:18:31  /tmp/harness/v2hecastep2.v2/HECA.graded.json  [MISSING]  — Design surface of the same v2hecastep2 closing build; HECA.report.json beside it. Owner's taxi44 read off it: centreline z-DEM +0.17/-0.21/-0.22/-0.20/+0.03/-0.19/-0.10/+0.22 m at stations 0..1400, 40 m right -0.05..-0.77 m (a CUT with the terrain rising right) except +1.20 m at station 400.
HECA  capture  base ed7cedab   lane v2hecastep       2026-09-16T18:18:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/r2/cap/HECA.on2.pkl  [MISSING]  — RE-READ by lane v2hecastep as THE CONTROL THAT REPRODUCES APP 1.0.344's HECA REPORT EXACTLY with no build: 'v2_solve_replay --replay HECA.on2.pkl --from planar --verify' at main ed7cedab (ritual base worktree) reads runway_step 4, pad_flat 237, airside_no_step 6867, taxi_box 4366, within_shape 16310, strip_transverse 310, transverse 1082, runway_crown 95, adjacent_ground_step 13 — every family identical to XPTerrainBuilderData/tmp/auto_patch_v2/+30+031/HECA/HECA.report.json. INTERVENTION (logs in scratchpad/step/arm_*.log of session 7b1630af): the pads-OFF capture HECA.lane2.pkl --from planar reads the SAME runway_step 4 and the same four magnitudes; --design-weight staged_solve=0 reads 3 at 0.6755/0.5674/0.3377 — NONE of the three 1.0.344 keys mints the rows. The lane's hairline merge on the same arm: runway_step 1.
HECA  capture  base 23b0adf0   lane v2hecastep       2026-09-16T18:33:53  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/r2/cap/HECA.on2.pkl  [MISSING]  — ROUND 2 re-price (claude/v2hecastep 23b0adf0, the span rule + cliff escape in verify/runway.runway_step): the SAME '--from planar --verify' arm over the SAME surface as the v2hecastep2 closing build — verify 29391 rows, every family byte-identical (within_shape 16301, taxi_box 4358, airside_no_step 6846, pad_flat 233, transverse 1081, strip_transverse 313, runway_crown 95, adjacent_ground_step 13), runway_step still ONE census row but now grade_pct 17.05 vs cap_pct 33.0, reading 'slope' -> 'verify DEFECT families (runway_transverse, runway_vertical_curve, runway_step): ALL ZERO'. No new build: the surface did not change. Log: scratchpad/step/arm_lane_planar_r2.log of session 7b1630af.
HECA  patch    base 6c8dfe71   lane xplatquantum     2026-09-17T17:19:00  /tmp/harness/xq_base_heca.osm  — BASE arm at main 6c8dfe71 (§46 price): rc 0, 393.2 s, ways 1954, nodes 32314, optimal, body_sha 0696f7810bf4, v2-verify 29391 rows; census law-true 63,820 ADJUDICATED 22,885. Shared repo UNCHANGED.
HECA  patch    base 6c8dfe71   lane xplatquantum     2026-09-17T17:19:00  /tmp/harness/xq_lane_heca4.osm  — LANE arm, claude/xplatquantum 0992d747 (§46 the 1 mm input quantum SHIPPED): rc 0, 319.1 s, ways 1961, nodes 32469, optimal, body_sha 3d01fc6270a9, v2-verify 29992 rows; census law-true 64,480 (+660) ADJUDICATED 23,592 (+707, +3.1 %). Families over 1 %: taxi_box +1.5 %, hairline_pair +4.4 %, airside_no_step +2.1 %, plane_gradient +7.7 %, adjacent_ground_step +15.4 % WORSE; road_cross_section -9.1 %, transverse -1.2 %, strip_arc -100 %, pad_airside_weld -6.7 % BETTER. NOTE: the first HECA arm on this branch DIED in classify (GEOS side location conflict) until the junction buffer repair. Shared repo UNCHANGED.

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
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py tests/test_auto_patch_freshness.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

