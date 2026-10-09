#!/bin/zsh
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/holering
n=0; until grep -q "chain3 DONE\|chain3 TIMED_OUT" $S/.progress || [ $n -ge 120 ]; do sleep 10; n=$((n+1)); done
[ $n -ge 120 ] && echo "chain4 TIMED_OUT waiting for chain3" >> $S/.progress
$S/pairC1.sh c2 HECA $S/armC2.py
$S/pairC1.sh kc2 KCLT $S/armC2.py
echo "chain4 DONE $(date +%T)" >> $S/.progress
