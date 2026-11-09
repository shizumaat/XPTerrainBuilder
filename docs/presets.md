# Settings presets (issue #822)

Three cards at the top of Settings (Mac: Settings ▸ General; Qt: above the
categories) and on the first-run screen (Mac: the X-Plane folder screen; Qt:
the setup assistant's Imagery page). One click writes the preset's keys; the
rows that show those keys change at once. When any of the keys differs from
every preset, the cards show **Custom**.

The table lives in `Ortho4XP/src/O4_Settings_Presets.py` (Qt app) and
`Sources/XPTerrainBuilder/SettingsPresets.swift` (Mac app).
`Ortho4XP/tests/test_settings_presets.py` fails when the two differ, when a
preset writes another key set, when a preset's airport keys stop being its
Detail choice's, or when a GB figure below stops matching its derivation.

The cards read Light on disk, Balanced, Sharper airports, left to right
(owner, #937). **Sharper airports is the default preset:** a new user's
first-run screen (Mac: the X-Plane folder screen; Qt: the setup assistant)
applies it when the global config sets none of the preset keys yet
(`O4_Settings_Presets.unset_in`, `DEFAULT_PRESET`; Swift
`applyDefaultPresetIfUnset`, `defaultKey`). An existing config keeps its
values. The engine's registry defaults do not change, so builds outside
the apps (the harness, the CLI) do not change either; since #1985 they
match no preset (grading and elevation at ICAO airports, sharper imagery
off), and a config at those defaults shows Custom.

## The keys

Every preset writes the same existing keys. None is new, and none changes
its stored format. Every preset is airport **Detail** "ICAO airports"
(#1985, `O4_Airport_Detail` / `AirportDetail.swift`; owner 2026-11-09T17:01Z:
"keep ICAO for all presets, ZL16 imagery everywhere but lidar elevation
data just at the airport without the approach rings, and the light option
drops elevation data to 30m at icao airports and 90m elsewhere"; 17:05Z:
"For all presets let's keep ZL18 at airports, but adjust the amount of
coverage, for light it's only within the airport boundary"): they differ
in the approach rings and how fine the elevation is. The ZL18 airport
imagery covers each ICAO airport inside its boundary (`cover_extent` 0 in
all three); the approach corridors (#1990, `cover_approach_ft`) add the
coverage beyond it.

| Key | Where it is stored | Light on disk | Balanced | Sharper airports |
|---|---|---|---|---|
| `zl` | Build zoom: Qt `prefs["zl"]`, Mac `@AppStorage("OrthoZoomLevel")` | 15 | 16 | 16 |
| `cover_zl` | Global `Ortho4XP.cfg` | 18 | 18 | 18 |
| `cover_extent` | Global `Ortho4XP.cfg` | 0.0 | 0.0 | 0.0 |
| `elevation_level` | Global `Ortho4XP.cfg` | 90 | auto | auto |
| `airport_elevation_level` | Global `Ortho4XP.cfg` | 30 | auto | auto |
| `approach_rings` | Global `Ortho4XP.cfg` | off | off | auto |
| `cover_approach_ft` | Global `Ortho4XP.cfg` | 0 | 500 | 1000 |
| `cover_airports_with_highres` | Global `Ortho4XP.cfg` | ICAO | ICAO | ICAO |
| `auto_patch` | Global `Ortho4XP.cfg` | ICAO | ICAO | ICAO |
| `airport_elevation_insets` | Global `Ortho4XP.cfg` | ICAO | ICAO | ICAO |
| `bathymetry_near_icao_airports` | Global `Ortho4XP.cfg` | True | True | True |
| `bathymetry_near_other_airports` | Global `Ortho4XP.cfg` | False | False | False |

- **Light on disk** builds at ZL15 (`zl` 15, about 5 m per pixel), with
  ZL18 inside each ICAO airport's boundary, 90 m
  elevation away from airports and the airport elevation warped to
  30 m (`airport_elevation_level` 30), no approach rings.
- **Balanced** builds at the registry's zoom (`default_zl`'s default, 16,
  as both apps' zoom default), ZL18 inside each ICAO airport's boundary,
  the best airport elevation but no approach rings. It equals the registry
  defaults except `cover_airports_with_highres` (default False),
  `cover_extent` (default 1.0), `approach_rings` (default auto) and `bathymetry_near_other_airports`
  (default True), which the engine keeps so builds outside the apps do not
  change: an untouched config shows Custom.
- **Sharper airports** turns on the existing airport high-detail zones for
  airports with ICAO codes (`cover_airports_with_highres` ICAO, owner
  2026-10-19 on #937): ZL18 imagery (`cover_zl` 18, about 0.6 m per pixel)
  inside each such airport's boundary (`cover_extent` 0), and the
  approach rings.
- `cover_approach_ft` (#1990): the ZL18 squares also follow each runway's
  approach, from each landing threshold (apt.dat row 100, displaced
  thresholds respected) out along the extended centreline until a 3° glide
  path is this many feet above the threshold (1,000 ft ≈ 5.8 km, 500 ft ≈
  2.9 km, 0 = the airport only), widening from the runway width to 1 km.
  `cover_extent` widens the boundary polygon itself, not its bounding
  box; the squares are those meeting boundary ∪ corridors
  (`O4_Airport_Approach_Cover`).

Owner rulings, 2026-10-18: detail levels are named by their ZL number,
never by an invented name; **Light on disk** does NOT set `cleaning_level`
(no preset touches it: the build-file cleanup stays whatever the user set);
**Sharper airports** keeps `cover_zl` 18 and `cover_extent` 1.0 (the
extent superseded on 2026-11-09: 0 in every preset, the coverage beyond
the boundary coming from the approach corridors, #1990).

Presets set the GLOBAL values, the defaults for new tiles. A tile's own
overrides are kept; its Settings rows go on showing them. A key outside the
table never makes the cards show Custom.

## Detail (#1985)

Under the cards, Settings ▸ General's **Detail** chooses where airport
detail goes: **None**, **ICAO airports** or **All airports**. It reads the
four airport features — sharper imagery (`cover_airports_with_highres`),
grading (`auto_patch`), high-resolution elevation
(`airport_elevation_insets`) and measured depth (the two
`bathymetry_near_*` keys) — each off or on for one choice, and shows the
choice every feature that is on agrees on (None when all are off), else
Custom. Choosing ICAO or All from None or Custom turns every feature on,
with the build zoom 16 and `cover_zl` 18; switching between ICAO and All
re-scopes the features that are on and leaves the off ones off (Balanced
switched to All airports keeps its approach rings off); None turns them all
off. Detail is not a stored key, so the per-feature rows in their own
categories still work. The build zoom is in Settings ▸ Imagery ("Imagery
detail").

An existing config is carried over once (`O4_Airport_Detail.migrate_cfg`,
recorded in `<cfg>.defaults`): its sharper-imagery scope, else its grading
scope, picks the choice, and the features that are on are re-scoped to it
wherever their keys still hold their old defaults (typically
`bathymetry_near_other_airports` True becomes False under ICAO). Nothing is
turned on or off, and a value the user chose is never changed.

## Card text

| Preset | Summary | Cost line |
|---|---|---|
| Light on disk | ZL15, and ZL18 only inside airports with ICAO codes; elevation 30 m there and 90 m elsewhere. | About 0.4–0.8 GB of imagery per tile, a quarter of Balanced, plus the airports. |
| Balanced | ZL16, and ZL18 imagery and the best elevation at airports with ICAO codes. | About 1.6–3.1 GB of imagery per tile, plus the sharper airports. |
| Sharper airports | ZL16, and at airports with ICAO codes ZL18 imagery and the best elevation, their approaches included. | About 1.6–3.1 GB per tile, plus the sharper airports. |

## Where the figures come from

The cost estimator (#820) has not landed. Until it does, every figure here is
either derived or cited. Nothing is measured in this table.

**Derived: imagery texture GB per tile.** A tile's textures are the
4096 × 4096 squares of the engine's texture grid (`O4_Geo_Utils.wgs84_to_orthogrid`)
that touch the 1° × 1° tile. Each one is a BC1 (DXT1) DDS with its full mip
chain, down to 1 × 1 (`O4_DDS_Encode`, `O4_DDS_File`):

    bytes per texture = 128 + Σ(level) ⌈w/4⌉·⌈h/4⌉·8 = 11,184,952   (≈ 8 MiB × 4/3)
    textures per tile = (grid columns touched) × (grid rows touched)
    GB per tile       = textures per tile × bytes per texture / 10⁹

At detail level z a grid square spans 360° / 2^(z−4) of longitude, so each
step up the scale multiplies the count by about 4. Rows grow toward the poles
(about 1 / cos latitude). Over tile latitudes 0° to 60°:

| Detail | Textures per tile | Imagery GB per tile |
|---|---|---|
| ZL15 | 36–72 | 0.4–0.8 |
| ZL16 | 144–276 | 1.6–3.1 |

`test_card_figures_equal_their_derivation` recomputes both rows.
`test_texture_arithmetic` checks the grid against the engine's own function.
The figures cover the textures only. Masks with imprinted alpha would be BC3,
twice the size, but that is not the default (`imprint_masks_to_dds` is False).

**Cited: whole-tile disk.** `docs/TESTING-GUIDE.md` says "3–8 GB per tile at
the default zoom". That covers the whole build folder, not just the textures.
Both apps now show the engine's per-tile ranges above Build instead of a
rule of thumb (`o4_engine/plan_estimate.py`, #820).

**Derived: relative imagery work.** Downloading and converting imagery scales
with the texture count. Light on disk's imagery work is therefore a quarter of
Balanced's (4^(16 − 15) = 4).

## Measured by the master (not filled)

These need a corpus build. The lane that wrote this table had none.

| Constant (`O4_Settings_Presets`) | What it is | Value |
|---|---|---|
| `SHARPER_AIRPORTS_EXTRA_GB` | Extra imagery GB per tile that Sharper airports adds. It depends on how many airports a tile holds, so it is a range. | not filled |
| `RELATIVE_BUILD_TIME` | Whole-tile build time relative to Balanced, per preset. | not filled |

The cards do not show these yet. When they are measured, add them to each
preset's cost line, in Python and Swift together.
