"""#2303 / #2200: the pack questions are answered beside the transport's
serial loop, never behind a build's slow command (view_lane.PACK_COMMANDS).

With tiles building, Pack choices… and a Modified-airports row's Adjust…
reached the engine behind whatever the serial loop was doing, so the
button did nothing; the read-only report must not wait for builds.
"""

import io
import json
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import jsonl  # noqa: E402
from o4_engine import view_lane  # noqa: E402


class _Capture(io.StringIO):
    def objects(self):
        return [json.loads(line) for line in self.getvalue().splitlines()
                if line.strip()]


def test_pack_adjust_is_answered_while_a_build_command_holds_the_session(monkeypatch):
    from auto_patch import adjust_edit, adjust_stage

    reported = threading.Event()
    monkeypatch.setattr(adjust_edit, "tile_state", lambda root: {})
    monkeypatch.setattr(adjust_stage, "adjust_choice",
                        lambda *a, **kw: (reported.set(), {})[1])
    answered = threading.Event()
    real_build = jsonl._build_handlers

    def build(session):
        handlers = real_build(session)
        real_adjust = handlers["pack_adjust"]
        handlers["pack_adjust"] = (
            lambda **kw: (lambda out: (answered.set(), out)[1])(real_adjust(**kw)))

        def held_by_a_build():
            # what a build's enqueue does: the session's command lock held
            # while the serial loop is busy with it
            with session._command_lock:
                return {"answered_first": answered.wait(5.0)}

        handlers["zz_build_busy"] = held_by_a_build
        return handlers

    monkeypatch.setattr(jsonl, "_build_handlers", build)
    assert "pack_adjust" in view_lane.PACK_COMMANDS
    commands = [{"cmd": "zz_build_busy", "id": 1},
                {"cmd": "pack_adjust", "id": 2, "pack_root": "/nowhere/LXYZ pack",
                 "action": "adjust", "lat": 39, "lon": 19},
                {"cmd": "shutdown", "id": 3}]
    capture = _Capture()
    jsonl.serve(io.StringIO("\n".join(json.dumps(c) for c in commands) + "\n"),
                capture)
    replies = {o["reply"]: o for o in capture.objects() if "reply" in o}
    assert replies[1]["result"] == {"answered_first": True}
    assert replies[2]["result"] == {"status": "started"}
    order = [o["reply"] for o in capture.objects() if "reply" in o]
    assert order.index(2) < order.index(1)
    assert reported.wait(5.0)


def test_every_pack_question_and_answer_takes_the_pack_lane():
    lane = view_lane.ViewLane()
    for command in ("pack_overlaps", "pack_adjust", "pack_forests",
                    "pack_optimise", "pack_readonly"):
        assert lane.takes(command)
    assert not lane.takes("enqueue_build")
