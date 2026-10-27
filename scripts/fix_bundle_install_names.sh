#!/bin/bash
# Make every @rpath reference in a frozen engine bundle name a library by
# the same leaf as that library's own install name.
#
# Under the hardened runtime dyld refuses a library whose install-name leaf
# differs from the leaf it was asked for ("security level requires its leaf
# name to match requested").  PyInstaller copies the real file
# (liblz4.1.10.0.dylib, id @rpath/liblz4.1.10.0.dylib) and links the
# requested name to it (liblz4.1.dylib), so an unsigned or ad-hoc engine
# loads it and the signed app does not: apps 1.0.429-1.0.431 shipped with
# GDAL unloadable this way.  The fix points each reference at the name the
# library carries; a library with no file under that name instead takes the
# requested name as its id.
#
# Usage: scripts/fix_bundle_install_names.sh BUNDLE_DIR   (the _internal dir)
set -euo pipefail
BUNDLE="${1:?usage: $0 BUNDLE_DIR}"
CHANGED=0

find_lib() {  # find_lib REFERRER_DIR LEAF -> path of the library dyld would use
  if [[ -e "$1/$2" ]]; then echo "$1/$2"; return; fi
  if [[ -e "$BUNDLE/$2" ]]; then echo "$BUNDLE/$2"; return; fi
  find "$BUNDLE" -name "$2" -print -quit
}

while IFS= read -r -d '' F; do
  for REF in $(otool -L "$F" 2>/dev/null | awk 'NR>1 && $1 ~ /^@rpath\// {print $1}'); do
    LEAF="${REF#@rpath/}"
    [[ "$LEAF" == */* ]] && continue
    T="$(find_lib "$(dirname "$F")" "$LEAF")"
    [[ -z "$T" ]] && continue
    ID="$(otool -D "$T" 2>/dev/null | awk 'NR==2 {print $1}')"
    IDLEAF="$(basename "$ID")"
    [[ -z "$ID" || "$IDLEAF" == "$LEAF" ]] && continue
    if [[ -e "$(dirname "$T")/$IDLEAF" ]]; then
      chmod u+w "$F"
      install_name_tool -change "$REF" "@rpath/$IDLEAF" "$F" 2>/dev/null
      codesign --force --sign - "$F" >/dev/null 2>&1
      echo "   $(basename "$F"): $LEAF -> $IDLEAF"
    else
      REAL="$(cd "$(dirname "$T")" && pwd -P)/$(basename "$(readlink "$T" || echo "$T")")"
      chmod u+w "$REAL"
      install_name_tool -id "@rpath/$LEAF" "$REAL" 2>/dev/null
      codesign --force --sign - "$REAL" >/dev/null 2>&1
      echo "   $(basename "$REAL"): id -> $LEAF"
    fi
    CHANGED=$((CHANGED + 1))
  done
done < <(find "$BUNDLE" -type f \( -name '*.dylib' -o -name '*.so' \) -print0)
echo "   install-name leaves matched ($CHANGED references fixed)"
