# CYXY INTERP_ALT flood leak (+60-136 tile mesh) — owner sim read 2026-08-28

Owner read of the fresh +60-136 tile (app 1.0.264, built 07:42): "terrain not
following the natural plateau edge — extends out too far into the town, then
drops steeply, then rises again to a really elevated road along the river."

## Attribution (verified this session, all three layers separated)

- The CYXY patch is INNOCENT: its emitted node altitudes match the HRDEM
  lidar 0.0-0.3 m at the east edge.
- The elevation data is INNOCENT: the tile's written `Data+60-136.alt`
  matches the HRDEM tif to 0.1 m at every probed point (extent convention
  [-0.01,1.01]², side 7345).
- The MESH contradicts its own .alt by ±60 m: bench ~700 extended ~500 m
  past the plateau edge (real 643 in town), displaced cliffs, west hill
  765→704.
- Cause: the Triangle4XP regionplague INTERP_ALT flood LEAKED. Attr-8
  triangles: **22,814 spanning lon -136.00..-135.0325, lat 60.6529..61.00**
  (~50×39 km) where patch coverage is ~2×1.5 km. Bounded east by the Yukon
  river's water edges, elsewhere by tile edges — one seed escaped its ring
  and flooded the whole uncut land component. Free interior vertices in the
  flood take `interpolate_free_interior_altitudes`' harmonic patch
  extension instead of the DEM (log: "4815 free interior vertex(es) of 6754
  took their face's interpolated altitude"; 1939 kept their own = the
  no-authored-vertex components).
- Prior art: the VMMC SEA|INTERP_ALT leak (O4_Vector_Map.py ~74-95,
  PATCH_RING_MARKER) — same plague-crossing class, water-flood direction;
  this is the INTERP_ALT-flood direction escaping the patch rings.

## Repro (deterministic, cheap)

`venv/bin/python tools/run_tile_mesh_only.py 60 -136` in the main tree
reproduces byte-for-byte the shipped mesh's attr population
({0:1367220, 1:52169, 8:22814, 4:1951, 9:109, 32:18, 16:231}) and leak
extent. NOTE the run ends REFUSING-to-report on a guard-blocked
`N60W136_airport_insets/index.json` write (inset fetch metadata refresh) —
irrelevant to the leak topology, fine for iteration; do not quote its
numbers as production frame.

## Work

1. INSTRUMENT FIRST: name the escaped seed / lost ring edge. Candidates:
   a seed from `include_patches`' 562 per-face seeds or
   `seed_interp_alt_subcells`' 16 sub-cell seeds landing in a face whose
   boundary lost bit-8 marking at CDT insertion (insert_way intersection
   cutting / degenerate-edge drop). Diagnostic: flood-fill the rebuilt
   mesh's attr-8 region, find the throat where it exits patch coverage.
2. Fix the sealing (ring edge marking must survive insertion), NOT the
   symptom. A post-hoc "clip flood to patch bbox" is a shield — refused.
3. GUARD: a build-time detector — after seeding, assert every INTERP_ALT
   seed's flood region stays within the patch coverage envelope (or:
   post-mesh, attr-8 area ≤ k × patch coverage area) — loud refusal, not
   silent clip. The VMMC incident got a marker fix but no leak detector;
   this is the second leak of the class.

## Acceptance

- Rebuilt +60-136: attr-8 extent confined to patch coverage (+ road
  ribbons/seawalls as designed); mesh samples at (60.70,-135.05),
  (60.72,-135.06), (60.69,-135.07), (60.70,-135.10), (60.74,-135.05)
  match the .alt raster within mesh-interpolation tolerance (were +58/+58/
  -38/-61/-37 m wrong).
- Escarpment transect at lat 60.7096 follows .alt (bench edge at
  ~-135.057, not -135.052; west hill gradient restored).
- Control: one tile with a healthy patch (e.g. +30+031 HECA or +25+051)
  rebuilt mesh attr population unchanged (or every delta attributed).
- The new leak detector fires on the pre-fix code at +60-136 and is quiet
  post-fix.
