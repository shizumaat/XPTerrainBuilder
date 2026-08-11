# App — restore the tile selection across launches

Spec: 2026-08-11, FROZEN (Fable lead). App-side only (Swift); no engine
change. Pre-ship mode (Ortho4XP/docs/RULINGS.md "PRE-SHIP DEVELOPMENT
MODE"): deviations STOP-and-report, never decided in-lane.

## Goal

On launch, the build map restores the previous session's tile selection:
the selected set AND the active tile. Today `BuildModel.selected` /
`BuildModel.activeTile` start empty every launch while built/installed
tiles are already restored optimistically (`loadCachedTileStates`,
BuildModel.swift:222) — selection joins that same doctrine.

## §1 Keys and format (one spelling, the canonical one)

* `PrefKeys.selectedTiles = "SelectedTiles"` — `[String]` of canonical
  tile keys (`TileMath.key(lat:lon:)`, e.g. `"+35-081"`), sorted by
  `(lat, lon)` for deterministic writes.
* `PrefKeys.activeTile = "ActiveTileKey"` — `String`, one canonical key;
  absent/empty = none.
* The reader is `TileMath.parse` (SceneryKit — already validates length
  and ±90/±180 ranges). NO second format, NO new parser: the tile key
  spelling used by built-tile folders and logs is the one persisted.

## §2 Write path

Persist on every selection change: `didSet` on BOTH
`@Published var selected` and `@Published var activeTile` (BuildModel.swift
~175-177) calling one private `persistSelection()` that writes both keys
to `UserDefaults.standard`. Sets are small (a user selects tiles by
hand); no debounce. `activeTile`'s existing `didSet` body
(`adoptActiveTileConfig()`) keeps running first — append, don't replace.

## §3 Restore path

Private `restoreSelection()`, called from `init()` immediately AFTER
`loadCachedTileStates()` (BuildModel.swift:216) — the ordering is load
the built-tile cache first so the active tile's config adoption
(`adoptActiveTileConfig`, which reads `built[coord]`) behaves on launch
exactly as it does on a user click.

* `selected` = stored keys mapped through `TileMath.parse`; malformed or
  out-of-range entries are dropped silently (parse already refuses them).
* `activeTile` = the stored key iff it parses AND is a member of the
  restored set; otherwise `selected.sorted().first` when the set is
  non-empty (the same fallback the deselect path uses,
  BuildModel.swift:685), else `nil`.
* The `didSet` re-writes fired during restore write back identical
  values — harmless, no suppression flag.
* Fresh install / absent keys ⇒ both empty, exactly today's launch.

## §4 Tests (pre-ship: changed behaviour, once)

* `Tests/SceneryKitTests`: `TileMath` key ↔ parse round trip over
  representative corners (`(0,0)`, negative lat/lon, `(+89,-180)`) and
  malformed rejects (`""`, `"35,-81"`, `"+91-000"`) — EXTEND the
  existing TileMath coverage if some of these are already pinned; do not
  duplicate. (The BuildModel wiring itself has no app-side test target;
  that skip gets a ledger line at merge, and the owner's in-app check is
  acceptance.)
* `swift build` (and the test run) with
  `DEVELOPER_DIR=/Applications/Xcode-beta.app` — CommandLineTools
  produces macro-cascade errors that are NOT code bugs.

## §5 Acceptance

* `DEVELOPER_DIR=/Applications/Xcode-beta.app swift build` clean;
  `swift test --filter TileMath` (or the suite's naming) green, once.
* Manual (owner, on the next app build): select several tiles, set an
  active one, quit, relaunch — the same set is selected, the same tile
  active, the header count matches; deselect-all then relaunch — empty.

## Constraints

* `PrefKeys` stays the single key registry (add the two constants there).
* No change to selection SEMANTICS (what clicking does), only
  persistence.
* Match the surrounding comment voice (the "optimistic launch" doc
  comment at `loadCachedTileStates` is the register to write in).
* Do not touch `Sources/XPTerrainBuilder/Resources/VERSION` or
  `Ortho4XP/` — version stamps are the lead's at app build; the engine
  is out of scope.
