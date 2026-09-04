# auto-patch-v2 M1d — the taxi-name rule (RULINGS 2026-09-04z-1)

Lane `lane/v2taxiname`, 2026-09-04, off main `99765929`. Files:
`classify/rules.toml` (`[taxi_name]`), `classify/rules.py` (typed record),
`classify/evidence.py` (`taxi_name_match`, `apron_named`),
`classify/sources.py` (a taxi-named source is never a strip or a lot),
`classify/roles.py` (the face rule), `classify/open_default.py` (docstring),
`classify/explain.py` (prints the token match), `tests/auto_patch_v2/test_taxi_name.py`.

## The rule

`[taxi_name]`: `tokens = ["taxiway", "twy"]` (whole words, case-insensitive,
in the apt.dat 110 description), `unauthored_names = ["new taxiway"]`,
`designator_max_len = 3`. A matching source is taxi evidence: at the
source stage it is `open` (never strip / lot — reason `taxi by name
'taxiway' (B) (04z-1)`); at the face stage a face on it that NO taxi
centreline touches and that holds NO startup is `junction` (whole face,
no proximity split), lettered by the nearest through-route within the
proximity band like any minted junction, evidence `taxi_name=taxiway
taxi_name_designator=B`, `stats.taxi_named`. Strength order: touching
1202 chain (corridor / junction, its letter) > startup on the face
(apron) > **taxi name (junction)** > open default (lot / groundside).
Demoted by the touch-chain law (06-09) it is `groundside_pavement`,
never a lot. An apron token in the same description is senior
("Taxiway E apron", CYXY pav11-15, is the apron a taxiway crosses — 03j).
`explain` prints `TAXI NAME 'taxiway' designator B (04z-1)` on the source
line and the evidence keys on the cell line.

## What the data said (attribution before fix)

* **"New Taxiway N" is WED's default description, not the author's
  word.** All 31 CYXY 110 polygons carry it — including the owner-ruled
  lots of shape 69 (`pav4` "New Taxiway 5") and the shape 161 service
  road (`pav29` "New Taxiway 41", `pav30` "New Taxiway 40"). The ruling's
  two CYXY examples (`pav1` "New Taxiway 3", `pav2` "New Taxiway 2") are
  the same default. SPJC's `pav1`/`pav2` "New Taxiway 19", `pav44` "New
  Taxiway 18", `pav50` "New Taxiway 30" likewise; its authored names are
  "Taxiway B", "Taxiway Aux B, C, D, E, F, G, Main Ramp, RWY 33 Head",
  "Taxiway V / U / Q / R / L / M".
* **The literal arm (`unauthored_names = []`) regresses 04j/04m at CYXY**
  (classification diff vs main, `(role: m²)` per source): `pav29` "New
  Taxiway 41" service_road 13,976 → junction 12,380 + apron 21,187 (the
  strip boundary no longer cuts; the road dissolves into the apron — the
  04j item-3 class); `pav30` "New Taxiway 40" service_road 6,596 →
  junction 1,461; `pav4` "New Taxiway 5" parking_lot 4,780 →
  groundside_pavement (demoted, name blocks the lot); `pav0` "New Taxiway
  5" service_road 2,073 → groundside_pavement; `pav10` "New Taxiway 9"
  junction 2,460 / apron 759 / service_junction 71 → junction 92 (rest
  absorbed); `pav1`/`pav2`/`pav3` faces absorbed into neighbours (mouth
  cuts gone). SPJC literal arm: no change. So the exclusion ships ON.
* **"Aeronaval" is not a taxiway name.** SPJC's 1202 names are letters
  only (A … V5); `pav3` "Aeronaval" (24,296 m², 63 m wide, 1206 route 137
  through it 33 m, no taxi, no startup within 30 m) lies 11 m from `pav35`
  "Naval Aviation Ramp" and beside the separate airport "Base de Aviacion
  Naval" the DEM prep names: it is the naval base's ramp pavement,
  Spanish *aeronaval* = naval aviation. No token; it stays the 04u lot.
* **`dsf:pol64` has no name.** A DSF page's "description" is its `.pol`
  library path (`lib/airport/pavement/concrete_2D.pol`); 68 m from
  `pav3`, no overlap. Unreachable by any name rule; stays the 04u lot.

## Flips per airport (shipped arm)

* CYXY: **none** (every name is the editor default). `pav1`/`pav2`
  remain parking_lot / groundside_pavement as under 04u.
* SPJC: **none** — the authored taxiway pages carry centrelines and
  stands on every face; `pav3` / `pol64` remain parking_lot.
* Classification diff vs main at both airports: empty (role, ref, area).

## Closing builds (harness, `--engine v2`, ledgered, tree `b830441a`)

* CYXY `CYXY_20260904T133813` body `634720df0a3b`, artifact ledger
  `6d8d337db14d`, 4.9 s, optimal, verify rows 0; census **0/0** PASS
  (key `df96f68da7c9`).
* SPJC `SPJC_20260904T133813` body `a00521d8d1cb`, artifact ledger
  `acc7c7858082`, 53.5 s, optimal, v2 verify 2 `adjacent_ground_tear`
  (pre-existing, not a census family); census **0/0** PASS — unchanged
  from main after v2caps (04y `e8992a9dbdd8`); the 04z "4 junction rows"
  are already gone on main, nothing here to attribute to v2junction.

## Twins (`tests/auto_patch_v2/test_taxi_name.py`, 5)

Matcher table (authored / default / apron-senior / Aeronaval / plural); a
"Taxiway K" page with no centreline that a route reaches → junction,
airside, evidence + explain text; "New Taxiway 7" and "Aeronaval" pages
→ lot; the synthetic parallel named "Taxiway P" → identical roles to the
unnamed tree, primary_parallel at letter D; a named page holding a stand
keeps apron on the body. `test_classify`, `test_classify_lots`,
`test_round3`: 15 passed.

## Open questions (owner)

1. `pav1`/`pav2` at CYXY: with the default name refuted as evidence they
   carry exactly the evidence of the ruled lot `pav4` (WED default name +
   a 1206 route). Lot under 04u, or aircraft pavement by the owner's sim
   read? If the latter, the evidence is something other than the name.
2. SPJC names its aprons "Ramp" ("Main Ramp", "Domestic Ramp", "Naval
   Aviation Ramp" …); `lot.apron_name_tokens = ["apron"]` misses all of
   them. Add "ramp"? Not done here (scope).

## Not done

No merge; no five-airport sweep; no `--base-arm` control rebuild (the
classification diff is empty, the only stage touched); no v1 imports, no
env reads; every file ≤ 1,000 lines (roles.py 782).
