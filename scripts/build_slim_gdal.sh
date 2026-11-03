#!/bin/zsh
# Build the SLIM GDAL the frozen macOS engine bundles (#1675).
#
# Homebrew's GDAL is the full-feature build: libgdal links ~55 libraries
# (Arrow/Parquet, SFCGAL, Poppler, HDF5, netCDF, HEIF/x265/aom, JPEG-XL,
# OpenEXR, SpatiaLite, Xerces, KML, ODBC, PostgreSQL, openssl@4 …) and the
# freeze bundles every one of them, ~100 MB the engine never opens.
#
# This builds the SAME GDAL release from its source tarball with NO optional
# external library except the ones the engine's reads need, and every GDAL
# driver that needs nothing external (GDAL_BUILD_OPTIONAL_DRIVERS stays on):
#   raster  GTiff/COG (+ DEFLATE, ZSTD, LZW, JPEG, LERC compression), VRT,
#           MEM, HFA (.img), AAIGrid (.asc), XYZ, SRTMHGT (.hgt), GSG (.grd),
#           PNG, JPEG, WCS/WMS (curl) and the rest of the internal drivers;
#   vector  GPKG (sqlite3), GeoJSON (internal json-c), ESRI Shapefile, MEM;
#   vsi     /vsicurl, /vsis3 (system libcurl), /vsizip;
#   other   PROJ, GEOS (OGR spatial filters keep their exact test).
# The census behind that list is in the #1675 PR (src/elevation_access,
# O4_Airport_Elevation_Insets, Providers/Elevation/*.elv).
#
# Libraries come from Homebrew (which the release job already installs) or
# macOS itself (libcurl, zlib, iconv) — no openssl is linked at all, which
# also drops the second libcrypto (openssl@4's) from the bundle.
#
# Usage: scripts/build_slim_gdal.sh            -> prints the install prefix
# The build is cached under ${XPTB_SLIM_GDAL_ROOT:-$TMPDIR/xptb-slim-gdal},
# keyed by the GDAL version and a hash of this script, so a rebuild happens
# only when either changes (~5 min on Apple silicon).  All progress goes to
# stderr; stdout is the prefix alone.
set -euo pipefail

GDAL_VERSION="${GDAL_VERSION:-3.13.3}"
# sha256 of the release tarball — the one Homebrew's gdal formula pins
# (brew info --json=v2 gdal → urls.stable.checksum).
typeset -A GDAL_SHA256=(
  3.13.3 5e0c388d83da2d686cc00a40272882432cdb54edff43d4af173e532844a0a0ea
)
SHA="${GDAL_SHA256[$GDAL_VERSION]:-}"
if [[ -z "$SHA" ]]; then
  echo "ERROR: no pinned sha256 for GDAL $GDAL_VERSION in $0 — add it (Homebrew's formula carries it)." >&2
  exit 1
fi

SELF_HASH="$(shasum -a 256 "$0" | cut -c1-12)"
ROOT_DIR="${XPTB_SLIM_GDAL_ROOT:-${TMPDIR:-/tmp}/xptb-slim-gdal}"
WORK="$ROOT_DIR/gdal-$GDAL_VERSION-$SELF_HASH"
PREFIX="$WORK/prefix"
if [[ -x "$PREFIX/bin/gdal-config" && -f "$PREFIX/.complete" ]]; then
  echo "$PREFIX"
  exit 0
fi

BREW="$(command -v brew || true)"
if [[ -z "$BREW" ]]; then
  echo "ERROR: Homebrew is required (it supplies proj, libtiff, libgeotiff …)." >&2
  exit 1
fi
DEPS=(proj libtiff libgeotiff sqlite libpng jpeg-turbo zstd libdeflate liblerc geos)
for DEP in $DEPS; do
  if [[ ! -d "$("$BREW" --prefix "$DEP" 2>/dev/null)/lib" ]]; then
    echo "ERROR: Homebrew formula $DEP is not installed (brew install ${DEPS[*]})." >&2
    exit 1
  fi
done
opt() { "$BREW" --prefix "$1"; }

rm -rf "$WORK"
mkdir -p "$WORK"
cd "$WORK"

TARBALL="gdal-$GDAL_VERSION.tar.gz"
echo "Fetching GDAL $GDAL_VERSION source …" >&2
curl -fsSL --retry 3 -o "$TARBALL" \
  "https://github.com/OSGeo/gdal/releases/download/v$GDAL_VERSION/$TARBALL"
GOT="$(shasum -a 256 "$TARBALL" | cut -d' ' -f1)"
if [[ "$GOT" != "$SHA" ]]; then
  echo "ERROR: $TARBALL sha256 $GOT, expected $SHA." >&2
  exit 1
fi
tar xzf "$TARBALL"

# cmake + ninja from PyPI into a private tool venv: no Homebrew change.
TOOLS="$WORK/tools-venv"
"${PYTHON:-python3}" -m venv "$TOOLS"
"$TOOLS/bin/python" -m pip install --quiet --upgrade pip >&2
"$TOOLS/bin/python" -m pip install --quiet cmake ninja >&2
export PATH="$TOOLS/bin:$PATH"

PREFIX_PATH="$(opt proj);$(opt libtiff);$(opt libgeotiff);$(opt sqlite);$(opt libpng);$(opt jpeg-turbo);$(opt zstd);$(opt libdeflate);$(opt liblerc);$(opt geos)"

echo "Configuring slim GDAL …" >&2
cmake -S "gdal-$GDAL_VERSION" -B build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_INSTALL_NAME_DIR="$PREFIX/lib" \
  -DCMAKE_OSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-14.0}" \
  -DCMAKE_PREFIX_PATH="$PREFIX_PATH" \
  -DCMAKE_FIND_FRAMEWORK=LAST \
  -DBUILD_TESTING=OFF \
  -DBUILD_PYTHON_BINDINGS=OFF \
  -DBUILD_JAVA_BINDINGS=OFF \
  -DBUILD_CSHARP_BINDINGS=OFF \
  -DBUILD_APPS=OFF \
  -DGDAL_USE_EXTERNAL_LIBS=OFF \
  -DGDAL_BUILD_OPTIONAL_DRIVERS=ON \
  -DOGR_BUILD_OPTIONAL_DRIVERS=ON \
  -DGDAL_USE_TIFF=ON -DGDAL_USE_GEOTIFF=ON \
  -DGDAL_USE_CURL=ON -DCURL_INCLUDE_DIR="$(xcrun --show-sdk-path)/usr/include" \
  -DCURL_LIBRARY="$(xcrun --show-sdk-path)/usr/lib/libcurl.tbd" \
  -DGDAL_USE_SQLITE3=ON \
  -DGDAL_USE_ZLIB=ON -DGDAL_USE_ZSTD=ON -DGDAL_USE_DEFLATE=ON \
  -DGDAL_USE_LERC=ON -DGDAL_USE_PNG=ON -DGDAL_USE_JPEG=ON \
  -DGDAL_USE_GEOS=ON -DGDAL_USE_ICONV=ON \
  -DGDAL_USE_JSONC_INTERNAL=ON \
  >"$WORK/configure.log" 2>&1 || { tail -40 "$WORK/configure.log" >&2; exit 1; }

echo "Building slim GDAL (log: $WORK/build.log) …" >&2
cmake --build build >"$WORK/build.log" 2>&1 || { tail -40 "$WORK/build.log" >&2; exit 1; }
cmake --install build >"$WORK/install.log" 2>&1 || { tail -40 "$WORK/install.log" >&2; exit 1; }
if [[ ! -x "$PREFIX/bin/gdal-config" ]]; then
  echo "ERROR: the slim GDAL install has no bin/gdal-config." >&2
  exit 1
fi
rm -rf build "gdal-$GDAL_VERSION" "$TARBALL"
touch "$PREFIX/.complete"
echo "Slim GDAL $GDAL_VERSION: $(otool -L "$PREFIX/lib/libgdal.dylib" | awk 'NR>2' | wc -l | tr -d ' ') linked libraries" >&2
echo "$PREFIX"
