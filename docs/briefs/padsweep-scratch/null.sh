#!/bin/zsh
# null.sh ICAO [--gap-free] — the --null-change replay of the registered pads67 capture on the padsweep tree.
A=$1; shift; S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padsweep
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/padsweep/Ortho4XP
echo "== null $A START $(date +%T)" >> $S/.progress
venv/bin/python -u tools/v2_solve_replay.py --replay /Users/noah/XPTerrainBuilderData/.harness/frames/pads67/$A.pkl --from classify "$@" --workers 9 --null-change --z-out $S/null/$A.z.json --json $S/null/$A.json > $S/null/$A.log 2>&1
echo "== null $A EXIT rc=$? $(date +%T)" >> $S/.progress; touch $S/null/$A.DONE
