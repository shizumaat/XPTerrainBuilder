# #1336 inland ponds drawn as holes: findings (lane lpond, 2026-10-26)

Site: the owner's pond at **-41.333237416, 174.813714740** (tile -42+174,
about 1 km east of the NZWN runway). The owner's build is engine 1.50.1874,
2026-10-25, on app defaults (`~/X-Plane 12/Custom Scenery/zOrtho4XP_-42+174`).
Everything below is measured on the written `.mesh` and `.dsf` (DSFTool
`--dsf2text`), not on the plan.

## Site numbers (owner's build)

| quantity | value |
|---|---|
| OSM pond | way -9, `natural=water` `water=pond`, 29 nodes, **1,793 m2** (about 60 m across) |
| `min_area` (default 0.001 km2 = 1,000 m2) | pond is 1.8x the threshold, so it is kept |
| lidar inset (NZWN_newzealand1m, LINZ 1 m) | inside the pond p10/p50 6.42/6.50 m, shore 6.99-7.69 m (p50 7.31): a 0.8 m return dip, no pit |
| mesh/DSF water surface | 108 interior + shore `terrain_Water` vertices, **7.08-7.12 m** (spread 0.04 m) |
| DSF `sea_level` raster (bed) under the pond | **0 m** (donor value; `elevation` raster there 9-10 m) |
| DSF water vertex depth ratio, before | **0 on the 29 shore vertices, 1.0 on every interior vertex**, the first one 0.7 m off the shore |
| drawn depth, before | 0 m at the shore, **7.1 m from 0.7 m off the shore inward**: a pit with walls about one triangle wide |

## The five questions

1. **In the OSM water layer and in the mesh as water?** Yes. The pond is way
   -9 in `-42+174_water.osm.bz2` (`natural=water`, `water=pond`), it is in
   the `.poly`, and the DSF carries it as `terrain_Water` plus the
   `_water_overlay.ter` orthophoto overlay; no land triangle lies inside it.
2. **One flat surface at shore level, or a size threshold?** The surface is
   flat: `water_smoothing` (10 mean passes over inland water triangles,
   `O4_Mesh_Utils`) levels it to 7.08-7.12 m against a lidar shore of
   7.0-7.7 m. The only size rule is `min_area` (1,000 m2): smaller ponds are
   not water at all and the imagery drapes on the DEM. This pond is above it.
3. **Does the DEM or a lidar inset cut a depression?** The 1 m lidar reads
   the water surface 0.8 m below the shore (6.4-6.5 m), and the smoothing
   lifts it to the shore. The mesh has no hole.
4. **Do sea bathymetry or masks apply to inland water?** The masks do not:
   `compute_depth_ratio_bounds_from_masks` reads distance masks only for sea
   vertices, and `distance_masks_too` is off by default anyway.
   `masks_use_DEM_too` and `masks_width` shape mask alpha only. The **DSF
   `sea_level` raster does apply**: X-Plane 12 draws the bed of a
   `terrain_Water` vertex at its depth ratio times the depth from the
   mesh's water surface down to the raster. The donor raster is 0 m under
   this pond (the `min(bathy, elevation - 2)` guard leaves 0), so the drawn
   depth is the pond's whole 7.1 m height above sea level. Inland vertices
   have no distance mask, so `set_depth_ratio` gives them ratio 1 the moment
   they leave the shore. `recut_water_tris` puts that first vertex half an
   edge off the shore. The result is the hole the owner saw: a flat surface
   with a 7 m bed under it and a bed wall one triangle wide on every side.
   Upstream's own hint for `distance_masks_too` names the class ("avoid steep
   walls close to piers or rocks"), but for the sea only.
5. **Census of inland-water readers (RULINGS 2026-08-30l).**

| pass | reads inland water as | touched by the fix |
|---|---|---|
| `O4_Vector_Map` water ingest (`min_area` filter, `WATER` seeds into `.poly`) | polygon in, small bodies out | no |
| `O4_Mesh_Utils` post-process (`water_tris` smoothing, `water_valued` shore datum over INTERP_ALT) | mesh altitude of the surface | no (already flat) |
| `O4_Mask_Utils` (`build_water_pre_mask`, `inland_shore_feather_m`, `use_masks_for_inland`) | mask alpha, feathered shore | no |
| `O4_DSF_Utils.remap_water_tri_type` | DSF class 1 inland / 2 sea | no (its classes are the input) |
| `O4_Bathymetry.recut_water_tris` | splits coast triangles so each has an off-shore vertex | no (its geometry is the input) |
| `O4_Bathymetry.compute_depth_ratio_bounds_from_masks` | sea vertices only | no |
| `O4_Bathymetry.set_depth_ratio` (4 call sites in `O4_DSF_Utils`) | per-vertex depth ratio of all water | **input changes for inland-only vertices** |
| DSF `sea_level` raster (donor copy / splice / synthesis) | the bed | no |
| auto_patch_v2 water (`constraints/water.py`, `planar/shore.py`, `geom/water_level.py`) | airport patch shore/levels | no |
| `airport_inset_water` hydro-flat scan | retired 2026-07-26, no effect | no |

## Rule (phase 2)

An inland water vertex's depth ratio ramps from its own shoreline the way
the sea's ramps from the coastline: `node_bathy` = its distance to the
nearest LAND-INLAND shore edge in ZL16 pixels, capped at 255. That is the
unit `distance_masks_too` writes, so `set_depth_ratio` is unchanged and full
raster depth is reached 25.5 / `ratio_bathy` ZL16 pixels off the shore
(45.8 m at -41 deg). That is the same as the sea's ramp, and it adds no new
constant. Shore vertices keep ratio 0. A vertex that touches the sea keeps
the sea's rule. With `use_masks_for_inland` the inland class is promoted to
sea, so nothing changes. The mesh is not touched: the surface was already
flat at the shore.

`O4_Bathymetry.shore_segments`, `O4_Bathymetry.inland_depth_from_shore`, one
call in `O4_DSF_Utils._build_dsf_body` after the mask bounds. Cost is 0.12 s
on the whole of -42+174 (11,649 inland vertices, 2.88 M triangles).

Owner's mesh replayed through the stage (before, then after): the 29 shore
vertices stay at 0. The 17 interior vertices go from 1.0 to 0.10-0.31, so
the drawn depth goes from 7.1 m everywhere off the shore to 0.7 m at 0.7 m
off the shore and 2.2 m at the centre (11 m off the shore). A 1 km lake
still reaches its full depth past about 46 m off the shore.

## Closing build

`build_airport.py NZWN --tile -42 174` would not run as briefed. The DEM
frame is cold (2-3 of 38 approach-ring cells unanswered), and the
`--refresh-data rings` run was refused by the session's permission
classifier. So the closing build is step 4 alone (tag `lpond-1336-dsf2`,
`--steps "4 tile" --allow-degraded-dem`, rc 0, 59.5 s, shared repo
unchanged), over a lane-local copy of the owner's own
`.mesh/.node/.poly/.alt/.apt/.cfg`. The DSF stage is the only thing this
fix changes, and the degraded frame does not reach it, because step 4
reads the donor rasters and not the DEM.

Written DSF, owner build then this build, over the whole tile: 188,161
`terrain_Water` vertices both ways, **0 elevations moved**, `sea_level`
raster byte-identical, **10,608 depth ratios lowered, none raised**. At the
pond the mesh is 7.08-7.12 m before and after. Each interior vertex's
ratio and drawn depth change as follows:

| m off the shore | ratio before -> after | drawn depth before -> after |
|---|---|---|
| 0 (29 shore vertices) | 0 -> 0 | 0 -> 0 m |
| 0.7 | 1 -> 0.100 | 7.09 -> 0.71 m |
| 4.0-5.5 | 1 -> 0.118-0.157 | 7.1 -> 0.83-1.12 m |
| 6.6-7.7 | 1 -> 0.196 | 7.1 -> 1.39 m |
| 8.8-11.2 | 1 -> 0.235-0.314 | 7.1 -> 1.67-2.22 m |

## Not settled here

- **Sim read** is the acceptance: the X-Plane 12 bed model above
  (ratio times surface-to-raster) is read from the engine's own encoding
  and upstream's notes. It was not observed in the sim.
- The raster bed under small inland water is still the donor's (0 m here),
  so a pond far above sea level still reaches its full height as depth past
  46 m off the shore. Whether inland water wants a bed tied to its own
  surface (for example surface minus a fixed depth) is an **owner question**.
  This fix only removes the wall.
- `recut_water_tris` files a barycentre node under its triangle's CLASS
  (1/2), not the class bit (2/4). So a sea barycentre is skipped by
  `compute_depth_ratio_bounds_from_masks` (it tests bit 4). That is
  inherited upstream behaviour and was left alone. The new code reads the
  classes from the triangles.
- Ponds under `min_area` (1,000 m2) are still not water.
