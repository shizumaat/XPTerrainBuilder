# Pack tunnel decks and portals pin the cut and seat to the surface (#1331, #1343, #1298)

Lane `lpackcut`, 2026-10-26, base `origin/main` 77e3a13e4, then merged with
7d202d512 (batch Z, which carries lramp's #1393).  Rulings read: 2026-10-26d
(Q142 "b"), 19p, 19e (1)-(3), 22m, 22n (#1138 held), 23b, 08-21d (strip
keep-out).

Captures (registered in `tools/harness/frames.py`, lane `lpackcut`): KBUF,
EGGW, EGLL at 77e3a13e4 (`/private/tmp/claude-501/lpackcut/*.pkl`); lramp's
LGAVft / NZWN / LFPG were reused.

## Site numbers first

### LGAV (#1331), FlyTampa pack enabled through a read-only Custom Scenery mirror

| | owner's 1.0.428 build (engine 1.50.1874) | this branch (harness `lpackcut_lgav2`, ledger `4164eeedbede`) |
|---|---|---|
| drop point 37.943947839, 23.951564905 — patch surface | 73.73 (`tunnel_ramp` pit = Trench_02's authored floor) | 73.73 (the cut is kept, 26d) |
| span end 37.943555918, 23.951786711 | 79.93 | 79.93 |
| span end 37.944227182, 23.950643419 | 80.00 | 80.00 |
| pack deck over the drop point (`Trench_00` body b1, `bridge_taxi1`) | zero 66.47: it rode `Trench_06`'s channel shell as a carried body, 13.5 m under the taxiway (66.47-66.77) | zero 79.99: flush with the taxiway at its end lines 80.16 / 80.02 (deck top y 0.00 at the ends, 0.30 at the crown) |

The deck numbers are the object stage replayed offline
(`tools/v2_rebake_replay.py plan`) on the build's own rebake plan and
graded surface (`--sampler graded`; base = `--src` of main, branch = this
tree).  On the owner's production plan + mesh the same replay reads 66.47 ->
80.09.  Only two bodies move, both `Trench_00`: b1 above, and b0 over the
`Trench_01` cut, 77.40 -> 77.34 (flush with the taxiways there).  Nothing
else in the LGAV plan changes.

lramp's "about 2.2 m below" was the AUTHORED stack zero (DEM 77.71 at the
stack anchor 1.3 km away); the shipped seat was worse: the body was carried
by the channel shell.

### KBUF (#1343)

Heights are the patch's own nodes (`alt_abs`).  The portal objects are
placed at several anchors (I-4: never re-seated), so X-Plane drapes each
object's zero on the mesh at its anchor: the portal's floor is the ramp
floor there and its roof top is floor + roof y.

| site | production patch | this branch (`lpackcut_kbuf`) |
|---|---|---|
| 1: 42.943562651, -78.726619628 (`Road_Tunnel.obj` dsf:obj6856, bore -766 end 0) | uncut, 219.13: the portal stood on the graded strip, roof 6.6 m proud | round 2 (`lpackcut_kbuf3`, RULINGS 2026-10-26k): cut inside the runway strip; the mouth moved 10.4 m into the bore to the portal's anchor; ramp floor 212.43 at the mouth, 212.66 read at the anchor; roof 219.07-219.30 = the rim 219.07 |
| 2: 42.935047080, -78.724917302 (`KBUF_Terminal_Parking_Underpass.obj` dsf:obj590, bore -756 end 1) | uncut: service road 211.55 (the mouth was refused: "cannot stand clear of pavement dsf:pol161") | cut: ramp floor 206.28 at the portal; roof 6.09 -> 212.37 = the rim 212.37-212.69 |
| 3: 42.935452165, -78.725199037 (same object, dsf:obj589, bore -756 end 0) | floor 204.13 (bore law 7.5 m): roof 210.22, 1.4 m under the rim 211.63 | floor 205.54: roof 211.63 = the rim 211.63 |
| `Road_Tunnel.obj` dsf:obj6855 (bore -709 end 1) | floor 209.53: roof 216.17, 0.9 m under the rim 217.03 | floor 210.38: roof 217.02 = the rim 217.03 |
| `Road_Tunnel.obj` dsf:obj6857 (bore -766 end 1) | slid 3.5 m out, floor 210.77 | pinned at the portal, floor 212.94: roof 219.58 = the apron edge 219.59 |
| `Road_Tunnel.obj` dsf:obj6854, 42.945182, -78.724549 (bores -5328 / -5327) | both built, slid 31.5 / 66.5 m out; the portal stood over covered bore | round 2: `-5327@0` pinned and moved 7.8 m to the anchor, floor 212.36 (212.44 at the anchor), roof 219.08 vs rim 219.00; its ramp is clipped 12 m out at `small_roads:-5326`, and `-5328@0` is refused because its corridor overlaps `-5327@0` (the two carriageways meet one portal) |

Round 2 (RULINGS 2026-10-26k, Q155 "b"): a pack portal's cut may stand inside
the runway strip keep-out (`structure_mouth.strip_keepout`), and the strip
families exempt it from the RUNWAY strip only (`publication.portal_cuts`;
`verify` `wall_in_runway_strip` / `ramp_in_strip` and `tools/check_grade`'s
twins).  Verify rows in the strip at KBUF: `wall_in_runway_strip` 4 -> 0;
`ramp_in_strip` 4 -> 4, all four now in the TAXIWAY strip (`primary_parallel`)
at the -709@0 and -766@1 portals (two were runway rows in round 1); within
150 m of the two strip portals, 2 new `within_shape` rows on the clipped
`-5327@0` ramp (10.76 % / 10.46 % against the 10 % cap).  Verify defects:
none (`lpackcut_kbuf3`, ledger `a09bbd8cc744`).  A pinned mouth whose portal
anchor stands on the covered side of the mapped bore end moves into the bore
to the anchor (`structure_mouth.portal_mouth`): an unseated portal is drawn
on the mesh at its anchor.

Residual: the anchors sit 0.6-2 m from the mouth line.  The graded surface
read AT each anchor is 0.0-0.9 m above the mouth floor (obj590 +0.02,
obj589 +0.23, obj6855 +0.9, obj6857 +0.8), so the two `Road_Tunnel`
portals may stand up to ~0.9 m proud.  That is under the 1 m class but not
zero; flattening the floor under a portal's own footprint is the follow-up.

### EGGW / EGLL (#1298)

No change, by design: neither reading in this branch applies (the dry
structure A/B below is identical at both).  EGGW's refused candidates are
UK2000 buildings, and `eggw_cabins.obj` boxes both ends of bore -908
(read as a portal by the first draft of the rule, refused once the roof had
to stand over the bore end).  EGLL's tunnel objects are hard-deck covers
whose walls run to -5 m with no floor — the #1298 class, which needs a spec
and an owner ruling (below).  No EGGW or EGLL build was made: the branch
changes nothing there.

## The consumer census (RULINGS 2026-08-30l) — one ruled table

Every pass that reads pack tunnel / deck objects or the cuts they make.

| # | pass | reads | ruling for this change |
|---|---|---|---|
| 1 | `airport/object_cut.read_shells` | signature-B shell + flush cover → `ObjectCut` (floor = DEM at the anchor + floor y) | unchanged (26d: keep the pack's cut) |
| 2 | `airport/tunnel_objects.read_corridors` | wall objects, shells → `Corridor`; refusals | CHANGED: also reads the PORTALS (`portal_objects.read_portals`) over the bore ends no corridor took, on `TunnelObjectStats.portals` |
| 3 | `airport/portal_objects` (new) | roofed objects at mapped bore ends | NEW reader: no floor plate, no hard deck, walls on its zero, roof 4.2 m (`bridge.clearance_minimum_m`) .. 7.5 m (`tunnel.mouth_depth_m`), the roof over the end (`bore_end_tolerance_m`) |
| 4 | `airport/thin_plates` / `structure_approach.apply_plates` | thin-plate wall objects govern a mouth (§33 (2)) | unchanged; runs first, a pin is read at the mouth it leaves |
| 5 | `planar/structures.build_structures` | OSM mouths: #971 slide, bore-law depth, strip keep-out, ramp truncation | CHANGED: a pinned mouth is not slid and its floor is ground − roof top; a portal in the runway strip keep-out, or whose opening meets a taxiway, is unpinned and named (`StructureStats.portals_unpinned`) |
| 6 | `planar/structure_mouth.mouth_at_pavement` | the stops a mapped mouth slides out of | CHANGED: `pinned` arm — the stops the mouth's own end stands in are the portal's; a taxi face there is never dropped (clause 1) and the mouth slides as before |
| 7 | `planar/object_corridor`, `door_ramps`, `wall_corridor_ramps`, channels (§45), basins | object corridors, door wells, channels, basin claims | unchanged (portals are read only where no corridor took the object) |
| 8 | `constraints/structures`, `emit/graded`, `osm_adapter` | `Tunnel.mouth_z`, ramp faces | unchanged code; a pinned mouth flows through the same `Tunnel` record |
| 9 | `pipeline/publication.tunnel_mouth_depths` → `verify/structures.tunnel_mouth_canonical` | a non-bore-law mouth depth per tunnel | unchanged code: a pinned mouth publishes its depth there as a slid one does, so the canonical-mouth verify reads it |
| 10 | `pipeline/authored_seats.seat_records` | the object tunnels' seat decision | unchanged |
| 11 | `pipeline/rebake_inputs._rebake_inputs` | the planar facts the rebake plan reads | CHANGED: stamps each OBJECT cut's footprint ring on its placements' seat records (`cut_ring`, lat/lon) |
| 12 | `airport/rebake_screen`, `rebake_plan`, `model/rebake.RebakePlan.authored_seats` | carry the seat records | unchanged code: the ring rides the record dicts (absent in an older plan = old law) |
| 13 | `airport/placement_plan` — class A (`airside_deck_seat.airside_frame`), §49 `deck_seat`, group zero (22o/q) | the deck seat | CHANGED: after the group zero, a frame that is NOT class A runs `cut_deck_seat.seat_cut_decks`; class A frames are untouched |
| 14 | `airport/cut_deck_seat` (new) | a FLAG deck body whose slab hull stands ≥ `[deck] on_fraction` over a pack cut ring | NEW: flush with the carried surface (airside, else road; never a structure role) at its end lines read one step outside the edge |
| 15 | `airport/airside_deck_seat.airside_end_ground` | end-line ground of a deck ring | CHANGED, defaults identical: optional `carried` role test and `outside` reading |
| 16 | `airport/placement_write`, `authored_seat` (DSF writer) | kept / re-seated rows | unchanged: the shell `Trench_02` stays "authored (cut)" |
| 17 | census (`placement_census` carried-body bar) | `merged_into` bodies | a re-seated deck body is no longer carried (`merged_into` cleared), so the carried-own-ground bar does not read its 6 m over the trench floor as a float |
| 18 | `tools/harness` census / `check_grade` / `tunnel_portal_acceptance` | patch populations | unchanged code; see the A/B below for the populations that move |

## The rules

1. **A pack hard deck over the pack's own cut sits flush with what it
   carries** (26d).  Witness: the cut ring the planar map publishes; a body
   of a flag-deck member whose slab hull is at least `on_fraction` over it.
   Ends: the airside where the taxiway drives onto the deck (else a road),
   one step outside the edge — the trench under the edge is never read, and
   the cut's own `tunnel_trench` role (airside-registered) is never the
   carried surface.  Only the deck body moves (it is re-anchored at its own
   centre); the shell keeps its cut and its authored seat.
2. **A pack portal pins its mouth** (#971 "or object if one is provided").
   The mouth stays at the mapped portal; its floor is the ground less the
   portal's roof top.  Exceptions, both left to the bore law and named: a
   portal inside the runway strip keep-out (08-21d), and a portal whose
   opening stands in a taxiway face (clause 1).

## What else changes (dry A/B, base 77e3a13e4 vs this branch)

`planar.__main__.structure_records` on each capture under both trees:

| capture | change |
|---|---|
| KBUF | -756@0 floor 203.95 -> 205.36; -756@1 built (was refused by #971); -709@0 209.31 -> 210.17 (ramp 72 -> 60 m); -766@1 210.63 -> 211.29, not slid (ramp 96 -> 84 m) |
| LGAVft, NZWN, LFPG, EGGW, EGLL | none |

Object stage (`v2_rebake_replay plan`, base `--src` vs branch, cut rings
injected from the captures): LGAV moves exactly the two `Trench_00` bodies;
LFPG none (no object cut carries a deck).

Readings refused on the way (kept as twins): LFPG's `H*.obj` taxiway
bridges read as portals until hard decks were excluded (they are class A,
22n, and the trench under them is #1138, held); EGLL's hard-deck covers
read as 0.8-1.0 m "portals" until the clearance floor and the
below-zero-walls test; EGGW's `eggw_cabins.obj` until the roof had to stand
over the bore end.

## Questions for the owner (the fix waits on each)

- **Q-a — RULED 2026-10-26k "b", implemented in round 2 (above).** (#1343 site 1, and KBUF bores -5328 / -5327): the pack's
  `Road_Tunnel.obj` portals at 42.943586, -78.726633 and 42.945182,
  -78.724549 stand inside the runway strip keep-out, where the law refuses
  a retaining wall (RULINGS 2026-08-21d, `retaining_wall.in_runway_strip =
  false`).  Today site 1 is uncut (the portal stands on the ground) and the
  other is slid 31.5 m out (the portal stands over covered bore).  Options:
  (A) the strip law stands — the portals stay where they are; (B) a pack
  portal states its cut, inside the strip too (the 19p reading for
  portals); (C) the portal object is dropped from the scenery there.
- **Q-b — RULED 2026-10-26l "yes" (spec only): `Ortho4XP/docs/specs/roofed-pack-tunnels-spec.md`.** (#1298 EGLL): the hard-deck covers (`2.obj` etc.: deck at y 0,
  walls to -5 m, no floor) need the shell reader to take the depth from the
  wall bottoms and assemble split pieces, and a census of lowering airside
  under the decks — the trench under a pack deck, which 22n (1) holds with
  #1138.  This is a spec round and a ruling, not this lane's.
- **Q-c (LFPG, not asked by any issue):** the `H*.obj` taxiway bridges sit
  over mapped bore ends; the road cut under them is the bore law's 7.5 m
  while each bridge's authored zero is 4.3-7.0 m under its deck top.  Read
  as portals, six LFPG mouths would rise 0.5-3.2 m to the bridge's own
  floor and one strip-refused mouth (-10778+-322) would be built.  Excluded
  here (22n / #1138).
