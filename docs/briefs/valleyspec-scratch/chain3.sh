#!/bin/zsh
W=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/valleyspec
SECONDS=0; until grep -q CHAIN1_DONE $W/.progress; do [ $SECONDS -gt 900 ] && { echo TIMED_OUT >> $W/.progress; exit 3; }; sleep 15; done
export FV_CAP=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/sweepwalls/base/KCLT.pkl
$W/arm.sh k_xs1 KCLT xsec:1,qp_tight:1e-12
$W/arm.sh k_xs3 KCLT xsec:3,qp_tight:1e-12
echo CHAIN3_DONE >> $W/.progress
