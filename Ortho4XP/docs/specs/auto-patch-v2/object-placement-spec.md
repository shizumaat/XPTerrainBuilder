# Object placement by X-Plane's own draping — split objects, placed anchors, no seat

Owner RULINGS 2026-09-11b (verbatim): "Rather than using MSL elevations, couldn't we just
modify the DSF to remove all hard coded elevations so every object sits on the terrain of
its anchor? X-Plane has the 'on ground' elevation option, then we might be able to avoid
seating objects at all and it could be a simple find and replace. The only edits we would
need to do to objects would be splitting large groups and ensuring each object's anchor
was in the right location." Ruled by interview: switch.

Author: the Fable session (design and review only). Implementers: lanes `v2dsfagl`
(§3, §5) and `v2objsplit` (§4, §6); they meet at the `PlacementPlan` of §2.

## §1 What changes and what stays

| today (09ac–10be) | after |
|---|---|
| the seat SOLVE: feet per body, deltas, plates following walls, plate seats, `_one_file_one_delta` | GONE — X-Plane places each object's origin on the terrain at its anchor |
| the per-vertex OBJ8 rewrite (`VT` y in place, `.anchor_bak`) | GONE for placement; the split writer (§4) writes NEW files instead |
| MSL placements as authored (KBNA 1,154, KMCI 716, KDFW 331, KDEN 126) | `OBJECT` (AGL) — a find-and-replace in the DSF text (§3) |
| one mega-object, one anchor kilometres from its far components (Aerosoft LEMD, 3,021 AGL placements, floats anyway) | one object per rigid BODY, each with its own anchor placed where the terrain equals its intended zero (§4, §6) |
| body formation: touching bodies (10i, 10aa), line objects (10bb), skirts (10ag), basins (10ba), elevated decks abutting a kerb (10ay/11a) | KEPT — these ARE the split rules |
| the design surface: pads for skirt-less buildings (09c, 10l, 10y, 10bd), basins cut to the object's depth (10ba), rims at the pavement (10an/10ar) | KEPT — X-Plane drapes onto it |
| the DSF text dump cache (09ac: `find_text_dump` refuses a stale dump) | the WRITE path re-encodes; the cache re-keys on the new mtime |

Why it is simpler: X-Plane already samples the terrain at every AGL anchor. The only thing
our seat ever computed was "how far is this body's zero from the terrain at its anchor" —
which is zero by construction once the anchor is under the body and the body is small
enough that one terrain sample describes it.

## §2 The `PlacementPlan` (the interface between the two lanes)

`model/placement.py` — a frozen dataclass, JSON-serialisable, written beside the patch
as `o4_v2_placement_<ICAO>.json` (replaces `o4_v2_rebake_*.json`):

```
PlacementPlan
  pack_root, dsf_path, dsf_backup_path, provenance (sha of the dump, engine version, law digest)
  conversions: [ {index, resource, lon, lat, heading, kind_before: "OBJECT_MSL"|"OBJECT_AGL", z_before} ]   # §3
  splits:      [ Split ]                                                                                     # §4
  kept:        [ {index, resource, reason} ]     # placements left exactly as authored (stock library objects — 09z (2); objects with no genuine solid; bodies that cannot be cut, §4.4)

Split
  placement: {index, resource, lon, lat, heading}          # the ORIGINAL placement it replaces
  bodies: [ Body ]
Body
  body_id, class: "building"|"skirted"|"basin"|"line_segment"|"deck"|"plate_only"|"other"
  components: [component ids in the authored file]
  anchor: {lon, lat, heading}                              # §6
  anchor_reason: text                                      # "low-side foot", "pad point", "rim point", "segment mid-foot", "kerb (merged into <resource>)"
  new_resource: "objects/<stem>__b<k>.obj"                 # §4.3
  authored_offset: {dx, dy, dz}                            # the rigid transform applied to the vertices (authored frame)
```

## §3 The DSF round-trip (lane `v2dsfagl`)

1. **Dump**: the existing text dump (`auto_patch.dsf_reader.ensure_dsf_text_path`, DSFTool
   `--dsf2text`); the read side (`airport/dsf.read_dump`) is unchanged.
2. **Edit** the text: (a) every `OBJECT_MSL idx lon lat hdg z` and `OBJECT_AGL idx lon lat hdg z`
   for a placement in `conversions` becomes `OBJECT idx lon lat hdg`; (b) every placement in
   `splits` is replaced by N `OBJECT idx_k lon_k lat_k hdg_k` lines, one per body, with
   `OBJECT_DEF` lines appended for the new resources (indices assigned at the end of the
   `OBJECT_DEF` list — never renumber existing defs); (c) every other line byte-identical
   (7-decimal coordinates preserved as text, never re-formatted).
3. **Encode** with DSFTool `--text2dsf` into the lane scratch, verify by dumping the result
   again and diffing against the edited text (must be identical modulo DSFTool's own
   canonical spacing — measure and pin), then write into the pack: the original DSF is
   kept as `<name>.dsf.anchor_bak` beside it (the OBJ discipline), a provenance record
   `o4_placement_provenance.json` beside it (dump sha, engine version, law digest, counts).
4. **Idempotence**: a rerun reads the backup as the pristine source (as the OBJ rewrite
   reads `.anchor_bak`), never the already-edited DSF.
5. **Safety**: a lane never writes `/Users/noah/X-Plane 12`; the closing test writes into
   a COPY of the pack under the lane scratch (pack root parameterised). The app's driver
   writes the real pack, as the OBJ rewrite does today.
6. **Consumers** (RULINGS 2026-08-30l table, the lane completes the RULE column): the dump
   cache key (mtime) — refresh after the write; `airport/dsf.read_dump` (new `OBJECT_DEF`s
   and placements must read back); the object-anchor worklist (`o4_object_anchor_worklist.json`);
   `seat_feet_census` (§7); `reanchor_dsf_objects.py` (the v1-era tool — retire or route
   through this writer, never a second writer); the Swift app's console lines.

## §4 The OBJ8 split writer (lane `v2objsplit`)

1. **Input**: the pristine OBJ8 (`.anchor_bak` if present, else the file) parsed by
   `airport/obj8.parse_obj8`, and the bodies of §1's rules (`emit/clusters` body formation,
   `airport/line_object`, `airport/skirt`, `airport/basin_witness`, the deck gate of 11a).
2. **Cut**: a body is the set of `TRIS`/`IDX` ranges whose vertices belong to its components.
   The OBJ8 is a header (`TEXTURE*`, `POINT_COUNTS`), a `VT`/`VLINE`/`VLIGHT` table, an
   `IDX` table, then commands (`TRIS`, `LINES`, `ATTR_*`, `ANIM_*`, `ATTR_LOD`). The writer
   walks the command stream once and emits, per body, the commands whose TRIS ranges fall
   in the body, re-indexing VT/IDX to the subset, copying every `ATTR_*` in effect at that
   point (attribute STATE is re-emitted at each body's first command), and copying
   `ATTR_LOD` brackets whole.
3. **Transform**: every kept vertex is translated by `authored_offset` so the body's new
   anchor is the origin (heading unchanged: X-Plane rotates about the anchor, so the
   translation is in the authored frame, computed from the anchor's authored (x, z) and
   the intended zero y — §6). Normals unchanged. `POINT_COUNTS` recomputed.
4. **What cannot be cut** (reported, placement KEPT whole): a body whose TRIS lie inside an
   `ANIM_begin … ANIM_end` block shared with another body (an animated door on a wall of a
   different body) — cut at ANIM block granularity instead: the whole block goes with the
   body owning most of its triangles; a body that would still straddle a block is not split
   and the placement is kept (§2 `kept`, reason `anim`). `ATTR_LOD` blocks are copied per
   body (a body appears in every LOD bracket it has triangles in).
5. **Naming**: `objects/<stem>__b<k>.obj` beside the original; the original file untouched
   (no `.anchor_bak` needed — nothing in it changes); textures referenced by the same
   relative paths.
6. **Provenance**: the split list in the `PlacementPlan`; a body's new file records its
   source and offset in a comment line after the header (`# o4 split of <stem> body <k> offset dx dy dz`).

## §5 MSL → AGL: which placements convert

Every `OBJECT_MSL` / `OBJECT_AGL` placement whose resource is a pack object (not a
library/stock resource — 09z (2) leaves stock objects to X-Plane exactly as authored).
An `OBJECT_MSL` that is a genuine flying object (a lamp on a mast authored MSL, an
aircraft on a stand) is not distinguishable from the DSF; the law is "on ground" for
everything the pack authored as a placed object, and the owner's sim read at KBNA/KMCI/KDFW
(the MSL packs) is the acceptance. Report the count per pack.

## §6 The anchor rule per body class

X-Plane places the object origin at the terrain height under the anchor. The anchor must
therefore be a point whose design-surface height equals the body's intended zero:

| class | anchor point | intended zero |
|---|---|---|
| skirt-less building | a point INSIDE its flat pad (the pad's centroid, or the nearest pad vertex if the centroid falls outside) | the pad plane |
| skirted building (10ag) | its LOW-SIDE FOOT: the ground-contact component whose design-surface height is lowest under the body | the low-side ground; the high side buries up to the skirt |
| basin (10ba) | a RIM point: the floor plate's rim vertex nearest the original anchor, projected onto the emitted `basin_wall` ring | the rim (the object's zero is the rim, its floor plate 7.05 m down on the floor ring) |
| line segment (10bb) | the segment's mid-foot (the ground under its lowest vertex at mid-length) | the ground; the segment drapes |
| elevated deck (11a) | none of its own: merged into the object of the building it abuts (one file, the building's anchor), so the deck stays at the kerb | the building's zero |
| plate-only / other | the centroid of its lowest component | the ground there |

The authored offset of §4.3 = (anchor_x − 0, y_zero − 0, anchor_z − 0) in the authored
frame, where y_zero is the authored y of the foot that must touch the ground (0 for a
skirt-less building on its pad; the skirt's floor y for a skirted one — so the body's
foot lands ON the terrain at the anchor).

## §7 The instrument and the acceptance

`tools/seat_feet_census.py` gains `--placement-plan`: for every body, the design-surface
height at its anchor vs the height under every ground-contact vertex of the body — the
"float" (foot above ground) and "burial" per foot, the same figures as today read from a
different source. Bars for the closing tests: LEMD feet > 0.3 m 284 → ≤ 60 (the old
one-foot mega-bodies no longer exist: every body has its own anchor), `> 3 m` compact 6 → 0;
OTHH's accepted read reproduced (Dewatering / tunnels / Fire Fuel bodies at their floors —
their anchors on their rims / floors as §6 says); KBNA or KMCI: MSL → AGL converted, the
pack's DSF re-encodes and dumps back identically. Acceptance is the owner's sim read of
LEMD and OTHH on the first build; the census is the report beside it.

## §8 Retirement

When §7 passes and the owner's reads accept LEMD and OTHH: `emit/rebake.py`'s seat,
`airport/rigid.py`'s completion, `_one_file_one_delta`, the `.anchor_bak` vertex rewrite
(restore every pack from its backups first — a one-shot restore tool), the `o4_v2_rebake_*`
JSON and their replays (`v2_rebake_replay.py`) are DELETED (refuted mechanisms are deleted,
not gated); body formation moves under `airport/placement/`.

## §9 Coarsening, the generic anchor, and the write half (RULINGS 2026-09-11e)

Round 1 cut every SEAT body into its own file (LEMD 13,924, OTHH 65,360): far
finer than a PLACEMENT needs. §6's per-class anchor table and §4's one-file-per-
body reading are superseded by this section.

1. **Body coarsening** (11e (1), `[placement] split_tol_m`, 0.3 m). Within one
   placement, bodies whose INTENDED-ZERO TERRAIN HEIGHTS — the design surface at
   each body's anchor minus its `y_zero`, i.e. its zero plane in world height —
   agree within `split_tol_m` become ONE file, anchored by the SENIOR body (the
   most ground-contact vertices). The walk is senior-first, so "agree" is always
   measured against the anchor the group takes. A split exists only where the
   terrain DIFFERS under the object. Bodies whose surface reads nowhere are one
   group (no reading is no evidence). An ELEVATED body (lowest authored y above
   `[rebake] elevated_base_m`) has no terrain under it to differ and never founds
   a group: it joins the group whose anchor is nearest it in plan — the seat law's
   own elevated rule (v1 I-8) one level up. Bars: OTHH ≤ 2× its placements,
   LEMD ≤ 4×.
2. **The generic anchor** (11e (2)). The anchor is the footprint point where the
   design surface equals the body's intended zero: with `zero(v) = surface(v) −
   y_v` over the body's ground-contact vertices and `D = median zero(v)`, the
   anchor is the vertex minimising `|zero(v) − D|`, ties to the vertex whose
   authored y is nearest the object's own zero, and `y_zero` is that vertex's y.
   A pit object anchors on its rim, a tunnel object whose zero is its road level
   on its floor ring, and both fall out of the one rule. A body with no such
   point within `split_tol_m` anchors at its LOW-SIDE FOOT and is reported with
   the residual; a body whose surface reads nowhere likewise. The class
   (§6's table) survives only as a LABEL for the report and the census.
3. **The write half** (11e (3)), `[rebake] placement = "agl"` (default) |
   `"seat"` — the one permitted gate, awaiting the owner's sim read; `"seat"`
   runs the pre-11b path unchanged. Under `"agl"` NO SEAT IS COMPUTED and
   `engine_v2.rebake_after_mesh` routes through `airport/placement_write.py`, in
   this order: the plan (conversions for every MSL/AGL row, 11d; splits; kept) →
   the cut files into the pack's `objects/` under NEW names only → the DSF
   edited, encoded, VERIFIED and backed up (`dsf_write.write_pack`, §3) → the
   READ path's text-dump cache refreshed (`dsf_reader.ensure_dsf_text_path` on
   the written DSF — §3.6's mtime key) → `o4_v2_placement_<ICAO>.json` beside
   the patch. The app is the only writer of the real pack (`allow_live_install`);
   lanes and tools write COPIES.
4. **Consumers touched** (the §3.6 table): the dump cache — refreshed by step 3,
   never as a read-time side effect; `airport/dsf.read_dump` — reads the new defs
   and rows back (LEMD 914/914, OTHH 1,090/1,090, 0 rows left carrying an
   elevation); the Swift console lines — the `[v2 placement]` line replaces
   `[v2 rebake]`'s under the gate; the object-anchor worklist — unchanged
   (the seat's, and it is not written on this path); `seat_feet_census.py
   --placement-plan` — §7's figures from the plan's own rows, `--graded` for a
   dry run with no mesh. A DSF `FILTER` is STATE, not a row: the round-trip
   verifier compares the filter IN FORCE per placement and polygon (OTHH).

## §10 The restore and the segment cut (RULINGS 2026-09-11f)

1. **RESTORE FIRST** (11f (1)). Under `placement = "agl"`, before ANY file is
   written, `placement_write.apply_plan` copies every `<obj>.anchor_bak` in the
   pack back over its object — §8's one-shot restore, run on every `agl` write
   and recorded in the provenance (`restore_backups` / `restore_restored`). v1's
   seat baked its deltas into the pack's own `.obj` files; under the placement
   law those deltas are wrong twice over — a cut body is re-anchored by the CUT,
   and a placement the plan keeps WHOLE is never rewritten at all and would
   otherwise render on the old seat's offsets forever. The pass is idempotent
   (a pack with no backup restores nothing; a second run rewrites nothing) and
   it KEEPS the backups: they are what `pristine_path` reads, and §8 deletes
   them with the seat, not before. A DSF's own `.dsf.anchor_bak` is §3's backup
   and is never copied back under it. Measured on pack copies: LEMD 310 of its
   322 backups differed and were restored, OTHH 93 of 229.
2. **THE SEGMENT CUT** (11f (2), `[placement] line_segment_m` = 100 m =
   `[rebake] body_feet_span_m`, capped by `line_object_stations_max`). A LINE
   OBJECT (10bb's verdict, per RESOURCE, over the plan's own genuine parts)
   whose body spans more than one station is cut into SEGMENTS: its triangles
   join the station nearest their plan CENTROID, the stations being spread over
   those centroids by the farthest-point walk that spreads 10bb's drape stations
   (so a perimeter fence's stations follow the LOOP — a projection onto one
   principal axis would chain its two far sides together). Each segment is a
   BODY: its own file, placement and MID-FOOT anchor (§6's line row — its own
   ground contact nearest the plan centre of its feet, so each end floats by
   half a segment's relief instead of a whole run's). Segments then coarsen and
   are cut with every other body, so a fence over flat ground still lands in one
   file. The cutter's body definition widens for it: `BodyCut.tris` names
   authored vertex triples and is SENIOR to the vertex vote — two segments share
   the vertices of the panel they meet at, and a vote cannot separate them.
   ANIM / LOD rules are unchanged.
3. **Measured** (pack copies, LEMD `LEMD_20260910T230749` / OTHH
   `OTHH_20260910T230730` artefacts, `seat_feet_census --placement-plan
   --graded`). LEMD 897 segments from 271 one-line bodies; 985 → 1,086 files
   (3.60×, bar 4×); `> 3 m` **30 → 25**, the ruling's bar of ≤ 5 MISSED, and the
   residual is attributed: only 5 of the 30 were the line class (the two
   `LEMDzaun` rows at 14.68 / 10.16 m and three `grass_FSX` rows are gone). The
   other 20 are RIGID bodies with authored relief — `Bridge3` 8.70, the
   `SWbaume` tree clusters 6.80 / 5.79 / 5.10, the `OldTerminal_FSX` buildings
   6.37 / 5.17 / 3.43, `Terminal4SAT` 4.41 — which the segment cut cannot reach
   and must not: cutting a rigid body into terrain stations would TEAR it, which
   is exactly why 10i binds one placement's touching set into one body. Closing
   that tail is a new question for the owner, not this mechanism. OTHH
   unchanged: `> 3 m` 0 (worst 2.82 Drainage), 1,187 files (1.24×, bar 2×), 210
   conversions, round trip ok, 1,187/1,187 new defs read back, 0 rows carrying
   an elevation.
4. **Refuted in this round, deleted**: a plan-DISTANCE limit on a segment's
   coarsening (a segment joins only a group whose anchor is within one station
   span). It was written to stop 11e (1)'s off-surface rule re-assembling a
   fence — measured at LEMD `North_FSX-LEMDzaun`, 215 off-surface segments came
   back as one 2,071 m body — but it cost 377 extra files (1,463 = 4.84×, OVER
   the 4× bar) and moved `> 3 m` the wrong way (25 → 26). The coarsening of
   11e (1) stands as ruled.

## §11 The canopy-and-building group: the terrain adapts to it (RULINGS 2026-09-11i)

Owner: "a canopy on columns needs to stay connected to its columns, and if it's
adjacent to a building, like a roadway, then it needs to stay connected to the
building as well. If it's a long thing like the railway connecting two far buildings
at HECA we accept disconnecting it so the buildings can seat. But if it's feasible,
adapting the terrain to accommodate the canopy and building group would be preferred."

1. **THE GROUP STANDS.** §9/§17's cross-placement rule (a junior that is an
   ELEVATED DECK by `deck_signature.elevated_deck` joins the building it abuts)
   already reads a canopy on columns as a deck; 11g's LEMD38 / LEMD84 / LEMD60
   groups with LEMD03 / LEMD54 / LEMD51 are CORRECT and stay one object each
   (one file, one placement, the building's anchor). Their `> 3 m` feet are a
   TERRAIN defect, not a grouping one, and this section is the fix.
2. **THE GROUP PAD.** The pad law today pads each `building` CELL on its own
   (`planar/structures.py` pads = `role == "building"`; constraints price
   `building_pad flat` / `frontage_level`; pads by proximity). A GROUP — the
   bodies that share one object under §9's grouping, canopy columns included —
   is ONE pad: the union of its members' `building` cells PLUS every
   ground-contact foot of the group that lies outside them (a column foot
   standing on apron or ground). The pad's LEVEL is the existing law over the
   union's frontages (10l apron-edge, pads by proximity, 10ag: a skirted member
   keeps the skirt rule for its own footprint); the pad's TARGET under each foot
   is `level + (y_foot − y_zero)` in the group's authored frame — a flat pad
   when every foot is authored at zero (the common case), the group's authored
   RELIEF otherwise — because X-Plane drapes the whole group at ONE anchor and
   the terrain under every column must meet that column. Under 11b the foot
   census is then exact for the group by construction.
3. **THE GROUP IS DERIVED ONCE, AT PLANAR TIME.** The pack is read at plan time
   (`airport/contact.py` welds + abutments, `deck_signature`); `emit/
   abutment_group.groups` reads the same group and must not re-derive it — one
   derivation site (`planar/group.py` or inside `planar/structures.py`, the
   lane's call, ≤ 1,000 lines), consumed by constraints (the group pad rows),
   emit (the grouping), the placement plan (one file per group) and the census
   (feet of a group reported against the group's anchor). Consumer census
   (08-30l), ruled here in one table — the lane greps each and reports any
   consumer this table misses BEFORE editing it:

   | consumer | reads | ruling |
   |---|---|---|
   | `constraints` pad rows (`pad_flat`, `frontage_level`, proximity) | pad polygon + level | the GROUP pad is the pad; one level, per-foot relief targets |
   | `verify/pads.py` `pad_flat` | emitted pad plane tilt | measured on the LEVEL plane, relief offsets subtracted |
   | `planar/structures.py` ramp clipping (`_pad_hit`, `_pad_relief_m`, `ramp_crosses_pad`) | pad polygons | the group pad clips as a pad does; its relief is the AUTHORED relief, not DEM relief — `_pad_relief_m` reads the DEM under the union as before |
   | skirt (10ag) | member footprint | a skirted MEMBER keeps its skirt inside its own footprint; the rest of the group pads |
   | basin (10ba) | rim | unchanged; a basin member is out of the group class (14.1 rule 4) |
   | `emit` graded `building` faces | pad faces | the union emits as `building` faces; the placement anchor (§6, §9) lands inside them |
   | `abutment_group.groups` | the group | reads it; the deck gate is unchanged |
   | `placement_plan` / `obj8_split` | the group | one file, the senior building's anchor |
   | `seat_feet_census --placement-plan` | feet + anchor | feet of a group against the group's anchor |

4. **FEASIBILITY, THEN THE LONG SPAN.** The group pad is feasible when the
   emitted surface stays lawful: the pad within `pad_slope_max`, and no DEFECT
   (the runway family gate) or new pavement-law target failures at its
   frontages beyond the base build's. Infeasible groups release their CONNECTING
   body only when it is LONG — `[placement] group_span_max_m` (default 150 m,
   per airport in `airports.toml` where needed; the HECA railway class): the
   junior deck becomes its own object with its own anchor (§6 deck row is
   superseded for it: it anchors at its low-side foot and buries the other end,
   10ay), and the buildings seat on their own pads. A short infeasible group is
   REPORTED with its residual, never split — the owner rules per case.
5. **The round.** Synthetic-first: a cut fixture with a building + a canopy on
   four columns over sloped DEM (the LEMD38/LEMD03 class), one over an apron
   edge, and a long-span pair. LEMD ONCE as the closing build (the owner's site:
   LEMD38 −6.89, LEMD84 −5.17, LEMD60 −3.36 → each within 0.3 m of its own
   group's anchor); OTHH and the HECA railway through the placement-plan dry run
   on their existing products (`obj8_split_report`, `seat_feet_census
   --placement-plan --graded`), no build: OTHH `> 3 m` stays 0 and its groups
   are exactly 11g's; the HECA railway releases (a long span) and its buildings
   seat. Bars: LEMD `> 3 m` 25 → ≤ 22 with the three named rows gone; files
   ≤ 4×; suite green. Two fix iterations, then STOP and report.

6. **Measured** (lane `v2canopy`, round 1, on the LEMD / OTHH artefacts of
   app 1.0.313 — `LEMD_20260911T081738`, `v2bridgegroup_othh`; no build).
   The derivation site landed (`planar/group.py`, 12 twins,
   `tests/auto_patch_v2/test_v2canopy.py`); the GROUP PAD, its consumer
   edits and the feasibility release did NOT, and three measurements say
   why §11 (2)/(4) cannot be implemented as written.

   * **THE UNIT IS THE BODY, NOT THE PLACEMENT.** §11 (2) says "the bodies
     that share one object" and then states the pad union and the span law
     over PLACEMENTS. At LEMD a placement is not a building: Aerosoft
     authors hundreds of unrelated structures into one file, so at
     placement level the owner's own rows read `LEMD38` span **2,654 m**
     relief **48.90 m**, `LEMD84` **1,481 m** / 10.03 m and `LEMD60`
     **1,003 m** / 6.21 m — and `LEMD84`/`LEMD60` are groups of ONE
     placement, so no grouping change can touch them. Under §11 (4)'s
     150 m, **8 of LEMD's 9 placement-level groups come out LONG and so
     RELEASABLE**, including `LEMD38`'s canopy cluster — the exact
     disconnection 11i forbids. Read at BODY level (the intra-placement
     ε-contact component, which is what §9 writes a file for and what the
     census reports a row against) the same site reads spans of 0–180 m,
     52 cross-placement groups of which 16 are long, and the span law
     separates what the owner described. `planar/group.py` derives at body
     level and imports `placement_plan._bodies_of` rather than restating
     it.
   * **THE DOMINANT RESIDUAL IS NOT A GROUPING DEFECT AND NEEDS NO GROUP.**
     `LEMD38`'s 150 bodies are canopy modules of nine column feet each,
     span 28–114 m, and EVERY one has an authored `y` spread of **2.63 m**
     with no cross-placement abutment at all. Under 11b such a body drapes
     at one anchor, so those 2.63 m are the census row. §11 (2)'s per-foot
     target `level + (y_foot − y_zero)` is the fix — but it is the fix for
     a body of ONE placement, which means the mechanism is the general pad
     law with a relief target, and the canopy group is the case that makes
     the union bigger, not the case that creates it. 1,158 of LEMD's 9,546
     bodies carry more than 3 m of authored relief.
   * **THE PAD CANNOT BE MINTED WHERE §11 (3) PUTS IT.** The pad is derived
     in `classify/evidence._pads` (:448) from OSM `airport.buildings`, is
     already unioned by footprint connectivity, and carries **no identity
     link to any placement** (`Building.dsf_object` is never populated;
     `_pads` discards `Building.id`). The group's own footprint is
     therefore new pad AREA, minted at classify time — and `LEMD38`'s
     bodies class as `other`, i.e. they stand on no pad today. But the
     group needs the pack's ABUTMENTS, which `airport/rebake_plan.plan()`
     derives **after emit** (`pipeline/build.py:694`), from inputs that are
     themselves planar products (`pm.basins`, `pm.structures`,
     `_plate_seats`) and the SOLVED surface (`deck_datum`). §11 (3)'s "the
     pack is read at plan time" is not true of this tree, and the
     dependency as stated is circular: pad ← group ← abutments ← planar ←
     classify ← pad.
   * **THE SMALLEST MOVE** (proposed, not taken — it changes the shape of
     the pipeline and belongs to the owner): split `rebake_plan.plan()`
     into `partition_pack()` — objects → members, parts, feet, contacts,
     abutments, and the deck / skirt / line verdicts, none of which reads
     `pm` or the solve — and a thin `plan()` that consumes a partition plus
     the planar- and solve-dependent inputs. `partition_pack()` runs ONCE,
     before `classify`; `planar/group.py` derives the groups from it;
     `_pads` mints the group pad; `plan()` reuses the same partition, so
     the build-time delta is a MOVE of 26 s at LEMD / 108 s at OTHH, not an
     addition. What must be measured before it is accepted: the
     pre-classify partition runs over the UNFILTERED object set (the
     `exclude` / `below_grade` filtering is planar-dependent), so `plan()`
     must filter a partition instead of partitioning a filtered set —
     `contacts` / `abutments` / `parts` counts before and after.
   * **OTHH AND HECA COULD NOT BE DRY-RUN.** No product on disk matches
     this main: OTHH's newest plan is `PLAN_VERSION` **8** (it predates
     11g's `elevated_deck` field, so it carries 0 deck verdicts and yields
     0 groups by construction) and HECA's is **6**. Neither was rebuilt
     (BUILD ECONOMY). The HECA railway class is therefore UNMEASURED.
   * `[placement] group_span_max_m` = 150 m landed with its per-airport
     override (`Affordances.group_span_max_m`, `law/tables.group_span_max_m`
     as the one resolution site). Suite 999 passed / 1 skipped.

## §11a Amendment after round 1 (Fable, 2026-09-11; RULINGS 2026-09-11j)

Round 1 measured §11's premises and refuted two of them. The owner's intent
(11i) is unchanged; the mechanism is restated:

1. **THE UNIT IS THE BODY.** The span law, the group and the pad are read at the
   BODY level (`placement_plan._bodies_of`, the welded set of 10i plus 11a/11g's
   deck-gated cross-placement join), never at the placement level: LEMD38 as a
   placement spans 2,654 m (it is 150 canopy modules of nine columns each,
   28–114 m apart, no cross-placement abutment), while each of its bodies spans
   under 114 m with 2.63 m of authored relief. `[placement] group_span_max_m`
   binds a BODY's connecting span.
2. **THE RELIEF TARGET IS THE MECHANISM.** What moves the owner's rows is
   §11 (2)'s per-foot target — the terrain under every ground-contact foot of a
   body = the body's anchor level + (y_foot − y_zero) — applied to EVERY rigid
   body with authored relief that stands on a pad or on ground the pad law may
   shape (1,158 of LEMD's 9,546 bodies carry over 3 m of it). The GROUP only
   widens which feet belong to one body; it does not create the target.
   A body's feet on PAVEMENT (apron, taxiway) take no relief row — pavement law
   is senior (09af-1: the object goes to the terrain there); the body's anchor
   then sits at its low-side foot as §9 already says, and the residual is
   reported.
3. **THE PACK PARTITION MOVES BEFORE CLASSIFY.** `rebake_plan.plan()` splits
   into `partition_pack()` — objects → members / parts / feet / contacts /
   abutments + the deck / skirt / line verdicts, reading NEITHER planar products
   NOR the solve — and a thin `plan()` that consumes the partition plus the
   planar and solved products it reads today. `partition_pack()` runs once at
   LOAD (the pack is a load-stage input like the DEM), `planar/group.py`
   derives the bodies and groups from it, `classify/evidence._pads` mints each
   body's pad from its FEET (the OSM footprint union stays the pad's plan
   extent where one exists; a body whose feet fall on no OSM building gets a
   pad of its feet's convex footprint buffered by the pad law's margin), and
   `plan()` reuses the partition. This is a MOVE of measured 26 s (LEMD) /
   108 s (OTHH), not an addition — and it must be proven: `plan()` must
   FILTER the load-time partition instead of partitioning a filtered object
   set, and the round's first twin compares `contacts` / `abutments` / `parts`
   of the two orders on the LEMD and OTHH dumps (byte-equal, or the difference
   listed and ruled).
4. **The consumer table of §11 (3) is superseded by round 1's census** (86
   consumers; the missed rows are listed in the round-1 report and in the
   lane's `group.py` module doc). Rule for all of them: a pad with a relief
   target is still ONE pad entity with ONE level — every consumer that reads
   the pad's polygon, contacts, rim or level is UNCHANGED; only the rows that
   price the pad's SURFACE (`pad_flat` in constraints and `verify/pads.py`,
   `pad_flat_i` / `pad_follow` in `solve/design.py`) read the relief offsets:
   flatness is priced on the LEVEL plane with the offsets subtracted. No
   consumer is edited that does not read a pad's surface heights.
5. **Two defects found in passing are IN SCOPE, fixed first, own commits:**
   (a) `auto_patch/engine_v2.py` never passes `pads=` / `rims=` to
   `placement_write.build_plan`, so a SHIPPED build classifies no body as
   `building` or `basin` — only the dry-run tool does; a twin drives the
   engine path and asserts the classes (lane `v2planfix`, merged and shipped
   as 1.0.314 before this round's build). (b) `planar/wall_corridor_ramps.py`
   duplicates `structures._pad_hit`: import it.
6. **The round (2).** Twins first (the partition-order twin, the relief-target
   fixture: one body of nine columns over 2.63 m of authored relief on sloped
   DEM, one over an apron edge whose apron feet take no row, one long-span
   release). LEMD ONCE; OTHH and HECA by dry run on products REBUILT by this
   branch's pipeline only if the ledger has none at PLAN_VERSION ≥ 9 — HECA
   may be built once for the railway class (the owner named it), OTHH stays a
   dry run on the 1.0.313 artefact re-planned by the new `plan()`. Bars as
   §11 (5): LEMD38 / LEMD84 / LEMD60 within 0.3 m of their bodies' anchors,
   `> 3 m` 25 → ≤ 22, files ≤ 4×, suite green, load-stage time within the
   26 s / 108 s moved.

### §11a Measured (round 5, lane `v2canopy5`; owner RULINGS 2026-09-11p)

**(3)'s "the feet's convex footprint" is REFUTED, and its "applied
unchanged" gate with it.** Round 4 measured the whole clause as a NO-OP;
round 5 attributed it inside `classify/evidence._body_pads`, at the one
derivation site, to two refusals:

* A COLONNADE'S FEET ARE A LINE. LEMD38's 150 canopy modules hull to
  5–21 m² over 22–114 m spans — a 0.18 m ribbon — and
  `building_pad.min_area_m2` (250) folded **1,101 of the 1,116** candidate
  pads. The union of the parts' AXIS-ALIGNED plan boxes over-covers a
  diagonal canopy **6×** (2,358 m² where the roof is 658) and pushes the
  representative point outside the boundary gate. THE PAD IS THE BODY'S
  OWN PLAN FOOTPRINT — `airport/skirt.component_footprint`, `footprint`
  restricted to the body's components (`Group.body_comps`, filled at
  `planar/group.derive`'s three construction sites), placed by
  `obj8.placement_affine` and unioned with the feet's hull. LEMD38's
  modules then read 658–917 m² and `min_area_m2` needs no exemption.
* THE OSM PADS' LOCATION GATE DOES NOT BIND A PACK BODY. It screens the
  surrounding CITY's mapped buildings, a population a pack does not have.
  It refused **130 of LEMD38's 150** modules: Aerosoft's old terminal
  stands outside LEMD's apt.dat 130 boundary AND more than 200 m from
  graded apt.dat pavement, so widening the gate to the union of the pad
  law's two expressions recovered only 33 of 157 refusals. `_body_pads`
  takes no `gate`.

MEASURED, LEMD (pristine frame, build `LEMD_20260911T131821`, 330.4 s
against round 4's 352.8 s; partition 87.5 s): pads **123 → 503**,
`pad_relief` vertices **623 → 2,706**, `seat_feet_census --placement-plan
--graded` **`> 3 m` 16 → 15** and `< 0.3 m` **50.1 % → 53.1 %** of
measured bodies, files 1,088 → 1,169 (3.87×), bodies classed `building`
193 → 297. HECA (`HECA_20260911T132857`, 205.4 s against 200.2 s):
`road_train/metal_titles.obj b0` **+15.95 → +1.11 m**; the census moves
the wrong way by a little (`< 0.3` 38,992 → 38,773, `> 3` 1,558 → 1,578)
and `Airport/T23/T3_brick_clean` b0/b3/b4 go +0.46/+1.51/+11.58 →
+3.83/+8.71/+15.29.

**THE STANDING RESIDUAL, for the owner.** A body pad is a RIGID PLANE cut
into bare sloping ground, so it makes a STEP where an UNPADDED neighbour
straddles its edge: LEMD38's worst body goes 0.98 → 3.33 m (a body classed
`other`, 7 feet over 39 m, beside a new pad), and LEMD's `pad_flat` verify
rows read **98** against the round's bar of 39. Two fix iterations were
spent (the body footprint, then the gate) and the round STOPPED there.
The open question is whether a body pad should be minted at all where the
DEM under it is steeper than the pad law can carry as one plane —
`Group.infeasible` prices the body's AUTHORED relief against `bank_slope`,
not the ground's own fall.

**(2) THE NEGATIVE RELIEF OFFSET is the CROSS-PLACEMENT group's own law,
not the skirt rule's.** All 12 of LEMD's negative-offset groups are
cross-placement: `Group.y_zero` is the SENIOR body's lowest ground contact,
so a junior deck standing below it reads negative by construction, and a
single-body group cannot (its zero is the minimum over its own feet). Only
2 of the 12 seniors carry a skirt reading at all (0.52 m / 1.36 m, neither
near its group's −3.51 / −0.02 magnitude), so 10ag does not own the class;
5 of the 12 are already refused by the `bank_slope` feasibility gate and
never reach `pad_relief`. The published −9.92 m end of round 4's range is
`OldTerminal_FSX-LEMD44#b4` (6 feet, relief slope 0.189, feasible). With
the body pads in, the published range closes to **−0.02 … +8.08 m**.


## §12 The pristine frame and idempotence (RULINGS 2026-09-11m; lane `v2idempotent`)

1. **ONE RESOLVER.** `dsf_write.pristine_dsf_path(dsf)` returns `<dsf>.anchor_bak`
   when it exists, else the live file (a backup path returns itself). EVERY
   object-stage read goes through it: the plan's pack read (`airport/load.pack_dsf`,
   the source of `dsf:objN` ids), `engine_v2._fresh_pack_dump` and `_place_objects`,
   `obj8_split_report --write-pack`, `dsf_placement_diff`, `seat_feet_census`.
   Readers left on the live file are the ones whose SUBJECT is the written product
   (`write_pack`'s encode / round-trip verify, the tool's read-back) and the v1
   seat-era terrain readers the `agl` path bypasses. §3's "dump → edit → encode"
   reads the pristine dump by construction; §3.6's cache refresh after the write
   is for the LIVE file's consumers only.
2. **THE DUMP CACHE KEY IS CONTENT.** `dsf_reader.dsf_content_tag` = sha256 of the
   file's bytes (first 8 hex, memoised on abspath/mtime/size, 0.74 ms on LEMD's
   2.2 MB) names the cache entry in BOTH `ensure_dsf_text_path` branches; the
   explicit-`cache_dir` branch ADOPTS a pre-existing fresh untagged legacy dump
   read-only (a build has no licence to re-derive the shared `Default_DSF_cache`);
   mtime staleness stays as the second guard. A written pack's pristine dump is
   therefore `<tile>.dsf.anchor_bak.<tag>.text`, and `airport/dsf.find_text_dump`
   never crosses the live and backup names (the freshness fallback would otherwise
   serve the WRITTEN dump as a pristine frame). The four cache files 11m named are
   orphaned, not deleted.
3. **THE RESTORE STEP REMOVES THE PREVIOUS WRITE'S BODIES.** `write_pack` records
   `body_files` (sorted, pack-relative) in `o4_placement_provenance.json`;
   `restore_pack_objects` removes exactly those names — each confirmed to carry
   the cut mark and to resolve inside the pack root — before any file is written
   (`restore_bodies_removed`). A provenance without the key removes nothing: the
   1.0.313 LEMD write leaves 50 orphan `__b*.obj` in the live pack that no DSF
   references after the next write; the owner decides whether to hand-clean them.
4. **Measured** (LEMD pack copy, 1.0.313-written, the 08:17 artefact plan, three
   consecutive `--write-pack` runs): DSF sha identical, 3,935 rows, 1,099 bodies /
   185 splits / 117 kept, 0 `__b<N>__b<M>` names, `restore_bodies_removed` 0 → 1,099
   → 1,099; the plan JSON differs between runs on that one count alone. Twins in
   `test_v2objsplit.py` (resolver, content key, twice-byte-identical, stale-body
   removal with the escape and corrupt-provenance refusals, plan read over a
   written pack) and `test_airport_load.py` (no name crossing).
7. **Measured** (lane `v2canopy` round 2, branch `claude/v2canopy2`; the
   partition-order twin on the real LEMD pack, the LEMD closing build,
   and the round's 16 twins in `tests/auto_patch_v2/test_v2canopy2.py`).

   * **THE PARTITION MOVED, AND IT IS NOT A FREE MOVE.**
     `airport/pack_partition.partition_pack()` reads the pack once at
     LOAD — objects to members, welded parts, ground feet, the ε-contact
     graph, the authored-frame abutments and the deck / skirt / line
     verdicts — and `airport/rebake_plan.plan()` is now the SCREEN (the
     planar and solved facts about which members and components leave the
     seat) plus the attachment of the deck ring, the deck datum and the
     plate stations. `pipeline/build` runs it between load and classify
     and hands `planar` the same objects, so the pack is still read once.
     §11a (3)'s "a MOVE of measured 26 s (LEMD) / 108 s (OTHH), not an
     addition" is **REFUTED, and it is the round's most important
     number.** The UNFILTERED partition is a bigger problem than the
     filtered one — LEMD 2,493 members / 44,414 parts against 1,187 /
     30,428, OTHH 5,090 / 212,738 against 1,814 / 160,624 — and the
     order twin measures, one pack per process:

     | | load order | old order | delta |
     |---|---|---|---|
     | LEMD partition | 84.4 s | 47.0 s | **+37 s** |
     | OTHH partition | 413.0 s | 150.4 s | **+263 s** |

     In the LEMD closing build the stage line reads `pack partition
     90.56 s` at load against `rebake plan 0.19 s` after the solve, for a
     whole-build 405 s. The surplus is the MULTI-ANCHOR members (LEMD
     repeats one resource at up to 72 anchors, OTHH 129, and the old
     order dropped them BEFORE partitioning), and that drop cannot simply
     move to load: its one exemption is the tunnel-wall PLATE set, which
     is a planar product. The lane kept the deferred drop — correctness
     over time, OTHH's plates over a faster OTHH — and reports the cost.
     This is a SPEC PREMISE, not an implementation choice, and it is the
     owner's to rule: either the load partition narrows (and OTHH's
     plate objects need another way to survive it) or the move is
     accepted at +37 s / +263 s.
   * **THE TWO ORDERS, MEASURED** (`v2_rebake_replay.py order LEMD`, the
     load-derivable screen; the basin exclusions and the tunnel plates
     have no value outside a build). `members` 1,187 = 1,187 EQUAL,
     `parts` 30,428 = 30,428 EQUAL, and keyed by a part's IDENTITY
     (resource, component index, position — the `pid` is partition-local
     and renumbers) the two part sets are the SAME SET: only-old 0,
     only-new 0. The edges differ, in ONE direction only:

     | | old | new | only-old | only-new | shared |
     |---|---|---|---|---|---|
     | LEMD contacts | 33,406 | 33,389 | 17 | **0** | 33,389 |
     | LEMD abutments | 3,305 | 3,267 | 38 | **0** | 3,267 |
     | OTHH contacts | 347,480 | 347,386 | 94 | — | — |
     | OTHH abutments | 20,301 | 20,030 | 271 | — | — |

     Nothing is INVENTED: the filtered reading is a strict SUBSET of what
     the old order found, 0.05 % / 1.1 % of it missing at LEMD and
     0.03 % / 1.3 % at OTHH. The mechanism is the one the
     `pack_partition` module doc predicts — the ε-contact edge set is a
     connectivity-equivalent SPANNING subset, so an edge the old order
     tested directly between two parts is, in the new order, already
     implied through a part the screen later removes, and removing that
     part removes the implication with it. On a fixture pack small enough
     that no such chain exists the two orders agree EXACTLY, and that is
     a twin (`test_m6a_rebake.test_the_new_order_plans_the_same_pack`:
     same units, members, parts, deck rings, plate fields and skip
     records), so a divergence there is a defect rather than this class.
     `no_parts` (+211 LEMD, +6,817 OTHH) and `multi_anchor` (−6, −34) are
     report counts taken over different populations — the load partition
     counts its skips over the whole object set — and name no geometry.
   * **THE RELIEF TARGET IS THE MECHANISM AND IT IS ONE FIELD.**
     `Diff.rel` (`offset[a] − offset[b]`) shifts both one-sided rows in
     `solve/rows._law_sides`, so a pad under a body with authored relief
     is priced FLAT ON ITS LEVEL PLANE and a flat-footed body's rows are
     bit-for-bit today's. `constraints/pad_relief.py` is the ONE
     derivation of the per-vertex offset (nearest foot within
     `[placement] relief_radius_m` = 12 m, never interpolated; feet on
     PAVEMENT take no row, 09af-1) and `classify/evidence._body_pads`
     mints a pad for a body the OSM does not know — the OSM union stays
     the plan extent where one exists, otherwise the feet's convex
     footprint buffered by `building_pad.footprint_outside_pad_m`.
   * **CONSUMERS TOUCHED** (§11a (4)'s rule, held): `constraints/pads.py`
     `_pad_rows` (both `pad_flats` and `pad_slope_ceiling` — the tilt
     CEILING must read the offsets too, or an authored 2.63 m over 28 m
     is refused as a 9 % pad), `solve/rows._law_sides`,
     `solve/design_report` and `solve/why` (a row's zero moved),
     `verify/pads.pad_flat`, and the sidecar key `pad_relief` that
     carries the offsets to it (`emit/osm_adapter.SIDECAR_KEYS`,
     `pipeline/publication`). NOTHING that reads a pad's polygon,
     contacts, rim or level was edited. `solve/design.py`'s `pad_flat_i`
     / `pad_follow` needed NO edit: they are index registers over the
     one-sided rows, which already carry the shift.
   * **THE SPAN LAW IS PER BODY, AND ROUND 1's WAS NOT.** `group.py` now
     carries `body_span_m` and binds `group_span_max_m` to a CONNECTING
     body's own diagonal. The twin that proves the difference is
     `test_a_far_but_short_junior_is_not_the_railway_class`: a canopy
     10 m long joining a building 400 m away has a group footprint over
     150 m and is NOT releasable.
   * **FEASIBILITY IS A READING OF THE GROUP'S OWN FEET.** `Group.
     relief_slope` is `max |y_i − y_j| / d_ij` over the feet; over
     `emit.within_shape.pad_slope_max` the group is INFEASIBLE. Only then
     does a long connecting body RELEASE (and become its own object at
     its own low-side foot); a short infeasible group keeps its canopy and
     is REPORTED, exactly as 11i requires.

   * **THE FEASIBILITY BAR IS THE GROUND'S, AND AN INFEASIBLE BODY IS NOT
     ADAPTED.** The round's first LEMD build priced feasibility at the
     PAD's own `pad_slope_max` (1 %) and admitted every body's relief:
     7,627 of 13,064 groups came out "infeasible" — a verdict that says
     nothing — and the published `pad_relief` reached **+35.53 /
     −14.51 m**, which is not a relief profile but a body whose "feet"
     are vertices up its own structure. The terrain under an object's
     feet is GROUND, so the bar is `emit.design.bank_slope` (1:3, "a
     slope a pilot reads as ground, not a wall"), and §11 (4)'s own
     sentence does the rest: an INFEASIBLE group's pad is NOT adapted —
     it keeps today's flat pad, anchors at its low-side foot (§9) and is
     REPORTED. One rebuild, one iteration:

     | LEMD | first arm | with the gate |
     |---|---|---|
     | `pad_relief` vertices | 2,356 (+35.53 / −14.51 m) | **927 (+5.07 / +0.00 m)** |
     | in-build verify rows | 27,583 | **4,351** |
     | of which `pad_flat` | 97 | **48** |
     | off-DEM `building` > 0.5 m | 1,778 / 2,733 (max 35.33 m) | **898 / 2,733 (max 8.09 m)** |
     | §7 census feet < 0.3 m | 56,532 | **63,803** |
     | 0.3–1 m / 1–3 m | 25,339 / 7,416 | **21,366 / 3,985** |
     | > 3 m | 4,296 | 4,371 |
     | floating | 7,655 | **6,705** |
     | groups infeasible | 7,627 (short 7,626) | **6,790 (short 6,789)** |
     | wall | 405.4 s | 404.9 s |

     Both arms are THIS branch's: the artifact ledger holds no LEMD
     control at main `06b51fa0`, and the round's build budget was two
     builds.

8. **Measured (round 3)** (lane `v2canopy` round 3, branch
   `claude/v2canopy2`; the partition-order twin on the real LEMD and OTHH
   packs, the LEMD closing build, and the harness twins in
   `tests/test_harness.py`). Round 3 did what RULINGS 2026-09-11l (1)/(2)
   ordered: the TWO-PHASE partition and the harness's `pad_relief` key.

   * **ROUND 2's TIMING NUMBER WAS AN INSTRUMENT ARTIFACT, AND THE MOVE
     IS FREE.** The order tool ran both arms in ONE process, load arm
     first. It is the arm that runs FIRST that is slow, whichever arm it
     is — on a warm cache, with `pairs_tested` equal to 1.4 %:

     | LEMD, one process | arm 1 | arm 2 | sum |
     |---|---|---|---|
     | load order first | 75.2 s | 49.7 s (old) | 124.9 s |
     | old order first | 72.3 s (old) | 49.3 s | 121.6 s |

     The sum is conserved: the ~25 s is a once-per-process first-touch
     cost (a 30 k-part / 34 k-edge heap being built for the first time),
     not work either order does. Read in the SAME position the two orders
     are **49.27 s (load, two-phase) against 49.71 s (old) = −0.9 %**,
     inside the round's ±1 % bar. OTHH, the same way: **151.20 s against
     148.67 s = +1.7 %**, the residual tracking its +1.9 % `pairs_tested`
     (2,111,971 vs 2,072,663) — the load reading is unscreened for the
     PLANAR facts (below-grade components, structure-seat line verdicts)
     by design, and that is the whole of it. `order` gains `--old-first`
     so the bar is read both ways, and forces a parse warm-up before
     either arm (LEMD 0.03 s, OTHH 4–5 s — the object read had already
     warmed it, so cache warmth was NOT the mechanism).
   * **THE TWO PHASES.** `partition_pack()` at load now applies the
     multi-anchor drop (the old order's own drop) and keeps the dropped
     placements on the partition (`deferred`) beside a box index of the
     parts already read (`contact.base_index` — boxes, member and
     component ids, line verdict, contact-component id; ~15 MB at OTHH's
     161 k parts, never the geometry). `pack_partition.extend_partition`,
     called by `rebake_plan.plan()`, adds the PLATE-exempt placements
     back: members by the ONE `_build_member`, parts and feet by the same
     `contact.placed_parts`, ε-contacts and abutments by SPATIAL QUERY
     against the existing part boxes only (`contact.extend`), with the
     union-find SEEDED from the base components so a pair already joined
     through the base is skipped exactly as the whole pass would skip it.
     No repartition of the pack.
   * **THE ORDER TWIN, ROUND 3.** The reading is now the old order's on
     every count the old order takes over the same population, and the
     accepted transitive-subset class SHRANK:

     | | round 2 | round 3 |
     |---|---|---|
     | LEMD `members` / `parts` | EQUAL / EQUAL | EQUAL / EQUAL |
     | LEMD `no_parts` | +211 | **EQUAL** |
     | LEMD `multi_anchor` | −6 | **EQUAL** |
     | LEMD contacts / abutments | −17 / −38 | **−9** / −38 |
     | OTHH `no_parts` | +6,817 | **EQUAL** |
     | OTHH `multi_anchor` | −34 | **EQUAL** |
     | OTHH contacts / abutments | −94 / −271 | **−79** / −261 |

     Parts keyed by identity: only-old 0, only-new 0 at both airports.
     Contact pairs only-new 0 (LEMD) and 1 (OTHH) — the subset class
     RULINGS 11l accepts. LEMD's load partition carries 1,188 members /
     30,743 parts against the old order's 1,187 / 30,428; the one extra
     member and 315 extra parts are the PLANAR screen's, applied by
     `filtered` as designed.
   * **PHASE 2 IS EMPTY AT BOTH SITES, AND THAT IS THE ANSWER TO "ARE THE
     PLATES THE WHOLE COST".** LEMD defers 1,517 multi-anchor placements
     and OTHH 10,084; of those, **0 are plate-seated at either airport**,
     so `extend_partition` returns the partition unchanged in 0.00 s. The
     machinery exists for OTHH's 43 kerb-wall corridors when a tunnel-wall
     plate IS a multi-anchor resource; today the plates cost nothing and
     the whole +37 s / +263 s of round 2 was the multi-anchor members
     plus the first-touch artifact, in that order.
   * **THE CLOSING LEMD BUILD** (`v2canopy-r3`, one build, against round
     2's `v2canopy2b` on this branch): `pack partition` **90.21 → 81.05 s**
     at 2,493 → 1,188 members and 44,414 → 30,743 parts; `rebake plan`
     0.17 → 0.24 s. The stage does NOT fall in proportion to the members
     because it is where the process pays the first-touch cost. `planar`
     130.20 → 151.74 s, `solve` 72.12 → 84.68 s and the wall 404.89 →
     445.41 s move in the direction nothing in this change touches
     (identical LP: 24,193 vs 24,205 columns, 80,518 vs 80,588 rows), and
     the build's own guard reports another process writing the shared mod
     cache in the window — so they are NOT attributed here.
   * **THE PAD NUMBERS ARE ROUND 2's, UNMOVED**, as a cost-and-order
     change should leave them: `pad_relief` **915 vertices**, +0.0010 to
     **+5.0700 m** (mean 0.1413, six over 3 m) against 927 in round 2;
     in-build verify **4,345 rows** (4,351), of which `pad_flat` **48**
     (48); the §7 float census over 93,690 feet of 2,358 bodies reads
     `<0.3 m` 63,777, `0.3–1` 21,396, `1–3` 3,985, `>3` 4,367,
     **floating 6,689** (6,705), buried 23,059.
   * **THE HARNESS READS THE KEY (11l (2)), AND IT MOVES THE REAL SITE.**
     `check_grade` registers `pad_relief` in `SIDECAR_LAW_KEYS` as LAW
     INPUT; `_crown_drops_by_nid` generalises to ONE per-vertex field
     reader (`_field_by_nid`) both `crown_drops` and `pad_relief` go
     through; the offsets are applied in exactly the two places a pad's
     own flatness is judged — `_check_plane_gradient` reads the triangle
     at `z − offset` (the subtraction `verify/pads._pad_points` makes) and
     `iter_shape_grade_constraints`, THE single source of constrained
     pairs, sets a pad pair's designed `offset` to `off_a − off_b` in one
     post-pass, so no family keeps its own copy. Interventional A/B on the
     SAME emitted LEMD patch, key read vs key stripped: **law-true total
     6,283 against 6,344 (−61 rows), all of it `within_shape` 4,276
     against 4,337**. A sidecar without the key reads exactly as before.
     Twins (`tests/test_harness.py`): one relief pad censuses 0
     `within_shape` and 0 `plane_gradient` through the harness AND 0 rows
     through `verify/pads.pad_flat`; with the key stripped the same pad
     prices rows on BOTH sides; the registration and the by-coordinate
     join are pinned. Suite `tests/auto_patch_v2` + `tests/test_harness.py`
     1,026 passed, 1 skipped.
   * **NOT DONE, BY THE BRIEF:** no `--write-pack`, no placement-level
     three-row read (the LEMD DSF/dump frame is scout `v2dsfframe`'s and
     those rows are round 4's), no OTHH build.

## §11b Bodies on bare ground take FOOT ROWS, not pads (Fable, 2026-09-11; RULINGS 2026-09-11q)

Round 5 minted a flat pad from each bare-ground body's own footprint (503 pads at
LEMD, `pad_flat` rows 39 → 98) and the three owner rows got WORSE (worst 1.94 →
3.33 m): a rigid plane cut into sloping ground steps wherever an unpadded
neighbour straddles its edge, and HECA's T3 released bodies went +1.5 → +8.7 m.
The colonnade's columns carry 2.63 m of authored relief BECAUSE the real ground
slopes there; a flat pad fights the authoring. Restated:

1. **A rigid body on BARE ground (its anchor on no graded face, its feet on no
   OSM building and no pavement) gets NO pad entity.** Round 5's bare-ground
   minting in `classify/evidence._body_pads` is withdrawn for that class; bodies
   INSIDE an OSM pad keep the pad with relief offsets (§11a (2)); bodies on
   pavement stay pavement-senior (09af-1) and are reported.
2. **FOOT ROWS.** The body goes to the terrain (09af-1): its LEVEL is the
   least-squares fit of `dem(foot) − (y_foot − y_zero)` over its ground-contact
   feet, and each foot gets ONE target row `z(foot) = level + (y_foot − y_zero)`
   priced as a GROUND target (the per-vertex ground datum weight of
   `design.ground_datum`, §23 — not `pad_flat`, not `law`). The sheet blends
   between feet as it does everywhere on adjacent ground; no polygon, no rim, no
   pad consumer is touched (§11a (4) holds by construction), and a neighbour's
   feet get their own rows, so there is no edge to straddle.
3. **FEASIBILITY** is the fit's residual: `max |dem(foot) − target(foot)|` over
   the feet against `bank_slope × (distance to the nearest other foot)`; within
   it the rows fire; beyond it the body is INFEASIBLE — no rows, low-side anchor,
   reported (the HECA `metal_titles` class). A long infeasible junior releases as
   §11 (4) says. `Group.infeasible` therefore prices the DEM's FALL against the
   authored relief, which answers round 5's open question: a body whose authored
   relief matches the ground's fall is feasible at zero cost; one that fights it
   is not.
4. **THE ANCHOR** of a foot-row body is the foot whose target equals the design
   surface after the solve — the low-side foot in practice, its residual reported;
   `y_zero` stays the senior body's lowest contact (round 5's negative-offset
   attribution stands: a junior deck below the senior's zero is negative by
   construction and lawful).
5. **Bars (round 6):** the three owner rows' bodies within 0.3 m except
   pavement-anchored ones (listed); LEMD `> 3 m` ≤ 15; files ≤ 4×; `pad_flat`
   rows ≤ 39 (round 4's); HECA railway bodies within 0.3 m and `T3_brick_clean`
   b0/b3/b4 not above round 4's +0.46 / +1.51 / +11.58; wall within +5 % of
   round 4.

### §11b Measured (round 6, lane `v2canopy5`; branch `claude/v2canopy5`)

Implemented as written — the bare-ground pad withdrawn, the fit, the per-foot
rows at `ground_datum`, the residual-vs-bank feasibility, the low-side anchor —
and **the mechanism does not carry the site.** Two of five bars miss.

MEASURED, LEMD (`LEMD_20260911T135954`, 365.3 s against round 4's 352.8 s,
+3.6 %; `foot_rows` generator 0.79 s):

| bar | round 4 | round 5 | **round 6** | |
|---|---|---|---|---|
| the three rows within 0.3 m | 13 of 24 | 17 of 51 | **9 of 31** | MISSED |
| worst body | +1.94 | +3.33 | **+7.88** (LEMD84 b3, `basin`) | |
| `> 3 m` (`seat_feet_census --placement-plan --graded`) | 16 | 15 | **18** | MISSED (bar ≤ 15) |
| `< 0.3 m` | 50.1 % | 53.1 % | **47.3 %** | |
| files (body rows) | 1,088 (3.60×) | 1,169 (3.87×) | **1,127 (3.73×)** | MET (≤ 4×) |
| `pad_flat` verify rows | 39 | 98 | **18** | MET (≤ 39) |

**THE ATTRIBUTION, from the generator's own census** (`constraints.by_generator.
foot_rows`, LEMD): of 9,561 bodies read, 5,127 stand inside an OSM pad (the pad
law keeps them, §11a (2)), 2,753 have a foot on pavement (09af-1, reported), 824
are INFEASIBLE and 857 fire rows. But of those bodies' ground-contact feet,
**1,901 of 2,663 — 71 % — lie inside NO FACE of the design sheet**, and take no
row: the patch simply does not reach them, and the DEM governs there. Only 762
feet (1,524 one-sided rows) are constrainable at all, out of 88,725 the census
measures. At HECA the class is **inert**: 4,859 bare-ground bodies, 12,003 feet
off the sheet, **3** feet with rows.

**AND WHERE THE ROWS DO FIRE THEY LOSE**: `design.families.foot_rows` reads
`rows 1524, missed 760, max 5.913 m` — half the rows are outpriced, by up to
5.9 m. That is the feasibility rule's own doing: `bank_slope x (distance to the
nearest other foot)` is 33 m of licence for four feet 100 m apart, so a body
whose authored relief fights the ground by metres is admitted as FEASIBLE, its
rows ask the sheet for those metres at `ground_datum` (3), and every law and the
DEM datum beside them outprice or cancel them. The gate binds only where feet
are CLOSE (280 feet 0.5 m apart ⇒ a 0.17 m limit), which is the opposite of
where the relief is.

**WHAT IMPROVED.** HECA's `road_train/metal_titles.obj b0` — the §11a residual,
+15.95 m at round 4 — reads **+1.80 m** with no pad at all, and
`T3_brick_clean` b0/b3/b4 read **+0.43 / +11.24 / +1.21** against round 4's
+0.46 / +1.51 / +11.58 (the same multiset, every member at or under). Both come
from `Group.infeasible` now pricing the DEM's FALL (§11b (3)) rather than the
authored relief, which changes which junior bodies RELEASE — not from the foot
rows, which fired three times at HECA. `pad_flat` 98 → 18 is the withdrawal.
HECA wall 236.5 s against 200.2 s (+18 %, a single run inside the ±25 % band;
the generator's own cost there is 1.77 s).

**FOR ROUND 7, not decided by the lane:**

1. **The sheet does not reach the bodies.** 71 % of bare-ground feet stand
   outside every face. Either the adjacent-ground region must extend under a
   pack body that stands on bare ground (a region question, and so a §11a (4)
   consumer census), or bodies out there are accepted as DEM-governed and the
   class is declared to cover only the ones inside the patch. No row law fixes
   this.
2. **A PARTIAL profile is the round-5 step wearing new clothes.** A body with 2
   of 12 feet on the sheet gets two thirds of its ground tilted and the rest
   left on the DEM. The rows should be ALL-OR-NOTHING per body — the cheapest
   change here, and the lane's recommendation.
3. **The feasibility bar is backwards.** It licenses metres where the feet are
   far apart and refuses centimetres where they are close. A bar on the fit's
   own SLOPE residual (the fitted relief against the DEM's own gradient between
   the same two feet) would price what the eye reads.
4. **The three rows' new worst is a `basin` body** (LEMD84 b3, +7.88 m, authored
   relief 4.94 m), not a foot-row body — the basin admission law (09af/11-09ak),
   outside §11b.

**DEVIATIONS REPORTED (never decided by the lane).**

* `constraints/foot_rows._triangles` is the same SHAPE as
  `solve/rows._face_triangles` and cannot share code with it: the layering law
  (`test_model.test_dependency_direction`) lets `constraints` import only `law`
  and `model`, `solve` likewise, and `model` may import neither `shapely` nor
  `numpy`. A shared home is the owner's call.
* The rows reach the solve through the `ConstraintSet` as TWO one-sided
  `Linear` rows per foot (a `lo == hi` row is read as the law's own equality),
  priced by a new register `[design] ground_datum_rulings` — the same shape as
  `hard_rulings` / `pad_flat_rulings`. `solve.assemble` takes no `Airport`, so
  there was no other channel.
* The fit is per GROUP, not per body: `Foot` carries no body key, and a group is
  what X-Plane drapes at one anchor.
* `model/ground_fit.py` is the ONE expression of the fit; `planar/group.derive`
  and `constraints/foot_rows` both call it.

### §11b Measured (round 8, lane `v2canopy8`; branch `claude/v2canopy8`)

11ab implemented as written, PRICING ONLY: the register
`[design] ground_datum_rulings` — whose only entry was ever the foot-row
head — is repriced from `ground_datum` (3) to `pad_flat` (3,000) and
renamed `foot_row_rulings`. **One register, no new price constant.** The
head stays DISTINCT from `pad_flat_rulings` because the report counts the
two classes apart (`design.foot_rows` is exactly the foot rows,
`verify/pads.pad_flat` exactly the pad planes); `law/design_schema` now
refuses a head that appears in both. All-or-nothing per body and the
neighbour-pair feasibility bar are untouched, so a priced row cannot mint
a step.

MEASURED, LEMD (`LEMD_20260911T151823`, artifact-ledger key `4ddb063cb61c`,
corpus `e512b4ea8cca`; engine total **366.5 s** against round 7's 379.9 s,
−3.5 %; harness wall **383.2 s**, bar 380 × 1.05 = 399 s — MET):

| bar | round 6 | round 7 | **round 8** | |
|---|---|---|---|---|
| `design.families.foot_rows` rows / missed / max | 1,524 / 760 / 5.91 | 1,434 / 715 / 5.702 | **1,434 / 691 / 3.792** | bar NOT met on `missed` |
| feet within 0.3 m of their target | — | — | **658 of 715 (92 %)** | NEW instrument |
| `foot_rows.partial` | 0 | 0 | **0** | MET |
| `pad_flat` verify rows | 18 | 23 | **19** | no regression |
| `> 3 m` | 18 | 16 | **not measurable** | see below |

**THE HEADLINE `missed` IS A TOLERANCE ARTEFACT, NOT A MISS.** A foot is
TWO one-sided rows sharing one target, and `families.missed` counts a side
violated beyond `active_set_tol_m` (0.02 m). The new per-FOOT reading
(`design.foot_row_diag`, `solve/design_report.foot_row_diagnostic`) is:

| | LEMD round 8 |
|---|---|
| feet with rows | 715 |
| within 0.01 m | 292 |
| within 0.1 m | 621 |
| within 0.3 m | **658 (92 %)** |
| within 1.0 m | 687 |
| p50 / p90 | **0.0138 m / 0.1698 m** |
| max | 3.7916 m |

So the price DOES govern: the median fired foot is carried to 1.4 cm and
nine in ten to 17 cm, where round 7's family max was 5.70 m. What remains
is **57 feet (8 %) outside 0.3 m**.

**THE RESIDUE IS THE TRIANGULATION, NOT THE PRICE** (the round-9
mechanism, measured here, not decided):

* `feet_no_free_column` = **0** — no foot row is frozen; the price reaches
  every one of them.
* 715 feet stand in **210 triangles** — 3.4 feet per face — and
  `feet_sharing_a_triangle` = **668 (93 %)**.
* `worst_triangle_spread_m` = **4.45 m**: two feet inside ONE face asking
  for levels 4.45 m apart.

The design sheet is LINEAR over a triangle. Two feet in one face asking
different levels cannot both be carried at ANY price, and the
least-squares compromise between them is exactly what the remaining 57
residuals are. This is the bank's 09x lesson (`bank_triangle_divisions`:
"the mesh must have vertices to carry the blend") arriving at the bodies:
the sheet needs a vertex where a foot stands. Raising the price again
cannot help; a region/triangulation change is a cross-cutting geometry
change and takes a consumer census at spec time first.

**`> 3 m` IS NOT MEASURABLE IN THIS LANE.** `build_airport.py` writes no
`o4_v2_placement_LEMD.json` (the rebake WRITE stage is a tile build), so
the instrument needs a plan from elsewhere. The only plan on the corpus,
`XPTerrainBuilderData/Patches/+40-010/+40-004/o4_v2_placement_LEMD.json`,
was rewritten by ANOTHER lane at 15:02 today, mid-round — reading round 8's
graded surface against it gives `>3 m = 47` of 741, which is a
CROSS-TREE number and is quoted here only to say it is not evidence
(RULINGS: cross-tree comparisons are not evidence). Round 7's 16 was read
against a different plan file and cannot be compared to it.

**WHAT ROUND 8 DID NOT DO.** No change to the rows, the feasibility bar,
the all-or-nothing rule, the basin exclusion, the sheet's triangulation or
any consumer; no HECA and no OTHH build (brief); no merge. The suite is
1,076 green (round 7: 1,072; +4 round-8 twins).

### §11b Measured (round 7, lane `v2canopy5`; branch `claude/v2canopy5`)

11x implemented as written — all-or-nothing per body, the neighbour-pair
feasibility, basin bodies out, one face triangulation. **Every bar met or
unmeasurable; the mechanism is now HONEST about how little it governs.**

MEASURED, LEMD (`v2canopy7_lemd`, engine total 379.9 s against round 6's
365.3 s on the same instrument, +4.0 %, bar 383.3 s; harness wall 396.8 s
against round 6's 385.4 s, +3.0 %; `foot_rows` generator 0.95 s):

| bar | round 4 | round 6 | **round 7** | |
|---|---|---|---|---|
| the three rows, ON-SHEET non-basin bodies within 0.3 m | — | — | **2 of 2** (−0.08, −0.09) | MET |
| the three rows, all 29 bodies within 0.3 m | 13 of 24 | 9 of 31 | 10 of 29 | (context) |
| worst NON-BASIN body | +1.94 | — | **+1.94** (LEMD60 b4, off-sheet) | |
| worst body overall | +1.94 | +7.88 (basin) | **+4.06** (LEMD84 b4, basin) | |
| `> 3 m` (`seat_feet_census --placement-plan --graded`) | 16 | 18 | **16** | baseline UNAVAILABLE |
| `pad_flat` verify rows | 39 | 18 | **23** | |
| files (body rows) | 1,088 | 1,127 | **847** | |

**THE MATCHED BASELINE DOES NOT EXIST.** The artifact ledger holds no LEMD
control at main's tree as of `3656a64c` (`artifact_ledger.load_entries()`,
141 entries, zero on that tree), and the brief forbids building one. `> 3 m`
16 is quoted against round 6's 18 and round 4's 16 instead.

**THE CENSUS** (`constraints.by_generator.foot_rows`):

| | LEMD | HECA |
|---|---|---|
| bodies | 9,561 | 21,981 |
| `padded` (the pad law, §11a) | 5,127 | 13,524 |
| `pavement` (09af-1) | 2,753 | 2,415 |
| `basin` (§14, NEW) | 195 | 0 |
| **`off_sheet`** | **1,117** | **6,040** |
| `infeasible` | 144 | 0 |
| `bare` (rows fired) | 225 | 2 |
| rows / feet off the sheet | 717 / 6,841 | 6 / 20,142 |
| **`partial`** | **0** | **0** |

`no_dem` is 0 at both. `partial` is 0 BY CONSTRUCTION and the twin
(`test_a_partial_profile_is_impossible`) asserts the invariant per body,
not the counter.

**THE THREE ROWS ARE NOT §11b's.** Per body, over the emitted design
surface's own faces (each body's feet tested for containment in a face of
`LEMD.graded.json`, the same predicate the generator uses pre-solve): of
the 29 bodies, **25 are OFF-SHEET, 2 are `basin`, and 2 are on-sheet and
non-basin** — `OldTerminal_FSX-LEMD60` b3 (−0.08 m) and b8 (−0.09 m), both
within 0.3 m. The off-sheet 25 are LEMD38 b0–b14 (every body; 1,116 of its
1,120 feet stand on no face), LEMD60 b0/b1/b2/b4/b6/b7 and LEMD84
b0/b1/b2/b3. Their residuals — worst +1.94 m — are the SPLIT and ANCHOR
law's (§9/§13, 09af-1), not a foot row's: no row was ever minted for them.
Round 6's worst body, the `basin` LEMD84 b3 at +7.88 m, is gone: the basin
class is excluded and the worst basin body now reads +4.06 m.

Note the instrument disagreement, reported not decided:
`obj8_split_report` reads `off-surface 0` for all 29 bodies while the
face-containment test reads 25 of them off-sheet — the split report's
surface sampler answers "is there a surface value here" (it falls back),
the generator's answers "is this foot inside a face". They are different
questions and only the second one mints a row.

**HECA** (`v2canopy7_heca`, 236.2 s against round 6's 236.5 s, −0.1 %):
`road_train/metal_titles.obj` b0 reads **+1.80 m**, exactly round 6's
figure. `T3_brick_clean` has TWO placements and neither is above round 6's
`+0.43 / +11.24 / +1.21`: b0/b3/b4 read **−0.11 / −0.11 / (no design
surface under any foot)** and **+0.45 / +0.64 / −0.47**. The 11 m member is
gone. The foot rows fired SIX times at HECA — the class is inert there, as
in round 6.

**WHAT ROUND 7 DID NOT FIX, and the round-8 questions (not decided here).**

1. **The sheet still does not reach the bodies** — 1,117 of LEMD's 1,486
   sheet-tested bodies and 6,040 of HECA's 6,042. All-or-nothing makes that
   HONEST (no partial profiles) but does not make it smaller. This is 11x's
   own reading of round 6 item 1 and still the owner's region question.
2. **Where the rows DO fire they are still outpriced.**
   `design.families.foot_rows` reads `rows 1434, missed 715, max 5.702 m` —
   essentially every fired foot row loses to the laws beside it at
   `ground_datum` (3). The feasibility bar now says the sheet COULD carry
   these bodies; the pricing says it will not. A row that is always
   outpriced is decoration, and whether `ground_datum` is the right price
   for a body's own feet is an owner question.
3. `infeasible` fell to 144 (LEMD) / 0 (HECA) only because the sheet test
   runs FIRST — a body off the sheet is never priced for feasibility. The
   two counts are not comparable with round 6's.

**DEVIATIONS REPORTED (never decided by the lane).**

* 11x (4) resolved by a NEW LEAF PACKAGE. `constraints` may import only
  `law` and `model` (`test_model.test_dependency_direction`) and `model`
  may import neither `shapely` nor `numpy`, so no existing module could
  host the shared triangulation. `src/auto_patch_v2/geom/` is that leaf —
  pure shape, importing nothing of v2 — and the layering law was EXTENDED
  to register it (`order[0]`, `producers["geom"] = set()`).
  `solve/rows._face_triangles` is now a map-reading adapter over
  `geom.face_triangles`, which is its own former body verbatim;
  `constraints/foot_rows._triangles` is deleted. The solve's triangulation
  is unchanged by construction.
* The NEIGHBOUR GRAPH is the feet's Euclidean MINIMUM SPANNING TREE
  (`model/ground_fit.neighbour_pairs`), not the Delaunay: it is the
  nearest-neighbour graph made CONNECTED, a Delaunay subgraph, and pure
  Python (the model layer may not import `scipy`). A bare nearest-neighbour
  graph leaves clustered feet — two columns' corner pairs — connected only
  within a cluster, so nothing between the clusters is ever tested.
* The BASIN class is read GEOMETRICALLY in the generator (a foot authored
  below the object's own zero inside a `retaining_wall` face whose ref
  starts `basin_wall:`), because the body class itself is minted after the
  emit, in `airport/placement_plan`. It is the same predicate `_rim_of`
  applies to the emitted `structure_rim` rings, read off the map those
  rings come from.
* A body whose DEM does not sample EVERY foot is `no_dem` and fires
  nothing — a fit over a subset is a partial profile by another name. It
  did not occur at either airport (0 / 0).

## §13 An ELEVATED body never has a file of its own (RULINGS 2026-09-11r/s)

The owner's LEMD read: roofs, road decks and tower parts sit on the ground. The
app's own `o4_v2_placement_LEMD.json` shows why: 218 of the 1,092 bodies written
as their own file carry `authored_offset.y` (the `y_zero` the file is shifted by
so that its lowest vertex lands on the terrain) more than 2 m above the object's
zero — a roof at 69.55 m (`Munoza-LEMD76__b13`), tower parts at 65–68 m
(`Terminal4sBlue-LEMD20`, `-LEMDz3alpha`, `-ZNTWR`), canopies at 40 m. §9's
"an elevated body joins the nearest ground group" was a coarsening preference,
not a law: a body whose intended zero (surface − y_zero) agrees with no ground
body's became its own file, and §6's "plate-only / other: the centroid of its
lowest component" placed it ON THE GROUND. The foot census read those bodies as
perfect (their lowest vertex IS on the ground), which is why the numbers were
green while the sim was broken.

1. **THE LAW.** A body is a candidate for its own file ONLY if its lowest
   vertex is a GROUND CONTACT of the object: `y_zero` within
   `[rebake] elevated_base_m` of the object's zero plane (below it is lawful:
   basins, skirts, foundations). Every other body is ELEVATED and NEVER a file
   of its own, whatever the coarsening says: it joins the file of its CARRIER —
   the ground body of the SAME placement with the largest plan overlap, else
   the nearest ground body of the placement in plan — at its authored offset in
   the carrier's frame (no vertex rewrite; the same authored coordinates, the
   carrier's anchor). A placement with NO ground body at all (a roof object, a
   deck object, a sign) is KEPT WHOLE, unsplit, its row untouched: X-Plane
   drapes it at its own anchor and its authored y keeps it above the ground
   there, which is the pack's shared-datum frame — the design surface's pad
   under it is what keeps it level with its neighbours.
2. **The intended zero of a file** is its carrier's; an elevated body
   contributes none to §9's coarsening.
3. **The census reports the class**: `seat_feet_census --placement-plan` and
   `obj8_split_report` print, per airport, `elevated bodies as own files` (must
   be 0) and `footless placements kept whole`, and a twin fails on a plan that
   writes an elevated body alone. The feet histogram excludes elevated bodies'
   vertices (they are not feet).
4. **Bars (lane `v2elevated`):** LEMD `elevated bodies as own files` 218 → 0,
   files fewer than 1,092, the DSF round trip ok, `> 3 m` not above 16, OTHH's
   groups unchanged (dry run on its artefact); the owner's read of the next app
   build is the acceptance.

## §14 Footless bodies are CARRIED; a basin is one file (RULINGS 2026-09-11u/v)

The shared-datum pack (LEMD unit:25: 171 resources on ONE `OBJECT` row) authored
every object against one flat plane. The switch moves each FOOTED body to its own
anchor (right: its feet meet the ground where they stand). A FOOTLESS body — a
footbridge deck, a terminal roof, a canopy plate — has no ground to meet: written
alone it is shifted onto the ground (the split half of the footbridge, 0.03 m under
the road), kept whole it drapes at the DATUM point, 15.7 m under its building
(`green-LEMD16`), 20 m for the T4S roof. Neither is the authoring.

1. **THE CARRIER.** For every body with no vertex below `[rebake] elevated_base_m`
   (a split body OR a whole placement): its carrier is (a) the footed body it abuts
   in the unit's contact/abutment graph with the largest contact, else (b) the
   nearest footed body of its UNIT in plan, else (c) the unit's largest footed body.
   The footless body is written as a body file anchored at the CARRIER's anchor with
   the carrier's `authored_offset` — the same translation every body file already
   carries; same heading (one unit, one row). `merged_into` records the carrier.
   Never at the datum; never on the ground. §13's "kept whole" for a footless
   placement is superseded: it is carried.
2. **THE BASIN IS ONE FILE.** A resource classed `basin` is never split; its one
   body anchors at a RIM point where the design surface equals its zero (§6), and
   `rims` — accepted-and-unused today (`anchor_rule.py:192`) — EXCLUDE the interior
   of the body's own ring from every anchor search (10bd's inside-the-trench class).
   Floor, walls and parapet share one zero.
3. **PLAN OVERLAP BINDS.** Bodies of one resource that overlap in plan (a floor
   under walls, a ledge inside a wall) are one body whatever the contact graph
   says; the split only separates bodies apart in plan whose terrain differs by
   more than `split_tol_m`. This closes the 7 m zero-plane scatter of one rigid
   object.
4. **Census** (`obj8_split_report`, `seat_feet_census --placement-plan`): `footless
   at datum`, `footless on ground`, `basin bodies split`, `spread` (max zero-plane
   range per resource) — bars 0 / 0 / 0 / ≤ `split_tol_m`.
5. **Bars (lane `v2carrier`, LEMD plan replay on a pack copy, then LEMD once):**
   the four footbridge resources at the terminal's zero (deck bottom ≈ 616.1 + 4.5
   over the road); `Terminal4SAT_pink-LEMD01` at its terminal's zero; the basin
   parapet +2.99 above the rim everywhere; the 89 footless placements 0 at datum /
   0 on ground; files not above 1,092; round trip ok; OTHH dry run unchanged.
**MEASURED (lane `v2carrier`, 2026-09-11).** Implemented in
`airport/placement_carrier.py` (NEW: the carrier search, the plan-overlap
binding, §9's coarsening moved here, and `census_v14` — the ONE
implementation of (4) that both tools call), `airport/anchor_rule.py`
(§6's basin RIM row, wired at last), `airport/placement_plan.py` (the walk
is now per UNIT in two passes) and `airport/obj8_split.py`.

* **THE SILENT FLOOR, found by measurement.** `split_obj8` refused to emit
  a SINGLE file (`kept_whole = "one_body"`, "the object already IS one
  body") — true while a one-body cut changed nothing, fatal the moment
  §14 (1) gives a one-body placement a REASON TO MOVE. Every carried
  footbridge was quietly returned to the datum while the plan and the
  census, reading the plan's own records, reported it carried. The cut
  now takes `allow_single=True` from a caller whose whole point is the
  move. A twin holds it.
* **LEMD, the six named sites** (the app's 1.0.315 `o4_v2_rebake_LEMD.json`
  + `LEMD.graded.json`, the write half into a pack COPY; the ruling's
  `Munoza-LEMD36/37` are `LEMD_OBJ-Ground-FSX-LEMD36/37`):

  | resource | before (main 0ecf96fc) | after |
  |---|---|---|
  | `Terminal4_green-LEMD16` | footless, kept at the DATUM (595.81) | carried by `Terminal4_yellow-LEMD13__b0`, zero **616.65** (abuts 7 part contacts) |
  | `Terminal4_green-LEMD17` | footless, kept at the DATUM | carried by the same, zero **616.65** (nearest footed body, 2 m) |
  | `Terminal4_green-LEMD18` | footless, kept at the DATUM | carried by `Terminal4_yellow-LEMD14__b0`, zero **616.63** |
  | `Terminal4_yellow-LEMD16` | footless, kept at the DATUM | carried by `Terminal4_yellow-LEMD13__b0`, zero **616.65** (abuts 71) |
  | `Terminal4SAT_pink-LEMD01` | footless, kept at the DATUM | carried by `Terminal4SAT_Yellow-LEMD11__b0`, zero **597.43** |
  | `Ground-FSX-LEMD36` / `-LEMD37` / `T4STower-SWbaume` | 1 + 2 + 23 bodies, each draped in its own trench, zeros 597.53 … 604.11 | **one file each**, all three on ONE rim vertex, zero **597.53** |

  The footbridge deck (authored y 4.5, no vertex below 3.9) therefore
  renders at 621.15 over a road at 616.05–616.20: **+4.95 m**, the
  authored clearance. The basin's parapet (+2.99) renders at **600.52 —
  +2.99 above the rim it anchors on**, where 11v measured `LEMD37` b1's
  1.35 m BELOW it.
* **The four bars (4):** `footless at datum` **0**, `footless on ground`
  **0**, `basin bodies split` **0**, basin-RING `spread` **7.0 m -> 0.00 m**.
  The literal per-placement `spread` is 50.71 m (`LEMDgrass`, 103
  placements over): it is dominated by the LAWFUL §9 split — a 2 km fence
  and 77 scattered taxi signs are one placement over terrain that
  genuinely differs — so the bar as written is not reachable and the
  reported figure is the rigid-object one beside it.
* **The rest of LEMD:** files 828 -> **855**, DSF round trip **OK**
  (855/855 new `OBJECT_DEF`s, 0 rows carrying an elevation), row census
  (`seat_feet_census --placement-plan --graded`) `> 3 m` 18 -> **17**,
  worst row 7.43 m (`Bridge3`, 11h's rigid-relief class). Feet census
  `> 3 m` 151 -> **489**, and that number is the LAW, not a regression:
  487 of the 489 are BURIED (`SWbaume` 12 -> 178 and `OldTerminal-LEMD38`
  0 -> 172, every one of them ground-over-foot) because a rigid object
  riding ONE zero necessarily buries its low feet — the very thing "the
  wall must stand above the apron" asks for. FLOATING feet, the class the
  eye reads, move 8,222 -> 8,657 and floating `> 3 m` 4 -> 23.
* **The one-body keep, and why §14 had to touch it.** A placement cut to
  ONE body is KEPT, its row untouched — and on a shared-datum row that
  row is the DATUM: 73 of LEMD's 104 one-body keeps drape more than 3 m
  from where their own anchor says their zero is, worst **31.0 m**
  (`Munoza-LEMD73`). The census could not see it (it reads the computed
  anchor for kept records too). (3)'s binding makes MORE such placements,
  and 45 of the 80 carried placements would have ridden such a carrier,
  so the keep is now admitted only where the authored row and the anchor
  read the SAME design surface (within `split_tol_m`); 99 LEMD placements
  are written instead of kept, and carried-onto-a-kept-carrier falls
  45 -> 1. This is the one place the lane read §14 (1)'s sentence onto a
  case §14 does not name, and it is reported for ruling, not decided.
* **OTHH dry run** (its PLAN_VERSION 9 artefact): footless 330, ALL
  carried (0 without a carrier); files 333 -> **525**; feet `> 3 m`
  6 -> **37**; floating 6,204 -> **5,938**. The §14 (5) bars of
  "unchanged" are missed on both counts and the mechanism is the law
  itself — 330 carried placements are 330 new files, and the binding
  adds the rest.
* **Deviations, reported not decided.** (a) The rim-interior exclusion is
  wired for the BASIN class only: 22 of LEMD's 23 `structure_rim` rings
  are `tunnel_wall`, and §6's tunnel row REQUIRES a tunnel object to
  anchor on its FLOOR ring, which lies inside its own ring — excluding
  every ring's interior "for all classes" would move every tunnel
  object's anchor to its rim. (b) A footless PLACEMENT takes ONE carrier
  for the whole placement, not one per body: a footbridge is a rigid span,
  and two carriers would give its halves two zeros. (c) A unit holding NO
  footed body (14 at LEMD, all one- or two-member units whose "datum" is
  their own authored row) has no carrier; those keep their row with the
  reason `footless_no_carrier` and are reported by name, never barred.
  (d) The carried body's offset is computed in ITS OWN member's authored
  frame with the carrier's anchor and `y_zero` — numerically the
  carrier's `authored_offset` when the unit is one row and one heading,
  and geometrically right when it is not.
* **Build time:** the LEMD plan stage 2.53 s -> **3.22 s** over 3 runs per
  arm (+0.69 s, 1.15 % of the 60 s per-airport budget) after two
  optimisations the measurement forced — a body-hull pre-reject before
  the part-by-part overlap scan, and walking a footless body's adjacency
  once instead of once per candidate (4.13 -> 3.22 s, identical output).

**MEASURED (lane `v2elevated`, 2026-09-11).** Implemented in
`airport/placement_plan.py` (`is_elevated`, the carrier rule inside
`coarsen`, the footless keep in `build_splits`) and reported by
`tools/obj8_split_report.py` and `tools/seat_feet_census.py`.

* **ATTRIBUTION (interventional, on the plan replay — no build).** The §9
  fold *worked*: with a ground body present, an elevated body never founded a
  group (0 cases). Three escapes produced all 274 LEMD files whose `y_zero`
  stood above 2 m (271 by the law's own 0.5 m threshold in the app's shipped
  plan, 278 in the matched replay):
  * **226 — the FOOTLESS placement.** `coarsen` began
    `if not ground: ground = all; elevated = frozenset()` — a placement whose
    every body is elevated had its elevated set *cleared*, and each roof then
    founded its own group and its own file. `Munoza-LEMD76` (23 bodies, all
    elevated), `Terminal4sBlue-LEMD20`, `-LEMDz3alpha`, `-ZNTWR` are this class.
  * **33 — the ANCHOR's zero.** The body has a ground contact (so it was never
    flagged), but `anchor_for`'s median zero plane landed on a welded ROOF part:
    `Munoza-rada` b1 anchored at `y_zero` +32.73 with feet 34.06 m off.
  * **15 — the LINE SEGMENT.** `build_splits` hard-coded `elevated=False` on
    every segment, so an elevated body that read line-shaped was cut into
    stations, each its own file (`-ZNTWR` at 65.34 / 56.81 m).
* **LEMD, matched arms on one frame** (the app's 1.0.315 `o4_v2_rebake_LEMD.json`
  + `LEMD.graded.json`, the write half into two pack COPIES):
  `elevated bodies as own files` **278 → 0**; files **1,099 → 828** (< 1,092);
  footless kept whole **0 → 94**; elevated bodies carried at their authored
  offset **0 → 1,178**; DSF round trip **OK**, 3,725 rows, 828/828 new
  `OBJECT_DEF`s, 0 rows carrying an elevation. Census feet `> 3 m`
  **1,060 → 151**, worst foot **34.06 → 13.75 m**. Row census
  (`seat_feet_census --placement-plan`) `> 3 m` **20 → 18** — the spec's bar of
  16 came from 11p's *different* artefact; on this frame the baseline is 20 and
  the residual 18 is the rigid-relief class of 11h (Bridge3 8.70, SWbaume 6.60,
  T2BCK 6.36), untouched by §13.
* **OTHH is the same defect, not a control.** Files **1,203 → 333**, footless
  kept whole **330**, `elevated bodies as own files` **0**, census feet
  `> 3 m` **952 → 6**, worst foot **54.02 → 4.26 m** — the 54 m row was
  `OTHH_ATC_Tower_02` set on the ground. §13 (4)'s "OTHH's groups unchanged"
  is therefore refuted as a premise and reported, not decided.
* **Build time:** the plan stage is FASTER — LEMD `--no-cut` 3.28 s → 2.54 s
  over 3 runs per arm (fewer bodies survive to be anchored and cut). No budget
  impact.

## §15 Stands-over is the carrier; binding re-cuts; duplicate rows (RULINGS 2026-09-11ae)

1. **THE CARRIER IS WHAT THE BODY STANDS OVER.** For an elevated body (§13) or a
   footless placement (§14) the carrier is chosen across the whole UNIT, every
   resource alike: (a) the footed body with the largest PLAN OVERLAP beneath the
   elevated body's plan footprint; (b) else the footed body with the largest
   contact; (c) else the nearest footed body in plan. §13 (1)'s "of the SAME
   placement" and §14 (1)(a)'s contact-first order are superseded. A roof authored
   as its own resource (`TEJ*`) over walls of another resource rides those walls.
2. **BINDING RE-CUTS.** §14 (3)'s plan-overlap union is followed by a terrain check:
   a bound group whose members' intended zeros (surface at each member's own feet
   minus its `y_zero`) span more than `split_tol_m` is re-cut into terrain groups
   by §9's rule, each with its own anchor; the plan-overlap bond holds only within
   a terrain group. A rigid body is never wider than the terrain it can stand on.
3. **THE RESIDUAL THE EYE READS.** A body anchored at its low-side foot reports
   `float = zero − zero_beneath` (the zero of the footed body under its plan
   footprint, else the ground under its own feet), and the census prints
   `stands-over float > 0.5 m` (bar 0 for carried bodies; reported for footed ones).
4. **DUPLICATE ROWS.** Rows of one resource identical in lon/lat/heading are ONE
   placement to the split: all of them are replaced by the body rows, none survives
   to draw the un-split object at the datum. Census `duplicate rows surviving` = 0.
5. **THE INSTRUMENT.** `obj8_split_report` samples the graded surface; the shipped
   plan samples the MESH. The tool marks an anchor or foot on no graded face
   `off-sheet` and excludes it from every comparison and bar; a body's dry-run
   number is evidence only on-sheet.
6. **Bars (lane `v2roofcarrier`, plan replay on a pack copy, then the owner's
   read):** site 1 `LEMD38` roof at `HANG3`'s zero (float 6.11 → ≤ 0.3); site 3
   `green-LEMD03` re-cut so the garage roof sits on `PKT4`'s walls (8.65 → ≤ 0.3);
   site 4 `tej2` on `LEMD41` (1.15 → ≤ 0.3); the class `stands-over float > 0.5 m`
   129 → 0 for carried bodies, the footed remainder listed; `duplicate rows
   surviving` 19 → 0; files ≤ 900; round trip ok; OTHH dry run: its class count
   before/after.

## §16 Every row is in the population; every body is re-cut; a carrier is a solid (RULINGS 2026-09-11ai)

1. **NO THICKNESS GATE.** Under `[rebake] placement = "agl"` the plan population is
   every `OBJECT` row of the pack. The seat-era skip "no genuine solid component:
   nothing to seat" (08-26 §2.1) is not applied: a resource with no solid component
   is a FOOTLESS body (§14) and is carried by §15's rule. `skipped` keeps only the
   classes the switch cannot place (ANIM, unparsable, stock-library rows that are
   converted rather than split). Census: `rows on the datum outside the plan` = 0.
2. **EVERY BODY IS RE-CUT BY TERRAIN.** §15 (2) applies to every body, not only to
   bound groups: a footed or skirted body whose feet's ground spans more than
   `split_tol_m` is cut into terrain groups over its feet; a carried/footless body
   whose footprint's ground spans more than `split_tol_m` is cut into terrain groups
   over the ground under its own triangles, each group carried by what IT stands
   over. The census reads the ground under the carried GEOMETRY (the body's own
   parts hull), never the carrier's plan box; `float = zero − ground_under_geometry`
   is printed beside `zero − zero_beneath`.
3. **A CARRIER IS A SOLID.** Line segments, grass, signs and any body whose footprint
   fill (parts-hull area over plan-box area) is under `[placement] carrier_fill_min`
   (0.2) never carry. "Stands over" is measured as parts-hull overlap, not box
   overlap. A candidate carrier whose zero is more than `split_tol_m` from the ground
   under the carried body is refused and the search continues; a footless body with
   no carrier anchors at the ground under its own footprint centroid, authored y
   kept (reason `footless_own_ground`).
4. **Bars (lane `v2skipped`, plan replay on a pack copy):** garage pavilions `green-TEJ1`
   on the slab (15.8 m below → within 0.3); `PKT4__b1` on the slab (−6 → 0.3);
   `green-TEJ3` panels on `CNTRL` (+3.06 → 0.3) and on their other buildings;
   `T4SAT_green-TEJ3` on `LEMD65` / `VRDCH` (+5.78 / +3.44 → 0.3); `rows on the datum
   outside the plan` 25 → 0; files whose own-geometry ground departs > 3 m from the
   row 138 → ≤ 20 (the residue named); carried bodies with carrier zero > 1 m off the
   ground beneath 54 → 0; round trip ok; OTHH dry run before/after.

**MEASURED (lane `v2skipped`, 2026-09-11; branch `claude/v2skipped`).**
Implemented in `airport/pack_partition.py` (§16 (1)), `airport/placement_cut.py`
(NEW: §16 (2)'s terrain cut, with §10's segment cut and the body formation
moved beside it), `airport/placement_plan.py` (the own-ground file, the
footless verdict), `airport/placement_carrier.py` (§16 (3)) and
`airport/placement_census.py` (NEW: §14/§15/§16's instruments, one
implementation for both tools).  Law: `[placement] carrier_fill_min = 0.2`.

* **THE POPULATION (1).** `_build_member`'s thickness gate is not applied
  under `[rebake] placement = "agl"`: the member is admitted with its thin
  components as parts, and ITS PARTS CARRY NO FEET — §16 (1)'s own sentence
  ("a FOOTLESS body"), forced by measurement: a two-triangle `AESlite-LEMD-VOR`
  marker reaching 50 m below its own zero was otherwise read as a footed body
  with three feet 50 m down, offered to the carrier search as ground and read
  by the census as something to stand over (every T4 body then "floated" 40 m).
  A body no part of which has a foot is FOOTLESS wherever it comes from
  (the structure-seated classes — basin, plate, deck — excluded: another law
  governs their elevation).
  LEMD `rows on the datum outside the plan` **25 → 0**, OTHH **99 → 0**.
* **THE RE-CUT (2)** runs at two levels, because a body the ε-contact graph
  formed is often ONE welded component the part cut cannot divide: the PARTS
  are grouped by the ground under them (§9's own `coarsen`, one level down),
  and where the body's own ground still spans more than `split_tol_m` its
  TRIANGLES are (`placement_cut._LineCutter.terrain_groups`, capped at
  `[rebake] line_object_stations_max`, the ground sampled once per
  `GROUND_CELL_M` of plan rather than once per triangle).  LEMD 3,091 bodies
  re-cut into 7,965 terrain groups.  A footless placement the cut DIVIDED is
  no longer one rigid span: its pieces each take the carrier they stand over.
* **THE CARRIER (3).** A LINE body never carries, nor one filling less than
  `carrier_fill_min` of its own plan box, and a candidate whose zero stands
  more than `split_tol_m` from the ground under the CARRIED body is refused
  and the search continues (LEMD: 12.8k line rejections, 12.8k fill, 10.9k
  ground refusals over the airport's searches).  With no candidate left the
  body is written at the ground under its own footprint with its authored y
  kept (`footless_own_ground`, 102 files at LEMD, 517 at OTHH) — where §15
  silently DROPPED such a body from every file.
* **THE BARS (4), matched arms on the app's 1.50.1763 LEMD frame** (the
  rebake plan + `LEMD.graded.json`, `--admit-skipped` restoring §16 (1)'s
  population into a plan written before it):

  | bar | before | after |
  |---|---|---|
  | `rows on the datum outside the plan` | 25 | **0** (OTHH 99 → 0) |
  | carried bodies with the carrier's zero > 1 m off the ground beneath | 39 | **0** |
  | files whose own-geometry ground departs > 3 m from their row | 26 | **26** |
  | `elevated bodies as own files` / `footless at datum` | 0 / 0 | **0 / 0** |
  | files | 1,103 | **1,591** (OTHH 988 → 1,466) |
  | DSF round trip (write half into a pack copy) | — | **OK**, 1,602 files, 1,601/1,601 new `OBJECT_DEF`s, 0 rows carrying an elevation, duplicate rows surviving 0 |

  The 138 of 11ai (C) was measured on the WRITTEN pack by sampling 60 vertices
  per file; the plan-side instrument above reads the body's own part boxes and
  puts the same population at 26 before and after.  The §16 (2) re-cut does not
  move it and CANNOT: the residue is bodies that lawfully ride one zero over
  sloping ground — a garage slab, a terminal roof, the T4S roof — plus the
  newly admitted `AESlite-LEMD-VOR` markers, whose two triangles span the
  airfield.  Named by class, not closed.
* **THE NAMED SITES.** `Terminal4_green-TEJ1` (the garage roof-top pavilions,
  SKIPPED and 15.8 m under the slab) is in the plan, cut into 9 terrain groups
  riding the garage's own bodies, float −1.27 … +3.70 m against the body each
  stands over (bar 0.3 MISSED, and the spread is the garage's own: `PKT4` is
  itself re-cut into terrain groups over 8 m of fall).  `Terminal4SAT_green-TEJ3`
  (SKIPPED, +5.78 / +3.44) is in the plan, five groups, float +0.00 … +0.54.
  `Terminal4_green-TEJ3` (one carried body over 1 × 2 km, +3.06 over `CNTRL`)
  rides `NAVEATR4` at **+0.00**.  `Terminal4_green-PKT4__b1` is no longer
  carried by a fence — no fence carries anything.  `green-rada__b1` reads
  −0.13 (was +13.18 on a fence at 0 m²).
* **THE REGRESSION, reported not decided.** §15 (3)'s `stands-over float > 0.5 m`
  for CARRIED bodies (bar 0) is LEMD 1 → **58**, OTHH 6 → 7.  Mechanism: §16 (3)
  chooses a carrier by the GROUND under the carried body while §15 (3) judges
  the result against the ZERO of the footed body beneath — and after the re-cut
  a neighbouring group anchored at its low-side foot can read a zero metres
  from the ground over it.  The two bars now measure different things; §16 (2)'s
  own (the carrier's zero against the ground beneath) is 0.  An owner ruling is
  needed on which is the law.
* **BUILD TIME.** The LEMD plan stage (dry run, no cut) **2.7 s → 9.9 s**, OTHH
  **28.6 → 46.4 s** — +7.2 s, 12 % of the 60 s per-airport budget, over the 1 %
  threshold and reported for the owner's decision.  The cost is the surface
  sampling the re-cut needs (913k reads at LEMD; the per-cell memo already took
  1.9 s of it back).  A vectorised surface sampler would take most of the rest
  and is not in this lane.

## §16a A carried body lives in its carrier's frame (RULINGS 2026-09-11aj)

§16 (2) and (3) as written cut and judged a carried body by the GROUND under its own
geometry; §15 (3) judges it by the ZERO of the body beneath. They disagree wherever
walls stand on sloping ground: the walls anchor at their low-side foot, the roof cut
by ground lands metres off them (LEMD carried `stands-over float > 0.5 m` 1 → 58; the
garage pavilions −1.27 … +3.70 against the slab). Resolved:

1. **A carried body is cut where its CARRIER is cut.** Its pieces are the carrier's
   terrain groups intersected with its own footprint — one piece per carrier group
   it stands over, each riding that group's zero at the authored offset. It is never
   cut by the ground under itself. A carried body standing over several carriers
   (a roof over two buildings) gets one piece per carrier.
2. **§16 (3)'s ground check is on the CARRIER**: a candidate whose zero is more than
   `split_tol_m` off the ground under its OWN feet is refused (it is itself
   mis-anchored, and would carry its error). The ground under the carried body is
   never compared.
3. **The bar for carried bodies is §15 (3)'s** `zero − zero_beneath` (≤ 0.3 m);
   `zero − ground_under_geometry` is printed for information only.
4. **Bars (lane `v2skipped2`):** garage pavilions `green-TEJ1` within 0.3 of the slab
   group beneath each piece; carried `stands-over float > 0.5 m` 58 → 0 at LEMD, ≤ 7
   at OTHH; the §16 (4) bars held (datum rows 0, fences never carry, carriers off the
   ground 0); plan stage back within LEMD ≤ 5 s / OTHH ≤ 35 s (the carried-body
   ground sampling removed); files quoted.
