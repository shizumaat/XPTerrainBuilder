"""``build_masks`` reports a finished step as 1 (#904).

The engine session records a tile step as finished (and so reusable, and
resumable after a Stop) only when its result ``== 1``
(``o4_engine/session.py`` ``_build_worker``).  ``build_masks`` ended with a
bare ``return`` (None), so the masks step was never recorded and every
rebuild and resume re-ran it.  The step needs a tile's data to run, so this
twin reads the function itself: every ``return`` at its own level (not in
a nested helper) returns the literal 0 or 1, and its last statement is
``return 1``.
"""

import ast
import os

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "O4_Mask_Utils.py")


def _own_returns(func: ast.FunctionDef):
    """The ``return`` statements of ``func`` itself, nested defs skipped."""
    stack = list(func.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return):
            yield node
        stack.extend(ast.iter_child_nodes(node))


def test_build_masks_returns_0_or_1_never_none():
    with open(SRC, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    (func,) = [n for n in tree.body
               if isinstance(n, ast.FunctionDef) and n.name == "build_masks"]
    values = [getattr(r.value, "value", r.value) for r in _own_returns(func)]
    assert values, "build_masks has no return"
    assert all(v in (0, 1) for v in values), values
    last = func.body[-1]
    assert isinstance(last, ast.Return) and getattr(last.value, "value", None) == 1
