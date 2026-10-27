# lvnlk — a steep runway flattens where taxiways join it (RULINGS 2026-10-26n, Q160–Q162)

Law: RULINGS 2026-10-26n (Q160–Q162), refining 26i and replacing 10-10j for steep
runways; 26i/26j (OurAirports end pins, 0 ft placeholders) already in law (PR #1416).
Test case: VNLK 06/24 (the owner's video site table, qualitative). VNLK is the place the
defect was found and the closing build, never the scope: no airport literal anywhere.

## 1. The site, numbers first (capture `lrwypin/VNLK.fbf12ccaa.pkl`, replay on origin/main 59fa7241d)

Runway 06/24, ICAO code 1B, 540.5 m between the pins (06 end 2784.04 m, 24 end
2845.00 m, OurAirports). Pin-to-pin 11.28 %; the §50 cap yields UNIFORMLY to
11.298 %, and the ridge is built at 11.26–11.33 % on every chord, including across both
junctions. Junction faces touching the runway edge (along = metres from the 06 end):

| junction | face(s) | contact along the runway edge | ridge chords covering it | t (face transverse max) |
|---|---|---|---|---|
| J1, top end and Main Apron joint | `pav4` junction face (left) + `pav0` (right) | 484.6–540.6 | 481.7–540.6 (58.9 m) | 1.5 % (letter F / default) |
| J2, the right-side spot partway down | `pav2` (letter E) | 388.7–407.7 | 388.0–411.1 (23.1 m) | 1.5 % |

Base replay census (v2 verify, 1,251 rows): `taxi_box` 482, `within_shape` 460,
`airside_no_step` 159, `strip_transverse` 84, `transverse` 28; DEFECT families zero.
77 hard rows relaxed (30 `pavement_max_grade ceiling`, 47 `road_max_grade pavement
fallback`) — the junction pavement welded to an 11.3 % runway edge. Main Apron body
planes tilt up to 9.5 m.

## 2. Attribution

The runway is one straight line pin to pin because §50 (09-18d (3)) yields the cap
UNIFORMLY and `runway_profile.yield_envelope` states a `Band` around the pin-to-pin line
at every station. So the runway's grade along each junction mouth is 11.3 %. A junction
face's TRANSVERSE direction at the mouth is along the runway, so its cross-slope there is
the runway's longitudinal grade: 11.3 % against a 1.5 % taxi transverse law. That is the
`taxi_box` / `transverse` / `within_shape` population and the 77 relaxed ceiling rows.
26i's twist zone was never built; 26n replaces it: no twist, the runway flattens.

## 3. The rule (one derivation, `constraints/runway_yield.derive` -> `constraints/runway_junctions.design`)

For a STEEP runway — its §50 cap YIELDED to pins demanding more than the 29ac universal
pavement ceiling (`tables.pavement_fallback_cap`, 10 %), the grade the pavement beside it can
no longer follow (Q160 was asked against that ceiling) — over its GOVERNING span (the two
consecutive hard pins §50 already names). A runway yielded under the ceiling keeps the
uniform §50 yield and the 30ah (1) / 10-10j following taxiways and aprons, byte for byte.

1. **Junctions.** A junction is a non-runway airside pavement face (taxi family or apron)
   sharing at least two ring vertices with the runway's own faces. Its span is the
   along-ridge extent of the JOINING PAVEMENT's frontage: the shared vertices plus every
   vertex of that pavement (the face's ref) the runway-edge tie reaches (within the runway's
   zone-2 half width of the centreline, `tables.runway_zone_edge_offset_m` + half width),
   widened to the ridge chords that cover it. Its cap `t` is the joining face's own
   TRANSVERSE maximum (`role_cap(...).transverse`, by its letter). Overlapping spans merge
   at the tighter `t`. A junction applies only where the pin grade exceeds its `t`.
   *Why the frontage and not the mouth alone (measured, arm a1 vs a3):* with the mouth
   only (J2 19 m, J1 56 m), the Main Apron's west faces and `pav2`'s run beside the runway
   stand inside the runway-edge tie while the runway curves at 10 %, and the census kept
   10 `transverse` + 3 `taxi_box` rows on `pav4` (0.34–0.55 m) and a `taxi_box` on `pav2`.
2. **The designed profile.** Grade as a function of ridge distance `u` from the lower pin:
   `g(u) = min(G, min_j (t_j − margin + r · δ_j(u)))`, `δ_j` the distance to junction `j`'s
   span (0 inside it). Inside a junction the grade is `t_j` (less the §50 margin); leaving
   it the grade eases up at a constant rate `r` (a vertical curve, `K = 1 % / r`) to the
   remaining grade `G`, solved (bisection) so the profile meets both pins exactly.
3. **The curve.** `K` is the law's own `vertical_curve_k_m` where it fits; otherwise it
   yields, uniformly per runway, only as far as keeps `G` within
   `[design] steep_junction_curve_share` (0.15) of the abrupt fit `G0` (no curve at all):
   `K = min(K_law, the largest K with G(K) ≤ (1 + share) · G0)`. The design is drawn 5 %
   gentler than the published K so the curve rows hold it with room. This is the one number
   the ruling does not give (Q160 says "eased by vertical curves", no radius); it is a value
   in `law/emit.toml`, never a switch.
4. **The record.** `RunwayCap` carries `junctions`, `curve_k_m`, `curve_rate_per_m` and the
   designed station heights (`profile_z`); `cap` names the steepest designed grade plus the
   margin. The sidecar `runway_caps` record publishes `junctions`, `curve_k_m` and
   `curve_rate_per_m` — only on a runway the ruling touched.
5. **Rows (`runway_profile`).** The §50 `Band` follows the DESIGNED profile (same width,
   `margin · min(d_a, d_b)`). Every ridge chord inside a junction span gets a hard `Diff` at
   that junction's `t` (head `rulesets.runway.longitudinal`, the runway tier). The
   vertical-curve rows use the yielded K (`tables.runway_vertical_curve_bound(yield_k_m=)`).
6. **The yielded curve has one meaning everywhere.** The runway ring's airside rate
   (`tables.airside_rate_per_m(yield_k_m=)`) and the strip along it
   (`tables.strip_arc_rate_per_m(yield_k_m)`) read the same K: the generators
   (`constraints/no_step.no_step_rate`, `constraints/strips.strip_arc`, through
   `precedence.curve_k_of`), v2 verify (`verify/runway`, `verify/no_step`, `verify/strips`,
   through `Patch.runway_curve_k`) and the census (`check_grade._check_airside_no_step_rate`,
   `_check_strip_arc_rate`, through the published `curve_rate_per_m`).
7. **Taxiways keep their own transverse law** (no twist zone): nothing relaxes a junction
   face; the flattened frontage is what lets its transverse law hold.
8. **An apron a steep runway joins is ONE terrace (Q162; replaces 10-10j there).**
   `constraints/steep_apron.py`: an apron pavement (a ref with an apron-role face) one of
   whose faces is a junction of a steep runway is ONE hard plane over every vertex of that
   ref, the runway-shared vertices left out (the `hard_plane` precedent); the basis is drawn
   from the pavement's own vertices, so a vertex a pad fronts may still give at its contact
   (10-08d (2)) without carrying the terrace. `derive_taxi` no longer yields an apron tied to
   a steep runway.

## 4. Acceptance and results (replay of the registered capture, then the closing build)

Capture `lrwypin/VNLK.fbf12ccaa.pkl`, replayed `--from constraints --emit --verify` on this
branch; census `tools/harness/census.py` on the emitted patch. Base = the same replay on
origin/main 59fa7241d (ADJUDICATED 822, the registered round-2 build's figure exactly).

| bar | result |
|---|---|
| runway grade across each junction ≤ the joining taxiway's transverse max (1.5 %) | J2 375.8–446.4 m: ridge chords max **1.504 %**; J1 458.1–540.5 m: **1.503 %** (the 0.02 m hard tolerance). Runway ring edges in the spans ≤ 1.55 %, one 1.4 m pair at 2.1 % (3 cm, the emit quantum) |
| no taxiway transverse breach | census `transverse` 28 → **0**, `taxi_box` 405 → **2** (both pre-existing sites) |
| the Main Apron is one level pad | `pav4` off the runway: one plane, 1.43 % along the runway, −0.51 % across, residual ≤ 0.034 m except the west corner vertex where building pads 22/24 front it (+0.47 m, the 10-08d (2) weld) |
| ends on the OurAirports pins | 06 end 2784.043 m, 24 end 2845.003 m: **exact** |
| zero new adjudicated violations | ADJUDICATED 822 → **143**; no family rises (`airside_no_step` 159 → 14, `taxi_box` 405 → 2, `within_shape` 4 → 3, `strip_transverse` 30 → 5, `strip_arc` 7 → 3, `hard_conflict` 76 → 40, `pavement_over_road_cap` 70 → 40). By site, 6 rows are at places the base did not have: 4 at the Main Apron's west corner (the pad weld above) and 2 `strip_transverse` zone-1 lip rows on the right side of the lower runway (0.41 m, 0.26 m) |

The runway now: flat at 1.5 % over its top 165 m (J1 and J2, 11.7 m apart, one chord at
2.0 % between them), a vertical curve at K 5.26 m per 1 % over about 90 m, and 17.44 % over
the lower 290 m (abrupt fit 15.17 %). Against the Copernicus DSM it stands up to 17 m above
the surface model at mid-runway (the uniform build stood within ±2 m there).

## 5. Census of consumers (08-30l) — what reads the changed records

| reader | reads | effect |
|---|---|---|
| `runway_profile.runway_profile` (Diff per chord at `cap_of`) | `RunwayCap.cap` | between-junction chords at `G + margin`; junction chords also at `t` |
| `runway_profile.yield_envelope` | the record | Band around the designed profile |
| `runway_profile.runway_vertical_curve` | `curve_k_m` (`precedence.curve_k_of`) | yielded K |
| `constraints/no_step.no_step_rate`, `constraints/strips.strip_arc` | `curve_k_of` | the runway ring and the strip along it at the yielded rate |
| `runway_profile.runway_within_shape`, `precedence.cap_of/face_cap`, `routes` | `cap` | looser cap on the runway ring; nothing else |
| `runway_yield.derive_taxi` | `cap`, `junctions` | taxi faces clipped at the 10 % fallback as before; aprons: no yield at a steep runway |
| `constraints/steep_apron.steep_apron_plane` | `junctions` | the terrace plane |
| `runway_mean_slope` | `yielded` | no rows on a yielded runway (unchanged) |
| `verify/frame.cap`, `tools/check_grade` (`runway_caps_by_ref`) | published `cap` | runway pairs at `G + margin` |
| `verify/runway`, `verify/no_step`, `verify/strips` | published `curve_k_m` (`Patch.runway_curve_k`) | the yielded K / rate |
| `tools/check_grade` rate readers | published `curve_rate_per_m` | the yielded rate |
| `pipeline/runway_report`, the §50.4 line | the record | the line names the junctions and the K |

## 6. Open points for the owner (not decided here)

1. **"Steep".** Implemented as "pins demand more than the 10 % pavement ceiling". If the
   owner means every yielded runway, the gate is one comparison in `runway_yield.derive`;
   that would reach the battery's mildly yielded runways (TFFJ, KASE class) and retire 10-10j
   there.
2. **The curve number.** `steep_junction_curve_share = 0.15` (K 5.26 m per 1 % at VNLK).
3. **The junction span.** The joining pavement's frontage within the runway-edge tie
   (70 m at J2, 82 m at J1) rather than the mouth alone (19 m / 56 m). The owner's video
   reading has "a bit steeper" between the top joint and the second spot; with the frontage
   rule that stretch is 11.7 m. The mouth-only arm (a1) gives that stretch (peak 10 %) but
   leaves the transverse rows above on the pads beside the runway.
4. **Retaining walls at the terrace's drop edges** are not built: the adjacent-ground zones
   still grade from the pad edge (`adjacent_ground_step` 6 rows, unchanged from base). A wall
   there is a new region read by the zone, strip and step families — a consumer census and a
   spec round (08-30l), not a lane edit.
5. **The 29ac pavement ceiling on the runway's own ring** (`pavement_over_road_cap` /
   `hard_conflict`, pre-existing): fewer rows (70 → 40) but the worst grows 6.5 → 9.5 m,
   because the lower runway is steeper. The ceiling does not yield with the runway.
