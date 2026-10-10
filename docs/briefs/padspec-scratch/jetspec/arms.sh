#!/bin/zsh
# jetspec: base (unpatched) and BAYS arm replays --from planar on one capture; then the airside read.
# usage: arms.sh ICAO CAP.pkl   (from Ortho4XP/)
set -u
A=$1; CAP=$2
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/jetspec
P=../docs/briefs/padspec-scratch/jetspec/replay_bays.py
for arm in base bays; do
  D=$S/arm_${arm}_$A; mkdir -p $D
  echo "$(date) arm $arm $A start" >> $S/.progress
  if [ $arm = base ]; then export JETSPEC_BAYS=0; else export JETSPEC_BAYS=1; fi
  venv/bin/python $P --replay $CAP --from planar --emit $D/emit --verify --workers 6 > $D/rep.log 2>&1
  echo "$(date) arm $arm $A rc=$?" >> $S/.progress
done
venv/bin/python tools/airside_value_delta.py $S/arm_base_$A/emit/${A}_auto.patch.osm $S/arm_bays_$A/emit/${A}_auto.patch.osm --tol 0.02 --top 15 --json $S/avd_$A.json > $S/avd_$A.txt 2>&1
echo "$(date) avd $A done" >> $S/.progress
