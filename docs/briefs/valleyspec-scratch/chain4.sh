#!/bin/zsh
W=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/valleyspec
SECONDS=0; until grep -q CHAIN3_DONE $W/.progress; do [ $SECONDS -gt 1500 ] && { echo TIMED_OUT >> $W/.progress; exit 3; }; sleep 15; done
export FV_CAP=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/sweepwalls/base/KCLT.pkl
$W/arm.sh k_xs1f KCLT xsec:1,xfall:0.3,qp_tight:1e-12
$W/arm.sh k_xs1f_slack KCLT xsec:1,xfall:0.3,qp_tight:1e-12,slack:$W/k_xs1f:0.05:30
echo CHAIN4_DONE >> $W/.progress
