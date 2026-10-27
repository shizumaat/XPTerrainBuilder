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
