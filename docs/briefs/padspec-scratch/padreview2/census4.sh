#!/bin/zsh
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padreview2
cd /Users/noah/XPTerrainBuilder/Ortho4XP
for a in KCLT KASE; do venv/bin/python tools/harness/census.py /tmp/harness/swg_$a.osm --json $S/census_main_$a.json --quiet > $S/census_main_$a.txt 2>&1; echo "census main $a rc=$?" >> $S/.progress; done
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/padspec/Ortho4XP
for a in KCLT KASE; do venv/bin/python tools/harness/census.py /tmp/harness/p60_$a.osm --json $S/census_lane_$a.json --quiet > $S/census_lane_$a.txt 2>&1; echo "census lane $a rc=$?" >> $S/.progress; done
echo CENSUS_DONE >> $S/.progress
