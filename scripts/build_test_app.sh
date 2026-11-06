#!/bin/zsh
# Build an owner test app the ONE checked way (owner 2026-11-06T15:01Z).
# 1.0.471 shipped a stale, unsigned engine and missed a lane branch; each
# step below is one of those misses, now a refusal.
#
#   scripts/build_test_app.sh TEST_REF [SKIP_BRANCH ...]
#
# Run in the MAIN checkout with the app quit. SKIP_BRANCH names an
# origin/claude/* branch deliberately left out (e.g. claude/r2-kiah).
set -u
REF="${1:?usage: build_test_app.sh TEST_REF [SKIP_BRANCH ...]}"; shift
SKIP=("$@")
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT" || exit 2
IDENTITY="${XPTB_SIGN_IDENTITY:-Developer ID Application: Noah Phillip Lieberman (5MVM7P5WDJ)}"
TEAM="5MVM7P5WDJ"
die() { echo "REFUSING: $*" >&2; exit 2; }

[ -z "$(git status --porcelain --untracked-files=no)" ] || die "main checkout has tracked changes"
git fetch -q origin || die "git fetch failed"
SHA=$(git rev-parse "$REF") || die "unknown ref $REF"

# 1. No finished lane work left out: every open PR and every claude/* branch
#    pushed in the last 3 days is in the test ref, or named in SKIP.
missing=""
since=$(date -u -v-3d +%s)
for b in $(git for-each-ref --format='%(refname:short) %(committerdate:unix)' refs/remotes/origin/claude/ \
           | awk -v s="$since" '$2 >= s {print $1}'); do
  short=${b#origin/}
  (( ${SKIP[(Ie)$short]} )) && continue
  n=$(git rev-list --count "$SHA..$b")
  [ "$n" = 0 ] || missing="$missing\n  $short ($n commits)"
done
[ -z "$missing" ] || die "branches with commits not in $REF:$missing\n  merge them, or name them as SKIP_BRANCH with the reason in the handoff"

# 2. Engine first, from the test ref; then the signed app.
PREV=$(cat Sources/XPTerrainBuilder/Resources/VERSION)
restore() { git checkout -q -- Sources/XPTerrainBuilder/Resources/VERSION Ortho4XP/src/O4_Version.py 2>/dev/null; git checkout -q main; }
trap restore EXIT
git checkout -q --detach "$SHA" || die "checkout $SHA failed"
echo "$PREV" > Sources/XPTerrainBuilder/Resources/VERSION
rm -rf Ortho4XP/dist Ortho4XP/build
./scripts/make_engine.sh || die "make_engine failed"
XPTB_SIGN_IDENTITY="$IDENTITY" ./scripts/make_app.sh release || die "make_app failed"

# 3. Verify what the owner will run.
APP=dist.nosync/XPTerrainBuilder.app
codesign -dv "$APP" 2>&1 | grep -q "TeamIdentifier=$TEAM" || die "app is not signed with team $TEAM"
stamp=$(grep -m1 '^commit' "$APP/Contents/Resources/Engine/_internal/ENGINE_STAMP.txt" 2>/dev/null | awk '{print $2}')
[ -n "$stamp" ] && [ "${stamp#$SHA}" != "$stamp" -o "${SHA#$stamp}" != "$SHA" ] \
  || echo "WARNING: could not read the engine stamp; check make_app's 'embedded engine commit' line"
echo "TEST APP OK: $(cat "$APP/Contents/Resources/VERSION" 2>/dev/null) at $SHA, team $TEAM"
