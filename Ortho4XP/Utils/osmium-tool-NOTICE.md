# Bundled osmium-tool

`Utils/<platform>/osmium` is **osmium-tool**, copyright Jochen Topf
<jochen@topf.org>, licensed under the **GNU General Public License
version 3** — the same license as Ortho4XP itself; the full text ships
in `Licence/gpl.txt`.  It is invoked as a separate subprocess by
`src/O4_OSM_Extracts.py` to cut per-area clips out of the regional OSM
extracts (`osmium extract --strategy smart --option types=any`), about
100x faster than the pure-Python cutter it falls back to.

Source code for the exact versions built:

* osmium-tool 1.19.1 — https://github.com/osmcode/osmium-tool (tag v1.19.1)
* libosmium 2.23.1 — https://github.com/osmcode/libosmium (tag v2.23.1)
* protozero 1.8.1 — https://github.com/mapbox/protozero (tag v1.8.1)
* nlohmann/json 3.11.3 — https://github.com/nlohmann/json (tag v3.11.3)
* Boost.Program_options and lz4, statically linked from their release
  sources (Homebrew builds of boost 1.90.0 and lz4 1.10.0 on macOS).

The reproducible build recipe is `Utils/toolchains/build_osmium_tool.sh`.

Binaries currently bundled:

| Path | Platform | Built | Notes |
| --- | --- | --- | --- |
| `mac/osmium` | macOS arm64 | 2026-07-23 | static boost/lz4; links only OS-provided dylibs (libz, libexpat, libbz2, libc++); deployment target macOS 14 |
| `win/osmium.exe` | Windows x64 | — not yet bundled | vcpkg `x64-windows-static` build (static CRT + deps); produced by CI, awaiting landing |
| `lin/osmium` | Linux x86_64 | — not yet bundled | fully static musl (Alpine) build, runs on any distro; produced by CI, awaiting landing |
| `lin/osmium-aarch64` | Linux aarch64 | — not yet bundled | same static musl build; the arch-suffixed name wins the lookup on aarch64 |

Platforms without a bundled binary automatically use a system `osmium`
from the PATH when present, and the pure-Python cutter otherwise — the
engine degrades gracefully, nothing breaks.  Per-platform resolution
(`src/O4_OSM_Extracts.py`, `_osmium_binary()`): `mac/osmium` is one
universal (arm64 + x86_64) file; on Linux an arch-suffixed
`lin/osmium-<uname -m>` is preferred over the plain `lin/osmium`
(x86_64, like the other `lin` binaries); Windows is x64-only.

## Cross-building

The GitHub Actions workflow `.github/workflows/build-osmium.yml`
(**repo root** of XPTerrainBuilder — the vendored `Ortho4XP/.github/`
directory is not active on GitHub) builds every platform from the pins
in `Utils/toolchains/build_osmium_tool.sh` on hosted runners:

* macOS arm64 + x86_64, `lipo`-merged into one universal binary;
* Windows x64 via vcpkg (`x64-windows-static`, static CRT);
* Linux x86_64 + aarch64, fully static musl builds in Alpine
  containers (run on native runners, so each binary is also executed
  on a glibc host as part of verification).

Every job verifies its binary with an exact `osmium --version` pin
check plus an `osmium extract` smoke test using the engine's flags
(`Utils/toolchains/smoke_test_osmium.sh` — also the check to run on a
manually built binary).  To land binaries: run the workflow (Actions
tab → "Build osmium-tool" → Run workflow), download the
`osmium-binaries` artifact, `tar -xzvf osmium-binaries.tar.gz -C
Ortho4XP/`, and update the Built column above.  Binaries can land
incrementally — any subset works.
