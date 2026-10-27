# #1305: mesher-inserted vertices inside graded faces on tile -13-078 (lane lmisc)

## Verdict

**No engine defect. The issue's numbers come from the instrument.** Every
mesher-inserted vertex inside a graded face sits on that face's own
surface within −0.16 to +0.46 m. Inside faces whose ring is planar, the
worst is 0.04 m. The −5.83 m of the issue is a vertex on a groundside
pavement strip beside a building pad. Its face reads +0.00 m there. An
unconstrained Delaunay over ALL graded vertices blends that strip with
the pad's ring across the step.

## Build

`build_airport.py SPJC --tile -13 -78 --refresh-data dem` on main
`2184b16df`, tag `SPJC_20261026T193355`. rc 0, 482 s, shared repo
UNCHANGED apart from the authorised refresh ledger lines (rings +0 ~4,
dem +0 ~2). Frames: `.harness/frames/lmisc/Data-13-078.mesh` and
`SPJC.graded.json` (registered, kinds mesh / graded).

The mesh step reported 45,306 of 123,728 INTERP_ALT triangles inside the
patch rings, 3,704 ring-segment splits and 67,956 ribbon nodes in the
Dirichlet set. 51 free interior vertices were interpolated.

## The instrument

*Truth per face* is the only interior surface the patch states: the
face's ring and holes as written in `SPJC.graded.json` / `SPLP.graded.json`.
Each face is triangulated by a constrained Delaunay of its own vertices
(`shapely.constrained_delaunay_triangles`). A mesher vertex at index ≥
the input-node count, inside an INTERP_ALT triangle of `Data-13-078.mesh`,
is read by barycentric interpolation in the CDT triangle that holds it. A
point inside several faces (nested pads) is read in the smallest one.
Planarity is the max residual of a least-squares plane through the
face's ring vertices.

*The issue's instrument* is a linear interpolation over an unconstrained
Delaunay of every graded vertex of the two airports.

| set | n inside a graded face | vs the face's own CDT | vs the unconstrained Delaunay |
|---|---|---|---|
| free mesher vertices (not on a ring) | 40 | 0 > 0.5 m, range −0.16 .. +0.28 | 0 > 0.5 m |
| all mesher-inserted (ring splits too) | 2,720 | 0 > 0.5 m, 0 > 1 m, range −0.16 .. +0.46 | **172 > 0.5 m, 78 > 1 m, range −6.39 .. +3.78** |
| — of them in planar faces (ring residual < 5 cm) | 700 | worst +0.04 | — |

4,053 mesher vertices in INTERP_ALT triangles lie in no graded face.
They are levelled road ribbons outside the patch, where R18-1c applies.

The worst rows of the issue's instrument, read against their own face:

| vertex | lat, lon | face | Delaunay | own face |
|---|---|---|---|---|
| v121064 | -12.0087595, -77.1272086 | tunnel_ramp (groundside) | −6.39 | −0.00 |
| v121266 | -12.0199712, -77.1293101 | tunnel_ramp (groundside) | −6.12 | −0.00 |
| v123735 | -12.0286304, -77.1033901 | facstrip:building18:2 (groundside pavement) | **−5.83** | +0.00 |
| v122889 | -12.0292818, -77.1154462 | building5 pad (airside) | −4.04 | +0.00 |
| v120948 | -12.0229956, -77.1070366 | service road small_roads:-6207 | +3.78 | −0.00 |

Every large reading is a vertex on a ramp, a pad or a strip beside a step.
There the unconstrained triangle spans two faces at different levels.
The same site (-12.0286304, -77.1033901) read −5.44 m on the issue's
mesh, build `SPJC_20261024T064246`.

The residual 0.1–0.3 m on free vertices is in NON-planar faces: pav40
(apron, ring residual 0.85 m) and service road -7331 (1.82 m). There the
patch states no single interior surface. The R18-1b harmonic extension
and the face CDT are two lawful interpolations of the same ring, and they
differ by less than the 0.5 m ground bar. The uniform-weight Laplacian is
not exactly linear-precise. Over the 207 free vertices of the 10-24 mesh,
a cotangent-weight solve differs from it by at most 0.69 m, and inside
planar faces the measured effect is 0.04 m. No change is warranted.

The tile north edge (lat −12.000000) carries the largest ring-split
readings (+0.46). Those vertices are clamped to the tile boundary (#1296)
and take the boundary value.

## Nothing changed

No engine edit. If a later round wants this read again, the face-CDT
instrument is the right one, and it is not in `tools/` yet (see the lane
report).
