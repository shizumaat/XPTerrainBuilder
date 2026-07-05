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

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>XPSceneryDoctor</string>
    <key>CFBundleIdentifier</key>
    <string>com.noahlieberman.XPSceneryDoctor</string>
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
