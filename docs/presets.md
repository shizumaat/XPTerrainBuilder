# Settings presets (issue #822)

Three cards at the top of Settings (Mac: Settings ▸ General; Qt: above the
categories) and on the first-run screen (Mac: the X-Plane folder screen; Qt:
the setup assistant's Imagery page). One click writes the preset's keys; the
rows that show those keys change at once. When any of the keys differs from
every preset, the cards show **Custom**.

The table lives in `Ortho4XP/src/O4_Settings_Presets.py` (Qt app) and
`Sources/XPTerrainBuilder/SettingsPresets.swift` (Mac app).
`Ortho4XP/tests/test_settings_presets.py` fails when the two differ, when a
preset writes another key set, when Recommended stops being the shipped
defaults, or when a GB figure below stops matching its derivation.

## The keys

Every preset writes the same four existing keys. None is new, and none changes
its stored format.

| Key | Where it is stored | Recommended | Sharper airports | Light on disk |
|---|---|---|---|---|
| `zl` | Build zoom: Qt `prefs["zl"]`, Mac `@AppStorage("OrthoZoomLevel")` | 16 | 16 | 15 |
| `cover_airports_with_highres` | Global `Ortho4XP.cfg` | False | True | False |
| `cover_zl` | Global `Ortho4XP.cfg` | 18 | 18 | 18 |
| `cover_extent` | Global `Ortho4XP.cfg` | 1.0 | 1.0 | 1.0 |

- **Recommended** equals the registry defaults (`O4_Cfg_Vars`; the build zoom
  is `default_zl`'s default, 16, as both apps' zoom default).
- **Sharper airports** turns on the existing airport high-detail zones: ZL18
  imagery (`cover_zl` 18, about 0.6 m per pixel) over each airport and
  1 km around it (`cover_extent`).
- **Light on disk** builds at ZL15 (`zl` 15, about 5 m per pixel).

Owner rulings, 2026-10-18: detail levels are named by their ZL number,
never by an invented name; **Light on disk** does NOT set `cleaning_level`
(no preset touches it: the build-file cleanup stays whatever the user set);
**Sharper airports** keeps `cover_zl` 18 and `cover_extent` 1.0.

Presets set the GLOBAL values, the defaults for new tiles. A tile's own
overrides are kept; its Settings rows go on showing them. A key outside the
table never makes the cards show Custom.

## Card text

| Preset | Summary | Cost line |
|---|---|---|
| Recommended | The settings the app ships with: ZL16 everywhere. | About 1.6–3.1 GB of imagery per tile. |
| Sharper airports | ZL16, and ZL18 imagery on and around every airport. | About 1.6–3.1 GB per tile, plus the sharper airports. |
| Light on disk | ZL15 everywhere: coarser imagery, smaller downloads. | About 0.4–0.8 GB of imagery per tile, a quarter of Recommended. |

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
The Qt Build pane's existing rough estimate is 3.0 GB × 4^(zl − 16) per tile
(`O4_Qt_GUI._update_build_summary`).

**Derived: relative imagery work.** Downloading and converting imagery scales
with the texture count. Light on disk's imagery work is therefore a quarter of
Recommended's (4^(16 − 15) = 4).

## Measured by the master (not filled)

These need a corpus build. The lane that wrote this table had none.

| Constant (`O4_Settings_Presets`) | What it is | Value |
|---|---|---|
| `SHARPER_AIRPORTS_EXTRA_GB` | Extra imagery GB per tile that Sharper airports adds. It depends on how many airports a tile holds, so it is a range. | not filled |
| `RELATIVE_BUILD_TIME` | Whole-tile build time relative to Recommended, per preset. | not filled |

The cards do not show these yet. When they are measured, add them to each
preset's cost line, in Python and Swift together.
