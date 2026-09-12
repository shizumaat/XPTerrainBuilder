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

**MEASURED (lane `v2skipped2`, 2026-09-11; branch `claude/v2skipped2`).**
Implemented in `airport/placement_cut.py` (§16a (1): `_raw_bodies` asks §6
of the WHOLE body first and a body that comes out ELEVATED or FOOTLESS
leaves it in one piece; `_LineCutter.carrier_groups` is the carrier cut,
and `_whole_body` is §6 read once for both), `airport/placement_plan.py`
(`_carrier_pieces`, and pass 3 now walks the elevated and the footless
members through ONE path), `airport/placement_carrier.py` (§16a (2):
`carriers_for` returns the RANKED accepted carriers a body stands over —
`carrier_for` is its first element — and `anchor_ground_off` /
`Candidate.ground_off` is the mis-anchoring test) and
`airport/placement_census.py` (§16a (3)).

* **THE CUT (1)** runs on the CARRIER's groups: a carried body's triangles
  are assigned to the first carrier whose FOOTPRINT boxes their plan
  centroid falls in, best-ranked first, and one piece is made per carrier
  with triangles; a triangle over no carrier joins the winner.  No surface
  is sampled — which is the point, and also most of what §16 (2)'s cost
  was.  Carriers standing at ONE zero (within `split_tol_m`) are collapsed
  before the cut: cutting against them would make pieces `merge_rides`
  puts straight back into one file, and at a flat airport that is the
  whole bill (OTHH asks for 3,869 cuts and needs 176).
* **THE GROUND CHECK (2), AND THE READING IT TURNS ON.**  "The ground under
  its OWN feet" says the body's zero is `surface(foot) - y_foot`, the
  MEDIAN over its feet — not `surface(foot)`.  Read as the raw surface it
  refuses every building on a slope: LEMD **313** footed bodies refused as
  carriers, `green-TEJ1` one piece instead of five, and carried float 49.
  Read per foot: **117** refused, carried float 4.  The 117 are §6's
  low-side-foot fallbacks with metres of authored relief (`PKT4__b8`,
  worst foot +7.43 m) — genuinely metres off the ground under their own
  feet, and that is what the clause bars.
* **THE BARS (4), matched arms on the app's 1.50.1763 LEMD frame** (the
  rebake plan + `LEMD.graded.json`, `--admit-skipped`), `v2skipped` (main
  `9bc5b8c2`) beside:

  | bar | v2skipped | v2skipped2 |
  |---|---|---|
  | carried `stands-over float > 0.5 m` (bar 0) | 58 | **4** — MISSED |
  | footed `stands-over float > 0.5 m` (reported) | 128 | 123 |
  | `green-TEJ1` (the garage pavilions) | 9 ground groups, −1.27 … +3.70 m | **2 pieces**, on `PKT4__b5` / `__b7`, both within the bar |
  | `T4SAT_green-TEJ3` | 5 ground groups | 3 pieces, on `elect__b2` / `b6` / `b8` |
  | `green-TEJ3` | +0.00 on `NAVEATR4` | +0.00 on `NAVEATR4__b2` |
  | `green-rada__b1` | −0.13 | its own ground, worst foot −0.26 (WITHIN 0.3) |
  | `rows on the datum outside the plan` | 0 | **0** |
  | `elevated bodies as own files` / `footless at datum` | 0 / 0 | **0 / 0** (OTHH 10 → **0**) |
  | fences carrying anything | 0 | **0** (`line` 4,615 refusals) |
  | carriers refused for their own ground | 10,938 searches | 954 searches |
  | files | 1,591 | **1,328** (own-ground files 102 → 38) |
  | plan stage, 3 runs | 9.9 s | **6.30 / 6.29 / 6.36 s** — bar ≤ 5 s MISSED |
  | round trip (write half into a pack COPY) | OK | **OK**, 1,327 files, 1,327/1,327 new `OBJECT_DEF`s, 0 rows carrying an elevation, duplicate rows surviving 0 |

  OTHH, same arms: carried float 7 → **39** (bar ≤ 7 MISSED), files 1,440 →
  1,686, `footless at datum` 10 → **0**, plan stage 48.1 → **60.0 / 60.2 /
  60.3 s** (bar ≤ 35 s MISSED).
* **THE RESIDUAL, ATTRIBUTED.**  3 of LEMD's 4 and 23 of OTHH's 39 stand
  over one of the footed bodies §16a (2) REFUSES as a carrier: the body
  rides whatever the search reached next, and the census still names the
  refused one as "beneath".  The census is NOT narrowed to the law's
  candidate set — §16a (3) makes `zero - zero_beneath` THE bar and says
  nothing about narrowing it, and narrowing it took LEMD's stands-over
  population from 610 bodies to 117.  The count is printed with the
  attribution beside it instead.  OTHH's other 16 are decks and roads
  (`Bridge_03` over `Bridge_02`, `TerminalRoads_01` over
  `TerminalRoads_Parking`) that §16 (2) used to cut by their own ground
  into pieces that happened to match; §16a (1) gives them their carrier's
  zero across the span, and the body the census finds beneath is a
  different one.  Reported, not decided.
* **THE ARM WITH (2) DISARMED**, measured on this same tree: LEMD carried
  float 2, files 1,338, `green-TEJ1` 5 pieces; OTHH carried float 21 —
  but OTHH `footless at datum` **5 (bar 0 VIOLATED)**, because a body with
  no carrier the law refuses is a body that keeps its row.  The clause
  earns its place; its residual is the open item, not the clause.
* **BUILD TIME.**  LEMD 9.9 → 6.3 s (§16's own cost partly given back: the
  ground under a carried body is no longer sampled).  OTHH 46.4 → 60.2 s:
  the carrier cut PARSES a member's OBJ8 where §16 (2)'s triangle cut did
  not (`solid_components` on OTHH's objects, 42 s of the stage in the
  first arm, 176 members in the last).  Over the 1 % threshold and
  reported for the owner's decision; a vectorised `solid_components` or a
  per-member component cache would take most of it and is not this lane.

**MEASURED (round 3, lane `v2skipped3`, 2026-09-11; branch `claude/v2skipped3`).**
The owner's 11ak items (1)-(4), on the app's 1.50.1763 frame (the rebake
plan + `<ICAO>.graded.json`, `--admit-skipped`), against main `adb64ed1`
(= `v2skipped2`).  Implemented in `airport/placement_census.py` (1),
`airport/placement_cut.py` (`_LineCutter.foot_groups`, the §16 (2) cut
BY FOOT) (2), and `airport/obj8.py` + `airport/placement_carrier.py` (4).

* **THE CENSUS SPLIT (1).**  A CARRIED body's `beneath` is the carrier
  THE LAW CHOSE — `merged_into`, resolved BY IDENTITY over every row
  that reads a zero, the kept-whole placements included.  A body the
  law refused as a carrier (§16a (2)) is no longer called "beneath":
  the row is counted and named as its own class, `carried over a
  refused body`, printed with how far that body's own feet stand off.
  The two counts ADD to the old one (LEMD 4 = 0 float + 3 refused + 1
  the identity reading closed).
* **THE FOOT RE-CUT (2).**  §16 (2)'s two cuts ask what the GROUND under
  a body does; neither sees the body whose own FEET disagree over ground
  that barely moves (`green-PKT4__b8`: 0.5 m of terrain, 7.43 m of
  authored relief), which is exactly the body §16a (2) refuses.  The
  feet are now grouped by the zero each of them says the body has
  (`surface(foot) - y_foot`, §7's reading and `anchor_ground_off`'s, so
  ONE reading decides both the cut and the refusal), and each triangle
  joins the group of the foot nearest it in plan — a wall stays with the
  floor it stands on.  LEMD refusal set **117 -> 21**; OTHH **55 -> 19**.
  A cheaper gate — the feet's AUTHORED span alone, no surface read — was
  tried and REFUTED: the cut then fired 195 times instead of 615 and
  LEMD's refusal set came back at 100, because a body is off its own
  feet over ground that moves under it as well as over relief it was
  authored with.
* **OTHH'S DECKS AND ROADS (3): NOT THE SHARED-ZERO COLLAPSE.**  The
  decks ARE cut across their carriers (`Bridge_03_LOD0_000` in four
  pieces at zeros 3.82 / 4.94 / 5.43 / 8.32), and the collapse cannot
  have merged them: it drops only a candidate standing within
  `split_tol_m` of one already kept, and a ramp's groups stand metres
  apart.  The mechanism is the INSTRUMENT: those decks ride a carrier
  written WHOLE, whose `merged_into` names its MEMBER RESOURCE
  (`_carried_file`'s `carrier_res` when the carrier was not written)
  and not a body file — 271 carried bodies at OTHH, 1 at LEMD — so the
  census could not find the law's carrier at all and fell back to
  whatever the footprint lay over: the road body on the ground beside
  the ramp, +4.36 m.  Resolving the kept-whole key closes all ten.
  What remains true of those placements is the class the report already
  counts by name, `N onto a carrier still on its authored row` (OTHH
  245): the carried body takes the carrier's COMPUTED anchor while the
  carrier keeps its authored row.  Reported, not this lane's bar.
* **THE TIME (4).**  The per-member PARSE CACHE was built and REFUTED:
  one cutter per member and the member IS the file — 318 parses over 318
  distinct files at OTHH (1 cache hit), 179 over 179 at LEMD (0) — and
  it cost ~230 MB of RSS for nothing.  Deleted.  What the 42 s actually
  was: `obj8.solid_components` masking EVERY triangle once per component
  (a clutter object publishes thousands of components over tens of
  thousands of triangles — quadratic in the two).  Read in ONE stable
  sort and split at the label boundaries it is the same components in
  the same order: OTHH 66 -> 43.5 s.  The rest was
  `bind_plan_overlaps` asking `overlap` 77 million times: ordered by the
  hull's south edge the scan breaks once a candidate starts north of
  this body's north edge — the same partition, since union-find does not
  care in what order it is told.  OTHH 43.5 -> 31 s.
* **THE BARS, matched arms:**

  | bar | main `adb64ed1` | `v2skipped3` |
  |---|---|---|
  | LEMD carried `stands-over float > 0.5 m` (bar 0) | 4 | **0** |
  | LEMD `carried over a refused body` (new class) | (3 of the 4) | **0** |
  | LEMD footed float > 0.5 m (reported) | 123 | 60 |
  | LEMD bodies §16a (2) REFUSES as carriers | 117 | **21** — bar <= 20, MISSED BY ONE |
  | LEMD files | 1,327 | **1,371** |
  | LEMD feet > 3 m / floating | 583 / 9,885 | 527 / 9,606 |
  | LEMD `rows on the datum` / `footless at datum` / elevated own files | 0 / 0 / 0 | **0 / 0 / 0** |
  | LEMD fences carrying anything | 0 | **0** |
  | LEMD plan stage, 3 runs | 6.37 / 6.14 / 6.21 s | **5.64 / 5.66 / 5.69 s** — bar <= 5 s MISSED |
  | LEMD round trip (write half into a pack COPY) | — | **OK**, 1,371 files, 1,370/1,370 new `OBJECT_DEF`s, 0 rows carrying an elevation, duplicate rows surviving 0 |
  | OTHH carried float (bar <= 7) | 42 | **0** |
  | OTHH footed float | 74 | 72 |
  | OTHH bodies refused as carriers | 55 | **19** |
  | OTHH files | 1,679 | **1,622** |
  | OTHH plan stage, 3 runs | 58.75 / 59.26 / 59.40 s | **31.24 / 31.36 / 31.05 s** — bar <= 35 s MET |

* **THE RESIDUE, NAMED.**  LEMD's 21 refused carriers are 13 BASIN
  bodies and 8 others.  The 13 are anchored at their RIM by §6/§14 (2) —
  the pit was cut to the object, and the basin's zero is the rim and not
  its feet — so `anchor_ground_off`, which reads their feet, refuses
  every one of them by construction (`Ground-FSX-LEMD03__b0` 6.17 m,
  `-LEMD85__b0` 5.87, `animRadarbig__b0` 5.09 on ONE foot,
  `T4STower-LEMDzaun__b0` 4.34, `Bridge3__b0` 4.02, `LEMD60__b5` 3.96,
  `LEMD35__b0` 1.23, `T2SL3__b0` 1.18, `TEJ1__b0` 1.12, `T2SL2__b0`
  0.59, `T2LG2__b0` 0.50, `LEMD13__b0` 0.44, `LEMD37__b0` 0.35).  The
  basin cut is EXEMPT for §14 (2)'s reason, so no cut can close them:
  whether §16a (2)'s test should read a rim-anchored body at all is an
  INTENT question for the owner, and read under its own law the number
  is 8.  The 8: `Terminal4sBlue-STRT4__b1` 4.18 m on 2 feet,
  `OldTerminal_FSX-LEMD61__b4` 1.10 on 2, `Terminal4_green-STRT4__b5`
  0.96 on 41, `Munoza-LEMDz4__b9` 0.70 / `__b12` 0.69,
  `Terminal4_green-LEMD02__b4` 0.42, `Cargo-WFS__b10` 0.40,
  `OldTerminal_FSX-LEMD54__b5` 0.35.

**MEASURED (round 4, lane `v2basincarry`, 2026-09-11; branch `claude/v2basincarry`).**
RULED (RULINGS 2026-09-11al): §16a (2)'s carrier ground test does NOT read a BASIN
body.  A basin's zero is its RIM by §14 (2) — the pit was cut to the object — and its
floor feet are authored metres BELOW that zero by construction, so `anchor_ground_off`,
which reads the feet, refuses every pit for a reason that is the basin law working (13
of LEMD's 21 refused carriers, the worst 6.17 m), and no cut can close them because the
foot re-cut is exempt for the same reason.  A basin body is therefore EXEMPT from the
refusal — it may carry, and the tower cluster on the T4S pit rides the rim — and the
census prints them as their own class, `§16a (2) basin carriers`, with how many of them
the feet test WOULD have taken out.  One line in
`placement_carrier.carriers_for._ok` (the class is the FIRST test, ahead of the
`ground_off` reading) and one in `placement_census.census_v15` (the refusal set skips
`_ar.BASIN`; `basin_carriers` / `basin_carriers_exempt` are new keys).  Matched arms on
the pristine LEMD/OTHH frames (`obj8_split_report.py --admit-skipped`, identical
inputs): LEMD refused carriers 21 → **8** (the eight named in 11al, `STRT4__b1` 4.18 m
worst), basin carriers 14 of which 13 exempt; OTHH 19 → **4**, basin carriers 21 of
which 15 exempt (the eight `tunnels/*` pits at 8.90 … 15.00 m, `Drainage_06_000__b4`
1.81, `Terminal_Parking_VCN_002__b0` 1.56).  Carried `stands-over float > 0.5 m` stays
**0 / 0**; `carried over a refused body` LEMD 0 → 0, OTHH 4 → **1**; `elevated bodies as
own files`, `footless at datum`, `footless on ground`, `basin bodies split` and `rows on
the datum` all stay **0**; the §7 foot census is byte-identical either side (74,275 feet,
`> 3 m` 527, floating 9,606 at LEMD).  What moved: one LEMD footless placement that had
no carrier the law would accept now rides a basin (footless carried 94 → 95, own-ground
26 → 25, files 1,371 → **1,369**); at OTHH 26 elevated bodies join a basin's file
(54,188 → 54,162 carried, files 1,622 both).  Round trip on a pack COPY: **OK** — 1,368
cut files, 1,367/1,367 new `OBJECT_DEF`s, 1,368 rows, 0 rows carrying an elevation,
duplicate rows surviving 0.  Twin:
`test_a_basin_body_is_never_refused_as_a_carrier`.  Suite 1,097.

## §16b The own-geometry cut is PRIOR; a rigid body is never wider than its terrain (Fable, 2026-09-11; RULINGS 2026-09-11ap)

The owner's read of 1.0.319 (RULINGS 11an/11ao, scout `v2lemd319`) found five of
its six items to be ONE mechanism §16a (1) created: a body written at ONE zero
across geometry spanning hundreds of metres to kilometres. `Terminal4_green-TEJ3__b0`
(53 triangles, 1,025 × 2,106 m) rides `NAVEATR4__b2` (111 × 56 m, 18 m² of overlap)
at one zero and reads +10.74 m at 40.4841758, −3.585487 and +16.22 m at 40.502207,
−3.5821158; T4's bamboo roof and Y-struts (`Terminal4_48__b0`, 289 × 1,168 m) and its
landside road deck (`green-STRT4__b10/b11`) ride the PARKING GARAGE across the road
(`PKT4__b0/b3`, zeros 611.23 / 612.19, the "nearest footed" fallback, fill 0.051) with
615.6–616.2 m of ground under them — 4.0–4.4 m low against piers footed at
615.8–617.0; 30 old-terminal roof plates ride `OldTerminal_FSX-LEMD38__b51`'s one
zero 602.25 across 1.8 km while the storeys under them are footed at their own metre
(coplanar plates at 614.28 … 616.33, a 2.05 m spread against wall tops within
0.34 m); the taxi-sign body `Taxisigns-SENRG__b10` (835 × 2,319 m, §9-coarsened by
intended zero with NO distance limit, zero set 1,590 m away) is +4.58 m at
40.4788449, −3.5745666. Every bar read 0: §15 (3)'s `zero − zero_beneath` is 0 by
construction for a body written at its carrier's zero, and every §16 number reads
the plan's `geom_box` (the patch over the carrier, 124 m for TEJ3) instead of the
written extent (2,342 m). The census was blind to what the eye reads.

1. **THE TERRAIN CUT IS PRIOR AND UNIVERSAL.** Every body — footed, footless or
   carried — is first cut into TERRAIN GROUPS by the design surface under its OWN
   written geometry (§16 (2) restored; read on the triangles, never on `geom_box`).
   §9's coarsening and §16a (1)'s carrier cut both act WITHIN a terrain group, never
   across one. §9 amended: bodies of one placement join into one file only when
   their intended zeros agree within `split_tol_m` AND they are plan-contiguous
   (plan gap under `[placement] coarsen_reach_m`, default 30 m); zero agreement
   alone never joins signs 1.5 km apart.
2. **EACH PIECE THEN FINDS ITS CARRIER WHERE IT STANDS** (§15; §16a (1) applies
   within the piece). A piece over a carrier of its own terrain group rides that
   carrier's zero at the authored offset — the garage pavilions on the slab remain
   exactly §16a. A piece standing over no accepted carrier anchors at the ground
   under its OWN footprint at its authored offset (§16 (3)'s fallback).
3. **THE FALLBACK CARRIER IS BOUNDED.** §15's "nearest footed" candidate (no plan
   overlap) is accepted only when its zero is within `split_tol_m` of the ground
   under the carried PIECE's footprint; otherwise it is refused and the piece takes
   (2)'s own-ground anchor. §16a (2)'s carrier-side test stays; this is the
   carried-side test, on the PIECE, which §16a struck for the WHOLE body. Under (1)
   + (3) `Terminal4_48__b0` cannot ride `PKT4__b3` at 612.19 with 616.19 beneath it.
4. **THE CENSUS READS THE WRITTEN GEOMETRY.** Every §16/§16a number is read over
   the written file's extent, never `geom_box`. New bars, both 0: `carried piece
   float over its own ground > 0.5 m` (items 3/4/5's class — 69 carried bodies
   whose plan diagonal exceeds their carrier's by > 100 m today) and `body wider
   than its terrain group` (a written body whose own-geometry ground spans more
   than `split_tol_m`; items 1/2's class — 140 bodies today whose written extent
   is > 50 m wider than their `geom_box`). §14's `spread` bar (50.81 m, 169
   placements over) is the same defect read from the other side and comes with them.
5. **BARS (lane `v2owncut`), matched arms on the APP'S WRITTEN 1.0.319 LEMD frame**
   (`o4_v2_placement_LEMD.json` + `LEMD.graded.json`; the rebake-plan replay and
   the written plan disagree — 1,371 vs 1,417 files, `> 3 m` 38 vs 235 — the lane
   names the cause (§15 (5) mesh-vs-graded sampling) and quotes the sim-read side):
   green-TEJ3's pieces within 0.3 m of the roof group beneath each (CNTRL__b0 tops
   619.40; at item 5 the `CNTRL__b1/b2/b3` group); T4 roof / struts / deck pieces
   within 0.3 m of the piers' zeros (~616); `SENRG__b10`'s panel at 604.02 within
   0.3 m; the T2 roof plates within 0.3 m of the storey beneath each; the garage
   pavilions unchanged (on the slab); OTHH carried float stays 0; plan stage LEMD
   ≤ 8 s / OTHH ≤ 45 s (the own-geometry cut samples the surface — the vectorised
   sampler 11al owed is in scope); files quoted; round trip OK on a pack COPY;
   suite green; `tools/INDEX.md` and the twins updated in the same commit.

**MEASURED (lane `v2owncut`, 2026-09-11; branch `claude/v2owncut`).**
Implemented in `airport/placement_cut.py` (§16b (1): the terrain cut is
PRIOR and UNIVERSAL and is read on the body's own written triangles —
`_LineCutter.all_tris` / `geom_points`, `terrain_groups(by_ground=True)`),
`airport/placement_geom.py` (NEW: the written-geometry reading — the
samples, the span, the median ground — ONE reading for the cut and the
census), `airport/placement_plan.py` (§16b (2): `_footless_targets`, the
per-piece carrier question, own-ground per GROUP),
`airport/placement_carrier.py` (§16b (3): the bounded fallback,
`box_gap_m`, the contiguity and terrain-group tests in `coarsen` /
`merge_rides` / `re_cut_by_terrain` / `group_at_zero`, and the
`CandidateIndex`), `airport/placement_boxes.py` + `placement_record.py`
(NEW: the 1,000-line law) and `airport/placement_census.py` (§16b (4):
`census_v16b`).  Law: `[placement] coarsen_reach_m = 30`.

* **WHAT THE CENSUS WAS BLIND TO, and it was not only `geom_box`.**  The
  plan's member for `Terminal4_green-TEJ3` carries ONE part of FOUR
  triangles (component 3 of twelve), and `obj8_split.split_obj8` gives
  every triangle no body owns to the NEAREST body — so a placement the
  plan reads as one body is WRITTEN as the whole object.  Its own-ground
  span read 0.22 m on the plan's parts and 8.06 m on the file, which is
  why every §16 number was green while the eye read +16.22 m.  Each body
  now publishes `geom_pts`: one sample per 10 m cell of the triangles ITS
  FILE WILL CONTAIN (the lowest thing over each patch), thinned to 32 by
  the farthest-point walk so the extremes survive.
* **THE 1,371-vs-1,417 DISAGREEMENT (5), ATTRIBUTED.**  Same population
  either side — 324 splits, 0 resources exclusive to either — and 101
  placements differing in BODY COUNT in both directions (−14 `Runway
  ILS/2`, +41 `OldTerminal_FSX-LEMD38`).  The cause is §15 (5)'s own:
  the app samples the MESH and the replay the GRADED surface, and over
  1,249 files common to both the surface at the same body's anchor
  differs by a median 0.42 m, p90 5.84 m, worst 46.23 m — enough to move
  a coarsening or terrain-group boundary at `split_tol_m` 0.3 m.  Not a
  one-line matter and not fixed: the sim-read side is the WRITTEN (mesh)
  frame, and the replay is comparative only.  Every site number below is
  read on the written frame; every bar on matched replay arms.
* **THE FIVE SITES, on the WRITTEN frame** (app 1.0.319's pack and plan
  against this lane's write into a pack COPY, the same reader both
  sides):

  | site | 1.0.319 | `v2owncut` |
  |---|---|---|
  | item 3, `green-TEJ3` at 40.4841758,−3.585487 | ONE body at zero 616.27, plate at **622.98 = +10.74 m** over the ground, 3.4 m over `CNTRL__b0`'s roof | `TEJ3__b1` on `CNTRL__b1`'s zero 612.27, plate at **618.58** against that roof's own top **618.60** (0.02 m) |
  | item 5, same body at 40.502207,−3.5821158 | **627.03 = +16.22 m** | `TEJ3__b3` on `CNTRL__b3`'s zero, plate **620.38** against `CNTRL__b2`'s top **620.27** (0.11 m) |
  | item 4, `Terminal4_48` (T4 roof + Y-struts) | ONE body, zero 612.19 with **616.21 m of ground beneath it (−4.02 m)**, riding the garage across the road | 3 pieces, zero−ground median **−0.36**, worst −1.62 |
  | item 4, `green-STRT4` (the landside road deck) | `__b10` zero 611.23, ground 616.34 (**−5.10 m**) | 41 pieces, median **−0.01**, 8 over 0.3 m |
  | item 2, `Taxisigns-SENRG` at 40.4788449,−3.5745666 | `__b10` **+4.58 m**; 38 of the resource's 80 bodies over 0.3 m from their own ground (−4.05 … +5.35) | the sign at the site reads **−0.15 m**; 12 of 419 bodies over 0.3 m (−0.99 … +0.94) |
  | item 1, the T2 roof plates at 40.4673861,−3.5681144 | five plates on `LEMD38__b51`'s one zero 602.25 — 616.08 / 616.69 / 616.97 / 618.82 / 618.93 against wall tops 615.34–615.75 | `tej2__b0` at **615.41** against `T2FT2zwei`'s top 615.75 (−0.34); the other plates split across their own carriers |

* **THE BARS (5), matched replay arms on the same frame** (the 1.0.319
  rebake plan + `LEMD.graded.json`, `--admit-skipped`; BEFORE is this
  lane's instrument commit `0be4ef5a` on main's law, so both arms are
  read by the same instrument):

  | bar | before | after |
  |---|---|---|
  | `carried piece float over its own ground > 0.5 m` (bar 0) | 115 | **120 — MISSED** |
  | `body wider than its terrain group` (bar 0) | 821 of 1,357 (widest 29.80 m) | **1,556 of 3,243 (widest 12.19 m; carried 138, footed 421, line 997) — MISSED** |
  | §15 carried `stands-over float > 0.5 m` (bar 0) | 0 | **0** |
  | §14 `footless at datum` / `on ground` / `basin split` | 0 / 0 / 0 | **0 / 0 / 0** |
  | §16 `rows on the datum outside the plan` | 0 | **0** |
  | §14 `spread` | 50.81 m, 170 placements over | 50.78 m, 193 over |
  | files | 1,371 | **3,272** |
  | round trip (write half into a pack COPY) | — | **OK**, 3,272 cut files, 3,276/3,276 new `OBJECT_DEF`s, 0 rows carrying an elevation, duplicate rows surviving 0 |
  | plan stage, 3 runs | 6.79 / 6.83 / 6.97 s | **10.01 / 10.20 / 10.11 s — bar <= 8 s MISSED** |

  OTHH, same arms: carried own-ground float **308 -> 196**, wide
  **141 -> 143** (32 basin bodies exempt), §15 carried float **0 -> 0**
  (the spec's "stays 0" MET), `footless at datum` 0, files 1,525 ->
  1,781, plan stage (3 runs) 48.7 / 41.3 / 41.8 -> **46.4 / 51.5 /
  53.4 s — bar <= 45 s MISSED**.
* **THE TWO BARS' RESIDUE, ATTRIBUTED — and the reading that says why
  they cannot be 0 as written.**  A body's cut ATOM is its TRIANGLE, and
  this pack authors slabs, ramps and roof plates as four of them:
  `green-PKT4__b19` is 4 triangles over 6.22 m of fall, and no cut short
  of re-meshing the object can make its own ground span 0.3 m.  The wide
  residue is therefore dominated by two classes the law cannot divide —
  big-triangle solids, and the BASIN bodies §14 (2) exempts (15 at LEMD,
  32 at OTHH, counted apart).  The carried residue is the same class one
  step on: a piece riding a carrier whose zero is its low-side foot (the
  T4S tower cluster on the pit RIM, 7 m above the pit floor, is the
  worst of them and is lawful by 11al).  Reported, not closed.
* **TWO CUTS TRIED AND REFUTED, and DELETED.**  (a) The FOOTED triangle
  cut read by GROUND instead of by intended zero: it slices a rigid
  footed solid wherever the terrain under it moves 0.3 m (LEMD files
  1,371 -> 5,891, a garage into 20 slices) and STILL misses the bar for
  the atom reason above.  (b) The SEGMENT cut followed by a ground cut
  per station: LEMD's fence and grass files 2,227 -> 7,722 for a class
  the eye does not read — §10's station is already a terrain reading
  every 100 m at its own mid-foot.  Both are gone; §16b (1)'s universal
  cut runs on the CARRIED class, which is the class 11ap attributes.
* **THE FILE COUNT, and the REACH (Fable's amendment).**  The lane first
  measured `coarsen_reach_m` at 30 m and reported the cost: shorter than
  §10's `line_segment_m` 100 m, it makes every line STATION its own file
  by construction — LEMD line-segment files 300 -> 1,755 and the airport
  1,371 -> **4,050**.  RULED: the reach is never below the station
  length, default **100 m**, and what forbids a body taking its zero
  from one a kilometre away is the TERRAIN-GROUP test beside the reach,
  not the reach.  At 100 m: LEMD files **3,272** (line segments back to
  one file per terrain group), OTHH **1,781**, both bars slightly better
  (120 / 1,556 and 196 / 143), the plan stage 11.4 -> **10.1 s** and
  OTHH 57.6 -> **50.4 s**, every site number held (item 3 0.02 m, item 5
  **0.04 m**, the gate-5 sign −0.15 m, `tej2__b0` −0.34 m against the T2
  wall top, `Terminal4_48` median −0.77 m), §15 carried float **0**.
  The signs do NOT chain back to kilometres: `Taxisigns-SENRG` is 316
  files (was 419 at 30 m, 80 at 1.0.319) and its zero-vs-own-ground runs
  −1.52 … +0.71 m with 24 of 316 over 0.3 m — where 1.0.319 had 38 of 80
  over, worst −4.05 / +5.35.  A twin holds the reach at or above the
  station length.
* **BUILD TIME.**  LEMD plan stage 6.9 -> 11.4 s over 3 runs per arm
  (bar <= 8 s MISSED), OTHH 43.9 -> 57.6 s (bar <= 45 s MISSED).  The cost is the cut itself —
  4,056 bodies where main makes 1,374, and §16b (2) asks the carrier
  question once per piece.  Three optimisations the measurement forced
  are already in (the vectorised surface read `placement_geom.surface_many`
  and `sampler.many`; a per-unit SOLID set and a plan-cell
  `CandidateIndex`, which took 11 M candidate rankings to 1 M; a
  memoised `_m_per_deg` and a vectorised piece box), worth 6.3 s
  together; the remainder is the body count.  Reported for the owner's
  decision.
* **Twins:** `test_the_16b_census_reads_the_written_geometry_not_the_plan_box`,
  `test_a_basin_body_is_exempt_from_both_16b_bars`,
  `test_coarsening_joins_only_bodies_contiguous_in_plan`,
  `test_the_coarsening_never_joins_across_a_terrain_group`,
  `test_the_fallback_carrier_is_bounded_by_the_ground_under_the_piece`,
  `test_the_candidate_index_offers_the_same_carriers_as_the_full_scan`;
  two §16a twins amended where §16b supersedes them.  Suite 1,103
  passed / 1 skipped.

## §14a The basin body follows its RING (Fable, 2026-09-11; RULINGS 2026-09-11ap item 6)

§24 (1) puts the apron's rim vertices ON the basin's cut ring AT THE APRON'S LEVEL —
the ring follows the apron, and at LEMD's T4 landside basin (`basin_wall:0@851`,
breakline 715, 59 nodes) its z runs 597.68 … 599.52, a 1.84 m spread. §14 (2) writes
every basin body at ONE rim point (598.39), so the wall base stands +0.71 m above
the apron edge on one arc and −1.13 m below it on another: the owner's "small gap
between wall and apron", read from 1.0.315 through 1.0.319 while the ring's
`spread` bar read 0.01 (it measures the bodies' agreement with each other, not with
the ring). And `Ground-FSX-LEMD13__b0` (5 × 18 m, 86 % of its vertices inside the
ring) is anchored on the rim at 598.31 while the floor under it is ~591: the loose
white slab in the garden.

1. **THE WALL IS CUT BY THE RING'S STATIONS.** A basin body is cut like a line
   object (§10): one piece per rim ARC over which the ring's z agrees within
   `split_tol_m`, each piece anchored at ITS arc's rim point at that arc's z. The
   floor plate under each piece follows (§24 (2): floor = plate − clearance, per
   arc). The bar: wall base within 0.3 m of the graded apron edge at EVERY ring
   node (today +0.71 / −1.13). §16b (1)'s universal cut does not read a basin's
   floor feet (the §15 exemption stands); the ring IS its terrain.
2. **A MEMBER INSIDE THE RING IS A FLOOR BODY.** A body of the basin resource with
   more than half its vertices interior to the ring anchors on the FLOOR under its
   own footprint at its authored offset (§16 (3)), never on the rim. `LEMD13__b0`
   from 598.31 to the floor.
3. **REPORTED, NOT BARRED HERE:** the parapet top's median 0.43 m horizontal
   offset outside the ring (§24 (1)'s 1.0 m identity spacing holds); a second
   round if the owner's read still shows a gap.
4. **BARS (lane `v2basinring`)**: (1) and (2) above on the 1.0.319 frame; the
   basin `spread` bar re-defined as max |wall base − ring z| over the ring's
   nodes; OTHH's 21 basin carriers (eight `tunnels/*` pits at 8.9–15.0 m) unchanged
   in float; round trip OK on a pack COPY; suite green; INDEX + twins.

**MEASURED (lane `v2basinring`, 2026-09-11; branch `claude/v2basinring`).**
Implemented in `airport/basin_ring.py` (NEW: the whole of §14a — `arcs_of`,
`ring_reading`, `ring_arcs`, `member_kind`, `ring_bar`, and the ONE spelling
of the wire between the cut and the bar), `airport/anchor_rule.py`
(`RimRing.z`, additive), `airport/placement_plan.py` (the ring's heights are
read off the graded doc; the bind keys; §14a (2)'s bodies take no carrier),
`airport/placement_cut.py` (the basin branch of `_raw_bodies`),
`airport/placement_carrier.py` (`bind_plan_overlaps(bind_keys=...)`, additive)
and `airport/placement_census.py` (the re-defined bar, printed by both tools
from the one `census_v14` call).

* **THE SITE, REPRODUCED FIRST on the app's WRITTEN 1.0.319 frame**
  (`o4_v2_placement_LEMD.json` + `LEMD.graded.json`): `basin_wall:0@851`,
  **59 nodes, z 597.68 … 599.52** (1.84 m); **nine** basin bodies
  (`Ground-FSX-LEMD03/13/36/37/85`, `T4STower-LEMDzaun`, `-SWbaume`,
  `animRadarbig`, `Terminal4sBlue-LEMD35`) all on ONE rim zero **598.39**;
  wall base vs the graded apron edge per ring node **+0.71 … −1.13 m, 9 of
  59 nodes over 0.30**, while the §14 `spread` bar read **0.01**.
* **THE READING §14a (2) NEEDED, AND WHAT THE MEASUREMENT CHANGED.** Read as
  written — "more than half its vertices interior to the ring" — the rule
  sends the pit's OWN WALL to the floor: the wall stands ON the ring, so
  plain ray casting calls it interior (`LEMDzaun` 60 %, median distance to
  the ring 0.35 m). Two readings the site forced, both reported:
  (a) a vertex is INTERIOR only when it is inside AND further than the
  identity spacing (1.0 m, §24 (1)'s own bar) from the ring, and the share
  is taken over the vertices that are DECISIVELY one side or the other — a
  body straddling the ring (`LEMD13` has half its vertices within 0.5 m of
  it) reads 76 % interior instead of 46 %;
  (b) what separates the pit's SHELL from a thing standing in it is the
  RIM PLANE, not the footprint: the shell is authored INTO the pit (LEMD
  −3.2 … −7.05, OTHH −1.4 … −15.0) and a thing standing in it is authored at
  the rim like anything on the ground (`LEMD13` −0.08). The admission is
  `[placement] split_tol_m`. At LEMD this admits `LEMD13` alone of the pit's
  members; at OTHH it admits **none** of them, which is why the 21 basin
  carriers are untouched.
* **§14a (1) AS BUILT, and the one deviation.** The ring is cut into ARCS
  whose z agrees within `split_tol_m` (LEMD: **6 arcs**), each carrying the
  rim point nearest its mid-level; a basin body's WALL BAND — the triangles
  whose nearest VERTEX stands within 3 m of a ring NODE — is cut by them,
  one piece per arc at that arc's rim point. **DEVIATION, reported not
  decided:** the body's INTERIOR remainder keeps §14 (2)'s single rim point
  instead of following its arc. §14a (1)'s "the floor plate under each piece
  follows (§24 (2) per arc)" needs the DESIGN SURFACE to cut the trench per
  arc as well; the trench is one level today, so a floor plate written per
  arc would step where the terrain under it does not and spend the 0.5 m
  clearance the plate renders in. That half is §24's and is not this lane's.
* **THE BAR (4), matched arms on the 1.0.319 frame** (`obj8_split_report.py`,
  `--no-cut`, identical inputs; main `73fa97af` beside):

  | bar | before | after |
  |---|---|---|
  | `max abs(wall base − ring z)` over the ring's nodes (bar ≤ 0.30) | **1.12 m, 9 of 59 nodes over**, +0.72 … −1.12 | **0.18 m, 0 over**, +0.11 … −0.18 |
  | nodes on an arc the pit has NO WALL on (reported, not barred) | 0 | **3** (z 598.90 / 599.52 / 598.90; 8.6–15.8 m from the nearest basin vertex — nothing stands there) |
  | `LEMD13__b0` | rim, zero 598.39, ground under its own base 597.18–597.67 | **own ground, 594.91 / 597.36 / 597.28** — off the rim, three pieces |
  | LEMD basin bodies cut by the ring's arcs | — | 11 into 20 piece(s); floor members 18 |
  | LEMD files | 1,371 | **1,394** |
  | LEMD feet > 3 m / floating | 518 / 9,509 | **412 / 9,014** |
  | LEMD §16 carried over 1 m / own-ground > 3 m | 82 / 38 | **72 / 36** |
  | LEMD `footless at datum` / `on ground` / `basin bodies split` / `elevated own files` / carried stands-over float | 0 / 0 / 0 / 0 / 0 | **0 / 0 / 0 / 0 / 0** |
  | LEMD footed stands-over float > 0.5 m (reported) | 57 | 63 |
  | LEMD round trip (write half into a pack COPY) | OK | **OK**, 1,394 files, 1,394/1,394 new `OBJECT_DEF`s, 0 rows carrying an elevation, duplicate rows surviving 0 |
  | OTHH basin carriers / exempt | 21 / 15 | **21 / 15** |
  | OTHH feet census (87,577 feet, `> 3 m` 32, floating 4,338) | — | **byte-identical** |
  | OTHH carried stands-over float | 0 | **0** |
  | OTHH files | 1,525 | 1,558 |

* **AN INDEPENDENT GEOMETRIC PROBE, on the WRITTEN pack copies of both arms**
  (each ring node against the nearest written basin piece's own vertices,
  reading nothing the plan says): **+0.71 … −0.50 m, 6 of the 48 walled
  nodes over 0.30 → +0.11 … −0.66 m, 1 over**. The residual is one triangle
  straddling the boundary between two arcs (node 3, its nearest geometry
  0.23 m away belonging to the piece cut to the neighbouring arc): whole
  triangles cannot be in two arcs at once.
* **§14a (3), REPORTED.** The parapet top's horizontal offset, over the 660
  wall-band top vertices of the T4S pit: **median −0.63 m, 38 % outside the
  ring** (before: −0.58 m, 39 % outside) — the parapet stands mostly INSIDE
  the ring, not outside it; §24 (1)'s 1.0 m identity spacing holds either
  way and the reading barely moves. The 0.43 m outside quoted in §14a (3) is
  not what this frame reads.
* **WHAT ELSE MOVED, named.** At OTHH 33 plates authored at the rim plane
  inside a drainage ring are §14a (2)'s own class and now stand on their own
  ground (+33 files, `plate_only` 3 → 29); no basin body of OTHH changed
  class, anchor or float. At LEMD the footed `stands-over float > 0.5 m`
  reading rises 57 → 63 because 18 more bodies stand on their own ground and
  are compared at all; it is reported, not barred.
* **Build time:** the LEMD plan stage (`--no-cut`, 3 runs per arm,
  foreground) **5.51 / 5.51 / 5.57 s → 5.75 / 5.79 / 5.74 s**: +0.24 s, 0.4 %
  of the 60 s per-airport budget, under the 1 % threshold. OTHH 30.4 → 34.4 s
  (one run per arm, not a timing claim).
* **NOT DONE, and why.** No airport build (the brief forbids one): every
  number above is the plan replay on the app's own 1.0.319 products plus the
  write half into a pack COPY. §24 (2)'s per-arc trench floor is not
  implemented (the deviation above). The three ring nodes with no wall cannot
  be closed by any placement law — there is no object there to place.
  Suite 1,102 passed / 1 skipped (main 1,097 / 1; five new twins).

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
