#!/bin/sh
# THE LANE RITUAL — create or tear down a lane worktree, correctly.
#
#   tools/harness/lane_worktree.sh up   NAME|PATH [REF]
#   tools/harness/lane_worktree.sh down NAME|PATH
#   tools/harness/lane_worktree.sh check NAME|PATH
#   tools/harness/lane_worktree.sh data          (report the shared repo)
#
# Run from anywhere.  Every lane sets its tree up with THIS script; a
# hand-typed ritual is a defect (see CLAUDE.md, "The standard test harness").
# A worktree missing any one of these pieces does not fail — it builds a
# silently different thing and exits 0.
#
# NAME or PATH: worktrees do not all live under one parent — Claude Code
# chip sessions create theirs at <repo>/Ortho4XP/.claude/worktrees/<name>,
# not $MAIN_REPO/.claude/worktrees/<name> — so the target resolves through
# `git worktree list` (the registry BOTH kinds live in), never a hard-coded
# parent dir.  A PATH (anything containing a slash; absolute or relative)
# addresses an EXISTING registered worktree — the "mount the corpus into a
# chip worktree" case that used to need a ../../ relative-NAME workaround
# (2026-08-27).  A bare NAME resolves to the unique registered worktree
# with that basename wherever it lives, falling back to $WT_ROOT/NAME —
# where `up` creates new lanes, exactly as before.
#
# ── ONE SHARED DATA REPO (owner ruling e9daef5, MANDATORY) ───────────
#
# /Users/noah/XPTerrainBuilderData is THE data repo: DEM + insets, OSM
# extracts + road feeds, airport mod cache, geotiffs, masks, DSF cache,
# orthophotos.  Every lane MOUNTS it — never copies, never creates a
# private cache.  Two lanes on two corpora do not measure the same thing:
# warm-vs-cold inset state alone has moved measured terrain by 12 m here,
# and a private cache is a second corpus that warms on its own schedule.
#
# WHAT `up` DOES, AND WHY EACH PIECE IS THE SHAPE IT IS:
#
#   the DATA DIRS      SYMLINKED into $DATA_REPO, all of them, whatever
#                      that repo actually holds (enumerated at run time,
#                      never a hard-coded subset — a data dir the ritual
#                      forgets is a private cache by omission).
#   venv/              SYMLINK to the MAIN ENGINE tree.  Not data: one
#                      interpreter and one set of installed packages for
#                      every lane.  A per-lane venv is 2 GB and a chance
#                      for the trees to diverge on a dependency.
#   Patches/           CLONED (cp -R), and this one is deliberate: every
#                      tile build WRITES {ICAO}_auto.patch.osm into
#                      Patches/<tile>/ (auto_patch.driver), so it is a
#                      lane's OUTPUT, not a cache.  Sharing it would let
#                      one lane's emitted patch enter another lane's tile
#                      build — the two lanes would then be grading each
#                      other's geometry.  Same reasoning keeps Tiles/,
#                      Previews/ and tmp/ lane-local; they are products,
#                      and the ruling's enumeration lists neither.
#   Ortho4XP.cfg       CLONED.  It is NOT tracked, so a fresh worktree has
#                      none at all — and then `Tile.read_from_config()`
#                      finds no config, the DEM prep runs on constructor
#                      defaults, and the lane grades against a surface
#                      production never builds.  Silent: one log line.
#   the PER-TILE cfg   NOT provisioned here, deliberately, and this is the
#                      one input that is not: it is per BUILD DIR, and a
#                      `--tile` run may be pointed at any directory
#                      (`--build-dir`, else <out>/tile_<tag>), which no
#                      lane-setup step can know.  `build_airport.py`
#                      provisions it at the build instead — a BYTE COPY
#                      from THIS SAME canonical tree
#                      ($MAIN_ENGINE/Tiles/zOrtho4XP_+XX+YYY/), recorded
#                      with its sha256 in <tag>.frame.json.  Do not add a
#                      second copy of that rule here: one source, one
#                      implementation (owner ruling 2026-08-12b, lane
#                      inputs are provisioned, never hand-seeded).
#   tools/INDEX.md     REACHABLE, always — see below.
#
# ── THE CONSULTATION SURFACE (owner ruling 7e90032) ──────────────────
#
# "Consult tools/INDEX.md BEFORE writing any script that builds, measures
# or audits; a tool absent from the index is treated as absent."  A lane
# that cannot READ the index consults nothing and forks a near-fit — the
# census-wrapper defect, which is what that ruling costs when it lapses.
#
# The index is a TRACKED file at the repo root, so a worktree checked out
# at a ref that already carries it has it.  Two ways a lane loses it, both
# silent:
#
#   * `up NAME <OLD-REF>` — the ref predates the index commit, so the
#     checkout has no tools/ at all.  Measured 2026-08-06: 30 of the 58
#     worktrees on this machine had NO tools/INDEX.md, and
#     tests/test_harness.py's own index twin fails in every one of them.
#   * the lane's tracked copy is a SNAPSHOT of its ref: a tool promoted
#     into the index after that point is invisible here, and "absent from
#     the index" then reads as "does not exist" — the fork again, from the
#     other direction.
#
# So `up` makes the index reachable and says which case it is: a TRACKED
# copy is reported and diffed against the main tree's live one (never
# overwritten — a lane promoting a tool EDITS its tracked index, and that
# is the same file); a missing one is MIRRORED read-only from the main
# tree so `Ortho4XP/tools/README.md`'s `../../tools/INDEX.md` pointer
# resolves here too.  `check` re-audits: MISSING is a failure with the
# one-command fix, STALE is reported and never a refusal (a lane adding
# its own index row is legitimately different from main).
#
# The symlinks are deliberately NOT git-added (the repo's .gitignore uses
# directory patterns, which do not match symlinks — so `git status` shows
# them as untracked and a careless `git add -A` would commit them).  `up`
# ends by REFUSING if anything but those paths — and an untracked index
# MIRROR — is untracked, and `check` re-runs that audit at any time.
#
# `down` refuses while a child process still holds the tree — tearing a
# worktree out from under a live build produces a half-written patch and a
# "not reproducible" report.
set -u

MAIN_REPO="${O4_MAIN_REPO:-/Users/noah/XPTerrainBuilder}"
MAIN_ENGINE="$MAIN_REPO/Ortho4XP"
WT_ROOT="$MAIN_REPO/.claude/worktrees"
DATA_REPO="${O4_DATA_REPO:-/Users/noah/XPTerrainBuilderData}"

# Mounted from the MAIN ENGINE tree (code-adjacent, not data).
ENGINE_LINKS="venv"
# Mounted from the SHARED DATA REPO.  Enumerated from the repo itself at
# run time; this list is the REQUIRED floor — a missing one is a refusal,
# because its absence is what silently turns road/corridor/DEM code paths
# into no-ops.
REQUIRED_DATA_DIRS="OSM_data Elevation_data Airport_mod_cache"
# Products, never shared.  See the header for why Patches is the exception.
CLONE_DIRS="Patches"
CLONE_FILES="Ortho4XP.cfg"
# Lane-local products that must NOT be mounted even if the data repo has
# them — two lanes writing one of these would overwrite each other's work.
NEVER_MOUNT="Patches Tiles Previews tmp"
# The consultation surface (owner ruling 7e90032), relative to the REPO
# ROOT of both the main tree and the worktree.  Mirrored read-only into a
# lane whose checkout does not carry it; never overwritten when it does.
INDEX_REL="tools/INDEX.md"

die() { echo "REFUSING: $*" >&2; exit 2; }

usage() {
    echo "usage: $0 {up|down|check} NAME|PATH [REF]" >&2
    echo "       $0 data" >&2
    echo "       (PATH — anything with a slash — addresses an EXISTING" >&2
    echo "        registered worktree, e.g. a chip session's under" >&2
    echo "        Ortho4XP/.claude/worktrees/; NAME creates/finds a lane)" >&2
    exit 64
}

# Every worktree registered on the repo, one absolute path per line —
# the ONE registry both $WT_ROOT lanes and chip-session worktrees
# (Ortho4XP/.claude/worktrees/*) appear in.
registered_worktrees() {
    git -C "$MAIN_REPO" worktree list --porcelain 2>/dev/null \
        | sed -n 's/^worktree //p'
}

# ── which data dirs does the shared repo actually hold? ──────────────
# Enumerated, never hard-coded: the ruling says every lane mounts THE data
# repo, so whatever data it grows is mounted too.  Products are excluded.
data_dirs() {
    [ -d "$DATA_REPO" ] || die "the shared data repo $DATA_REPO does not
    exist.  Owner ruling e9daef5: it is THE data repo and every lane mounts
    it.  Set O4_DATA_REPO if it lives elsewhere on this machine."
    for entry in "$DATA_REPO"/*/; do
        [ -d "$entry" ] || continue
        base=$(basename "$entry")
        skip=0
        for n in $NEVER_MOUNT; do
            [ "$base" = "$n" ] && skip=1
        done
        [ $skip -eq 1 ] && continue
        echo "$base"
    done
}

[ $# -ge 1 ] || usage
ACTION="$1"

if [ "$ACTION" = "data" ]; then
    echo "  [ritual] shared data repo: $DATA_REPO"
    for d in $(data_dirs); do
        printf "  [ritual]   %-20s %s entries, %s\n" "$d" \
            "$(ls -1 "$DATA_REPO/$d" 2>/dev/null | wc -l | tr -d ' ')" \
            "$(du -sh "$DATA_REPO/$d" 2>/dev/null | cut -f1)"
    done
    echo "  [ritual] NOT mounted (lane-local products): $NEVER_MOUNT"
    echo "  [ritual] trees and their corpus:"
    # Enumerated from `git worktree list`, so chip-session worktrees
    # (Ortho4XP/.claude/worktrees/*) are reported alongside $WT_ROOT lanes.
    { echo "$MAIN_ENGINE"
      registered_worktrees | grep -vFx "$MAIN_REPO" | sed 's|$|/Ortho4XP|'
    } | while IFS= read -r tree; do
        [ -d "$tree" ] || continue
        on_shared=0; private=0
        for d in $(data_dirs); do
            [ -e "$tree/$d" ] || continue
            case "$(cd "$tree" 2>/dev/null && readlink -f "$d" 2>/dev/null)" in
                "$DATA_REPO"/*) on_shared=$((on_shared+1)) ;;
                *) private=$((private+1)) ;;
            esac
        done
        if [ $private -gt 0 ]; then
            printf "  [ritual]   PRIVATE  %s (%s shared, %s private)\n" \
                "$tree" "$on_shared" "$private"
        elif [ $on_shared -gt 0 ]; then
            printf "  [ritual]   shared   %s (%s dirs)\n" "$tree" "$on_shared"
        fi
    done
    echo "  [ritual] a PRIVATE tree is on a DIFFERENT CORPUS — never A/B a"
    echo "           build from one against a build from a shared tree."
    exit 0
fi

[ $# -ge 2 ] || usage
TARGET="$2"
REF="${3:-HEAD}"

# ── NAME or PATH → the worktree, via `git worktree list` ─────────────
case "$TARGET" in
*/*|.|..)
    # PATH form: an EXISTING registered worktree, wherever it lives.
    [ $# -le 2 ] || die "a REF only applies when 'up' CREATES a new lane
    by NAME; the PATH form addresses an existing worktree at its own
    checkout."
    _dir=$( (cd "$TARGET" 2>/dev/null && pwd -P) ) \
        || die "no directory at $TARGET.  The PATH form addresses an
    EXISTING worktree; create a new lane by NAME."
    WT=$(registered_worktrees | while IFS= read -r _w; do
            if [ "$( (cd "$_w" 2>/dev/null && pwd -P) )" = "$_dir" ]; then
                printf '%s\n' "$_w"
                break
            fi
         done)
    [ -n "$WT" ] || die "$_dir is not a registered worktree of $MAIN_REPO
    ('git worktree list' does not know it).  The ritual mounts real
    worktrees only — a plain directory would become a second private tree."
    ;;
*)
    # NAME form: the unique registered worktree with this basename —
    # chip worktrees under Ortho4XP/.claude/worktrees/ resolve too —
    # else $WT_ROOT/NAME, where `up` creates new lanes.
    _hits=$(registered_worktrees | grep -vFx "$MAIN_REPO" \
            | awk -v n="$TARGET" \
                  'substr($0, length($0) - length(n)) == "/" n')
    _n=$(printf '%s\n' "$_hits" | grep -c .)
    if [ "$_n" -gt 1 ]; then
        echo "$_hits" | sed 's/^/    /' >&2
        die "worktree name '$TARGET' is AMBIGUOUS (the trees above all
    carry it).  Address the one you mean by PATH."
    elif [ "$_n" -eq 1 ]; then
        WT="$_hits"
    else
        WT="$WT_ROOT/$TARGET"
    fi
    ;;
esac
_mainphys=$( (cd "$MAIN_REPO" && pwd -P) )
[ "$( (cd "$WT" 2>/dev/null && pwd -P) )" != "$_mainphys" ] \
    || die "$WT is the MAIN repository, not a lane worktree — the ritual
    never mounts or tears down the main tree."
NAME=$(basename "$WT")
ENGINE="$WT/Ortho4XP"

# ── the untracked-path audit ─────────────────────────────────────────
# Only the mounted symlinks — and an index MIRROR in a worktree whose ref
# predates the tracked index — may be untracked.  Anything else is either
# a lane artifact that belongs in the scratchpad or an edit about to be
# swept into someone else's "Round N" omnibus commit.  (git collapses a
# wholly-untracked directory to `tools/`, so both spellings are allowed.)
audit_untracked() {
    _allow="venv"
    for d in $(data_dirs); do
        _allow="$_allow|$d"
    done
    _bad=$(git -C "$WT" status --porcelain 2>/dev/null \
           | sed -n 's/^?? //p' \
           | grep -v -E "^Ortho4XP/($_allow)/?$" \
           | grep -v -E "^tools/(INDEX\.md)?$")
    if [ -n "$_bad" ]; then
        echo "  [ritual] UNTRACKED paths beyond the mounted symlinks:"
        echo "$_bad" | sed 's/^/    /'
        echo "  [ritual] NEVER 'git add -A' in a lane tree — the symlinks"
        echo "           would be committed (the .gitignore dir patterns do"
        echo "           not match symlinks).  Add files by explicit path."
        return 1
    fi
    echo "  [ritual] untracked audit clean (only the mounted symlinks)."
    return 0
}

# One symlink, reported.  $1 = name, $2 = target.
mount_link() {
    _name="$1"; _target="$2"
    if [ -L "$ENGINE/$_name" ]; then
        _cur=$(readlink "$ENGINE/$_name")
        if [ "$_cur" != "$_target" ]; then
            rm "$ENGINE/$_name"
            ln -s "$_target" "$ENGINE/$_name" || die "could not relink $_name"
            echo "  [ritual] RE-MOUNTED $_name -> $_target"
            echo "             (was $_cur — this lane's CORPUS CHANGED;"
            echo "              do not compare its builds against earlier ones)"
            return 0
        fi
    elif [ -e "$ENGINE/$_name" ]; then
        die "$ENGINE/$_name exists and is NOT a symlink.  A real
    $_name in a lane tree is a PRIVATE CACHE — the one thing owner ruling
    e9daef5 forbids.  Move its contents into $DATA_REPO/$_name, remove it,
    and re-run."
    else
        ln -s "$_target" "$ENGINE/$_name" || die "could not link $_name"
    fi
    echo "  [ritual] mount $_name -> $_target"
}

# Is $WT/$INDEX_REL a TRACKED file in this worktree's checkout?
index_is_tracked() {
    git -C "$WT" ls-files --error-unmatch "$INDEX_REL" >/dev/null 2>&1
}

# ── the consultation surface, made reachable ─────────────────────────
# $1 = "up" (mirror what is missing, refresh a mirror) or "check" (audit
# only, never write).  Echoes one [ritual] line per state and returns
# non-zero ONLY for MISSING — a stale or lane-edited index is reported,
# because a lane that is ADDING its index row differs from main by design.
index_state() {
    _mode="$1"
    _src="$MAIN_REPO/$INDEX_REL"
    _dst="$WT/$INDEX_REL"
    if [ ! -f "$_src" ]; then
        echo "  [ritual] NO INDEX  the MAIN tree has no $INDEX_REL —"
        echo "                   owner ruling 7e90032's consultation surface"
        echo "                   is gone from the source of truth itself"
        return 1
    fi
    if index_is_tracked; then
        if cmp -s "$_src" "$_dst"; then
            echo "  [ritual] OK      $INDEX_REL tracked here and identical to the main tree"
        else
            echo "  [ritual] DIFFERS $INDEX_REL is tracked here but differs from"
            echo "                   $_src — expected while this lane is adding its"
            echo "                   own index row; otherwise this checkout's ref"
            echo "                   PREDATES a promotion and a tool that exists"
            echo "                   will read as absent.  Not overwritten: the"
            echo "                   tracked file is the one a promotion edits."
        fi
        return 0
    fi
    # Untracked: either an existing MIRROR or nothing at all.
    if [ "$_mode" = "up" ]; then
        mkdir -p "$(dirname "$_dst")" || die "could not create $(dirname "$_dst")"
        [ -f "$_dst" ] && chmod u+w "$_dst" 2>/dev/null
        cp "$_src" "$_dst" || die "could not mirror $INDEX_REL into $WT"
        chmod 444 "$_dst"
        echo "  [ritual] MIRRORED $INDEX_REL (read-only) from the main tree —"
        echo "                   this checkout's ref predates the tracked index;"
        echo "                   consult it, do not edit it here"
        return 0
    fi
    if [ -f "$_dst" ]; then
        if cmp -s "$_src" "$_dst"; then
            echo "  [ritual] OK      $INDEX_REL mirrored (read-only) and current"
        else
            echo "  [ritual] STALE   $INDEX_REL mirror differs from the main tree's."
            echo "                   Re-run 'up $NAME' to refresh it — a stale index"
            echo "                   hides a promoted tool, and an absent tool is"
            echo "                   forked (owner ruling 7e90032)."
        fi
        return 0
    fi
    echo "  [ritual] MISSING $INDEX_REL — this lane cannot consult the tool"
    echo "                   index at all, so every 'does this tool exist?'"
    echo "                   answers NO and the near-fit gets forked"
    echo "                   (owner ruling 7e90032).  Fix: $0 up $NAME"
    return 1
}

case "$ACTION" in
up)
    [ -d "$MAIN_ENGINE" ] || die "no engine tree at $MAIN_ENGINE"
    DATA_LIST=$(data_dirs)
    for d in $REQUIRED_DATA_DIRS; do
        [ -d "$DATA_REPO/$d" ] || die "the shared data repo has no $d.
    Without it the road / corridor / DEM code paths silently NO-OP and the
    build exits 0 with a smaller layout that reads as a speedup."
    done
    if [ -d "$WT" ]; then
        echo "  [ritual] worktree $WT already exists — completing the ritual."
    else
        git -C "$MAIN_REPO" worktree add "$WT" "$REF" || die "worktree add failed"
    fi
    for d in $ENGINE_LINKS; do
        mount_link "$d" "$MAIN_ENGINE/$d"
    done
    for d in $DATA_LIST; do
        mount_link "$d" "$DATA_REPO/$d"
    done
    for d in $CLONE_DIRS; do
        mkdir -p "$ENGINE/$d"
        [ -L "$ENGINE/$d" ] && die "$d must be a real directory, not a symlink:
    every tile build WRITES its emitted patches there, so sharing it would
    put one lane's geometry into another lane's build."
        for src in "$MAIN_ENGINE/$d"/*/; do
            [ -d "$src" ] || continue
            base=$(basename "$src")
            [ -e "$ENGINE/$d/$base" ] || cp -R "$src" "$ENGINE/$d/$base"
        done
        echo "  [ritual] cloned $d ($(ls -1 "$ENGINE/$d" 2>/dev/null | wc -l | tr -d ' ') entries) — lane-private OUTPUT, writes stay here"
    done
    for f in $CLONE_FILES; do
        [ -e "$MAIN_ENGINE/$f" ] || die "the MAIN tree has no $f — without
    it every build in this lane would run on constructor defaults."
        [ -e "$ENGINE/$f" ] || cp "$MAIN_ENGINE/$f" "$ENGINE/$f"
        echo "  [ritual] cloned $f (untracked in git: a fresh worktree has none)"
    done
    # The consultation surface, before anything is built here.
    index_state up || die "the tool index is unreachable from $WT and could
    not be mirrored.  Owner ruling 7e90032 makes it the consultation
    surface; a lane without it forks near-fits by construction."
    # Prove the ritual took: the build entry's own refusal, run here.
    ( cd "$ENGINE" && [ -d venv ] && [ -d OSM_data ] ) \
        || die "post-ritual check failed: $ENGINE still lacks venv/OSM_data"
    echo "  [ritual] $ENGINE is build-ready on the SHARED corpus."
    # The main tree may still hold private caches; a lane that A/Bs against
    # it would be comparing two corpora.  Say so rather than assume.
    for d in $REQUIRED_DATA_DIRS; do
        if [ -d "$MAIN_ENGINE/$d" ] && [ ! -L "$MAIN_ENGINE/$d" ]; then
            echo "  [ritual] NOTE: $MAIN_ENGINE/$d is a PRIVATE directory,"
            echo "           not a mount of $DATA_REPO/$d.  The main tree is"
            echo "           on a DIFFERENT CORPUS from this lane — never A/B"
            echo "           a build here against one from there.  ('$0 data'"
            echo "           lists every tree and its corpus.)"
            break
        fi
    done
    audit_untracked
    echo "  [ritual] next: cd $ENGINE && venv/bin/python tools/harness/build_airport.py ICAO"
    ;;

check)
    [ -d "$WT" ] || die "no worktree at $WT"
    rc=0
    for d in $ENGINE_LINKS; do
        if [ -L "$ENGINE/$d" ]; then
            echo "  [ritual] OK      $d -> $(readlink "$ENGINE/$d")"
        else
            echo "  [ritual] BROKEN  $d is not a symlink"; rc=1
        fi
    done
    for d in $(data_dirs); do
        if [ ! -e "$ENGINE/$d" ]; then
            echo "  [ritual] MISSING $d — not mounted from the shared repo"
            rc=1
        elif [ ! -L "$ENGINE/$d" ]; then
            echo "  [ritual] PRIVATE $d is a REAL directory — a private cache,"
            echo "                   which owner ruling e9daef5 forbids"; rc=1
        else
            _real=$(cd "$ENGINE" && readlink -f "$d" 2>/dev/null)
            case "$_real" in
                "$DATA_REPO"/*) echo "  [ritual] OK      $d -> $_real" ;;
                *) echo "  [ritual] OFF-REPO $d resolves to $_real, not under"
                   echo "                   $DATA_REPO — a DIFFERENT CORPUS"
                   rc=1 ;;
            esac
        fi
    done
    for d in $CLONE_DIRS; do
        if [ -L "$ENGINE/$d" ]; then
            echo "  [ritual] BROKEN  $d is a SYMLINK (must be a lane-local clone:"
            echo "                   every tile build writes its patches there)"
            rc=1
        else
            echo "  [ritual] OK      $d cloned (lane-local output)"
        fi
    done
    for f in $CLONE_FILES; do
        if [ -f "$ENGINE/$f" ]; then
            echo "  [ritual] OK      $f present"
        else
            echo "  [ritual] BROKEN  $f missing — builds would run on"
            echo "                   constructor defaults, not production's"; rc=1
        fi
    done
    index_state check || rc=1
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
    # A lock this lane still holds in the SHARED repo would strand every
    # other lane behind a worktree that no longer exists.
    lockdir="$DATA_REPO/.harness/locks"
    if [ -d "$lockdir" ]; then
        held=$(grep -l "$WT" "$lockdir"/*.lock 2>/dev/null)
        if [ -n "$held" ]; then
            echo "$held" | sed 's/^/    /'
            die "this lane still holds shared-repo refresh lock(s) above.
    Let the refresh finish, or release them, before removing the tree —
    a stale lock blocks every other lane's explicit refresh."
        fi
    fi
    # The index MIRROR is ritual scaffolding, not lane work: drop it before
    # the dirty audit so it can never read as "uncommitted changes" and
    # strand a finished lane.  A TRACKED index is never touched — if the
    # lane edited it, that IS lane work and the audit below must see it.
    if [ -f "$WT/$INDEX_REL" ] && ! index_is_tracked; then
        chmod u+w "$WT/$INDEX_REL" 2>/dev/null
        rm -f "$WT/$INDEX_REL"
        rmdir "$WT/$(dirname "$INDEX_REL")" 2>/dev/null
    fi
    dirty=$(git -C "$WT" status --porcelain 2>/dev/null | sed -n 's/^?? //p' \
            | grep -v -E "^Ortho4XP/(venv|$(data_dirs | tr '\n' '|' | sed 's/|$//'))/?$")
    dirty="$dirty$(git -C "$WT" status --porcelain 2>/dev/null | grep -v '^??')"
    if [ -n "$dirty" ]; then
        echo "$dirty" | sed 's/^/    /'
        die "uncommitted changes in $WT (above).  Commit or record them
    first — a removed worktree takes them with it."
    fi
    for d in $ENGINE_LINKS $(data_dirs); do
        [ -L "$ENGINE/$d" ] && rm "$ENGINE/$d"
    done
    for d in $CLONE_DIRS; do
        [ -d "$ENGINE/$d" ] && [ ! -L "$ENGINE/$d" ] && rm -rf "$ENGINE/$d"
        # …and PUT BACK whatever git tracks under it.  `Patches/` is
        # gitignored as a whole, but one shipped patch inside it
        # (Ortho4XP/Patches/+39-078/2W2_runways.patch.osm) is tracked, so
        # the clone removal above deletes a TRACKED file and
        # `git worktree remove` then refuses "contains modified or
        # untracked files" — teardown fails at the last step, after the
        # mounts are already gone.  Measured 2026-08-06 on a real lane;
        # 58 worktrees were lingering on this machine.  The dirty audit
        # above has already refused any real lane work, so the only
        # deletions here are the ritual's own.
        git -C "$WT" checkout -- "Ortho4XP/$d" 2>/dev/null || true
    done
    for f in $CLONE_FILES; do
        [ -f "$ENGINE/$f" ] && rm -f "$ENGINE/$f"
        git -C "$WT" checkout -- "Ortho4XP/$f" 2>/dev/null || true
    done
    git -C "$MAIN_REPO" worktree remove "$WT" || die "worktree remove failed"
    echo "  [ritual] $WT removed."
    ;;

*)
    usage
    ;;
esac
