# Lane c2186: a failed object stage must reach the build result (#2186, #2226)

Read `common.md`. `auto_patch/object_stage.py:1408` appears to log and count a failure and continue, with no
path to the build outcome, so a user can fly floating buildings on a build marked OK. That is a search
result: trace it end to end first. Fix: a failed object stage reaches the tile's result and the failure table
in both UIs, through the existing failure catalogue. For #2226, list every place a tile step can fail without
reaching the result, fix the ones in this path, and list the rest in the PR. Tests: a synthetic stage failure
produces a non-OK outcome and the user's message.
