#!/bin/zsh
W=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/valleyspec
export FV_CAP=/Users/noah/XPTerrainBuilderData/.harness/frames/gapapron3/HECA.pkl
$W/arm.sh h_xs1g_slackF HECA xsec:1,xfall:1,qp_tight:1e-12,slack:$W/h_xs1g:0.05:30,force:$W/h_xs1g
echo CHAIN8_DONE >> $W/.progress
