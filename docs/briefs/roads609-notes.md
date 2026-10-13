# roads609 — notes (issue #609: the forecourt roads between KCLT's garages; owner 2026-10-12 "admit the forecourt roads", RULINGS 12r owed)

## RESUME HERE
* Branch `claude/roads609` (worktree `.claude/worktrees/roads609`) off origin/main 8d0cd75e8.
* Scratch `<scratchpad 466e18b3…>/roads609/`: `base/` (replay of `frames/pads67/KCLT.pkl --from classify --emit
  --verify --solved-out`, main code), `a1_extent_arm.py` (the attribution instrument: classify-only, shipped vs one
  intervention, read at the site).
* Step A (attribution) DONE below. Consumer census DONE below. Code next.

## Step A — WHY THE FORECOURT ROADS ARE NOT IN THE PATCH (verified on the pads67 KCLT capture, main 8d0cd75e8)
Facts re-read (`tools/osm_site.py`, base replay patch): within 250 m of 35.2248,-80.9450 the patch holds ONE
`service_road` (`small_roads:-30034`, 247 m); within 150 m the three garage pads building86 (223.0–223.4),
building88 (223.1), building90 (223.0–223.45); the feed (`+35-081_airport_small_roads.osm.bz2`) holds 32
`highway=service` ways within 120 m (34 with `big_roads`; one `bridge=yes layer=2`, dropped by `road_ways` as
every bridge is).

THE GATE: `classify/ribbon_mint.ribbon_extent` — 30e (2) "the way's parts INSIDE THE PATCH" — defines the patch as
the pavement union + the airside bands' zone-2 envelopes. A BUILDING PAD IS NOT IN IT (nor is anything groundside),
so a road that reaches a pad and nothing airside has no in-patch stretch at all, and 30e (2)'s gap bridge joins
stretches of ONE OSM WAY only — the forecourt network is 32 short ways (2–23 nodes; OSM splits a road at every
junction), so no way has two in-patch stretches to bridge. The other candidate gates do NOT fire: not the airport
boundary / airside claim (the ways are inside the load box, `airport.osm_ways` holds 34 of them), not the 1206 dedup
(no route there), not min_len (10 m), not the bridge/layer handling (1 of 32), not the pack-object cover (the mint
subtracts standing CELLS only; the slab `techos_1` is no cell — #229 unbuilt), not the feed's own filter (the ways
are in the feed).

Intervention (`a1_extent_arm.py`, classify only, seconds): SHIPPED 529 ribbons / 36,988 m² airport-wide, 0 within
150 m of the site. ARM "the pads are in the extent" (one line: `ribbon_extent` ∪ the building cells): 547 ribbons /
38,682 m², 8 within 150 m — but only 1,054 m² of STUBS at the garage rims (`small_roads:-16665` 84 m², `-16649` 45 m²,
`-16651` 46 m², `-24655` 777 m² …): the way's part inside the pad is in the extent, the pad then subtracts it, and
the part BETWEEN the garages is still out of the patch. So two things are missing, both at the one site:
1. A PAD IS PATCH: `ribbon_extent` gains the pad cells (a road entering a pad in source = the road serving it; the
   touch witness of 09j then welds it to the rim).
2. THE GAP IS THE ROAD'S, NOT THE WAY'S: 30e (2)'s 250 m bridge joins two in-patch stretches along the ROAD
   NETWORK (ways sharing a node), not along one OSM way — the forecourt between two garage entries is a path of
   several ways. The per-way bridge is the special case of the path along one way; `road_gap_bridge_m` is unchanged.
3. THE WELD: `mint_osm_ribbons` subtracts every pad WITH the set-back knife (roadweld100: "the ribbon takes the same
   set-back itself"), so a ribbon is always GAPPED from a pad and never welds (09j (2) says a road touching a pad
   in source is welded; the knife is the engine's own gap, which 09j says is no witness). The ribbon cells now go
   through the same touch witness every lot and 1206 corridor goes through (`_cut_back_groundside`, read on the
   NEW ribbon cells only so no existing cell is re-cut — the roadweld100 measured hazard).

## Consumer census — every pass that reads a mapped-road ribbon (`is_osm_ribbon_ref`) or groundside pavement at a pad
| site | reads | with a ribbon WELDED to a pad rim / admitted between pads |
|---|---|---|
| `classify/roles._cut_back_groundside` | touch witness per groundside cell vs pads | NOW reads the ribbon cells too (new cells only): touching → clipped at rim + `pad_touch`/`pad_weld`; held (§28 (6) step > 2.4 m) → knife; gapped → as drawn |
| `classify/gap_mint` :123 | ribbons are FLUSH (no stand-off) for gap pieces | unchanged: a gap piece abuts a ribbon flush; the ribbon now also abuts the pad |
| `classify/facade_mint` | facades minted BEFORE ribbons | unchanged (a road inside a facade lot is the lot) |
| `planar/weld.weld_cells` | `pad_touch.weld_partners(cell)` → welds the cell to the named pad's rim, pad frozen | the ribbon now names its pad; same halves as a lot |
| `planar/zones` :183 | ribbon gets no stand-off inside a band; kerb is the band's | unchanged |
| `planar/shapes` :430 | a ribbon is UNLABELLED (30aa) — no road separator | unchanged |
| `planar/shape_mouths` :45, `shape_airside` :98/:185 | ribbon is no side, no separator | unchanged |
| `planar/ribbons` | ribbon stations | unchanged |
| `constraints/pads.pad_welded_vertices` | every vertex both a pad's and a groundside value face's = PAD column | the ribbon's rim vertices become pad columns (senior) — the weld law of 09j (2) |
| `constraints/pads` :510 | rim-strip rule skips ribbons | unchanged |
| `constraints/pad_frontage_gs` :358/:404 | 09j touch: a cell sharing the pad's rim | the ribbon is such a cell now |
| `constraints/apron` :449 | ribbon mints no apron row | unchanged |
| `constraints/ceiling` :119 | band→ribbon rows keep the road cap | unchanged |
| `constraints/roads` / `road_ramp` :1141 | ribbon vertices are never "own" bordered runs; contact set = airside value roles (pad included) + lot | a ribbon welded to a pad gets the §37 (6) ramp from that CONTACT at the pad's pre-solve level, design 5 % / cap 10 % |
| `solve/design_stage._welded_faces` | ribbons are the welded road faces (stage 2) | unchanged |
| `pipeline/ribbon_steps` | ribbon kerb vs airside cliff read | unchanged |
| `pipeline/terrace_witness` | retaining-wall witness on road ring edges | reads the new faces like every road |
| `pipeline/late_stage` :98 | ribbon near a gap piece skipped for stations | unchanged |
| `verify` families | `road_cross_section`, `within_shape`, `pad_*` price the new faces | counted in the census |
Object stage: a body whose feet stand on a ribbon face reads that graded surface (10n (3)); the bodies between the
garages stood on NO face before (off-surface → mesh ground in the tile build).
