# Triangle4XP (Triangle 1.6 by J. R. Shewchuk, modified by Oscar Pilote for
# Ortho4XP; the modifications since are listed in Triangle4XP-CHANGES.md).
# Under Triangle's own licence, not the GPL (LICENSING.md §3, §6).
#
#   cmake -S Utils -B build && cmake --build build --config Release
#
# The platform options follow OrthoStudio XP's native/triangle4xp/CMakeLists.txt
# (radioharris, 7c028d82d), adapted.  Floating-point contraction is left at the
# compiler default on purpose: the shipped macOS binary was built that way
# (cc -O2 -arch arm64 -arch x86_64 ... -lm) and only that setting reproduces
# its meshes bit for bit.  Fast-math stays off: Triangle's exact predicates
# need IEEE doubles.
cmake_minimum_required(VERSION 3.13)
cmake_policy(VERSION 3.13)

project(Ortho4XP VERSION 1.4 LANGUAGES C)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()
if(APPLE AND NOT CMAKE_OSX_ARCHITECTURES)
  set(CMAKE_OSX_ARCHITECTURES "arm64;x86_64" CACHE STRING "Universal binary" FORCE)
endif()

set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
set(CMAKE_VERBOSE_MAKEFILE OFF)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE OFF)

add_executable(Triangle4XP src/Triangle4XP.c)
# <build>/Triangle4XP(.exe) whatever the generator, Visual Studio included
set_target_properties(Triangle4XP PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}"
  RUNTIME_OUTPUT_DIRECTORY_RELEASE "${CMAKE_BINARY_DIR}"
  RUNTIME_OUTPUT_DIRECTORY_DEBUG "${CMAKE_BINARY_DIR}")
if(MSVC)
  # no <sys/time.h> (Triangle's -V timings) and no separate maths library
  target_compile_definitions(Triangle4XP PRIVATE NO_TIMER _CRT_SECURE_NO_WARNINGS)
  target_compile_options(Triangle4XP PRIVATE /fp:precise)
else()
  target_compile_options(Triangle4XP PRIVATE -fno-fast-math)
  if(CMAKE_C_COMPILER_ID MATCHES "GNU")
    target_compile_options(Triangle4XP PRIVATE -fexcess-precision=standard)
  endif()
  target_link_libraries(Triangle4XP m)
endif()
