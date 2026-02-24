"""
Backward compatibility shim for the base plugin module.

This module provides backward compatibility for plugins that import from
`GUI.plugins.base`. It re-exports the classes and objects from the new
`GUI.plugin_system.base` module.
"""

from __future__ import annotations

from GUI.plugin_system import BaseTabPlugin, CoreTabPlugin, PluginRegistry, plugin_registry

__all__ = [
    "BaseTabPlugin",
    "CoreTabPlugin",
    "PluginRegistry",
    "plugin_registry",
]
