#!/bin/sh
# THE LANE RITUAL — create or tear down a lane worktree, correctly.
#
#   tools/harness/lane_worktree.sh up   NAME [REF]
#   tools/harness/lane_worktree.sh down NAME
#   tools/harness/lane_worktree.sh check NAME
#
# Run from anywhere.  Every lane sets its tree up with THIS script; a
# hand-typed ritual is a defect (see CLAUDE.md, "The standard test harness").
# A worktree missing any one of these pieces does not fail — it builds a
# silently different thing and exits 0.
#
# WHAT `up` DOES, AND WHY EACH PIECE IS THE SHAPE IT IS:
#
#   venv/              SYMLINK.  One interpreter and one set of installed
#                      packages for every lane; a per-lane venv is 2 GB and
#                      a chance for the trees to diverge on a dependency.
#   OSM_data/          SYMLINK.  A fresh worktree has none, and the road /
#                      corridor code paths then silently NO-OP: the build
#                      exits 0 with a smaller layout that reads as a
#                      speedup and a defect drop.
#   Airport_mod_cache/ SYMLINK.  Shared third-party apt.dat packs.
#   Elevation_data/    SYMLINK, never a copy.  A copied inset cache is a
#                      SECOND cache that warms independently, and warm-vs-
#                      cold cache state has moved measured terrain by 12 m
#                      and faked an 8 s regression in this repo.  One cache
#                      is the only way two lanes measure one surface.
#   Patches/           CLONED (cp -R), never symlinked.  Lanes WRITE here;
#                      a shared Patches dir means one lane's emitted patch
#                      lands in another lane's tile build.
#   Ortho4XP.cfg       CLONED.  It is NOT tracked, so a fresh worktree has
#                      none at all — and then `Tile.read_from_config()`
#                      finds no config, the DEM prep runs on constructor
#                      defaults, and the lane grades against a surface
#                      production never builds.  Silent: one log line.
#
# The symlinks are deliberately NOT git-added (the repo's .gitignore uses
# directory patterns, which do not match symlinks — so `git status` shows
# them as untracked and a careless `git add -A` would commit them).  `up`
# ends by REFUSING if anything but those four paths is untracked, and
# `check` re-runs that audit at any time.
#
# `down` refuses while a child process still holds the tree — tearing a
# worktree out from under a live build produces a half-written patch and a
# "not reproducible" report.
set -u

MAIN_REPO="${O4_MAIN_REPO:-/Users/noah/XPTerrainBuilder}"
MAIN_ENGINE="$MAIN_REPO/Ortho4XP"
WT_ROOT="$MAIN_REPO/.claude/worktrees"

LINK_DIRS="venv OSM_data Airport_mod_cache Elevation_data"
CLONE_DIRS="Patches"
CLONE_FILES="Ortho4XP.cfg"

die() { echo "REFUSING: $*" >&2; exit 2; }

usage() {
    echo "usage: $0 {up|down|check} NAME [REF]" >&2
    exit 64
}

[ $# -ge 2 ] || usage
ACTION="$1"
NAME="$2"
REF="${3:-HEAD}"
WT="$WT_ROOT/$NAME"
ENGINE="$WT/Ortho4XP"

# ── the untracked-path audit ─────────────────────────────────────────
# Only the four symlinks may be untracked.  Anything else is either a
# lane artifact that belongs in the scratchpad or an edit about to be
# swept into someone else's "Round N" omnibus commit.
audit_untracked() {
    _bad=$(git -C "$WT" status --porcelain 2>/dev/null \
           | sed -n 's/^?? //p' \
           | grep -v -E "^Ortho4XP/(venv|OSM_data|Airport_mod_cache|Elevation_data)/?$")
    if [ -n "$_bad" ]; then
        echo "  [ritual] UNTRACKED paths beyond the four shared symlinks:"
        echo "$_bad" | sed 's/^/    /'
        echo "  [ritual] NEVER 'git add -A' in a lane tree — the symlinks"
        echo "           would be committed (the .gitignore dir patterns do"
        echo "           not match symlinks).  Add files by explicit path."
        return 1
    fi
    echo "  [ritual] untracked audit clean (only the four shared symlinks)."
    return 0
}

case "$ACTION" in
up)
    [ -d "$MAIN_ENGINE" ] || die "no engine tree at $MAIN_ENGINE"
    for d in $LINK_DIRS; do
        [ -e "$MAIN_ENGINE/$d" ] || die "the MAIN tree has no $d — a lane
    worktree cannot be given what the main tree lacks."
    done
    if [ -d "$WT" ]; then
        echo "  [ritual] worktree $WT already exists — completing the ritual."
    else
        git -C "$MAIN_REPO" worktree add "$WT" "$REF" || die "worktree add failed"
    fi
    for d in $LINK_DIRS; do
        if [ -L "$ENGINE/$d" ]; then
            :
        elif [ -e "$ENGINE/$d" ]; then
            die "$ENGINE/$d exists and is NOT a symlink.  A real
    $d in a lane tree is a second cache / second venv — remove it and re-run."
        else
            ln -s "$MAIN_ENGINE/$d" "$ENGINE/$d" || die "could not link $d"
        fi
        echo "  [ritual] symlink $d -> $MAIN_ENGINE/$d"
    done
    for d in $CLONE_DIRS; do
        mkdir -p "$ENGINE/$d"
        [ -L "$ENGINE/$d" ] && die "$d must be a real directory, not a symlink"
        for src in "$MAIN_ENGINE/$d"/*/; do
            [ -d "$src" ] || continue
            base=$(basename "$src")
            [ -e "$ENGINE/$d/$base" ] || cp -R "$src" "$ENGINE/$d/$base"
        done
        echo "  [ritual] cloned $d ($(ls -1 "$ENGINE/$d" 2>/dev/null | wc -l | tr -d ' ') entries) — lane-private, writes stay here"
    done
    for f in $CLONE_FILES; do
        [ -e "$MAIN_ENGINE/$f" ] || die "the MAIN tree has no $f — without
    it every build in this lane would run on constructor defaults."
        [ -e "$ENGINE/$f" ] || cp "$MAIN_ENGINE/$f" "$ENGINE/$f"
        echo "  [ritual] cloned $f (untracked in git: a fresh worktree has none)"
    done
    # Prove the ritual took: the build entry's own refusal, run here.
    ( cd "$ENGINE" && [ -d venv ] && [ -d OSM_data ] ) \
        || die "post-ritual check failed: $ENGINE still lacks venv/OSM_data"
    echo "  [ritual] $ENGINE is build-ready."
    audit_untracked
    echo "  [ritual] next: cd $ENGINE && venv/bin/python tools/harness/build_airport.py ICAO"
    ;;

check)
    [ -d "$WT" ] || die "no worktree at $WT"
    rc=0
    for d in $LINK_DIRS; do
        if [ -L "$ENGINE/$d" ]; then
            echo "  [ritual] OK    $d -> $(readlink "$ENGINE/$d")"
        else
            echo "  [ritual] BROKEN $d is not a symlink"; rc=1
        fi
    done
    for d in $CLONE_DIRS; do
        if [ -L "$ENGINE/$d" ]; then
            echo "  [ritual] BROKEN $d is a SYMLINK (must be a clone)"; rc=1
        else
            echo "  [ritual] OK    $d cloned"
        fi
    done
    for f in $CLONE_FILES; do
        if [ -f "$ENGINE/$f" ]; then
            echo "  [ritual] OK    $f present"
        else
            echo "  [ritual] BROKEN $f missing — builds would run on"
            echo "                  constructor defaults, not production's"; rc=1
        fi
    done
    audit_untracked || rc=1
    exit $rc
    ;;

down)
    [ -d "$WT" ] || die "no worktree at $WT"
    # A live process holding the tree: tearing it out mid-build yields a
    # half-written patch and a "not reproducible" report next session.
    holders=$(pgrep -fl "$WT" 2>/dev/null | grep -v "lane_worktree.sh")
    if [ -n "$holders" ]; then
        echo "$holders" | sed 's/^/    /'
        die "process(es) above still hold $WT.  Wait for them (a build
    killed mid-write leaves a patch that reads as a real result)."
    fi
    if command -v lsof >/dev/null 2>&1; then
        openfiles=$(lsof +D "$WT" 2>/dev/null | tail -n +2 | head -5)
        if [ -n "$openfiles" ]; then
            echo "$openfiles" | sed 's/^/    /'
            die "open file handles under $WT — see above."
        fi
    fi
    dirty=$(git -C "$WT" status --porcelain 2>/dev/null \
            | grep -v -E "^\?\? Ortho4XP/(venv|OSM_data|Airport_mod_cache|Elevation_data)/?$")
    if [ -n "$dirty" ]; then
        echo "$dirty" | sed 's/^/    /'
        die "uncommitted changes in $WT (above).  Commit or record them
    first — a removed worktree takes them with it."
    fi
    for d in $LINK_DIRS; do
        [ -L "$ENGINE/$d" ] && rm "$ENGINE/$d"
    done
    for d in $CLONE_DIRS; do
        [ -d "$ENGINE/$d" ] && [ ! -L "$ENGINE/$d" ] && rm -rf "$ENGINE/$d"
    done
    for f in $CLONE_FILES; do
        [ -f "$ENGINE/$f" ] && rm -f "$ENGINE/$f"
    done
    git -C "$MAIN_REPO" worktree remove "$WT" || die "worktree remove failed"
    echo "  [ritual] $WT removed."
    ;;

*)
    usage
    ;;
esac
