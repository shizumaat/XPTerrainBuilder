# Drawn-gate object classes: member feet, the level floor, and the rigid frame (spec after the round-1 miss)

Issues: #1903 (drawn gate, objects layer), #1918 (LGAV hidden shell), #1902.
Status: SPEC ONLY (one-miss review, RULINGS 2026-11-11c). No engine code was
written. A fresh Opus lane implements it; this spec's author never does.
Round reviewed: claude/lobjgate1 `c4dcf4234` (capture at `a8f6f4897`, closing
build at `4528cdf96`; its one engine commit `ea92f5e77` was reverted by
`7f79caced`; nothing landed).
Base for round 2: origin/claude/beta8-batch15 `daf5cb06f` or later.
Law: RULINGS 2026-11-06d (1) (4) (5) (6), 2026-11-06b (1), 2026-11-07b (1),
2026-11-13g (the drawn gate is the lane bar), 2026-11-13i ("we don't want any
visible edge to be floating"), 2026-10-15 visibility bars (pavement 0.05 m,
ground 0.5 m), 2026-10-05e (no airport-specific code), 2026-08-30l (consumer
census).
Paths are under `Ortho4XP/src/auto_patch_v2/` unless they say otherwise.

## 0. Summary

Round 1 named six classes (A-F) and tried two fixes. Both read worse on the
drawn products and were reverted. This review re-measured every class on the
products themselves (the pack OBJ files, the written and pristine pack DSF,
the lobjgate1 closing patch, the owner's 1.0.501 patch). Four findings change
the plan:

1. **C/D are an instrument error, not an engine defect.** The four rows
   -0.03 ... -0.37 are WALL FEET (vertical faces only, no floor plate within
   20 m of the site) standing 0-0.37 m under the channel floor: buried, not
   visible. `drawn_check.read_claims` gives every member of an object-floor
   frame the floor record's 0.3 m clearance, so it expects each wall to hang
   0.3 m over the cut. No visible frame member at LGAV has a floor plate
   there. The bar changes; the engine does not need "per-member floors" for
   those rows.
2. **A is one case of a corridor-wide class.** On the lobjgate1 closing patch
   63 of 564 sampled member feet stand more than 0.3 m over the patch surface
   under them. Five mechanisms (§2.2): three in `planar/channel_depth.py`
   are fixed here (M1-M3), one is a choice of statistic (M5, question Q2),
   one is class B (M4).
3. **B is the real LGAV problem and needs the owner.** The pack's trench
   frame is one rigid, FLAT 3 km set (rim 77.5-79 everywhere). Our ground
   falls toward the south-west: along the south-west 1.4 km the frame's rim
   stands 4-10 m over the DEM and the solved ground beside it (69-72 m) is at
   the trench FLOOR's level (69.7). No change to the channel can make a flat
   3 km frame fit ground that falls 8 m. This round closes the gaps under the
   members' feet; whether the frame may follow the ground is question Q1.
4. **F regresses on batch 15 as it stands.** In 1.0.501 the garage's level
   floor was cut as a sunken road, and that cut is what kept a 1.2 m lidar
   mound out of the floor (drawn mesh 26.68 = floor 26.68). lobjgate2's rule
   (on batch 15) refuses every level plate, so the mound returns. The garage
   has no building pad in 1.0.501. The fix keeps the cut for a level floor
   under a mound and names it a level floor.

Four parts: P0 the gate reads each member against the ground under its own
foot, and predicts on a patch (§3); P1 the hidden-shell channel takes the
members' feet per side (§4); P2 the level floor under a mound (§5); P3 the
frame misfit is measured and published, no behaviour (§6). Owner questions in
§9.

## 1. What was read, and what could not be

Read: round 1's commits and its scratch folder
`.claude/worktrees/lobjgate1/Ortho4XP/tmp/lobjgate1/` (drawn-check reports,
logs, scripts; it holds no notes file); frames `lobjgate1/LGAV.pkl` (not
loaded: 454 MB) and `lobjgate1/LGAV_auto.patch.osm` + sidecar; the owner's
1.0.501 patches under `/Users/noah/XPTerrainBuilderData/Patches`; the two
packs' OBJ and DSF files.

NOT VERIFIED (each is used below only where marked):
- Round 1's lane report is not on disk. "A per-side cut reading made it
  worse (2.82 -> 3.78)" has no artefact; §2.3 gives my reading of why.
- "Refusing the claim left the DEM rising 1.18 m into the floor" (KIAH): the
  replay patches were deleted. The inset DEM agrees (27.5-27.9 against a
  floor at 26.68, §2.5). It needs one replay to confirm on batch 15.
- Why the KIAH garage has no building pad (pad gate, or no building
  evidence) was not determined; P2 does not depend on it.
- That the patches and packs installed under the owner's folders are the
  1.0.501 build is round 1's statement (its `*_owner.json`, its commit
  message); "1.0.501" below means those installed products.
- #2051 was not read. No build and no replay was run for this spec.
- The feet census of §2.2 is a proxy written for this review (scratch, not
  in the repo): `visible_cut._dense` at 2.5 m over six frame members, feet
  under 75.0 m, one per member per side per 10 m station, read against
  `patch_faces.PatchFaces`. The lane re-baselines with the tool of §3.4.

## 2. Mechanisms, measured

### 2.1 The frame (classes A and B)

Pristine pack DSF, tile +37+023: `Trench/Trench_00 ... 08.obj`,
`Trench_veg`, `train_powercable`, `Bridge_Fences-Fence2` are rows 608-618,
all plain `OBJECT` at ONE anchor 37.935378, 23.940777, heading 0. The
written DSF (owner 1.0.501) holds them as `OBJECT_MSL` 77.6875; `Trench_06`
(the shell) is dropped; `Trench_00` is split into three bodies. The sidecar's
frame zero is 77.717 (`object_floors[].zero_m`). The DEM at the anchor is
77.70 and no patch face covers the anchor: the zero of a 3 km frame is one
sample of a 30 m DEM (`airport/below_grade_witness.py:55` `zero_of`,
`airport/object_floor.py:605` `_concave`, `:636` `seat_records`).

Along `channel:0`'s axis (s = metres from the first point of the published
`floor_profile`, stations 10 m apart; shell = `Trench_06` placed at 77.717;
DEM = the build's `LGAV_copernicusglo30.tif` inset):

| s (m) | channel floor | shell rim L / R | shell floor | DEM at -60 / 0 / +60 | rim - DEM L / R |
|---|---|---|---|---|---|
| 120 | 70.76 | 78.1 / 77.6 | 70.8 | 68.3 / 64.7 / 68.6 | +9.8 / +9.0 |
| 240 | 69.63 | 78.1 / 77.6 | 69.7 | 70.5 / 65.3 / 71.1 | +7.6 / +6.5 |
| 720 | 69.78 | 78.2 / 77.7 | 69.8 | 70.9 / 65.6 / 67.8 | +7.3 / +9.9 |
| 1200 | 69.95 | 78.5 / 78.0 | 70.0 | 71.8 / 65.2 / 67.8 | +6.7 / +10.3 |
| 1440 | 67.46 | 78.3 / 77.7 | 66.2 | 74.1 / 67.7 / 72.8 | +4.2 / +5.0 |
| 1800 | 69.67 | 78.5 / 77.8 | 69.6 | 77.5 / 73.7 / 76.5 | +0.9 / +1.4 |
| 2160 | 69.82 | 78.0 / 77.7 | 70.0 | 78.9 / 76.6 / 78.6 | -0.9 / -1.0 |
| 2760 | 69.88 | 77.7 / 78.9 | 69.9 | 77.8 / 76.5 / 79.3 | -0.1 / -0.4 |

North-east of s = 1500 m the frame's rim is at the ground (within 1.6 m).
South-west of it the rim stands 4-10 m over the DEM, and the channel floor
stands 2-6 m OVER the DEM on the axis: there the "cut" is a fill. The
lobjgate1 patch beside the corridor at s = 120-480 m reads service roads and
pads at 68.2-72.3 m, 50-90 m off the axis, against the floor at 69.7.

The site of class A (37.921672, 23.93079; s = 240 m, 36.5 m left of the
axis). Cross-section at that station, metres from the axis:

| | -45 | -40 | -35 | -30 ... +35 | +40 | +45 |
|---|---|---|---|---|---|---|
| shell `Trench_06` | 77.4 | 75.5 | 73.8 | 69.7 | 74.4 | 77.5 |
| lobjgate1 patch | - | 69.0 (void band) | 69.7 (floor) | 69.7 (floor) | 69.1 (void band) | - |

`Trench_07`'s lowest vertex there is 72.49 at -33.5 m: it is the liner of the
UPPER bank, standing on the hidden shell's lower bank (69.7 at -30 to 72.5
at -33.5). With the shell hidden nothing draws that lower bank, the channel's
floor (69.63) runs under the liner's lower edge to -35 m, and the void band
beyond it FALLS to a crest of 68.4-69.1, because the crest is the solved
ground and the solved ground there is below the floor.

### 2.2 The feet census (class A, corridor-wide)

Proxy of §1, lobjgate1 closing patch: 564 station/side feet of `Trench_01,
02, 03, 04, 07, 08`. `floor` = a foot within 1.0 m of the channel floor at
its station, `ledge` = more than 1.0 m over it. 63 stand more than 0.3 m over
the patch surface under them (half: SW = the first 1.5 km of the profile):

| member, half, class | feet | float > 0.3 m | p95 / worst gap |
|---|---|---|---|
| `Trench_07` SW floor | 147 | 30 | +2.54 / +3.50 |
| `Trench_07` SW ledge | 7 | 6 | +5.83 / +6.36 |
| `Trench_07` NE floor | 32 | 8 | +0.65 / +0.72 |
| `Trench_07` NE ledge | 5 | 5 | +1.13 / +1.13 |
| `Trench_08` SW floor | 45 | 3 | +0.51 / +0.93 |
| `Trench_08` SW ledge | 4 | 4 | +3.96 / +4.10 |
| `Trench_08` NE floor | 159 | 0 | +0.03 / +0.16 |
| `Trench_03` SW floor | 47 | 3 | +0.30 / +3.41 |
| `Trench_03` SW ledge | 3 | 3 | +7.46 / +7.46 |
| `Trench_01` NE floor | 10 | 1 | +0.21 / +0.57 |
| every other group | 105 | 0 | buried or flush |

Five mechanisms, each with its witness rows from that census (station k of
the profile, side, member, foot, offset from the axis, patch under the foot):

M1, A LEDGE FOOT INSIDE THE FLOOR. k 52, left, `Trench_08` foot 74.52 at
-41.5 m over `tunnel_trench` 70.43: +4.10 (37.923724, 23.932829); k 53,
+3.20; the class-A site itself. `channel_depth.cut_points`
(`planar/channel_depth.py:54`) keeps the UNSIGNED offset
(`shapely.distance`), so `cut_halves` (`:95`) takes one half width for both
sides: the farthest foot standing on the floor on EITHER side. At the class-A
site the right wall's foot (69.5 at +35 m) sets 35 m; the left floor then
runs under the left liner's foot at -33.5 m.

M2, A FLOOR FOOT OVER THE FALLING VOID BAND. k 77-80, right, `Trench_07` foot
69.96-70.07 at +35.3 ... +35.5 m over `structure_rim` 66.91-66.93: +3.05 ...
+3.14 (37.925894 ... 37.926106, 23.933804 ... 23.934004). The floor's edge is
exactly the farthest floor foot, then averaged (`_smooth`, `:118`), so the
foot lies over the void band, and the band falls wherever the solved crest
is below the floor.

M3, THE FLOOR HIJACKED BY LEDGES. k 102 (37.927317, 23.936273): the channel
floor reads 72.56 (the sidecar's `floor_declared_max_m`) where the shell's
floor is 69.9-70.2 either side. `cut_profile` (`:84`) is the median of ALL
feet at a station; where ledge members outnumber floor members it is a ledge
level.

M4, THE SOUTH-WEST END. k 2-5: `Trench_03` foot 74.99 over 67.54: +7.46;
`Trench_07` 74.76 / 74.07 / 73.51: +6.36 / +4.59 / +3.18. `rejoin` (`:187`)
clamps the floor to the DEM (65.0) within ramp reach of the end, where the
pack's floor ramps UP to its flat-world grade (the shell reads 75.9 on the
axis at the first station). This is class B, not a channel defect.

M5, FLOOR FEET OVER THE MEDIAN. The NE `Trench_07` rows (8 of 32, worst
+0.72). A second proxy over nine members (a foot within 1.0 m of the SHELL's
floor level at its station; 642 feet): against the station MEDIAN 29 float
more than 0.3 m (worst 1.42); against the station MAXIMUM none float, 54 are
buried more than 0.5 m (16 more than 1.0 m, worst 1.45).

### 2.3 Why round 1's per-side reading read worse (inference, see §1)

Moving the left floor edge in (to the shell's floor edge, -30 m) without
moving the crest leaves the void band running from the floor edge to the same
low crest: the band's surface under the liner's foot drops below the floor
level it had before. A per-side floor edge is necessary (M1) but only works
together with a crest held at the member's foot (§4.4).

### 2.4 Classes C and D

`drawn_check.read_claims` (`tools/drawn_check.py:244`) reads
`object_floors[].clearance_m` into `clear[r["id"]]` and gives it to every
object of the record (`:258-260`, `:273-274`). At LGAV the three records
(`Trench_01@shell`, `Trench_02@shell`, `Trench_06@shell`, each listing all 11
frame rows, `area_m2` 0 / 0 / 520,625) make every frame member a CUT claim
with clearance 0.3; `check_site` (`:339`) then requires
|bottom - way floor - 0.3| <= 0.3. Measured at the four sites (faces within
20 m): `Trench_02` lowest 69.33, 8 faces touch it, all vertical; `Trench_01`
65.22 / 65.14, vertical; `Trench_08` 69.43, vertical; no near-horizontal face
within 4 m of the floor in any of them. RULINGS 2026-11-06d (4): "If there's
no floor then just to the wall depth is good." A wall has no clearance; a
wall foot 0.37 m under the ground is under the ground bar.

The 0.3 m clearance is honoured where a floor OWNS ground
(`constraints/object_floor.py:43`). A hidden shell owns none
(`object_floor.py:192`), and no visible member here carries a floor plate, so
2026-11-06d (4) asks nothing of this channel. If a later pack has a visible
FLOORED member in a hidden shell's frame, the gate of §3 fails it (the
`floor` bar), which is the witness an engine rule needs. None is written now.

### 2.5 Class F (KIAH, 29.969644, -95.332167)

`KIAH_ParkingGarage1.obj`: one row (pristine 23656, written 20927), plain
`OBJECT`, 267 x 334 m, y -3.30 ... 14.71, levels at y = -2.8, -0.5, 0.0,
0.3. Owner 1.0.501 sidecar: `tunnel_objects[]`
`sunken-road:KIAH_ParkingGarage1.obj@0`, kind `sunken_road`, floor 26.678,
crest 26.514, depth -0.163, length 248.7, width 120.4, design grade 0.0004,
profile flat at 26.678. Owner drawn check: site `tunnel_ramp -10657`, floor
26.68, drawn mesh 26.68, FAIL on "bottom-floor -3.54" (the garage's
foundation skirt, y -3.3) and "ramp relief +0.00".

The owner's patch over the garage footprint (7 x 7 samples): 33 uncovered
(DEM), 15 `tunnel_ramp`, 1 `groundside_pavement`, no building pad. The inset
DEM (`KIAH_usgs3dep.tif`) is 26.5-26.7 round the plate and 27.5-27.9 over
about 60 x 100 m inside it.

On batch 15, `sunken_roads.read_family` refuses a plate whose own floor falls
less than `min_descent_m` (`airport/sunken_roads.py`, the block "THE PLATE
descends", lobjgate2 `6536c57a0`). The garage plate falls 0.00 m, so it is
refused, nothing owns that ground, and the mound stands 0.8-1.2 m through the
floor. Round 1's reverted `ea92f5e77` was the same refusal with a narrower
test; its replay read +1.18 m (not re-verified).

The plate's depth under the ground at its two ends is -0.29 and -0.16 m
(round 1's commit message for `ea92f5e77`, and `depth_m` -0.163 in the
1.0.501 record), 1.16 m at its deepest.

lobjgate2's case (KLAX TBIT) is a level storey on a SLOPE: one end at grade,
the other 3.6 m under the uphill ground; the split-level reader owns it. The
garage is a level floor under a MOUND: both ends at grade, the middle under.
That is the witness that separates them (§5).

## 3. P0: the gate reads members, and predicts

### 3.1 Sidecar (publication)

`pipeline/publication.py:1403` `object_floors`: each record adds
`"object": f.object_id`, `"owns_ground": owns_ground(f)`,
`"hidden": bool(f.hidden)`. `:1317` `channel_facilities` adds
`"member_feet"` and `"ledge_pins"` (§4.6). `:1277` `tunnel_objects` adds
`"level_floor": true` on a record of §5.

### 3.2 `tools/drawn_check.py`

- `read_claims` (`:244`): for an `object_floors` record the claim kind is
  `object_floor` only for `record["object"]` when `owns_ground` is true (it
  alone carries `clearance_m`); every other listed object is
  `frame_member`, clearance 0. A record without the new keys (an old
  sidecar) reads as today.
- `Drawn.feet_near(lon, lat, radius_m)` beside `bottoms_near` (`:319`):
  `{row: (bottom, gap)}`, `gap` = the median of (z - drawn mesh at the
  vertex's own position) over the row's vertices within `radius_m` standing
  within `drawn_site_bars.FOOT_BAND_M` of its lowest one there. No second
  placement code: it reads `Drawn.vertices`.
- `check_site` (`:339`): a `frame_member` takes the FOOT bar:
  `gap <= tol` (no member foot floats); `gap < -GROUND_BAR_M` is listed
  `BURIED`, not failed (a skirt). An `object_floor` keeps today's bar. A site
  whose only claims are frame members is role `CUT` with `delta` = its worst
  gap. A `tunnel_object` with `level_floor` takes the FLOOR bar of §5.3 and
  neither the relief bar nor the bottom-floor bar.
- `check_feet(rec, drawn, tol)`: one `FEET <channel id>` row per channel
  record carrying `member_feet`: each foot's drawn z is the WRITTEN row's
  zero (the row's own `OBJECT_MSL` elevation, or the mesh under its anchor)
  plus the published authored y; against the mesh at the foot. FAIL when any
  `floor` or `ledge` foot floats more than `tol`; `end` and `unmet` feet and
  feet buried more than the ground bar are counted and listed, not failed.
- `run_predict` (`:1020`): with `--predict PATCH --plan PLAN` it also runs
  `read_sites`, `read_claims`, `check_site` and `check_feet` over
  `PatchAtlas(PATCH)`; `--site NAME=LAT,LON[,R]` (repeatable,
  `drawn_gate.parse_site`) limits the sites. Without `--plan` only the stack
  rows run, as today. `PLAN` is `v2_rebake_replay.py plan --write-pack COPY
  --plan-out PLAN` (the existing route of the stack rows).

### 3.3 `tools/patch_faces.py`

`PatchAtlas(patch_path, cell_m=300.0)`: `elevation_at_or_none(lat, lon)`
over the whole patch, building one `PatchFaces` per 300 m cell on first use
(centre = the cell's centre, radius = half its diagonal plus the stand-off).
A row's anchor can lie 1.6 km from its site (§2.1); one fixed-radius
`PatchFaces` does not reach it.

### 3.4 Harness and index

`tools/harness/drawn_gate.py` `_objects` (`:269`) is unchanged; the new rows
arrive in `rep["sites"]` and `judge` (`:340`) filters them by `--site`.
`tools/INDEX.md` rows of `drawn_check.py` and `patch_faces.py` are updated in
the same commit (the predict of CUT sites, `PatchAtlas`).

## 4. P1: the hidden-shell channel takes the members' feet per side

The rule, in law terms: under a hidden shell the cut is stated by the
visible members lying on it (2026-11-06d (6)). Each such member's FOOT is
where the ground meets it. The ground never stands under a foot by more than
the gate's tolerance; a foot under the ground is a buried skirt. The hidden
shell stays a witness of extent and of which member lies where
(2026-11-06d (1)), never of depth.

Scope: only a channel whose floor comes from a visible cut
(`witness_name == "visible cut"`, `planar/channel.py:768`). Every other
channel, every basin and every object floor is byte-identical.

### 4.1 `airport/visible_cut.py`

`VisibleCut` gains `extent`: `(m, 3)` points (step = `[channel] station_m`
/ 4, as `points`) on the hidden shell's own near-horizontal faces (normal y
>= `tunnel.object.plate_normal_y_min`) standing `channel.object_min_depth_m`
or more under its rim: where the shell's floor plates lie. And `members`:
for each member index of `points`, its `(placement id, authored zero)`.

### 4.2 `planar/channel_depth.py`

- `cut_points` (`:54`): the offset is SIGNED, positive on the axis's left
  (the sense of `channel_geometry._sides`, `:241`); `extent` goes through the
  same projection (`cut_extent`).
- `shell_floor(extent, ss, step)`: per station the MEDIAN z of the extent
  points within half a station (the 60 m floor outweighs a ledge's plate);
  NaN where none.
- `cut_feet` (`:69`): one foot per member PER SIDE per station.
- `classify(feet, shell_floor, flat)`: per station each foot is `floor`
  (within `shell_flat_m` of the shell's floor level there), `ledge` (over
  it) or `below` (under it: buried, states nothing). A station with no
  shell floor level classifies against the lowest foot (today's reading).
- `cut_profile` (`:84`): over the `floor` feet only; the station value is
  their MAXIMUM (Q2; the median with a "no" to Q2). Stations without a floor
  foot interpolate, as today.
- `cut_halves` (`:95`): per SIDE. Floor edge = the farthest `floor` foot of
  that side plus `[channel] foot_margin_m` (new, 1.0), or the farthest
  extent point of that side within `shell_flat_m` of the profile, whichever
  is farther; never under the road's own half (`floor_half`); enveloped
  (maximum filter over `corridor_min_length_m`), no averaging below the
  envelope; and never nearer than the wall band
  (`wall_gap_m + wall_band_width_m`) to that side's innermost ledge foot.
  Crest line = that side's innermost `ledge` foot where the station has one,
  else today's farthest below-grade member point.
- `ledge_pins(...)`: `(x, y, z)` of each station/side ledge foot the crest
  line runs through.
- `member_feet(...)`: one record per member/side/station:
  `(x, y, authored y, placement id, kind)`, kind `floor`, `ledge`, `end` (a
  floor or ledge foot at a station `rejoin` moved) or `unmet` (a ledge foot
  beyond the innermost one, or a `below` foot).
- `visible_floor(cuts, axis_ln, axis_fn, ss, ...)`: the one entry
  `planar/channel.py` calls; it returns the profile, the two edge lists, the
  two crest lists, the pins and the feet. `planar/channel.py` is 996 lines:
  its three visible-cut blocks (`:645-651`, `:677-681`, `:766-773`) become
  calls of this function; the file must not grow.
- `rejoin` (`:187`) is unchanged (M4 is class B, Q1).

### 4.3 `model/structures.py` (`Channel`, `:560`)

New fields, default `()`: `ledge_pins`, `member_feet`. `widths` stays one
half per station (the larger side: `half_width`, `:647`, has one reader,
`planar/__main__.py:509`). `region` and `crest_ring` are built from the
per-side lines (`_sides` is called once per side list).

### 4.4 `constraints/channel.py` (`channels`, `:76`)

In the crest loop (`:136-146`): a crest vertex within
`emit.identity.min_distinct_spacing_m` of a ledge pin takes
`Pin(v, z_ledge)` in place of the two `Offset` rows, unless a governed cell
shares it (`_shared_with_ground`, `:156`: one node, one value: the cell
governs, and the foot is published `unmet`). Source ruling: 2026-11-06d (6)
with 2026-11-13i. The floor rows are unchanged: the floor stays a function
of the station alone, which is what `channel_floor_at_declaration` judges at
0.01 m.

### 4.5 Emittable in a heightfield

At every (x, y) exactly one of floor / void band / outside: the band is the
crest ring less the floor (`planar/channel_claims.py:311` `channel_cells`),
and the crest ring is still outside the floor by at least the wall band. A
ledge pin is a value on the band's outer ring, the shape
`constraints/object_floor._rim_pins` (`:92`) already emits. Its own warning
applies: a rim vertex only the band carries was drawn 1-4.3 m off before
#2034; batch 15 holds the #2034 fix (`a82176f7c`), and the gate's
patch -> drawn layer is the bar that catches a relapse (§8).

### 4.6 Publication and the census

`pipeline/publication.py:1317`: `"ledge_pins": [[lat, lon, z], ...]`,
`"member_feet": [[lat, lon, y_m, "dsf:objN", kind], ...]`.
`verify/channel.py:161` `channel_crest_at_edge` and
`tools/check_grade.py:7399` `_check_channel_crest_at_edge`: a crest vertex
with a declared ledge pin within the identity spacing is judged against the
pin (+- 0.01 m), not against the adjacent cell. `LAW_FAMILIES` does not
change (no new family).

## 5. P2: a level floor under a mound keeps its cut

### 5.1 The rule

A roofed, LEVEL floor plate (it falls less than `min_descent_m`) with BOTH
ends within `basin.contact_band_m` of the ground, under ground that stands
over it inside (the existing tests: deepest minus shallow >=
`min_descent_m`, shallow end within the contact band, roof share >=
`roof_min_fraction`) is a floor the ground breaks through. The ground is cut
to the plate over the plate, as a sunken road's is. A level plate with one
end deep stays lobjgate2's refusal (a storey on a slope: the split-level
reader's). No new threshold.

### 5.2 Code

`airport/sunken_roads.py` `read_family`: in lobjgate2's block (the
`fall < sr.min_descent_m` refusal) the refusal is skipped when
`max(d_first, d_last) <= bl.contact_band_m`; the record continues down the
existing path and is built exactly as 1.0.501 built it.
`SunkenRoadRecord` (`:85`) gains `level: bool = False`, set there, with a
note "LEVEL FLOOR under a mound: both ends at grade". Its `source` stays
`"sunken_road"`, so its seven readers (§7) behave as in 1.0.501.
`pipeline/publication.py:1277` publishes `"level_floor": true`.

### 5.3 The FLOOR bar (`drawn_check.check_site`)

For a `level_floor` record: the plate's drawn z is the written row's zero
plus `plate_y_m`; sampled along `axis_ll` every 10 m and at 0, +-1/4, +-1/2
of `width_m`. FAIL when the drawn mesh stands more than `tol` (0.3) over the
plate anywhere (ground through the floor), or the plate's median height over
the mesh exceeds the ground bar (0.5: the floor floats). The object's skirt
is not read; no relief bar.

## 6. P3: the frame misfit is measured and published

`airport/object_floor.py` `_rim_at_ground` (`:394`) already reads the shell's
rim against the ground along its outline for the hide decision and returns
only the share at the ground. It is extended to return the differences it
took as well, and they are published: `object_floors[]` gains `"rim_misfit_m": {"p05", "p50", "p95"}`
and `"rim_off_share"` (the share of the outline where |rim - ground| exceeds
`shell_rim_ground_m`). `drawn_check` prints one `FRAME <id>` row from it,
never failed. LGAV today (proxy, §2.1): about +7 ... +10 m along the
south-west 1.4 km. No engine behaviour reads it in this round.

## 7. Consumer census (RULINGS 2026-08-30l)

One table; a reader not listed was searched for and not found
(`grep` of `cut_points|cut_feet|cut_profile|cut_halves|visible_cuts`,
`crest_ring`, `\.region`, `floor_z(`, `half_width(`, `"sunken_road"`,
`object_floors`, `clearance`).

| reader | file:line | reads | this spec |
|---|---|---|---|
| visible cut reader | `airport/visible_cut.py:63` | hidden shell, members | adds `extent`, `members`; `points` unchanged |
| visible cuts producer | `planar/object_floor_cells.py:200` | `visible_cuts` | unchanged call |
| channel builder | `planar/channel.py:645-651, 677-681, 766-773` | points, feet, profile, halves | one call of `visible_floor`; per-side lines |
| floor datum | `planar/channel_floor.py:31` (`visible=`) | the profile | unchanged; receives the new profile |
| `rejoin` | `planar/channel_depth.py:187` | profile ends | unchanged |
| axis run-on | `planar/channel_depth.py:137` `extend_axis` | `points`, `bound` | unchanged |
| channel cells / knives | `planar/channel_claims.py:311, 352` | `region`, `crest_ring`, `wall_band_m` | unchanged code; rings now per side |
| object gates "inside a corridor" | `planar/channel_claims.py:179, 215, 258, 287` | `region` / `crest_ring` | unchanged; a ledge side's ring is narrower: the ground between the ledge line and the old crest returns to the zone laws (intended) |
| flat-site region | `constraints/flat_site.py:78` | `crest_ring or region` | unchanged |
| floor pins | `constraints/channel.py:122-133` | `floor_z(s)` | unchanged |
| crest rows | `constraints/channel.py:136-146` | void band's outer ring | ledge `Pin` (§4.4) |
| object-floor pins | `constraints/object_floor.py:43` | floors owning ground | untouched (a hidden shell owns none) |
| verify floor | `verify/channel.py:80-110` | `floor_profile` | unchanged |
| verify crest | `verify/channel.py:161` | crest vertices | reads `ledge_pins` |
| census floor / crest | `tools/check_grade.py:7367, 7399` | sidecar record | crest reads `ledge_pins` |
| publication | `pipeline/publication.py:1317, 1403, 1277` | records | new keys (§3.1) |
| planar report | `planar/__main__.py:501-509` | walls, `half_width` | unchanged |
| stage keys | `pipeline/stage_code.py:460, 2000, 2150` | module lists | no new module; if the lane adds one it registers it here |
| sunken-road readers | `constraints/structures.py:364, 618`; `planar/door_ramps.py:205`; `planar/structures.py:395`; `planar/viaduct_road.py:58`; `pipeline/planar_report.py:165`; `pipeline/rebake_inputs.py:325` | `source == "sunken_road"` | unchanged: a level floor keeps the source |
| split-level reader | `airport/split_level.py` | its own walls | untouched; a level plate with one end deep is still refused to it |
| gate claims | `tools/drawn_check.py:244, 339`; `tools/harness/drawn_gate.py:269, 340` | sidecar claims | §3.2 |
| per-site instrument | `tools/drawn_site.py`, `drawn_site_bars.py` | products only | untouched; `FOOT_BAND_M` and the ground bar are imported from it, not copied |

## 8. Twins and bars

Twins (synthetic, no corpus):
- `tests/auto_patch_v2/test_visible_cut1918.py` (extend): a shell with a
  60 m floor, a 1:1.25 lower bank on the left and a wall on the right; a
  ledge liner on the left bank; a ledge-only station. Asserts: signed sides;
  `classify`; the profile ignores ledges (the ledge-only station
  interpolates, no bump); left floor edge at the shell's floor edge and not
  under the ledge; right floor edge = wall foot + margin; crest left = the
  ledge line; one pin per ledge station at the foot's z; `member_feet`
  kinds.
- `tests/auto_patch_v2/test_v2channel.py` (extend): a planar map with a
  ledge pin: the crest vertex takes a `Pin`, a vertex a governed cell shares
  takes none; `channel_crest_at_edge` reads zero rows; a channel without a
  visible cut emits byte-identical rows.
- `tests/test_drawn_check.py` (extend): an old sidecar reads as today; a
  frame wall buried 0.37 m passes; a frame wall floating 2.86 m fails with
  its gap; the floor object that owns ground keeps the clearance bar; a
  `level_floor` record passes at mesh = plate and fails with the mesh 1.18 m
  over it, and takes no relief bar; `check_feet`; `--predict` with a
  synthetic patch gives the same rows as the drawn path on an identical
  surface; `PatchAtlas` equals `PatchFaces` inside one cell.
- `tests/auto_patch_v2/test_v2doorramp.py` (extend): a level plate under a
  mound with both ends at grade yields a record with `level`; lobjgate2's
  storey-on-a-slope twin stays refused.
- `tests/test_harness.py` stays green (no family added).

Replay first (no build): `tools/v2_solve_replay.py --replay
/Users/noah/XPTerrainBuilderData/.harness/frames/lobjgate1/LGAV.pkl --from
planar --emit DIR`, then `tools/v2_rebake_replay.py plan --write-pack COPY
--plan-out PLAN`, then `tools/drawn_check.py LGAV --predict PATCH --plan
PLAN --site ...`. Before any engine edit the lane runs the new `--predict`
on `frames/lobjgate1/LGAV_auto.patch.osm` and records the `FEET` baseline
(this review's proxy: 63 of 564).

Bars, LGAV (closing tile build, ONE: `tools/harness/build_airport.py LGAV
--tile 37 23 --pack-copy DIR`; sites by position, way ids change per build):

| # | bar | today | target |
|---|---|---|---|
| L1 | `A=37.921672,23.93079`: `Trench_07` foot gap | +2.86 FAIL | <= +0.30 |
| L2 | `37.926348,23.935242` (`Trench_02`), `37.931055,23.938699` and `37.931641,23.939222` (`Trench_01`), `37.940768,23.947941` (`Trench_08`): FOOT bar | 4 FAIL (-0.26, -0.03, -0.23, -0.37) | 4 PASS |
| L3 | `FEET channel:0`: `floor` + `ledge` feet floating > 0.3 m | lane's baseline | 0; `end` / `unmet` listed |
| L4 | the declared floor at 37.927317, 23.936273 (profile station 102) | 72.56 | within 0.5 m of the stations either side (69.9) |
| L5 | patch -> drawn layer against the control (frames `l2035/LGAV_auto.patch.osm`, 0 of 27,215) | - | no new site |
| L6 | census `channel_floor_at_declaration`, `channel_crest_at_edge` | control | no new row |
| L7 | predict = drawn: each of L1-L3 on the replay patch within 0.3 m of the same row on the built tile | - | holds, or the difference is reported per row |

Bars, KIAH. The +29-096 tile build is blocked by #2051 (another lane), so
this round closes KIAH on predict and names the build as owed:

| # | bar | today | target |
|---|---|---|---|
| K1 | `garage=29.969644,-95.332167,200`, FLOOR bar on the replay patch (`--capture KIAH` at the base, `--replay --from planar --emit`, `--predict`) | batch 15: mound through the floor (round 1 read +1.18, unverified); 1.0.501 drawn 0.00 with two wrong FAILs | mesh over the plate <= 0.30; no relief or skirt bar |
| K2 | the record | refused on batch 15 | `tunnel_objects[]` with `level_floor: true`, profile flat |
| K3 | KLAX control: frames `lobjgate2/KLAX_auto.patch.osm`'s refusal of the TBIT plate | refused | still refused (twin) |
| K4 | when #2051 lands: the drawn FLOOR bar on the +29-096 tile | - | owed to the master's batch build, not this lane |

Never raise the lane cap; delete scratch builds when you report.

## 9. Owner questions (yes / no)

Q1. LGAV's trench walls are one rigid 3 km set the pack drew for flat ground.
Our ground falls about 8 m toward the south-west end, so along the
south-west 1.4 km the walls' tops stand 4-10 m over the ground around them,
and the roads beside the trench are at the trench floor's level. This round
only closes the gaps under the walls' feet; the walls still stand tall there.
**May a trench frame whose shell we hide be cut into pieces that each sit at
the local ground, so the trench stays about 8 m deep along its whole length?**
Yes = a follow-up spec lifts "a trench frame is never split" for a hidden
shell's frame (2026-11-06d (1) already takes that shell out of the solve).
No = the set stays rigid and the south-west end stays as this round leaves it.

Q2. In one cross-section the walls' feet stand at slightly different levels
(LGAV: usually under 0.4 m apart, at worst 1.4 m). **Put the trench floor at
the highest wall foot, so no wall floats and the lower ones are buried by
that much?** Yes (recommended) = no visible gap under a wall; about 1 foot in
12 is buried more than 0.5 m. No = the middle level; about 1 foot in 20
floats 0.3-1.4 m.

Q3. KIAH garage: its level ground floor has a 1.2 m bump of terrain data
inside it. 1.0.501 flattened the ground to the floor there; batch 15 stops
doing so as a side effect of the KLAX fix. **Keep flattening the ground to a
building's level floor where both ends of the floor are at ground level and
the ground rises through it in between?** Yes = §5 (the 1.0.501 result, with
the right name and bars).

Q4. **Is a wall foot buried up to 0.5 m a pass on the drawn gate, with only
floating feet (over 0.3 m) and covered floors failing?** Yes = §3.2.

## 10. Risks, stated

- A ledge crest vertex a governed cell shares is not pinned (§4.4); the foot
  is published `unmet` and listed. L3 counts only `floor` and `ledge` feet;
  if many ledge feet come back `unmet` the lane reports the count and the
  cells that govern them instead of widening the pin.
- `shell_floor` is a median; a shell whose floor plates are a minority of
  its low horizontal faces would classify wrongly. The twin holds a ledge
  plate; the LGAV replay is the second check (profile against the shell
  floor: this review read p50 -0.04, p05 -0.29, p95 +0.59 for the median
  statistic).
- P2 restores a cut the gate once failed for the wrong reasons; whether the
  terrain coplanar with the plate flickers was not observed and is not
  measured by any bar here.
- If Q1 is "yes", §4 stays valid (the feet are read after the pieces are
  seated); M4 and the tall walls are the follow-up's.
