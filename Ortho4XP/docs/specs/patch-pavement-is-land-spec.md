# PATCH PAVEMENT IS LAND — spec (2026-08-10, FROZEN; pre-ship mode)

Author: lead (Fable). Charter: owner 2026-08-10 (VMMC) — "we need a
way to ensure that areas we know are pavement and are in our patch,
do not end up water in the generated tile." Recon measured: VMMC's
taxiways C1/G/H are OSM `bridge=yes` viaducts over real open water
(OSM self-consistent, coastline fresh); 113,414 m² of patch pavement
lies seaward; the built tile carries 263 triangles / 114,406 m² of
`SEA|INTERP_ALT` (attr 10) over pavement. ROOT CAUSE: patch rings
are inserted with marker `INTERP_ALT` only
(`O4_Vector_Map.py:1647-1651`) and `Triangle4XP.c:13545-13549`
floods ACROSS any ring lacking the flood's own bit — an elevation
ring does not stop a SEA flood. PRE-SHIP MODE applies.

## The law

Pavement that is in our patch is LAND. Implementation, two points:

1. **The ring blocks the floods** (kills all three symptoms at one
   point): closed patch pavement rings are inserted with marker
   `INTERP_ALT | WATER | SEA | SEA_EQUIV` (bit value 15) instead of
   `INTERP_ALT` (8) at `O4_Vector_Map.py:1647-1651`. Per
   `Triangle4XP.c:1225` the interior keeps only bit 8, so:
   `O4_DSF_Utils.py:400` (`has_water=7`) reads land — wet texture
   gone; `O4_Mask_Utils.py:956-967` reads land — mask transparency
   gone; `O4_Mesh_Utils.py:188` already exempts INTERP_ALT from sea
   leveling. A patch ring that genuinely encloses water no longer
   floods it — intended.
2. **Belt-and-braces seed withholding** (existing precedent at
   `O4_Vector_Map.py:91` / `_tidal_water_area`): the patch pavement
   union (`patches_area`, already computed at `:1671-1673` and
   returned at `:829`) joins the sea-seed subtractors, so no SEA
   seed is ever planted inside pavement.

THE CUTTER IS THE PAVEMENT UNION, NEVER the flat-site extent or the
aerodrome boundary — VMMC's boundary spans the genuine channel;
drying it would be wrong. (The owner's boundary-master-shape
directive decomposes: flat-site extent = the ELEVATION authority
(landed, phase 2); pavement union = the LAND authority (this spec).)

Record for later (not this spec): patched airports never emit the
RUNWAY/TAXIWAY/APRON attr bits (`O4_Airport_Utils.py:1150-1151`
`continue`) — any future law keyed on those bits is dead at patched
airports.

## Tests (run once)

Synthetic vector-map fixture: a closed patch ring crossing a sea
polygon → sea flood stops at the ring (interior tris carry no water
bit), seed withheld inside pavement; a road (INTERP_ALT, open way)
over water keeps its `WATER|INTERP_ALT` behavior (the 36,410
genuine bridge-road triangles must NOT dry out — regression pin);
mask/DSF classification twins on the attr arithmetic (10→land never;
8→land; 9 unchanged).

## Acceptance

Unit tests once. The owner verifies VMMC in-sim after the next tile
build (expected: C1/G/H render as land at patch elevation, the
channel stays sea). No builds by the implementer.
