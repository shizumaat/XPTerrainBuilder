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

## Step 1 (cont.) — WHAT HOLDS building88 AT 223.21 (`--why-from base/KCLT.solved.pkl --why-at 35.2242287,-80.9428688`)
v17133 z 223.21, DEM 218.05 (+5.16): binding rows = its own `pads` flat rows only (cap 0 x 119.6 m -> v17122);
"chain trace: no terminal reached — THE OBJECTIVE holds it". I.e. no hard row: building88 is a face of the
TERMINAL's §30 (4) plane group (`constraints/cluster_pad.plane_groups`: "the faces of ONE TERMINAL CLUSTER are ONE
entry", cluster = `airport.placement_family.plan_clusters` of the pack partition = anchor family unit:31), priced as
ONE plane with building75 / 84 / 92, whose level fit is their airside frontage (pav14 plateau 222.44–223.67); a
fronting group carries no §9b DEM datum (`pads.pad_datum_withdrawn`), so building88's own ground (218.0–219.3) never
enters. building90 (--why-at 35.2256079,-80.9459114): v17199 z 218.99, DEM 222.06 at that rim vertex, "FREE, above
its DEM, held by bending alone" = its own §9b DEM datum (its rim DEM 218.07–222.06, mean ~219).

## Step 2 — THE WITNESS POPULATION (p6 / p8 / p8b / p10; seven airports)
* W1 "one anchor family + equal authored base": TRUE of EVERY big pack: KCLT unit:3 (8 `Charlotte_Airport_00N_ALB`
  files, one anchor, 239 walled bodies at y 0.00, 66 pads over 22.5 m of relief), HECA unit:41 (72 pads, 45 m),
  OTHH unit:80 (25 pads). FALSE POSITIVE as a level witness — the engine's standing law (§16c/§16g) re-cuts such
  families per body on relief and the owner accepted it (HECA, 10c).
* W2/W3 "one family at the modal base, chained in plan at gap <= D, pads fronting no airside and with no fixed level":
  KCLT fires at D = 10 m on exactly {building86, building88, building90} (spread 5.10 m, DEM relief 4.07, hull 4.9 ha,
  0 held pads in the chain) and on nothing else over 0.5 m at KCLT except hangar rows already within 0.8–0.9 m
  (unit:3 b36/37/40, b78/80) and the FuelFarm tanks (unit:58, 6 pads within 0.33 m). HECA: unit:41 fires on 10–20
  chains per D with spreads 0.7–7.4 m over relief 1–8 m (rows of small landside buildings on Cairo's slopes) —
  the owner has NOT asked for those to be one level; a plan-distance witness over-fires at HECA. OTHH: flat site,
  every group within 0.6 m (inert). SPJC / KASE / CYXY / NLWF: none.
* W4 THE ENGINE'S OWN WITNESS — the §16g FOOTPRINT UNIT (placement plan `unit_of`, `ground_off` per body):
  KCLT 41 units with >= 2 bodies; 14 with a body > 0.5 m off its own ground, ONE > 2 m: `fu:31:2809@cluster_pad`
  (14 bodies, 10 over 2 m, worst 5.13 m, zero = building88 at 223.21) = THE GARAGE GROUP. HECA 129 / 21 (> 2 m:
  the T3 district fu:40:120 216 bodies worst 10.5 incl. viaduct landings; fu:42:1233 27 bodies 4.53; fu:42:944@ground
  24 bodies 4.04 ...), OTHH 42 / 18 (viaducts, pits), KASE 22 / 17 (two-body @ground pairs on the mountainside,
  3–11 m), SPJC 1 / 0.
  So the DESIGN surface and the OBJECT stage already disagree about the group: the object stage seats all 14
  bodies of fu:31:2809 at ONE zero (building88's 223.21, §16g (2)), the design surface gives them three pads at
  223.21 / 218.99 / 218.11 and raw DEM between. The object unit chains building88's deck to building90 / 86 (plan
  touch 0.5 m through the connecting bodies); the design cluster (`plan_clusters` of the pack partition) chains
  building88 to the TERMINAL instead. Two derivations of "the group" (the census-wrapper defect in geometry).
* Base edge read of the group (p11): building88 rim z-DEM +3.89..+5.22 (28/28 over 1 m); building90 -3.07..+1.12
  (17/52); building86 -0.28..+0.35; the ground BETWEEN the three (hull minus pads, 2.42 ha) DEM 218.03 / 218.23 /
  219.22 — flat, at the garages' own ground. Base floats in the window (seat_feet_census --graded, 112 measured
  bodies): 23 over 0.5 m, 3 over 1 m, 1 over 3 m, worst 5.07 m (`paredes_12 b1` at 35.224214,-80.943764).
