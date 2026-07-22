#!/bin/zsh
# Build XPTerrainBuilder.app from the SwiftPM executable.
# Usage: scripts/make_app.sh [debug|release]   (default: release)
set -euo pipefail

CONFIG="${1:-release}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# .nosync: iCloud Drive skips such folders. The repo may live under the
# synced Documents folder, and letting the file provider chew on a half-
# gigabyte app bundle mid-assembly causes conflict duplicates and stalls.
APP="$ROOT/dist.nosync/XPTerrainBuilder.app"

# Assemble and sign in a private temp dir: the repo may live in a synced
# folder (iCloud Documents), where the file provider re-stamps FinderInfo
# xattrs mid-build and codesign then rejects the bundle as "detritus".
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT
STAGE="$STAGE_DIR/XPTerrainBuilder.app"

cd "$ROOT"
swift build --build-system native -c "$CONFIG"
BIN="$(swift build --build-system native -c "$CONFIG" --show-bin-path)/XPTerrainBuilder"

mkdir -p "$STAGE/Contents/MacOS" "$STAGE/Contents/Resources"
cp "$BIN" "$STAGE/Contents/MacOS/XPTerrainBuilder"

# SwiftPM resource bundle (map data etc.) — Bundle.module looks for it next
# to the executable's resources.
BUNDLE="$(dirname "$BIN")/XPTerrainBuilder_XPTerrainBuilder.bundle"
if [[ -d "$BUNDLE" ]]; then
  cp -R "$BUNDLE" "$STAGE/Contents/Resources/"
fi

# Bundled Ortho4XP engine — the app's default build engine. Read-only inside
# the bundle: all writable data (downloads, tiles, config) goes to the user's
# data folder via ORTHO4XP_DATA_ROOT.
#
# Preferred flavor: the FROZEN engine (scripts/make_engine.sh) — bundled
# Python runtime and packages, nothing for the user to install. Falls back
# to embedding the engine source tree (dev builds), which needs a system
# python3 with the engine's packages.
FROZEN="$ROOT/Ortho4XP/dist/Ortho4XP"
if [[ -x "$FROZEN/Ortho4XP" ]]; then
  echo "Embedding frozen engine (self-contained)"
  rsync -a --exclude '* [2-9].*' "$FROZEN/" "$STAGE/Contents/Resources/Engine/"
else
  echo "NOTE: frozen engine not found ($FROZEN)."
  echo "      Embedding the engine source tree instead — users would need"
  echo "      python3 + packages. Run scripts/make_engine.sh for releases."
  rsync -a --exclude '* [2-9].*' \
    --exclude 'venv/' --exclude '.venv*/' --exclude '__pycache__/' \
    --exclude '.git*' --exclude 'build/' --exclude 'dist/' \
    --exclude 'tests/' --exclude 'docs/' --exclude 'prototypes/' \
    --exclude 'tools/' --exclude 'Previews/' --exclude '.pytest_cache/' \
    --exclude 'Ortho4XP.cfg' --exclude 'Ortho4XP.cfg.bak' \
    --exclude 'Tiles/' --exclude 'tmp/' --exclude 'OSM_data/' \
    --exclude 'Orthophotos/' --exclude 'Elevation_data/' --exclude 'Masks/' \
    --exclude 'Geotiffs/' --exclude '.DS_Store' \
    "$ROOT/Ortho4XP/" "$STAGE/Contents/Resources/Engine/"
fi

# App icon: Liquid Glass pipeline. The white Mjolnir glyph (icon_glass.swift)
# feeds the Icon Composer document at Resources/AppIcon.icon; actool
# compiles it into Assets.car (macOS 26+ applies the real glass material,
# including dark/tinted variants) plus a baked fallback AppIcon.icns for
# older systems.
ICON_DOC="$ROOT/Resources/AppIcon.icon"
if [[ ! -f "$ROOT/Resources/AppIcon.icns" \
      || ! -f "$ROOT/Resources/Assets.car" \
      || "$ROOT/scripts/icon_glass.swift" -nt "$ROOT/Resources/AppIcon.icns" \
      || "$ICON_DOC/icon.json" -nt "$ROOT/Resources/AppIcon.icns" ]]; then
  TMP_ICON="$(mktemp -d)"
  swift "$ROOT/scripts/icon_glass.swift" "$TMP_ICON"
  cp "$TMP_ICON/glyph-1024.png" "$ICON_DOC/Assets/glyph-1024.png"
  mkdir -p "$TMP_ICON/out"
  xcrun actool "$ICON_DOC" --compile "$TMP_ICON/out" --platform macosx \
    --minimum-deployment-target 26.0 --app-icon AppIcon \
    --output-partial-info-plist "$TMP_ICON/out/partial.plist" >/dev/null
  cp "$TMP_ICON/out/Assets.car" "$ROOT/Resources/Assets.car"
  cp "$TMP_ICON/out/AppIcon.icns" "$ROOT/Resources/AppIcon.icns"
  rm -rf "$TMP_ICON"
fi
cp "$ROOT/Resources/AppIcon.icns" "$STAGE/Contents/Resources/AppIcon.icns"
cp "$ROOT/Resources/Assets.car" "$STAGE/Contents/Resources/Assets.car"

cat > "$STAGE/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>XPTerrainBuilder</string>
    <key>CFBundleIdentifier</key>
    <string>com.novemberlima.XPTerrainBuilder</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIconName</key>
    <string>AppIcon</string>
    <key>CFBundleName</key>
    <string>XPTerrainBuilder</string>
    <key>CFBundleDisplayName</key>
    <string>XPTerrainBuilder</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>NSAppTransportSecurity</key>
    <dict>
        <!-- Many Ortho4XP imagery providers serve over plain http (Bing,
             national orthophoto services); ATS would silently block them
             in the map preview and future in-app fetches. -->
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>
</dict>
</plist>
PLIST

# Strip any metadata the sources carried over, then sign in the temp dir
# where nothing races us.
xattr -cr "$STAGE" 2>/dev/null || true
codesign --force --sign - "$STAGE"

rm -rf "$APP"
mkdir -p "$ROOT/dist.nosync"
ditto "$STAGE" "$APP"
echo "Built $APP"
