"""The modules ``tools/check_grade.py`` is cut into (issue #857; spec
``code-quality-beta3-spec.md`` §3).

``check_grade.py`` stays THE harness library and re-exports every name
moved here, so ``import check_grade`` / ``from check_grade import X`` and
every by-path load of ``tools/check_grade.py`` keep working unchanged.
Import these modules through ``check_grade``; they may never import it
back (a by-path load would then execute a second copy).

* :mod:`.rows` — the row and way records every family emits.
* :mod:`.context` — the sidecar law context (the frame, the sidecar keys,
  ``law_context_from_sidecar``).
* :mod:`.families` — one module per law family: its check(s) and its
  ``LAW_FAMILY_ROWS``, spliced into ``check_grade.LAW_FAMILIES`` at its
  emission position.
"""
