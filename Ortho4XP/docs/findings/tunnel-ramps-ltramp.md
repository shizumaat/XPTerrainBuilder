# Tunnel ramps: #742 (KDEN), #807 (KCLT), #1280 (LFPG) — lane `ltramp`

Base: origin/main 59fa7241d (2026-10-26). Instrument: the dry structure replay
(`tools/bore_table.py run ICAO`, i.e. `python -m auto_patch_v2.planar ICAO --stage
structures`) on each airport, read with lane scratch scripts against the registered
captures (`frames/m5/KDEN.pkl`, `frames/m4/KCLT.pkl`, `frames/llfpg2/LFPG.pkl`) for
the OSM ways and the DEM.

## Attribution (site numbers first)

### #742 KDEN service road 39.8633093, -104.6577104 — MET on main, nothing to do

No tunnel, channel or ramp record within 600 m of the site. The only structure read
there is the refused `channel:0` (way -3675, 39.8566 → 39.8651): "the airport's
CREDIBLE lidar inset reads NO cut along the corridor — the road at grade between its
2 crossings" (§45 (21), #748). The second point of the issue (shapeID 1048 cliff,
39.865184, -104.65583) is not a tunnel ramp and is out of this lane's scope.

### #1280 LFPG 49.008056316, 2.557537871 — the floor ignores the lidar's own road

The ramp is `tunnel:-300@0` (bore -300, `secondary`, `layer=-1`, 59 m under the
taxiway berm). Its mapped portal stands 33 m south of the site; the mouth slid 20.5 m
north out of the pavement to 49.0079476, 2.5574706 and the ramp climbs 72 m north
through the intersection: floor 94.81 at the mouth, 7.4 m under the DEM there
(102.21).

The 1 m lidar (credible) reads the berm at 106.4–106.7 m and, through it, a 10 m wide
notch along the bore at 101.1–102.2 m — the survey's ground under the taxiway, i.e.
THE ROAD (lidar ground classification drops the structure over a road, as it drops a
bridge deck). The intersection at the site reads 102.2–102.6 m. The road therefore
runs from the intersection under the taxiway at grade, exactly as the owner says.
The engine takes the DEM at the mouth (the notch, 102.21 m) as the GROUND over the
mouth and cuts `mouth_depth_m` = 7.5 m (RULINGS 2026-10-14f) below it: 7.4 m below a
road the lidar already shows.

Census of every built mouth at the three airports (the first 40 m of each bore from
its mapped portal; "cut" = ground ≥ `[channel] object_min_depth_m` 3.0 m above the
lidar floor on BOTH sides within 30 m, the §45 `_lidar_cut` witness):

* LFPG: 13 of 61 built mouths read the cut at a majority of stations (most 10/10,
  rises 3.5–7.5 m) — `-300` (the owner's), `-294`, `-314`, `-317`, `-384`, `-412`,
  `-413`, `-3458`, `-10256`, `-1719`, `-10776`, `-28283` ×2, plus partial readings.
  In every one the approach ground stands within −1.8..+0.6 m of the lidar floor at the
  portal: the roads of the CDG terminal-2 network pass under the taxiway berms at
  grade, and each is dug 7.5 m below it today.
* KCLT: 1 of 8 (`tunnel:-30363…@0`, the #807 NORTH ramp, a 10 m underpass bore:
  1/2 stations, rises 3.0/2.8 m; lidar road 211.04 m, approach 212.1 m, built floor
  203.46 m — 7.6 m under the road the lidar reads under the taxiway bridge).
* KDEN: 0 of 18.

THE RULE (general; no airport named): **where a credible lidar inset reads the cut
along a bore — the §45 `_lidar_cut` witness read over the WHOLE bore, end to end, so
both mouths take one verdict — the survey carries the road through the cover at its
own level, and the mouth is refused by name: no ramp, no trench.** `mouth_depth_m`
under the ground stays the default wherever the survey does not show the road. (A
ramp floored at the lidar road would carve nothing: it meets the DEM at its first
station. The first form, read over each portal's first 30 m only, split KCLT's
underpass of way -31625 under taxiway bridge -71 — one mouth built, one refused — and
was replaced by the whole-bore reading.)

### #807 KCLT south ramp 35.201072847, -80.940416217 — one width for two diverging carriageways

`tunnel:-30363+-30362+-30359+-30361+-30360+-30358@1` is a dual (two `tertiary`
2-lane carriageways, -30356 / -30357, 3.5 m half each). `merge_duals` gives it ONE
width, the widest span over the ramp before the carriageways part. Measured stand-off
of the ramp edge beyond each carriageway's outer edge (rim − 1.6 m rim stand-off −
3.5 m half), from the mouth outward:

| from mouth | 4–20 m | 25–30 m | 35 m | 40 m | 45 m | 50 m |
|---|---|---|---|---|---|---|
| west (-30356) | +5.3..+5.5 | +5.0..+4.0 | +2.6 | +1.0 | −1.4 | −3.8 |
| east (-30357) | +5.4..+5.8 | +4.5..+3.7 | +2.6 | +1.2 | −0.7 | −2.9 |

Too wide by ~5.4 m a side at the mouth, and both carriageways leave the ramp in its
last 10 m where they spread to 25 m apart into the roundabout.

THE RULE: **a dual ramp's edges are its carriageways' outer edges station by
station** — per station, left/right half width = the farthest member carriageway's
lateral offset plus its own half width on that side, never less than the widest
member's own half (`planar/dual_width.dual_half_fn`) — instead of one constant width.
A pavement tracing the road (2026-09-06b (2)) stays senior where it reads; where the
per-station edges fold the ring at a bend, the one constant span stands (LFPG
`-27468…` / `-27470…`). And **a dual's own carriageways are its own road** (clause 4
of `structure_mouth.mouth_stops`, read against each member's approach as
`crossing_roads` already reads them): the mean axis runs between the carriageways,
along neither, so each carriageway's road cell was a STOP — it slid KCLT's south mouth
57 m out from its mapped portal and, with the narrower ramp, clipped its top.

### Shared reading

Both are one statement: **a ramp is shaped from its own road — the depth the survey
reads the road at, and the carriageways' own edges — and the law's defaults (7.5 m,
one constant width) apply only where the road states nothing.** #742's channel
refusal (§45 (21)) is the same witness read on an open channel.

## Measured (dry structure replay `tools/bore_table.py run`, base main 59fa7241d vs branch)

Site numbers first.

* **#1280 LFPG `tunnel:-300@0` (owner's site)**: built (floor 94.81, 72 m ramp north
  through the intersection) → REFUSED: "the credible lidar reads the road UNDER the
  cover … 101.65 m at the mapped portal". Its south mouth `-300@1` likewise (99.24 m).
  LFPG tunnels 63 → 50: 15 lidar-read mouths refused (-294, -300, -314, -317, -384,
  -412, -413, -3458, -10256, -10776, -1667, -1719…, -28283 ×2, -8478), 7 other bore
  ends now refused by the same witness instead of an overlap / bend / strip refusal;
  2 duals newly built (`-13770+-13769+-13768@0` at 49.0242428, 2.5356231 — the
  narrower ramp clears the runway strip keep-out; `-17946…@0`); 16 duals changed in
  rim only, three of them in top / mouth too (`-27468…` top 60 → 96 m, no longer
  clipped by its own carriageway; `-13212…` mouth 12 m nearer its portal; `-4530…`
  clip). No other record changed.
* **#807 KCLT south ramp** (`…@1`): constant 29.4 m → per-station; both carriageways
  (-30356 / -30357) inside the ramp at every station, outer stand-off +0.3..+1.2 m
  (was +5.3..+5.8 m at the mouth and −3.8 / −2.9 m in its last 10 m). The mouth now
  stands 6 m from its mapped portal (was 57 m out): 35.2013691, -80.9404155, floor
  203.34 (7.18 m), ramp 84 m south at 9.27 % (was 60 m at 8.60 %), unclipped. The
  owner's point 35.201072847, -80.940416217 now lies on the ramp, 33 m from its mouth.
  **#807 KCLT north ramp** (`…@0`): rim only; both carriageways (-30093 / -30094)
  inside at +0.5..+0.9 m past the mouth's first 9 m. KCLT tunnels 8 → 8, no lidar
  refusal (the whole-bore witness does not fire at KCLT).
* **#742 KDEN**: no structure within 600 m of the site in either arm; tunnels 18 → 18,
  three duals' rims only; channels identical.

## Closing build (KCLT, `build_airport.py KCLT --tag ltramp_KCLT`, branch 56c549ce5)

LFPG carries the #1280 site and exercises every clause, but its build refused on a
`--refresh-data dem` demand (FRANCE50CM / WALLONIA1M negatives re-asked per engine
version) and the refresh was not permitted from this lane; KCLT (#807's two sites,
both rules exercised, the lidar witness not firing) was built instead. rc 0,
status optimal, body ff7d64469360, patch created 1254.5 s; registered
`frames/ltramp/ltramp_KCLT.osm`. Census: CRITICAL motion 0; CRITICAL visual 868 (864
unmeshable). Rows within 60 m of the two ramps: south mouth `ramp_in_strip`
cross_connector|tunnel_ramp 5.65 / 3.40 m and `adjacent_ground_step`
graded_strip|service_road 1.65–1.84 m ×3 (the mouth now stands at the taxiway
bridge's south face, in its graded strip — 2026-10-20as: a tunnel cuts through the
graded strip and stops at the pavement edge), `road_cross_section` ≤ 0.27 m; north
mouth `ramp_in_strip` 2.25 m (position unchanged). No control was built at this base
(one build per lane), so these are not deltas.

## Owner question (non-blocking; the branch implements (a))

Q: Where the airport's lidar shows a road passing under a taxiway at the road's own
level (LFPG: 15 underpass mouths under the terminal-2 taxiway berms, the #1280 site
among them), should we (a) cut nothing there and leave the road where the survey has
it (recommended), or (b) keep cutting a 7.5 m-deep ramp under the ground over the
mouth (RULINGS 2026-10-14f) even below a road the survey shows?

## What the owner should look at in the sim

* LFPG, Terminal 2 roads under the taxiway berms (the owner's #1280 point, the
  intersection ~60 m north of the taxiway berm south of the T2 car parks): no ramp
  dug into the intersection; the road runs at grade into the slot under the taxiway.
  The same at the other T2 underpasses within ~300 m of it.
* LFPG, the new ramp at 49.0242428, 2.5356231 (north field, beside the runway strip):
  a dual road ramp now built where its wall used to stand in the strip.
* KCLT, the two underpass ramps under the taxiway bridge (#807 points): each ramp's
  edges sit about a metre outside its two carriageways the whole way, the south one
  now starting at the bridge's south face and running ~84 m toward the roundabout.
