# #1197 — the retaining-wall classifier misfires on a fence and on glass (lane lwalls)

## Attribution (dry, classify-only, `airport/wall_class.wall_class_components` on registered captures)

Both misfires are `retains = True` components (`_retains_its_height`: the 90th
percentile of the DEM step across the outline lies in 0.75–1.25 x the height).

| component | h | plan width | step across (90th pct) | why it passed |
|---|---|---|---|---|
| LEMD `LEMD_OBJ-T4STower_(c)_Sim-wings-LEMDzaun.obj` comp 0 (40.491703, -3.569284) | 2.39 m | 0.19 m | 2.40 m | a fence 739 m long; the fence word table is English only (RULINGS 2026-09-29h, Q-72b). It is not a line object either: its authored y extent is 6.99 m (it is authored down the terrain), over `line_object_max_h` 6.0 |
| KATL `Vidrios.obj` comp 17 (33.640763, -84.419664) | 12.51 m | 0.10 m | 10.97 m | a band of glass whose base stands 3.00 m up its object (`base_y` 3.00, member minimum 0.00): the partition judged it ELEVATED (no feet, RULINGS 2026-09-09s (2)). Its ring reaches 12.5 m out and reads the slope beside the terminal |

Population of `retains = True` over 41 registered captures: 29 components. The
ELEVATED ones (no feet) are KATL `Vidrios` comp 17, EDDF `Cyan_2_Pillar` comp 44
(base 6.50 m), KMCI `white.obj` comps 15/16/44/45 (bases 4.54 / 8.68 m: upper
storeys of a garage), KCLT `Charlotte_Airport_002_ALB` comp 200 (5.51 m) and
`paredes_8_charlotte` comp 24 (4.80 m). Every KATL `muro_*` wall stands on the
ground (4 feet each).

Refuted on the way (not shipped): reading a line object's height LOCALLY
(`contact.solid_height`) would make the LEMD fence a line object, but it turns
63 more resources over the captures into line objects, OTHH bridge decks and
terminal roads among them. A sheet test (plan width under the decal thickness)
catches the glass and the fence but also EDDF `Tunnel_3.obj` comp 5, a 5 m
tunnel-approach wall drawn as one sheet.

## Rule

1. A component that does not stand on the ground — the partition's ELEVATED
   part, `Part.feet` empty (RULINGS 2026-09-09s (2)) — never RETAINS ITS OWN
   HEIGHT: a wall holds the ground at its foot, and an elevated part has no
   foot. Geometry from the object's own structure; no name.
2. The fence word table of 29h is read in the general languages the installed
   packs use: `zaun` (de), `cloture` / `clôture` (fr), `recinzione` (it),
   `hangrao` (vi, *hàng rào*), `staket` (sv), `baranda` (es, railing),
   `gelaender` / `geländer` (de, railing), `ringhiera` (it, railing), `guardrail`
   (en). Precedent: `NOT_WALL_RESOURCE_WORDS` (29h). Words that are also common
   name parts (`valla` in Vallarta / Valladolid, `cerca` "near") stay out.

## Acceptance

- LEMD T4STower `LEMDzaun` is not wall-class; KATL `Vidrios` comp 17 does not
  retain; the four KATL `muro_*` walls still retain (dry, captures).
- Twins: an elevated wall-shaped part with a matching step does not retain; a
  `…zaun.obj` resource is not wall-class.
