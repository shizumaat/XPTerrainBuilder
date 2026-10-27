# Roofed pack tunnels (#1298, EGLL / EGGW): the spec to lift 22n's hold

Status: DRAFT for the owner's ruling. Authorised by RULINGS 2026-10-26l (Q156,
"yes"), which authorises this spec only. The hold of 2026-10-22n (1), the
trench under a pack deck alongside #1138, **stands until the owner rules on the
questions in §8**. Written by lane `lpackcut` on branch
`claude/lpackcut-pack-tunnels` after batches Y, Z and AA.

Rulings it reads: 2026-08-30l (the consumer census comes first), 09-15e/15g
(§33 (6) B, shell plus flush hard cover), 05n-3 (per-mouth precedence), 19e (1)-(3),
19p, 22n, 26d (LGAV: keep the pack's cut and seat its deck), 26k (a pack
portal may cut inside the runway strip).

## 1. Sites: what the packs state (measured on this lane's captures)

The captures are at `/Users/noah/XPTerrainBuilderData/.harness/frames/lpackcut/EGLL.pkl`
and `EGGW.pkl`, base 77e3a13e4, registered in `docs/frames.jsonl`. The probes
are in the lane scratchpad: `probe_covers.py`, `probe_shells.py` and the dry
`planar.__main__.structure_records`.

### 1.1 EGLL (TaiModels): a SPLIT shell, the floor in one object and the walls in the other

Each tunnel is TWO co-placed objects:

- `N.obj` is the COVER: an `ATTR_hard_deck` plate at y ≈ 0 (the apron) with
  vertical walls down to the floor level, and NO floor.
- `Na.obj` is the FLOOR: the floor and ramp plates, also `ATTR_hard_deck` (the
  road surface), at −4 to −7 m, with NO vertical walls.

The §33 (6) B reader wants floor AND walls in one object plus a separate
cover, so it refuses both halves:
- every `N.obj`: "no floor plate";
- `2a`, `3a`, `8a`, `11b`: "the shell has no vertical wall face";
- `5a`, `9a`: "the trench ring has 1 open end".

| pair (anchor) | cover deck at y≈0 | floor (Na) | wall bottoms (N) | deck over floor | mapped bores under it | how it is cut today (OSM bore law) |
|---|---|---|---|---|---|---|
| `2`/`2a` (51.468917, −0.480277) | 16,734 m² | 16,892 m² at −5.0 | −5.0 | ~99 % | −12057, −10108, −10105, −10102, −10101, −6797 | `-12057+-6797@0` 10.81 (5.94 deep), `-10108@1` 11.45, `-10102@0` 17.05 (slid, 2.27 deep); 4 refused |
| `3`/`3a` (51.473647, −0.484077) | 5,782 m² | 4,868 m² at −5.0 | −5.0 | >100 % | −10096 | `-10096@0` 1.52 deep (12 m ramp), `-10096@1` 7.5 deep |
| `5`/`5a` (51.467455, −0.490588) | 626 m² | 1,934 m² at −4.83 | −4.83 | 32 % (open ramp) | −10108 | `-10108@1` 11.45; `@0` refused |
| `8`/`8a` (51.469003, −0.454553) | 382 m² | 1,742 m² at −4.0 | −4.08 | 22 % (open ramp) | −12057, −6797 | `-12057+-6797@0` 10.81 |
| `9`/`9a` (51.467216, −0.444671) | 7,808 m² | 9,596 m² at −4.49 | −4.55 | 81 % | −37634 … −12035 | `-12037@0/@1`, `-12035@0`, all 7.5 deep |
| `11`/`11a`/`11b` (51.45995, −0.459956) | 2,058 + 1,095 m² | 5,060 m² at −7.01 | −6.0 / −7.04 | 62 % | −6787, −13448 | `-6787@0` 7.5 deep, `@1` 4.55 |

The floor is AUTHORED, and the wall bottoms agree with it to within 0.1 m at 2, 3, 5, 8 and 9 (11's walls
reach −6.0 and −7.04 against a floor of −7.01). So **the depth is the Na floor
plate**. The wall bottoms are only the fallback for a cover with no floor
object. Today the bore law cuts 7.5 m (or a slid profile) where the pack
states 4.0–7.0 m, and it places the mouths at the OSM ends, not at the cover's
open ends. That is the owner's "our tunnel cuts are not aligned at all".

### 1.2 EGGW (UK2000): a bare PORTAL FACE, and no cover

- At both ends of bore `-20893+-908` stands a `…-eggw_tex14.obj`. It is ONE
  vertical quad, 45.2 m wide, from y +0.06 down to **−8.33 m**: the portal's
  headwall face at the anchors 51.876717, −0.376467 and 51.877144, −0.375404.
  Both readers refuse it: "no floor plate", and "the solids' plan hull is
  degenerate (a line)".
- There is no cover deck. The taxiway over the bore is mesh, and the bore law
  cuts each mouth 7.5 m deep, while the face's foot stands at 8.33 m.
- The other candidates (`eggw2020_7`, `tex3`, `tex6`, `tex13`) are buildings,
  and they rightly stay refused. `eggw_cabins.obj` is not a portal (#1343's
  roof-over-the-end test).

## 2. The census of consumers (RULINGS 2026-08-30l): one ruled table

Every pass that reads a pack tunnel object, the cut it makes, or the surface
over it. "R1" is the split-pair reading of §3, "R2" the portal face of §4 and
"R3" the airside over the cover of §5.

| # | pass | what it reads | effect of R1–R3 | ruling |
|---|---|---|---|---|
| 1 | `airport/object_cut.read_shells` / `shell_reading` | one shell resource and a co-placed flush cover | R1 assembles the PAIR before reading: the floor from `Na`, the walls from `N` | extend (§3); no new reader |
| 2 | `airport/object_cut._cover_plate` | the flush hard-deck plate | unchanged: `N`'s deck at y ≈ 0 is the cover | — |
| 3 | `airport/tunnel_objects.shell_corridor` | the trench, axis, stations and depth | depth = the authored floor (already its law); the mouths at the pair's open ends | unchanged code |
| 4 | `airport/tunnel_objects.read_corridors` refusals | the per-resource verdicts | `N` / `Na` leave the refusal list | — |
| 5 | `airport/portal_objects` (#1343) | roofed portals over bore ends | R2 adds a bare FACE reading (no roof): the face's foot is the depth | extend (§4) |
| 6 | `planar/structures.build_structures`, 05n-3 precedence | an OSM mouth inside an object corridor's footprint is the object's | EGLL bores under the pairs become the object's (replaced) | unchanged |
| 7 | `planar/structure_mouth.mouth_at_pavement` (#971) | a mapped mouth slides out of pavement | an object corridor is never bound (19p) | unchanged |
| 8 | `planar/object_corridor.object_groups` | object corridor groups | unchanged | — |
| 9 | `planar/basins` (claimed shells are never basins) | `shell_claimed` | must claim BOTH `N` and `Na` | extend (§3 (4)) |
| 10 | `planar/channel_*` (§45) | channel witnesses | a pair is not a channel witness (its open ends are bores) | verify on EGLL (§7) |
| 11 | `classify` (airside cells over the cover) | the apron pavement over the trench | R3 decides: cut (5a) or stays (5b) | **owner (§8 Q2)** |
| 12 | `constraints/structures` (floor rows, rim rows) | the trench floor, the rim | floor = the authored floor; the rim at the cover's edge | unchanged code |
| 13 | `constraints` airside laws (airside_no_step, within_shape) at the cover's edge | the apron either side of a cut | under 5a the apron edge meets the void; the existing #946 / §33 (6) B AMENDED (3) (c) exemptions (`decked`) apply | unchanged code; verify the rows (§7) |
| 14 | `emit/graded`, `osm_adapter` | the floor and ramp faces | unchanged | — |
| 15 | `pipeline/publication.object_cuts` → `verify` `object_cut_offset` / `object_cut_depth`, `ramp_in_strip` (#946) | the object's outline and floor | the pair's union outline; the Na floor | extend (the outline is the union) |
| 16 | `pipeline/authored_seats`, `rebake_inputs` (cut rings, 26d) | the seat decision; the cut ring | the pair is "authored (cut)" when its floor matches; the ring rides the record | unchanged code |
| 17 | `airport/placement_plan` class A (22n) / `cut_deck_seat` (26d) | the deck seat | `N` is a FLAG deck over a pack cut, so 26d's body seat puts it flush with the airside at its end lines | unchanged code (26d already reads it) |
| 18 | `airport/placement_write` | the kept rows | `Na` stays at its authored seat when the cut matches it | unchanged |
| 19 | the census (`tools/check_grade`, harness law families) | the object cut families, ramp_in_strip | read the published pair outline | unchanged code |
| 20 | #1138 (held): grading to a bridge's far end, the trench under a pack bridge | — | R3 (5a) IS a trench under a pack deck, for roofed TUNNELS only (a cover with walls, floor and bores at its open ends), never a bridge over a road | **owner (§8 Q1)** |

## 3. R1: the split shell (EGLL)

1. **The pair.** Two placements at the same anchor and heading
   (`cover_placement_tol_m`, 1°), the same rule `read_shells` already uses for
   the cover:
   - the FLOOR member carries the deepest plate of a plate's worth
     (`plate_min_area_m2`), `shell_floor_min_m` or more under its zero;
   - the WALL member carries the vertical faces and a flush hard deck at
     |y| ≤ `cover_flush_m`.

   Today `shell_reading` takes one resource. R1 hands it the UNION of the two
   members' genuine components, in the shared authored frame, and the cover
   is the wall member. No new constants.
2. **The depth.** The authored floor (`floor_y`), as §33 (6) B already rules
   ("the DEPTH IS AUTHORED").
   - Where a cover has walls but no floor member, the depth is the median of
     the wall faces' bottom y: the cut ground is the floor the author left to
     the terrain. This amends the 09-08l reading at `tunnel_objects.py` (the
     depth was the floor slab, else `mouth_depth_m`) for a roofed cover only.
   - Measured: the walls agree with the floor to within 0.1 m at 2, 3, 5, 8 and 9.
     At 11 they reach −6.0 and −7.04 against a −7.01 floor, the one place the
     fallback would read shallower.
3. **The ends.** The open runs of the union's trench ring (the existing
   `_ring_ends`). 5a and 9a read "1 open end" alone; with the walls of `N`
   added, the ring is walled everywhere but at its portals.
4. **The claim.** Both members are claimed out of the basin intake
   (`shell_claimed`), as the cover already is.
5. **Precedence.** 05n-3 unchanged: every OSM mouth inside the pair's footprint
   is replaced. At EGLL this retires the ten OSM ramps in §1.1's last column and
   the refusals beside them.

## 4. R2: the bare portal face (EGGW)

This extends the #1343 portal reader (`airport/portal_objects`) with one case:
a single near-VERTICAL face, at least a lane wide
(`tunnel.object.hull_min_length_m`, 10 m), standing over a mapped bore end
(`bore_end_tolerance_m`), whose foot reaches below its zero:

- **the depth at the mouth = the face's foot** (8.33 m at EGGW), never
  `mouth_depth_m`;
- the mouth is pinned at the face (#971 "or object if one is provided");
- the face, at one anchor, re-seats so its foot meets the ramp floor (the
  object stage's plate seat, 05n-4).

The same exclusions as the roofed portal: no hard deck, no floor, the face
over the end, and at most `mouth_depth_m` + 1 storey (a deeper face is a wall,
not a portal). A face in the runway strip may cut there under 26k.

## 5. R3: the airside over a roofed tunnel

The cover `N.obj` IS the apron surface over the trench (`ATTR_hard_deck` at
y ≈ 0, 99 % of the trench at pair 2). Two models, both emittable (§6):

- **5a: the cut goes under the deck (the LGAV / VHHH model, 26d, 19e (3)).**
  - The apron faces over the trench are cut out; the mesh drops to the floor.
  - The deck carries the airside, seated flush by 26d's `cut_deck_seat` at its
    end lines.
  - Where the deck does not cover the trench (pairs 5, 8 and 11: 32 %, 22 % and
    62 %), the uncovered part is the open ramp, exactly as the pack draws it.
  - The cut is bounded by the pair's own outline (19p); it never crosses a
    taxiway edge outside the walls (19e (2)).
- **5b: the airside stays and the cut goes under it.**
  - The apron faces over the trench keep their graded surface; only the
    uncovered open ramps are cut.
  - The deck sits flush on the mesh, so the tunnel's interior (walls, floor)
    is buried under the mesh, invisible except at the open ends.
  - The ramps align with the pack's (§3 (3)), so the mouths match the
    objects, which is the owner's complaint. A vehicle on the floor drives
    into the mesh where the deck covers it.

## 6. Can a heightfield mesh emit it?

- **5a.** The mesh has one z per (x, y). Under the deck, z is the floor (−5 m);
  the apron surface is the deck OBJECT above, not the mesh. The trench's
  vertical walls are mesh faces between rim vertices (z = grade) and floor
  vertices (z = floor) at the identity spacing, as every object corridor
  already emits them (`emit.identity.min_distinct_spacing_m`; LGAV, VHHH).
  - At the deck's edge the mesh's rim stands at the apron level and the deck
    sits on it (26d end lines). Emittable.
  - Where the deck is narrower than the trench, the uncovered strip is an open
    pit. That is the author's own open ramp: pairs 5, 8 and 11, ≈ 1,300 /
    1,360 / 1,900 m² uncovered.
- **5b.** The mesh is the graded apron; no vertical faces are added except at
  the open ramps. Emittable trivially.
  - The pack's tunnel walls and floor lie inside the solid earth, which
    X-Plane draws without complaint, but the tunnel interior is unreachable.
- **R2.** A mouth whose floor is 8.33 m under the ground is an existing bore
  ramp with another depth. Emittable (the #1343 pinned mouths are the
  precedent).

## 7. What a lane round must measure (the closing bars)

1. EGLL dry structure A/B on the registered capture:
   - the six pairs read as six object corridors;
   - the ten OSM mouths in §1.1 replaced;
   - the floor at each = anchor DEM + floor y, within 0.1 m.
2. EGLL build:
   - the six owner sites' floors and deck tops against the solved apron at
     the cover's end lines (|Δ| ≤ 0.05 m, 12y);
   - the open ramps against the `Na` ramp plates;
   - no new `airside_no_step` / `within_shape` rows outside the covered
     outline (under 5a).
3. EGGW dry A/B: `-20893+-908@0/@1` pinned by the two `eggw_tex14` faces at
   8.33 m; nothing else changes.
4. The consumer table in §2 re-read against the code at that base, before
   any edit (08-30l).

## 8. Questions for the owner (each answerable in one word)

- **Q1 (lift the hold):** May a ROOFED pack tunnel (a cover deck with walls,
  over mapped bores) cut its trench under its own deck, so that 22n (1)'s hold
  is lifted for roofed tunnels only, while #1138 (bridges over roads) stays
  held? *yes / no*
- **Q2 (the airside model, §5):** Over a roofed pack tunnel, does the deck
  carry the airside (5a: cut under the deck), or does the airside stay graded
  (5b: only the open ramps cut)? *deck / airside*
- **Q3 (split pairs, §3):** May a pack's floor object and its co-placed cover
  be read together as one tunnel (EGLL's `Na` + `N`)? *yes / no*
- **Q4 (depth without a floor, §3 (2)):** Where a cover has walls but no floor
  object, is the cut depth the walls' bottom? *yes / no*
- **Q5 (portal faces, §4):** Does a bare vertical portal face over a mapped
  bore end (EGGW's `eggw_tex14`) set that mouth's depth to its foot? *yes / no*

## 9. R4: the edge-wall bridge (KATL, #1138; owner RULINGS 2026-10-27l)

**What the pack states.**  KATL's `tunel_A/B/C` model a taxiway bridge over
I-285 by its EDGES only: a deck slab (plates at y 0 and −2.1, 3,200–8,150 m²,
no `ATTR_hard_deck`) projecting over the highway on piers to −25.4/−25.9 m,
behind it a headwall to −23.2 m, and NOTHING over the span between the two
edges (`tunel_C`'s headwall and `tunel_B`'s face each other across the
taxiway, ~40 m apart).  The bare-earth DEM carries the highway (290–293)
under the whole bridge; the field beside it stands at 300–303.

**The rule (27l (a), with 20am / 20ao / 20ar and 26p Q167).**  A pack
object with no hard deck whose top is a deck — plates of `plate_min_area_m2`
within `cover_flush_m` of a top flush with its zero — standing on walls that
hang `shell_floor_min_m` or more under it with no floor at their bottom, is
an EDGE-WALL BRIDGE (`airport/hanging_objects.edge_wall_reading`).  Over a
mapped bore end it is read like a hanging portal, with three differences:

1. **The trench stops at the walls' backs** (20ao "the road ends at the back
   of the object"): the mouth moves into the bore to the furthest station any
   of its deep walls reaches across the corridor's width
   (`planar/structure_mouth.edge_wall_mouth`) — the headwall — never to the
   far corner of its plan.  The #971 pavement yield then applies as for every
   pinned mouth: the trench never cuts a taxiway (KATL: the taxiway `pav15`
   runs over the slabs, so the mouths stop at its edge).
2. **The depth is the walls' bottom under the deck level** (20am / 20ar /
   Q167): floor = the ground the top is flush with (the ground beside the
   cover, #714) − the walls' bottom.
3. **The span keeps the deck level** (27l; 27r "drop straight down ... at
   the back of those edge objects, with the top of the objects flush with the
   airside surface"): the covered ground of #714 is clipped to the airside
   pavement AND the span between consecutive edge objects over the bore, from
   one's walls' back to the other's (`planar/covered_span.edge_spans`) — the
   ground there takes the ground beside the cover, never the lidar road —
   and every terrain deck over the trench (a mapped bridge way — KATL's
   service road `-3152`) stands at or above that deck level as a HARD row
   (`constraints/structures._span_deck_rows`, head
   `bridge.edge_wall_deck_level` in `[design] hard_rulings`, ranked with
   `tunnel.mouth_depth_m`; the record `Tunnel.span_deck_z`): the service road
   level with the taxiway.  Measured soft, the road cap held it 6.5 m under.

**Consumer census (08-30l), the passes this reading reaches:**

| pass | effect | ruling |
|---|---|---|
| `airport/portal_objects.read_portals` | a plated hanging object over a bore end is a `Portal` with `edge_walls` | extend |
| `planar/structures` pin | `edge_wall_mouth` instead of the plan hull; the deck level recorded | extend |
| `planar/structure_mouth.mouth_at_pavement` (#971) | the pinned mouth slides out of pavement, keeping its depth (20am / 20ar) | unchanged |
| `planar/structure_mouth.strip_keepout` (26k) | a pinned cut may stand in the runway strip | unchanged |
| `planar/structure_overlap` (31h) | parallel carriageways 46 m apart are no dual: one corridor of the overlapping set is kept | unchanged — finding: merging the mouths one edge object stops into one trench was measured worse (the merged mouth slid 140 m out and lost the deck) |
| `planar/covered_ground` (#714) | the cover's clip takes in the span between the edges (`covered_span`) | extend |
| `constraints/structures` terrain deck rows | hard rows at the deck level; the end ties skip below it (`deck_floor`) | extend |
| `pipeline/publication.portal_cuts`, `verify` strip families | the pinned cut's rim | unchanged |
| object stage seat (`placement_plan`) | the edges seated by the existing seat law | unchanged — follow-up (the EGGW face seat, §4) |

**Closing bars (KATL).**  The owner's site 33.622378944, −84.426822485 (the
service road on the bridge next to the taxiway) level with the taxiway beside
it (12y: ≤ 0.05 m on pavement); the I-285 trench floor at the walls' bottom
under the deck level; the span between the edges at the deck level; no new
verify rows outside the cut.
