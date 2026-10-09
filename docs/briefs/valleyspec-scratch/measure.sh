#!/bin/zsh
# usage: measure.sh A B ICAO   — per-stage diff, stage-1 movers by role, avd, census (+rows), rows diff, all under $W/m_A_B/
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad; W=$S/valleyspec
A=$1; B=$2; I=$3; M=$W/m_${A}_${B}; mkdir -p $M
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/valleyspec/Ortho4XP || exit 2
P=venv/bin/python
$P $W/cmp.py $W/$A $W/$B > $M/cmp.txt 2>&1
for k in 0 1; do echo "== stage call $k ($A -> $B)"; $P $W/mv.py $W/$A $W/$B $k $W/$A/solved.pkl; done > $M/mv.txt 2>&1
$P tools/airside_value_delta.py $W/$A/emit/${I}_auto.patch.osm $W/$B/emit/${I}_auto.patch.osm --tol 0.02 --json $M/avd.json > $M/avd.txt 2>&1
for T in $A $B; do
  [ -f $W/census_$T.json ] || $P tools/harness/census.py $W/$T/emit/${I}_auto.patch.osm --json $W/census_$T.json --rows-json $W/rows_$T.json --quiet > $W/census_$T.txt 2>&1
done
$P tools/census_rows_diff.py $W/rows_$A.json $W/rows_$B.json --side airside --top 12 --json $M/rowsdiff.json > $M/rowsdiff.txt 2>&1
$P - <<PY > $M/summary.txt
import json
a=json.load(open("$W/census_$A.json")); b=json.load(open("$W/census_$B.json"))
def g(j,*ks):
    for k in ks: j=j[k]
    return j
print("adjudicated airside (for acceptance): $A", a["adjudicated_airside_for_acceptance"], " $B", b["adjudicated_airside_for_acceptance"])
print("adjudicated by side:", g(a,"adjudication","adjudicated_by_side"), g(b,"adjudication","adjudicated_by_side"))
fa=g(a,"cockpit","report","by_family"); fb=g(b,"cockpit","report","by_family")
print("families that differ:", {k:(fa.get(k,0),fb.get(k,0)) for k in set(fa)|set(fb) if fa.get(k,0)!=fb.get(k,0)})
ca=g(a,"cockpit","by_family"); cb=g(b,"cockpit","by_family")
print("CRITICAL motion/visual that differ:", {k+"."+m:(ca[k][m],cb.get(k,{}).get(m)) for k in ca for m in ("critical_motion","critical_visual") if ca[k][m]!=cb.get(k,{}).get(m)})
av=json.load(open("$M/avd.json"))["frames"]["row-side"]["families"]
print("avd row-side by family:", {k:(v["n"],v["worst_dz_m"]) for k,v in av.items()})
PY
echo "measured $A $B -> $M $(date)" >> $W/.progress
