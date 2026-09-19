# BETA2 CYXY-2 / CYXY-3 — §28 (6) OPTION C: the pad's AIRSIDE-FRONTAGE datum

Owner RULINGS 2026-09-18c (1), verbatim model: "Building pads are seated
based on their airside frontage, then we leave a gap" — so §28 (6)'s
`pair_dem_step_m` becomes

    median dem_z over the groundside face's FRONTAGE vertices
  − median dem_z over the PAD'S AIRSIDE-FRONTAGE vertices

replacing the pad-RIM median that the arrangement has been free to trim
since `dba32406` (mechanism: `docs/findings/beta2-CYXY-2-3-mechanism.md`).
Fallback for a pad with no airside frontage: an AREA-WEIGHTED DEM over the
pad's own outline, sampling the planar map's own `Vertex.dem_z`.

## Instrument

`tools/pad_frontage_step.py CAP.pkl` (promoted this lane from the previous
lane's `scratchpad/probe28.py` on its second use, RULINGS `7e90032`). It
re-uses the engine's own derivations and re-spells nothing: the pair
population is `pad_frontage_gs._groundside_geoms` + `pads._pad_polys` +
`pads.pad_fronts_airside` + `pad_frontage_gs._airside_pavement_vertices`,
and the PAD'S AIRSIDE FRONTAGE is `pads.pad_frontage()`'s own contacts
restricted to `role_side(law, role) == "airside"` — the same `_fronting`
relation §20 seats the pad on, so the two directions cannot disagree.

Captures taken on this branch off `main 0bac9241` (the `--capture` pickling
repair `2dff85c2` is what makes this readable at all — the previous lane
had to stub `pickle.dump`): CYXY 7 s / 4,412 vertices, LEMD 220 s / 21,533,
HECA <see below>. `[guard] shared repo UNCHANGED` on every capture.

## The population, both quantities (production DEM, the engine's own frame)

`frontage_radius_m` 3.0. OLD = frontage median − pad RIM median (the
shipped quantity); NEW = frontage median − pad AIRSIDE-FRONTAGE median
(option C); FB = the fallback, frontage median − area-weighted DEM over the
pad outline.

| airport | groundside face (role) | pad | OLD m | **NEW m** | FB m | airside-frontage verts |
|---|---|---|---|---|---|---|
| CYXY | `pav4` (parking_lot) | `building9` | 0.861 | **+4.192** | 2.249 | 7 |
| CYXY | `dsf:pol129` (groundside_pavement) | `building10` | 0.915 | **+3.283** | 1.532 | 3 |
| CYXY | `pav29` (service_road) | `building1` | 0.018 | **+0.047** | 0.031 | 5 |
| CYXY | `pav29#2` (service_road) | `building1` | 0.053 | **+0.082** | 0.066 | 5 |
| LEMD | `route2` (service_road) | `building26` | −0.753 | **−0.049** | −0.593 | 1 |

CYXY `building9`: frontage median 698.300, rim median 697.439, AIRSIDE
frontage median **694.108** — the pad is seated 4.19 m under the lot that
fronts it, which is exactly the owner's 13l item 1 reading ("cut into the
hillside, the lot a storey up"). `building10`: 699.533 / 698.618 /
**696.250**.

## THE 13o-ERA LEMD PAIRS NO LONGER EXIST IN THE RELATION

The law comment's population (`emit.toml:527-538`) lists LEMD `building4 →
pav124` twice, `building4 → route3/6` and `building12 → pav70`. **None of
them is a §28 pair on this tree.** `pav124` is now `role = apron`, i.e.
AIRSIDE (`role_side` airside) — it is `building4`'s §20 frontage, not a
groundside neighbour — and `pav70` / `route3` / `route6` carry no face at
all. Measured directly: over LEMD's 34 airside-fronting pads and 56
groundside faces, only FOUR pad/groundside polygon distances fall under
30 m, all of them `building25`/`building26` against `route2` and a bridge
deck; `building4`'s nearest groundside face is beyond 30 m. So the LEMD
arming the brief required could not be read as such — and the option-C
frame is what dissolves it: a pad's own airside frontage IS its datum, so
the `pav124` pair 13o/12r ordered graded is now stated by §20 and not by
§28 at all.

## Arming under option C

Sorted: **−0.049, 0.047, 0.082 | 3.283, 4.192**. The population separates
cleanly and IN THE RIGHT ORDER — the two CYXY hillside lots at the top, the
graded pairs at the bottom — with a gap of **3.20 m** (0.082 → 3.283),
against the 0.23 m gap the shipped rim-median frame left (3.00 → 3.43).
Centre of the gap: (0.082 + 3.283) / 2 = 1.6825 → **`frontage_step_max_m =
1.7`**.

CAVEAT, stated not decided: the gap is wide because the population is
small, so 1.7 is under-constrained on the HIGH side — no measured pair
stands between 0.09 and 3.28 anywhere in this population. The value is the
gap centre the ruling asks for; a pair landing in that band on an unbuilt
airport would be held as a terrace under it and graded under 3.2.
