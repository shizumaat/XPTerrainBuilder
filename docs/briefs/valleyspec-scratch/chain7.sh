#!/bin/zsh
W=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/valleyspec
SECONDS=0; until grep -q "arm h_ctl HECA rc" $W/.progress; do [ $SECONDS -gt 900 ] && { echo TIMED_OUT >> $W/.progress; exit 3; }; sleep 15; done
pkill -f "arm.sh h_xs1f" 2>/dev/null; pkill -f "FV_OUT=$W/h_xs1f" 2>/dev/null
export FV_CAP=/Users/noah/XPTerrainBuilderData/.harness/frames/gapapron3/HECA.pkl
$W/arm.sh h_xs1g HECA xsec:1,xfall:1,qp_tight:1e-12
$W/arm.sh h_xs1g_slack HECA xsec:1,xfall:1,qp_tight:1e-12,slack:$W/h_xs1g:0.05:30
echo CHAIN7_DONE >> $W/.progress
