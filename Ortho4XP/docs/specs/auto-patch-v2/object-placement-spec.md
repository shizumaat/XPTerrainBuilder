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
