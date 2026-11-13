"""#2055: a launch scan's ~10 Hz batches reach the screen at most once per
second.  Twin of ``Tests/SceneryKitTests/ScanStreamThrottleTests.swift``:
both feed ``fixtures/scan_stream_throttle_cases.json`` to a fresh
throttle."""
from __future__ import annotations

import json
from pathlib import Path

import O4_Scan_Stream_Throttle as THROTTLE

CASES = Path(__file__).parent / "fixtures" / "scan_stream_throttle_cases.json"


def test_the_shared_cases():
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    assert cases
    for case in cases:
        throttle = THROTTLE.ScanStreamThrottle(case["interval"])
        for step in case["steps"]:
            if step.get("reset"):
                throttle.reset()
            else:
                assert throttle.should_publish(step["at"]) is step["publish"], case["name"]


def test_a_25_s_scan_at_10_hz_publishes_about_25_times():
    throttle = THROTTLE.ScanStreamThrottle()
    published = [t / 10 for t in range(250) if throttle.should_publish(t / 10)]
    assert published[0] == 0.0 and 24 <= len(published) <= 26
