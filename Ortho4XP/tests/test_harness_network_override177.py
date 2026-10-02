"""THE HARNESS MUST NOT DISARM THE SUITE'S NETWORK GUARD — issue #177.

``build_airport.main()`` carried
``os.environ.setdefault("O4_SUITE_ALLOW_NETWORK", "1")`` — lane las130's
CONSUMER-SIDE workaround for #146 (RULINGS 2026-09-30ay), when importing
``tests/conftest.py`` for ``xplane_root`` armed #122's socket-level
network refusal in the importing process.

#146 fixed that AT THE DERIVATION SITE: the guard arms only under
``running_under_pytest()``.  So the setdefault was redundant — and it was
a residual hole, because it wrote the variable into the PROCESS
ENVIRONMENT, which any pytest subprocess spawned from a build inherits
with the suite's guard explicitly DISARMED.  That is precisely the
Windows 600 s hang class #122 exists to prevent (a live Overpass request
waits timeout + 30 s and retries 8x).

Both halves are pinned here, and both are OFFLINE: the harness no longer
names the variable, and conftest's #146 gate really does leave a
NON-pytest process its network.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tools" / "harness"

#: The suite's explicit network override — the variable that must not be
#: written into any process environment by a harness entry.
OVERRIDE_VARIABLE = "O4_SUITE_ALLOW_NETWORK"


def test_no_harness_entry_writes_the_suite_network_override():
    """A harness entry may READ the variable; writing it into the process
    environment leaks a disarmed guard into every pytest subprocess."""
    offenders = []
    for path in sorted(HARNESS.glob("*.py")):
        for n, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            bare = line.strip()
            if bare.startswith("#") or OVERRIDE_VARIABLE not in bare:
                continue
            if ("environ[" in bare or "setdefault(" in bare
                    or "setenv(" in bare or "putenv(" in bare):
                offenders.append(f"{path.name}:{n}: {bare}")
    assert offenders == [], offenders


def test_the_146_gate_leaves_a_NON_pytest_process_its_network():
    """VERIFIED BY READING THE GATE, in a process that is not pytest.

    ``tests/conftest.py`` arms the #122 guard only
    ``if running_under_pytest() and <override> != "1"``, and
    ``running_under_pytest()`` is frozen BEFORE conftest imports pytest
    itself.  So a tool that imports conftest for ``xplane_root`` keeps
    its sockets AND its proxy variables — which is what makes the
    harness's own ``setdefault`` redundant (#177).

    A SUBPROCESS, deliberately: inside the suite the answer is the other
    one.  No network is touched — the probe only reads the flags the
    import set.
    """
    probe = (
        "import sys, socket, json\n"
        "assert 'pytest' not in sys.modules, 'the probe must not be pytest'\n"
        f"sys.path.insert(0, {str(ROOT / 'tests')!r})\n"
        "import conftest\n"
        "print(json.dumps({\n"
        "  'under_pytest': conftest.running_under_pytest(),\n"
        "  'armed_at_import': conftest._GUARD_ARMED_AT_IMPORT,\n"
        "  'socket_patched': getattr(\n"
        "      socket, '_o4_suite_network_guard', False),\n"
        "}))\n")
    done = subprocess.run([sys.executable, "-c", probe], cwd=str(ROOT),
                          capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin",
                               "HOME": str(ROOT)})
    assert done.returncode == 0, done.stderr[-2000:]
    answer = json.loads(done.stdout.strip().splitlines()[-1])
    assert answer == {"under_pytest": False, "armed_at_import": False,
                      "socket_patched": False}, answer
    # ...and the gate is the ONE condition, read from the source
    src = (ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")
    assert ("if running_under_pytest() and \\\n"
            f"        os.environ.get(\"{OVERRIDE_VARIABLE}\", \"0\") != \"1\":"
            in src), "the #146 gate moved — re-read it before trusting #177"


def test_main_says_WHY_the_override_is_gone():
    """The removal must carry its reason, or the next lane re-adds it
    the next time a conftest import looks like an outage."""
    build_mod = None
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "harness_net177_build", HARNESS / "build_airport.py")
    build_mod = importlib.util.module_from_spec(spec)
    sys.modules["harness_net177_build"] = build_mod
    spec.loader.exec_module(build_mod)
    src = inspect.getsource(build_mod.main)
    assert "#177" in src and OVERRIDE_VARIABLE in src
    for forbidden in (f'setdefault("{OVERRIDE_VARIABLE}"',
                      f'environ["{OVERRIDE_VARIABLE}"]'):
        assert forbidden not in src, forbidden
