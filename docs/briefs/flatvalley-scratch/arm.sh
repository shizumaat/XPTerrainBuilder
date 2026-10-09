#!/bin/zsh
# usage: arm.sh TAG ICAO FV_ARM [extra replay args…]
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad; W=$S/flatvalley
TAG=$1; A=$2; ARM=$3; shift 3
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/flatvalley/Ortho4XP || exit 2
unsetopt bg_nice 2>/dev/null
D=$W/$TAG; mkdir -p $D
$W/hold.sh 3000 || { echo "arm $TAG $A HOLD_TIMED_OUT $(date)" >> $W/.progress; exit 3; }
echo "arm $TAG $A start $(date)" >> $W/.progress
FV_OUT=$D FV_ARM=$ARM venv/bin/python $W/nullarm.py --replay ${FV_CAP:-$W/cap/$A.pkl} --workers ${FV_WORKERS:-6} --from ${FV_FROM:-classify} --emit $D/emit --verify --solved-out $D/solved.pkl --json $D/rep.json "$@" > $D/rep.log 2>&1
rc=$?
echo "arm $TAG $A rc=$rc $(date)" >> $W/.progress
