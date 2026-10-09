#!/bin/zsh
# usage: null.sh A B ICAO — the null-change read: per-stage diff, movers by role, avd (no census)
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad; W=$S/valleyspec
A=$1; B=$2; I=$3; M=$W/m_${A}_${B}; mkdir -p $M
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/valleyspec/Ortho4XP || exit 2
P=venv/bin/python
$P $W/cmp.py $W/$A $W/$B > $M/cmp.txt 2>&1
for k in 0 1; do echo "== stage call $k ($A -> $B)"; $P $W/mv.py $W/$A $W/$B $k $W/$A/solved.pkl; done > $M/mv.txt 2>&1
$P tools/airside_value_delta.py $W/$A/emit/${I}_auto.patch.osm $W/$B/emit/${I}_auto.patch.osm --tol 0.02 --json $M/avd.json > $M/avd.txt 2>&1
grep "MOVED by\|by family" $M/avd.txt | head -3
