# The ramp foot's run-out — one rule for #669 and #1093 (lane lramp2)

Base: `origin/main` 2cc289364. Capture `KCLT.pkl` (this lane), base solve
`--gap-free --solved-out base.pkl`, last stage `--late-from base.pkl`
(scratchpad `lramp2/`). Site: the KCLT departures roadway's object ramp
(`Terminals/techos_1_charlotte.obj`, unit:31, an elevated deck seated on the
terminal pad `building75`, plate 222.85 m) comes down northward to its foot;
lip 35.2223764, -80.9423153, 14 m wide, deck foot at the unit level
(y_foot -0.03 m: 222.82 m). Second witness: the same object's west foot
(lip 35.2220405, -80.9459112, 18 m wide).

## 1. What main does now (replay, site numbers first)

The 2026-10-22g road reach (#1246) now ribbons the mapped departures
roadway: `big_roads:-6300` (OSM secondary, 8 m wide) leaves the lip north
for 62 m, and two slivers of it (`-6300#1`, `-6300#2`, 0.26 m wide, 42 m
long) lie inside the ramp's footprint. All three share vertices with the
pack pavement under the ramp (`gap:0`), so they are FOLLOWERS of the gap
stage (`stage_one_map.late_followers`), solved with `gap:0` at their own
road profile:

| east foot (the #669 / #1093 site) | main 2cc289364 |
|---|---|
| ground on the axis 0.5 m behind the lip (`gap:0` / `-6300#2`, v22956) | 220.32 m — **2.5 m under the deck's foot (222.82)** |
| `-6300` at s = 6 m (v16183 / v16184) | 219.86 / 219.48 (DEM 218.5) |
| run-out start level `z0` read off the patch | 219.63 (sw27: 221.92) |
| run-out strips | `runout:1` (east of the road, 2.5 m), `runout:2` (west, 4.5 m), run 11 m |
| open edges > 0.5 m off the DEM within 30 m of the strips | 16 of 21 (`runout:2` west side +1.66 / +2.22 / +2.62 m; `gap:0` west side +4.0 m) |
| the 2026-10-21 east corner (35.2229758, -80.9422428) | now inside `-6300`'s course; `runout:1` corner +0.09 m |

West foot (no mapped road ahead; `runout:0`, z0 222.69, run 39 m x 18 m):
the run-out's design rows are missed again, **9 of 9 at the last stage
(max 5.80 m)** — the strip's far end is held at 222.7 m by the pad road
`small_roads:-6064#1` that runs along its east side at the pad's level
(13e released it to 52.8 % over 8.6 m where it leaves); its open edges stand
+4.18 / +3.75 / +3.58 m (east side) and -1.97 / -1.19 m (west, the ground
rising 11 % across the 18 m strip).

## 2. Attribution

1. **The ramp's foot does not lead what lies ahead of it.** The strip's
   start (`classify/ramp_runout._level_at`) reads whatever the patch solved
   at the strip's start; nothing ties the patch at the lip to the deck's
   foot. Before 10-22g the gap piece followed the terminal pad (222.2-222.5
   at the lip, sw27); now the mapped road ahead and its slivers are
   followers of the same stage and pull it to the road's own ground — the
   foot ends 2.5 m in the air (the #669 symptom, back in another form).
2. **The mapped road ahead has no run-out law.** RULINGS 2026-10-14i
   ("where a mapped road continues from a ramp landing or foot, that road
   descends from the landing's level along its own course at road grade …
   until it meets raw DEM") is implemented for LANDINGS only
   (`runout_exempt`: a road on a landing's strip rides it). At a non-landing
   foot the road keeps its own profile off its DEM.
3. **The run-out's open edges are not finished.** The strip is a 2 %
   cross-fall road laid on the axis ground; where the ground falls across
   it (11 %) or the strip stands over the ground along its sides, its edge
   is a step at the patch boundary. The 10-20aw bank trial (lane l1093b)
   failed because its fixed 15 m bank's toe had no row on the ground.

## 3. The rule (one rule, both issues)

**THE FOOT LEADS ITS RUN-OUT, AND THE RUN-OUT ENDS ON THE GROUND.**

* **R1 — the level.** Ahead of an object ramp's foot, the ground starts at
  the FOOT's level: the unit's seat (the held, flat pad under the unit's
  anchor: its datum column, a stage-1 constant) + the deck's authored
  `y_foot`. Never the level the patch happened to solve under the lip.
* **R2 — who carries it (14i, 14c (5)).** Along the direction of travel,
  over the foot's width, a mapped road continuing from the foot carries the
  run-out: each of its vertices from `FOOT_SPAN_M` behind the lip onward is
  held between the foot's level and the design profile off it (the shared
  ramp law `geom/ramp_profile.ramp_delta`: design 5 % closing the foot's
  offset over the axis ground, never steeper than the road cap 10 %),
  behind the lip AT the foot's level — the landing run-out's own row shape
  (`landing_runout_rows`) against the foot's datum column, a row of every
  stage that solves the road; the road's §37 rows on those vertices are
  withdrawn as on a strip (`runout_exempt`). Elsewhere in that width the
  strip (14c (5)) carries it, as now. A pad road keeps its own law (13a),
  and a landing's foot stays with `planar/landing_runout`.
* **R3 — the edges (10-20aw trial, 10-20ay bar).** Every side and the end of
  a run-out strip that stands on open ground finishes on the raw DEM through
  a 1:3 bank (`runout:<k>#collar`, the collar class every bank reader
  knows) whose width at each station is the DAYLIGHT distance — where a 1:3
  slope off the strip's edge meets the ground (capped at
  `[building_pad] platform_collar_max_m`) — and whose own vertices take a
  design row at their DEM clamped into the 1:3 cone off the nearest strip
  point (the toe row the l1093b bank lacked). A vertex another face shares
  (a pad road, a lot) is that face's: the bank never lifts it.
* **The strip beside its carrying road is that road's shoulder.** Where a
  mapped road carries the run-out (R2) and the strip fills the foot's width
  beside it, the strip's level at a station is the road's (its LEAD,
  `geom/ramp_profile.strip_level`), and past the road's last station the
  ramp law continued off it; the bank's daylight reads the same level.

Law cited: 14c (5), 14i, 03e (1:3 bank), 20aw (trial), 20ay (bar), 22g
(the road reach that exposed it). No new ruling is needed; R3 is the 20aw
trial, for the owner's sim read.

## 4. Acceptance bar (east foot; the west foot reported)

* the ground at the lip within 0.5 m of the deck's foot (222.82 m);
* `-6300` within 0.5 m of the design profile off the foot for its descent;
* `ramp_runout` rows: no miss over 0.05 m on the east foot's strips;
* no open patch edge of the run-out (strips, their banks, the road in the
  corridor) more than 0.5 m off the DEM (20ay);
* no new relaxed hard row family; airside 0 movers; census not worse
  outside the site.

## 5. Out of scope (reported)

* `gap:0`'s own open west edge (+4.0 m) and `building75`'s coverage edge
  (+5.7 m) beside the ramp — the ramp's SIDES (10-14c (5): 10-03e's bank
  stays for the sides; there is no side bank at a non-landing foot), a
  class of pad / gap-piece edges, not the run-out.
* The west foot's pad road `small_roads:-6064#1` at pad level along the
  strip, released to 52.8 % (13e) — a pad-road question.
* #684 (roads inside a lot are the lot) — separate PR if time allows.

## 6. Measured (replays off one capture; base `--gap-free` solve shared)

Capture `lramp2/KCLT.pkl` at 2cc289364; control `late_ctl.pkl` (main);
arm `late_r5.pkl` (this branch). Coordinate-joined movers, arm vs control:
building (bank vertices only) 9, groundside_pavement 34, service_road 142;
**airside 0, pads 0**. Gap stage: relaxed hard rows 9 + 8 + 3 (follow,
ramp ceiling, pavement ceiling) -> **none**; pad-roads stage unchanged in
kind (cross-section 38 -> 35).

| east foot (#669 / #1093) | main | this branch |
|---|---|---|
| ground at the lip on the axis (deck foot 222.82) | 220.32 | **222.75** |
| `-6300` at s = 6 / 17.5 m | 219.86 / 218.71 | 222.15 / 221.07 (the foot's 5 % profile) |
| run-out start `z0` / run | 219.63 / 11 m | 222.15 / 62 m |
| strip design rows: misses > 0.05 m, worst | 4 of 4, 0.53 m | 10 of 15, **0.29 m** |
| open patch edge > 0.5 m off the DEM within the run-out box (s -15..75 m, ±22 m), all faces | 412 m | 203 m |
| of it the run-out's own (strips, banks) + the road `-6300` | 18 + 95 m | **11 + 0 m** |

The 11 m left on the run-out's own faces are two wedges where its bank meets
a neighbour that itself stands off the ground: the bank's start flank beside
`gap:0` / the apron `pav14` (35.22243, -80.94219, +1.6 to +2.7 m over 4.5 m)
and its north end against the raised junction with `big_roads:-1570`
(35.22300, -80.94225, +1.9 to +2.9 m over 3 m).

West foot (no carrying road; `runout:0`): the run-out's own open edge 23 m ->
5 m; its far end stays 4.6 m over its design (the pad road
`small_roads:-6064#1` along it at the pad's level, 13e — out of scope).

Still visible beside the east foot and NOT the run-out's: the west side of the
pack pavement under the ramp's last metres (`gap:0`, 35.22242, -80.94241, up to
+5.6 m — higher than on main because the foot's ground now meets the deck),
the terminal pad `building75` (+7.3 m) and the pad roads west of it
(`small_roads:-11471`, `-8197`, `-8201`, +5 m). The ramp's SIDES at a
non-landing foot have no bank (10-14c (5) keeps 10-03e's bank for the sides;
none is minted where there is no landing) — a follow-up.
