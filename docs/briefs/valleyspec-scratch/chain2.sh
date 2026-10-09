#!/bin/zsh
W=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/valleyspec
SECONDS=0; until grep -q CHAIN1_DONE $W/.progress; do [ $SECONDS -gt 1800 ] && { echo TIMED_OUT >> $W/.progress; exit 3; }; sleep 20; done
export FV_CAP=/Users/noah/XPTerrainBuilderData/.harness/frames/gapapron3/HECA.pkl
$W/arm.sh h_ctl HECA ""
$W/arm.sh h_xs HECA xsec:30,qp_tight:1e-12
$W/arm.sh h_xs_slack HECA xsec:30,qp_tight:1e-12,slack:$W/h_xs:0.05:30
echo CHAIN2_DONE >> $W/.progress
