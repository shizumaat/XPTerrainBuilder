#!/bin/sh
# lane_worktree.sh prune-merged [--apply] — tear down every lane worktree
# whose work is on main (owner request 2026-11-03: "purges completed lanes
# worktrees when their PRs are merged").  Reached ONLY through
# lane_worktree.sh, which execs this with its own path first.
#
# A tree under any */.claude/worktrees/ is REMOVED, through the ritual's own
# `down` (so every `down` refusal — uncommitted work, a live holder, a
# shared-repo lock — still keeps it), only when its work is merged:
#   * its HEAD is an ancestor of $BASE (origin/main) and is not a commit of
#     main's own first-parent line — lane commits land as merge parents; or
#   * a MERGED pull request's head is its HEAD (or descends from it) — the
#     squash/rebase case ancestry cannot see; or
#   * its HEAD sits ON main's first-parent line (no commits of its own) and
#     the tree has been idle for $MIN_AGE_H hours — a fresh lane looks
#     exactly like this, so it gets the grace period.
# Never touched: the tree this runs from, the tree this script lives in,
# and the main checkout.  Dry run unless --apply.
set -u
RITUAL="$1"; shift; shift            # our caller's path, then "prune-merged"
APPLY=0
for a in "$@"; do
    case "$a" in
        --apply) APPLY=1 ;;
        *) echo "usage: lane_worktree.sh prune-merged [--apply]" >&2; exit 64 ;;
    esac
done
MAIN_REPO="${O4_MAIN_REPO:-/Users/noah/XPTerrainBuilder}"
BASE="${O4_PRUNE_BASE:-origin/main}"
MIN_AGE_H="${O4_PRUNE_MIN_AGE_H:-24}"
TMPD=$(mktemp -d "${TMPDIR:-/tmp}/prune_merged.XXXXXX") || exit 1
trap 'rm -rf "$TMPD"' EXIT

phys() { (cd "$1" 2>/dev/null && pwd -P); }
avail() { df -h "$MAIN_REPO" 2>/dev/null | awk 'NR == 2 { print $4 }'; }
# GNU stat first: on Linux `stat -f` is filesystem status and succeeds
# with a non-mtime answer, so the BSD spelling must not be tried first.
mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }

case "$BASE" in origin/*)
    git -C "$MAIN_REPO" fetch -q origin "${BASE#origin/}" 2>/dev/null \
        || echo "  [prune] WARNING: fetch failed; judging against the local $BASE" ;;
esac
git -C "$MAIN_REPO" rev-parse -q --verify "$BASE^{commit}" >/dev/null \
    || { echo "REFUSING: no $BASE in $MAIN_REPO" >&2; exit 2; }
git -C "$MAIN_REPO" rev-list --first-parent "$BASE" > "$TMPD/firstparent"
# Merged PRs as "branch<TAB>head-sha<TAB>number"; gh failing only narrows
# the evidence to ancestry.
(cd "$MAIN_REPO" && gh pr list --state merged --limit 1000 \
    --json headRefName,headRefOid,number \
    --jq '.[] | [.headRefName, .headRefOid, (.number | tostring)] | @tsv') \
    > "$TMPD/merged" 2>/dev/null \
    || { : > "$TMPD/merged"
         echo "  [prune] WARNING: gh pr list failed; ancestry is the only evidence"; }

SELF=$(git rev-parse --show-toplevel 2>/dev/null); SELF=$(phys "${SELF:-.}")
HOME_TREE=$(phys "$(dirname "$RITUAL")/../../..")
MAIN_PHYS=$(phys "$MAIN_REPO")
NOW=$(date +%s)
BEFORE=$(avail)
removed=0; kept=0

# One record per worktree: path, HEAD, branch ("" when detached).
git -C "$MAIN_REPO" worktree list --porcelain | awk '
    /^worktree / { if (p != "") print p "\t" h "\t" b; p = substr($0, 10); h = ""; b = "" }
    /^HEAD /     { h = substr($0, 6) }
    /^branch /   { b = substr($0, 8); sub("^refs/heads/", "", b) }
    END          { if (p != "") print p "\t" h "\t" b }' > "$TMPD/trees"

while IFS="	" read -r wt head branch; do
    case "$wt" in */.claude/worktrees/*) ;; *) continue ;; esac
    name=$(basename "$wt")
    say() { printf '  %-7s %-28s %s\n' "$1" "$name" "$2"; }
    p=$(phys "$wt")
    if [ -z "$p" ]; then say kept "directory missing (git worktree prune clears it)"; kept=$((kept+1)); continue; fi
    if [ "$p" = "$SELF" ] || [ "$p" = "$HOME_TREE" ] || [ "$p" = "$MAIN_PHYS" ]; then
        say kept "the tree this runs from"; kept=$((kept+1)); continue
    fi
    why=""
    on_line=0; grep -qx "$head" "$TMPD/firstparent" && on_line=1
    if [ $on_line -eq 0 ] && git -C "$MAIN_REPO" merge-base --is-ancestor "$head" "$BASE" 2>/dev/null; then
        why="merged: HEAD ${head%"${head#???????}"} is in $BASE"
    fi
    if [ -z "$why" ] && [ -n "$branch" ]; then
        while IFS="	" read -r b oid num; do
            [ "$b" = "$branch" ] || continue
            if [ "$oid" = "$head" ] || git -C "$MAIN_REPO" merge-base --is-ancestor "$head" "$oid" 2>/dev/null; then
                why="merged: PR #$num"; break
            fi
        done < "$TMPD/merged"
    fi
    if [ -z "$why" ] && [ $on_line -eq 1 ]; then
        gd=$(git -C "$wt" rev-parse --absolute-git-dir 2>/dev/null)
        last=0
        for f in "$gd/index" "$gd/HEAD" "$gd/logs/HEAD"; do
            m=$(mtime "$f"); [ "$m" -gt "$last" ] && last=$m
        done
        idle_h=$(( (NOW - last) / 3600 ))
        if [ "$idle_h" -ge "$MIN_AGE_H" ]; then
            why="no commits of its own, idle ${idle_h}h"
        else
            say kept "no commits of its own, active ${idle_h}h ago (fresh lane?)"; kept=$((kept+1)); continue
        fi
    fi
    if [ -z "$why" ]; then
        say kept "not merged${branch:+ (branch $branch)}"; kept=$((kept+1)); continue
    fi
    if [ -n "$(git -C "$wt" status --porcelain --untracked-files=no 2>/dev/null)" ]; then
        say kept "$why, but has uncommitted changes"; kept=$((kept+1)); continue
    fi
    if [ $APPLY -eq 0 ]; then
        say remove "$why  [dry run; down may still refuse]"; removed=$((removed+1)); continue
    fi
    if out=$("$RITUAL" down "$wt" 2>&1 </dev/null); then
        say removed "$why"; removed=$((removed+1))
    else
        say kept "$why, but down refused: $(printf '%s\n' "$out" | grep -m1 REFUSING | cut -c1-110)"
        kept=$((kept+1))
    fi
done < "$TMPD/trees"

if [ $APPLY -eq 1 ]; then
    echo "  [prune] removed $removed, kept $kept; free space $BEFORE before, $(avail) after"
else
    echo "  [prune] DRY RUN: would remove $removed, keep $kept; free space $BEFORE (--apply to remove)"
fi
