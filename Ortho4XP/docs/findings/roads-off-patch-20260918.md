# Roads raised / sunk outside the patch — attribution (scout, 2026-09-18)

Owner site: TFFJ 17.8985499, −62.838825 (tile +17-063, app 1.0.351 / engine 1.50.1797).
Read-only scout; every number is from the shipped artefacts of the 19:15 build.

## Site

OSM way index 435 of `o4_levelled_roads.json`, station 46–47; 637 m outside the patch.

| quantity | value |
|---|---|
| road z in the mesh | 41.16 m (clamp station 41.479) |
| working raster `Data+17-063.alt` (= sidecar `dem_alt` to 0.001 m) | 10.60 m |
| base DEM 1″ | 14.50 m |
| step across the ribbon edge | ≈ +30.9 m |

Way 435: 652 m, 59/59 stations clamped, max cut = max fill = 33.86 m (the min–max
mid-profile signature): −33.86 m at s=0 (cutting), +30.88 m at the owner's point,
+31.45 m at the end. Terrain grade along it: median 15.2 %, p90 31 %; the cap is 8 %.

Tile: 4,429 ways / 60,594 stations; 19,531 (32.2 %) off the terrain by > 0.5 m,
6,074 by > 5 m, 547 by > 20 m, worst 45.44 m. Other tiles on disk: +17-097 77 %
clamped, worst 196.8 m; +16-097 186.6 m; −13-077 174.1 m; +46+006 121.6 m (vector-step
number, tile aborted before the mesh).

## Mechanism — RULED IN: the longitudinal road clamp

`O4_Vector_Utils.py:1664 cap_lipschitz_profile` ← `:1942 clamp_road_network` ←
`O4_Vector_Map.py:2190` (`include_roads`). It returns the mid-profile of the
cap-Lipschitz majorant/minorant: where terrain is cap-infeasible over L the deviation
`(|Δz| − cap·L)/2` is split into a CUT at the high end and a FILL at the low end.
Offline re-run on the sidecar arrays reproduces the shipped profile bit-exactly at 0.08.

| cap | way 435 max | tile > 0.5 m | > 20 m | tile max |
|---|---|---|---|---|
| 0.08 (shipped) | 33.86 m | 19,531 (32.2 %) | 547 | 45.44 m |
| 0.12 | 22.66 | 12,921 | 42 | 23.91 |
| 0.15 | 15.80 | 9,183 | 11 | 21.20 |
| 0.20 | 13.10 | 5,136 (8.5 %) | 0 | 17.01 |
| 0.30 | 8.22 | 1,703 | 0 | 10.02 |

Contributing: `road_is_too_much_banked` (`O4_Vector_Map.py:2024`) admits every way
touching `apt_array` unconditionally; the airport road feed covers the 2 km-margin
INSET BOX = the whole island (4,342 of 4,429 clamped ways: service 1,990,
residential 1,714, track 423 …). The cap read (`O4_Cfg_Vars.py:23`) is the airside
`service_road` value applied to every OSM class.

Transmission, not cause: RULINGS 2026-09-13cp (`O4_Mesh_Utils.py:2381`) — ribbon
nodes keep their authored (= clamp) altitude as Dirichlet, so the excursion renders
faithfully. Pre-13cp A/B not run.

RULED OUT: two-surface mismatch (clamp and mesher both read `tile.dem.alt_vec` /
`.alt`); airport smoothing (mask-confined, ~237 m radius, site 1.1 km away, and the
inset bake overwrites it); inset seam (60 m feather works: residual mean −0.045 m,
max 1.487 m).

Since when: `e80ebd97` 2026-08-31, RULINGS 2026-08-31b ROAD PROFILE LAW (8 % clamp,
"a road may LIFT or CUT terrain"); 13cp/13be 2026-09-13 made it render and made the
clamped ribbon the sole road authority off the patch.

Discontinuity ranking at the site: clamp ≈ 31 m ≫ base-vs-inset interior ≈ 4 m ≫
inset seam ≤ 1.5 m ≫ smoothing 0.

## Fix shape (words)

1. Deviation budget: the profile stays within `dem ± B`; the cap yields where they
   conflict (`cap_lipschitz_pin_envelope` is the same shape).
2. Per-highway-class cap instead of the airside service-road value.
3. Scope the unconditional admission to the patch neighbourhood, not the inset box.
4. No road↔terrain lateral feather exists: the ribbon is `lane_width` wide with raw
   terrain immediately outside.

One confirming run: a +17-063 tile rebuild with a relaxed cap (vector 48 s + mesh 26 s
+ masks/DSF).
