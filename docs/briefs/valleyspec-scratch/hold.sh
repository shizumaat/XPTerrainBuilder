#!/bin/zsh
# bounded hold: FREEZE/TIMING windows always; else while MORE THAN ${FV_FOREIGN_MAX:-1} foreign engine
# python processes are burning CPU (strict hold starved 25 min: three lanes overlap continuously)
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad
busy() {
  for f in $S/FREEZE*_START(N) $S/TIMING*_START(N); do [ -e ${f%_START}_DONE ] || return 0; done
  n=$(ps -Ao pcpu,command | grep -E '[Pp]ython.*(build_airport.py|v2_solve_replay.py|pack_stage_profile.py|run_tile_mesh|nullarm.py)' | grep -v valleyspec | awk '$1>50' | wc -l)
  [ ${n:-0} -gt ${FV_FOREIGN_MAX:-1} ] && return 0
  return 1
}
while busy; do [ $SECONDS -gt ${1:-2400} ] && { echo TIMED_OUT; exit 3; }; sleep 20; done
exit 0
