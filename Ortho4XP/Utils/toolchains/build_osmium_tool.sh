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
# macOS (native arch — run once on arm64, once on an x86_64 machine,
#   then `lipo -create` the two into a universal Utils/mac/osmium):
#   requires: cmake (pip install cmake works), Homebrew boost + lz4
#   (their static .a archives are linked in; zlib/bz2/expat come from
#   the OS).  Produces a ~3 MB binary linking only /usr/lib dylibs.
#
# Linux (x86_64 / aarch64): run this same script inside an Alpine
#   container for a fully static musl binary (runs on any distro):
#     apk add build-base cmake git curl boost-dev boost-static \
#         zlib-dev zlib-static bzip2-dev bzip2-static \
#         expat-dev expat-static lz4-dev lz4-static
#   The non-Darwin branch below adds -static and points every dep at
#   its .a archive.  Ship as Utils/lin/osmium (x86_64) or
#   Utils/lin/osmium-aarch64 (arch-suffixed names win the
#   O4_OSM_Extracts._osmium_binary() lookup on Linux).
#
# Windows (x64): use vcpkg per osmium-tool's upstream README
#   (vcpkg install --triplet x64-windows-static boost-program-options
#    bzip2 expat lz4 zlib, header-only deps from the pinned tags below,
#    then cmake with the vcpkg toolchain file); ship as
#    Utils/win/osmium.exe.  The exact recipe is the windows job of
#    .github/workflows/build-osmium.yml (repo root), which sources its
#    version pins from this file.
#
# CI: .github/workflows/build-osmium.yml builds and smoke-tests every
# platform on GitHub-hosted runners — no local cross-build machine
# needed.  Verification for any binary, however built:
#   sh Utils/toolchains/smoke_test_osmium.sh <path-to-osmium>
set -eu

OSMIUM_TOOL_TAG=v1.19.1
LIBOSMIUM_TAG=v2.23.1
PROTOZERO_TAG=v1.8.1
NLOHMANN_JSON_TAG=v3.11.3

WORK="${1:-$(mktemp -d)}"
echo "Building in $WORK"
mkdir -p "$WORK"
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

mkdir -p osmium-tool/build
cd osmium-tool/build
set -- \
  -DCMAKE_BUILD_TYPE=Release \
  -DOSMIUM_INCLUDE_DIR="$WORK/libosmium/include" \
  -DPROTOZERO_INCLUDE_DIR="$WORK/protozero/include" \
  -DNLOHMANN_INCLUDE_DIR="$WORK/nlohmann-include" \
  -DBoost_USE_STATIC_LIBS=ON \
  -DBUILD_TESTING=OFF
case "$(uname -s)" in
  Darwin)
    BREW_PREFIX="$(brew --prefix 2>/dev/null || echo /opt/homebrew)"
    set -- "$@" \
      -DCMAKE_OSX_DEPLOYMENT_TARGET=14.0 \
      -DLZ4_LIBRARY="$BREW_PREFIX/opt/lz4/lib/liblz4.a" \
      -DLZ4_INCLUDE_DIR="$BREW_PREFIX/opt/lz4/include"
    ;;
  *)
    # Alpine/musl: fully static.  Every dep is pointed at its .a
    # archive explicitly — find_package would hand cmake the .so
    # paths, which -static cannot link.
    set -- "$@" \
      -DCMAKE_EXE_LINKER_FLAGS=-static \
      -DZLIB_LIBRARY=/usr/lib/libz.a \
      -DBZIP2_LIBRARY_RELEASE=/usr/lib/libbz2.a \
      -DEXPAT_LIBRARY=/usr/lib/libexpat.a \
      -DLZ4_LIBRARY=/usr/lib/liblz4.a \
      -DLZ4_INCLUDE_DIR=/usr/include
    ;;
esac
cmake .. "$@"
cmake --build . -j"$(sysctl -n hw.ncpu 2>/dev/null || nproc)"

echo
echo "Built: $WORK/osmium-tool/build/src/osmium"
./src/osmium --version | head -1
otool -L src/osmium 2>/dev/null || ldd src/osmium 2>/dev/null || true
echo "Install: cp $WORK/osmium-tool/build/src/osmium <engine>/Utils/<platform>/osmium"
