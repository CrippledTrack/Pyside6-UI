"""
Core plugins registry for bundling and deterministic registration.

Purpose:
- Provide a single place to statically import core plugin classes so tools
  like PyInstaller can detect and bundle them.
- Return a list of core plugin classes for early registration.

Usage:
- Import your core plugin classes below and add them to CORE_PLUGINS.
- Being listed here is sufficient to treat a plugin as core (for registration and UI).
- Optionally set `is_core_plugin = True` on the class for clarity; not required.
"""

from __future__ import annotations

from typing import List, Type

from .base import BaseTabPlugin

# Example (uncomment and replace with real imports):
# from app.ui.some_core_tab import SomeCoreTabPlugin


CORE_PLUGINS: List[Type[BaseTabPlugin]] = [
    # SomeCoreTabPlugin,
]


def get_core_plugins() -> List[Type[BaseTabPlugin]]:
    return CORE_PLUGINS


__all__ = ['get_core_plugins']