# XPScenery Doctor v2 — Map-Centric Redesign Plan

Driven by user feedback, July 2026. Four phases, each shippable on its own.

## Phase 0 — Bugs, trust and paper cuts ✅ (shipped)

1. **Search crash / beachball.** Reproduce and fix. Suspected: every keystroke
   re-filters 7,600+ findings with `localizedCaseInsensitiveContains` on the
   main thread inside grouped Lists, plus List selection holding IDs that the
   filter removes. Fix: debounce input (~250 ms), precompute a lowercased
   search corpus per finding once per report, filter off the main thread,
   prune stale selection IDs on every filter change.
2. **Persist the analysis report.** Save the report (Codable JSON) to
   Application Support on completion and after every fix/action mutation;
   load on launch. Report header shows "Generated <date> — <install path>".
   Quit, relaunch, continue fixing where you left off.
3. **Sortable tables.** All Tables get clickable column headers
   (`sortOrder` + `KeyPathComparator`): packages, duplicates, unused files,
   modifications.
4. **Modification-date column** on package tables (folder mtime) and unused
   files (file mtime). Plus a **Type column** using the refined PackKind
   (Phase 1.5).
5. **Backup messaging honesty.** Backups stay as sidecars next to the
   original (user preference: easy to find). But renames don't create a
   backup file at all — the record just remembers the old name — so the
   apply-fix dialog and Modifications window must describe what each fix
   actually does instead of claiming ".xpsd-backup" universally.
6. **Modifications grouped by package**, with per-package "Revert All in
   Package". Package derived from the path under Custom Scenery.
7. **Findings grouped by package** in every category list (sections by pack,
   with per-pack counts), matching how people actually review.
8. **Fixability at a glance.** Wrench badge on every row whose finding
   carries an applyable fix; "Fixable" filter in the toolbar. Spill-light
   findings (C-10) drop to info severity per feedback — real cost, but no
   one-click action yet, and warning-severity should mean "actionable".

## Phase 1 — Engine correctness and new fixes ✅ (shipped)

1. **Proactive missing-resource analysis** (no Log.txt required). For every
   pack: resolve each DSF DEFN entry, apt.dat library reference and
   obj/pol/ter/fac texture reference against (a) pack-relative files,
   (b) installed library exports, (c) **default X-Plane libraries**
   (index `Resources/default scenery/*/library.txt` — required to avoid
   false positives). Unresolved → missing-resource finding *before X-Plane
   ever runs*; near-misses go through the existing PathRepair mojibake/case
   matcher with auto-rename fixes. Log.txt analysis remains as corroboration.
2. **Unused-resources rewrite: true reachability.** Roots = DSF DEFN entries
   + library.txt exports + apt.dat references. Breadth-first closure over
   file references (DSF→obj/ter/pol/fac/agp/str→textures/objects). Anything
   unreachable is unused — this both kills the current false positives
   (references extracted only from TEXTURE-keyword lines; switch to
   any-token-with-image/obj-extension scanning so ROOF/TILE/OBJECT lines
   count) and correctly catches more true orphans (textures of dead objects).
   Verify against the real packs that showed false positives before shipping.
   All existing guards stay (plugin markers, seasonal folders, ambiguity =
   alive).
3. **New fixes:** (a) ATTR_no_blend → GLOBAL_no_blend promotion (byte-level
   edit, validated by re-parse; the safe-case detection already exists);
   (b) non-power-of-two textures: resample to nearest POT inside the DDS
   converter (UVs are normalized; assisted fix).
4. **Uninstalled packs.** Scan `Custom Scenery (Disabled)` alongside
   Custom Scenery; status becomes enabled / disabled / **uninstalled**.
5. **Precise pack types.** Read the `sim/overlay` property from one DSF per
   pack (extend DSFReader to the PROP atom): non-overlay + ortho textures =
   Ortho, non-overlay = Mesh, overlay + airports = Airport, overlay = 
   Landmark, library.txt = Library. Replaces the name-based heuristic.
6. **Context-aware actions.** Action menu and right-click contextual menu
   compute from selection state: Enable/Disable (ini), Install/Uninstall
   (move between Custom Scenery and Custom Scenery (Disabled), ini updated);
   mixed selections show both directions. One shared code path.

## Phase 2 — Map-centric main window

Single main window: toolbar / map + right inspector / bottom results.

1. **Map view.** Custom SwiftUI Canvas (not MapKit — offline, no Apple Maps
   dependency, full control of drawing): equirectangular projection,
   pan/zoom (pinch, scroll, double-click), bundled simplified Natural Earth
   coastline GeoJSON (~1-2 MB) for context, 1°×1° X-Plane tile grid fading
   in with zoom.
2. **Overlays.** Mesh/ortho packs tint whole tiles (per-kind colors, blended
   when stacked); airports drawn with FAA-sectional-inspired iconography
   (magenta/blue airport symbols, runway tick marks at higher zooms) and
   ICAO labels. Airport lat/lon from apt.dat (datum row / first runway).
   Landmark packs get a small diamond marker.
3. **Selection.** Click = select tile; drag/⌘-click = multi-select. Selected
   tiles highlight; right pane lists packages affecting the selection,
   grouped Airport / Landmark / Library / Mesh / Ortho (libraries appear
   when a selected pack's DSFs reference their exports). Status shown,
   context actions apply.
4. **Scoped analysis.** Analyze (toolbar, enabled when ≥1 tile selected)
   runs the engine restricted to the selected packs (+ Log.txt findings
   filtered to them). Whole-install analysis remains available (Analyze All,
   ⌘⇧R). Results land in the bottom third: category groups with total
   counts, expand/collapse, the existing rows inside, multi-select + Fix.
5. **Search + filter** in the toolbar: search zooms the map to matching
   airports/packages (ICAO, name); filters by kind/status/severity apply to
   both map overlays and lists.
6. The old report window's content becomes the bottom pane; Modifications
   stays its own window. Settings unchanged.

## Phase 3 — Identity

1. **App icon** (user-specified design): an FAA-sectional-style airport
   symbol, half of it under a magnifying glass — the part inside the lens
   enlarged. The airport symbol is flat vector (sectional magenta); the
   magnifying glass is richly rendered — brass rim with gradient highlights,
   wooden handle with grain, a glint on the glass. Rendered by a Swift
   CoreGraphics script to a 1024px squircle master, iconutil → .icns,
   wired into make_app.sh.

## Deliberate choices (veto welcome)

- Custom canvas map over MapKit: offline, styleable, no entitlements.
- Spill lights demoted to info until a "reduce radius" assisted fix ships.
- Analyze scope: tile-selection–driven per the redesign, with Analyze All
  preserved for the full-install sweep.

## Order & validation

Phase 0 → 1 → 2 → 3, tests extended per phase (map math, reachability BFS,
default-library resolution, pack-status transitions). Each phase validated
against the real 1,669-pack install before commit, like previous rounds.
