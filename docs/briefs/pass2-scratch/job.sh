#!/bin/zsh
# job.sh TAG CMD... — one heavy job, stamped in .progress; waits (bounded, 1 h) while another job holds the lock
TAG=$1; shift
until mkdir /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/.lock 2>/dev/null || [ $SECONDS -gt 3600 ]; do sleep 10; done
[ $SECONDS -gt 3600 ] && { echo "== $TAG TIMED_OUT waiting lock" >> /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/.progress; exit 9; }
echo "== $TAG START $(date +%T)" >> /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/.progress
"$@" > /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/$TAG.log 2>&1; rc=$?
echo "== $TAG rc $rc $(date +%T)" >> /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/.progress; touch /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/$TAG.DONE; rmdir /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/pass2/.lock
