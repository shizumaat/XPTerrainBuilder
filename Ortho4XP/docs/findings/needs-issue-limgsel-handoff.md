# limgsel handoff (needs issue): Build "Imagery" menu stays on USA2 for a Bing tile (app 1.0.433)

## Cause (attributed, read-only on the owner's data)
- Owner's active tile +48-124 (prefs ActiveTileKey): textures *_BI16/18.dds, only `Ortho4XP_+48-124.cfg`
  (default_website=BI), no XPTerrainBuilder_ cfg. Engine `tile_info` (adopt stubbed, read-only):
  provider="", detected_provider=BI, detected_zl=18 -> effective_imagery = (BI, 18, detected). Engine is right.
- (a) refuted: provider is "" (no global default leaks). (b) n/a: Ortho4XP cfg also says BI (ignored by 26c).
- (c) refuted: BI is in `imagery_sources` (buildable, covers +48-124) and its liveness probe answers online
  (USA2 answers HTTP 400 = offline, side note).
- ROOT CAUSE (both apps): adoption runs only at the moment the selection changes. If the tile's scan info is
  not in `built` yet, nothing adopts later when the scan reports it. In 1.0.433 this always hits: the scan
  cache `~/Library/Caches/XPTerrainBuilder/tile-scan.json` is version 3 (written 16:25 PDT by the previous
  app), 1.0.433 expects v4 (#1334 bump) -> cache rejected -> `built` empty until ScanDone; no ScanDone had
  been saved 16 min after launch (22:29) while builds ran. Offline scan of his Custom Scenery: 2521 tiles, 32 s.
  Qt has the same flaw: `_sync_build_controls_to_selection` runs once per selection key and `_built`
  arriving later is ignored.
- (d) partially: a running build slows/delays the scan; open question why no ScanDone in 16 min (not chased;
  lqueue owns session busy checks).

## Done (uncommitted work is in this WIP commit)
- New `Sources/SceneryKit/TileImageryAdoption.swift` (public struct TileImageryAdoption: select/arrived/userPicked).
- `BuildModel.swift`: `built` didSet -> adoptArrivedTileConfig; activeTile didSet uses imageryAdoption.select;
  `adopt(_:)` replaces adoptActiveTileConfig (sends objectWillChange: AppStorage doesn't self-publish);
  new `chooseBuildProvider(_:)`; `BuildPane.swift` providerBinding setter calls it.
- Qt `O4_Qt_GUI.py`: sync key gains frozenset of selected tiles known in `_built`; `imagery_combo.activated`
  -> `_imagery_picked` marks all as known (user pick wins).
- Twins: `Tests/SceneryKitTests/TileImageryTests.swift::adoptionWaitsForTheTilesInfo` (NOT yet run);
  `tests/test_qt_build_controls_sync.py` two new tests — 15 passed (-n0); test_qt_stop_resume 61 passed.

## Next step
1. `swift build` and `swift test --filter TileImageryTests`.
2. Merge origin/main; CI registry twins, closure twins, ratchets, `ruff check --select I001` on O4_Qt_GUI.py.
3. Open PR (body per lane_rules), report "needs issue". No real airport build needed (UI-only).
