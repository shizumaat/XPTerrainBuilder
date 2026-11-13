# EGLL tunnel mouths, round 2 (#1938): both mouths as X-Plane draws them

Review under the one-miss rule (RULINGS 2026-11-11c) of round 1, lane
`legll2` (`claude/legll2` 24cd5e3fe: 0d6b69944, 7921b3cd9). Written
2026-11-12 (local) by the reviewer; read-only, no code changed. A fresh
Opus lane implements this from `claude/legll2` at 24cd5e3fe. If this round
also misses the drawn gate, the task goes to the owner (2026-11-03d).

Owner, 2026-11-13T04:00Z: "There's definitely a tunnel mouth there that
should be cut at 51.4798, -0.4530". 04:02:29Z: "There should be a ramp on
the south side too at EGLL, why are we refusing it?"

Site: OSM bores -11670 / -11669 (`highway=tertiary tunnel=yes layer=-1`,
632 m, a dual carriageway), tile +51-001. South mouth 51.47409, -0.45295
(in the central terminal area); north mouth 51.47977, -0.45299 (north of
runway 09L/27R, where the road leaves the airfield in an open cutting). Elevation is 1 m lidar (`EGLL_england1m`).

## 0. What round 1 did, and why it missed

Round 1 narrowed §34 (12) (5) (e) (RULINGS 2026-11-13h): both bores are
admitted. That change is right and stays. The drawn gate
(`legll2E1.drawn.json`) failed because admission was the first of four
defects, and the other three were not on the lane's list.

Every number below was measured by the reviewer on 24cd5e3fe unless marked
*(lane)*. Sources: the frames in
`/Users/noah/XPTerrainBuilderData/.harness/frames/legll2/`, the dry
replays `python -m auto_patch_v2.planar EGLL --stage structures` and
`python -m auto_patch_v2.planar EGLL` (2 min each), the pack's `10.obj`
through `airport/obj8.parse_obj8`, and the lidar inset.

### 0.1 South: the ramp is not drawn at all

| What | Value |
|---|---|
| Tunnel record `tunnel:-11670+-11669@0` | mouth_z 17.30, top_s **24.0 m**, grade 5.95 %, `clipped 'building48'` |
| Patch polygon that contains the ramp centre 51.47400, -0.45297 | way -10360, role `building`, ref `building31` (the 70,370 m2 terminal pad, 23.35..24.14); its only holes there are the two wall strips |
| `tunnel_ramp` ways of this tunnel in the patch | 2 slivers: -11663 (3.4 x 0.5 m, 17.30..17.46) and -11664 (2.5 x 0.5 m, all 23.71) |
| Drawn mesh at the mouth point *(lane)* | 20.26, against a floor of 17.30 |
| `10.obj` as drawn *(lane)* | one split body `10__b0`, anchor moved 154 m, draped at 23.73, bottom 19.97: +2.67 m over the floor (bar 0.3) |

Three causes, each a general defect:

**(S-a) A pad is never cut by a mapped bore's ramp.**
`planar/structures.py:1452` cuts a `building` cell with `hull_knife` only
(the knives of object corridors, `:1349`); a mapped bore's footprint goes
into `knife`, which pads are exempt from. The comment at `:1415` says why:
"never a pad — those refused above". That stopped being true when
`structure_mouth._pinned` (`structure_mouth.py:589-593`, #1747 / LOWS)
began to drop the pad the pinned opening stands in from the ramp's stops.
The pad is no longer a stop, and it is still not cut, so the pad cell and
the new ramp cell overlap and the pad keeps the ground. The full planar
replay shows the same: the ramp centre lies in a `building` face and the
tunnel has no `tunnel_ramp` face. At LOWS the pad at the opening was the
entrance object's own, which 2026-11-06b (6) no longer mints; at EGLL it
is the terminal block's pad.

**(S-b) A pad clips the ramp inside the object's own walls.** The ramp
stops at 24 m at `building48` (cluster `unit:100#889/0`, no bodies, no
footed bodies, level 23.81; it crosses the carriageway 26–46 m south of
the mouth). `10.obj`'s east wing wall runs 64 m. The clip law for an
object corridor is "an object corridor's WALLS are never clipped: only
its ramp BEYOND the walls is" (`structures.py:938-945`, 05k-1 / 08-26),
but `beyond` is set only for `c is not None`, and an entrance object's
mouth is a mapped bore's (`c is None`). Unverified: which pack parts mint
`building48` (the sidecar lists no members). The rule below does not
depend on it.

**(S-c) The object is not seated on the floor its own bottom set.**
`trench_objects.mouth_portals` reads the floor as the pack's zero plus the
solids' bottom (23.379 - 6.075 = 17.304) and then publishes
`bottom_y=None` (`trench_objects.py:338-344`), because the solids at the
end are a "face" only when their top is within `cover_flush_m` (1.0) of
the object's zero; `10.obj`'s coping top stands at y +1.78. With no
`bottom_y`, `structures.py:1244-1247` publishes the ROOFED-portal seat
(zero ON the floor), `terrain_shaped.row_seats` (`:344`) drops it because
the plan splits the row, and the one body (`placement_plan.py:1246-1260`,
`one_body_off_row`) is draped on whatever stands under its new anchor. The
floor was read against the DEM at the authored anchor (24.38); the body is
drawn against the solved pad (23.73) at another point. Nothing ties them.

### 0.2 South: what `10.obj` is

`OBJECT_AGL` row 11851, anchor 51.472490845, -0.453031777, AGL -1.0001,
heading 0. 920 solid triangles, no hard deck, y -6.07..+1.86; it stands
113–178 m north of its anchor.

- A headwall across the road at the bore ends (25 m wide), with two
  openings 9.92 and 9.86 m wide, lintel y -1.21..-1.29, jamb feet
  -5.64..-5.86, outer corners -5.91 and **-6.07**.
- Two wing walls running south: east 64 m (foot -6.07 at the portal to
  -1.27 at its end), west 16 m along the road (-5.91 to -4.70). **Both
  feet rise 7.5 % along the road.**
- **No floor.** Up-facing plates total 129 m2. The "-3.0 m, 13 m2 floor
  plate" of the lane's report is the top of the 1.6 m wide median pier
  between the carriageways (x 3.5..5.2, z -165..-172). It is not a floor.

So the depth question has one answer in law: RULINGS 2026-11-06d (4) "If
there's not floor then just to the wall depth is good", and 2026-11-06c
(5) "the bottom of the ramp meets the bottom of the mouth object that
faces the ramp". The mouth floor is the wall feet, 17.30. The lidar road
at the south portal is 19.8 (5.5–5.9 m under its cover 25.3–25.7, and it
reaches grade 23.3 about 95 m south); at 19.8 the openings would be 2.4 m
tall, at 17.30 they are 4.87 m.

### 0.3 North: the patch itself draws the slope

`tunnel:-11670+-11669@1` is refused: "the credible survey carries the
road: 16.57 at the portal, 8.60 m under the cover 25.17 over the bore — it
clears the 7.50 m owed (under airside pavement, 231 b); nothing is cut a
second time (RULINGS 2026-10-28k (226 a))" (`lidar_road.py:301`, verdict
`KEPT`; `structures.py:559-561` then `continue`s).

The lidar does carry the portal: at 51.47975 it reads 24.9 across the
whole width, at 51.47979 it reads 16.3–17.0 on the carriageways. A face of
8.6 m in 4 m, in a cutting 35 m wide.

The patch does not. With no structure there, the mapped roads north of the
portal are ordinary `service_road` cells (`small_roads:-35648`, `-2654`,
`-26115`, `-7410`): 20.04–20.44 on the portal line and 16.97–17.67 at
15 m north. The road at the portal is drawn 3.7 m over the surveyed road
and climbs the face at 20 %. That is the lane's "7 m slope over 22 m".
226 a's refusal assumes the raw survey reaches the mesh; nothing in a
refused mouth makes it so.

## 1. Rules (all general; no rule names an airport, pack or resource)

### N1. A surveyed mouth is still a mouth (narrows 2026-10-28k "refused by name")

Where the credible survey's verdict is `KEPT` (the surveyed road already
clears the depth owed), nothing is cut under the surveyed road — that part
of 226 a / 232 a stands — but the mouth is BUILT at the survey's own
depth: `floor = road`, `extra = 0`. Its cap is the portal face, its rim
the walls, and its ramp the short run from the portal to where the floor
meets the survey (`ramp_top`: the first station plus one of slack). `NO_SIGN`
(no cut shown, 232 a) stays a refusal. A `KEPT` mouth whose cap does not
stand over its floor (`structures.py:691-698`, `slid_depth <= tol_m`)
stays a refusal: there is no face to draw.

- `planar/structures.py:559-561`: refuse and `continue` only for
  `NO_SIGN`. For `KEPT`, fall through with `road_f = road_rd.floor`.
- `planar/lidar_road.py`: `survey_mouth_refusal` keeps its `KEPT` text for
  the `:697` site; `survey_mouth_note` gains the `extra == 0` wording
  ("built at the surveyed road: the portal face and walls at the survey's
  depth, nothing cut under it"). The module doc's "the mouth is refused by
  name" sentence is replaced by this rule.
- The crest: if the replay lists the mouth in `crest_from_approach`
  (`structures.py:657-676` caps the crest at the approach ground +
  `mouth_depth_m`; the approach ground is about 16.6–17.5, so the cap
  would be about 24.1–25.0 against a surveyed cover of 25.17), a mouth the
  survey decides keeps the survey's cover: R1 measured it, and a rim under
  the ground behind it would be a second step. Skip the cap when
  `road_rd is not None`; say so in the note.
- `survey_trench` (R2) is unchanged: the open cutting beyond the ramp is
  still a keepout the zones stop at.

Scope: every `KEPT` mouth on a credible inset, road or rail, paved or not
(owner question Q1 offers the narrower reading).

### S1. The pad a pinned opening stands in is cut by that ramp

The pads `_pinned` drops as stops because the opening stands in them
(`structure_mouth.py:593`) are that tunnel's HOST pads. The tunnel's
footprint (`outer`) cuts its host pads, and only those: a per-pad blade
beside `hull_knife` at `structures.py:1452`. A pad beyond the opening
still stops the ramp (08-07 ruling 3) and is still not cut. `_pinned`
returns the host refs (or `build_structures` re-reads them with the same
`mouth_ring` test: one derivation, not two).

### S2. Inside an entrance object's walls the trench is senior to a pad

For a mouth pinned by an entrance object (`trench_objects.mouth_portals`),
the WALL REACH is how far the object's solid triangles whose lowest
vertex hangs `shell_floor_min_m` or more under its zero run along the
approach from the mouth (their plan projected on the axis; 64 m here). Over that reach the ramp is the trench between the
pack's own walls: it is not clipped by a pad (`structures.py:945` —
`beyond` starts at the wall reach, as it does at `g.hull_s` for a
corridor) and its footprint cuts the pads it crosses (as `:1328-1349`
does for a corridor, with the same guard for pads beyond the walls).
Beyond the reach every stop works as today.

### S3. Under an entrance object's walls the ramp climbs at the walls' foot slope

The design grade of that ramp is the slope of the object's wall feet along
the approach (a least-squares line through the lowest solid per 2 m
station over the wall reach, both sides), never under `ramp_grade` and
never over `ramp_max_grade` (2026-10-08d (1): the cap is for "situations
where an object dictates a shorter distance"; here the object dictates the
grade). Read it in `trench_objects` next to `_wall_opening`, carry it on
the `Portal` (`foot_grade`, 0.0 for any other pin) and use it where
`design_g` is set (`structures.py:544`). Expected for `10.obj`: 0.075 ±
0.005; the ramp then tops out about 81 m from the mouth, the lidar road
about 95 m.

### S4. A walled entrance is seated with its bottom on its floor

`mouth_portals` publishes `bottom_y` for every entrance whose solids at
the end stand a wall's height (`top - bottom >= shell_floor_min_m`),
whether or not their top is flush with the object's zero. For the
flush-top FACE nothing changes (floor = cover - height). For a walled
entrance whose top is not flush (this object) the floor stays the pack's
zero plus the bottom, so the published zero `floor - bottom_y` is the
pack's own zero (23.38) and `entrance_seat.seat_faces` pins the body
there. A floor plate or sheet (LFLL `TGV_LY_13`: height 0.05 m) still
publishes none. `face_plan`, `face_top_z` and `top_plan` stay `None` for
the non-flush case, so no skirt is built and the mouth stays at the
portal's anchor (`portal_mouth`), as in round 1.

Seat authority, as asked: the split body is the authority
(`row_seats`' one-authority rule is right), and it takes its zero from the
ENTRANCE record. The roofed-portal record (`zero = floor`) must never be
published for an object whose solids hang under its zero: it would have
put `10.obj`'s bottom at 11.2.

One trap: `open_frame_seat._at_zero` seats a body by an offset from the
plan's surface under the body's own anchor, and X-Plane drapes it on the
drawn mesh there. The two agree on the ramp floor (7.5 %: 1 cm per
0.15 m) and do not agree on a wall band or rim. If the body's anchor
lands within 2 m of the ramp's edge, report it; do not tune the anchor
for this object.

## 2. Consumer census (RULINGS 2026-08-30l)

| # | Region or value | Reader | Ruling |
|---|---|---|---|
| 1 | KEPT mouth now a `Tunnel` | `structures.build_structures` loop | built with `road_f`, `extra` 0 (N1) |
| 2 | | `structure_mouth.mouth_at_pavement` (unpinned) | unchanged; if it slides the north mouth more than 3 m, stop and report the stop's ref |
| 3 | | `lidar_road.survey_trench` / `zones.zone_regions` | unchanged; the corridor's `outer` joins the keepouts as for any tunnel |
| 4 | | `structure_overlap.resolve_overlaps` | unchanged; replay must show no new overlap refusal |
| 5 | | `constraints/structures` (floor tied to cap by `depth_m`) | `depth_m = mouth_dem - mouth_z` (8.6), the R1 value already used for built survey mouths |
| 6 | | `publication.tunnel_mouth_depths`, `check_grade` | reads the same value; census run once on the closing patch |
| 7 | | road cells on the ramp | cut by `knife` like any pavement (08-07 ruling 4) |
| 8 | | `drawn_check.read_sites` | a new `tunnel_ramp` site and a mouth site, role UNCLAIMED (no object): no object bar; the patch→drawn layer judges it |
| 9 | Host pad cut by a pinned ramp | `structures.py:1452` `_cut` | S1 |
| 10 | | pad flats / `frontage_hold` rows (`constraints`) | the cut removes the pad's vertices from the ramp; replay must show no new `hard_conflict` row naming `tunnel_ramp` or `tunnel_wall` with the host pad |
| 11 | | cluster pads, landings, `pad_touch` | read the cut cell; `building31/landing1` stands 30 m east of the ramp edge, untouched |
| 12 | | object plan: bodies footed on the host pad inside the cut | only the entrance object itself (S4) and elevated parts, which keep the group seat (2026-11-13h) |
| 13 | | emit (`face_holes`), `verify/keepout`, `publication.portal_cuts` | unchanged |
| 14 | Pads inside the wall reach | `_pad_hit` probe, `hull_knives` | S2 |
| 15 | `Portal.bottom_y` on a non-flush walled entrance | `structures.py:1228-1243` | publishes the 4-tuple ENTRANCE seat |
| 16 | | `entrance_skirt.is_entrance_face` | false (`face_plan` None): no skirt, no `face_front_mouth` |
| 17 | | `entrance_skirt.entrance_top` / `constraints/airside_top` | `()` (`top_plan` None): no airside-top zero |
| 18 | | `airport/portal_floor.py:74`, `object_floor.py:691` | already skip on `floor_z`; unchanged |
| 19 | | `terrain_shaped.portal_seat_records` → `entrance_seat.seat_faces` (`placement_plan.py:1041`) | the body within 10 m of the end takes zero 23.38 |
| 20 | `Portal.foot_grade` | `structures.py:544` design grade, `_unframed_climb` | S3 |

Emittable in a heightfield: yes. Every face here is the ramp edge and the
rim `wall_gap_m + wall_band_width_m` (1.6 m) apart, the form every built
mouth already has.

## 3. Twins

- `tests/auto_patch_v2/test_tunnel_ramps_ltramp.py`: a KEPT survey mouth
  is built at `floor == road` with a ramp of at most two stations and its
  `survey_trench` keepout; `NO_SIGN` is still refused; a KEPT mouth with
  no face at its cap is still refused.
- `tests/auto_patch_v2/test_entrance_object1747.py`: (i) the host pad is
  cut by the pinned ramp's footprint and a pad beyond is not (beside the
  existing `test_the_entrances_own_pad_never_stops_its_ramp`); (ii) a pad
  across the approach inside the wall reach neither clips nor survives the
  trench, and one beyond the reach still clips; (iii) a walled entrance
  whose top stands 1.8 m over its zero publishes `bottom_y`, keeps
  `floor = zero + bottom`, and its body is seated at that zero; a sheet
  publishes none; (iv) `foot_grade` of two synthetic wing walls rising
  7.5 % is 0.075 and sets the design grade, capped at `ramp_max_grade`.
- `tests/auto_patch_v2/test_tunnelwitness2.py` (round 1) stays as is.

## 4. Bars

Replay first; the tile is built once.

**R1, structure replay** (`cd Ortho4XP && PYTHONPATH=src venv/bin/python
-m auto_patch_v2.planar EGLL --stage structures --out DIR
--allow-degraded-dem`, 2 min):
- `@0`: mouth_z 17.30 ± 0.02, `design_grade` 0.075 ± 0.005, top_s ≥ 64,
  no `clipped_by` inside the wall reach; portal pin `bottom_y` -6.07.
- `@1`: present in `tunnels`, mouth_z 16.57 ± 0.05, mouth within 3 m of
  51.47977, -0.45299, top_s ≤ 36; absent from `tunnel_refused`.

**R2, planar replay** (`... -m auto_patch_v2.planar EGLL --out DIR
--allow-degraded-dem`, 2 min; `faces.geojson`): the face containing
51.47400, -0.45295 is `tunnel_ramp` (today `building`), and the face
containing 51.47985, -0.45300 is `tunnel_ramp` (today `service_road
small_roads:-2654`).

**R3, corpus** (`tools/structure_replay_diff.py`, base 24cd5e3fe, the
lidar and entrance airports that have frames: EGLL, LFPG, LOWS, ENTC,
KLAX, EGKK, KBUF, EDDF, OMDB, CYXY): the report lists every mouth that
changes, by class — KEPT → built (with cover, road, clearance), host pad
now cut, walled entrance now seated, grade from the foot slope. Anything
outside those four classes is a stop. The master reads the list before
the build.

**R4, object stage** (`tools/v2_rebake_replay.py`,
`tools/rebake_plan_diff.py`): `10.obj`'s body carries the reason
"entrance face on its portal's floor at zero 23.38".

**Closing build** (after the harness fix below):
`venv/bin/python tools/harness/build_airport.py EGLL --tile 51 -1
--pack-copy DIR`, then the drawn gate with
`--site north=51.4798,-0.4530,60 --site south=51.4741,-0.4530,60
--against /Users/noah/XPTerrainBuilderData/.harness/frames/legll1/legll1E1.drawn.json`:
PASS at both sites, nothing MOVED. (The control has 23 object-layer FAILs
of 94 claimed sites elsewhere at EGLL; round 1 had the same 23 plus the
three at the south mouth. The gate is judged at the sites and against the
control, as the drawn-gate rule says.) In the gate's JSON:
- `mouth tunnel:-11670+-11669@0`: floor 17.30, bottom − floor within 0.3
  (round 1: +2.67).
- every `tunnel_ramp` site in the south site: PASS, relief > 0; the ramp's
  top ≥ 23.0.

And four reads of the drawn mesh with `tools/drawn_site.py --site` (the
site header prints the drawn mesh at its centre):

| Probe | Point | Bar | Round 1 patch there |
|---|---|---|---|
| south floor, 10 m out | 51.474002, -0.452953 | 18.05 ± 0.3 | 23.73 (the pad) |
| south floor, 44 m out | 51.473696, -0.452960 | 20.6 ± 0.5 | 23.75 (pad `building48`) |
| north road, 3 m outside | 51.479800, -0.452990 | 16.6 ± 0.5 | about 19.7 (road cells, interpolated) |
| north cover, 3 m inside | 51.479740, -0.452990 | ≥ 24.5 | not in the patch (lidar 24.9) |

The north pair is the portal face: at least 7.5 m in 7 m.

Expected residual, to quote at closing: the south walls' coping will stand
about 1.4 m over the terminal pad (23.73); the author drew it 0.8 m over
his ground. The 0.65 m is the pad standing lower than the lidar at the
object's anchor (24.38). It is inside the 0.5 m ground bar only loosely;
report the drawn figure.

## 5. Harness and process

- **Blocker:** `build_airport.py` returns rc=1 at the inset
  `complete.json` write guard (both legll1 and legll2 closing builds).
  Lane `lkdenclose` is fixing it. Round 2 rebases onto that fix before its
  closing build. If the fix has not landed, the lane says so, builds, and
  runs `tools/harness/drawn_gate.py EGLL --tag T --out DIR ...` on the
  products as round 1 did; it does not write a private wrapper.
- `tools/blast.py` on each edited file; ratchets may not rise; no ICAO,
  pack or resource literal in code (`test_no_airport_specific_code`).
- Never raise the lane cap; delete the scratch build and pack copy when
  reporting; `df -h` ≥ 30 GB before the tile build.
- RULINGS: the master records N1 (the narrowing of 2026-10-28k) and S1–S4
  under the key it assigns, and corrects 2026-11-13h's last clause ("the
  north mouth is decided by the credible survey"): after this round the
  survey decides its depth, not whether it is drawn.

## 6. Owner questions (yes / no)

**Q1.** Where the lidar already shows a tunnel road deep enough, we will
now draw the portal face and short walls at the surveyed depth, with no
extra digging — at every airport, not only the EGLL north mouth. Yes
(recommended)? No means: only for roads that pass under runway, taxiway or
apron pavement.

**Q2.** At the EGLL south portal the pack's walls reach 2.5 m below the
road the lidar shows (wall feet 17.30 m, surveyed road 19.8 m). We will
cut the ramp to the wall feet, so the portal openings stand 4.9 m tall and
the ramp follows the walls at 7.5 %. Yes (recommended; it is the
2026-11-06 "cut to the wall depth" rule)? No means: keep the surveyed road
and leave the lower half of the openings buried.

The spec's default is Yes / Yes, the reading the standing rulings give.
The master decides whether the lane waits for the answers.

## 7. Not verified by this review

- The drawn tile mesh and the written body file of round 1 (the lane's
  scratch build was deleted): the drawn figures marked *(lane)* come from
  `legll2E1.drawn.json` and the lane's report.
- Which pack parts mint `building48`.
- That `mouth_at_pavement` leaves the north mouth on its mapped end once
  N1 lets the group through (bar R1 tests it).
- The corpus effect of N1, S1 and S4 beyond EGLL (bar R3 measures it).
- The full planar replay runs without the pack partition
  (`planar/__main__.py:147`); pad names differ from the build's
  (`building6` there, `building31` in the build), the ownership finding is
  the same in both.
