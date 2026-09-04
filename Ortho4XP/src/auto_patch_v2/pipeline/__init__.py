"""Orchestration, CLI, config (plan §1 row ``pipeline``)."""
from .build import Config, DEFAULT_WEIGHTS, BuildResult, build

__all__ = ["Config", "DEFAULT_WEIGHTS", "BuildResult", "build"]
