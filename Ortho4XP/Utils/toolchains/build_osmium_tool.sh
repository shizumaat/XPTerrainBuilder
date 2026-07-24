#!/bin/sh
# Build the bundled osmium-tool binary (Utils/<platform>/osmium) from
# pinned release sources.  See Utils/osmium-tool-NOTICE.md for license
# (GPL-3, same as the engine; text in Licence/gpl.txt) and provenance.
#
# The binary is an ACCELERATOR: O4_OSM_Extracts feature-detects it and
# falls back to the pure-Python clip cutter when it is missing or
# failing, so a platform without a bundled binary works — just slower
# on the one-time per-area clip cut (~100x: 0.9 s vs 90 s measured on a
# 250 MB extract, 2026-07-23).
#
# macOS (native arch — run once on arm64, once on an x86_64 machine):
#   requires: cmake (pip install cmake works), Homebrew boost + lz4
#   (their static .a archives are linked in; zlib/bz2/expat come from
#   the OS).  Produces a ~3 MB binary linking only /usr/lib dylibs.
#
# Linux (x86_64 / aarch64): build in an Alpine container for a fully
#   static musl binary, or on the oldest supported glibc:
#     apk add build-base cmake boost-dev boost-static zlib-static \
#         bzip2-static expat-static lz4-static zlib-dev bzip2-dev \
#         expat-dev lz4-dev
#     ...then the same cmake invocation below plus
#     -DCMAKE_EXE_LINKER_FLAGS=-static
#
# Windows (x64): use vcpkg per osmium-tool's upstream README
#   (vcpkg install libosmium protozero boost-program-options lz4
#    nlohmann-json, then cmake with the vcpkg toolchain file, static
#    triplet x64-windows-static); ship as Utils/win/osmium.exe.
set -eu

OSMIUM_TOOL_TAG=v1.19.1
LIBOSMIUM_TAG=v2.23.1
PROTOZERO_TAG=v1.8.1
NLOHMANN_JSON_TAG=v3.11.3

WORK="${1:-$(mktemp -d)}"
echo "Building in $WORK"
cd "$WORK"

for repo_tag in \
    "https://github.com/osmcode/osmium-tool.git $OSMIUM_TOOL_TAG" \
    "https://github.com/osmcode/libosmium.git $LIBOSMIUM_TAG" \
    "https://github.com/mapbox/protozero.git $PROTOZERO_TAG"; do
  repo="${repo_tag% *}"; tag="${repo_tag#* }"
  dir="$(basename "$repo" .git)"
  [ -d "$dir" ] || git clone --depth 1 --branch "$tag" "$repo"
done
mkdir -p nlohmann-include/nlohmann
[ -f nlohmann-include/nlohmann/json.hpp ] || curl -fsSL \
  -o nlohmann-include/nlohmann/json.hpp \
  "https://github.com/nlohmann/json/releases/download/$NLOHMANN_JSON_TAG/json.hpp"

BREW_PREFIX="$(brew --prefix 2>/dev/null || echo /opt/homebrew)"
mkdir -p osmium-tool/build
cd osmium-tool/build
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=14.0 \
  -DOSMIUM_INCLUDE_DIR="$WORK/libosmium/include" \
  -DPROTOZERO_INCLUDE_DIR="$WORK/protozero/include" \
  -DNLOHMANN_INCLUDE_DIR="$WORK/nlohmann-include" \
  -DBoost_USE_STATIC_LIBS=ON \
  -DLZ4_LIBRARY="$BREW_PREFIX/opt/lz4/lib/liblz4.a" \
  -DLZ4_INCLUDE_DIR="$BREW_PREFIX/opt/lz4/include" \
  -DBUILD_TESTING=OFF
cmake --build . -j"$(sysctl -n hw.ncpu 2>/dev/null || nproc)"

echo
echo "Built: $WORK/osmium-tool/build/src/osmium"
./src/osmium --version | head -1
otool -L src/osmium 2>/dev/null || ldd src/osmium 2>/dev/null || true
echo "Install: cp $WORK/osmium-tool/build/src/osmium <engine>/Utils/mac/osmium"
