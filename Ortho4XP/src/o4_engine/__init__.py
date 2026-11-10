"""o4_engine — the Controller layer of Ortho4XP's one-engine / many-views
architecture (docs/specs/engine-protocol-multi-gui.md).

Views import :class:`o4_engine.session.EngineSession` and the event types
(``o4_engine.events``); core pipeline modules never import the session
(they reach it through the ``O4_UI_Utils.engine_session`` attribute the
session registers).

THIS FILE IMPORTS NOTHING (#1901): the tile core imports two leaf meters
from this package (``download_meter``, ``task_meter``), and Python runs
this ``__init__`` first.  When it loaded the session, the patch build's
code key (``auto_patch.provenance_code``, which follows package inits as
Python runs them) reached the whole app — the object stage included — so
a change to the pack writer re-solved every airport's terrain.
"""
