#!/bin/zsh
# chain2: after ke0 — KCLT m null-change (base only, m tree), then SPJC m / c2, then OTHH m / c2. One at a time.
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/reverify
W=/Users/noah/XPTerrainBuilder/.claude/worktrees
n=0; until [ -f $S/ke0/DONE ] || [ -f $S/ke0/FAILED ] || [ -f $S/kc2/FAILED ] || [ $n -ge 360 ]; do sleep 10; n=$((n+1)); done
[ $n -ge 360 ] && { echo "chain2 TIMED_OUT waiting for ke0" >> $S/.progress; exit 1; }
mkdir -p $S/km0
echo "== km0 KCLT base_gf (m tree, null-change only) START $(date +%T)" >> $S/.progress
(cd $W/seat2f/Ortho4XP && venv/bin/python -u tools/v2_solve_replay.py --replay /Users/noah/XPTerrainBuilderData/.harness/frames/pads67/KCLT.pkl --from classify --gap-free --workers 9 --null-change --json $S/km0/base_gf.json > $S/km0/base_gf.log 2>&1)
echo "== km0 rc $? $(date +%T)" >> $S/.progress
TREE=$W/seat2f $S/pair.sh sm SPJC
$S/pair.sh sc2 SPJC
TREE=$W/seat2f $S/pair.sh om OTHH
$S/pair.sh oc2 OTHH
echo "chain2 DONE $(date +%T)" >> $S/.progress
