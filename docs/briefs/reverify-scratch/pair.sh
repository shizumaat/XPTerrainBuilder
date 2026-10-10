#!/bin/zsh
# pair.sh NAME ICAO [DRIVER] — gap-free base with --null-change, late pair, pad_edge_read (seat2 pair.sh form).
# TREE=worktree root (default reverify); NULL=0 drops --null-change.
NAME=$1; ICAO=$2
TREE=${TREE:-/Users/noah/XPTerrainBuilder/.claude/worktrees/reverify}
DRV=${3:-tools/v2_solve_replay.py}
cd $TREE/Ortho4XP
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/reverify
CAP=/Users/noah/XPTerrainBuilderData/.harness/frames/pads67/$ICAO.pkl
D=$S/$NAME; mkdir -p $D
NC=--null-change; [ "$NULL" = 0 ] && NC=
echo "== $NAME $ICAO base_gf START $(date +%T) tree $(git rev-parse --short HEAD)" >> $S/.progress
venv/bin/python -u $DRV --replay $CAP --from classify --gap-free --workers 9 --solved-out $D/base_gf.pkl ${=NC} --json $D/base_gf.json > $D/base_gf.log 2>&1 || { echo "== $NAME base_gf FAILED $(date +%T)" >> $S/.progress; touch $D/FAILED; exit 1; }
echo "== $NAME late START $(date +%T)" >> $S/.progress
venv/bin/python -u $DRV --replay $CAP --from classify --workers 9 --late-from $D/base_gf.pkl --emit $D/emit --json $D/late.json > $D/late.log 2>&1 || { echo "== $NAME late FAILED $(date +%T)" >> $S/.progress; touch $D/FAILED; exit 1; }
venv/bin/python tools/pad_edge_read.py $D/emit/$ICAO.graded.json --capture $CAP --json $D/edge.json > $D/edge.txt 2>&1
echo "== $NAME $ICAO DONE $(date +%T)" >> $S/.progress; touch $D/DONE
