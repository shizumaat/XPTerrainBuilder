#!/bin/zsh
# Build XPSceneryDoctor.app from the SwiftPM executable.
# Usage: scripts/make_app.sh [debug|release]   (default: release)
set -euo pipefail

CONFIG="${1:-release}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/XPSceneryDoctor.app"

cd "$ROOT"
swift build --build-system native -c "$CONFIG"
BIN="$(swift build --build-system native -c "$CONFIG" --show-bin-path)/XPSceneryDoctor"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/XPSceneryDoctor"

# App icon: use the committed .icns, regenerating it if missing.
if [[ ! -f "$ROOT/Resources/AppIcon.icns" ]]; then
  TMP_ICON="$(mktemp -d)"
  swift "$ROOT/scripts/make_icon.swift" "$TMP_ICON"
  mkdir -p "$ROOT/Resources"
  iconutil -c icns "$TMP_ICON/AppIcon.iconset" -o "$ROOT/Resources/AppIcon.icns"
  rm -rf "$TMP_ICON"
fi
cp "$ROOT/Resources/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>XPSceneryDoctor</string>
    <key>CFBundleIdentifier</key>
    <string>com.novemberlima.XPSceneryDoctor</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleName</key>
    <string>XPScenery Doctor</string>
    <key>CFBundleDisplayName</key>
    <string>XPScenery Doctor</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
PLIST

codesign --force --sign - "$APP"
echo "Built $APP"
