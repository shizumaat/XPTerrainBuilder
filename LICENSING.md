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
| Files ported from OrthoStudio XP: `Ortho4XP/src/O4_Imagery_Fetch.py`, `Ortho4XP/src/O4_Imagery_Certs.py`, `Ortho4XP/tests/test_imagery_fetch_async.py`, `Ortho4XP/tests/test_imagery_certs.py` (each names its origin in its header) | **GPL v3**, plus OrthoStudio XP's GPL §7 additional terms (`Ortho4XP/THIRD_PARTY/orthostudio-xp/NOTICE`) | radioharris, 2026; modifications Noah Lieberman, 2026 |
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
  (`dsf_reader`, `flat_site_mode`), `O4_Qt_GUI.py` (`object_rebake`).

Both directions run in one Python process. Contributions to these
directories are accepted under GPL v3.

## 3. Bundled third-party binaries

Everything in `Ortho4XP/Utils/{mac,win,lin}/` is redistributed. Binary
releases **must** carry the notices for all of it.

| Component | License | Obligation on us |
| --- | --- | --- |
| **Triangle / Triangle4XP** (J. Shewchuk; 4XP mods by O. Pilote) | Custom — **no compensation may be received**; commercial distribution only by direct arrangement with the author | **Free-of-charge distribution only.** Ship source (`Utils/src/`) and object code, keep the header notice intact, state clearly that it is modified. See §6. |
| **DSFTool**, **DDSTool** (Laminar Research, xptools) | MIT/X11 | Reproduce notice. Source: <http://dev.x-plane.com/cgit/cgit.cgi/xptools.git/> |
| **7-Zip** / `7zz`, `7z.exe`, `7z.dll` (Igor Pavlov) | LGPL 2.1+, plus BSD-3 (LZFSE) and the unRAR restriction | Reproduce the full license block from `Licence/copyright.txt` verbatim in binary releases |
| **nvcompress** / NVIDIA Texture Tools (I. Castaño, NVIDIA) | MIT | Reproduce notice |
| **osmium-tool** 1.19.1 + libosmium, protozero, nlohmann/json, Boost, lz4 | GPL v3 (tool); Boost/MIT/BSD (deps) | Offer source. Already documented in [`Ortho4XP/Utils/osmium-tool-NOTICE.md`](Ortho4XP/Utils/osmium-tool-NOTICE.md) with exact tags and build recipe — this is the template the other components should match |
| Bundled wheels (`numpy`, `gdal`) | BSD-3 / MIT | Reproduce notices |
| **OrthoStudio XP** (radioharris, <https://github.com/radioharris/orthostudio-xp>, at `7c028d82d`) — ported source, not a binary (RULINGS 2026-10-17c): the async imagery fetcher (`net/fetch.py`, `net/certs.py` → `O4_Imagery_Fetch.py`, `O4_Imagery_Certs.py`), the in-process DDS encoder (`textures/*` → `O4_DDS_Encode.py`, `O4_DDS_Mips.py`, `O4_DDS_Refine.py`, `O4_DDS_Decode.py`, header writer in `O4_DDS_File.py`) and the mesh / Triangle I/O (`mesh/*`, `numtext.py` → `O4_Mesh_IO.py`, `O4_Triangle_IO.py`, `O4_Triangle_Binary.py`, `O4_Num_Text.py`; the Triangle4XP `-b` hunks are under Triangle's licence, `Utils/Triangle4XP-CHANGES.md`) | GPL v3 with §7 additional terms: (b) keep radioharris's copyright notice and author attribution, (c) a modified version carries its own name, (e) no trademark right in "OrthoStudio XP" | Keep each ported file's header; ship [`Ortho4XP/THIRD_PARTY/orthostudio-xp/NOTICE`](Ortho4XP/THIRD_PARTY/orthostudio-xp/NOTICE) (E's NOTICE, byte-identical); the About box of both apps credits radioharris / OrthoStudio XP. Code lands only under `Ortho4XP/` (GPL v3), never under the MIT paths |
| **ispc_texcomp** 1.0.1 (Python wheel, native extension; R. Kolbe's bindings of Intel's ISPCTextureCompressor) — frozen in only for the in-process DDS encoder (`O4_DDS_Encode`, default on, `O4_DDS_ENCODER=tool` opts out (RULINGS 2026-10-17d)) | MIT (bindings: wheel `LICENSE`, Copyright (c) 2022 Rudolf Kolbe; compressor: Intel, MIT per <https://github.com/GameTechDev/ISPCTextureCompressor> — not repeated in the wheel, so our notice must carry it) | Reproduce both notices |

**Removed as of v1.0.0-alpha.1 — no longer in the tree, shipped by no
artifact:** **medit** 2.3 (Pascal Frey — proprietary, APP-registered
IDDN.FR.001.410023.00.R.P.2001.000.10800; its distribution authorization was
given to Ortho4XP specifically) and **moulinette** (Pascal / Scratchfly — no
stated terms anywhere upstream). Both were deleted on 2026-08-26; see §6 (b)
and (c).

> **Gap being tracked:** upstream `Licence/copyright.txt` predates DDSTool,
> osmium, and the bundled wheels, and gives moulinette no terms at all. Our
> release notices must cover the tree we actually ship, not the tree
> upstream documented in 2018.

### 3.1 The AppImage type-2 runtime — **Linux `.AppImage` artifact only**

The Linux `.AppImage` is one file whose first ~945 KB are the AppImage
*runtime*: a small static launcher that mounts the squashfs payload and
executes `AppRun`. It is the first code a Linux user runs, so we vendor one
verified copy rather than let the build tool download it:
`scripts/appimage/runtime-x86_64`, upstream
[AppImage/type2-runtime](https://github.com/AppImage/type2-runtime) commit
`75849dce7cc37e4319b633df1f116ca895c71a12`, sha256
`1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf`
(provenance: `scripts/appimage/README.md`; the pin is enforced by
`scripts/make_appimage.sh`).

**It ships only inside the Linux AppImage.** It is not in the Linux
`tar.gz`, the Windows zip, the macOS app, or any frozen PyInstaller bundle
(it lives under `scripts/`, which no `.spec` bundles).

| Component | License | Copyright |
| --- | --- | --- |
| **AppImage type-2 runtime** (`runtime.c`) | **MIT** | © 2004-23 probonopd |
| **musl libc** (Alpine 3.21; the runtime is built in an Alpine chroot) | **MIT** | © 2005-2020 Rich Felker and contributors |
| **libfuse 3.15.0** — `lib/` + `include/`, patched with upstream's `patches/libfuse/mount.c.diff` | **LGPL v2.1** (libfuse's other files are GPL v2 and are *not* linked in) | © Miklos Szeredi and contributors |
| **squashfuse 0.5.2** (`libsquashfuse`, `libsquashfuse_ll`) | **BSD-2-Clause** | © 2012 Dave Vasilevsky; `squashfs_fs.h` © Phillip Lougher |
| **zstd** (Alpine 3.21 `zstd-static`) | **BSD-3-Clause** (dual-licensed BSD-3 / GPL v2; taken under BSD-3) | © Meta Platforms, Inc. and affiliates |
| **zlib** (Alpine 3.21 `zlib-static`) | **zlib license** | © 1995-2024 Jean-loup Gailly and Mark Adler |
| **mimalloc** (Alpine 3.21 `mimalloc-dev`) | **MIT** | © 2018-2025 Microsoft Corporation, Daan Leijen |

This list is upstream's own, not a guess: the link line is
`src/runtime/Makefile` at that commit
(`-lsquashfuse -lsquashfuse_ll -lzstd -lz -lfuse3 -lmimalloc`), the two
from-source dependencies and their versions are
`scripts/common/install-dependencies.sh`, and the distribution-supplied
ones are the `apk add` list in `scripts/chroot/build.sh` /
`scripts/docker/Dockerfile` (`alpine:3.21`).

**Obligation on us.** Reproduce these notices (this section is copied into
`THIRD-PARTY-NOTICES.txt`, which ships in the AppImage root). libfuse's
LGPL v2.1 §6 applies to a *static* link: users must be able to relink the
runtime against a modified libfuse. We satisfy it by identifying the exact
upstream commit above — its `BUILD.md` is a complete, containerised build
recipe for the exact binary we ship, and upstream publishes the matching
`runtime-x86_64.debug`. The runtime is not part of XPTerrainBuilder's own
GPL v3 work: it is an unmodified upstream launcher concatenated in front of
our payload, which is why it is listed here rather than in §1.

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
  `pyproj`, `Rtree`, `keyring`, `gdal`, `lazrs` (MIT); `requests` (Apache-2.0);
  `osmium`, `laspy` (BSD-2).
- `curl_cffi` 0.16.3 — **MIT** (recorded from the installed wheel's metadata,
  `License-Expression: MIT`, 2026-10-17). Its `_wrapper` extension carries
  libcurl statically linked (the curl-impersonate build: curl, BoringSSL,
  nghttp2, brotli, zstd, zlib — permissive licences; component notices to be
  reproduced in release notices, not yet verified one by one). Pulls `cffi`
  (MIT-0) and `pycparser` (BSD-3). Shipped for the async imagery fetcher
  (`O4_IMAGERY_FETCHER=async`).
- `certifi` — **MPL-2.0** (unmodified; already shipped as `requests`'
  dependency): the CA bundle of the async imagery fetcher only.

## 5. Generated scenery is not covered

Oscar Pilote's statement in `Licence/copyright.txt`:

> "The output of Ortho4XP covered works is not considered a covered work
> (according to GPL v3's definition). Mesh and dsf files built using
> Ortho4XP covered works and used in commercial products are subject to the
> Creative Commons Attribution license."

So a user's `.dsf`/mesh output is **not** GPL'd, and nothing we ship makes
their scenery open source. The CC-BY sentence is the author asking for
attribution when scenery is sold; honor it by crediting Ortho4XP. We ask
the same for this project on top of it: scenery sold commercially should
credit XPTerrainBuilder as well when it was built using our `auto_patch`
airport terrain — the graded airport surfaces.

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

**(b) medit is dropped — RESOLVED (removed 2026-08-26).** A mesh *viewer*
referenced by no Python code path in this tree, whose distribution
authorization was given to Ortho4XP specifically — thin ground for a fork.
`Utils/lin/medit-2.3-linux` and `Utils/win/medit-2.3-win.exe` were deleted;
no proprietary component remains in the release.

**(c) moulinette is dropped — RESOLVED (removed 2026-08-26).** It had no
stated terms anywhere upstream, and was invoked only by the GUI's per-step
mesh re-sort (`O4_Mesh_Utils.sort_mesh`), never by `build_all`;
`Utils/mac/moulinette` never existed, so the macOS path was already the
no-moulinette path. `Utils/lin/moulinette` and `Utils/win/moulinette.exe`
were deleted and `sort_mesh` now refuses with an explanatory message when
the binary is absent. Reimplementing the ZL-bucket triangle re-sort in
Python remains open as a feature, not a licensing item.

**(d) Notices must ship with binaries.** Every release artifact needs a
`THIRD-PARTY-NOTICES` file assembled from §3 and §4, plus
`Ortho4XP/Licence/gpl.txt`. See `docs/RELEASES-PLAN.md` §G.

## 7. Contributing

Contributions to `Sources/`, `Tests/`, `scripts/`, `tools/` are accepted
under MIT. Contributions anywhere under `Ortho4XP/` — including
`auto_patch/` and `o4_engine/` — are accepted under GPL v3.
