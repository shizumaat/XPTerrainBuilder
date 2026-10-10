#!/bin/zsh
S=/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padfix
cd /Users/noah/XPTerrainBuilder/.claude/worktrees/padfix/Ortho4XP
echo "== suite START $(date +%T)" >> $S/.progress
venv/bin/python -m pytest -q -n auto --ignore-glob='tests/test_qt_*.py' tests > $S/suite.log 2>&1; echo "nonqt rc=$?" >> $S/suite.rc
venv/bin/python -m pytest -q -n0 tests/test_qt_*.py > $S/qt.log 2>&1; echo "qt rc=$?" >> $S/suite.rc
venv/bin/python -m pytest -q -n0 tests/test_console_encoding.py tests/test_windows_text_io.py tests/test_v1_retired.py tests/test_no_airport_specific_code.py > $S/named.log 2>&1; echo "named rc=$?" >> $S/suite.rc
venv/bin/python ../tools/ratchets.py > $S/ratchets.log 2>&1; echo "ratchets rc=$?" >> $S/suite.rc
echo "== suite EXIT $(date +%T)" >> $S/.progress; touch $S/suite.DONE
