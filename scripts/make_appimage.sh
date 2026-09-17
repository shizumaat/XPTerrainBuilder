#!/usr/bin/env bash
# THE LINUX APPIMAGE (RELEASES-PLAN §D2).
#
# A single double-clickable file, built from the SAME staged tree the
# tar.gz is made from, so the license payload and VERSION.txt of
# RELEASES-PLAN §G are carried by both artifacts by construction rather
# than by two lists that can drift.
#
# Usage:
#   scripts/make_appimage.sh <staged-dir> <out.AppImage> <icon-png> [appimagetool]
#
#   <staged-dir>    the branded frozen onedir (contains the executable
#                   XPTerrainBuilder plus LICENSE, LICENSING.md,
#                   THIRD-PARTY-NOTICES.txt, gpl.txt, copyright.txt,
#                   VERSION.txt)
#   <out.AppImage>  the file to write
#   <icon-png>      the 256px icon (scripts/make_icon.py output)
#   [appimagetool]  the appimagetool AppImage; default $APPIMAGETOOL.  The
#                   caller downloads it by exact URL and verifies its
#                   sha256 (.github/workflows/release.yml) — this script
#                   never downloads anything.
#
# THE TYPE-2 RUNTIME IS VENDORED (owner decision 2026-09-17).
# appimagetool is pinned, but by DEFAULT it downloads the type-2 runtime
# at build time from upstream's mutable `continuous` tag — and those bytes
# are the first code a Linux tester executes.  We ship one verified copy,
# scripts/appimage/runtime-x86_64 (provenance: scripts/appimage/README.md),
# pass it with --runtime-file, and refuse to build if its sha256 is not the
# one pinned below.  Three checks, each of which alone would be enough to
# notice a substitution, and which together also catch a silent fallback:
#
#   (1) the vendored file's sha256, verified BEFORE the build;
#   (2) appimagetool's own log, which must contain no download;
#   (3) THE SHIPPED ARTIFACT: the AppImage's runtime region (everything
#       before the squashfs offset) is compared byte for byte against the
#       vendored file.  The only region appimagetool is permitted to
#       differ in is the 16-byte `.digest_md5` ELF section it fills with
#       the AppImage's md5; a difference anywhere else fails the build and
#       the offsets are printed.  (The `AI\x02` type magic at offset 8 is
#       already in the vendored asset — upstream's build-runtime.sh writes
#       it with dd after strip — so appimagetool rewriting it is a no-op.)
#
# AppDir layout (the AppImage spec's, plus what desktop environments read):
#
#   AppRun                                            -> execs the binary
#   xpterrainbuilder.desktop                          (root copy: required)
#   xpterrainbuilder.png                              (root copy: required)
#   usr/share/applications/xpterrainbuilder.desktop
#   usr/share/icons/hicolor/256x256/apps/xpterrainbuilder.png
#   usr/bin/<the whole staged tree>
#   LICENSE, LICENSING.md, THIRD-PARTY-NOTICES.txt, gpl.txt,
#   copyright.txt, VERSION.txt                        (§G, at the root)
#
# PyInstaller onedir, never onefile (LGPL v3 / RELEASES-PLAN §G): the Qt
# libraries stay separate relinkable files inside the AppImage's squashfs.
#
# appimagetool runs with --appimage-extract-and-run: the ubuntu-22.04
# runner has no usable FUSE, and without it appimagetool cannot even
# mount itself.
#
# bash, not zsh: this runs on the Linux release runner.
set -euo pipefail

STAGED="${1:?usage: make_appimage.sh <staged-dir> <out.AppImage> <icon-png> [appimagetool]}"
OUT="${2:?usage: make_appimage.sh <staged-dir> <out.AppImage> <icon-png> [appimagetool]}"
ICON="${3:?usage: make_appimage.sh <staged-dir> <out.AppImage> <icon-png> [appimagetool]}"
TOOL="${4:-${APPIMAGETOOL:-}}"

APP_NAME=XPTerrainBuilder
ICON_NAME=xpterrainbuilder

# Resolved from THIS SCRIPT's location, never the caller's cwd: the
# release job runs us from the repository root today, and a cwd-relative
# runtime path would turn a moved cwd into a silent network fallback.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="$SCRIPT_DIR/appimage/runtime-x86_64"
# THE PIN.  scripts/appimage/README.md records the same value with the
# provenance; this line is the enforcement.  Changing the vendored file
# without changing this line fails the build.
RUNTIME_SHA256=1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf
RUNTIME_SIZE=944632
# The `.digest_md5` section of that ELF (measured from its section
# headers): the ONE region appimagetool writes into a runtime it did not
# download.  Offsets are 0-based file offsets into runtime-x86_64.
DIGEST_MD5_OFF=932096
DIGEST_MD5_LEN=16

# sha256sum on the Linux runner; shasum -a 256 so the script still runs on
# a mac for local checks.
sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | cut -d' ' -f1
  else
    echo "ERROR: neither sha256sum nor shasum is available — cannot verify" \
         "the vendored AppImage runtime, refusing to build." >&2
    exit 1
  fi
}

[ -d "$STAGED" ] || { echo "ERROR: no staged dir at $STAGED" >&2; exit 1; }
[ -x "$STAGED/$APP_NAME" ] || {
  echo "ERROR: no executable $STAGED/$APP_NAME — the brand step renames" \
       "the frozen Ortho4XP_Qt binary before this runs." >&2
  exit 1; }
[ -f "$ICON" ] || { echo "ERROR: no icon at $ICON" >&2; exit 1; }
[ -n "$TOOL" ] && [ -f "$TOOL" ] || {
  echo "ERROR: no appimagetool (\$APPIMAGETOOL or 4th argument)" >&2
  exit 1; }

# ---- (1) the vendored runtime, verified BEFORE anything is built -------
[ -f "$RUNTIME" ] || {
  echo "ERROR: the vendored AppImage runtime is missing:" >&2
  echo "       $RUNTIME" >&2
  echo "       It is committed to the repository (see" \
       "scripts/appimage/README.md)." >&2
  echo "       Refusing to build: appimagetool would silently DOWNLOAD a" \
       "runtime from upstream's mutable continuous tag instead." >&2
  exit 1; }

RUNTIME_GOT="$(sha256_of "$RUNTIME")"
if [ "$RUNTIME_GOT" != "$RUNTIME_SHA256" ]; then
  echo "ERROR: vendored AppImage runtime FAILS its sha256 pin — refusing" \
       "to build." >&2
  echo "       file:     $RUNTIME" >&2
  echo "       expected: $RUNTIME_SHA256" >&2
  echo "       got:      $RUNTIME_GOT" >&2
  echo "       This file becomes the first code a Linux tester runs." \
       "Update it deliberately (scripts/appimage/README.md, 'Updating" \
       "it'), never as a build side effect." >&2
  exit 1
fi
RUNTIME_GOT_SIZE="$(wc -c < "$RUNTIME" | tr -d ' ')"
if [ "$RUNTIME_GOT_SIZE" != "$RUNTIME_SIZE" ]; then
  echo "ERROR: vendored AppImage runtime $RUNTIME is $RUNTIME_GOT_SIZE" \
       "bytes, expected $RUNTIME_SIZE — refusing to build." >&2
  exit 1
fi
echo "vendored AppImage runtime verified: $RUNTIME"
echo "  sha256 $RUNTIME_GOT ($RUNTIME_SIZE bytes) OK"

WORK="$(cd "$(dirname "$OUT")" && pwd)"
OUT="$WORK/$(basename "$OUT")"
APPDIR="$WORK/${APP_NAME}.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -a "$STAGED/." "$APPDIR/usr/bin/"

# The license payload and the version triple at the AppDir root, where a
# user who runs `--appimage-extract` finds them (RELEASES-PLAN §G).  The
# staged tree already carries them; this is the same files, one level up.
for f in LICENSE LICENSING.md THIRD-PARTY-NOTICES.txt gpl.txt \
         copyright.txt VERSION.txt; do
  if [ -f "$STAGED/$f" ]; then
    cp "$STAGED/$f" "$APPDIR/$f"
  else
    echo "ERROR: $f missing from the staged tree — RELEASES-PLAN §G" \
         "requires it in every artifact root." >&2
    exit 1
  fi
done

# AppRun: no `cd`.  The engine resolves relative paths from the caller's
# working directory, and check_frozen_tile.py drives this very entry point
# with a temp data root — a cd here would silently change both.
cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
# Generated by scripts/make_appimage.sh — the AppImage entry point.
HERE="$(dirname "$(readlink -f "$0")")"
export ORTHO4XP_APPIMAGE=1
exec "$HERE/usr/bin/XPTerrainBuilder" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/usr/share/applications/$ICON_NAME.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=XPTerrainBuilder
GenericName=Ortho scenery builder
Comment=Build X-Plane ortho scenery from imagery and elevation data
Exec=XPTerrainBuilder
Icon=$ICON_NAME
Categories=Utility;
Terminal=false
DESKTOP
cp "$APPDIR/usr/share/applications/$ICON_NAME.desktop" \
   "$APPDIR/$ICON_NAME.desktop"

cp "$ICON" "$APPDIR/usr/share/icons/hicolor/256x256/apps/$ICON_NAME.png"
cp "$ICON" "$APPDIR/$ICON_NAME.png"

echo "AppDir assembled at $APPDIR:"
ls -l "$APPDIR"

chmod +x "$TOOL" || true
# ARCH is not always inferred from a PyInstaller tree; state it.
export ARCH="${ARCH:-x86_64}"
# --no-appstream: we ship no AppStream metainfo, and appimagetool's
# validator is not a release gate (the release gate is the tile build
# below it in the job).
# --runtime-file: the vendored runtime verified above.  Without it
# appimagetool downloads one.
TOOL_LOG="$WORK/appimagetool.log"
set +e
"$TOOL" --appimage-extract-and-run --no-appstream \
        --runtime-file "$RUNTIME" "$APPDIR" "$OUT" 2>&1 | tee "$TOOL_LOG"
TOOL_RC=${PIPESTATUS[0]}
set -e
[ "$TOOL_RC" -eq 0 ] || {
  echo "ERROR: appimagetool exited $TOOL_RC" >&2; exit "$TOOL_RC"; }

# ---- (2) appimagetool's own log must show no download ------------------
if grep -inE 'download' "$TOOL_LOG" >&2; then
  echo "ERROR: appimagetool reported a DOWNLOAD (lines above) despite" \
       "--runtime-file $RUNTIME." >&2
  echo "       A network-fetched runtime is exactly what vendoring" \
       "removes. Refusing to ship this AppImage." >&2
  exit 1
fi
echo "appimagetool log: no download (grep -i download over $TOOL_LOG)"

chmod +x "$OUT"

# ---- (3) the SHIPPED artifact carries the vendored runtime -------------
# The runtime is the AppImage's prefix: the squashfs payload starts at
# --appimage-offset.  Ask the artifact itself; fall back to the vendored
# size if the runtime cannot answer (it is an ELF exec — on a runner
# without FUSE, argument parsing still happens before any mount).
EMBED_OFFSET=""
EMBED_OFFSET_SOURCE="--appimage-offset"
if OFF_OUT="$("$OUT" --appimage-offset 2>/dev/null)"; then
  OFF_OUT="$(printf '%s' "$OFF_OUT" | tr -d '[:space:]')"
  case "$OFF_OUT" in
    ''|*[!0-9]*) EMBED_OFFSET="" ;;
    *)           EMBED_OFFSET="$OFF_OUT" ;;
  esac
fi
if [ -z "$EMBED_OFFSET" ]; then
  EMBED_OFFSET="$RUNTIME_SIZE"
  EMBED_OFFSET_SOURCE="vendored size (the AppImage could not report one)"
fi
echo "AppImage squashfs offset: $EMBED_OFFSET  [$EMBED_OFFSET_SOURCE]"
if [ "$EMBED_OFFSET" != "$RUNTIME_SIZE" ]; then
  echo "ERROR: the AppImage's payload starts at $EMBED_OFFSET but the" \
       "vendored runtime is $RUNTIME_SIZE bytes — the embedded runtime is" \
       "NOT the vendored file. Refusing to ship." >&2
  exit 1
fi

EMBEDDED="$WORK/.embedded-runtime.bin"
head -c "$EMBED_OFFSET" "$OUT" > "$EMBEDDED"
EMBEDDED_SHA="$(sha256_of "$EMBEDDED")"
if [ "$EMBEDDED_SHA" = "$RUNTIME_SHA256" ]; then
  echo "embedded runtime proof: BYTE-IDENTICAL to the vendored file"
  echo "  sha256 $EMBEDDED_SHA over all $RUNTIME_SIZE bytes;" \
       "appimagetool patched nothing"
else
  DIFF_LIST="$WORK/.embedded-runtime.diff"
  cmp -l "$RUNTIME" "$EMBEDDED" > "$DIFF_LIST" || true
  NDIFF="$(wc -l < "$DIFF_LIST" | tr -d ' ')"
  # cmp -l prints 1-based byte numbers in decimal.
  FIRST="$(awk 'NR==1 {print $1-1; exit}' "$DIFF_LIST")"
  LAST="$(awk 'END {print $1-1}' "$DIFF_LIST")"
  echo "embedded runtime proof: $NDIFF of $RUNTIME_SIZE bytes differ" \
       "(sha256 $EMBEDDED_SHA vs vendored $RUNTIME_SHA256)"
  echo "  differing byte offsets (0-based): first $FIRST, last $LAST"
  OUTSIDE="$(awk -v lo="$((DIGEST_MD5_OFF + 1))" \
                 -v hi="$((DIGEST_MD5_OFF + DIGEST_MD5_LEN))" \
                 '$1 < lo || $1 > hi' "$DIFF_LIST")"
  if [ -n "$OUTSIDE" ]; then
    echo "ERROR: the embedded runtime differs OUTSIDE the .digest_md5" \
         "section [$DIGEST_MD5_OFF, $((DIGEST_MD5_OFF + DIGEST_MD5_LEN)))." \
         >&2
    echo "       appimagetool is permitted to write that md5 and nothing" \
         "else; this is a different runtime, or a patched one." >&2
    echo "       first 40 offending bytes (offset, vendored, embedded," \
         "octal):" >&2
    printf '%s\n' "$OUTSIDE" | head -40 \
      | awk '{printf "       %d %s %s\n", $1-1, $2, $3}' >&2
    exit 1
  fi
  echo "  ALL differing bytes lie inside .digest_md5 (offset" \
       "$DIGEST_MD5_OFF, $DIGEST_MD5_LEN bytes) — the md5 appimagetool" \
       "embeds; $((RUNTIME_SIZE - NDIFF)) of $RUNTIME_SIZE bytes are" \
       "byte-identical to the vendored file"
fi
rm -f "$EMBEDDED"

ls -l "$OUT"
echo "AppImage: $OUT"
