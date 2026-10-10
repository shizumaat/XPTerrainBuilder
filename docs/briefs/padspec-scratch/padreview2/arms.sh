#!/bin/zsh
# padreview2 intervention arms (the sweepwalls method): lane code (claude/pads56 132116b1) with ONE law group disarmed per arm,
# replayed from the MAIN-era capture sweepwalls/base/<ICAO>.pkl (--from classify), whose main-code replay == swg_<ICAO> (0 movers, arm_Z2).
#   F   = lane as is (full)                      O0 = outline keys 0 (close/chord/hole)
#   A0  = pad_road_absorb_m 0                    OA0 = both 0  (what is left = collar deletion + 4F + F1b + F2 + hygiene)
# usage: arms.sh ICAO ARM...
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padreview2
CAP=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/sweepwalls/base/$1.pkl
T=/Users/noah/XPTerrainBuilder/.claude/worktrees/padspec/Ortho4XP
L=src/auto_patch_v2/law/structures.toml
A=$1; shift
cd $T || exit 2
unsetopt bg_nice 2>/dev/null
for arm in "$@"; do
  git checkout -q -- $L
  case $arm in
    O0)  sed -i '' '502s/= 3.0 /= 0.0 /;503s/= 1.0 /= 0.0 /;504s/= 200.0/= 0.0  /' $L;;
    A0)  sed -i '' '505s/= 10.0 /= 0.0  /' $L;;
    OA0) sed -i '' '502s/= 3.0 /= 0.0 /;503s/= 1.0 /= 0.0 /;504s/= 200.0/= 0.0  /;505s/= 10.0 /= 0.0  /' $L;;
    C0)  sed -i '' '503s/= 1.0 /= 0.0 /' $L;;
    F) ;;
  esac
  D=$S/arm_$arm; mkdir -p $D
  git diff -- $L | grep '^[-+]' | grep -v '^[-+][-+]' > $D/$A.lawdiff.txt
  echo "arm $arm $A start $(date)" >> $S/.progress
  venv/bin/python tools/v2_solve_replay.py --replay $CAP --from classify --emit $D/${A}_emit --verify --solved-out $D/$A.solved.pkl --workers 6 > $D/$A.rep.log 2>&1
  echo "arm $arm $A rc=$? $(date)" >> $S/.progress
  git checkout -q -- $L
  venv/bin/python tools/airside_value_delta.py /tmp/harness/swg_$A.osm $D/${A}_emit/${A}_auto.patch.osm --tol 0.02 --top 15 --json $D/avd_$A.json > $D/avd_$A.txt 2>&1
done
git status --short -- $L
