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

Platforms without a bundled binary (macOS x86_64, Windows x64, Linux)
automatically use a system `osmium` from the PATH when present, and the
pure-Python cutter otherwise — the engine degrades gracefully, nothing
breaks.  To add one, see the build recipe's per-platform notes.
