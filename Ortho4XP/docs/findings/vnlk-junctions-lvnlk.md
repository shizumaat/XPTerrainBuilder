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

1. **Junctions (round 2, RULINGS 2026-10-27b Q182 (a)).** A junction is a non-runway
   airside pavement face (taxi family or apron) sharing at least two ring vertices with the
   runway's own faces. Its span is the MOUTH: the along-ridge extent of those shared
   vertices' feet, widened to the ridge chords that cover it (J2 388.0–411.1 m, J1
   481.7–540.6 m at VNLK). Its cap `t` is the joining face's own TRANSVERSE maximum.
   Overlapping spans merge at the tighter `t`. A junction applies only where the pin grade
   exceeds its `t`. (Round 1's frontage-within-the-tie span is withdrawn by Q182.)
2. **The designed profile is the smoothest the pins and the caps allow (Q182: "the runway
   must still minimize curvature changes, it can't create a dramatic bump or dip").** Over
   the station chords' grades `g_k`: minimise `Σ (g_{k+1} − g_k)² / s_k` (`s_k` the mean
   spacing — the discrete ∫g′²) subject to `Σ g_k d_k = Δz` (both pins exact) and
   `|g_k| ≤ t − margin` on every junction chord (`runway_junctions.smoothest_grades`, a
   bounded least squares, `scipy.optimize.lsq_linear` BVLS). Its continuous optimum is a
   parabolic grade between the caps — a cubic profile, no kink and no crest or sag beyond
   what the caps force. Parameter-free: round 1's `[design] steep_junction_curve_share` is
   DELETED (refuted mechanism).
2b. **The ski jump (round 3, RULINGS 2026-10-27e Q185).** "Least slope at the two ends,
   most in the middle ... we definitely don't want the steepest part to be at the low end."
   Each runway END's chord (a threshold pin ends the governing span) is capped like the
   runway's gentlest junction (here 1.5 %; an end inside a junction already is), and the
   smoothest profile above then rises from both ends to its steepest grade between them.
   Still one bounded least squares, still parameter-free.
3. **The curve the rows hold** is the one the design needs: the law's K where the design's
   largest change of grade fits it, else the K it reads, published 5 % sharper than drawn
   so the vertical-curve rows hold it with room.
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

## 4. Round 1 acceptance and results (frontage spans; superseded by §7)

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

**Closing build** (harness `build_airport.py VNLK --tag lvnlk`, branch at de78009e9; frame
registered `lvnlk/lvnlk.osm`): body `194de949d191`, patch 32.1 s, `status=optimal`, shared
repo unchanged. Census identical to the replay: ADJUDICATED **143** (base 822), CRITICAL
motion **0** (the registered round-2 build had 1: 3.435 m `strip_transverse`
junction|runway), v2 verify DEFECT families all zero.

**Sim read (by landmark).** From the Main Apron at the top (RWY 24) end, look down the
runway: the runway should be flat (1.5 %) from the 24 threshold past the apron joint and
the right-side spot (about 165 m from the 24 end), then curve over about 90 m into a
steady 17 % fall to the RWY 06 threshold. On the apron: one flat pad meeting the runway
edge with no twist; its west corner (toward the lodge and terminal buildings) is the one
place it bends (about 0.5 m) to meet the building pads.

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

## 6. Round 1 open points (2 and 3 answered by RULINGS 2026-10-27b; see §7)

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

## 7. Round 2 (RULINGS 2026-10-27b, Q182 (a); #1461)

Mouth-only spans and the least-change-of-grade profile. Replay of the same capture, then
the closing harness build `lvnlk2` (body `b8eeef807e69`; census identical to the replay).

| | round 1 (frontage spans, share 0.15) | round 2 (mouth, smoothest) |
|---|---|---|
| junction spans | 375.8–446.4 m, 458.1–540.5 m | 387.9–411.0 m, 481.6–540.5 m |
| ridge across each junction | ≤ 1.504 % | ≤ 1.503 % |
| peak grade | 17.44 % (lower 290 m) | **21.6 %**, at the RWY 06 threshold, easing steadily to 1.5 % at J2 |
| largest change of grade | 19.0 pp per 100 m (K 5.26 m per 1 %) | **10.1 pp per 100 m** (K 9.94 drawn, 9.44 published) |
| between J2 and J1 | 2.0 % (one chord) | 1.6–1.7 % |
| max height above the Copernicus DSM | 17 m | **19.5 m** (near s = 280 m) |
| ends | exact | exact |
| census ADJUDICATED / CRITICAL motion | 143 / 0 | **139 / 0** |
| `transverse` / `taxi_box` | 0 / 2 | **0 / 2** |

No family rises against base (`strip_arc` 7 → 7). By site, 9 rows are where base had none:
the 4 at the Main Apron's west corner (pad weld, as round 1), 2 `strip_transverse` lip
rows beside the lower runway (0.35, 0.34 m), and 3 `strip_arc` rows on the outer graded
strip of the lower runway (zone 2, 15.8–17.2 m: the strip's 58 m ring chords against the
runway's long curve).

**The pad cross-slope rows the mouth-only span leaves.** Round 1 estimated 10 `transverse`
+ 4 `taxi_box` on the pads beside the runway with a mouth-only span; with the smoothest
profile the runway between the two spots stays at 1.6–1.7 %, so they do not occur. What
the census reports on junction / apron pavement (all `pav4`, the Main Apron; none on
`pav2` or `pav0`): `transverse` 0; `taxi_box` 2 (0.21 m at the 24 end, 0.18 m at s = 488,
both base sites); `within_shape` 3 (0.67 m at the runway weld s = 525, a base site; 0.54
and 0.32 m at the west corner); `airside_no_step` 10 (7 at the runway-edge weld s ≈ 520–524,
0.67–0.78 m, base sites; 1 internal 0.59 m; 2 at the west corner).

**The trade the smoothest profile makes (for the owner).** Flat junctions near the top end
and the pins fixed, a gentler curve can only come from a steeper bottom. The smoothest
profile with the steepest grade bounded (same capture, mouth spans):

| peak bound | largest change | K (m per 1 %) | between the spots | above the DSM |
|---|---|---|---|---|
| 13.1 % (the least possible) | 46 pp / 100 m | 2.2 | 13.1 % | 5.1 m |
| 14 % | 36 | 2.7 | 10.3 % | 7.6 m |
| 15 % | 30 | 3.4 | 6.6 % | 10.5 m |
| 17 % | 17 | 5.9 | 2.9 % | 15.6 m |
| 20 % | 11 | 9.0 | 2.0 % | 18.9 m |
| none (shipped) | 10 | 9.9 | 1.7 % | 19.5 m |

A peak bound would be one law number over the same solver (`smoothest_grades` with a cap on
every chord); it is not built, because Q182 asks for the smoothest profile and names no
peak.

## 8. Round 3 (RULINGS 2026-10-27e, Q185: the ski jump; #1461)

Formulation: §3 item 2b — the round-2 smoothest profile with each runway end's chord capped
like the gentlest junction (1.5 %). Closing harness build `lvnlk3`, body `515a308afe9d`
(census identical to the replay).

Grade profile at 50 m stations (metres from the RWY 06 low end; the 24 end is at 540.5 m):

| s (m) | 0 | 50 | 100 | 150 | 200 | 250 | 300 | 350 | 400 | 450 | 500 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| grade | 1.5 % | 10.0 % | 16.4 % | 20.3 % | 21.8 % | 20.3 % | 16.4 % | 10.1 % | 1.5 % (J2) | 2.4 % | 1.5 % (J1) |
| above DSM (m) | +1.1 | −3.0 | −2.4 | +1.3 | +6.8 | +11.7 | +14.7 | +14.0 | +12.2 | +6.4 | −2.1 |

- Peak **21.75 %** at s = 206 m (335 m below the 24 threshold): the middle of the lower runway.
- End grades: RWY 06 **1.5 %**, RWY 24 **1.5 %**; ends exact on the pins (2784.043 / 2845.003 m).
- Largest change of grade 20.3 pp per 100 m (K 4.68 m per 1 % published).
- Max height above the surface model **14.8 m** (s = 305 m), against round 2's 19.5 m and
  round 1's 17 m.
- Junction mouths ≤ 1.503 %.
- Census ADJUDICATED **130** (round 2: 139; base 822), CRITICAL motion 0, `transverse` 0,
  `taxi_box` 2. Against round 2: `airside_no_step` 16 → 11, `strip_arc` 7 → 3,
  `pavement_over_road_cap` / `hard_conflict` 35 → 34, `strip_longitudinal` 27 → 28,
  `strip_transverse` 5 → 6. Against base, 7 rows are at new sites: the 4 west-corner pad
  rows, 2 `strip_transverse` lip rows (0.35–0.42 m) and one 0.28 m `airside_no_step` pair on
  the lower runway.

**The middle taxiway against the owner's shape.** The owner places the steepest part
between the apron and the middle taxiway, easing past it. J2's mouth (388–411 m) is
130–150 m below the 24 end and must be 1.5 %, and the stretch between J2 and the apron
joint is 70 m. Forcing that stretch steep puts a dip at J2 (same capture, smoothest profile
with the J1–J2 stretch held at least at the grade named):

| J1–J2 grade at least | peak | largest change at J2 | above DSM |
|---|---|---|---|
| (shipped, free) 2.4 % | 21.8 % | 4 pp / 100 m (20 elsewhere) | 14.8 m |
| 6 % | 20.9 % | 20 pp / 100 m | 12.9 m |
| 9 % | 20.2 % | 33 pp / 100 m | 11.4 m |
| 11.3 % (the pin average) | 19.7 % | 43 pp / 100 m | 10.2 m |

A steep J1–J2 stretch costs a 1.5 % dip at J2 with up to twice the shipped largest change —
the "dramatic bump or dip" 27b forbids. So the shipped shape is: gentle from the 24
threshold past the apron joint and the middle taxiway (1.5–2.4 %), then steepening below
J2 to the peak in the middle of the lower runway, then easing to 1.5 % at the low end.

**Sim read (by landmark).** From the RWY 24 threshold by the Main Apron, roll toward RWY 06:
nearly level past the apron joint and the right-side spot (the middle taxiway, about 140 m
down); below it the runway tips over and steepens to about 22 % in the middle of its lower
half (about 200 m above the 06 threshold), then eases out to almost level across the last
50 m before the 06 threshold — the lip of the ski jump over the drop.

## 9. Cross-check against the owner's video (lane lvnlkvid, 2026-10-27; no engine change)

Source: the 9 contact sheets of the owner's video (74 frames, every 5 s, 640x360 per frame),
the tile's ZL18 orthophoto (`110064_194224_Arc18.dds`), the Copernicus GLO-30 inset
(`VNLK_copernicusglo30.tif`) and the pack's `apt.dat`. `s` = metres from the 24 end along
the pack's runway line (540.4 m); 06 end = 540.4 − s.

**Method.** Two frames from the camera beside the Main Apron (sheet 9 frame 1, sheet 4
frame 2, same zoom: their dash half-widths agree within 1 %) carry 10 and 12 centreline
dashes. The ortho gives the dash period, 28.5 m (autocorrelation 0.75). In both frames
1/(half-width) is linear in dash index within 0.07 %, so the dashes are evenly spaced and
each one is ranged: depth Z_k = (2.95 + k) · 28.5 m, focal length 1,097 px (half-width
10.15 m). Drop below the camera H = (row − horizon row) · Z / f; grade = ΔH / ΔZ. The
horizon row is the one free number: it shifts every grade by 0.09 pp per pixel and nothing
else. It is fixed by the two pins plus the camera height: the top pin bounds the camera at
≤ 2,863 m, and the DSM at the camera spot (beside the apron's NE corner, about 19 m left of
the centreline, ~10 m down-runway of the 24 end) puts it at ~2,860 m. The helipad connector
lands on dash 7.5 (Z ≈ 298 m) and the ortho has it at s ≈ 298–317 m, which ties Z to s
(s ≈ Z + 10 m).

**The video's profile** (horizon at the DSM camera height; ± is the horizon band plus
row noise):

| s from 24 (m) | 0–50 | 50–100 | 100–150 | 150–200 | 200–250 | 250–300 | 300–350 | 350–400 | 400–500 | 500–540 |
|---|---|---|---|---|---|---|---|---|---|---|
| grade | ≈ 2 (1.5–6) | 12 (break near 55–65 m) | 15.0 ± 1 | 13.2 ± 1 | 12.2 ± 1 | 11.9 ± 1 | 11.8 ± 1 | 11.2 ± 1.2 | 12 ± 2 (mean only) | not resolved |
| confidence | low (not in frame) | medium | high | high | high | high | high | medium | low | none |

- The shape does not depend on the horizon row: steepest just below the top joint
  (s ≈ 65–160 m), easing ~3 pp to a near-uniform ~12 % from s ≈ 190 m on (dashes 4–9 agree
  within ±0.5 pp). The two frames agree (rms 0.3 pp on the shared dashes).
- **No tip-over.** Every dash sits higher in the image than the one before, out to the 06
  threshold bars (row 213.5 in sheet 9 frame 1). The far ~140 m (s ≈ 380–520) fits in 16 px,
  so only its mean grade is measured (12 ± 2 %). A 1.5 % lip over the last 40–50 m can be
  neither seen nor ruled out at this resolution.
- The DSM agrees on its own: 14.8 % over s 50–150, 11.8 % over 150–300, 11.9 % over 300–525,
  and 2844.0 m at s = 50 against the 2845.0 m top pin.

**Against round 3.** Round 3 keeps s 0–150 at 1.5–2.4 % and peaks at 21.8 % at s ≈ 335. In
height, round 3 sits **+5.6 m at s = 100, +12.1 m at 150, +15.0 m at 200, +13.9 m at 250,
+10.3 m at 300, +5.6 m at 350** above the video profile (within 2 m elsewhere). From the
video's camera, round 3 would hide the runway from s ≈ 200 m to the 06 end behind a crest.
Round 3 is visible end to end only from 45 m above the 24 pin, and the pins rule that out.
So the video refutes round 3's shape.

**Attribution: the pack's J2 is not the video's second spot.** Round 3's flat top is J2, the
pack's `Helo Apron` polygon. It touches the runway edge at s = 132.5–151.8 (lateral −10.1 m).
In the ortho, that polygon covers a bare dirt plot behind a grass verge, and nothing paved
joins the runway there. The video's "flat open area on the right" is the helipad: a
light-grey pad with yellow H circles, joined by a concrete connector at s ≈ 298–317 m
(ortho), on dash 7.5 in the video. The pack does not draw it, and the runway shows no flat
there either (11.7–12.0 % across it). Rulings 27b and 27e (Q182, Q185) were asked with J2
taken to be that spot. Under 27b/27e and the pack's pavement, round 3 is already the unique
smoothest profile, so no reshaping within those rulings can follow the video. Following it
needs the 1.5 % flat at the pack's J2 to go. No geometric witness tells that face apart from
a real taxiway mouth (the pack has no taxi network), so this goes to the owner for a ruling
and is not built.

**Sim read (by landmark).** From the RWY 24 threshold beside the Main Apron: level across
the apron joint (about the first 60 m), then the runway breaks steeply at the bottom of the
joint. The steepest stretch (~15 %) runs over the next ~100 m. From about 200 m down (just past
the dirt plot on the right where the pack draws its Helo Apron) the runway is a steady ~12 %
to the RWY 06 threshold, and it passes
the helipad connector on the right (~300 m down) without flattening.

## 10. Round 4 (RULINGS 2026-10-27n, Q205: flatten only where the imagery shows real pavement; #1461)

**The junction witness** (`airport/junction_witness.py`, at load beside the threshold
witness, on lane ltriang2's imagery reader — `imagery_read.TextureSet`, the classic method
of `image_edges_classic`): for every apt.dat pavement touching a runway edge, probes every
1 m along the contact, each from the runway body out 6 m past the edge. The classic method's
new kind `edges(..., "paved_contact")` reads the ground beyond the edge as pavement when its
median HSV saturation exceeds the runway body's by no more than `_PAVE_SAT_TOL = 0.05`. A
pavement joins paved when ≥ 50 % of its stations do. `Airport.paved_joins` carries the
verdicts. `runway_junctions.junctions` drops a face whose pavement the imagery refutes. No
imagery means `None`: every junction stands (the vote abstains).

**Calibration** (Arc ZL18 texture, the tile's own; strips 5.5 m deep beyond the edge):

| surface | luminance median | saturation median | Δsat vs the runway |
|---|---|---|---|
| runway body (asphalt) | 122.6 | 0.113 | — |
| Main Apron contact (asphalt) | 124.5 | 0.099 | −0.014 |
| helipad connector, video s ≈ 300 (concrete) | 223.0 | 0.039 | −0.074 |
| `pav0` "Taxiway 6" contact | 141.5 | 0.149 | +0.036 |
| `pav2` "Helo Apron" contact (dirt) | 124.1 | 0.191 | +0.078 |
| grass verges | 118.6 / 122.6 | 0.303 / 0.250 | +0.19 / +0.14 |

Luminance cannot separate these: the dirt plot reads within 1.5 levels of the asphalt runway,
and the concrete connector reads 100 above it. The classic `pavement_start` test (luminance
within 25 levels) would call the dirt paved and the concrete not. Saturation separates them,
with the cut at +0.05. The calibration rests on one texture and one airport. Witness at
VNLK: `pav0` paved (54 % of 56 stations), `pav3` paved (64 % of 53), `pav2` Helo Apron
**not paved (16 % of 19)**. `pav4` reads no contact of its own (`pav3` overlies the apron's
edge), so it abstains and keeps its junction.

**The profile follows the ground** (§3 item 2, round 4): with J2 gone, round 3's pure
smoothest profile put the steepest grade at the low end (17.8 %), against the video and the
DEM, which agree with each other. The design is now the smoothing spline of the DEM along the
ridge, through the pins and the paved junction caps:
`[design] steep_runway_ground_wavelength_m = 200` (relief longer than 200 m is followed).
**That value comes from one witness, the VNLK video:**

| wavelength (m) | 175 | 200 | 225 | 250 |
|---|---|---|---|---|
| peak grade | 19.2 % | 18.1 % | 17.3 % | 16.8 % |

Any wavelength from 175 to 250 m gives the same shape; only the peak moves, as above. The
round-3 ski-jump end cap is deleted (27n supersedes 27e).

**Closing build** `lvnlk4` (body `939b32004ea4`; census identical to the replay of capture
`lvnlk/VNLK.r4.pkl`). Against the video (§9), `s` in metres from the RWY 24 end:

| s from 24 (m) | built grade | video | video confidence | within? |
|---|---|---|---|---|
| 0–50 | 1.3 % | ≈ 2 (1.5–6) | low | no (flat cap) |
| 50–100 | 11.6 % | 12 | medium | yes |
| 100–150 | 16.5 % | 15.0 ± 1 | high | **no, +0.5 pp** |
| 150–200 | 13.0 % | 13.2 ± 1 | high | yes |
| 200–250 | 12.9 % | 12.2 ± 1 | high | yes |
| 250–300 | 12.0 % | 11.9 ± 1 | high | yes |
| 300–350 | 11.4 % | 11.8 ± 1 | high | yes |
| 350–400 | 11.1 % | 11.2 ± 1.2 | medium | yes |
| 400–500 | 11.5 % | 12 ± 2 | low | yes |
| 500–540 | 11.1 % | not resolved | none | — |

Height, built minus the video profile (integrated from the top pin), at 50 m stations from
the 24 end:

| s (m) | 0 | 50 | 100 | 150 | 200 | 250 | 300 | 350 | 400 | 450 | 500 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Δ (m) | 0.0 | +0.3 | +0.6 | −0.2 | −0.1 | −0.4 | −0.5 | −0.3 | −0.3 | +0.1 | +0.2 |

Largest gap 1.6 m. Peak 17.65 % at 100 m below the 24 end. End grades: RWY 24 0.7 % (flat),
RWY 06 10.8 %. At most 3.3 m above the Copernicus surface model (round 3: 14.8 m). Both pins
exact. Largest change of grade: the break at the foot of the apron joint, published K
1.49 m per 1 %.

**Census** ADJUDICATED **223** (round 3: 130; base 822), CRITICAL motion 0. The rise:

- `pav2` (the Helo Apron, unpaved per the imagery) now meets the 12–15 % runway, so it takes
  9 of the 11 `taxi_box` rows (up to 2.7 m).
- `pavement_over_road_cap` 34 → 63 and `hard_conflict` 34 → 69: more of the runway is over
  29ac's 10 %.
- 3 `transverse` rows (0.37–0.39 m) and 1 `taxi_box` row (0.42 m) on the Main Apron's west
  faces beside the break. These are the pad cross-slope rows 27b accepted.

Pricing a pavement the imagery refutes as ground rather than taxiway would remove the `pav2`
rows. That is not built: it needs a ruling.

**No-imagery arm** (the round-2 capture, which carries no witness): both junctions stand
(abstain), and the same ground spline peaks at 21.2 % between them.

**Sim read, by landmark.** From the RWY 24 threshold beside the Main Apron, roll toward 06:
level across the apron joint (about 60 m). The runway breaks over at the foot of the joint
into its steepest stretch, about 16–17 % over the next 100 m. It passes the dirt plot on the
right (the pack's Helo Apron, about 140 m down) without flattening. From about 200 m down
it is a steady 11–12 % to the RWY 06 threshold, passing the helipad connector on the right
(about 300 m down).
