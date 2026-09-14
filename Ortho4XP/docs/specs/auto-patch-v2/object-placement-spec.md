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

## §8 Retirement — DONE (owner RULINGS 2026-09-12s "Retire now", lane `v2seatretire`)

The original clause: when §7 passes and the owner's reads accept LEMD and OTHH:
`emit/rebake.py`'s seat, `airport/rigid.py`'s completion, `_one_file_one_delta`, the
`.anchor_bak` vertex rewrite (restore every pack from its backups first — a one-shot restore
tool), the `o4_v2_rebake_*` JSON and their replays (`v2_rebake_replay.py`) are DELETED
(refuted mechanisms are deleted, not gated); body formation moves under `airport/placement/`.

WHAT WAS DELETED (2026-09-12): `emit/rebake.py`'s `seat`, `Sampler`, `_Datum`,
`_abutment_grade`, `_mid_span`, `_plate_reading`, `_deck_reading`, `_structure_seat` and
`_one_file_one_delta` — the module survives holding `deck_datum_from_surface` alone, which
`pipeline/build.py` calls to stamp `Member.deck_datum_z` into the plan; `emit/clusters.py`
and `emit/abutment_group.py` whole; `airport/rigid.py` whole; `model/rebake.py`'s
`MemberSeat` / `ClusterSeat` / `PadRequest` / `UnitSeat` / `SeatResult` and the `DATUM_*`
constants (the PLAN types — `Part`, `Member`, `Unit`, `FlatDatum`, `RebakePlan` — stay: the
placement path reads the same plan); `engine_v2._decision_from_seats`, `_line_drape`,
`REBAKE_RESULT_FILENAME` and the seat branch of `rebake_after_mesh`; the `[rebake] placement`
key and `engine_v2.object_stage_is_placement` (the placement path is the only object stage,
so there is no gate to read); `tools/reanchor_dsf_objects.py`; and
`v2_rebake_replay.py`'s `seat` / `bodies` / `pairs` subcommands. `seat_feet_census.py` keeps
its `--placement-plan` mode and loses the seat-result mode (the name is kept: the INDEX row,
`obj8_split_report` and the twins address it by it).

WHAT STAYS: the `.obj.anchor_bak` RESTORE of §10 — how a pack authored under the seat is put
back before the placement path writes — and v1's `auto_patch/object_rebake.py`, which is v1's
own engine's writer and reachable only through `auto_patch_engine = v1`.

NOT DONE: body formation does NOT move under `airport/placement/` (deferred — lane
`v2unitbind` held `airport/placement_*.py` in parallel).

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

## §16d THE PLAN BOXES WHAT THE WRITER WRITES (Fable 2026-09-13; RULINGS 2026-09-13h) — lane `v2unboxed`

Owner (13d items 3, 4): a dark plate ~15 m over the T4 apron; roofs still floating at
the cargo hangars. Scout `v2lemd325o` on the 1.0.325 written frame: the DSF has no
polygon with an elevation (every one of its 1,609 `.pol`/`.lin` is draped) — the
plate is an OBJECT: the FS2XPlane 10 × 10 m shadow quad every source object carries
at its origin, y = −5, normal down (`North_FSX-LEMD80.obj` is nothing else). Aerosoft
LEMD is a shared-datum pack — 2,035 of 2,109 bodies sit on two placement rows 18 m
from the owner's point — so seven such quads stack at that spot, and four ride zeros
chosen kilometres away: `Terminal4_green-T4BJO__b0` +16.37 m, `Terminal4_yellow-
LEMD16__b0` +15.90 (its box is the T4 terminal 2.27 km west), `Cargo-LEMD63__b6`
+7.13, `OldTerminal_FSX-LEMD43__b0` +2.22. At the cargo hangars `Cargo-TEJ1__b0`'s
roof plate stands +3.71 m over `NEWCO__b9`'s roof (76 of its 105 vertices lie 694 m
outside its own `geom_box`; on `NEWCO__b9`'s zero it lands 0.03 m from the roof top);
`Cargo-TEJ3__b1` the same. THE MECHANISM: `geom_box` is the hull of the ADMITTED
parts (`placement_plan.py:230`, `:298`) while the writer emits the source object's
triangles regardless — a zero-thickness one-sided quad is not admitted (`no_solid_
admitted 25`), a roof plate over another hangar was never boxed — so the geometry
rides a zero the body chose elsewhere and NO instrument reads it (§15, §16a, §16b
read the box; §7 reads feet; the quad has neither). Class: 397 of 2,109 bodies carry
geometry > 1 m outside their own box (202 > 10 m, 65 > 100 m, 8 > 1 km; 91 of them
carried/bound). Two instrument defects beside it: the cockpit block's worst
coordinate for §15/§16a/§16b rows is the PLACEMENT ROW (`placement_cockpit.py:42-60`)
— at a shared-datum pack that is one of two points for 96.5 % of bodies (12ak's
"LEMD03__b33 at 40.4928202" was that artefact); and the `nearest footed body of the
unit` fallback (`placement_carrier.py:833-843`) has no distance cap (35 binds, 19 over
100 m, one 3,323 m).

1. **EVERY WRITTEN TRIANGLE BELONGS TO A BODY WHOSE BOX CONTAINS IT.** At the split,
   a connected component — admitted as a part or not — whose plan distance from
   the body's part hull exceeds `coarsen_reach_m` (100 m) is not that body's: it is
   its own body, footless, anchored on its own ground at its authored offset
   (§16 (3)). The FS2XPlane origin plate (a one-sided, zero-thickness quad at the
   object origin below y = 0) is such a body: written on its own ground at −5 m, it
   is buried as the pack authored it. `geom_box` is the hull of what the file will
   contain, and §16b's span bar reads it.
2. **THE NEAREST-FOOTED FALLBACK IS CAPPED** at `coarsen_reach_m`; beyond it a
   footless body takes its own ground (§16 (3)).
3. **THE COCKPIT COORDINATE IS THE BODY'S**: the worst row's coordinate is the
   centre of the body's written geometry (or its worst foot), never the placement
   row.
4. **BARS (1.0.325 written frame, matched arms)**: the four plates gone from the sky
   (each on its own ground at −5 m); `Cargo-TEJ1__b0` on `NEWCO__b9` (roof base within
   0.3 m of 605.04); `TEJ3__b1` likewise; bodies with geometry > 1 m outside their
   box 397 → 0 (twin); the nearest-footed fallback beyond 100 m 19 → 0; the 11at/12h/
   12o/12z/12aq/12ar sites held; torn seams 0; §15 carried float 0; files quoted;
   plan stage LEMD ≤ 10.3 s; OTHH the same under the guard; the cockpit block's
   worst coordinates verified against the bodies' geometry (twin); suite. No build;
   the app after.

### §16d (1)–(3) MEASURED (lane `v2unboxed`, 2026-09-13; branch `claude/v2unboxed`)

Implemented in `airport/placement_orphan.py` (NEW: §16d (1)'s whole law — the
components the plan's bodies do not own, placed), `airport/placement_cut.py`
(`_LineCutter.written_components` / `plan_box_of_tris` / `_draped_components`),
`airport/placement_plan.py` (the pass between §15's candidates and §15's search;
`_geom_hull`, `Staged.geom_boxes`), `airport/placement_carrier.py` (§16d (2)'s
cap), `airport/placement_cockpit.py` (§16d (3)) and `airport/placement_seams.py`
(`census_outside_box`, §16d (1)'s bar instrument, printed by `--write-pack` and
`--torn-seams`).  Two files moved for the 1,000-line law: `_footless_targets` /
`_carrier_pieces` into `placement_body.py`, `group_at_zero` into
`placement_boxes.py`; both re-exported where every caller reads them.

* **ATTRIBUTION FIRST — the dry arm is NOT the app's arm.**  `obj8_split_report`
  on the 1.0.325 rebake plan does not reproduce the app's written carriers, and
  the cause is THE SURFACE, not the population: the app hands `build_splits`
  the built MESH sampler (`engine_v2._placement_surface(mesh_sample)`) while the
  tool hands it a `LinearNDInterpolator` over `LEMD.graded.json`'s emitted
  vertices (`surface_from_graded`).  Everything else matches — identical
  `bodies_uncoarsened` 11,135 and `line_segments` 849, identical law keys, the
  same `--admit-skipped` population — while the SURFACE-driven readings do not:
  `anchor_off_surface` 0 (app) vs 6 (dry), `carrier_refused_zero_off_ground`
  105 vs 221, `carrier_refused_far_from_carried_ground` 179 vs 274,
  `unit_clusters` 206 vs 202.  Those refusals are exactly what pushes a search
  down to the fallback rules, which is where `Terminal4-LEMD01__b0` sits
  (`elect__b0 (838 m)` written, `SENRG__b233 (512 m)` dry).  **Every bar below
  is therefore read on MATCHED DRY ARMS** — main `59790e5f` into pack copy A,
  this branch into pack copy B, the same rebake plan, the same graded surface,
  APFS clones of the live pack, the guard armed (both runs print `shared repo
  UNCHANGED`).  The app's own figures are quoted beside them where they exist.

* **THE INSTRUMENT (§16d (1)'s bar).** `census_outside_box` opens the WRITTEN
  files and asks whether every `VT` row lies inside the `geom_box` the plan
  published for that body.  On the app's live 1.0.325 pack it reads **378** of
  2,109 bodies over 1 m (the scout's 397 under its own fixed metres-per-degree;
  same population, same 8 over a kilometre, worst `Munoza-LEMD80__b0` 3,682 m).

  | bar (matched dry arms) | A (main) | B (branch) |
  |---|---|---|
  | §16d bodies with geometry > 1 m outside their box | 390 | **0** (0 even over 1 cm) |
  | nearest-footed fallback binds / over 100 m | 49 / 29 | **21 / 0** |
  | §16c torn seams outside line/arc pieces | 0 | **0** |
  | §16c single-component resources in ≥ 2 files | 0 | **0** |
  | §15 carried body floating over its carrier | 0 | **0** |
  | duplicate rows of a split placement surviving | 0 | **0** |
  | DSF round trip / new `OBJECT_DEF`s read back | OK 2,141 | **OK 2,279** |
  | files | 2,141 | **2,279** |

* **THE FOUR PLATES (§16d (4)).**  Each is now its own footless body on its own
  ground with its authored y kept, so it renders 5 m UNDER the ground the pack
  put it over — buried, as authored:

  | plate | A: render − ground | B |
  |---|---|---|
  | `Terminal4_green-T4BJO` | **+15.94** | −5.00 (ground 595.81) |
  | `Terminal4_yellow-LEMD16` | **+15.73** | −5.00 |
  | `Cargo-LEMD63` | **+5.77** | −5.00 |
  | `OldTerminal_FSX-LEMD43` | **+1.72** | −5.00 (ground 595.82) |

  (the app's own frame read +16.37 / +15.90 / +7.13 / +2.22 — the same four
  plates, the surface difference above.)

* **THE CARGO ROOFS.**  `Cargo-TEJ1`'s roof plates are no longer one carried
  body riding a zero chosen elsewhere: each component finds the hangar it stands
  over.  The piece over `NEWCO__b9` has its roof base at **604.95** — 0.09 m
  from the hangar's authored roof top 605.04, inside the 0.3 m bar; the piece
  over `NEWCO__b10` reads 604.72 on its own hangar.  `Cargo-TEJ3` likewise
  (ten pieces on `CNTRL`, `FBRIK__b0/b1`, `NEWCO__b0/b3/b5/b8/b11/b12`, `TNT__b3`).

* **THE NAMED SITES HELD** (11at/12h/12o/12z/12aq/12ar; base planes per
  resource, arm A → arm B): `Terminal4_green-TEJ3` 610.41–617.17 → identical;
  `Terminal4SAT_green-TEJ3` 589.47–597.26 → identical; `HANG3` 605.73–606.06 →
  identical; `LEMD47` one body 603.53 → identical; `Bridge2` 598.73–607.03 →
  identical; `TABOX` spread 0.01 → identical; `T2NBG` 602.81–607.24 → identical;
  `green-PKT4` and `Terminal4_green-TEJ1` identical; `Terminal4_48` one body,
  spread 0.00 → identical.  `green-STRT4` gains 5 files (19 → 24) at the SAME
  base range 597.54–617.71: the orphan components now have files of their own
  inside the range, not outside it.

* **A LATENT WRITER DEFECT FOUND AND FIXED.**  `obj8_split` named a body's file
  by its index in the LIVE list (`body_resource_name(rel, k)`) while the plan
  spells it `body_resource_name(resource, body_id)` and the DSF row is written
  on the plan's name.  A body the cut leaves with NO triangle (its geometry
  inside an ANIM block another body owns) therefore shifted every later body's
  file one name down — the row carried the NEXT body's geometry at this body's
  zero.  Measured at LEMD: `OldTerminal_FSX-DCNEUN`'s `__b0` row held `b1`'s
  object, 254 m from `b0`'s own box.  The file is now named by its body, and a
  body with no file is dropped from the plan's rows (`bodies_without_a_file`) so
  no `OBJECT_DEF` points at a file nothing wrote.

* **THE COST, REPORTED NOT HIDDEN.**  LEMD plan stage **13.6 → 17.8 s** (wall
  16.81 → 21.08 s, medians of 3 foreground runs each; the branch's own
  `plan stage` line is new and reads 17.6–18.2 s, the baseline's inferred from
  the same fixed 3.2 s of tool overhead).  §16d (4)'s `LEMD ≤ 10.3 s` is
  **MISSED on BOTH arms in this frame** — the 10.3 s figure was read without
  `--admit-skipped`, which this replay needs.  OTHH plan stage **≈ 83 → 86.1 s**
  (wall 86.99 → 89.89, +3 %), the ≤ 60 s bar missed on both arms as it was at
  12ap.  The cost is the POPULATION: LEMD now places 27,737 components the plan
  never saw (19,905 joined to a body within the reach, 7,832 their own bodies),
  OTHH 143,950 (98,776 / 45,174), and 7,786 more carrier searches run at LEMD.
  Three optimisations already took most of it back and are part of the change:
  `written_components` hands back numpy arrays and the caller builds Python
  triples only for what it places; the joined components of one group are ONE
  append, not one per component; `group_at_zero` memoises each group's zero and
  ground range on its length (29.6 M inner steps, 9 s of the profiled stage).
  A further reduction is a new question, not this lane's.

* **MOVING THE WRONG WAY, NAMED.**  §16b's two counts rise because the
  population they read grew: `carried piece float over its OWN ground > 0.5 m`
  120 → 151 and `body wider than its terrain group` 1,037 → 1,116 (both already
  over their bar 0 on main).  The rise is the components that previously stood
  in some other body's file where NO instrument read them; they are now bodies
  with their own ground reading.  `§16 CARRIED bodies whose carrier's zero is
  over 1 m from the ground under their own geometry` 62 → 81 (information only),
  and COCKPIT CRITICAL visual 459 → 494 for the same reason.

* **SUITE** `tests/auto_patch_v2 tests/test_harness.py
  tests/test_role_edge_census.py tests/test_mesh_sampler*.py
  tests/test_post_mesh.py tests/test_object_rebake.py`: **1,234 passed, 1
  skipped**, twice.  Twins: `test_16d_1_a_component_beyond_the_reach_is_its_own_body`,
  `test_16d_1_every_written_triangle_lies_inside_its_body_box` (the bar as a
  property), `test_16d_2_the_nearest_footed_fallback_is_capped`,
  `test_16d_3_the_cockpit_coordinate_is_the_bodys_not_the_row`.
  `coarsen_reach_m <= 0` DISARMS the reach (the convention every other
  plan-contiguity key takes): the component then joins the nearest body.


### §16d (4)–(6) Carried components group by carrier; the ground bound is member-agnostic; a body anchors on the pad it stands on (Fable 2026-09-13; RULINGS 2026-09-13m)

Scout `v2kclt1o` on KCLT (Nimbus, native XP12: master models per material — `paredes_N`
walls, `techos_N` roofs, `vidrios` glazing — each on ONE placement row; 34 rows carry 71
split placements, bodies up to 1,628 m from their row): (a) hangar wall `005_ALB__b9`
5.04 m into its pad — a SAME-MEMBER §16c (7)/(8) bind to a body 500 m away on the
apron; 12ap's 0.5 m ground bound tests only `member != top.member`, so it was skipped
(the cluster spans 714 m at one zero; the airport's worst §17 row +5.96 m); (b) roof
plates `001_ALB__b5/b6/b11/b18/b28/b29` float +2.5 … +7.4 m — elevated bodies of 3–12
components spanning 154–1,774 m carried at ONE zero (`carried_bodies_uncut` 5,295 vs
3 cut by carrier), the walls under them correctly seated; (c) the terminal: one pad
`building80` (1.19 m of relief); 213 bodies overlap it, zeros 210.5–223.7 — the 80
whose ANCHOR POINT lands on the pad agree with it to 1.13 m, the 133 whose anchor
point lands on apron/adjacent ground (213.8–224.6) do not; clusters by contact are 272
separate things at one zero each; 12 rest-on carriers with authored gaps to −9.9 m;
a wall carried by GLAZING; a 20-vertex z = 0.00 crater in apron face 661 (`dsf:pol31`)
— design surface, not object law (RULINGS 13m, lane `v2zerocrater`).

4. **A CARRIED BODY'S COMPONENTS GROUP BY CARRIER.** Each connected component of a
   carried (elevated / footless) body finds the footed body IT stands over (§15's
   overlap at the component); components over different carriers are different
   pieces, each at its carrier's zero; a component over none anchors on its own
   ground (§16 (3)). §16a (1)'s "cut where the carrier is cut" and (1)'s reach are
   read per component. A roof resource of twelve plates over twelve buildings is
   twelve pieces.
5. **THE GROUND BOUND IS MEMBER-AGNOSTIC**: §16c (7)'s bind holds only while the
   bound body's own-ground zero is within `visual_m` 0.5 of the senior's, same
   member or not (12ap (A) applied everywhere); a cluster's zero-plane span obeys it.
6. **A BODY ANCHORS ON THE PAD IT STANDS ON.** Where a footed body's written
   geometry lies mostly on a `building` pad, its anchor point is chosen on that pad
   (the low-side foot that lies on the pad, else the pad's level under the body's
   centroid) — never on the apron or ground it happens to spill onto. The pad's own
   relief (§20: 1.19 m over 900 m at KCLT's terminal) is a §20/§28 reading, reported.
7. **BARS (KCLT 1.0.324 frame + LEMD 1.0.325 frame, matched arms)**: `005_ALB__b9` on
   its pad (−5.04 → within 0.5); the six `001_ALB` roof bodies on their walls (each
   piece within 0.5 m of the wall top beneath it); terminal bodies anchoring off
   every pad 133 → 0, the complex's zero spread 13.2 m → the pad's relief; the
   glazing carrier named and, if glazing is footless by authoring, excluded by the
   existing solid test (report, do not name-match); the LEMD sites held; seams 0;
   §16b carried-own-ground bar at KCLT 32 → quoted; files; plan stage; suite.

### §16d (4)–(6) MEASURED (lane `v2unboxed`, 2026-09-13; branch `claude/v2unboxed`)

Implemented in `airport/placement_body.py` (§16d (4): `_atom_targets`, one carried
target per ATOM, and `CARRIED_ATOMS_MAX`), `airport/placement_plan.py` (the split
before §15's search, carrying the SOURCE group so §16c (7)'s cluster membership
survives it), `airport/placement_atom.py` (§16d (5): the `member != top.member`
clause deleted) and `airport/anchor_rule.py` (§16d (6): `pad_majority`, and the
`pads` argument WIRED at last).  `placement_geom.py` took `written_components` /
`part_tris` / `plan_box_of_tris` for the 1,000-line law.

* **THE ATOM, NOT THE BARE COMPONENT.**  §16d (4) says "each connected component";
  the division here is by §16c (1)'s ATOM (`_comp_blocks`) — the component, or the
  CLUSTER §16c (6)/(7) bound it into.  Dividing a rigid cluster would undo that law,
  and the two readings are the same wherever no cluster exists.  **Reported as a
  deviation from the sentence, held to be its intent.**

* **BARS (KCLT 1.0.324 frame, matched dry arms; the write half into an APFS clone,
  guard armed, `shared repo UNCHANGED` on every run).**

  | bar | before (this branch after §16d (1)–(3)) | after |
  |---|---|---|
  | `005_ALB__b9` vs its `building` pad | **−5.04** (12ap's frame) / −5.85 here (zero 210.46, pad 216.31) | **+0.02** (zero 215.51, pad `building26` 215.49–215.51) |
  | widest RETAINED cluster zero-plane span | 5.69 m | **0.64 m** |
  | binds refused for ground | 14 | **22** |
  | carried bodies divided by ATOM | 0 | **473** |
  | footed bodies anchored ON their pad (§16d (6)) | 0 | **61** |
  | §15 carried body floating over its carrier | 0 | **0** (bar 0) |
  | §16d written geometry outside its own box | — | **0** (bar 0) |
  | §16c torn seams outside line/arc pieces | 0 | **1**, step **+0.16 m**, `paredes_9_charlotte` b1↔b6, ONE shared vertex — under the 0.3 m census tolerance and under `visual_m`; NAMED, bar missed |
  | files | 473 | **477** |
  | DSF round trip / defs read back | — | **OK, 477/477** |
  | plan stage (dry, 3 runs) | 8.65 s | **8.3–8.5 s** |

  The `001_ALB` roof bodies the owner's read names are now cut per atom and each
  rides the wall body IT stands over (`b5` → `006_ALB__b0` 219.56 vs 219.94 ground,
  `b6` → `008_ALB__b1` 221.39 vs pad `building59` 221.38–221.41, `b11` →
  `004_ALB__b0` 217.51 vs pad 217.59, `b29` → `004_ALB__b25` 216.93 vs pad
  216.93–216.96) where before they were ONE carried body per resource at one zero
  (217.51 under 223.75 m of ground, 208.81 under 221.89).  §15's own carried bar —
  `zero − zero_beneath`, which IS "within 0.5 m of the wall beneath" — is **0 on
  both arms**.

* **THE TERMINAL, REPORTED NOT CLOSED.**  Over `building80` (1.19 m of relief,
  865-node ring) the ON-PAD set's zero spread is **1.03 m** on both arms — the pad's
  own relief, as §16d (6) predicts.  The count of bodies whose anchor lands OFF the
  pad moves only 71 → 65 (footed 26 → 24) in this frame, NOT 133 → 0: the 133 was
  read on the app's 1.0.324 WRITTEN frame, and the residue here is bodies whose
  ground contacts are MOSTLY off the pad (the rule's own majority test declines
  them) plus carried bodies, which take their carrier's anchor by §15 and not their
  own.  Named, not closed.

* **A DEFECT §16d (4) EXPOSED AND FIXED.**  A target group holding BOTH a cut piece
  (its own `tris`) and a raw the cut never touched (its parts' whole components) was
  read for its `tris` alone, so the rest of the group's triangles were claimed by no
  body and `obj8_split` handed them to the nearest one: measured at KCLT, 9
  placements left 990–3,280 triangles unclaimed and `001_ALB__b32`'s file reached
  207 m outside its own box.  The audit (every placement's solid triangles against
  the union of its bodies' `tris` and `cut_components`) reads **0 of 103** after.

* **THE COST — OVER BUDGET, AND NAMED.**  Plan stage, dry, this machine: LEMD
  13.6 (main) → 17.8 (§16d (1)–(3)) → **25.0 / 28.6 / 46.0 s** over three runs;
  OTHH ≈83 → 86.1 → **136.5 s**; KCLT 8.65 → **8.3–8.5 s**.  The LEMD run-to-run
  swing is the standing ±25 % and worse; the OTHH figure is one run.  §16d (4) asks
  a carrier search PER ATOM, and OTHH's clutter members publish thousands of them.
  Three narrowings are already in: a body narrower than `coarsen_reach_m` is not
  divided (§16a (1) already cuts those against the carriers the search returns),
  `CARRIED_ATOMS_MAX` 64 bounds a body's pieces, each piece carries only ITS OWN
  parts (so §15's contact fallback reads its own neighbours, not the whole body's),
  and that fallback now counts by set intersection instead of scanning the unit's
  neighbour list once per candidate.  **This takes an airport that was already over
  the 60 s per-airport budget further over it: it needs the owner's approval and a
  Fable-5 whole-pipeline optimisation review before it ships** (`Ortho4XP/CLAUDE.md`
  HARD LAW).  No further reduction was attempted in this lane.

* **THE LEMD SITES HELD** on the same 1.0.325 frame, written arm: the four shadow
  plates still −5.00 on their own ground; `Cargo-TEJ1` on `NEWCO__b9` at 604.95;
  §16d outside-box 0; seams 0; §15 carried float 0; round trip OK 2,435/2,435;
  every named site's base range identical to §16d (1)–(3)'s except
  `Terminal4_green-TEJ1` (spread 4.01 → **1.28**) and `T2NBG` (4.44 → **4.28**).
  §16b's carried-piece own-ground count rises again with the population it reads
  (LEMD 151 → 154, KCLT 41 → 41), already over its bar 0 on every arm.

* **SUITE**: **1,237 passed, 1 skipped**.  Twins:
  `test_16d_4_each_atom_of_a_carried_body_finds_its_own_carrier`,
  `test_16d_5_the_ground_bound_holds_inside_one_member_too`,
  `test_16d_6_a_body_anchors_on_the_pad_it_stands_on`.  Four existing twins were
  re-read against the new law and are marked with the ruling that changed them: the
  two §16a (1) roof twins now assert the OUTCOME and the atom count, §14 (1)'s
  footless twin reads two atoms as two own-ground bodies, and 12ap's bind twin
  asserts the refusal INSIDE one member.

* **NOT DONE.** The KCLT z = 0 crater in apron face 661 (`dsf:pol31`) is lane
  `v2zerocrater`'s and no bar here excludes or names its bodies — the terminal
  figures above are quoted whole.  The glazing carrier is not separately attributed.
  No airport was built.


## §16e THE DECK TOP AND THE CREST PLATE ARE DATUMS (owner RULINGS 2026-09-13k; Fable 2026-09-13n) — lane `v2othhdatums`

Owner: "With single layer bridges over water we should be seating the top deck to
align with the ground and let the feet land where they may. The tunnel walls are now
seating above ground, where before, and as they should, be creating the tunnel ramp
walls, with their tops flush with terrain." Scout `v2othh1o` on OTHH 1.0.326: no bridge
is torn (1 seam airport-wide, not a bridge); the bridges come apart because (a) half
of a bridge stands over the canal (water is a datum at 0.00) and half on land (3.96),
so pieces anchored at their own feet sit 2.8 m apart (Bridge_01: 12 bodies at 1.946,
one at 4.763); (b) piers of one solid get per-pier zeros (`Bridge_02_CLUTTER_007`: six
piers, 3.2 m spread); (c) §16c (4)'s rest-on ranking inside a unit of four bridges
picks carriers on OTHER bridges 250 m away. The seat era had NOT seated these at all
(no seat: "anchor on water and no site datum") — rigid at authored y was what "not
coming apart" looked like; R12's `deck_top` lived in v1's post-mesh seat. The tunnel
walls: §14 (2)'s rim anchor sets `y_zero = 0` (its docstring assumes the floor plate
authored −depth and the parapet +2.99 — LEMD's pits, OTHH's 8 drainage basins with
`plate_y` < 0) — OTHH's nine `tunnels/*` walls carry `plate_y` **+5.00 / +9.55 / +10.00**
(the CREST plate), so their crests stand +5 … +10 m over the rim; `tunnel middle -
west` classifies as no basin and takes a low-side foot: +20 m. §5's MSL→AGL
conversion removed the author's sink (−3 … −8 m) that the seat used to correct.
`Member.deck_datum_z`, `deck_ends`, `plate_stations`, `plate_y` are stamped by the plan
and READ BY NOTHING in the placement path; `reseat_expect_m` (05n-4) is computed and
published with no executor. §8's byte-identity proof was taken at LEMD, where no
tunnel wall object is admitted — OTHH is the only corpus airport with them.

1. **THE CREST PLATE IS THE DATUM.** A body whose member carries `plate_y` anchors at a
   wall-band station (`plate_stations`) with `y_zero = plate_y`: the crest plate at
   the ground there. For `plate_y ≤ 0` (a floor-plate basin) this is byte-identical
   to §14 (2); for `plate_y > 0` (a crest-plate wall) it restores `DATUM_PLATE`. The
   rule keys on `plate_y`, never on the basin classification. `reseat_expect_m` is
   the residual the census prints.
2. **THE DECK TOP IS THE DATUM OF A SINGLE-LAYER SPAN OVER WATER.** A deck member
   whose ring stands over no graded face (`deck_datum_z` None) and whose components
   reach no ground within the ring anchors so that `zero = ground at its END LINES −
   deck_top_y` (R12's abutment reading; `deck_ends` derived for flag decks from the
   ring's ends on land); the feet land where they may. A flyover with land under its
   ring (`deck_datum_z` set, `deck_top_y` 8–10 m) is untouched.
3. **A BRIDGE IS ONE RIGID ASSEMBLY.** The bodies of one deck member (deck, piers,
   clutter of that `Bridge_NN` family) ride the deck's datum as one cluster — never
   per-pier zeros, never a carrier on another bridge: within a unit, a body of a deck
   family may rest only on its own family. The feet are reported, not seated.
4. **BARS (OTHH 1.0.326 frame, matched arms; no build)**: the nine walls' crests
   within 0.3 m of the corridor rim (today +5 … +20 m; `worst feet` 15.00/10.00 rows
   gone; the 8 drainage basins byte-identical); Bridge_01/04/05 deck tops at the land
   (3.96 ± 0.3; today 5.52 / 6.43 / 6.43), Bridge_02/06 unchanged; per-placement zero
   spread for every bridge ≤ 0.3 (`Bridge_02_CLUTTER_007` 3.2 → 0); cross-bridge
   carriers 0; §14 footless-at-datum 4 → ≤ 1; seams unchanged (1, not a bridge);
   the LEMD sites held; plan stage; suite. Instrument: `seat_feet_census.py
   --placement-plan --mesh` passes its bbox as (lat, lon) to a sampler that takes
   (lon, lat) — broken since the switch; fixed with a twin.

**MEASURED (lane `v2othhdatums`, 2026-09-13).** Implemented in
`airport/anchor_rule.py` (`Datum`, `datum_of`, `_datum_anchor`, `keep_off_row`,
`Anchor.datum`), `airport/rebake_plan.py` (`ring_ends` / `end_line_stations`,
stamped into the new `Member.deck_end_stations`), `model/rebake.py` +
`model/placement.py` (the two published fields), `airport/placement_body.py`
(the two `anchor_for` call sites pass `datum=`), `airport/placement_carrier.py`
(`is_elevated`), `airport/placement_plan.py` (the keep test), and
`auto_patch/engine_v2.py` (`surface.water`). Matched arms on the app's 1.0.326
OTHH frame (`o4_v2_rebake_OTHH.json` + `OTHH.graded.json` + the built
`Data+25+051.mesh`) replayed through `v2_rebake_replay.py plan --sampler mesh`,
and the LEMD 1.0.325 frame the same way.

* **WHY THE MESH AND NOT THE GRADED SAMPLER.** `obj8_split_report`'s graded
  sampler reads the canal as OFF-SHEET, and the whole of §16e (2) turns on
  water being a DATUM AT 0.00 — which only the mesh states. `v2_rebake_replay
  plan --sampler mesh` is also the sampler the APP calls (12g) and the entry the
  plan-stage time is read on, so one instrument gives both. No `--mesh` option
  was added to `obj8_split_report`: a second sampler in a second entry is the
  census-wrapper defect.
* **§16e (1), THE NINE WALLS (bar: crest within 0.3 m of the corridor rim).**
  Before / after, crest − ground at the wall band: `tunnel middle - west`
  **+19.54 → 0.00**, `tunnel1` (two placements) **+10.78 / +9.13 → +0.02 /
  +0.21**, `tunnel south west 2` **+10.30 → 0.00**, `tunnel_sw` **+5.29 →
  0.00**, `tunnel west 1` **+5.01 → 0.00**, `tunnel west 3` **+4.47 → 0.00**,
  `tunnel west 2` **+3.98 → +0.02**, `tunnel middle - east` **+6.02 → 0.00**.
  **Walls over 0.3 m from the band: 9 → 0.** Four of the nine were KEPT on
  their authored row before (the crest then stands `plate_y` over the ground by
  construction) and are WRITTEN now: the keep test asked whether the row and
  the anchor read the same SURFACE, which for a datum body says nothing
  (`anchor_rule.keep_off_row`).
* **The 8 drainage basins (`plate_y` ≤ 0) are BYTE-IDENTICAL** — every anchor
  point, `y_zero`, surface and reason unchanged, all still `basin rim (...)` at
  zero 3.959/3.960. **LEMD IS BYTE-IDENTICAL WHOLE**: 2,109 body rows and 4
  keeps, ZERO changed, including the T4S pit and every named site
  (green-TEJ3 20 rows, T4 47, HANG3 2, LEMD47 1, TABOX 2, Bridge4 2 — all 0).
* **§16e (2), THE DECK TOP.** `Bridge_01`'s deck takes the datum: deck top
  **5.52 → 3.23 m** against land at 3.96 — the bar (3.96 ± 0.3) is **MISSED by
  0.43 m**, and the mechanism is measured, not guessed: its end lines stand on
  the CANAL BANK, which the mesh reads 2.52 (start end median) and 3.60 (far
  end) with one station on water; 3.96 is the graded road further landward.
  R12's landward walk is not armed here — it walks on too few LAND samples and
  this end line has eleven. Reported, not iterated (materiality/attempt cap).
* **NOT DONE — `Bridge_04` / `Bridge_05` deck tops (6.43 / 6.43, bar 3.96).**
  Their deck members carry NO PART AT ALL in the plan (`parts 0`: the partition
  found no genuine solid in them), so the placement path forms no body for them
  and there is nothing to anchor; both stay KEPT on their row. Giving a
  partless datum member a body is a BODY-FORMATION change in
  `placement_body._raw_bodies` (every downstream reader indexes the body's
  parts) and belongs with §16 (1)'s population rule — reported for ruling.
* **NOT DONE — §16e (3), and the two attempts are the attribution.** The rule
  needs "the Bridge_NN family", and the pack states no such thing: OTHH's
  unit:6 puts Bridge_02, Bridge_03 and Bridge_06 — three bridges 250 m apart —
  on ONE row at ONE AGL, so `deck_signature.family_key` (the anchor spelling)
  calls all thirty members one family, and at LEMD a shared-datum row would
  call 171 resources one. The lane tried the DECK'S RING as the family (a body
  standing inside `deck_ring` is that bridge's: the placement bound rigid, its
  cuts exempt, and the rest-on candidate set — `placement_carrier.carriers_for`,
  the `ranked` list built under `if box is not None` — cut to its own family).
  Read on the member's LOWEST part the cross-bridge carries went **2 → 3**;
  read on ALL its parts (attempt 2) **2 → 5**, and Bridge_02's per-placement
  spreads went the wrong way too. Both attempts moved the section's own bar
  backwards and the code is DELETED, not kept: the ring does not partition the
  clutter (OTHH's `Bridge_02_CLUTTER_000` stands inside Bridge_06's ring) and a
  family-less body is not filtered at all. What §16e (3) needs ruled is what
  names a bridge when the row does not and the ring does not either.
  `Bridge_02_CLUTTER_007`'s six piers therefore still span **4.97 m**, the
  per-placement spreads are unchanged, and cross-bridge carriers stay **2**.
* **The rest of OTHH** (matched arms, mesh census): feet histogram IDENTICAL
  (437 / 164 / 44 / 3; rows with a foot > 0.3 m 211, > 3 m 3); files 1,334 →
  **1,338** (the four written walls); §13 `elevated bodies as own files` **0**
  with the 10 datum bodies counted apart; §14 `footless at datum` **3 → 3**
  (§16e (4) asked 4 → ≤ 1; on the MESH frame the baseline is 3, and the datum
  law does not touch that class — the graded frame's 4 is a sampler
  difference); §14 basin-RING spread 0.00 → **0.20 m** (bar 0.3: the walls now
  anchor on a band station rather than on the rim ring, and the bar reads them
  there); §15 stands-over float 72 → 74 with CARRIED **7 → 7**; §16b carried
  float 118 → **117**, wide 170 → **170**; cockpit CRITICAL visual 281 → 289.
  Torn seams were not re-read (the written-pack census; no pack was written).
* **Plan stage** (`--runs 3`, mesh sampler, foreground): **72.23 → 79.64 s**
  mean (min 70.71 → 74.45). The ≤ 60 s bar is MISSED ON BOTH ARMS — it was
  already missed on main — and the +7.4 s is the datum's own stations plus the
  four newly-written walls; `surface` calls 568,468 → 569,216 (+748, 0.13 %),
  so the wall time is not the datum reading and the two arms are within the
  ±25 % single-run swing the law names. Reported, not optimised.
* **THE INSTRUMENT (§16e (4)), fixed and twinned.** `seat_feet_census.py
  --placement-plan --mesh` passed `(min lat, min lon, max lat, max lon)` to a
  sampler taking `(min_lon, min_lat, max_lon, max_lat)`: at OTHH it raised
  `no mesh triangles inside (25.24, 51.59, 25.28, 51.62) — wrong tile?` and the
  mode had never run. `plan_bounds()` is the one place the two orders meet.
* **THE REPLAY NOW ARMS THE SHARED-REPO GUARD** (`v2_rebake_replay.py`, the
  same `harness/shared_repo_guard` implementation): `plan` calls
  `ensure_dsf_text_path`, which generates a DSF dump into a mod cache the lane
  worktree MOUNTS at the shared repo. Every run of this lane printed
  `[guard] shared repo UNCHANGED`.
* **Suite**: `tests/auto_patch_v2 tests/test_harness.py
  tests/test_role_edge_census.py tests/test_mesh_sampler*.py
  tests/test_post_mesh.py tests/test_object_rebake.py` — **1,237 passed, 1
  skipped**, twice. Six new twins in `tests/auto_patch_v2/test_v2objsplit.py`.

### §16e (3) AMENDED, (5)–(6) ADDED (Fable 2026-09-13; RULINGS 2026-09-13v) — lane `v2bridgecontact`

The lane's two attempts are the attribution: the ROW does not name a bridge
(OTHH unit:6 puts three bridges 250 m apart on one row at one AGL; LEMD's
shared-datum row would call 171 resources one family) and the RING does not
either (it is a bbox; `Bridge_02_CLUTTER_000` stands inside Bridge_06's ring).

3. **A BRIDGE IS NAMED BY CONTACT WITH THE DECK'S OWN MODEL FOOTPRINT.** The
   deck member's mesh projected to plan is the deck's FOOTPRINT POLYGON (the
   ring is its bbox and is too coarse where decks overlap in plan). A pier or
   clutter body BELONGS to the deck whose footprint polygon contains its plan
   centroid, or lies within 0.5 m of it; where two decks' footprints both
   contain it, the deck whose underside is nearest ABOVE the body's top wins
   (absolute vertical distance — §16c (4)). A body no deck footprint contains
   has NO bridge family: it takes the ordinary §16c rest-on ground, is never
   filtered and never carried by a deck. `family_key` is untouched for every
   other class; the bridge family is a derived relation computed once per
   plan and published per body (`bridge_of`). The bodies of one bridge ride
   the deck's datum as ONE rigid cluster (per-placement zero spread ≤ 0.3 m);
   within that cluster a body may rest only on its own deck or its own piers.
5. **A PARTLESS DECK MEMBER IS A BODY.** A deck member whose partition found no
   genuine solid (`parts 0`: Bridge_04, Bridge_05) is admitted in
   `placement_body._raw_bodies` as one body whose footprint is the model's
   declared bounds and whose deck top is its plate — the §16 (1) population
   class, not a skip. It anchors under (2) like any other deck.
6. **THE DECK'S END-LINE DATUM IS THE GRADED FACE THE DECK CONNECTS TO, NOT
   THE BANK UNDER THE END LINE.** Bridge_01's end lines stand on the canal
   bank (mesh 2.52 / 3.60) and the deck seated to 3.23, 0.73 m below the road
   at 3.96 that drives onto it — a step at the abutment an aircraft or vehicle
   would feel. The datum walks LANDWARD from the end line (R12's walk, armed
   regardless of sample count) until it meets a graded pavement/road face or
   the design surface's graded ground; bank and water samples are excluded.
   The owner's rule ("seat the top deck to align with the ground and let the
   feet land where they may") is judged there: |deck top − datum| ≤ 0.5 m
   (§31 visual) at EACH abutment; feet unconstrained and reported.

BARS (OTHH 1.0.326 frame, `v2_rebake_replay.py plan --sampler mesh`, matched
arms): Bridge_01/04/05 deck tops within 0.5 m of the graded road at each
abutment (today 3.23 / 6.43 / 6.43 vs 3.96); `Bridge_02_CLUTTER_007` pier
spread 4.97 → ≤ 0.3; per-placement zero spread ≤ 0.3 for every bridge;
cross-bridge carriers 2 → 0; `bridge_of` published for all 30 members;
walls (§16e (1)) and the 8 drainage basins byte-identical; LEMD 1.0.325
byte-identical; plan stage not worse than 80 s (`--runs 3`); suite twice.

**MEASURED — §16e (3)(5)(6) (lane `v2bridgecontact`, 2026-09-13).** Arms
on the app's 1.0.326 OTHH frame (`o4_v2_rebake_OTHH.json` +
`OTHH.graded.json` + the built `Data+25+051.mesh`) and the 1.0.325 LEMD
frame, replayed through `v2_rebake_replay.py plan --sampler mesh` and
censused with `seat_feet_census.py --placement-plan --mesh`. Implemented
in `airport/anchor_rule.py` (`Datum.ends` / `step_m` / `walk_max_m` /
`level_tol_m`, `_walked_stations`, `_line_reading`),
`airport/placement_body.py` (`_declared_parts` / `_declared_box` and the
§16e (5) admission), the new `airport/bridge_family.py` (the whole
relation, its census and its bars), `model/placement.py` +
`airport/placement_record.py` (`Body.bridge_of`, `Staged.bridge`),
`airport/placement_plan.py` (the once-per-plan footprint pass over
shared cutters), `airport/placement_write.py` + `auto_patch/engine_v2.py`
+ `tools/v2_rebake_replay.py` (the two `[bridge]` keys), and
`tools/seat_feet_census.py` (the block). Two modules were MOVED WHOLE
for the 1,000-line law, no line changed and both re-exported from
`placement_plan`: `airport/placement_read.py` (`read_plan`,
`pads_rims_from_graded*`) and `airport/placement_targets.py`
(`_footless_targets`, `_carrier_pieces`).

| bar | before | after |
| --- | --- | --- |
| `Bridge_01` deck top vs the graded road 3.96 | 3.23 (0.73 off) | **3.96 (0.00) PASS** |
| `Bridge_04` deck top | KEPT on its row, 6.43 | **3.96 (0.00) PASS** |
| `Bridge_05` deck top | KEPT on its row, 6.43 | **3.96 (0.00) PASS** |
| `Bridge_02_CLUTTER_007` pier spread | 4.97 m | 4.97 m — **MISSED** |
| per-placement zero spread > 0.3 m | 12 of 14 | 12 of 14 — **MISSED** |
| cross-bridge carriers (resource-name axis) | 2 | 2 — **MISSED** |
| `bridge_of` published | – | 57 bodies / 34 of 39 split bridge placements |
| §16e (1) nine walls + 8 drainage basins | – | **BYTE-IDENTICAL** |
| LEMD 1.0.325 whole | – | **BYTE-IDENTICAL** (322 splits, 2,122 bodies, 0 changed) |
| plan stage (`--runs 3`, mesh, foreground) | 79.64 s mean (13v) | **70.87 s mean, min 67.92** |
| suite | – | 1,264 passed, 1 skipped, twice |

(The three §16e (3) rows read MISSED against the bars as they stood when
this lane ran; RULINGS 2026-09-13ae WITHDREW (3) on this measurement and
made all three CENSUS LINES rather than bars — the section below.)

* **§16e (6), THE LANDWARD WALK, AND THE ONE LIMB THAT IS NOT THE
  SPEC'S.** The spec stops the walk at "a graded pavement/road face or
  the design surface's graded ground". THE FIRST LIMB IS UNREADABLE AT
  THIS SITE AND THAT IS MEASURED, NOT ASSUMED: `graded_roles_from_doc`
  builds 894 faces from `OTHH.graded.json` and `roles_many` is EMPTY at
  every station of every 5 m offset out to 140 m landward of BOTH of
  `Bridge_01`'s end lines — there is no graded face at the abutments at
  all, which is the same fact `deck_datum_z = None` states. The second
  limb is implemented as the reading the mesh does give: the walk stops
  at the first offset where no station is on water or off-sheet AND the
  line is LEVEL within `[placement] split_tol_m`. The bank is exactly
  the stretch where it is not — `end0` spans 1.34 m at the end line,
  1.76 at 5 m, 0.44 at 10 m and 0.00 (all 3.96) from 15 m; `end1` spans
  1.41 / 0.28 / 0.24 / 0.12 and 0.00 from 20 m; and 3.96 is the level
  the other three bridges carry as their own `deck_datum_z`. The
  role limb is kept and asked first wherever a sampler carries roles.
  **INTENT QUESTION for the spec's author:** is "the design surface's
  graded ground" the level line the walk finds, or is a deck whose
  abutments touch no graded face outside §16e (6) altogether?
* **§16e (5) IS THE WHOLE OF Bridge_04/05.** Their deck members carry
  ONE solid component each (54 and 18 `ATTR_hard_deck` triangles, y
  4.51–4.65 and 4.55–4.61 — a 0.14 m plate the thickness gate refused),
  so `_declared_parts` reads the components the cutter already has open
  and the member becomes one body with negative pids the contact graph
  can never match. Both end lines already read 3.96 with zero spread, so
  the walk does not move them: the datum alone puts them on the road.
  Files 1,338 → 1,340, placements kept 376 → 374.
* **§16e (3) IS DERIVED, PUBLISHED AND CENSUSED — AND WIRED TO NOTHING.**
  The relation (the deck's mesh projected to plan, exact
  point-in-triangle plus the 0.5 m reach, ties to the underside nearest
  the body's top) is in `bridge_family.py` and published as
  `Body.bridge_of`. Its other two halves — one bridge is one rigid
  cluster, and a body rests only on its own deck or piers — were built
  on it and BOTH ARMS MOVED THE SECTION'S OWN BARS BACKWARDS, so the
  code is DELETED under the attempt cap:
  * arm 1 (family cluster + pool cut to the family): cross-bridge
    carriers 2 → **9**, per-placement spreads over 0.3 m 12 of 14 → **17
    of 19**, `Bridge_02_CLUTTER_007` 4.97 → **6.61 m**.
  * arm 2 (the family actually UNIONED — §16c (7) deliberately never
    unions two footed bodies of one member, so arm 1's cluster never
    formed at all — and only the DECKS cut out of a family-LESS body's
    pool, which is §16e (3)'s own "never filtered"): cross 2 → **9**,
    spreads 12 of 16, worst 4.97 → **9.66 m**.
  THE MECHANISM (the distance from every bridge body's plan centroid to
  the nearest deck footprint): (a) THE FAMILY IS PARTIAL — 51 to 71 of
  ~80–102 bridge bodies fall inside a footprint or within 0.5 m and the
  rest stand 0.6 … 45 m outside it, because OTHH's bridge clutter runs
  BESIDE the deck plate (parapets, kerbs, lamp masts); a partly-bound
  bridge is worse than an unbound one, its named half on one zero and
  its unnamed half on its own ground, and the per-placement bar reads
  across both. (b) THE DECKS OVERLAP EACH OTHER — Bridge_02/03/06 are an
  INTERCHANGE: `Bridge_03_CLUTTER_000__b1` stands INSIDE Bridge_02's
  footprint (0.1 m), `Bridge_02_CLUTTER_001__b3` and `_002__b0` inside
  Bridge_06's. By CONTACT those bodies are that deck's, which is the
  law; the bar is stated over the pack's `Bridge_NN` SPELLING, which the
  law deliberately does not read. 66 of 71 published values agreed with
  the name and the five that did not are the interchange.
  **TWO INTENT QUESTIONS:** is a body BESIDE a deck plate that bridge's
  (the 0.5 m reach is the spec's own number and this lane did not change
  it), and on which axis is the cross-bridge bar read when contact and
  name disagree?
* **THE BYTE-IDENTITY WAS NEARLY LOST TO A MEMO, AND THE FIX IS THE
  RULE.** `anchor_rule._m_per_deg` memoises per 1e-4 deg of latitude and
  keeps whichever exact latitude touched a key FIRST. Reading it from a
  NEW call site before the unit loop handed every later caller in the
  same 11 m band a value it did not compute: 94 `authored_offset`s moved
  by ~8 microns and **101 OTHH placements this law does not touch** —
  four drainage/dewatering resources among them — stopped being
  byte-identical while every anchor point, zero and reason was
  unchanged. The footprint pass, `_declared_parts` and the landward walk
  all read the UNMEMOISED `rebake_plan._mpd` instead (`bridge_family._latlon`
  is `placement_cut.authored_latlon`'s own two lines over it), and the
  changed set went 101 → 59 → 58 → **1** (`Bridge_01`'s deck, which is
  §16e (6)) plus the two decks §16e (5) adds.
* **THE RESIDUE OTHH CARRIES.** §15 stands-over float 74 → 78 with
  CARRIED **7 → 9** and §16b wide 170 → 172: `Bridge_04`'s two clutter
  bodies now ride the deck body §16e (5) created (+2.47 m each), which
  did not exist to ride before. §14 footless-at-datum 3 → 3, §13
  elevated-own-files 0 → 0, §16b carried-own-ground 117 → 117.
* **A CONTROL TRAP, RECORDED — AND ITS CAUSE CORRECTED AT THE MERGE.**
  `v2_rebake_replay plan --src` pointed at ANOTHER LIVE CHECKOUT is not a
  control: `/Users/noah/XPTerrainBuilder/Ortho4XP/src` gave LEMD **3,646**
  bodies where a `git archive` of the sha this lane read on that tree gave
  **2,122**. The reason is not `--src` and not the same sha — it is that a
  LIVE CHECKOUT MOVES: the orchestrator merged §16d (`v2unboxed`, 748be853)
  into main between the `git log` that read the sha and the replay that
  used the tree, and 3,646 is §16d's own LEMD number, which BOTH arms give
  once this lane merges main `8ce4792a`. Every base arm here is cut with
  `git archive <sha> src | tar -x -C <scratch>`, which is the only spelling
  another session cannot change underneath a measurement.

### §16e (3) WITHDRAWN; (6) AMENDED (Fable 2026-09-13; RULINGS 2026-09-13ae)

Lane `v2bridgecontact` refuted (3) a third way (its MEASURED block above):
OTHH's bridge clutter runs BESIDE the deck plate (only 51–71 of ~80–102
bridge bodies inside a deck footprint or within 0.5 m; the rest 0.6 … 45 m
outside) and Bridge_02/03/06 are an interchange whose decks overlap in plan.
A footprint family is partial, and a partly-bound bridge is worse than an
unbound one (cross-bridge carriers 2 → 9 on both arms).

3. **WITHDRAWN.** The deck is the only datum body of a bridge. Its separate
   clutter and piers rest on their own ground under §16c and are REPORTED
   per body: `Body.bridge_of` (the deck whose model footprint contains the
   body, or ""), the per-placement zero spread and the cross-bridge carrier
   count are census lines, not bars. No bind and no carrier filter reads
   `bridge_of`. The owner's read of OTHH in app 1.0.327 decides whether any
   further bridge law is wanted.
6. **AMENDED — the walk stops at the first dry, level line.** The first
   limb (a graded pavement/road face) is unreadable where the mesh carries
   no roles (no graded face within 140 m landward of either Bridge_01
   abutment). The end-line datum walks landward from the end line in 5 m
   steps and stops at the first line that is DRY (no water sample) and
   LEVEL within `split_tol_m` across its span — that line is the design
   surface's graded ground there; the bank is exactly where the line is not
   level. Measured: Bridge_01 / 04 / 05 deck tops 3.96 / 3.96 / 3.96 against
   the land at 3.96.

**RE-MEASURED ON MERGED MAIN `8ce4792a` (lane `v2bridgecontact`).** The
lane merged main — §16d's `geom_boxes` parameter and
`PlacementState.geom_boxes` run through the same body constructors as
§16e (3)'s `bridge`, and both survive in every signature and call site —
and re-read the two bars against a base arm cut with
`git archive 8ce4792a src`:

* **Bridge_01 / 04 / 05 deck tops 3.96 / 3.96 / 3.96**, each 0.00 m from
  the land at 3.96 (§31 visual 0.5 m, PASS).
* **LEMD 1.0.325 BYTE-IDENTICAL** to main: 322 splits, 3,646 bodies (the
  §16d number, on both arms), ZERO changed rows.
* OTHH: **5** changed placements and 2 new, every one of them
  `Bridge_01` / `Bridge_04` / `Bridge_05` — the two datum decks §16e (5)
  admits and the sibling members that now find one. Every non-bridge
  placement in the airport is byte-identical.
* Suite `tests/auto_patch_v2 tests/test_harness.py
  tests/test_object_rebake.py`: **1,227 passed, 1 skipped, twice**
  (124 twins in `test_v2objsplit.py` — main's 118 and this lane's 6).
* §16e (3) stays WITHDRAWN per RULINGS 2026-09-13ae: `bridge_of` is
  published and censused, and nothing binds or filters on it.

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

### §16f (8) A RAMP STAYS IN ITS FAMILY (Fable 2026-09-13; RULINGS 2026-09-13bm item 3) — lane `v2spjc`

SPJC's departures viaduct (`SPJC_LIMANUEVA_xp11_007__b0`) was expelled from
the terminal family by the `bind_ground_m` test reading its own authored
descent as a ground disagreement, then seated by the low-side foot at its
deepest authored point: +7.81 m above the terminal.

8. The family ground test reads a member's disagreement NET OF ITS AUTHORED
   RELIEF — the HIGH end's `surface − y` (where it meets the building)
   against the family plane, not the median over all contacts. A member
   whose geometry descends is not expelled for descending; its low end may
   sink below grade to the DEM (owner: "stay locked to the building and sink
   into the ground so its ramp meets DEM").

BAR: `…_007__b0` on `building6`'s plane (19.56) with its low end ≤ DEM; §15
float 7.85 → ≤ 0.5 m; `ground_off` 7.05 → ≤ 0.5; KCLT / LEMD / OTHH families
re-read (named).

### §16e (3) REINSTATED BY NAME — A BRIDGE IS ITS PACK'S NAME FAMILY (owner RULINGS 2026-09-13bn; Fable 2026-09-13) — lane `v2bridgename`

Owner (OTHH 1.0.327): "the actual deck is at the right level, but other
components are still too high so the bridge is still coming apart into
different components instead of staying a single unit." Row, ring and
footprint families were each refuted (13v, 13ae); the pack's NAMING is what
its author meant.

3. **THE NAME FAMILY.** A bridge's members are every placement whose
   resource file name shares the deck's stem — the text before `_CLUTTER`,
   `_LOD`, or a trailing numbered suffix (`Bridge_01`, `Bridge_02`, …), read
   off the pack's `OBJECT_DEF` paths by ONE derivation
   (`bridge_family.name_stem`). The deck member (§16e (2)'s datum body) is
   the family's datum; every other member — piers, clutter, railings —
   takes the deck's zero as ONE rigid zero: no per-member cut, no carrier
   search, no ground test (the feet land where they may — on, above or
   below the ground the deck spans). A stem with no deck member falls back
   to §16c. `bridge_of` publishes the stem; the census prints each family's
   spread and members.

BARS (OTHH frame, `v2_rebake_replay plan --sampler mesh`, matched arms):
per-family zero spread 0.00 for every `Bridge_NN` (today `Bridge_02_CLUTTER_007`
4.97 m); deck tops 3.96 / 3.96 / 3.96 held; cross-bridge carriers 0 on the
name axis; LEMD and KCLT byte-identical (LEMD's `Bridge4` is a line-station
body — name it); ONE OTHH build; suite twice.

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

### §11b (7) A FOOT ON A STRUCTURE CUT STATES NO GROUND ROW (Fable 2026-09-13; RULINGS 2026-09-13bs, owner OTHH read 13bn item 2) — lane `v2cutfeet`

OTHH's tunnel object `tunnel south west 2#b0` is re-seated to the ground
(3.962) and its §11b foot rows then demand that the ramp its own walls cut
stand at that ground every few metres: the ramp sags between the nails
(+3.31 m off its design line at the owner's point; 12 of 21 monotone rows
violated; all 13 of OTHH's over-cap `tunnel_ramp` rows on this one ramp).
Dropping the foot rows solves the same capture as a +3.6 % descent, optimal,
hard set settled.

7. A placement foot whose surface sample lands on a structure-cut face —
   `tunnel_ramp`, `tunnel_trench`, `wall_corridor_ramp`, `door_ramp`,
   `garage_ramp`, `retaining_wall`, a basin floor — takes a `cut` verdict at
   `foot_rows._verdict` (beside `basin` / `pavement` / `padded` / `bare`),
   counted and reported, and emits NO `Linear`. The cut surface is §33 /
   §34's; the object RIDES it (§16a: cut where its carrier is cut; §16c (3):
   a foot over a structure cut is not a ground foot). An object at a trench
   edge keeps its crest plate (§16e (1)) and rides the cut with its feet.

BARS (the registered OTHH capture): `tunnel_ramp` off-design max 5.09 →
≤ 0.05 m; in-scope `within_shape tunnel_ramp` 13 → 0; `wall_corridor_ramp`
off-DEM 1.39 → ≤ 0.15; design solve OPTIMAL, hard set settled; `cut`
verdicts printed (~574 pairs); LEMD and KCLT byte-identical; ONE OTHH build;
suite twice. Owed: a `Flat` row at every station of a curving ramp (the
kerbs separate past `_STATION_CLUSTER_M` and the monotone chain zig-zags).

MEASURED (lane `v2cutfeet`, branch `claude/v2cutfeet`; a MATCHED replay
pair on the registered OTHH capture `v2othh327/OTHH.pkl`, both arms
resumed at `constraints` under `a0f65165` — the base arm cut with
`git archive a0f65165`, never a live checkout).

THE ROLE SET IS ONE LIST, not the prose tuple above: `_FaceIndex` reads
`law.tables.is_structure_role` (`precedence.toml` `structure = true`),
which at OTHH resolves to `tunnel_ramp`, `tunnel_trench` (the role a
basin floor's face carries — `verify/structures._basin_floors` reads
`tunnel_trench` + ref `basin_floor:`), `wall_corridor_ramp`, `door_ramp`,
`garage_ramp`, `retaining_wall`, `bridge_trench`, `bridge_causeway`. The
last two are the register's, not the ruling's prose: a bridge cut states
its surface exactly as a tunnel's does, and taking the register whole is
what keeps a role added tomorrow covered the day it lands.

OTHH, base → cut arm: the owner's point 25.253869, 51.603365 (63
vertices within 60 m) z − DEM mean **0.42 → −0.04**, max **3.31 → 0.02**,
max step over a short edge 0.10 → 0.01; the site vertex v5266 z 3.54 →
0.23 against DEM 0.23. The ramp `tunnel-object:tunnel south west
2.obj@0` (face 697, 22 station groups) runs **−1.138 → 3.962 MONOTONE at
+3.52 … +3.88 % at every station**, z == its target to 3 dp (worst
|z − target| 0.017 m at the crest station), zero cross-fall — against 12
of 21 monotone rows violated and +3.31 m off the design line at base.
`off_dem_by_role`: `tunnel_ramp` **5.09 (99 of 361 over 0.5 m) → 1.16 (8
of 361)**, `wall_corridor_ramp` **1.39 (20/692) → 0.15 (0/692)**,
`retaining_wall` **1.42 (14/1705) → 0.09 (0/1705)**, `tunnel_trench`
13.64 either arm (§34's own floor, not a ground reading). The verify
census on the solved surface: **336 → 41 rows**, `within_shape` **281 →
3** — in-scope `tunnel_ramp` **19 → 0** and `wall_corridor_ramp` **257 →
0**, the 3 left `building|building`; `basin_floor_at_declaration` 10 → 0;
DEFECT families ALL ZERO both arms. THE SOLVE: `feasible`, 91 active-set
rounds, **SET NOT SETTLED (833 flips, worst 0.052 m)**, **HARD SET NOT
SETTLED, 2 of 78,238 violated (max 0.0255 m)**, LAG NOT SETTLED after 3
rounds (2 rows over 0.01 m, worst 0.0305 m) → **OPTIMAL, 37 rounds, SET
SETTLED, HARD SET SETTLED 0 of 78,238 (max 0.0130 m), LAG settled in 2
rounds (worst leader move 0.008 m)**; solver 6.63 → 2.76 s. THE COUNT:
foot rows **771 → 197 pairs — exactly the 574 pairs 13bs predicted** —
over `foot_rows.cut` **485 bodies** / `foot_rows.cut_feet` 10,216 feet
(the feet of those bodies; most carried no row before, being off-sheet).
`bare` 357 → 60.

LEMD AND KCLT ARE NOT BYTE-IDENTICAL — the premise is REFUTED, and the
count is the answer. KCLT (registered capture `scratchpad/cap/KCLT.pkl`,
base 70646dc8, both arms): `foot_rows.cut` **64 bodies**, fired pairs
**135 → 9**; `tunnel_ramp` off-DEM 6.71 (160/385) → 6.00 (100/385),
`retaining_wall` 0.26 → 0.18. KCLT's solve is `feasible` and NOT settled
in EITHER arm, and its hard set moves the wrong way by a hundredth (11 of
131,714 violated, max 0.0302 m → 19, max 0.0440 m; flips 351 → 922) —
REPORTED, not iterated on: no KCLT bar was set and the base is already
unsettled. LEMD: every registered LEMD capture PREDATES the `PlanarMap`
fields `road_ramp_z` / `road_route_frame` and is refused at replay on
`a0f65165` (`AttributeError` in `_dc.replace`), so the count was read
OFFLINE by running `foot_targets` over `v2settle/armA.solved.pkl` under
both source trees: `foot_rows.cut` **29 bodies**, fired pairs **608 →
591** (17 suppressed). LEMD's 7a remains `source osm` with zero foot
rows (13bs); the 29 are elsewhere.

THE OBJECT STAGE NEEDS NO CHANGE (static confirmation, §16 (2)): a
body's zero is compared with `ground_under_geometry` —
`placement_census.ground_at_box` over the DESIGN SURFACE, never the DEM —
so the tunnel object is seated on the solved cut the day the cut is
solved, and nothing in the object stage reads a `BodyVerdict`.

THE CLOSING BUILD: `OTHH_20260913T171324`, rc 0, 968.0 s, ways 1,097,
nodes 25,707, `body_sha 0ff85d1a7bff`, artifact ledger `86493fdab68b`;
`[guard] shared repo UNCHANGED` (16 lock-file churn operations, the
allowed class). Its design solve carries **HARD SET SETTLED, 0 of
155,709 violated**, `foot_rows` 394 (the same 197 pairs), SET NOT SETTLED
568 flips worst 0.015 m — a LARGER problem than the capture (23,286
unknowns against 19,238: the tile build carries OTBH and the rest of the
frame), and no matched base build exists in the artifact ledger at
`a0f65165`, so the build stands as the closing test, not as a bar arm.
Suite twice from `Ortho4XP/`: 1,265 passed, 1 skipped, both runs. Twin:
`tests/auto_patch_v2/test_v2cutfeet.py` (three readings — the cut
verdict, the register-not-a-literal role set, and the neighbour on bare
ground that still fires every foot).

STILL OWED, unchanged: the cross-kerb monotone chain
(`planar/structures.py:116, 375, 439`) — it cost no bar here, and the
ramp reads monotone at every station in the cut arm.

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
