#!/bin/zsh
# pads61 arms (the padreview2 method): lane code with the R-W pin, replayed from a main-era capture --from classify.
#   P = lane as is (pin on, everything)   PA0 = pad_road_absorb_m 0   OA0 = outline + absorb keys 0   F0 = pin off is the padreview2 arm_F
# usage: arms.sh ICAO CAPTURE MAINPATCH ARM...
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pads61
T=/Users/noah/XPTerrainBuilder/.claude/worktrees/padspec/Ortho4XP
L=src/auto_patch_v2/law/structures.toml
A=$1; CAP=$2; MAIN=$3; shift 3
cd $T || exit 2
unsetopt bg_nice 2>/dev/null
for arm in "$@"; do
  git checkout -q -- $L
  case $arm in
    PA0) sed -i '' '505s/= 10.0 /= 0.0  /' $L;;
    OA0) sed -i '' '502s/= 3.0 /= 0.0 /;503s/= 1.0 /= 0.0 /;504s/= 200.0/= 0.0  /;505s/= 10.0 /= 0.0  /' $L;;
    P*) ;;
  esac
  D=$S/arm_$arm; mkdir -p $D
  git diff -- $L | grep '^[-+]' | grep -v '^[-+][-+]' | cut -c1-40 > $D/$A.lawdiff.txt
  echo "arm $arm $A start $(date)" >> $S/.progress
  venv/bin/python tools/v2_solve_replay.py --replay $CAP --from classify --emit $D/${A}_emit --verify --solved-out $D/$A.solved.pkl --workers 6 > $D/$A.rep.log 2>&1
  echo "arm $arm $A rc=$? $(date)" >> $S/.progress
  git checkout -q -- $L
  venv/bin/python tools/airside_value_delta.py $MAIN $D/${A}_emit/${A}_auto.patch.osm --tol 0.02 --top 15 --json $D/avd_$A.json > $D/avd_$A.txt 2>&1
done
git status --short -- $L
