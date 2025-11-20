"""
Plugin system for Basic GUI Application

This package contains the plugin system for the Basic GUI Application.
"""

from .base import BaseTabPlugin, CoreTabPlugin
from .registry import PluginRegistry, plugin_registry

__all__ = [
    "BaseTabPlugin",
    "CoreTabPlugin",
    "PluginRegistry",
    "plugin_registry",
]