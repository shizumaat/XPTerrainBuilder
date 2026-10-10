#!/bin/zsh
# build.sh ICAO — the sw11 closing build of one airport on the padsweep tree, through the harness entry.
A=$1; S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padsweep
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/padsweep/Ortho4XP
echo "== build $A START $(date +%T)" >> $S/.progress
venv/bin/python tools/harness/build_airport.py $A --tag sw11_$A > $S/build_$A.log 2>&1
echo "== build $A EXIT rc=$? $(date +%T)" >> $S/.progress
touch $S/build_$A.DONE
