# level549 — notes (spec author, #549 common-level group; KCLT garages the witness)

Scratch: `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/level549/`
(p1..p9 probes, `base/` = replay of `frames/valley2/KCLT.pkl --from classify --emit --verify --solved-out`).

## Step 1 — ATTRIBUTION (owner's 1.0.387 KCLT frame = `XPTerrainBuilderData/tmp/auto_patch_v2/+35-081/KCLT/KCLT.graded.json` 2026-10-10 12:24; plan `/tmp/harness/sw11_KCLT.v2/KCLT.rebake.json` v13; DEM off `frames/valley2/KCLT.pkl`)

* The garages are NOT separate objects. They are bodies of the TERMINAL's object files: 20 files
  (`Terminals/paredes_1..12`, `techos_1/2`, `suelos_interiores`, `vidrios_*`) at ONE DSF anchor
  35.221229591, -80.943372339 (plan `unit:31`, heading 355.847) plus a 19-file twin set `-paredes_*`
  at 35.221137083, -80.943364710 (`unit:30`). Every row is plain `OBJECT` (on-ground; the pack has
  0 `OBJECT_MSL`, 2,368 `OBJECT_AGL` none of them these). So the author's level for EVERY body is
  "ground at the anchor + authored y".
* Authored bases (plan parts, grounded walled bodies): building88's 135 walled bodies min -0.034 /
  median 0.000; building90's 39: -0.034 / 0.000; building92: 0.000 (one 4,084 m2 body);
  building86: 0.000 (3 bodies); building84 (terminal north): 0.000 median 1.000 (upper floors);
  the hourly deck itself is ONE 70,405 m2 connected body (`paredes_10` comp 737, base_y 0.000, h 10.93).
  Spread of grounded bases across the garages and the terminal: 0.000 +- 0.034 m (0.357 for one footed body).
  OWNER'S PREMISE TRUE: one authored level, rigid by construction (one anchor), and it is the
  terminal's own ground — DEM at the anchors 220.15 / 219.92 (not a constant, not an MSL row).
* Today's pads (graded.json) and the DEM under them:
  building75 (terminal) 222.44 held; building84 222.70 (fronts pav14 plateau); building85 222.87 (fronts);
  building92 223.67 (fronts `pav14#plateau:building92`; DEM 222.29..228.85 — a 6.5 m hillside);
  building88 (hourly deck, 22,027 m2) 223.21, DEM under it 217.99..219.32, fronts NOTHING;
  building90 218.99 (DEM 218.07..222.06, fronts nothing); building86 218.11 (DEM 218.1..218.4, fronts nothing).
* How the object stage seats them (placement plan `Patches/+30-090/+35-081/o4_v2_placement_KCLT.json`):
  §16g footprint unit `fu:31:2809@cluster_pad of 4 member(s) on pad building88 at 223.21` — 14 bodies,
  INCLUDING the bodies standing over building90 / building86 / raw ground ("own ground -4.58 .. -5.03 m"):
  that is the 4.6–6.3 m float class (f6.27 = `paredes_10` b3 at 35.224181,-80.945802 own ground -4.79;
  f5.56 = b5 -4.58; f5.76 = b8 -4.95). The glass files (`vidrios_*`, "kept: anim") stay whole at the
  anchor row (222.44 via building75) and float the same way. The toll plaza (`techos_1` b3/b4) = "surface at
  the body's zero" / "low-side foot, terrain spread 5.37 m" (lane kclt546's case).
* What holds building88 at 223.21: --why-at pending (replay `base/` done, why running); the §16g (2) rule
  explains the OBJECT side (one zero per unit = the pad most contacts stand on = building88).
