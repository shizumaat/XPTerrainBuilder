#!/bin/zsh
# small.sh — the four small airports, control tree then fix tree, body hash of each emitted patch.
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padfix
for A in NLWF CYXY KASE SPJC; do
  $S/rep.sh padfixctl $A s0_$A; $S/rep.sh padfix $A s1_$A
  echo "$A control $(shasum -a 256 $S/s0_$A/${A}_auto.patch.osm | cut -c1-16) fix $(shasum -a 256 $S/s1_$A/${A}_auto.patch.osm | cut -c1-16)" >> $S/small.txt
done
touch $S/small.DONE
