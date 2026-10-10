#!/bin/zsh
# rep.sh TREE ICAO TAG [extra replay args] — one replay of the registered pads67 capture under TREE (padfix | padfixctl),
# --from classify --emit into <scratch>/padfix/TAG; HECA and OTHH on the --gap-free base (as padsweep's null lines).
T=$1; A=$2; TAG=$3; shift 3
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padfix
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/$T/Ortho4XP
GF=(); [[ $A == HECA || $A == OTHH ]] && GF=(--gap-free)
mkdir -p $S/$TAG; rm -f $S/$TAG/DONE
echo "== rep $T $A $TAG START $(date +%T)" >> $S/.progress
venv/bin/python -u -W ignore tools/v2_solve_replay.py --replay /Users/noah/XPTerrainBuilderData/.harness/frames/pads67/$A.pkl --from classify $GF --workers 9 --emit $S/$TAG --json $S/$TAG/$A.json "$@" > $S/$TAG/log.txt 2>&1
echo "== rep $T $A $TAG EXIT rc=$? $(date +%T)" >> $S/.progress; touch $S/$TAG/DONE
