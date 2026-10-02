# The collar's consumer census (#86, owner RULINGS 2026-10-02v (5),
# amended 2026-10-02z)

Owner ruling 2026-10-02v (5): the platform collar is minted at the CAP
width and the SOLVE places the toe, in ONE pass.  RULINGS 2026-08-30l
(consumer census before cross-cutting geometry law) asks for a census of
EVERY pass that reads the affected geometry, ruled in ONE table, before a
consumer is edited.  The affected geometry is the collar ring / region:
the annulus `<ref>#collar` between the pad rim and the platform, whose
width goes from `C = clamp(relief / bank_slope, 5, 15)` to a flat
`platform_collar_max_m` (15 m).

**The region does not grow.**  The collar is
`P.difference(the platform pieces)` where `P` is the pad polygon AFTER
`planar/pad_cut.apron_cut_to_pads` (which differences each apron by the
pads standing on it and TRIMS a pad that reaches a runway or taxiway).
The unit footprint `platform u collar` is the pad, unchanged; the cap mint
only moves area from the PLATFORM to the COLLAR inside it.  So the ring
cannot claim an airside face, and no trim is needed at the derivation
site.  Twin:
`test_unitplatform_platform.py::test_the_cap_width_collar_never_claims_an_airside_face`
asserts zero area of intersection between every collar face and every
`rolled_on_roles` face on the arrangement.  If a future change ever let a
pad polygon overlap airside, the trim belongs at `apron_cut_to_pads` /
`platform_split` — the single derivation site — never as a per-consumer
veto.

## The table

| # | Consumer (site) | What it reads of the collar | Under a cap-width ring | Ruling |
|---|---|---|---|---|
| 1 | `planar/platform.py::platform_split` | THE derivation: mints `platform = pad (-) C`, `collar = pad - platform` | C is `platform_collar_max_m`; platform smaller, collar wider | **Edited.** The one site C is minted; `collar_width_m` is its one derivation |
| 2 | `planar/platform.py::_mint_blocks` | per block the platform pieces + a terrace STRIP at each cut chord | erodes by the cap too; the strip half-width stays `bank_min_width_m` (a different law) | Unchanged; a block left with no platform piece keeps the unit whole, as today |
| 3 | `constraints/platform.py::platform_collar_rows` | the collar's outer + inner rings | same rings, so the SAME row count; `d` grows to ~15 m, so the 1:3 bound grows with it | **Edited.** The own-rim cap-0 equality becomes the one-way 1:3 bank (`follows=(o,)`) |
| 4 | `constraints/platform.py::platform_plane_rows`, `platform_level_rows`, `platform_contacts`, `refused_plates` | the collar face for the frontage, the platform ring for the plane | the plane is fit on fewer vertices; the frontage is read on the OUTER rim, which does not move | Unchanged |
| 5 | `constraints/platform.py::platform_records` / `collar_width` | the ring, for the sidecar | `collar_m` reads 15.0; `collar_needed_m` still reports what the SOLVED relief needs | Unchanged — this row is how the cap is judged |
| 6 | `constraints/pads.py` frontage read (`is_collar_ref` branch) | reads the OUTER rim, EXCLUDES the platform ring | the excluded ring moves 15 m in; the rim the frontage reads does not move | Unchanged (comment's "5 m" corrected to C) |
| 7 | `constraints/cluster_pad.py::plane_groups` | the collar's face id rides its platform's entry; none of its vertices joins the plate | the plate's vertex set shrinks with the platform | Unchanged |
| 8 | `constraints/pavement_cap.py` | collar faces go to `collar_v`, never to the 5 % fallback pairs | more of the pad is exempt from the pavement fallback | Unchanged — intended: the collar IS a bank |
| 9 | `constraints/ceiling.py` | skips the `COLLAR` / `RIM` / `PLANE` heads when twinning the 5 % ceiling | the rim row is now an inequality, and is still skipped BY HEAD | Unchanged |
| 10 | `constraints/pad_frontage_gs.py::_unit_outline` | the UNION of every face of the unit (platform u collar) | the union is the pad, unchanged | Unchanged |
| 11 | `constraints/jetway_strip.py` | the rider's host is `ref.split("#")[0]`; the outline it stands on is the collar's | the unit outline is unchanged, so rider -> host is unchanged | Unchanged |
| 12 | `constraints/no_step.py` | the HOLD rows / sets by ref | refs unchanged | Unchanged |
| 13 | `airport/placement_read.py::_collars_as_platform` | publishes the collar's OUTER ring under the PLATFORM's ref, at the PLATFORM PLANE's heights | containment is still the whole unit footprint; the plane is the same plane | Unchanged |
| 14 | `airport/pad_block_seat.py` | seats the unit on the block collar's outer ring | unchanged | Unchanged |
| 15 | `model/platform.py::datum_vertices` | a HELD block's collar must share a vertex with a stage-1 face | the collar still carries the whole outer rim | Unchanged |
| 16 | `model/islands.py` | a collar's hole IS its platform (the courtyard rule) | the hole is smaller | Unchanged |
| 17 | `planar/pad_cut.py` plateau cut | the outline per PLATFORM ref = platform u collar | unchanged | Unchanged |
| 18 | `verify/pads.py`, `verify/within.py` | skip collar shapes in `pad_flat` / within-shape | a larger share of the pad is exempt from those two families | Unchanged — intended |
| 19 | `tools/check_grade.py` (`_is_platform_collar`, `platform_rim_relief`, `platform_refused`) | the census families | `platform_rim_relief` keeps judging the cap against the solved relief; `platform_refused` carries MORE rows (see below) | Unchanged |
| 20 | `emit/osm_adapter.py` `platforms` sidecar key | per platform its collar width | reads 15.0 for every platform | Unchanged |
| 21 | `pipeline/publication.py` refused-platform report | `PLATFORMS[].refused` | more refusals | Unchanged |
| 22 | `planar/cluster.py`, `airport/footprint_connector.py` | read the CONSTANT `platform_collar_max_m * bank_slope` as `step_max_m` | they read the constant, not the ring; the constant is unchanged | Unchanged |
| 23 | `solve/why.py` | the `platform_collar` attribution heads | heads unchanged | Unchanged |

## The one consequence that was NOT neutral — MEASURED, and closed in round 2

Round 1 minted at the cap UNCONDITIONALLY, so a pad that leaves
`[placement] cluster_pad_min_m2` (5,000 m2) after a 5 m erosion and not
after a 15 m one lost its platform and kept today's welded plate
(`under_min_area`).  For a square pad the mint bar moved from about
6,500 m2 to about 10,100 m2.  This lane REPORTED it and the owner's sweep
sw1008c MEASURED it (RULINGS 2026-10-02z): live platforms **KCLT 10 -> 3,
SPJC 8 -> 5, HECA 14 -> 8**, KCLT plateaus 192,770 -> 114,314 m2, 106 KCLT
runway movers with 18L/36R flex at 98 % of budget, and a new KCLT CRITICAL
`strip_arc` 0.18 m. Round 1 was REVERTED (10ee7b99); where the platform
survived, the bank goal WAS met (HECA `building4` 1:3.27 -> 1:4.61, SPJC
`building5` 1:1.89 -> 1:4.41, `building13` 1:2.81 -> 1:3.14), i.e. the
one-way rows of rows 3 + 9 below are sound and only the WIDTH needed
re-deriving.

### Round 2 (owner RULINGS 2026-10-02z): C is the widest width the pad CARRIES

`planar/platform.py::_collar_for_pad` is now the one derivation: the
widest width at or under `platform_collar_max_m` whose erosion still
passes the mint's own gates, **searched up from the width the pre-collar86
engine minted** (`clamp(relief / bank_slope, bank_min_width_m,
platform_collar_max_m)`), on the lattice of
`emit.identity.input_quantum_m` (§46 (4), 1 mm — a named law resolution,
no literal of C's own). One pass, no re-mint, no second solve; the toe
stays solve-placed.

**The platform SET is unchanged by construction.** The refusal is judged
at that same status-quo width, so round 2 alters a collar's WIDTH and
nothing else — the invariant the owner asked to twin
(`test_round_2_never_refuses_a_platform_main_grants`, 50 synthetic pads
over two DEM arms: the verdict is identical pad for pad and every C is at
or over main's). A floor at `bank_min_width_m` instead — the ruling's
literal words — would additionally MINT platforms main refuses (2 of those
50 pads: a pad whose relief-width erosion crossed the min-area bar while a
5 m one does not). That is a strict gain in 10-02z's own direction, but it
CHANGES the platform set, so it is REPORTED here for the owner and not
taken.

**The census table below stands unchanged**, with two readings narrowed:

| # | Row | Round 1 reading | Round 2 reading |
|---|---|---|---|
| 1 | `platform_split` | C is `platform_collar_max_m` for every pad | C is the widest width the pad carries, `_collar_for_pad`; `_eroded` is the gate predicate the search and the mint SHARE |
| 3 | `platform_collar_rows` | `d` grows to ~15 m | `d` grows to C, which is ~15 m wherever the pad carries it and narrower where it does not — the one-way 1:3 rows are unchanged |
| 5 | `platform_records` / `collar_width` | `collar_m` reads 15.0 | `collar_m` reads C; the record also carries `collar_minted_m` and `collar_why` (`cap` / `area` / `floor`), so an area-limited collar is READ, never inferred |
| 20 | `osm_adapter` `platforms` key | reads 15.0 for every platform | reads C, with `collar_why` beside it |
| 21 | `publication` refused report | more refusals | the SAME refusals as `origin/main`, by construction |

Rows 2, 4, 6-19, 22, 23 are unaffected by the change from a constant C to
a per-pad C: each reads the ring, the unit footprint or a constant, none
of which the derivation moves. Row 6's `pads.py` comment reads "C inside
the pad", which stays correct.
