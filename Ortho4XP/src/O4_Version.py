# Ortho4XP engine version, MAJOR.MINOR.BUILD. scripts/make_engine.sh bumps
# the build component on every freeze, so a frozen engine traces back to the
# commit that produced it. Nothing else may move it.
#
# Keep this file to comments plus the single assignment below, and keep no
# "equals" sign in the comments: the PyInstaller specs, the freeze script,
# the schema dumper and the mac app all read the version textually rather
# than importing it, and their parsers are pinned by
# tests/test_version_scheme.py.
version='1.50.1683'
