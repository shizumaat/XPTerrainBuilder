#!/bin/zsh
W=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/valleyspec
export FV_CAP=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/sweepwalls/base/KCLT.pkl
$W/arm.sh k_xs1g KCLT xsec:1,xfall:1,qp_tight:1e-12
$W/arm.sh k_xs1g_slack KCLT xsec:1,xfall:1,qp_tight:1e-12,slack:$W/k_xs1g:0.05:30
echo CHAIN6_DONE >> $W/.progress
