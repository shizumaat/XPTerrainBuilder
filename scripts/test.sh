#!/bin/zsh
# Run the SceneryKit unit tests.
#
# When building with Command Line Tools (no Xcode), swift-testing's
# Testing.framework and its interop dylib are not on the default runtime
# search path, so we pass explicit framework/rpath flags and use the classic
# build system (the new swiftbuild one drops the testing macro plugin path on
# incremental rebuilds). With full Xcode installed, plain `swift test` works.
set -euo pipefail

CLT=/Library/Developer/CommandLineTools
FW="$CLT/Library/Developer/Frameworks"
LIB="$CLT/Library/Developer/usr/lib"

if [[ -d "$FW/Testing.framework" && ! -d /Applications/Xcode.app ]]; then
  exec swift test --build-system native \
    -Xswiftc -F"$FW" -Xlinker -F"$FW" \
    -Xlinker -rpath -Xlinker "$FW" \
    -Xlinker -rpath -Xlinker "$LIB" "$@"
else
  exec swift test "$@"
fi
