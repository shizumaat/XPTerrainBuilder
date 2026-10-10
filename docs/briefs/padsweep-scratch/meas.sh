#!/bin/zsh
# meas.sh ICAO — the reads of sw11_ICAO against sw10_ICAO: census (each tree's own), value delta, pad edge read.
A=$1; SS=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad; S=$SS/padsweep; M=$S/m
W=/Users/noah/XPTerrainBuilder/.claude/worktrees/padsweep/Ortho4XP; B=/Users/noah/XPTerrainBuilder/.claude/worktrees/pass2main/Ortho4XP
CAP=/Users/noah/XPTerrainBuilderData/.harness/frames/pads67/$A.pkl; H=/tmp/harness
echo "== meas $A START $(date +%T)" >> $S/.progress
( cd $B; [ -f $M/${A}_base.census.json ] || venv/bin/python tools/harness/census.py $H/sw10_$A.osm --json $M/${A}_base.census.json --rows-json $M/${A}_base.rows.json --class > $M/${A}_base.census.txt 2>&1 ) &
( cd $W; venv/bin/python tools/harness/census.py $H/sw11_$A.osm --json $M/${A}_arm.census.json --rows-json $M/${A}_arm.rows.json --class > $M/${A}_arm.census.txt 2>&1 ) &
wait
cd $W
venv/bin/python -W ignore tools/airside_value_delta.py $H/sw10_$A.osm $H/sw11_$A.osm --tol 0.02 --top 5 --by-ref 12 --json $M/${A}_avd.json > $M/${A}_avd.txt 2>&1
SRC=$H/sw11_$A.osm.axes.json; grep -q '"pad_touch"' $SRC || SRC=$CAP
( venv/bin/python -W ignore tools/pad_edge_read.py $H/sw11_$A.v2/$A.graded.json --capture $CAP --source $SRC --json $M/${A}_arm.edge.json > $M/${A}_arm.edge.txt 2>&1 ) &
( [ -f $M/${A}_base.edge.json ] || venv/bin/python -W ignore tools/pad_edge_read.py $H/sw10_$A.v2/$A.graded.json --capture $CAP --source $CAP --json $M/${A}_base.edge.json > $M/${A}_base.edge.txt 2>&1 ) &
wait
venv/bin/python tools/census_rows_diff.py $M/${A}_base.rows.json $M/${A}_arm.rows.json --top 8 --json $M/${A}_rowsdiff.json > $M/${A}_rowsdiff.txt 2>&1
echo "== meas $A DONE $(date +%T)" >> $S/.progress; touch $M/$A.DONE
