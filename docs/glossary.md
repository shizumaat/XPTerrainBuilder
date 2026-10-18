# Glossary — the words the apps show

One shared table of user-facing words, used by the Mac app, the Qt app and
these docs (issue #831). The engine's internal names, the wire protocol and
the law vocabulary stay as they are; only what a user reads changes.

The machine-readable tables are `Ortho4XP/src/O4_Glossary.py` (Qt app) and
`Sources/SceneryKit/Glossary.swift` (Mac app).
`Ortho4XP/tests/test_glossary_parity.py` fails when the two differ, when a
wording below is missing from them, or when a retired word comes back as a
primary label in either app.

## The owner's table (issue #831, verbatim)

| Shown today (example location) | Plain wording |
|---|---|
| "Build ZL", ZL16 (`BuildPane.swift:343`) | "Detail: Standard (~2 m per pixel)", ZL as secondary text |
| DSF, "Imagery & DSF" (`BuildPane.swift:352`) | "Scenery file" / "Imagery and scenery file" |
| "Triangulate 3D mesh" (`OrthoBuildRunner.swift:43`) | "Shape the ground" |
| "Draw water masks" (`:44`) | "Blend coastlines and water" |
| "Assemble vector data" (`:42`) | "Download map data (roads, water, airports)" |
| "Auto-patch airports (runway slopes)" (`SettingsLayout.swift:96`) | "Grade airports to official standards (FAA / ICAO / EASA)" |
| "Modify custom airports (reseat objects)" (`SettingsLayout.swift:100`) | "Fit custom airport buildings to the new ground" |
| Patch, "Save Patch", "Revert to auto…" (`PatchSaveBar.swift`) | "Airport ground shape", "Save my edits", "Undo my edits" |
| CIFP / AIRAC (`MapMainView.swift:379`, `SettingsLayout.swift:49`) | "X-Plane's runway data" |
| Overlays / "Extract overlays" (`BuildPane.swift:354`) | "Roads, forests and buildings from X-Plane" |
| Lidar insets / DEM | "High-resolution airport elevation" / "Elevation source" |
| Bathymetry | "Underwater depth near the shore" |
| Overpass server | "Map data server" |
| Curvature tolerance, min_angle, limit_tris, mask_zl, texture mode | Expert-only labels (see the Settings issue) |
| Census, law families, airside, terrace | Not shown in the UI. If a summary is shown: "Airport surface check: N spots outside the rules" |

## Derived wording (not in the owner's table)

| Where | Plain wording |
|---|---|
| A progress row while airports are graded | "Grading airports" |
| The Build-pane toggle that runs the first three steps | "Map data, ground shape and water" |
| Detail levels (ZL12–ZL21) | Very coarse, Coarse, Low, Light, **Standard** (ZL16), Sharp, Very sharp, Ultra sharp, Extreme, Maximum — each with its pixel size at the equator (~40 m … ~0.07 m) |

## Rules

- A **primary label** (a title, button, toggle, menu item or row name) uses
  the plain wording. The old word may stay in secondary text: help,
  tooltips, file names, and the ZL number after a detail level.
- **Settings rows** (issue #823) are worded in ONE table,
  `Ortho4XP/src/O4_Settings_Model.py` `_LAYOUT`, mirrored row for row by
  `Sources/XPTerrainBuilder/SettingsLayout.swift`
  (`Ortho4XP/tests/test_settings_layout_parity.py` keeps them equal). A row
  outside Expert is a plain question (or a term from this glossary) with a
  one-line hint and the recommended value (the shipped default). Its label
  never names a config key or a technical word (`O4_Glossary.RETIRED_WORDS`:
  ZL, DEM, DSF, mesh, mask, lidar, bathymetry …).
- **Expert settings** — the mesh, mask and texture-format tuning and the
  other technical knobs — sit in each category's Expert section, collapsed
  by default. They keep their technical labels and show the config key
  (`curvature_tol`, `mask_zl` …) as secondary text, so forum advice still
  maps to them. Search matches the plain label, the hint and the key.
- Config KEYS and stored values never change with the wording.
- **Step names** reach the apps from the engine's `StepProgress` events. The
  wire values (`step_key`, `label`) never change; each app maps them to the
  plain step name where it shows them.
