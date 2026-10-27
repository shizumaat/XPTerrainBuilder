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
along a bore — the §45 `_lidar_cut` witness over the bore's own first stations — the
lidar floor at the portal IS the road, and it is the mouth's floor; `mouth_depth_m`
under the ground is the default only where the survey does not show the road.** The
existing machinery then decides the ramp: a slid mouth whose road surfaces under the
pavement is refused (#1028 "the road reaches grade … before its mouth stands clear"),
an unslid one climbs from the lidar road at the design grade to the DEM.

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
member's own half — instead of one constant width (`half_fn`, the per-station
mechanism the pavement-traced ramp and the object corridors already use).
A pavement tracing the road (2026-09-06b (2)) stays senior where it reads.

### Shared reading

Both are one statement: **a ramp is shaped from its own road — the depth the survey
reads the road at, and the carriageways' own edges — and the law's defaults (7.5 m,
one constant width) apply only where the road states nothing.** #742's channel
refusal (§45 (21)) is the same witness read on an open channel.

## Acceptance bar

* LFPG `tunnel:-300@0`: no ramp north of the berm (the mouth refused as surfacing
  under the pavement, or a floor ≥ the lidar road at its mouth).
* Every bore the witness does not fire on: `Tunnel` records byte-identical
  (`tools/structure_replay_diff.py`), except duals (width only).
* KCLT south ramp: both carriageway edges inside the ramp at every station, and the
  ramp no wider than the carriageways + the identity grid.
* KDEN: structure records identical.

## Owner question (non-blocking; the fix implements (a))

Q: Where the airport's 1 m lidar shows a road passing under a taxiway at its own level
(LFPG: 13 underpasses under the terminal-2 taxiway berms; KCLT's north underpass),
should the tunnel floor be the road the lidar shows — (a) yes, the road stays where
the survey has it and only the approach is ramped if it is higher (recommended), or
(b) always cut 7.5 m under the ground over the mouth (RULINGS 2026-10-14f), even
below a road the survey shows?
