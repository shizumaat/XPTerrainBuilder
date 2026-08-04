# Licensing

This repository is **not** under a single license. It is an aggregation of a
GPL v3 engine, MIT-licensed application code, and a set of third-party
binaries with their own terms — one of which (**Triangle**) forbids
distribution for compensation.

This file is authoritative. The root [`LICENSE`](LICENSE) covers only the
parts named below as MIT.

---

## 1. Scope: what is under what

| Path | License | Copyright |
| --- | --- | --- |
| `Sources/`, `Tests/`, `Resources/`, `scripts/`, `tools/`, `sim_review/` | **MIT** | Noah Lieberman, 2026 |
| `Ortho4XP/` (the whole vendored engine tree) | **GPL v3** | Oscar Pilote 2014–2018, and contributors |
| `Ortho4XP/src/auto_patch/`, `Ortho4XP/src/o4_engine/` | **GPL v3** (see §2) | Noah Lieberman, 2026 |
| `Ortho4XP/Utils/**` (binaries) | Various — see §3 | Various |
| `docs/`, `Ortho4XP/docs/` | Same license as the tree they document | — |

The engine's own license texts ship in
[`Ortho4XP/Licence/`](Ortho4XP/Licence): `gpl.txt` (the GPL v3 text) and
`copyright.txt` (Oscar Pilote's statement plus upstream third-party notices).

## 2. Why our own engine code is GPL v3

`auto_patch/` and `o4_engine/` are original work, but they are **derivative
works of the GPL v3 engine** and are distributed under GPL v3. This is not a
choice we can revisit while the code sits where it sits — the coupling is
mutual and in-process:

- `auto_patch` imports engine modules (`O4_UI_Utils`, `O4_File_Names`,
  `O4_DEM_Utils`, `O4_OSM_Utils`, `O4_Vector_Map`, `O4_Geo_Utils`,
  `O4_Config_Utils`, `O4_OSM_Extracts`, `O4_Version`).
- The engine imports back **into** `auto_patch` — `O4_Default_Terrain_Map.py`
  (`dsf_reader`, `agp_reader`), `O4_Airport_Elevation_Insets.py`
  (`cifp_reader`), `O4_Qt_GUI.py` (`object_rebake`).

Both directions run in one Python process. Contributions to these
directories are accepted under GPL v3.

## 3. Bundled third-party binaries

Everything in `Ortho4XP/Utils/{mac,win,lin}/` is redistributed. Binary
releases **must** carry the notices for all of it.

| Component | License | Obligation on us |
| --- | --- | --- |
| **Triangle / Triangle4XP** (J. Shewchuk; 4XP mods by O. Pilote) | Custom — **no compensation may be received**; commercial distribution only by direct arrangement with the author | **Free-of-charge distribution only.** Ship source (`Utils/src/`) and object code, keep the header notice intact, state clearly that it is modified. See §6. |
| **medit** 2.3 (Pascal Frey) | Proprietary; APP-registered (IDDN.FR.001.410023.00.R.P.2001.000.10800). Distribution authorized by the author *for Ortho4XP* | Ships in `lin/`, `win/`. **Unused by any code path** — see §6. |
| **moulinette** (Pascal / Scratchfly) | **No stated terms** anywhere upstream | Ships in `lin/`, `win/`; absent on macOS. GUI-only mesh re-sort. See §6. |
| **DSFTool**, **DDSTool** (Laminar Research, xptools) | MIT/X11 | Reproduce notice. Source: <http://dev.x-plane.com/cgit/cgit.cgi/xptools.git/> |
| **7-Zip** / `7zz`, `7z.exe`, `7z.dll` (Igor Pavlov) | LGPL 2.1+, plus BSD-3 (LZFSE) and the unRAR restriction | Reproduce the full license block from `Licence/copyright.txt` verbatim in binary releases |
| **nvcompress** / NVIDIA Texture Tools (I. Castaño, NVIDIA) | MIT | Reproduce notice |
| **osmium-tool** 1.19.1 + libosmium, protozero, nlohmann/json, Boost, lz4 | GPL v3 (tool); Boost/MIT/BSD (deps) | Offer source. Already documented in [`Ortho4XP/Utils/osmium-tool-NOTICE.md`](Ortho4XP/Utils/osmium-tool-NOTICE.md) with exact tags and build recipe — this is the template the other components should match |
| Bundled wheels (`numpy`, `gdal`) | BSD-3 / MIT | Reproduce notices |

> **Gap being tracked:** upstream `Licence/copyright.txt` predates DDSTool,
> osmium, and the bundled wheels, and gives moulinette no terms at all. Our
> release notices must cover the tree we actually ship, not the tree
> upstream documented in 2018.

## 4. Python dependencies (frozen into release builds)

PyInstaller embeds these, so releases redistribute them.

- **PySide6 6.11.1 — LGPL v3** (Qt builds only: `Ortho4XP_Qt.spec`, i.e. the
  Windows and Linux apps). LGPL §4 requires that users be able to relink
  against a modified Qt/PySide6. In a frozen one-dir build this is
  satisfied by shipping the Qt shared libraries as separate `.so`/`.dylib`/
  `.dll` files (PyInstaller onedir already does this — **do not switch the
  Qt builds to onefile**) and by publishing the exact PySide6/Qt versions
  and the freeze recipe. The macOS app does not link Qt.
- Permissive, notice-only: `numpy`, `scipy`, `networkx`, `shapely`,
  `scikit-fmm`, `tifffile`, `imagecodecs` (BSD-3); `pillow` (MIT-CMU);
  `pyproj`, `Rtree`, `keyring`, `gdal` (MIT); `requests` (Apache-2.0);
  `osmium` (BSD-2).

## 5. Generated scenery is not covered

Oscar Pilote's statement in `Licence/copyright.txt`:

> "The output of Ortho4XP covered works is not considered a covered work
> (according to GPL v3's definition). Mesh and dsf files built using
> Ortho4XP covered works and used in commercial products are subject to the
> Creative Commons Attribution license."

So a user's `.dsf`/mesh output is **not** GPL'd, and nothing we ship makes
their scenery open source. The CC-BY sentence is the author asking for
attribution when scenery is sold; honor it by crediting Ortho4XP.

**The binding constraint on scenery is not this license — it is the imagery
terms of service.** `Ortho4XP/Providers/` ships tile templates for Esri
World Imagery, Google (`mt.google.com/vt/lyrs=s`), Bing/VirtualEarth, and
Here. Bulk tile fetching and redistribution of derived imagery violate all
four providers' terms. We do not grant, and cannot grant, any right to that
imagery. Releases must say so plainly:

> XPTerrainBuilder downloads imagery from the provider you select. You are
> responsible for complying with that provider's terms of service. Most
> commercial providers prohibit bulk download and redistribution of derived
> imagery. Scenery you build is for your own use unless the provider's
> license says otherwise.

## 6. Known issues and required actions

**(a) Triangle caps us at free distribution.** Its terms permit
redistribution only where "no compensation is received," and commercial
distribution "ONLY BY DIRECT ARRANGEMENT WITH THE AUTHOR." A free, public,
open-source release complies. Selling XPTerrainBuilder, or bundling it into
anything paid, does not. This restriction is also formally incompatible with
GPL v3 (the GPL forbids additional restrictions), which is why Debian ships
Triangle in `non-free` — an inconsistency inherited from upstream Ortho4XP,
not introduced here. It is acceptable for a free release and is a blocker
for a paid one.

**(b) medit should be dropped.** It is a mesh *viewer*, referenced by no
Python code path in this tree, and its distribution authorization was given
to Ortho4XP specifically — thin ground for a fork. Removing it costs nothing
and deletes a proprietary component from the release:

```bash
git rm Ortho4XP/Utils/lin/medit-2.3-linux Ortho4XP/Utils/win/medit-2.3-win.exe
```

**(c) moulinette has no license at all.** It is invoked only by the GUI's
per-step mesh re-sort (`O4_Mesh_Utils.sort_mesh`), never by `build_all`, and
`Utils/mac/moulinette` does not exist — the macOS app already ships without
it. Either obtain terms from the author, drop it and let the mac path be the
only path, or reimplement the ZL-bucket triangle re-sort in Python.

**(d) Notices must ship with binaries.** Every release artifact needs a
`THIRD-PARTY-NOTICES` file assembled from §3 and §4, plus
`Ortho4XP/Licence/gpl.txt`. See `docs/RELEASES-PLAN.md` §G.

## 7. Contributing

Contributions to `Sources/`, `Tests/`, `scripts/`, `tools/` are accepted
under MIT. Contributions anywhere under `Ortho4XP/` — including
`auto_patch/` and `o4_engine/` — are accepted under GPL v3.
