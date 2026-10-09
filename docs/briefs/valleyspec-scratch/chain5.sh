#!/bin/zsh
W=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/valleyspec
SECONDS=0; until grep -q CHAIN4_DONE $W/.progress; do [ $SECONDS -gt 1500 ] && { echo TIMED_OUT >> $W/.progress; exit 3; }; sleep 15; done
export FV_CAP=/Users/noah/XPTerrainBuilderData/.harness/frames/gapapron3/HECA.pkl
$W/arm.sh h_ctl HECA ""
$W/arm.sh h_xs1f HECA xsec:1,xfall:0.3,qp_tight:1e-12
$W/arm.sh h_xs1f_slack HECA xsec:1,xfall:0.3,qp_tight:1e-12,slack:$W/h_xs1f:0.05:30
echo CHAIN5_DONE >> $W/.progress
