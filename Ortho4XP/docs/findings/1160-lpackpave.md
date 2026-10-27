# #1160 — a custom pack's own draped pavement counts before Global Airports pavement is borrowed (lane lpackpave)

Law: RULINGS 2026-10-20al (1) "pavement is read from the pack's own scenery
where it can be identified; only otherwise is Global pavement borrowed";
2026-10-20bb (invisible gap-filler sheets do not count toward a pack's
pavement coverage); 2026-10-20az (Global-only narrow strips the pack does not
draw are not borrowed); refines 2026-09-15m (spec §44). The fallback half of
20al (borrowed pavement yields to pack walls) and 20ax (a wall cuts pavement,
pack-own and borrowed alike) are #1158, lane lwalls — not this lane.

## Attribution (KATL, capture `l1140/KATL.pkl`, main 901f2f587)

* The Nimbus KATL V3.5 apt.dat carries 0 row-110 rows and one row-130
  boundary. §44 (2) measures coverage on row-110 ONLY, so coverage = 0 and
  the borrow fires in `airport/pack.select_pack` → `borrow.decide`: 20
  Global Airports polygons (6,191,577 m² as a union) are appended.
* The pack DOES draw its pavement: 223 draped `.pol` pages in its DSF
  (`pols/concrete_dirty.pol` 114, `pols/concrete.pol` 98,
  `pols/concrete_groove.pol` 5, `poligonos/concreto_claro_verde.pol` 4,
  `objects/concreto_claro.pol` 2) — 5,386,542 m² as a union, admitted by
  `load.load_with_report` as `dsf:pol*` sources. Their union covers
  5,283,325 m² of the Global union: **85.3 %** — far above the 25 % key.
  Five `poligonos/piso_hangares.pol` pages are gap sheets (§60), not
  sources.
* Why the pack's pages lose: `classify/evidence._dsf_pavements` drops a
  draped page lying ≥ `overlay_fraction` on the apt.dat union (it is read
  as a page painted ON apt.dat pavement) and keeps only its remainder.
  With the borrow, the "apt.dat union" is Global's, so the pack's own
  pages are dropped where Global lies and the Global polygons govern the
  layout — the Global taxiway `pav14` that crosses `muro_concreto`
  (#1139 / #1158) is one of them.
* Root cause: the borrow trigger asks only the apt.dat for the pack's
  pavement; it never asks the pack's scenery. The decision is made before
  the DSF is read (select_pack), so it cannot.

## The rule

§44 (2) AMENDED: the pack's own pavement, for the coverage test, is its
apt.dat row-110 polygons ∪ every draped pavement SOURCE its scenery
supplies — the `.pol` pages admitted as `dsf:pol*` and the §42 object
pavement bodies (`dsf:objpav*`, hard planes included); never the §60 gap
sheets (20bb). `coverage = area(own ∩ global) / area(global)`, the same
key (`[load] pavement_borrow_coverage_max` 0.25). At or above the key the
borrow is WITHDRAWN: no Global pavement, no Global boundary, and the
signature / partition key / patch header carry no borrowed path. Below it
the borrow stands as today (LGAV: its `Ground_*.obj` pages are refused by
§42's layer-group gate, so its scenery adds nothing and it still borrows).
No partial borrow: the Global pavement the pack does not draw is not taken
(20az's 0.88 km² at KATL is exactly Global − pack).

ONE DERIVATION SITE, in two stages of the same decision (`airport/borrow.py`):
`decide` (apt.dat, in `select_pack`, unchanged — it is what DEM prep's
flat-site decision can see) and `yield_to_scenery` (the pack's scenery, in
`load.load_with_report` right after the DSF pages and object bodies are
read, the one place they exist). Nothing downstream re-derives it.

## Consumer census (RULINGS 2026-08-30l)

| # | Consumer | Reads | Ruling |
|---|---|---|---|
| C1 | `borrow.decide` / `pack.select_pack` | apt.dat coverage | UNCHANGED (stage 1). |
| C2 | `load.read_apt` → `borrow.compose` | composes the tentative borrow | UNCHANGED. |
| C3 | `load._own_extent` (DSF admission gate, 1 km) | pavement ∪ runways ∪ boundary, borrowed included | UNCHANGED: it runs before the scenery is known; the borrowed extent is the airport's extent, so the same pages are admitted either way. |
| C4 | `load.load_with_report` pavements / boundaries | the composed tuple | EDIT: when withdrawn, the `global_airports` pavements and boundary are dropped. |
| C5 | `pack.signature` → `SceneryPack.borrowed_*`, partition key, emit header `o4_apt_dat_borrowed`, freshness stat | `sel.borrow` | EDIT (data): the signature is built from the withdrawn decision → `""`. |
| C6 | `LoadReport.pavement_source` / `pavement_borrow_line`, `pipeline/build` `[load]` line | the decision | EDIT: `scenery_pavements`, `scenery_coverage` added; the line names the withdrawal. |
| C7 | `classify/evidence._dsf_pavements` overlay drop | apt.dat union | UNAFFECTED in code; CHANGED BY DATA as intended — with no borrowed union the pack's pages are no longer dropped as overlays. |
| C8 | `flat_site_prep.site_inputs` (DEM prep, #932) | `read_apt` (stage 1 only; no DSF in DEM prep) | UNAFFECTED, recorded: DEM prep's flat-site region still stands on the borrowed Global pavement where stage 1 borrowed. It is a REGION (pavement ∪ runways ∪ boundary ⊕ margin), and at KATL Global and the pack overlap 85 %; KATL is not a flat site. Unifying it needs the DSF in DEM prep — follow-up, not this lane. |
| C9 | #1158 (lane lwalls) wall clip | borrowed / all pavement | COLLISION NOTE: at KATL nothing is borrowed after this change, so #1158's KATL witness `pav14` (a Global polygon) is gone; 20ax makes the clip apply to the pack's own pages too, so lwalls must re-measure on the pack's pages. No shared code. |

## Acceptance (KATL closing build)

1. `pavement_source.borrowed_from` null, `scenery_coverage` ≈ 0.85, no
   `global_airports` pavement in the airport; the planar map's pavement
   faces are born of `dsf:pol*` pages.
2. Zero NEW adjudicated violations against the KATL control at the base sha
   (census through `tools/harness/census.py`), site numbers first.
3. Twins (`tests/auto_patch_v2/test_airport_load.py`): a pack with no
   row-110 whose `.pol` pages cover ≥ 25 % of Global → nothing borrowed; the
   same pages as gap sheets only → still borrows (20bb); pages under 25 % →
   borrows (and the existing §44 twins unchanged).

Build-time impact: one shapely union of the pack's sources and the Global
union per load, only when stage 1 borrowed (KATL: ~0.1 s) — under the 1 %
review floor.

## Measured (lane lpackpave, 2026-10-26)

Captures (registered, `frames.py list KATL`): control
`lpackpave/KATL_base.pkl` (main ec307265a), lane `lpackpave/KATL.pkl`.
Closing builds through `build_airport.py`: lane `lpackpave_KATL` (branch
merged with main 2cc289364; body 5fc910dd7671) and control `lpackpave_base`
(`--base-arm` at 2cc289364, a ledger miss, built; body 5ef38fe4e910).

* Load line: "the pack's apt.dat carries 0 pavement(s) covering 0.0 % of
  Global Airports' 20, but its scenery's 223 draped pavement(s) bring it to
  85.3 % (>= 25 %): the pack's own pavement stands, nothing BORROWED".
* Taxiway + apron + junction faces by source: control 99.0 % Global `pav*`
  (4.95 km²), 1.0 % pack `.pol`; lane **100 % pack `.pol`** (4.36 km²).
  Airside (runway included) 5.97 → 5.14 km²: the 0.83 km² gone is the
  Global-only pavement the pack does not draw (20az).
* The #1139/#1158 wall site: pavement over `muro_concreto`'s footprint
  1,039 → 120 m² (Global `pav14` 917 m² gone; the pack's own `dsf:pol43`
  reaches 117 m² into it), `muro_concreto5` 1,011 → 398 m²
  (`dsf:pol22` 392 m²); the 8.13 m `strip_seam_tear` at 33.63717,
  -84.41709 is GONE. The pack's own residual is #1158's (20ax).
* Census (`tools/harness/census.py`), control → lane: CRITICAL motion
  0 → 0; ADJUDICATED 5,461 → 3,889 (airside_for_acceptance 4,882 →
  3,366); actionable sites 197 → 183; CRITICAL visual 1,223 → 1,618
  (cliff rows 153 → 544).
* NOT MET — "zero new adjudicated violations": 23 actionable sites have
  no same-family control site within 50 m (53 control sites are gone).
  The large ones sit SOUTH OF RUNWAY 10/28 between 33.6198,-84.4324 and
  33.6208,-84.4282: `adjacent_ground_step` 8.53 m, `strip_seam_tear`
  6.97 m, `mid_edge_step` 2.74 m, and the 116-row `strip_transverse` site
  (worst 20.16 m over 51.5 m at 33.61983,-84.43218). There the Global
  block's `pav17` carried two ~25 m-wide strips (15,240 + 15,111 m²)
  beside the runway that the pack does not draw; graded as apron at runway
  level they hid the runway's ~20 m embankment. Without them the runway
  strip (adjacent ground zones 1–2) meets the real slope — the same
  strip-over-embankment class the control carries along other runways
  (worst control row 19.1 m at 33.63414,-84.40886). Smaller new sites:
  `mid_edge_step` 1.21 m at the 10 end (33.62138,-84.44656), `strip_arc`
  1.45 m (33.64609,-84.42454), `transverse` 0.99 m junction (33.64523,
  -84.41675), `within_shape` 0.69 / 0.59 m cross_connector|runway.
  Whether the 10/28 embankment strip is graded or left as the cliff is
  the strip law's question, not this rule's — named for the owner.

## Round 2 — attribution of the 10/28-south sites (RULINGS 2026-10-27r)

Read on the registered captures `lpackpave/KATL.pkl` / `KATL_base.pkl` and
the two closing patches; stations along 10/28 from the 10 end (2,743 m).

* **The sites are inside the I-285 bridge-edge span.** The south bridge-edge
  object `New Buildings/tunel_A.obj` (heading 90) spans stations
  1,423–1,603 at 65–102 m south of the axis, 23.7 m deep (top at y = 0);
  its north twin spans 1,627–1,807 at 46–82 m north; the I-285 bores
  (`-2190`, `-2193`, tunnel=yes) cross the axis at stations 1,599 and
  1,655, their south portals at 1,459 / 1,521, ~90 m south. Of the new
  rows > 0.5 m within 250 m of the axis on the south side, 67 lie within
  60 m of the bridge-edge objects (stations 1,200–1,800: the 116-row
  `strip_transverse` site, `adjacent_ground_step` 8.53 m,
  `mid_edge_step` 2.74 m), 3 lie over the bores just past 60 m (station
  ~1,730, 25 m south: `strip_seam_tear` 6.97 m, `strip_arc` 7.54 m), and 2
  are groundside service-road rows 190 m south (station ~800). No strip row
  is new on the south side away from the span.
* **Away from the span the strip already holds (27r (2)).** DEM / face
  transects south of the axis at stations 800, 1,300, 1,350, 1,900,
  2,100: graded strip at runway level (299–303 m) out to the zone-2 edge
  (60–75 m from the axis), then the embankment on the DEM (≈ 298 → 278 m
  between 75 and 120 m, about 1 : 2). That is "a standard graded strip,
  then the sloped embankment". No change at the strip's derivation site.
* **Why the span got worse than the control.** Inside the span the lidar
  reads the HIGHWAY under the deck: at stations 1,430–1,700 the DEM is
  280–289 m from 30 m south of the axis, and 281–285 m under the runway
  itself at 1,490–1,700. On main the Global block's `pav17` shoulder
  strips (offset 23–48 m) were apron graded at runway level across that
  ground — by accident the reading 27r (1) asks for (flush with the
  airside surface out to the edge objects' backs). With the pack's own
  pavement the ground there is adjacent-ground zones 1–2, which take the
  lidar trench. Holding the ground between the runway edge and the edge
  objects' backs at deck level is 27r (1) — the bridge-edge span, lane
  lpackcut (#1138, PR #1489). Not edited here.
* **The other new site (not 10/28-south).** North of 10/28 at the 10 end
  (33.62167, -84.44659, stations 0–600), 408 `within_shape` rows, worst
  12.96 m over 180 m, all on ONE `terrain_edge:22` way (-14902, 96 nodes)
  whose run joins the taxiway's adjacent-ground ring and the service road
  `big_roads:-13911` below it. A `terrain_edge` way is role-less
  articulation (check_grade `ROLE_LESS_FEATURE_CLASSES`: "carries no grade
  law of its own"); the census prices it as a shape when no single host
  covers the whole run. The control carries the same class (terrain_edge
  ways of 442 rows each, e.g. `terrain_edge:59/68/76`). The pack's
  `dsf:pol93` / `dsf:pol85` end the taxi ring at the road over a longer
  run than Global's `pav15` did. This is an instrument class, not a surface
  step — a follow-up for the census owner, not edited here.
