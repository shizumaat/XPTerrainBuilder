#!/bin/zsh
W=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/valleyspec
export FV_CAP=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/sweepwalls/base/KCLT.pkl
# k_ctl kept
$W/arm.sh k_xs KCLT xsec:30,qp_tight:1e-12
$W/arm.sh k_xs_slack KCLT xsec:30,qp_tight:1e-12,slack:$W/k_xs:0.05:30
echo CHAIN1_DONE >> $W/.progress
