#!/bin/zsh
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad
busy() { pgrep -f 'label harness-build' >/dev/null; }
n=0; while [ $n -lt 240 ]; do grep -q "avd OTHH done" $S/jetspec/.progress && break; sleep 15; n=$((n+1)); done
[ $n -ge 240 ] && { echo "$(date) TIMED_OUT waiting for OTHH" >> $S/jetspec/.progress; exit 1; }
m=0; while busy && [ $m -lt 120 ]; do sleep 15; m=$((m+1)); done
../docs/briefs/padspec-scratch/jetspec/arms.sh HECA /Users/noah/XPTerrainBuilderData/.harness/frames/gaps3/HECA.pkl
m=0; while busy && [ $m -lt 120 ]; do sleep 15; m=$((m+1)); done
../docs/briefs/padspec-scratch/jetspec/arms.sh KCLT $S/sweepwalls/base/KCLT.pkl
echo "$(date) ALL ARMS DONE" >> $S/jetspec/.progress
