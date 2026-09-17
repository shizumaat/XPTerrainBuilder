#!/usr/bin/env bash
# THE TAG SCHEME GATE — one implementation, every release job
# (docs/BETA-PLAN-20260916.md §1 B3).
#
# A release tag names a build that exists: `v1.0.<app-build>[-beta.N]`, whose
# numeric part is EXACTLY the app version tracked in
# Sources/XPTerrainBuilder/Resources/VERSION at the tagged commit.  Nothing
# else may move that number (scripts/version.sh) — so a tag disagreeing with
# it means the tag was typed from memory, and the artifacts would carry a
# version the release page does not.  That fails HERE, in the first step of
# every job, before an hour of freezing and notarizing.
#
# workflow_dispatch is unaffected: a non-tag ref passes with a note.
#
# Usage: scripts/check_tag_version.sh [ref] [version-file]
#   [ref]           refs/tags/v1.0.347-beta.1, or the bare tag, or any
#                   non-tag ref.  Default: $GITHUB_REF.
#   [version-file]  default: Sources/XPTerrainBuilder/Resources/VERSION
#                   relative to the repo root.
#
# bash, not zsh: this runs on the Windows and Linux release runners too.
set -euo pipefail

REF="${1:-${GITHUB_REF:-}}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION_FILE="${2:-$HERE/Sources/XPTerrainBuilder/Resources/VERSION}"

case "$REF" in
  refs/tags/v*) TAG="${REF#refs/tags/}" ;;
  v[0-9]*)      TAG="$REF" ;;
  *)
    echo "not a v* tag ref (${REF:-<empty>}) — tag/version check skipped"
    exit 0
    ;;
esac

if [[ ! -f "$VERSION_FILE" ]]; then
  echo "ERROR: version file not found: $VERSION_FILE" >&2
  exit 1
fi

# The tracked file is a bare MAJOR.MINOR.BUILD line; read it the way
# scripts/version.sh does, so the two can never disagree about a build.
TREE_VERSION="$(grep -o -E -m1 '[0-9]+\.[0-9]+\.[0-9]+' "$VERSION_FILE" || true)"
if [[ -z "$TREE_VERSION" ]]; then
  echo "ERROR: no MAJOR.MINOR.BUILD version found in $VERSION_FILE" >&2
  exit 1
fi

# v1.0.347 and v1.0.347-beta.2 are the only shapes; anything else is a typo
# we refuse rather than guess at.
TAG_BODY="${TAG#v}"
TAG_VERSION="${TAG_BODY%%-*}"
TAG_SUFFIX=""
if [[ "$TAG_BODY" == *-* ]]; then TAG_SUFFIX="${TAG_BODY#*-}"; fi

if ! [[ "$TAG_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
   || { [[ -n "$TAG_SUFFIX" ]] && ! [[ "$TAG_SUFFIX" =~ ^beta\.[0-9]+$ ]]; }; then
  echo "ERROR: tag $TAG does not follow the scheme v<MAJOR>.<MINOR>.<BUILD>[-beta.<N>]" >&2
  echo "  tag:  $TAG" >&2
  echo "  tree: $TREE_VERSION  ($VERSION_FILE)" >&2
  exit 1
fi

if [[ "$TAG_VERSION" != "$TREE_VERSION" ]]; then
  echo "ERROR: tag version does not match the app version at this commit" >&2
  echo "  tag:  $TAG_VERSION   (from $TAG)" >&2
  echo "  tree: $TREE_VERSION  ($VERSION_FILE)" >&2
  echo "Tag the commit whose VERSION is $TAG_VERSION, or re-tag as v$TREE_VERSION." >&2
  exit 1
fi

echo "tag $TAG matches the tree app version $TREE_VERSION"
