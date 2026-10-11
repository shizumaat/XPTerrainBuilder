# connect549 — notes (implementation of RULINGS 2026-10-10n/10o at the KCLT garage group; supersedes §64 as written by level549)

Scratch `<scratchpad>/connect549/` (c1..c5). Branch `claude/connect549` off main b7505552d.

## Step 1 — THE CONNECTION AT KCLT (c1/c2/c3/c5 on plan sw11 v13 + owner's 1.0.387 graded + capture valley2)
* building88 (hourly deck) <-> terminal pads: **125.9 m gap, NOTHING spans it** (no part of any unit within 8 m of both;
  nearest part 22 m from the terminal / 8 m from the deck is an 89 m2 canopy). The terminal's own elevated roadway
  decks (`paredes_8` 19,324 m2 base 6.9, `suelos_interiores` 9,182 m2 base 7.8, `paredes_5` 7,147 m2 base 11.3)
  join building75 / 81 / 83 / the plateau pieces — component 0 — and stop short of the deck. OWNER'S PREMISE
  "the large garage connected to the terminal" is NOT in the pack geometry — FINDING for the master.
* The deck IS connected to the two outer garages: covered walkways `paredes_12` comps 296–303 (5.3 x 68 m), 663–666
  (9.5 x 37 m), 679–682 (4.5 x 36 m), 924 (7.9 x 29 m): h 1.86 m, one per storey at base 2.38 / 5.70 / 9.03 / 12.34 m,
  footless; plus their ground columns (`paredes_12` 203/218: 1.0 x 2.3 m, h 6.0, footed). Component 7 =
  {building86, building90, building88} (c3). Today's design cluster `unit:31#1117` (5 members, 141 bodies, footed 63)
  already chains all three garages (through the columns) but its outline is in 10 pieces (gaps 0.50–1.12 m between
  the column pieces, 4–35 m otherwise) because the walkways are THIN (h 1.86 < chain_min_height_m 2.5) -> leaves
  (§16g (10) (4)), not in the cluster, their rings not in the union; each piece is then its own pad and plane
  (§16g (10) (5)) and seats alone: /2 (deck) 223.21 by a soft term, /0 /4 at their DEM. 09-11i ("one pad across the
  footprint union") is the law that fails here; 08-27's split never fired (no pavement touches: no grade violation).
* (B) base plates (10o) in unit:31: 18 plates / 61,026 m2 — `suelos_interiores` comp 45 (36,377 m2, 238 x 515 m,
  h 0.95, 37 % inside the pads) and `techos_1` comp 8 (23,162 m2, 63 % inside building75): the terminal's forecourt
  slab = object-drawn roads/lots where the toll plaza stands (+4.5 m float). BETWEEN the outer garages: no base
  plate (the only candidates are 1.6–3.5 m kerb strips and an 89 m2 canopy) -> the outer garages are served by no
  pavement in the pack; their seat is their own ground (10n (2)).
* Population (c3, 7 airports; connectors = elevated parts chaining pads): HECA unit:42 component 0 links pads 147/133/
  31/38/13/33 (71–93 m) via `concrete_3` 88.7 x 1160 m plates (h 1.37, base 8.3) and `metal_blue` roofs 69 x 120 m;
  unit:43 component 829 = T3 building4 (101.79) + building6 (92.03) + building7 via 148 x 256 m plates — the 14ah
  precedent (floor plates between buildings) — a connector rule MUST exclude plates: KCLT's walkways are 4.5–9.5 m
  wide, HECA's linking plates 69–148 m: a natural gap [9.5, 69] m. OTHH: unit components all within 0.06 m (flat).
  SPJC 1 unit, CYXY 0, KASE 0.

## Step 2 — the repair site and arm A (branch baf681d99, merged with origin/claude/kclt546 a143765ba -> 6b34588af)
* Site: `constraints/cluster_pad._plane_groups` read each outline PIECE `<cid>/<k>` of one cluster as its own plane
  (§16g (10) (5)); 09-11i says the welded group takes ONE pad across its footprint union. Fix: pieces of one cluster
  are re-united into one plane entry unless a piece is pinned (fronts airside — `pads.pad_fronts_airside` — or is a
  HELD block). Twin `tests/auto_patch_v2/test_connect549.py` (4 tests); the four covering files 62 passed.
* ARM A (KCLT valley2 capture, --from classify --emit --verify): the three garages are now ONE plane — but at
  **223.0–223.4 m**, not their ground: building86 222.99–223.37 (rim z-DEM +4.6..+5.3), building88 223.09–223.14
  (+3.8..+5.1), building90 222.99–223.45 (+0.9..+5.1). Airside movers vs base 0 / 14,894; the terminal pads
  unchanged (building75 222.44, 84 222.70, 92 223.67). So the soft term that held piece /2 at 223.21 now holds the
  merged group there; it is NOT the §9b DEM datum (the group's rim DEM means 218.2–219.5) and NOT a HELD block
  (the capture's 73 HELD refs do not include the garages). Attribution arm A2 (`--solved-out` + `--why-at`
  building86 / building88) running. Until it is named, the fix is NOT the owner's outcome for the outer garages
  ("seated lower"): STOP point if A2 does not name it.
* #547 (kclt546 Finding 2): c3 COMPONENT 0 of unit:31 = {building75 (541 bodies), building81 (89), building83 (3)}
  joined by 829 elevated parts — the terminal's road decks (`paredes_8` comp 23: 106 x 312 m, base 6.93, h 1.07;
  comp 115 52 x 263 m; `suelos_interiores` comp 1 48 x 301 m base 7.8) = class (A) connectors. Connected, and BOTH
  pieces are held by airside at different levels (222.44 / 221.75, 36.6 m of apron between): the 09-11i
  "infeasible -> long-span exception" / 08-27 split case — the group keeps its two held levels with the 0.69 m
  step AT the link, and the object side must seat per piece (`plan_unit_datums` one-zero is the site). Not
  implemented here (design in §64 (3) (e)).
