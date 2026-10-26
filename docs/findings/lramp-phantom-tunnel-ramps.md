# Phantom `tunnel_ramp` shapes in airside pavement — attribution (#1331 LGAV, #1337 NZWN)

Lane `lramp`, 2026-10-26, base `origin/main` c95b84fb6. Captures:
`v2_solve_replay --capture` of NZWN and LGAV on that base (LGAV twice: the
owner's FlyTampa pack is now `SCENERY_PACK_DISABLED` in his
`scenery_packs.ini`, so the plain capture reads Global Airports; the
attribution capture reads the pack through a lane-local read-only mirror of
`Custom Scenery` whose ini differs from his in that one line only).

## Site numbers first

| site | production patch (engine 1.50.1874) | this branch, harness build |
|---|---|---|
| NZWN -41.328982258, 174.813874159 | `tunnel_ramp` -10180 (shape 175), -1.73 .. 4.13 m | no patch surface; terrain DEM 5.29 m (`lramp_nzwn5`, artifact ledger `60e537b5ed30`) |
| NZWN -41.329986226, 174.813713002 | `tunnel_ramp` -10181 (shape 177), -1.68 .. 5.40 m | no patch surface; terrain DEM 5.74 m |
| LGAV 37.943947839, 23.951564905 | `tunnel_ramp` -10307 (shape 316), flat 73.73 m | `cross_connector` pav37, ~79.4 m — BUT the harness build reads no FlyTampa pack (disabled); with the pack, the cut is unchanged by this branch (below) |

LGAV harness build `lramp_lgav1` (artifact ledger `3da85cbc2514`): the span
37.943555918, 23.951786711 → 37.944227182, 23.950643419 lies in
`cross_connector` pav37 end to end; its nodes read 79.07 (end A, IDW) →
79.40 → 79.67 → 79.85 (end B) over 125 m (< 0.7 %); no census row on the
three owner points.  That is the NO-PACK reading, which is also main's.

## NZWN — shapes 175 / 177 (FIXED here)

**Minted by** OSM way `-2756`: `highway=service tunnel=yes covered=yes
layer=-1`, 4 nodes, 13 m, a covered lane at the terminal forecourt.  Its two
ends join 6 m stubs (`-2721`, `-2720`, plain `highway=service`) that meet the
at-grade forecourt road `-2745` (`highway=unclassified`) at a T.  Not a
culvert, not a waterway (both are already refused: `[tunnel]
admitted_values = ["yes"]` and `deck_signature.is_tunnel_way` admits only
`highway` / `railway`).

**Code path** (`planar/structures.build_structures`):
1. `structure_approach.mouths` admits both ends (on-field: the forecourt lot
   `dsf:pol2`, classified `apron`/airside, is field cover).
2. `structure_approach.approach` walks the 6 m stub, refuses the ~60°+ turn
   onto `-2745` and continues as a STRAIGHT EXTENSION.
3. `structure_mouth.mouth_at_pavement` (#971) slides each mouth out of
   `dsf:pol2`: 42.5 m and 48.0 m along the axis — 36–42 m of it on the
   extension, past the mapped road.
4. `structure_approach.road_end_m` (#1028 "the ramp follows the road") was
   read on the SLID axis, whose start is already off the road: it found no
   road within `_JOIN_LEAD` half-widths and returned `None` ("the bore's own
   line"), so the ramp ran its full design length: 144 m and 84 m at 5 %,
   7.2 m deep, across unclassified ground east of the lot.
5. The ramp cells take role `tunnel_ramp`; `aeroway=taxiway` is not a
   reclassification of taxiway pavement — it is the EMIT tag every ramp role
   carries (`law/precedence.toml`: `tunnel_ramp … aeroway = "taxiway"`).
   Neither site lies on a taxiway; both lie 35–44 m outside `dsf:pol2`.

**The rule (fix):** a slid mouth stays on its road.  The road's end is read
on the MAPPED approach from the portal and moved by the slide
(`structure_mouth.road_end_after_slide`); a mouth that had to slide past it
stands on no road, the road surfaces under the pavement, and the corridor is
refused, named (`#1337`).  This is #1028's existing law applied in the frame
it was written for; no new law key, no owner ruling needed.

## LGAV — shape 316 (NOT fixed: needs an owner ruling)

**Minted by** the pack object `Trench/Trench_02.obj` (`dsf:obj615`, FlyTampa
`c_GRC - 100_airport - LGAV Athens_0_airport`), read as `object-cut:
Trench_02.obj@0` — a §33 (6) signature-B shell: floor plate 5,194 m² at
-3.98 m, walls 125 × 49.8 m, ends open/open at the portals of the two mapped
road tunnels under the parallel taxiways (`-2503` / `-2500`, `highway=
tertiary tunnel=yes layer=-1`, ~60 m each).  It REPLACES those bores
(05n-3), so its trench is flat at the AUTHORED floor: 73.73 = the object's
zero 77.71 − 3.98.  6,028 m² of `cross_connector` (pav33/pav39 in the
capture, pav31/pav37 without the pack) lie inside the cut.  No OSM tag is
involved (no culvert, no `covered`).

**Code path:** `airport/tunnel_objects` / `object_cut` → `planar/pack_reads`
→ `build_structures(corridors=…)` → the `g.corridor is not None` branch,
which never calls `mouth_at_pavement`: "a pack-stated corridor is never
bound" by the airside set — owner RULINGS 2026-10-19p ("a pack-stated
tunnel/wall object keeps cutting the pavement inside its own walls") and
2026-10-19e (3) ("the full taxiway width stays graded unless it is fully
cut out for an object with a hard deck top").

**Measured against 19e (3):** the hard decks over the cut — `Trench_00.obj`
(`dsf:obj611`, texture `bridge_taxi1`, ATTR_hard_deck, deck top 78.01) and
`Trench_06.obj` (`dsf:obj618`, deck top 79.81) — cover 5,939 of the 6,028 m²;
the 90 m² left are two strips under 4 m wide at the trench ends (nothing
survives a 2 m erosion).  So by the letter of 19e (3) the cut IS lawful, and
the code does what the law says.  The owner's point is under `Trench_00`'s
deck at its y = 0, i.e. at the object stack's zero (77.71 m), while the
solved taxiway either side stands at 79.9–80.0 m: whichever surface the sim
draws there (the bridge deck ~2.2 m low, or the draped pavement in the
73.73 m pit beneath it), the taxiway falls.  The same pack's §45 channel
(Attiki Odos, shapes 301–306, flat 66.47 m) takes 7,213 m² of
`primary_parallel` / `cross_connector` and is 100 % under hard deck.

**Question for the owner (the fix waits on it):** where a pack's
hard-deck bridge carries a taxiway over a cut, but its deck stands
materially off the solved taxiway's level (here ~2.2 m below):
- (A) airside is king — the cut is refused under taxi/runway pavement, the
  taxiway stays graded, the pack's deck and trench end up under the mesh,
  and the two mapped bores keep their own portals outside the taxiway edges
  (exactly what the no-pack build shows: flat 79.07–79.85 m);
- (B) keep the cut and re-seat the pack's deck to the solved taxiway (object
  stage; the #1298 / #1343 family — the stack is ONE placement shared by
  Trench_00…08, so this is a split/seat question);
- (C) keep the cut and hold the taxiway to the deck's level (airside follows
  the object).
19e (3) as written reads as (B)/(C); the master's brief reads as (A).

## #1280 (LFPG 49.008056316, 2.557537871) — NOT the same mechanism

The site is on `tunnel:-300@0` (mouth 49.007948, 2.557471, floor 94.81 m,
72 m ramp): `-300` is `highway=secondary tunnel=yes layer=-1`, and its
approach is the MAPPED at-grade secondary `-13033` → `-1216` running north,
so the ramp follows a real road and this branch leaves it unchanged (LFPG
capture A/B below).  Nor is it LGAV's: no pack object is involved.  The
owner's reading ("the whole intersection is already at tunnel depth, the
taxiway is on a berm") points at the ramp's datum — the DEM the climb is
read against is the berm, not the road's own ground (§33 (3) crest cap /
#1028 road profile) — a separate item.

## What the rule changes elsewhere (dry structure A/B, base c95b84fb6 vs this branch)

`planar.build` run on each capture under both trees; tunnel ids compared.
Every removed ramp is the NZWN class: a mouth slid past its mapped road's
end onto the approach walk's straight extension.

| airport | change | where |
|---|---|---|
| NZWN | `tunnel:-2756@0`, `@1` refused (the owner's two sites) | -41.32916, 174.81340 / -41.32978, 174.81337 |
| LGAV (FlyTampa capture) | none | — |
| VHHH (`c946b` capture) | `tunnel:-5995@1` refused (slid 47.5 m, road ends ≤ 24 m; 156 m ramp) | 22.296405, 113.954648 |
| VHHH | `tunnel:-646@0` refused (slid 69.5 m, road ends ≤ 48 m; 156 m ramp) | 22.303633, 113.938087 |
| VHHH | `tunnel:-4482@0` (36 m) now refused "cannot top out" (its road end is now read from the portal), so `tunnel:-8557@1` (24 m) — refused before as its overlap — is built in its place | 22.3225, 113.9231 |
| EDDF (`c971` capture) | `tunnel:-35430+-18812@0` refused (service tunnel, cutting approaches; slid 51 m, road ends ≤ 48 m; 60 m ramp) | 50.049235, 8.543463 |
| EDDF | `tunnel:-3189+-1462@0` refused (`highway=track` underpass, 35 m; slid 15.5 m, road ends ≤ 12 m; 156 m ramp) | 50.056391, 8.610787 |
| LFPG (this lane's capture) | `tunnel:-31274+-11827@0` refused (slid 68.5 m, road ends ≤ 36 m; 12 m ramp) | 49.010830, 2.576177 |

These want a sim read in the next batch (needs-sim-read); none is on a
taxiway.

## Consumer census of the `tunnel_ramp` role (RULINGS 2026-08-30l)

The change adds no role, region or exemption: it REFUSES corridors at the
one site that mints ramp cells (`structures.py`, `ramp_role = g.ramp_role or
("door_ramp" if g.kind == "door" else "tunnel_ramp")`).  Every reader below
consumes whatever that site minted, so each sees a smaller population and
needs no edit:

| reader | what it reads | effect of a refused corridor |
|---|---|---|
| `planar/structure_geometry.py` (ramp targets, airside-vertex pins) | ramp faces by role | fewer faces |
| `planar/door_ramps.py`, `object_corridor.py`, `wall_corridor_ramps.py` | role naming only | none |
| `pipeline/publication.py` `RAMP_ROLES` | sidecar publication | fewer ramp rows |
| `pipeline/build.py` (snap note) | comment | none |
| `classify/airside_edge.py` | structure ramps excluded from airside edges | none |
| `constraints/structures.py` (RAMP_REF, flat cross-section, rim/wall rows) | ramp faces per tunnel id | rows for refused tunnels absent |
| `constraints/groundside.py`, `foot_rows.py`, `channel.py` | structure-role membership | none |
| `emit/graded.py` `FLOOR_ROLES`, `emit/osm_adapter.py` | floor edges, cap tags | fewer floor shapes |
| `verify/structures.py`, `within.py`, `keepout.py`, `channel.py` | oracle populations | fewer rows |
| `law/model.py`, `law/tables.py`, `precedence.toml`, `families.toml`, `rulesets.toml`, `emit.toml`, `structures.toml` | caps and families by role | none |
| `O4_Vector_Map.py:216` | role list for the mesh | none |
| `tools/check_grade.py`, `harness/law_support/*`, `tunnel_portal_acceptance.py`, `tunnel_mouth_depths.py`, … | census / audit populations | fewer rows |
