"""
Plugin system for Basic GUI Application

This package contains the plugin system for the Basic GUI Application.
"""

from GUI.plugin_system import BaseTabPlugin, CoreTabPlugin, PluginRegistry, plugin_registry
from . import base as _legacy_base  # noqa: F401

__all__ = [
    "BaseTabPlugin",
    "CoreTabPlugin",
    "PluginRegistry",
    "plugin_registry",
]