#!/usr/bin/env bash
# master_land.sh — the ONLY way anything reaches main (owner 2026-10-02:
# ruleset "master-ack on main" requires a pull request AND the status
# `master-ack` on the head commit; nobody is on the bypass list, so a cloud
# lane's `gh pr merge` is refused and so is a direct push).
#
#   tools/master_land.sh pr  <PR#>  [merge message...]
#       set `master-ack` on the PR's head, merge it (merge commit), pull main.
#   tools/master_land.sh here <branch-name> <commit message...>
#       the master's own local commits on main (RULINGS, frames, briefs):
#       move them to <branch-name>, push, open a PR, ack, merge, pull.
#
# `master-ack` is a plain commit status set by this script; the master sets
# it only after the measurement that the merge message cites exists.
set -euo pipefail
REPO="shizumaat/XPTerrainBuilder"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ack() { # sha
  gh api -X POST "repos/$REPO/statuses/$1" -f state=success -f context=master-ack \
    -f description="measured and merged by the master session" >/dev/null
}

case "${1:-}" in
  pr)
    pr="$2"; shift 2
    sha="$(gh pr view "$pr" --json headRefOid --jq .headRefOid)"
    ack "$sha"
    if [ $# -gt 0 ]; then
      gh pr merge "$pr" --merge --subject "$*" --body "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
    else
      gh pr merge "$pr" --merge
    fi
    git pull -q --ff-only origin main
    ;;
  here)
    br="$2"; shift 2; msg="$*"
    git fetch -q origin
    base="$(git merge-base HEAD origin/main)"
    [ "$(git rev-parse HEAD)" != "$base" ] || { echo "nothing to land"; exit 1; }
    git branch -f "$br" HEAD
    git reset -q --hard origin/main
    git push -q -u origin "$br"
    url="$(gh pr create --base main --head "$br" --title "$msg" \
      --body "Master session landing (RULINGS / frames / briefs).

🤖 Generated with [Claude Code](https://claude.com/claude-code)")"
    pr="${url##*/}"
    ack "$(git rev-parse "$br")"
    gh pr merge "$pr" --merge --delete-branch
    git pull -q --ff-only origin main
    ;;
  *) sed -n 2,14p "$0"; exit 2 ;;
esac
