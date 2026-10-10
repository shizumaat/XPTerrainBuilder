#!/bin/zsh
# meas.sh ICAO — the reads of sw12_ICAO (claude/padfix) against sw10_ICAO (main; base reads shared from padsweep's m/)
# and the value delta against sw11_ICAO (the merged head the fixes started from).
A=$1; SS=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad; S=$SS/padfix; M=$S/m
W=/Users/noah/XPTerrainBuilder/.claude/worktrees/padfix/Ortho4XP
CAP=/Users/noah/XPTerrainBuilderData/.harness/frames/pads67/$A.pkl; H=/tmp/harness
echo "== meas $A START $(date +%T)" >> $S/.progress
cd $W
venv/bin/python tools/harness/census.py $H/sw12_$A.osm --json $M/${A}_arm.census.json --rows-json $M/${A}_arm.rows.json --class > $M/${A}_arm.census.txt 2>&1
venv/bin/python -W ignore tools/airside_value_delta.py $H/sw10_$A.osm $H/sw12_$A.osm --tol 0.02 --top 5 --by-ref 12 --json $M/${A}_avd.json > $M/${A}_avd.txt 2>&1
venv/bin/python -W ignore tools/airside_value_delta.py $H/sw11_$A.osm $H/sw12_$A.osm --tol 0.02 --top 8 --by-ref 12 --json $M/${A}_avd11.json > $M/${A}_avd11.txt 2>&1
SRC=$H/sw12_$A.osm.axes.json; grep -q '"pad_touch"' $SRC || SRC=$CAP
venv/bin/python -W ignore tools/pad_edge_read.py $H/sw12_$A.v2/$A.graded.json --capture $CAP --source $SRC --json $M/${A}_arm.edge.json > $M/${A}_arm.edge.txt 2>&1
venv/bin/python tools/census_rows_diff.py $M/${A}_base.rows.json $M/${A}_arm.rows.json --top 8 --json $M/${A}_rowsdiff.json > $M/${A}_rowsdiff.txt 2>&1
venv/bin/python tools/census_rows_diff.py $SS/padsweep/m/${A}_arm.rows.json $M/${A}_arm.rows.json --top 8 --json $M/${A}_rowsdiff11.json > $M/${A}_rowsdiff11.txt 2>&1
venv/bin/python $S/row.py $A > $M/${A}_row.txt 2>&1
echo "== meas $A DONE $(date +%T)" >> $S/.progress; touch $M/$A.DONE
