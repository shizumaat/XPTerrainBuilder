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
