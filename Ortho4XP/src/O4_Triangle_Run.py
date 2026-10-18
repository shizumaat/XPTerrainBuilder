"""Run the stock ``triangle`` binary (``-pAYPQ``) on a ``<name>.poly``:
``triangulate`` — the masks step's and the imagery step's small
triangulations (the tile mesh itself runs Triangle4XP in
``O4_Mesh_Utils``).

Moved out of ``O4_Mesh_Utils`` (#836): the masks step imported the whole
mesh module for this one function.
"""
from __future__ import annotations

import os
import subprocess
import sys

import O4_Console_Encoding as CONSOLE
import O4_File_Names as FNAMES
import O4_UI_Utils as UI

__all__ = ["triangulate", "triangle_cmd"]

if "dar" in sys.platform:
    triangle_cmd = os.path.join(FNAMES.Utils_dir, "mac", "triangle ")
elif "win" in sys.platform:
    triangle_cmd = os.path.join(FNAMES.Utils_dir, "win", "triangle.exe ")
else:
    triangle_cmd = os.path.join(FNAMES.Utils_dir, "lin", "triangle ")


def triangulate(name, path_to_Ortho4XP_dir):
    Tri_option = " -pAYPQ "
    mesh_cmd = [
        os.path.join(path_to_Ortho4XP_dir, triangle_cmd).strip(),
        Tri_option.strip(),
        name + ".poly",
    ]
    fingers_crossed = subprocess.Popen(
        mesh_cmd, stdout=subprocess.PIPE, bufsize=0, **UI.external_tool_keyword_arguments()
    )
    while True:
        line = fingers_crossed.stdout.readline()
        if not line:
            break
        else:
            print(CONSOLE.native_tool_text(line)[:-1])
    fingers_crossed.poll()
    if fingers_crossed.returncode:
        print("\nERROR: triangle crashed, check osm mask data.\n")
        UI.tile_failure("mesh_failed", "triangle crashed")
        return 0
    return 1
