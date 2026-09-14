# Brief pack — lane `v2connector`

Base: main `3dec37a2` · generated 2026-09-13 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§16g (6): a connector joins two units; an identified connector keeps its high-end unit datum; authored_unit census

## The brief

Implement §16g (6) in `Ortho4XP/src/auto_patch_v2/airport/footprint_unit.py` (`_is_connector`, `_bind_plan_wide`; read `blast.py` first):

1. `_is_connector` takes the plan-wide unit partition: a body is a connector only if span ≥ `connector_span_m` AND end spread ≥ `visual_m` AND its two hull ends touch (≤ `footprint_touch_m`) two DIFFERENT units, or one unit and nothing within `connector_span_m` at the other end. Every contact into one unit → member, keep it chained.
2. An identified connector is NOT `continue`d out of the bind: seat it on the datum of the unit its HIGH end touches (DECK > PAD > GROUND between the two candidates), record `connector_of = (unit_a, unit_b)` in the placement record; it never reaches §16c's low-side foot. Do not write the station cut in this round (say so in the report).
3. `authored_unit`: group source-pack placements sharing one DSF origin (lat, lon to 1e-7) and heading; publish in the census; a unit partition separating two siblings → cockpit `unit_split_authored` WARN (register the family in `tools/check_grade.py` LAW_FAMILIES if it is a census family; the harness twin will tell you).
4. Twins in `tests/auto_patch_v2/test_v2clusterpad.py` or a new `test_v2connector.py`: a 549 m body chained to one unit stays a member; a 300 m body bridging two units is a connector seated on the high-end datum; the low-side foot is never reached for it.

Frame: the owner's 1.0.329 SPJC products are the read (`/Users/noah/XPTerrainBuilderData/Patches/-20-080/-13-078/o4_v2_placement_SPJC.json`, placement index 2149 = `SPJC_LIMANUEVA_xp11_007__b0`, index for `xp11_010__b0` per the census); scout `v2spjcramp`'s numbers are in RULINGS 13cn. Dry arm through `tools/obj8_split_report.py` before the build. Closing test: ONE SPJC build through `tools/harness/build_airport.py SPJC`; then re-read the HECA / KCLT / OTHH unit censuses from their REGISTERED frames (`frames.py list`) dry — no other builds.

## Bars

- SPJC `xp11_007__b0` and `xp11_010__b0`: `unit_of = fu:0:0@cluster_pad`, authored zero = 19.56 ± 0.02 (today 27.366 / 18.575); `unit_connectors_cut` 0 at SPJC (today 2).
- HECA's elevated rail: still a connector (two end units named) and seated on its high-end unit's datum — before → after named.
- KCLT / OTHH / LEMD unit censuses: connectors before → after, each with its two end units; no member lost from a unit it was in before.
- `unit_split_authored` = 0 at SPJC after.
- Plan stage not worse than +5 % (SPJC, dry arm timed both ways).
- Suite twice green.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/airport/footprint_unit.py`, `Ortho4XP/src/auto_patch_v2/airport/placement_record.py`, `Ortho4XP/tests/auto_patch_v2/test_v2connector.py`
Other lanes' (do not touch): `Ortho4XP/src/O4_Mesh_Utils.py`, `Ortho4XP/src/O4_Vector_Map.py`, `Ortho4XP/src/auto_patch_v2/planar/`

## Spec (object-placement) §16g (6)

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

## RULINGS

## 2026-09-13cn SPJC viaduct attributed: §16g (3) EXPELS the body it should bind — §16g (6) written, lane `v2connector`

Scout `v2spjcramp` on the owner's 1.0.329 SPJC products (no build; read-only).
The access-road viaduct `SPJC_LIMANUEVA_xp11_007__b0` (span 549 m, 16
components, one body) has `unit_of = None`: §16g (3)'s connector test (span
≥ 200 m AND end-ground spread ≥ 0.5 m; here 11.58 m) names it a connector and
`_bind_plan_wide` drops it from the terminal unit `fu:0:0@cluster_pad`
(datum `building6` 19.5604) WITHOUT writing the promised station cut, so it
falls to §16c's low-side foot: the −8.308 m footing bottom is pinned to the
mesh (19.058), authored zero lands at 27.366 — **7.81 m above the unit
datum**, the deck 18.3–19.7 m over the apron, the south abutment slab +8.96 m
in the air; the only contact with the mesh is the footing bottom at s 0–50 m
(−0.02 … +0.15). `xp11_010__b0` (span 1,030 m) is expelled the same way,
0.99 m LOW. All eleven LIMANUEVA placements share ONE DSF origin/heading in
the source pack (a shared-datum pack); nine chain into the terminal unit, the
two longest are thrown out. The terminal did not move 1.0.327 → 1.0.329
(`SPJC.rebake.json` byte-identical across three frames; `building6`
[18.84, 20.13] in all). Second, smaller class: no road face reaches the
viaduct's low end (nearest road chain 655.7 m; OSM `highway=service`
−10092/−10616 within 25 m are absorbed into `pav49`/`pav46` under the
free-road ruling), so §37 (6)/§34 grade nothing there — at the correct datum
the south abutment still wants +1.56 m of fill, NE columns up to 2.4 m of
cut. `--why-at` not run (no capture; no solved vertex within 52.6 m).

* RULING (the owner's words 13ce: cutting is allowed ONLY for "very long
  connecting pieces like the elevated rail at HECA"): a connector CONNECTS
  two units. §16g (6) written: (1) connector = span ≥ 200 m AND spread ≥
  0.5 m AND its two ends touch two DIFFERENT units (or one unit and open
  ground); a body whose every contact chains into one unit is that unit's
  member however long; (2) an identified connector is seated on its
  high-end unit's datum until the station cut is written — it never falls
  to the low-side foot; (3) the shared-DSF-origin pack row is recorded as
  `authored_unit`, and a partition separating siblings raises
  `unit_split_authored` (WARN).
* Lane `v2connector` (Opus, brief pack) implements §16g (6) in
  `airport/footprint_unit.py`; closing test SPJC through the harness (the
  two bodies at the datum, `unit_connectors_cut` 0 there, HECA rail still a
  connector).
* The residual (+1.56 m fill at the abutment, no road under the viaduct)
  stays open under §37 (6)/§34 — the absorbed service ways are the next
  read once the datum is right.
* Not verified: the 1.0.327 placement plan (overwritten; app builds are not
  in the artifact ledger); `artifact_ledger.py --history` does not exist as
  a CLI — the brief was wrong to name it.

## 2026-09-13cb — OWNER (verbatim, on 13by): "Ahh, but like with the people on the ground problem, many placements of the same object can't just be set to 'on ground' because they have to stay relative to the object family they're grouped with, otherwise they are back to being on the actual ground, rather than 'floating' on the second floor of the terminal where the author placed them. Right?" — RIGHT. 13by stated the case, not the rule. §16g (5) AMENDED (the third time; this is the law): THE FAMILY RELATION IS THE INVARIANT — a placement in a footprint unit is seated at the UNIT'S DATUM plus its authored offset (its `OBJECT_AGL` / MSL offset, or the height its geometry is authored at above the row), wherever its anchor falls; "on ground" is only the CASE where the terrain at the anchor already equals the unit datum (to `hard_tol_m`, 0.02 m) — the cluster pad under the terminal — and there the row is left alone because rewriting it would change nothing. Everywhere else — an anchor over apron, a road, a sunken pier area, a deck, a terraced pad, any spot where the terrain at the anchor is not the unit's plane — the row is written `OBJECT_MSL` = unit datum + authored offset, so the piece floats on the second floor where the author put it, never dropped to the actual ground. A pack's own `OBJECT_MSL` / `OBJECT_AGL` rows are read as the authored offset RELATIVE to the pack's authored ground (the flat datum the pack was built on), not as absolute elevations to keep — that is the 11b conversion. The writer counts, per airport: placements in a unit / left on ground (terrain = datum) / written `OBJECT_MSL` / converted from the pack's MSL. Told to lane `v2clusterpad` (round 2): the passengers/seats bar is "seated at the cluster plane + their authored offset — on the floor where the author placed them — by whichever row form the terrain at the anchor requires", and a twin with an anchor over apron beside the pad proves the `OBJECT_MSL` branch.

## 2026-09-13ce — v2clusterpad ROUND 3 MERGED (273ce491, lane 04c4bfa6) WITH THE REACH DISARMED: the taxi bar MISSED again under 13cc's two amendments (the no-step-coupled apron excluded from the population; the rows at `apron_trend` 30 via a new `cluster_reach_rulings` weight class): taxi vertices moved 2,815 → 2,651, worst 1.88 → 1.45 m, 1,607 over `hard_tol_m` (bar 0); cluster union spread 1.08 → 2.81 (bar ≤ 1.5 MISSED); `building91` 219.37; apron median |dz| 0.25. THE ATTRIBUTION (three matched one-tree KCLT arms): PAD-ONLY (pad 5,000, reach 0) is BYTE-IDENTICAL to DISARM (`4da4d2811eee` both, graded `bde3f0aff32e`, patch `47c91c99b599`) — THE PLANE MERGE CHANGES NOTHING AT KCLT ON ITS OWN; every metre of flattening and every moved taxi vertex is the REACH's. Why the merge is inert (static): `pads._pairs` decimates a rim over `_MAX_PAIRWISE` (40) — the merged 883-vertex cluster group prices 1,624 pairs of which only 40 CROSS the two faces, and `building91` LOSES ITS OWN PLATE (153 pairwise cap-0 rows → 17 consecutive ones): the merge hands the small pad 40 weak cross links while removing nine tenths of its rigidity — a defect in the merge, not in the ruling. So the reach is the WRONG LEVER and the right one is broken. RULED (Fable): 1.0.328 ships with `cluster_apron_reach_m = 0.0` (DISARMED by law value — PAD-ONLY == DISARM byte-identical, so no taxi movement and no regression) and carries the passengers fix (§16g (5)); ROUND 4 on the same lane: fix `_pairs` for a cluster group (per-face-complete pairs + explicit cross-links between the faces), re-measure the three arms; if the merge then does the work (union spread ≤ 1.5, `building91` on the plane, taxi ≤ 0.02) the reach stays off or comes back short; `building91`'s lift is then the merge's. ALSO LANDED: `obj8_split_report --write-pack` built its OWN `PlacementPlan` and never called `msl_seats_for_dump` — the write half was silently DROPPING every §16g (5) row (first run: "0 rows still carry an elevation" on a run that owed 4,846); fixed to make the same call `build_plan` makes; KCLT round trip: 640 cut files, DSF rewritten, round trip OK, torn seams 0, duplicate rows 0, 11,992 placements read back, 4,872 rows carry an elevation — all written by §16g (5), the terminal's `sala_*` rows at 225.44 / 225.64 (`cluster_pad` + offset). THE PLAN-WIDE GRID REFUTED AND DELETED (OTHH `plan_units` grid 557.5 s vs sweep 485.7 s, identical clusters; the cost is `bodies_of_plan` and the part-box product in `_bind`, not the pairing) — OTHH's plan stage stands at ~809 s vs 249 pre-plan-wide: OWED to round 4 with the `_pairs` fix (the profiling-round item). `Bridge_02` / `Bridge_03` 1.52 / 1.93 named. Suite: next line. `docs/frames.jsonl` committed from the main tree again (lanes' `frames.py register` writes the repo-root registry — by design).

## Tool: obj8_split_report

| `Ortho4XP/tools/obj8_split_report.py` | THE OBJ8 SPLIT, DRY-RUN (spec `object-placement-spec.md` §4 / §6 / §7; owner RULINGS 2026-09-11b) — what a pack's object stage becomes once placements are AGL, objects are cut into their RIGID BODIES and each body carries its own anchor. Reads only a build's own two products — the re-seat plan (`<ICAO>.rebake.json`: the pack read once, its welded parts and the ε-contact graph) and the emitted DESIGN SURFACE (`<ICAO>.graded.json`, whose `building` faces are the object pads and `structure_rim` breaklines the basin walls) — and NEVER opens the pack for writing, never reads the DSF and never builds anything. Prints per placement the bodies, their §6 class, each body's anchor point / reason / authored offset, the files that would be written and the placements KEPT WHOLE with the reason (`one_body`, `anim`, `unparsable`); `--write-into DIR` writes every cut file into a scratch dir and parses each back through `airport/obj8.parse_obj8` (LEMD 13,924 files, OTHH 65,360, all parsing back with the written triangle count, 2026-09-11); and prints §7's CENSUS — the design surface at a body's ANCHOR against the surface under each of its ground-contact FEET, the |Δ| histogram `seat_feet_census.py` prints from a mesh and a seat result, read instead from the plan and the design surface so the two are comparable. A foot or anchor outside every graded face reads `off-surface` and is never guessed at (the DEM governs there and this tool does not open the DEM). `--no-cut` for body counts only, `--filter`, `--json`, `--split-tol` to override `[placement] split_tol_m`. ROUND 2 (owner RULINGS 2026-09-11e, spec §9): the bodies are COARSENED (bodies of one placement whose intended-zero terrain heights agree within `split_tol_m` are one file, the senior body's anchor; an elevated body joins the nearest ground group) and each anchor is the GENERIC one (the footprint point where the design surface equals the body's zero; a body with authored relief beyond its skirt takes its low-side foot and is reported with the residual) — LEMD 302 placements -> 985 files (3.26x), OTHH 954 -> 1,172 (1.23x). §13 (owner RULINGS 2026-09-11r/s): an ELEVATED body — one whose lowest authored vertex, or the `y_zero` of the anchor the generic rule gives it, stands above `[rebake] elevated_base_m` — NEVER has a file of its own; it joins its CARRIER (the same placement's ground body with the largest plan overlap, else the nearest) at its authored offset, and a placement with NO ground body is KEPT WHOLE with reason `footless`. The report prints the two classes by name — `elevated bodies as own files` (BAR 0) and `footless placements kept whole` — because the FEET histogram cannot see this defect: the writer shifts an elevated body so its own lowest vertex lands on the terrain and every foot then reads perfect (LEMD's 218 roofs/decks/tower parts censused green while the sim was broken). Measured on matched pack copies: LEMD own-files 278 -> 0, files 1,099 -> 828, feet > 3 m 1,060 -> 151, worst 34.06 -> 13.75 m; OTHH 1,203 -> 333 files, feet > 3 m 952 -> 6. ROUND 3 (owner RULINGS 2026-09-11f, spec §10): the write half RESTORES every `<obj>.anchor_bak` in the pack before any file is written (counts in the plan's provenance), and a LINE OBJECT authored as one component is cut into SEGMENTS by triangle station (`--line-segment M` overrides `[placement] line_segment_m`; 0 disarms it) — LEMD 897 segments from 271 one-line bodies, 985 -> 1,086 files, census `> 3 m` 30 -> 25; OTHH 1,187 files, `> 3 m` 0. `--write-pack PACK_COPY` runs THE WHOLE WRITE HALF into a pack COPY through `airport/placement_write.apply_plan` (cut files, DSF + backup + provenance, dump-cache refresh, `o4_v2_placement_<ICAO>.json`) and reads the written DSF back; it REFUSES a live X-Plane install. The census also splits the feet over 0.3 m into BURIED (lawful) and FLOATING (the defect the eye reads). `--rows SUBSTR,SUBSTR` (lane `v2canopy4`) prints the PER-BODY rows of the placements named — the body's anchor (point, surface z, `y_zero`, reason), its ground-contact feet, its worst foot signed with |Δ|, and the 0.3 m verdict — for the owner's named sites (`OldTerminal_FSX-LEMD38,-LEMD84,-LEMD60`); it is a PROJECTION of the one census pass, never a second instrument (the bins, feet and worst list are identical with and without it, twinned). §14 (owner RULINGS 2026-09-11u/v, lane `v2carrier`): a FOOTLESS placement is CARRIED — written as a body file at its CARRIER's anchor with the carrier's `y_zero` (the footed body of its UNIT it abuts with the largest contact, else the nearest, else the largest) — a BASIN resource is never split and anchors at a RIM point where the design surface equals its zero (`rims` wired at last), and bodies of one resource that OVERLAP IN PLAN bind whatever the contact graph says. The report prints the four §14 bars (`footless at datum` 0, `footless on ground` 0, `basin bodies split` 0, `spread`) beside §13's, from `airport/placement_carrier.census_v14` — the same call `seat_feet_census --placement-plan` makes over the same plan shape, so the two instruments are one code path. Measured on the app's 1.0.315 LEMD frame: the four footbridge resources at the terminal's zero 616.65 (deck bottom road + 4.4-5.0 m, was ON the road), `Terminal4SAT_pink-LEMD01` at its terminal's 597.43, the basin's three resources one file each on ONE rim vertex (zero spread 7.0 m -> 0.00, parapet +2.99 above the rim), files 828 -> 855, round trip OK, row census `> 3 m` 17. Twin: `tests/auto_patch_v2/test_v2objsplit.py`. §15 (owner RULINGS 2026-09-11ae, lane `v2roofcarrier`): the CARRIER IS WHAT THE BODY STANDS OVER — chosen across the whole UNIT, every resource alike, by largest PLAN OVERLAP beneath, else largest contact, else nearest (§13's same-placement scope and §14's contact-first order are superseded; the pack names its roofs as their own resources, so the walls a roof rides are almost never its own file); the plan-overlap BOND is RE-CUT where a bound group's intended zeros span more than `split_tol_m` (a rigid body is never wider than the terrain it can stand on; BASIN exempt); DUPLICATE ROWS of one resource identical in lon/lat/heading are ONE placement, all of them replaced (`--write-pack` reports `duplicate rows of a SPLIT placement ... surviving after the write`, bar 0); an anchor or foot on no graded face is marked OFF-SHEET and excluded from every comparison and bar; and the report prints §15 (3)'s `stands-over float > 0.5 m` from `airport/placement_carrier.census_v15` — `float = zero - zero_beneath`, the class NEITHER the feet histogram nor §14's bars can see (a carried body has no feet at all), barred at 0 for CARRIED bodies and reported for footed ones. §16 (owner RULINGS 2026-09-11ai, lane `v2skipped`): the report adds the POPULATION census (`placement_carrier.census_population`: `rows on the datum outside the plan` — the resources the SEAT-era thickness gate dropped, which keep the pack's shared-datum row and render where the datum is, bar 0 — beside the lawful skips and the multi-anchor class, reported not barred) and `census_v16`'s `float = zero - ground_under_geometry`: the ground read under the body's OWN parts (`geom_box` / `foot_boxes`, the median of the part-box centres) and never under its carrier's box — `CARRIED bodies whose carrier's zero is over 1 m from the ground under their own geometry` (bar 0; LEMD 39 -> 0 on matched arms) and `files whose own-geometry ground departs over 3 m from the ground at their row` (26, reported). `--admit-skipped PACK_ROOT` puts the thickness-gated resources of a PRE-§16 plan back into the population by reading their rows from the pack's own DSF (one part per component, no contact graph, the member id IS the DSF row index) — what a build's own plan now carries, for replaying a plan written before the switch; LEMD 25 resources / 25 rows, OTHH 99. §16a (owner RULINGS 2026-09-11aj, lane `v2skipped2`): a CARRIED body is cut where its CARRIER is cut (one piece per carrier terrain group its own triangles stand over, each riding that group's zero; never by the ground under itself), the ground check moved to the carrier's OWN feet (`Candidate.ground_off`, `surface(foot) - y_foot` against the body's zero), and `census_v16`'s carried number demoted to INFORMATION — the bar for a carried body is §15 (3)'s `zero - zero_beneath`. The report prints `carried bodies left uncut by the ground` / `cut by their CARRIER into N piece(s)` and, beside the §15 bar, how many of the carried floats stand over a body the law REFUSES as a carrier. LEMD carried float 58 → 4, files 1,591 → 1,328, plan stage 9.9 → 6.3 s; OTHH 7 → 39, 46.4 → 60.2 s (both OTHH bars missed and reported). 11ak (lane `v2skipped3`): the CARRIED bar's `beneath` is the carrier THE LAW CHOSE (`merged_into`, resolved by identity over every row that reads a zero — a carrier written WHOLE names its MEMBER RESOURCE, which is the whole of OTHH's residual), and a body the law REFUSES as a carrier is counted and named as its own class, `carried over a refused body`, with how far its own feet stand off; §16 (2) also cuts BY FOOT (`placement_cut._LineCutter.foot_groups`: the feet grouped by the zero each says the body has, `surface(foot) - y_foot`, each triangle joining the group of the foot nearest it in plan) — the class no ground cut can see, a body whose FEET are authored over metres of relief on terrain that barely moves, which is exactly what §16a (2) refuses. The re-cut line prints the three cuts (terrain / triangle / foot). LEMD carried float 4 → 0, refused carriers 117 → 21 (13 of the residue are rim-anchored BASIN bodies the foot cut is exempt from), files 1,328 → 1,371, plan stage 6.2 → 5.66 s; OTHH carried 42 → 0, refused 55 → 19, files 1,679 → 1,622, plan stage 59 → 31 s (`solid_components` read in one sort instead of a mask per component; `bind_plan_overlaps` swept by the hull's south edge). 11al (lane `v2basincarry`): a BASIN body is EXEMPT from §16a (2)'s ground test — its zero is the RIM (§14 (2)) and its floor feet are authored below it by construction — so it may carry, and the report prints `§16a (2) basin carriers` (how many basins, how many the feet test would have refused) beside the refusal set: LEMD refused carriers 21 → 8, OTHH 19 → 4, carried float 0/0 unchanged. §14a (owner RULINGS 2026-09-11ap item 6, lane `v2basinring`): a BASIN body follows its RING. §24 (1) puts the rim vertices at the APRON's level, so the ring is not level (LEMD's T4 pit 597.68 … 599.52 over 59 nodes) while §14 (2) wrote every basin body at ONE rim point — the owner's "gap between wall and apron", +0.71 / −1.13 m, while the §14 `spread` bar read 0.01 because it measures the pit's bodies against EACH OTHER. `airport/basin_ring.py` (NEW: the whole law — `arcs_of`, `ring_arcs`, `member_kind`, `ring_bar`) cuts the ring into ARCS whose z agrees within `split_tol_m` and cuts each basin body's WALL BAND by them, one piece per arc anchored at that arc's rim point (the interior remainder keeps §14 (2)'s single point: the trench floor is one level); and a member authored AT THE RIM PLANE but standing inside the ring is a FLOOR body that takes §16 (3)'s ground under its own footprint, never the rim, never a carrier. The report prints the RE-DEFINED bar — `§14a spread of a BASIN RING = max |wall base − ring z| over its nodes` (bar ≤ `split_tol_m`), with the nodes on an arc the pit has NO WALL on reported beside it — and the `§14a basin FLOOR members` / `basin bodies cut by the ring's ARCS` counts. It needs the rings WITH their heights (`census_v14(rims=..., arc_cap=..., counts=...)`; `RimRing.z`, and the `basin_arc_wall:<ref>#<k>` counts keys the cut writes are how the bar tells "no wall here" from "the wall is written in the interior piece"). Matched arms on the app's 1.0.319 LEMD frame: the ring bar 1.12 m / 9 nodes over → **0.18 m / 0 over**, `LEMD13__b0` off the rim and onto its own ground, files 1,371 → 1,394, feet > 3 m 518 → 412, floating 9,509 → 9,014; OTHH's 21 basin carriers and its whole foot census byte-identical. §16b (owner RULINGS 2026-09-11ap, lane `v2owncut`): the TERRAIN CUT IS PRIOR AND UNIVERSAL and is read on the body's OWN WRITTEN TRIANGLES — including everything the writer will put in the file (`placement_cut._LineCutter.all_tris`: a placement the plan reads as ONE body is written as the WHOLE object, which is why `green-TEJ3`'s 4-triangle part read 0.22 m of ground while its 2,342 m file stood +16.22 m over it) — so a CARRIED body is divided by the ground under itself first and §16a (1)'s carrier cut runs inside each piece; §9's coarsening additionally requires PLAN CONTIGUITY (`[placement] coarsen_reach_m`, 30 m) and acts WITHIN a terrain group (the pieces carry the ground they stand on, or the very next pass welds them back); each PIECE finds its own carrier, and a FALLBACK candidate (contact / nearest / largest, no plan overlap) is refused unless its zero is within `split_tol_m` of the ground under the piece (`carrier_refused_far_from_carried_ground`). The report prints `census_v16b`'s two bars over the WRITTEN geometry the plan now publishes per body (`geom_pts`, one sample per 10 m cell, thinned to 32 by the farthest-point walk): `carried piece float over its own ground > 0.5 m` and `body wider than its terrain group`, both bar 0, with the BASIN exemptions (§14 (2) / 11al) counted apart and the wide residue split by class. `--coarsen-reach M` overrides the contiguity reach. Measured on the app's 1.0.319 LEMD frame: the owner's item 3 +10.74 → the plate ON the roof beneath it (618.58 vs the group's 618.60), item 5 +16.22 → 620.38 vs 620.27, `Terminal4_48` zero-vs-ground −4.02 → median −0.01, `Taxisigns-SENRG` 38 of 80 bodies over 0.3 m → 12 of 419; files 1,371 → 3,272 at the amended 100 m reach (4,633 at the refuted 30 m), plan stage 5.6 → 10.1 s (bar ≤ 8 s MISSED, reported). §16c (owner RULINGS 2026-09-12b/12d, lane `v2atom`): THE CONNECTED COMPONENT IS THE ATOM — `--torn-seams PACK_ROOT` prints the TORN-SEAM CENSUS over a WRITTEN pack (the plan argument is then the WRITTEN `o4_v2_placement_<ICAO>.json` and `--graded` is not read), and the same census prints automatically after `--write-pack`: sibling files of ONE placement that share an AUTHORED VERTEX (the key `obj8.solid_components` welds on, `round(x, 3)`) are two halves of one connected solid written at two zeros, with the base step per seam, the step histogram, the worst list and the per-class breakdown, and §10's line segments / §14a's basin arcs — the only lawful station cuts — counted APART.  Two bars, both 0: `torn seams outside line/arc pieces` and `single-component resources in >= 2 files`.  The instrument is the scout `v2lemd320`'s `tear.py`, promoted on its second use, and lives in `airport/placement_seams.py` (`census_torn_seams` / `census_torn_seams_lines`, re-exported through `placement_census`).  Measured on the live 1.0.320 LEMD pack it reproduces the owner's four sites exactly (`HANG3` 10 files / 14 seams worst 3.05 m; `green-LEMD50` 7 / 11.12 m; `Bridge2` 8 / 11.72 m; `green-STRT4` 53 files, `__b44` 16.29 m) and the class (2,554 seams, 1,994 over 0.30 m).  On matched replay arms the law takes LEMD 723 -> **0** seams and 128 -> **0** single-component splits (files 3,253 -> 2,804, plan stage 13.5 -> 10.2 s over 3 runs, round trip OK), OTHH 639 -> **1** and 165 -> **1** (files 1,897 -> 1,898). §16c (6) (RULINGS 2026-09-12h, round 2): `--contact-eps M` overrides `[placement] contact_eps_m` (2 mm) — components of ONE resource whose geometry comes within it, or whose parts the rebake plan's ε-contact graph already links, BIND into one rigid body for anchoring (one zero, the senior component's carrier): OTHH's `OTHH_Fuel_02_LOD0_007` carries two components 0.4 mm apart that the millimetre weld key reads as separate.  LEMD files 2,804 -> 2,776, seams stay 0, `Terminal4_48` zero spread 3.58 -> 0.69 m, plan stage 9.6 s (main 13.5). ROUND 3 (RULINGS 2026-09-12j): the entry now runs inside `harness/shared_repo_guard`'s WRITE GUARD and its before/after audit (a round-2 OTHH `--admit-skipped` run had created `Airport_mod_cache/Global Airports/+25+051.dsf.e0518fe0.text` in the SHARED repo with both lane-local cache env vars exported and nothing refused it); every run prints `[guard] shared repo UNCHANGED`.  `--rigid-reach M` overrides `[placement] rigid_reach_m` (2.0) — §16c (8): SOLID components of one resource within it chain into ONE rigid cluster, which is the atom of the BODY as well as of the cut (LINE objects excluded).  `carrier_fill_min` is DELETED from carrier candidacy (§16c (7)); the CLASS exclusion stays.  LEMD: `HANG3` 6 files / 1.37 m -> 2 / 0.45, `green-STRT4` 23 -> 15 files (spread 8.90 -> 3.73), files 2,776 -> 2,121, §16b wide 1,405 -> 967, seams 0, round trip OK; five largest rigid clusters are all SINGLE components (5,157 / 2,890 / 2,514 m — fences and VOR markers, not chained) and `green-TEJ3` stays 9 components / 9 clusters. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. **§17 CRITICAL MOTION IS READ** (owner RULINGS 2026-09-12am (2), lane `v2objmotion`): the graded surface's FACE ROLE under every foot (`airport/placement_boxes.GradedRoles` / `graded_roles_from_doc`, built from the SAME parsed `<ICAO>.graded.json` the sampler and the pads are, senior face by `precedence.toml`'s authority order, a 55 m grid over the faces' boxes) joined to §7's own float there (`airport/placement_motion.census_motion`, re-exported through `placement_census`): a body with a foot on a ROLLED-ON face (`law.tables.rolled_on_roles`) is ON PAVEMENT and every such foot is judged at `[cockpit] motion_step_m` 0.05 m, named with resource, foot coordinate, face role and SIGN. The block prints the count of bodies on pavement, the feet over the threshold, the worst ten, and the breakdowns by resource / face role / body class / anchor rule / size band, plus what the EYE reads at those feet (floating vs buried over `visual_m`) and the MEDIAN-anchor arm. BASIN bodies are counted APART (§14 (2) / 11al: a pit's zero is its rim and its floor feet are authored below it — they were LEMD's whole worst ten). Measured on the 1.0.320 LEMD frame: 493 of 2,153 bodies stand on pavement, 7,124 feet on 399 over 0.05 m; after the §17 anchor rule 6,635 on 407 (OTHH 6,234 → 3,877 on 113 → 103). RULINGS 2026-09-12ap (lane `v2pavefeet`): `--motion-rows OUT.json` writes §17's PER-BODY projection — one row per written body with its anchor, class, anchor reason and every ground-contact foot (lat/lon, authored y, surface z, face role, on-pavement, float) — the rows `census_motion` itself reads, never a second census (the scout's scratchpad projection, promoted on its second use). (E) THE SAMPLER HONOURS GRADED HOLES: a Delaunay over the emitted VERTICES spans a hole ring with triangles reaching from an apron vertex to a trench vertex, and LEMD read **592.22 m at a point whose ROLE is apron** six metres outside the hole — 12ap's two worst pavement feet (`LEMDblast__b1` +7.18, `Terminal4sBlue-STRT4__b1` −5.08) were that fabricated ramp, and the anchor correction is 6.91 m. A simplex CROSSING a hole ring with a step over `split_tol_m` is struck and a point inside one reads the nearest vertex of that simplex ON ITS OWN SIDE of the ring; measured narrowings: "centroid on no face" struck 8,689 of 47,287 simplices and cost 421 files / 435 off-sheet bodies, and a strike with no side-aware read cost 160. (B) §17 is judged at the GROUND-CONTACT feet — the in-band feet within `split_tol_m` of the lowest (`placement_motion.ground_contact_feet`); `contact_band_m` is shared law and unchanged, BOTH sets are sampled and the wider reading prints beside the judged one so the report states its own attribution. (A) `bind_ground_m` (`[cockpit] visual_m`) bounds §16c (7): a FOOTED body of ANOTHER member keeps the cluster only while its own zero is within it of the senior's, else it keeps its own anchor and is counted — the report prints `bound refused for ground N` with the worst refused disagreement and the widest RETAINED cluster zero-plane span. Matched arms, LEMD main → branch: CRITICAL MOTION 6,640 → 5,400 feet on 407 → 356 bodies, over 0.5 m FLOATING 663 → 128 and BURIED 1,109 → 808 (of which (B) alone 581 → 128 / 816 → 808), worst pavement foot +7.18 → +2.41 m, 74 binds refused (worst 2.38 m), files 2,107 → 2,149, seams 0/0, round trip OK, plan stage 10.19 → 10.03 s; OTHH 3,891 → 2,822 feet on 103 → 74, floating 332 → 12, §14 footless at datum 5 → 4, files 1,252 → 1,269, plan stage 60.8 → 61.4 s (the ≤ 60 s bar missed on BOTH arms). §16b's carried-piece float and wide counts move the WRONG way at both airports (LEMD 111 → 119 / 967 → 983, OTHH 126 → 135 / 75 → 78) and are named. §16d (owner RULINGS 2026-09-13h, lane `v2unboxed`): THE PLAN BOXES WHAT THE WRITER WRITES — a WRITTEN-FRAME bar beside the torn seams, `§16d bodies with written geometry > 1 m outside their geom_box` (`airport/placement_seams.census_outside_box`, printed after `--write-pack` and by `--torn-seams`, bar 0): `geom_box` was the hull of the ADMITTED PARTS while the writer emitted the source object's triangles regardless, so a component no part named (the FS2XPlane origin plate, an exporter's ground paint, a roof plate over the next hangar) rode a zero the body chose elsewhere and NO instrument read it — LEMD 1.0.325 live pack 378 of 2,109 bodies, 8 over a kilometre. Every connected component the writer will emit — draped ones included — is now PLACED: within `coarsen_reach_m` of a ground group's part hull it joins that group and `geom_box` grows to the hull of what the file will contain; beyond it, it is a FOOTLESS BODY §15's search places, or §16 (3)'s own ground (`--coarsen-reach 0` disarms the reach and the component joins the nearest body, the pre-§16d reading). The nearest-footed fallback is CAPPED at the same reach (`carrier_refused_nearest_beyond_reach`), and the COCKPIT block names the worst row by the centre of the BODY'S OWN written geometry, never the placement row (a shared-datum pack puts 96.5 % of its bodies on two points). `plan stage: N.NN s` is printed after the split — the number a round's budget is quoted in, timed exactly where the shipped engine's own `build_splits` call is, without the graded parse or the census. Matched dry arms on the 1.0.325 LEMD frame (the app's own arm reads a MESH sampler where the tool reads a Delaunay over the graded vertices — the two disagree on every surface-driven refusal and the bars are read dry-to-dry): outside-box 390 → **0**, nearest-footed over 100 m 29 → **0**, the four shadow plates +15.94/+15.73/+5.77/+1.72 → **−5.00 on their own ground**, `Cargo-TEJ1` on `NEWCO__b9` roof base 604.95 (bar 0.3 of 605.04), seams 0/0, §15 carried float 0/0, round trip OK, files 2,141 → 2,279, LEMD plan stage 13.6 → 17.8 s and OTHH ≈83 → 86.1 s (both bars missed on BOTH arms, named). It also fixed a latent WRITER defect: the cut file was named by its index in the LIVE body list while the DSF row is written on the plan's `body_id` name, so a body the cut left with no triangle shifted every later body's file one name down (`OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s object). §16d (4)-(6) (owner RULINGS 2026-09-13m, same lane, second frame KCLT 1.0.324): a CARRIED body's components group BY CARRIER — each ATOM (§16c (1)'s, so a rigid cluster is never divided) asks its own carrier question BEFORE the search, counted as `carried bodies cut by ATOM`, where §16a (1)'s after-the-fact cut could only divide the answer the whole body got (KCLT 5,295 carried bodies left uncut against 3 cut; a native pack's master roof model spans 1,774 m); §16c (7)'s 0.5 m ground bound is MEMBER-AGNOSTIC (12ap tested `member != top.member`, and a native pack's one-model-per-material member spans the airport: KCLT's `005_ALB__b9` sank 5.04 m into its pad on a same-member bind to an apron body 500 m away); and a FOOTED body whose ground contacts lie mostly inside one emitted `building` pad reads only the contacts ON it (`anchor_rule.pad_majority`; the anchor reason then says `on pad <ref>`). Matched dry arms at KCLT: `005_ALB__b9` -5.85 -> **+0.02** against its pad, widest retained cluster zero span 5.69 -> **0.64 m**, 473 carried bodies divided by atom, 61 bodies anchored on their pad, `building80`'s on-pad zero spread 1.03 m (the pad's own relief 1.19), §16d outside-box **0**, §15 carried float **0**, round trip OK 477/477, one new torn seam (+0.16 m, one shared vertex, named), files 473 -> 477, plan stage 8.65 -> 8.3-8.5 s. It also exposed a defect the atom cut made visible: a target group holding BOTH a cut piece and an untouched raw was read for its `tris` alone, leaving 990-3,280 triangles per placement claimed by no body (9 of KCLT's 103) for `obj8_split` to hand to the nearest one — the audit reads 0 of 103 after. **COST: plan stage LEMD 17.8 -> 25-46 s and OTHH 86 -> 136 s** (KCLT flat) — the per-atom carrier search, narrowed by a `coarsen_reach_m` span gate, a 64-atom cap, per-atom pids and a set-intersection contact count, and still needing the owner's approval and a Fable-5 review before it ships. |

## Tool: seat_feet_census

| `Ortho4XP/tools/seat_feet_census.py` | THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3); the placement reading 11e (3), spec §7/§9) — `--placement-plan o4_v2_placement_<ICAO>.json` with `--mesh` (a built mesh) or `--graded` (the emitted design surface, for a dry run with no tile built): per placement of the plan's own rows, `surface(foot) − (surface(anchor) + y_foot)`, the |Δ| histogram (<0.3 / 0.3-1 / 1-3 / >3 m), the same by class, the worst N with lat/lon, and §13's elevated-body / footless-carrier bars. Feet are read from the AUTHORED pack (`.anchor_bak` when one exists). THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8) — the name is kept because the INDEX row, `obj8_split_report` and the twins address it by it. Writes nothing to the pack. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. CRITICAL MOTION is named as an instrument limit rather than printed as a zero HERE: §17's motion reading needs the graded face ROLE under each foot, and this tool hands the block none — `obj8_split_report.py` is the entry that takes it (owner RULINGS 2026-09-12am (2), lane `v2objmotion`). §16e (owner RULINGS 2026-09-13k, lane `v2othhdatums`): `--placement-plan --mesh` WAS BROKEN — it passed its bbox as `(lat, lon)` to `MeshElevationSampler`, which takes `(min_lon, min_lat, max_lon, max_lat)`, so at OTHH it asked for a box at lon 25.2 / lat 51.6 and the sampler raised `no mesh triangles inside ... — wrong tile?`; the one place the two orders meet is now `plan_bounds()` and a twin holds it end to end over the sampler's own mesh fixture. The report also prints `§16e bodies on a DATUM` (a crest plate / a deck top) as its own class and EXCLUDES them from §13's `elevated bodies as own files` bar: a datum body's `y_zero` is +5 … +10 m by construction, and counting it there reported the law as the defect (OTHH 0 -> 10 -> 0 with the class printed apart). §16e (3) (Fable 2026-09-13, RULINGS 2026-09-13v, lane `v2bridgecontact`): the report also prints THE BRIDGE FAMILY block (`airport/bridge_family.census_bridges` / `census_bridges_lines`, re-exported through `placement_census`, the same call `obj8_split_report` makes over the same plan shape) — per `Bridge_NN` the deck's own body's world DECK TOP against the land under that bridge's own written geometry (`|deck top - highest land|`, bar `[cockpit] visual_m` 0.5 m), the PER-PLACEMENT zero spread (`max - min` of `surface_z - y_zero` over one placement's bodies; `Bridge_02_CLUTTER_007` is six piers of ONE solid), the CROSS-BRIDGE carriers (a body whose `merged_into` names a file of another bridge, bar 0) and how many bodies publish `bridge_of` and agree with the resource's own tag. The `Bridge_NN` axis is the CENSUS's, never the law's — §16e (3) exists because the name does not name a bridge — so the agreement count is the instrument's own check on the derived relation. Measured on the app's 1.0.326 OTHH frame: `Bridge_01` deck top 3.23 -> 3.96 and `Bridge_04`/`Bridge_05` KEPT -> 3.96 (all three |deck top - land| 0.00, PASS), cross-bridge carriers 2 (unchanged — the bind and the filter are refuted and deleted, see `bridge_family`'s module doc). |

## Tool: build_airport.py

| `Ortho4XP/tools/harness/build_airport.py` | You need to BUILD anything for measurement: one airport patch, a constant-DEM oracle world, or a whole tile. Enforces the build cwd, refuses a cold DEM/inset frame, a drifted config frame, a PRIVATE data corpus and any implicit download into the shared repo; guarantees the axes sidecar; wraps the run in the ledger; audits the shared repo before/after; and records the env, DEM-frame and data-mount snapshots every later claim depends on. It also refuses a DEGRADATION THE ENGINE SWALLOWED (2026-08-07): `auto_patch.elevation._load_airport_dem` runs production's whole DEM prep inside one `except Exception`, so a write the shared-repo guard blocked became a WARN line, `dem_inset_provenance: null` and a build that exited 0 on 18.5 k nodes against production's 34-36 k (measured at HECA, `tmp/sliver_attrib`). Two independent detectors close it — a write the guard blocked during a build that nevertheless returned, and a laylane carrying no DEM provenance at all — and either refuses BEFORE the patch is written, so a DEM-less `.osm` never lands where a census would find it. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. The mod-cache redirect is also handed to v2's own loader (`inputs.mod_cache_root`), which `planar.__main__.default_inputs` cannot do for itself — it reads no environment by design, so before 2026-09-13 the pack-dump FRESHNESS guard (`airport/load.py:289`) judged the SHARED root and refused every KCLT / HECA v2 build and `explain` (RULINGS 2026-09-13q, "chip"); the build now reads and derives its DSF text dumps in the same lane-local overlay every other derived cache lands in. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. |

| `Ortho4XP/tools/harness/build_airport.py` | **Default.** See above. |

## Registered frames: SPJC

SPJC  patch    base 95c78040   lane v2spjc327        2026-09-13T15:52:21  /tmp/harness/SPJC_20260913T154126.osm  — scout v2spjc327 SPJC build 2026-09-13, rc0 121.7s, body_sha e61277b2bbbc, artifact 7857e8587009, solve=feasible, guard UNCHANGED; reproduces owner 1.0.327 tile -13-078 structures line exactly
SPJC  graded   base 95c78040   lane v2spjc327        2026-09-13T15:52:21  /tmp/harness/SPJC_20260913T154126.v2/SPJC.graded.json  — scout v2spjc327 SPJC build 2026-09-13, rc0 121.7s, body_sha e61277b2bbbc, artifact 7857e8587009, solve=feasible, guard UNCHANGED; reproduces owner 1.0.327 tile -13-078 structures line exactly
SPJC  rebake   base 95c78040   lane v2spjc327        2026-09-13T15:52:21  /tmp/harness/SPJC_20260913T154126.v2/SPJC.rebake.json  — scout v2spjc327 SPJC build 2026-09-13, rc0 121.7s, body_sha e61277b2bbbc, artifact 7857e8587009, solve=feasible, guard UNCHANGED; reproduces owner 1.0.327 tile -13-078 structures line exactly
SPJC  patch    base 0c86fe2c   lane v2spjc           2026-09-13T17:03:04  /tmp/harness/v2spjc-r2.osm  — lane v2spjc closing SPJC build on claude/v2spjc 1992e754 (base main 0c86fe2c): rc0 111.2s, body_sha 0c903ea7b254, artifact 60993cdd0302, solve=optimal, guard UNCHANGED; structures bores 10 underpasses 0 tunnels 8 decks 0 refused 6 (scout base 95c78040: 59/19/18/4/31)
SPJC  graded   base 0c86fe2c   lane v2spjc           2026-09-13T17:03:04  /tmp/harness/v2spjc-r2.v2/SPJC.graded.json  — lane v2spjc closing SPJC build on claude/v2spjc 1992e754 (base main 0c86fe2c): rc0 111.2s, body_sha 0c903ea7b254, artifact 60993cdd0302, solve=optimal, guard UNCHANGED; structures bores 10 underpasses 0 tunnels 8 decks 0 refused 6 (scout base 95c78040: 59/19/18/4/31)
SPJC  rebake   base 0c86fe2c   lane v2spjc           2026-09-13T17:03:04  /tmp/harness/v2spjc-r2.v2/SPJC.rebake.json  — lane v2spjc closing SPJC build on claude/v2spjc 1992e754 (base main 0c86fe2c): rc0 111.2s, body_sha 0c903ea7b254, artifact 60993cdd0302, solve=optimal, guard UNCHANGED; structures bores 10 underpasses 0 tunnels 8 decks 0 refused 6 (scout base 95c78040: 59/19/18/4/31)

## Registered frames: HECA

(none registered)

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

## Registered frames: OTHH

OTHH  rebake   base 05050624   lane v2unboxed        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/unboxed  — KCLT 1.0.324 / LEMD 1.0.325 / OTHH 1.0.326 rebake frames + dry arms
OTHH  capture  base 7949757a   lane v2othh327        2026-09-13T16:30:07  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othh327/OTHH.pkl  — v2_solve_replay --capture OTHH on main 7949757a (402 s); solved arms beside it: OTHH.solved.pkl (base) and OTHH.nofeet.pkl (--drop-generator foot_rows)
OTHH  patch    base a0f65165   lane v2cutfeet        2026-09-13T17:37:22  /tmp/harness/OTHH_20260913T171324.osm  — closing build of lane v2cutfeet (§11b (7) cut foot verdicts), rc 0, 968.0 s, ways 1097, body_sha 0ff85d1a7bff, artifact ledger 86493fdab68b; matched replay arms on the v2othh327 capture live in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cutfeet/out (OTHH.base.pkl / OTHH.cut.pkl / othh.base.json / othh.cut.json / *.log), KCLT arms beside them
OTHH  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_OTHH/structures.json  — OTHH planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_OTHH: basins array BYTE-IDENTICAL; only one sunken_refused message rounds 50%->49% roofed, same verdict

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

