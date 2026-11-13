# Automatic photo source per tile, and the blend across provider edges (#2018)

Owner 2026-11-13T02:00Z ("Yes to all three"), lane l2018. Three parts:

1. **Automatic provider per tile** for World / flight-job drapes and the
   flight's full builds: the national orthophoto service where one covers
   the tile, else Bing (`BI`), each at no less than its `min_source_zl`
   (#2017). Each tile's provider is shown on the map (tile pane, hover
   readout); the map key keeps its 8 items (#2031).
2. **Blend across provider edges**: one tile on each side of an edge
   where the provider changes has its colour pulled toward the other
   side, as one continuous field per tile (never a per-texture constant:
   the OTHH seams of 2026-09-18).
3. The Fly pane's "Photo source" picker offers **Automatic** first, its
   default; a provider chosen there is used for every tile, as before.

The World pack records which provider each tile uses.

## 1. Choice (`O4_Imagery_Auto`)

* Candidates are the national layers of the combined sources
  (`Providers/*.comb`, today `EUR.comb`), in file order (the order the
  combined build paints them, top first), each with its extent
  (`Extents/**/<extent>.ext` + mask PNG). Global layers (`Arc@`) are not
  candidates: the fallback is `BI` (owner).
* A layer covers a tile when its extent mask (`O4_Imagery_Utils.has_data`
  with `return_mask`) is set over at least `COVER_FRACTION` = 0.99 of the
  1° tile (the rest is the mask's anti-aliased edge). A border tile, or a
  coastal tile reaching past the extent (open sea beyond the territorial
  waters), is not covered: one provider draws the whole tile, and a
  national service is blank outside its country. Measured on the shipped
  masks: +48+002 France 1.000, +43+005 0.994, +48-005 0.872 (Brest, sea),
  +46+006 France 0.52 / Switzerland 0.51 (Geneva), +52+005 Netherlands
  1.000, +52+004 0.814 (sea).
* The zoom is the user's `default_zl` raised to the chosen provider's
  `min_source_zl` (never a capture the provider serves differently).
* A pure function of the shipped files: the same tile always gets the
  same answer, so two neighbours agree on where the edges are.

## 2. Setting and consumers

New app setting `fly_photo_source` (str, default `"auto"`; any other
value is a provider code). The Fly pane's picker writes it (both apps).
`world_job_run.photo_source(tile)` reads it: `auto` asks `O4_Imagery_Auto`
for that tile, a code is used as is, at `default_zl`. The Build pane's
`default_website` is no longer written by the Fly pane.

Consumer census of `default_website` / `default_zl` (every reader, ruled):

| Reader | What it reads | Ruling |
|---|---|---|
| `world_job_run.photo_source` (+ `flight_job_run._Runner`, track `_Runner`) | the global pair, per job | per TILE now: `photo_source(tile)` (§1); the time estimates keep the global pair |
| `session` build loop (session.py ~1683) | the command's provider → `tile.default_website` | unchanged: the per-tile provider is passed per `enqueue_build` |
| `O4_World_Drape_Fetch.fetch` | sets the tile's pair from its argument | unchanged (gets the per-tile code) |
| `O4_Tile_Utils` manifest / step checks, `O4_DSF_Utils`, `O4_Mesh_Utils`, `O4_Imagery_Prefetch`, `O4_Imagery_Utils.initialize_local_combined_providers_dict`, `imagery_follow_land.OWN_KEYS`, `parallel.py` | the TILE object's pair | unchanged: each tile carries its own |
| `O4_Tile_Info` scan, `PackImagery.swift`, `TileTextureAudit.swift`, `O4_Qt_Map` audit, `O4_Qt_GUI` provenance | the tile cfg | unchanged: a World tile's cfg names the provider it was built with |
| `O4_Settings_Model` (`_TILE_PRESERVED`, `LEGACY_KEPT_KEYS`), `O4_Cfg_Vars`, Settings presets / selection, `BuildModel.swift:1813` | the Build pane's global pair | unchanged (Build pane only) |
| `O4_Qt_Fly_Pane._photo_source`, `FlyModel.photoSource`, `FlyText.photoSourceKey`, `O4_Fly_Text.PHOTO_SOURCE_KEY` | the global `default_website` | MOVED to `fly_photo_source` |
| `plan_estimate._tile_settings` | the tile cfg, else the argument | unchanged |
| `o4_driver.py` (bundled kit) | its job dict | unchanged |

## 3. Blend (`O4_Imagery_Provider_Blend`)

For a drape tile T with provider P:

* **Edges.** A side of T whose neighbour's provider Q differs is a
  provider edge. The neighbour's provider is the World pack record's
  (§4) when the pack holds a real tile there, else the choice the job
  would make (§1 under Automatic, the forced code otherwise).
* **Cast.** `c = mean(Q − P)` per RGB channel over the pixels of the
  texture squares that straddle the shared edge (each square shows the
  same ground in both providers) lying within 1/64° (~1.7 km) of the
  edge line, luminance in [10, 248] in both, at the drape's 512 px tier
  (drop 3, raised to each provider's `min_source_zl` by
  `download_jpeg_ortho`). Measured (lane l2018, BI/USA2 at 32 N 110 W):
  the whole squares read +21 red, the 1.7 km band +34, a median +14 —
  two providers differ in contrast as well as level, so the band near
  the line is what the seam shows. Antisymmetric by construction (the
  neighbour measures −c on the same squares; cached per edge in
  `<data>/World_build/provider_casts.json`). Clipped to ±40 counts.
* **Weight.** w = ½ when the neighbour also blends (a drape not built
  yet, or one whose record says it blended toward T); w = 1 when it will
  not (a full, kept or adopted tile: T then closes the whole gap).
* **Field.** Side s contributes `v_s(t) · d_s`, where `d_s` is 1 on the
  edge and falls linearly to 0 at the opposite edge, and `v_s` is
  piecewise linear along the edge: `w·c` at its midpoint and, at each
  end, the corner value — `½(w·c + w_A·c_A)` when the tile A beside T
  along that edge also blends and has a provider edge on the same side,
  else 0. Every term vanishes on an edge whose far side does not apply
  the same term, so the field never adds a step where there was none:
  along a same-provider edge both tiles evaluate equal values; across
  the provider edge, T + w·c and its neighbour − w·c meet halfway.
* Evaluated per texture at its pixel centres' lat/lon (one function of
  position per tile, applied by `O4_Color_Harmonization.apply_color_field`),
  so two textures agree on their shared edge.
* Full builds take the automatic provider but no blend this round.
* **Follow-up (lane lblend2018b, 2026-11-13).** Measured on cached
  BI/USA2 (150 m strips either side of the line, per-square mean Lab,
  ΔE76): the cast varies ALONG an edge as much as across it (H 32 N
  110 W: squares 7–31), and real casts exceed ±40. So (a) the cast is
  measured per straddling square (`O4_Imagery_Provider_Cast._measure`), each a knot at its
  centre's fraction `t` of the edge, and `v_s(t)` is piecewise linear
  through them (corners as before, from the end knots); (b) each knot
  is an affine `x → (1+k)x + b` matching mean AND spread: the target
  spread is the geometric mean of the two (w = ½) or the neighbour's
  (w = 1), the gain clipped to [½, 2]; the field is two continuous
  fields (offset, slope), applied by `apply_color_field(gain=)`; (c) the
  band is 1/128° (~0.87 km); (d) the cap is ±80. H 32 N: raw 18.25,
  first round 9.70, now 2.68; H 33 N: 9.47, 4.98, 1.97; same-provider
  control 0.8–1.5. Upgraded drape tiers re-apply the blend from the
  pack record (`imagery_follow_drape.prepare`).

## 4. World pack record (`O4_World_Imagery_Record`)

`<pack>/XPTerrainBuilder_imagery/<tile>.json`:
`{"provider", "zl", "kind", "auto", "blend": {side: {"toward", "cast", "w"}}, "at"}`,
written into the staging folder by the drape writer and carried in by
`O4_World_Pack.swap_in`. A tile with none (built before this, adopted,
full) reads its provider from its DDS names
(`<y>_<x>_<provider><zl>.dds`). `world_state.WorldTile.provider` carries
it: the 9th `ScanBatch.world` element (readers of the first eight are
unchanged), the tile pane's World-pack detail ("photo: FRorth") and the
map's cursor readout ("photo: FRorth") in both apps.

## 5. Acceptance

* Unit twins: the choice (covered / border / coastal / zoom floor), the
  field's continuity (equal values on a same-provider edge, halfway
  meeting on a provider edge, zero far from edges), the record round
  trip, both apps' picker and readout text.
* ΔE (CIE76, mean Lab of the strips either side of the edge) across a
  real provider edge from cached imagery, before and after.
