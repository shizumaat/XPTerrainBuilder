#!/bin/zsh
# usage: build.sh ICAO TAG  (pads60's build.sh, this lane's scratch)
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pads62
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/padspec/Ortho4XP
unsetopt bg_nice 2>/dev/null
echo "build $2 start $(date)" >> $S/.progress
venv/bin/python tools/run_with_ledger.py -- venv/bin/python tools/harness/build_airport.py $1 --tag $2 > $S/build_$2.log 2>&1
echo "build $2 EXIT $? $(date)" >> $S/.progress
