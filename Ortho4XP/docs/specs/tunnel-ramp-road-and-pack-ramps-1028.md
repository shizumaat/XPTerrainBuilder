# Tunnel ramps follow their road; pack ramps govern the trench (#1028, owner Q31/Q32)

Owner, 2026-10-20 01:51Z.

- **Q32:** "We need to understand the situation better, either there isn't really a tunnel there, or it's steeper, or the shape is wrong, but they definitely shouldn't cross a pavement edge or go through another road."
- **Q31:** "Yes, just like OTHH, VHHH, KATL, etc. when a package includes any objects around a tunnel they take priority for defining the size, shape, depth, and location of tunnel trenches."

## A. The 18 ramps that ran past their mapped road (#1062 residual)

Evidence comes from the registered captures: `EDDF capture cd8fd9ff2 lane c971`, `KCLT capture e2f2e7e43 lane m4` and `LEMD capture c6c9fe7d3 lane c971`. The structure pass ran on #1062's head (84d7438b4).

How each column is measured:

- **Walk end:** what the approach walk (`structure_approach.approach`) found at the node where it stopped. The turn is measured against the road's heading. The cap is 60°.
- **Grade needed:** the rise from the mouth floor to the DEM where the axis leaves its road, divided by the run to that point. The cap is 10 %.

| # | tunnel | landmark | walk end (evidence) | grade needed | class | now (this branch) |
|---|---|---|---|---|---|---|
| 1 | EDDF `-35458+-18828@0` (service, layer −1, 75 m bore) | 1.3 km NE of the 25C threshold, 581 m from taxiway N | at the portal the roads leave at 88° (a T junction); 0 m walked | 102 % | **shape**: the portal opens onto a crossing road | refused: no road to climb along after the mouth slides out of the crossing road |
| 2 | EDDF `-35430+-18812@0` (service, layer −1, 295 m) | 846 m NE of the 25R threshold | the service road dead-ends 43 m out | 16 % | **steeper** (over the cap), and the road ends | refused |
| 3 | EDDF `-25266+-13396@0` (service, layer −1) | 1.7 km NW of the 25R threshold | the second feed's copy `-33590` of the same tunnel continues at 0°; 0 m walked | 42 % | **no real portal**: duplicate ways from two feeds split the chain (four ways meet at the node) | not a mouth |
| 4 | EDDF `-21432+-11431@0` (service, 52 m) | 831 m N of the 25C threshold | tunnel `-21450` (layer −3) continues at 25° | — (the road leaves at 0 m) | **no real portal**: the road goes on down into a deeper level | not a mouth |
| 5 | EDDF `-20307+-11008@0` (service) | 1.9 km E of the 25R threshold, apron edge, 330 m from N8 | 101 m of layer +1 service road, then tunnel `-29600` at 2° | 133 % | **no real portal**: the road between the two bores is mapped above ground, not in a cutting | refused (the road leaves the corridor 12 m out) |
| 6 | EDDF `-16931+-9518@0` (service, 4 lanes, no layer, 15 m bore) | 1.9 km W of the 25C threshold | nothing continues at the end | 21 % | **no real tunnel** (a 15 m passage) | trimmed at the crossing road `-25918` (12 m) |
| 7 | EDDF `-14187+-8545@0` (track, layer −1) | 2.8 km N of the 25R threshold, by trunk road `-16028` | the track turns 90° 10 m out | 34 % | **shape**: the track turns at the portal | refused |
| 8 | EDDF `-11095+-6523@0` (track, layer −1) | 2.3 km N of the 25R threshold | junction 47 m out; the continuations turn 93° and 114° | 13 % | **steeper** (over the cap) | refused |
| 9 | EDDF `-3189+-1462@0` (track) | 2.1 km NE of the 25C threshold | the track dead-ends 9 m out | 50 % | **shape**: the road ends at the portal | refused |
| 10 | EDDF `-27364+-478@0` (rail, layer −1, 494 m) | 989 m E of the 25R threshold | rail tunnel `-10179` continues at 1°, 7 m out | — | **no real portal**: duplicate-feed split | not a mouth |
| 11 | EDDF `-9546@1` (rail, layer −1) | 1.5 km NE of the 25C threshold | the bore's end meets no way at all | 23.5 % | **no real portal**: a dangling rail-tunnel end | trimmed at track `-8725` (36 m) |
| 12 | EDDF `-2201@1` (rail, layer −1) | 2.8 km NE of the 25C threshold | rail tunnel `-2200` continues at 1°, 36 m out | 7.7 % | **no real portal**: an open slot between two bores, shorter than the shortest lawful ramp | not a mouth |
| 13 | KCLT `-6954@1` (service, layer −1) | 1.3 km SW of the 18L threshold, 28 m from taxiway M | tunnel `-8739` continues at 0°, 19 m out | 35 % | **no real portal**: a 19 m gap between two bores | not a mouth (the `-8739` far end builds as before) |
| 14 | KCLT `-30363…@1` (an underpass under taxiway U, tertiary dual) | 570 m W of the 36R threshold, 88 m from U | the two carriageways part 48–56 m out (one runs into a roundabout) | 7.5–8.7 % | **shape**: the dual's mean axis stops being a road where the carriageways part | refused: it cannot top out before the parting. **Regression on #1035's ramp**; per-carriageway ramps past the parting are the fix |
| 15, 16 | LEMD `-15336@0/@1` (service, layer −1, 37 m bore) | 2.2 km W of the 32L threshold, 274 m from I7 | the service road dead-ends 96 m out; tertiary `-5293` crosses at 72 m | 10.0 / 10.6 % | **steeper** (at or over the cap), and a road crosses | trimmed at road `-5293` (72 m) |
| 17 | LEMD `-12795@1` (service, layer −1, 17 m bore) | 2.7 km W of the 32L threshold, 140 m from C2 | the road dead-ends 6 m out | 16 % | **no real tunnel** (a 17 m passage whose road ends) | refused |
| 18 | LEMD `-4439@1` (track, layer −1, 106 m) | 3.6 km SE of the 32L threshold | the bore's end meets no way | 68 % | **no real portal**: a dangling end | refused |

**Tally:** no real portal or tunnel 10 (rows 3, 4, 5, 6, 10, 11, 12, 13, 17, 18); steeper 4 (rows 2, 8, 15, 16); shape 4 (rows 1, 7, 9, 14).

### Proposed general rule (implemented here)

1. **A bore end is no portal** where the road goes on underground: another tunnel way leaves the end's node within the turn cap. That includes a second feed's copy of the same way, and a tunnel reached after an open stretch shorter than `mouth_depth_m / ramp_max_grade` (75 m). The end builds no mouth, and the structures line names it. Implemented in `planar/bore_continuation.py`.
2. **A ramp never goes through another road.** Every mapped road that passes through the corridor axis is a stop. Excluded: a road the ramp runs along (its own, or another feed's copy), a road that only ends on the axis (a junction), and a bridge over it (its deck). These stops slide the mouth out of a road over the bore, as pavement does (`structure_mouth`), and they trim the ramp's top. Implemented in `structure_approach.crossing_roads`.
3. **A ramp never leaves its road.** If no grade up to the 10 % cap tops out before the axis leaves its mapped road, the ramp is refused by name. A corridor that reaches no road within 4 half widths of its mouth has no road to follow and is refused too. This replaces #1062's "built past it as before".
4. **Pavement edges.** These were already stops (#971, `structure_mouth.mouth_stops`). One gap remains: a ramp hosted inside an apron (clause 3) is not stopped at that apron's own edge. Not changed here.

The follow-ups this table points at:

- `chains()` should merge coincident ways from two feeds. Rule 1 drops those ends today; merging would build the bore's real far mouth.
- Row 14 needs a ramp per carriageway past the point where they part.

## B. Pack ramp objects govern the trench (Q31): consumer census (RULINGS 2026-08-30l)

The objects: EDDF `GP/Bridges/Tunnel_3.obj` (379 × 75 m) and `Tunnel_4.obj` (220 × 28 m). The sunken-road reader (`airport/sunken_roads.read_family`) reads each as a descending floor: −6.15..+1.53 m and −5.90..+1.79 m. It refuses them only because they are 29 % and 2 % roofed ("an open ramp, not a sunken road", Law B's `roof_min_fraction` 50 %).

| consumer | reads | ruling for an OPEN ramp object |
|---|---|---|
| `airport/sunken_roads.read_family` (admission) | roof cover ≥ `roof_min_fraction` | ADMIT an unroofed plate when a mapped tunnel way enters it (its line meets the plate). The record is marked `open`. Without a bore it stays refused. |
| `read_family` (profile, cut) | `max_depth_m` 4 m: deeper is the road under the building's tube | For an OPEN record the cut runs to the plate's deep end. There is no tube to hide a terrain end wall. |
| `read_family` (two-ended plate) | one deep end, walked down from one grade end | A plate shallow at BOTH ends is split at its deepest station into two records, one ramp per end. |
| `planar/door_ramps.sunken_groups` | the record becomes `Group(kind="sunken_road")`: floor = the plate per station, width = the plate's half widths | unchanged |
| `planar/structures` precedence (05n-3) | OSM mouths inside an object corridor's footprint are replaced | EXTENDED: an OSM mouth inside an OPEN sunken group's footprint ⊕ `bore_end_tolerance_m` is the object's, and its OSM ramp is not built |
| `constraints/structures`, `verify/structures`, `publication.tunnel_objects`, `rebake_inputs` | `Tunnel.source == "sunken_road"` | unchanged: the profile pins and the mouth-law exemption apply to object ramps alike |
| `structure_mouth` (#971 slides, #1028 profile) | OSM mouths only | not reached: the object's mouth replaces the OSM one |
| basin / object-cut readers | refuse Tunnel_3/4 ("no floor plate", rule 5b) | unchanged |

Check: OTHH, VHHH and KATL tunnels that already follow pack objects must not change. Measured by structure replay.
