#!/bin/zsh
# Shared version helpers for the build scripts — sourced, never executed.
#
# Each product carries a tracked MAJOR.MINOR.BUILD version whose BUILD
# component the build script increments once per build, so every binary we
# hand out traces back to the commit that produced it:
#
#   engine  Ortho4XP/src/O4_Version.py           version='1.50.<build>'
#           bumped by scripts/make_engine.sh, stamped into
#           Ortho4XP/dist/Ortho4XP/VERSION.txt (frozen engines have no
#           src/ on disk, so that file is how they report themselves).
#   app     Sources/XPTerrainBuilder/Resources/VERSION   1.0.<build>
#           bumped by scripts/make_app.sh; SwiftPM copies it into the app's
#           resource bundle and the script stamps the same string into
#           Info.plist (CFBundleShortVersionString).
#
# One line of tracked churn per build is intended. Nothing else may move
# these numbers — they exist to identify builds, not moments in time.

# xptb_version_read <file>
#   Print the bare MAJOR.MINOR.BUILD held in <file>. Accepts both shapes
#   above.
xptb_version_read() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    echo "ERROR: version file not found: $file" >&2
    return 1
  fi
  # An assignment line wins, and it is matched exactly the way the freeze
  # script's own extraction matches it — those two can then never disagree
  # about what a build is called, whatever comments the file grows. Files
  # without one (the app's bare VERSION) fall back to the first triple.
  local line
  line="$(grep -m1 '^version' "$file" 2>/dev/null || true)"
  [[ -n "$line" ]] || line="$(cat "$file")"
  local found
  found="$(grep -o -E -m1 '[0-9]+\.[0-9]+\.[0-9]+' <<< "$line" || true)"
  if [[ -z "$found" ]]; then
    echo "ERROR: no MAJOR.MINOR.BUILD version found in $file" >&2
    return 1
  fi
  echo "$found"
}

# xptb_version_bump <file>
#   Increment BUILD by one, rewrite <file> keeping its surrounding text
#   (python assignment or bare line) and print the new version.
#
#   The rewrite goes to a hidden sibling temp file and is moved into place,
#   so the destination is either the old version or the new one — an
#   interrupted or failed build never leaves a truncated version file, and
#   never leaves the tree without a version at all.
xptb_version_bump() {
  local file="$1"
  local current
  current="$(xptb_version_read "$file")" || return 1

  local stem="${current%.*}"
  local build="${current##*.}"
  local next="$stem.$(( build + 1 ))"

  local dir="${file:h}" base="${file:t}"
  local tmp
  tmp="$(mktemp "$dir/.$base.XXXXXX")" || return 1

  # Dots are regex wildcards; match the version literally so a stray
  # "1x50x3" elsewhere in the file can never be the thing we rewrite.
  local pattern="${current//./\\.}"
  if ! sed "s/$pattern/$next/" "$file" > "$tmp"; then
    rm -f "$tmp"
    echo "ERROR: could not rewrite $file" >&2
    return 1
  fi
  # Read the rewrite back before it goes live: whatever we hand the caller
  # has to be what the next reader of this file will see.
  if [[ "$(xptb_version_read "$tmp" 2>/dev/null)" != "$next" ]]; then
    rm -f "$tmp"
    echo "ERROR: version rewrite of $file did not take — bad shape?" >&2
    return 1
  fi

  chmod "$(stat -f '%Lp' "$file" 2>/dev/null || echo 644)" "$tmp"
  if ! mv "$tmp" "$file"; then
    rm -f "$tmp"
    return 1
  fi
  echo "$next"
}
