#!/usr/bin/env bash
# Sign XPTerrainBuilder.app for Developer ID distribution — INNER-FIRST.
#
#   scripts/sign_app.sh APP [IDENTITY] [ENTITLEMENTS]
#
# Why inner-first and never `codesign --deep`: the app embeds a PyInstaller
# onedir freeze of the engine (Contents/Resources/Engine) carrying ~500
# Mach-O objects — CPython extension modules (.so), dylibs, the
# Python.framework, and the Utils/mac helper executables (DSFTool,
# Triangle4XP, osmium, 7zz, nvcompress, DDSTool, triangle).  Apple's own
# guidance: `--deep` is a repair tool, not a signing strategy — it applies
# the OUTER identifier and entitlements to nested code and silently misses
# anything it does not recognise as a bundle.  Notarization rejects the
# result.  So every Mach-O is discovered with `find` + `file` (never a hand
# list, which goes stale the moment a dependency is added), signed deepest
# path first with the hardened runtime, a secure timestamp and ONE
# entitlements plist, then the engine executable, then the app.
#
# The repo lives in iCloud-synced Documents, where xattrs appear mid-build
# and codesign refuses the bundle as "resource fork, Finder information, or
# similar detritus not allowed" — hence the `xattr -cr` first.
#
# Closing checks are INSIDE this script (rc != 0 on any failure):
#   * codesign --verify --deep --strict --verbose=2 on the app
#   * every Mach-O reports the expected TeamIdentifier and the `runtime`
#     CodeDirectory flag; the counted "N signed / N found" must match.
# `spctl -a -t exec -vv` is NOT a closing check here: before notarization it
# legitimately says "Unnotarized Developer ID".  scripts/notarize_app.sh
# owns that one.
#
# bash, not zsh: this also runs on the GitHub macOS runner.
set -euo pipefail

APP="${1:?usage: sign_app.sh APP [IDENTITY] [ENTITLEMENTS]}"
APP="${APP%/}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IDENTITY="${2:-${XPTB_SIGN_IDENTITY:-}}"
ENTITLEMENTS="${3:-$HERE/XPTerrainBuilder.entitlements}"

if [[ ! -d "$APP" ]]; then
  echo "ERROR: no app bundle at $APP" >&2
  exit 1
fi
if [[ -z "$IDENTITY" ]]; then
  # One Developer ID Application identity in the keychain is the normal
  # case; more than one is ambiguous and must be named explicitly.
  # bash 3.2 on the runner and on stock macOS: no mapfile.
  FOUND="$(security find-identity -v -p codesigning 2>/dev/null \
    | sed -n 's/.*"\(Developer ID Application:[^"]*\)".*/\1/p')"
  NFOUND=$(printf '%s' "$FOUND" | grep -c . || true)
  if [[ "$NFOUND" -eq 1 ]]; then
    IDENTITY="$FOUND"
  else
    echo "ERROR: pass the signing identity (or set XPTB_SIGN_IDENTITY);" >&2
    echo "       $NFOUND 'Developer ID Application' identities in the keychain." >&2
    exit 1
  fi
fi
if [[ ! -f "$ENTITLEMENTS" ]]; then
  echo "ERROR: no entitlements plist at $ENTITLEMENTS" >&2
  exit 1
fi

# "Developer ID Application: Name (TEAMID)" -> TEAMID.  Every signature in
# the bundle must carry it; a stale ad-hoc leftover would otherwise sail
# through a bundle-level verify and be caught only by the notary service.
EXPECT_TEAM="$(sed -n 's/.*(\([A-Z0-9]\{10\}\))$/\1/p' <<<"$IDENTITY")"
if [[ -z "$EXPECT_TEAM" ]]; then
  echo "ERROR: cannot read a Team ID out of the identity string." >&2
  exit 1
fi

echo "Signing $APP"
echo "  identity      : ${IDENTITY%% (*} (team $EXPECT_TEAM)"
echo "  entitlements  : $ENTITLEMENTS"

xattr -cr "$APP" 2>/dev/null || true

sign_one() {  # sign_one PATH
  codesign --force --sign "$IDENTITY" \
    --options runtime --timestamp \
    --entitlements "$ENTITLEMENTS" \
    "$1"
}

# ------------------------------------------------- archives with native code
# Apple's notary UNPACKS archives and rejects any unsigned Mach-O inside one;
# codesign cannot reach into a zip.  Measured 2026-09-17: a vendored
# numpy-*.whl under Utils/mac cost a full CI round and a notary submission
# (status Invalid, 23 objects).  Refuse the class here, in seconds, by name.
ARCHIVE_HITS=0
while IFS= read -r -d '' ar; do
  # Listing captured FIRST: under pipefail `unzip | grep -q` reads as a
  # failure (grep exits at the first match, unzip dies of SIGPIPE, rc 141)
  # and the guard silently MISSES — measured on the very wheel it exists for.
  listing="$(unzip -Z1 "$ar" 2>/dev/null || true)"
  if grep -qE '\.(so|dylib|bundle)$' <<<"$listing"; then
    echo "REFUSED: archive carries native code the notary will reject: ${ar#"$APP"/}" >&2
    ARCHIVE_HITS=$((ARCHIVE_HITS + 1))
  fi
done < <(find "$APP" -type f \( -name '*.whl' -o -name '*.zip' -o -name '*.egg' -o -name '*.jar' \) -print0)
if [ "$ARCHIVE_HITS" -gt 0 ]; then
  echo "REFUSED: $ARCHIVE_HITS archive(s) with unsigned native code; drop them from the bundle (Ortho4XP.spec) — they cannot be signed in place." >&2
  exit 1
fi

# ---------------------------------------------------------------- discovery
# Regular files only (a symlink is signed through its target), Mach-O by
# content, never by name: PyInstaller ships extensionless executables and
# `.so`/`.dylib` alike, and the helper binaries under Utils/mac have no
# extension at all.
MACHO_LIST="$(mktemp)"
FRAMEWORK_LIST="$(mktemp)"
trap 'rm -f "$MACHO_LIST" "$FRAMEWORK_LIST"' EXIT

# NOTE the ': *' — BSD `file` PADS the name field to a column when it is
# given many paths at once, so an exact ': application/…' match finds four
# objects out of ~500 and the bundle ships mostly unsigned.  Measured here
# on 2026-09-17 (first run: "7 signed / 4 found").
find "$APP" -type f -print0 \
  | xargs -0 -n 200 file --mime-type 2>/dev/null \
  | sed -n 's/^\(.*\): *application\/x-mach-binary$/\1/p' \
  > "$MACHO_LIST"

# Versioned frameworks are signed as BUNDLES (their version directory), not
# as a loose binary: a framework signed file-wise fails --strict verification.
find "$APP" -type d -name '*.framework' -print > "$FRAMEWORK_LIST"

TOTAL_FOUND=$(wc -l < "$MACHO_LIST" | tr -d ' ')
echo "  Mach-O objects: $TOTAL_FOUND"

# Deepest path first (most '/' first), so nested code is sealed before the
# container that seals it.  Framework interiors are handled by the framework
# pass below, and the app executable + engine entry point are signed last,
# in that order, by the explicit steps after the loop.
APP_EXE="$APP/Contents/MacOS/$(/usr/libexec/PlistBuddy -c 'Print :CFBundleExecutable' "$APP/Contents/Info.plist" 2>/dev/null || echo XPTerrainBuilder)"
ENGINE_EXE="$APP/Contents/Resources/Engine/Ortho4XP"

# SIGNED counts DISCOVERED Mach-O objects that this run covered — directly
# in the loop, or through the framework bundle that contains them.  It must
# end equal to TOTAL_FOUND; the app bundle itself is counted separately, so
# the two numbers are comparable.
SIGNED=0
n=0
while IFS= read -r f; do
  n=$((n + 1))
  case "$f" in
    *.framework/*) continue ;;                 # covered by the framework pass
    "$APP_EXE"|"$ENGINE_EXE") continue ;;      # signed last, in that order
  esac
  sign_one "$f"
  SIGNED=$((SIGNED + 1))
  if (( SIGNED % 100 == 0 )); then
    echo "    … $SIGNED signed (scanned $n/$TOTAL_FOUND)"
  fi
done < <(awk '{ d = gsub("/", "/"); print d "\t" $0 }' "$MACHO_LIST" \
           | sort -rn -k1,1 | cut -f2-)

while IFS= read -r fw; do
  [[ -n "$fw" ]] || continue
  if [[ -d "$fw/Versions" ]]; then
    while IFS= read -r v; do
      [[ "$(basename "$v")" == "Current" ]] && continue
      sign_one "$v"
      echo "    framework $(basename "$fw") ($(basename "$v"))"
    done < <(find "$fw/Versions" -maxdepth 1 -mindepth 1 -type d)
  else
    sign_one "$fw"
    echo "    framework $(basename "$fw")"
  fi
  inside=$(grep -c "^$fw/" "$MACHO_LIST" || true)
  SIGNED=$((SIGNED + inside))
done < "$FRAMEWORK_LIST"

if [[ -f "$ENGINE_EXE" ]]; then
  sign_one "$ENGINE_EXE"
  SIGNED=$((SIGNED + 1))
  echo "    engine entry point Engine/Ortho4XP"
fi

# The app's own executable is sealed by signing the bundle.
sign_one "$APP"
if grep -qx "$APP_EXE" "$MACHO_LIST"; then SIGNED=$((SIGNED + 1)); fi
echo "    app bundle $(basename "$APP")"
echo "  $SIGNED signed / $TOTAL_FOUND found"
if [[ "$SIGNED" -ne "$TOTAL_FOUND" ]]; then
  echo "REFUSED: $((TOTAL_FOUND - SIGNED)) discovered Mach-O object(s) were not covered." >&2
  exit 1
fi

# ------------------------------------------------------------------ checks
echo "Verifying …"
codesign --verify --deep --strict --verbose=2 "$APP"

# Per-object audit.  A bundle-level verify passes while an interior object
# still carries an ad-hoc signature or lacks the runtime flag — the notary
# service is otherwise the first thing to notice.
BAD=0
CHECKED=0
while IFS= read -r f; do
  info="$(codesign --display --verbose=4 "$f" 2>&1 || true)"
  team="$(sed -n 's/^TeamIdentifier=//p' <<<"$info")"
  flags="$(sed -n 's/^CodeDirectory .*flags=\([^ ]*\).*/\1/p' <<<"$info" | head -1)"
  if [[ "$team" != "$EXPECT_TEAM" ]]; then
    echo "  BAD team ($team): $f" >&2
    BAD=$((BAD + 1))
  elif [[ "$flags" != *runtime* ]]; then
    echo "  BAD flags ($flags): $f" >&2
    BAD=$((BAD + 1))
  fi
  CHECKED=$((CHECKED + 1))
  if (( CHECKED % 100 == 0 )); then
    echo "    … audited $CHECKED/$TOTAL_FOUND"
  fi
done < "$MACHO_LIST"

app_info="$(codesign --display --verbose=4 "$APP" 2>&1 || true)"
app_team="$(sed -n 's/^TeamIdentifier=//p' <<<"$app_info")"
app_flags="$(sed -n 's/^CodeDirectory .*flags=\([^ ]*\).*/\1/p' <<<"$app_info" | head -1)"
[[ "$app_team" == "$EXPECT_TEAM" ]] || { echo "  BAD team on the app: $app_team" >&2; BAD=$((BAD + 1)); }
[[ "$app_flags" == *runtime* ]] || { echo "  BAD flags on the app: $app_flags" >&2; BAD=$((BAD + 1)); }

if (( BAD > 0 )); then
  echo "REFUSED: $BAD object(s) are not hardened team-$EXPECT_TEAM signatures." >&2
  exit 1
fi

echo "  audited $CHECKED Mach-O objects + the app: TeamIdentifier=$EXPECT_TEAM, flags include runtime"
echo "OK: $APP is hardened-runtime signed inner-first ($SIGNED signed / $TOTAL_FOUND found)."
echo "Next: scripts/notarize_app.sh \"$APP\"  (until then spctl says 'Unnotarized Developer ID')."
