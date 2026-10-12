#!/bin/sh
# Build the bundled DSFTool (Utils/<platform>/DSFTool[.exe]) from pinned
# X-Plane/xptools sources: release 24-5 (what Laminar shipped as DSFTool
# 2.4.0-b1) plus the two upstream commits that fix the --dsf2text crash on
# an overlay whose command stream sets a 16-bit definition before its
# first pool select (issue #587, owner RULINGS 2026-10-12f; root cause in
# docs/briefs/dsftool568-notes.md).  No tool release carries the fix.
# Licence and provenance: Utils/DSFTool-NOTICE.md.
#
#   sh build_dsftool.sh WORKDIR                 # fetch, patch, build (mac / linux)
#   sh build_dsftool.sh WORKDIR --source-only   # fetch + patch only (windows job)
#
# The built tool is left at WORKDIR/DSFTool.  Every pin lives HERE; the
# windows job of .github/workflows/build-dsftool.yml (repo root) sources
# them from this file.  POSIX sh: macOS /bin/sh, dash and git-bash.
#
# THE RECIPE IS UPSTREAM'S OWN (Building.md at the pinned commit), one
# target only.  DSFTool needs far less than WED: its sources (the list in
# makerules/DSFTool) and zlib.  The `libs` submodule is NOT needed.
#
# macOS (universal arm64 + x86_64, one xcodebuild):
#     xcodebuild -project SceneryTools.xcodeproj -target DSFTool
#         -configuration Release
#   requires Xcode only; links the OS libz, libc++ and Carbon.  Two build
#   settings are overridden on the command line, no source is touched:
#   * MACOSX_DEPLOYMENT_TARGET=12.0 — the project says 10.12, which
#     current Xcode refuses ("supported deployment target versions 12.0
#     to 27.0", Xcode 27).  The app's floor is macOS 14.
#   * GCC_PREFIX_HEADER=<a two-line wrapper> — the project's prefix
#     header src/Obj/XDefs.h defines `fopen(a, b)` as a macro (its
#     case-insensitive x_fopen), and current libc++'s <fstream> calls
#     `std::fopen(...)`: tri_stripper.cpp then fails with "no member named
#     'x_fopen' in namespace 'std'".  The wrapper includes <fstream> FIRST
#     for C++ sources, then XDefs.h, so the library header is read before
#     the macro exists and every xptools source still gets x_fopen.
#     (Upstream 9c1a06c7b carries the same workaround for one file.)
#   and one compiler flag is added on every unix build:
#   * -fno-delete-null-pointer-checks — the pinned sources take
#     `&*vector.begin()` of vectors that may be EMPTY (DSFPointPool.cpp
#     WritePoolAtoms, still so on upstream master 0137e80cd).  That is
#     undefined behaviour, and a current optimiser acts on it: built with
#     Xcode 27 at the project's -Ofast, the x86_64 slice died with SIGSEGV
#     in DSF32BitPointPool::WritePoolAtoms on --text2dsf of EVERY overlay
#     (an overlay's 32-bit pool is empty), measured 2026-10-12; -O0 did
#     not, the arm64 slice did not.  The flag tells the compiler not to
#     reason from "this pointer was dereferenced, so it is not null"; with
#     it both slices encode and dump.  The smoke test encodes on every
#     slice, so a build where this returns fails there.
#
# Linux x86_64 (run on the oldest glibc the frozen engine supports —
#   ubuntu-22.04, glibc 2.35, as .github/workflows/release.yml does):
#     make conf=release_opt DSFTool CC="gcc <flag>" CXX="g++ <flag>"
#   (the same -fno-delete-null-pointer-checks; the makefiles leave no
#   other slot for a flag — a command-line CC/CXX is passed down to
#   makerules/global/toplevel.mk)
#   requires gcc, g++, make, zlib1g-dev.  Dynamic against libc, libm,
#   libstdc++, libgcc_s and libz, exactly as the stock binary is.
#
# Windows x64: upstream's msvc/DSFTool/DSFTool.vcxproj, Release|x64,
#   static CRT, with zlib from upstream's `msvc_libs` submodule
#   (msvc_libs/include/zlib.h, msvc_libs/lib/zlibstat.lib) at the commit
#   the pinned xptools tree records.  The project names toolset v142; the
#   job overrides it with the runner's (v143).
#
# Verification for any binary, however built:
#   python3 Utils/toolchains/smoke_test_dsftool.py <path-to-DSFTool>
set -eu

XPTOOLS_REPO=https://github.com/X-Plane/xptools.git
# "compile fix linux", 2024-05-08: XPT_PACKAGE_VER 24-5, DSFTOOL_VER 2.4.0-b1.
XPTOOLS_BASE_SHA=c31ed76b58d9cb3ab6e08e6c4026b2e3bf242e52
# "Fix dsf2text crash for object def indices over 255", 2026-03-08.
XPTOOLS_FIX1_SHA=9c1a06c7b21a63da1f862de1e1cdb7d0dd0baff1
# "Fix minor error" (the same guard for terrain patches), 2026-04-14.
XPTOOLS_FIX2_SHA=a3725c8f5ed6d9681573496ab0153e550d54cd09
# The git TREE of base + fix1 + fix2.  A tree id is a hash of file content
# only, so it is the same on every machine; anything else is a refusal.
XPTOOLS_PATCHED_TREE=6dc3a2dc7e821baf6ca261fc9e6da745877a9cd9
# The msvc_libs commit the base tree records (windows only).
XPTOOLS_MSVC_LIBS_SHA=782be015dba4758a8c183c3f7d045d97da6e86e9
MACOS_DEPLOYMENT_TARGET=12.0
NULL_SAFE_FLAG=-fno-delete-null-pointer-checks

WORK="${1:?usage: build_dsftool.sh WORKDIR [--source-only]}"
MODE="${2:-build}"
mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd)"
SRC="$WORK/xptools"

if [ ! -d "$SRC/.git" ]; then
  # blobs arrive on checkout: the full history is 300 MB, this is ~40
  git clone --filter=blob:none --no-checkout "$XPTOOLS_REPO" "$SRC"
fi
cd "$SRC"
git checkout --quiet --detach "$XPTOOLS_BASE_SHA"
# a conflict, an empty pick or a missing commit stops the script here
git -c user.name=dsftool-build -c user.email=dsftool-build@localhost \
    cherry-pick "$XPTOOLS_FIX1_SHA" "$XPTOOLS_FIX2_SHA"
TREE="$(git rev-parse 'HEAD^{tree}')"
if [ "$TREE" != "$XPTOOLS_PATCHED_TREE" ]; then
  echo "FAIL: patched tree is $TREE, expected $XPTOOLS_PATCHED_TREE" >&2
  exit 1
fi
[ -z "$(git status --porcelain)" ] || {
  echo "FAIL: the source tree is not clean after the cherry-picks" >&2; exit 1; }
echo "xptools $XPTOOLS_BASE_SHA + $XPTOOLS_FIX1_SHA + $XPTOOLS_FIX2_SHA = tree $TREE"
git diff --stat "$XPTOOLS_BASE_SHA" HEAD

if [ "$MODE" = "--source-only" ]; then
  exit 0
fi

case "$(uname)" in
  Darwin)
    PREFIX="$WORK/dsftool_prefix.h"
    printf '#ifdef __cplusplus\n#include <fstream>\n#endif\n#include "%s/src/Obj/XDefs.h"\n' \
        "$SRC" > "$PREFIX"
    xcodebuild -version
    xcodebuild -project SceneryTools.xcodeproj -target DSFTool \
        -configuration Release \
        MACOSX_DEPLOYMENT_TARGET="$MACOS_DEPLOYMENT_TARGET" \
        GCC_PREFIX_HEADER="$PREFIX" \
        "OTHER_CFLAGS=\$(inherited) $NULL_SAFE_FLAG" \
        SYMROOT="$WORK/xcode" OBJROOT="$WORK/xcode/obj" build
    cp "$WORK/xcode/Release/DSFTool" "$WORK/DSFTool"
    lipo -archs "$WORK/DSFTool"
    ;;
  Linux)
    gcc --version | head -1
    make conf=release_opt DSFTool \
        CC="gcc $NULL_SAFE_FLAG" CXX="g++ $NULL_SAFE_FLAG"
    cp build/Linux/release_opt/DSFTool "$WORK/DSFTool"
    ;;
  *)
    echo "FAIL: no unix recipe for $(uname); windows runs --source-only" \
         "and msbuild (see .github/workflows/build-dsftool.yml)" >&2
    exit 1
    ;;
esac
chmod +x "$WORK/DSFTool"
echo "Built $WORK/DSFTool"
