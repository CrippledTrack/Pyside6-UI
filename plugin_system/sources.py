"""
Plugin discovery source models.

This module provides a small, explicit model for the *intended* plugin sources
we support in-repo (app_plugins/, platforms/, and built-in GUI/plugins).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PluginSource:
    """A package-based plugin source.

    Attributes:
        source_id: Stable identifier used for logs.
        package: Importable Python package path to scan (e.g. "app_plugins.linux.plugins").
        priority: Higher priority sources should win on conflicts.
    """

    source_id: str
    package: str
    priority: int


__all__ = ["PluginSource"]

